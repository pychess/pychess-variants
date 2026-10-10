import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { GameController } from '../../gameCtrl';
import { BugBoardName, PyChessModel } from '../../types';
import type { TwoBoardController } from '../twoBoardCtrl';
import { premove } from 'chessgroundx/premove';
import { predrop } from 'chessgroundx/predrop';
import { uci2LastMove } from '@/chess';

export class GameControllerBughouse extends GameController {
    /* Narrowed from the base's `BoardName`, which carries the single-board page's `''`. A
       bughouse controller is constructed with `'a'` or `'b'` — see the constructor below — so
       callers that key something on the board (a PV column, a gauge, a stack) do not each have
       to re-narrow a case that cannot arise. */
    declare boardName: BugBoardName;

    partnerCC: GameControllerBughouse;
    parent: TwoBoardController;
    localAnalysis: boolean = false;

    isCheck: boolean;
    lastmove: cg.Orig[] | undefined;

    constructor(
        el: HTMLElement,
        elPocket1: HTMLElement,
        elPocket2: HTMLElement,
        boardName: BugBoardName,
        model: PyChessModel,
    ) {
        super(
            el,
            model,
            boardName === 'a' ? model.fen.split(' | ')[0] : model.fen.split(' | ')[1],
            elPocket1,
            elPocket2,
            boardName,
        );
        this.setGround();
        this.mycolor = 'white';
    }

    doSendMove(move: string) {
        this.ply++;
        this.parent.sendMove(this, move);
    }

    onUserDrop = (piece: cg.Piece, dest: cg.Key, meta: cg.MoveMetadata) => {
        console.log(piece, dest, meta);
        this.preaction = meta.premove;
        this.sendMove(util.dropOrigOf(piece.role), dest, '');
        this.preaction = false;
    };

    onSelect = () => {
        return (key: cg.Key) => {
            console.log(key);
        };
    };

    performPremove = () => {
        // const { orig, dest, meta } = this.premove;
        // todo: once premove+promotion bug is fixed for regular variants, apply here as well
        // console.log("performPremove()", orig, dest, meta);
        this.chessground.playPremove();
    };

    onUserMove = (orig: cg.Key, dest: cg.Key, meta: cg.MoveMetadata) => {
        console.log(orig, dest, meta);

        this.preaction = meta.premove;
        // chessground doesn't knows about ep, so we have to remove ep captured pawn
        const pieces = this.chessground.state.boardState.pieces;
        // console.log("ground.onUserMove()", orig, dest, meta);
        let moved = pieces.get(dest);
        // Fix king to rook 960 castling case
        if (moved === undefined) moved = { role: 'k-piece', color: this.mycolor } as cg.Piece;
        //en - passant logic
        this.performEnPassant(meta, moved, orig, dest, pieces, this.chessground, this.variant, this.mycolor);

        if (
            meta.captured === undefined &&
            moved !== undefined &&
            moved.role === 'p-piece' &&
            orig[0] !== dest[0] &&
            this.variant.rules.enPassant
        ) {
            const pos = util.key2pos(dest),
                pawnPos: cg.Pos = [pos[0], pos[1] + (this.mycolor === 'white' ? -1 : 1)];
            const diff: cg.PiecesDiff = new Map();
            diff.set(util.pos2key(pawnPos), undefined);
            this.chessground.setPieces(diff);
            meta.captured = {
                role: 'p-piece',
                color: moved.color === 'white' ? 'black' : 'white' /*or could get it from pieces[pawnPos] probably*/,
            };
        }

        // increase partner's pocket count
        // important only during gap before we receive board message from server and reset whole FEN (see also onUserDrop)
        if (meta.captured) {
            this.feedPartnerPocket(meta.captured);
        }
        this.processInput(moved, orig, dest, meta);
        this.preaction = false;
    };

    private setPremove = (orig: cg.Orig, dest: cg.Key, metadata?: cg.SetPremoveMetadata) => {
        this.premove = { orig, dest, metadata };
        // console.log("setPremove() to:", orig, dest, meta);
    };

    private unsetPremove = () => {
        this.premove = undefined;
        this.preaction = false;
    };

    setState = (fen: cg.FEN, turnColor: cg.Color, move: cg.Orig[] | undefined) => {
        this.fullfen = fen;

        // this is used by clocks to prevent sending "flag" message by flagCallback when turnColor == oppcolor
        this.turnColor = turnColor;

        this.lastmove = move;
        this.ffishBoard.setFen(this.fullfen);
        this.isCheck = this.ffishBoard.isCheck();
        this.setDests();
    };

    /** HAND A CAPTURED PIECE TO THE PARTNER'S POCKET, locally.
     *
     *  Only ever right during the gap before the server's board message resets the whole FEN — the
     *  note this was extracted from says so, and it is still true. There are now TWO such gaps: the
     *  ordinary one between a move and its confirmation, and the one a disconnect holds open, which
     *  `roundCtrl.replayPendingMove()` closes by replaying the move on top of a snapshot.
     *
     *  A PROMOTED PIECE GOES BACK AS A PAWN, which is what `promoted` is asked for. */
    feedPartnerPocket = (captured: cg.Piece) => {
        const role = captured.promoted ? 'p-piece' : captured.role;
        const pocketPartner = this.partnerCC.chessground.state.boardState.pockets![captured.color];
        if (!pocketPartner.has(role)) {
            pocketPartner.set(role, 0);
        }
        pocketPartner.set(role, pocketPartner.get(role)! + 1);
        // update fen of partner board:
        const partnerFenFromFFish = this.partnerCC.ffishBoard.fen();
        // we updated pocket model, so now chessground returns correct new fen with updated pockets:
        const partnerFenFromCG = this.partnerCC.chessground.getFen();
        const partnerFenFromCGPocketsPart = partnerFenFromCG.match(/\[.*\]/)![0]; // how the pocket should look like
        // todo: don't remember if there was any reason for not just using the fen from chessground directly instead
        //       of replacing the pockets in the ffish fen
        const partnerFenFromFFishNewPockets = partnerFenFromFFish.replace(/\[.*\]/, partnerFenFromCGPocketsPart);
        this.partnerCC.setState(partnerFenFromFFishNewPockets, this.partnerCC.turnColor, this.partnerCC.lastmove);
        this.partnerCC.chessground.state.dom.redraw();
    };

    /* A REASON TO REFUSE MOVES THAT IS NOT ABOUT THE POSITION.
     *
     * `setDests()` in the base class answers "what does the variant allow here", computed from the
     * position alone. A bughouse board sometimes has to refuse a move for a reason the position
     * cannot express: that a move of ours is outstanding and a second one would race it — branch
     * 1.2.3 of the reconnect tree.
     *
     * OVERRIDDEN HERE RATHER THAN ADDED TO THE BASE, because it is a bughouse concept. Every
     * single-board game and the analysis page keep exactly the `setDests()` they had.
     *
     * ASKED, NOT STORED. A copy of the answer kept on this object would be a third place the same
     * fact lives — beside the records the reconnect controller holds and the map chessground holds
     * — and every one of those needs a moment where somebody remembers to update it. That is the
     * exact shape of the bug this replaces: the gate used to be applied by BLANKING the map after
     * the fact, at one of the four places that write it, and the other three recomputed it and
     * silently gave the board back. A predicate has no such moment — it is evaluated when the
     * answer is needed, so it cannot be stale.
     *
     * The mirror of `snapshot(history, playableNow)`, where the controller borrows a board it does
     * not have. Here a board borrows a controller it does not have. Defaults to allowing
     * everything, so a board nobody wires behaves exactly as before.
     *
     * ALWAYS TRUE HERE, AND THAT IS THE BASE CASE RATHER THAN DEAD CODE. Two readers reach it.
     * The ANALYSIS page never wires anything — `AnalysisControllerBughouse` has no socket, no
     * reconnection and no unconfirmed move, so its boards must never refuse one. And every board
     * reaches it while being BUILT, before any owner could have wired it; a board under
     * construction has nothing in flight, so `true` is the right answer there too.
     *
     * `RoundControllerBughouse` is the only thing that installs a real answer, by assigning over
     * this in its constructor (`this.boardA.movesAllowed = ...`). Delete this and that assignment
     * has nothing to shadow.
     *
     * A PROTOTYPE METHOD, NOT A CLASS FIELD, AND THE DIFFERENCE IS LOAD-BEARING. `GameController`'s
     * constructor calls `this.setDests()`, which dispatches to the override below — and a subclass
     * class field is not initialised until `super()` RETURNS, so a field here would still be
     * `undefined` at that call and every board would die building itself. A prototype method exists
     * before any constructor body runs. `roundCtrl` still assigns over it; that makes an own
     * property which shadows this, which is exactly what is wanted. */
    movesAllowed(): boolean {
        return true;
    }

    /** Asked BEFORE the legal moves are generated: a board that is refusing moves has nothing to
     *  ask the engine, and computing an answer we are about to discard invites somebody to use it
     *  later. */
    setDests() {
        if (!this.movesAllowed()) {
            this.chessground.set({ movable: { dests: new Map() } });
            return;
        }
        super.setDests();
    }

    pushMove = (move: string) => {
        this.ffishBoard.push(move);

        this.fullfen = this.ffishBoard.fen(this.variant.ui.showPromoted, 0);
        const parts = this.fullfen.split(' ');
        this.turnColor = parts[1] === 'w' ? 'white' : 'black';
        this.lastmove = uci2LastMove(move);
        this.isCheck = this.ffishBoard.isCheck();
        this.setDests();
    };

    getFFishPly = () => {
        console.log('>>>>>>>>>>>>>>>>>>>>>');
        console.log(this.partnerCC.ffishBoard.moveStack().split(' '));
        console.log(this.ffishBoard.moveStack().split(' '));
        return this.ffishBoard.moveStack().split(' ').length;
    };

    hasNoMoves = () => {
        return this.ffishBoard.moveStack().split(' ')[0] === '';
    };

    san = (move: string): string => {
        return this.ffishBoard.sanMove(move, this.notationAsObject);
    };

    sanSAN = (move: string): string => {
        return this.ffishBoard.sanMove(move);
    };

    // applies a locally-computed move (no server round-trip): SAN must be read
    // before pushMove, since the move is no longer legal on ffishBoard afterward
    playMove = (move: string): { san: string; sanSAN: string } => {
        const san = this.san(move);
        const sanSAN = this.sanSAN(move);
        this.pushMove(move);
        this.renderState();
        this.chessground.set({ movable: { color: this.turnColor } });
        return { san, sanSAN };
    };

    // The game status belongs to both boards, so the parent reports it (on one board only).
    updateBoardSummary(lastMove: string | undefined): void {
        this.boardSummary.setPosition(this.chessground.state.boardState, lastMove);
    }

    renderState = () => {
        this.chessground.set({
            fen: this.fullfen,
            turnColor: this.turnColor,
            check: this.isCheck,
            lastMove: this.lastmove,
        });
        this.updateBoardSummary(this.parent?.lastSanOn(this.boardName));
    };

    setGround = () => {
        //TODO: There already is initialization of chessground in the parent class, but might require some changes to it
        //      to decouple from model object and pass custom fens, etc. Ideally below initialization should happen there as well
        this.chessground.set({
            movable: {
                free: false,
                color: 'white',
                events: {
                    after: this.onUserMove,
                    afterNewPiece: this.onUserDrop,
                },
            },
            premovable: {
                enabled: true,
                premoveFunc: premove(this.variant.name, this.chess960, this.variant.board.dimensions),
                predropFunc: predrop(this.variant.name, this.variant.board.dimensions),
                events: {
                    set: this.setPremove,
                    unset: this.unsetPremove,
                },
            },
            events: {
                move: this.onMove(),
                dropNewPiece: this.onDrop(),
                select: this.onSelect(),
            },
        });
    };

    toggleSettings(): void {}
}
