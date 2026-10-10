import { WebsocketHeartbeatJs } from './socket/socket';

import { h, VNode } from 'snabbdom';
import * as Mousetrap from 'mousetrap';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { _ } from './i18n';
import { patch } from './document';
import { alertDialog } from './alertDialog';
import { Step, MsgChat, MsgFullChat, MsgSpectators, MsgShutdown, MsgGameNotFound } from './messages';
import { adjacent, uci2LastMove, moveDests, cg2uci, unpromotedRole, UCIMove } from './chess';
import { InputType } from '@/input/input';
import { GatingInput } from './input/gating';
import { PromotionInput } from './input/promotion';
import { DuckInput } from './input/duck';
import { ArrowingInput } from './input/arrowing';
import { ChessgroundController } from './cgCtrl';
import { BoardName, JSONObject, PyChessModel } from './types';
import { updateCount, updatePoint } from './info';
import { sound } from './sound';
import { chatMessage, ChatController, replayingChat } from './chat';
import { selectMove } from './movelist';
import { Api } from 'chessgroundx/api';
import { Chessground } from 'chessgroundx/chessground';
import type { Config } from 'chessgroundx/config';
import { fogFen, Variant } from './variants';
import { renderSpectators } from './spectators';
import { animatePassMove } from './passMove';
import {
    buildGameKeyboardHelpSections,
    hideGameKeyboardHelp,
    isKeyboardHelpShortcut,
    showGameKeyboardHelp,
} from './gameKeyboardHelp';
import { boardSettings } from './boardSettings';
import { aliceBoardFen } from './aliceBoard';
import type { AliceBoardName } from './aliceBoard';
import { BoardSummaryView } from './accessibility/boardSummary';
import { result } from './result';

export abstract class GameController extends ChessgroundController implements ChatController {
    sock: WebsocketHeartbeatJs;

    // Info
    username: string;
    gameId: string;
    tournamentId: string;
    tournamentSystem: number;
    handicap: boolean;
    wplayer: string;
    bplayer: string;
    aiLevel: number;
    rated: string;
    corr: boolean;

    base: number;
    inc: number;

    players: string[];
    titles: string[];
    ratings: string[];
    patrons: boolean[];
    wtitle: string;
    btitle: string;
    wpatron: boolean;
    bpatron: boolean;
    wrating: string;
    brating: string;

    // Helpers
    gating: GatingInput;
    promotion: PromotionInput;
    duck: DuckInput;
    arrowing: ArrowingInput;

    // Game state
    turnColor: cg.Color;
    suffix: string;

    setupFen: string;

    premove?: { orig: cg.Orig; dest: cg.Key; metadata?: cg.SetPremoveMetadata };
    preaction: boolean;

    steps: Step[];

    // TODO: moveList: MoveList;
    status: number;
    pgn: string;
    ply: number;
    result: string;

    // UI state
    vplayer0: VNode;
    vplayer1: VNode;
    vmovelist: VNode | HTMLElement;
    spectatorsContainer: VNode | HTMLElement;
    gameControls: VNode;
    moveControls: VNode;
    vmiscInfoW: VNode;
    vmiscInfoB: VNode;
    ctableContainer: VNode | HTMLElement;
    clickDrop: cg.Piece | undefined;
    mirrorBoard: boolean;
    aliceSplitBoards: boolean;
    aliceSplitBoard?: Api;

    spectator: boolean;

    // Settings
    clickDropEnabled: boolean;
    autoPromote?: boolean;
    autoClaimDraw?: boolean;
    dblClickPass?: boolean;

    // Main line ply where analysis variation starts
    plyVari: number;

    undo?: any;

    keyboardHelpOpen: boolean;
    boardSummary: BoardSummaryView;
    private readonly onGameKeyboardHelpKeyDown: (event: KeyboardEvent) => void;

    get pocketHotkeyRoles(): readonly cg.Role[] | undefined {
        return !this.spectator && this.status < 0 && this.variant.pocket
            ? this.variant.pocket.roles[this.mycolor]
            : undefined;
    }

    constructor(
        el: HTMLElement,
        model: PyChessModel,
        fullfen: string,
        pocket0: HTMLElement,
        pocket1: HTMLElement,
        boardName: BoardName = '',
        aliceBoardEl?: HTMLElement,
    ) {
        super(el, model, fullfen, pocket0, pocket1, boardName);
        this.boardSummary = new BoardSummaryView(this.variant, boardName);

        this.gameId = model['gameId'] as string;
        this.tournamentId = model['tournamentId'];
        this.tournamentSystem = Number(model['tsystem'] || 0);
        this.username = model['username'];
        this.wplayer = model['wplayer'];
        this.bplayer = model['bplayer'];
        this.base = Number(model['base']);
        this.inc = Number(model['inc']);
        this.status = Number(model['status']);
        this.steps = [];
        this.pgn = '';
        this.ply = isNaN(model['ply']) ? 0 : model['ply'];
        this.wtitle = model['wtitle'];
        this.btitle = model['btitle'];
        this.wpatron = model['wpatron'];
        this.bpatron = model['bpatron'];
        this.wrating = model['wrating'];
        this.brating = model['brating'];
        this.rated = model['rated'];
        this.corr = model['corr'] === 'True';
        this.mirrorBoard = false;
        this.aliceSplitBoards = false;

        this.spectator = this.username !== this.wplayer && this.username !== this.bplayer;

        this.gating = new GatingInput(this);
        this.promotion = new PromotionInput(this);
        this.duck = new DuckInput(this);
        this.arrowing = new ArrowingInput(this);

        // orientation = this.mycolor
        if (this.spectator) {
            this.mycolor = 'white';
            this.oppcolor = 'black';
        } else {
            this.mycolor = this.username === this.wplayer ? 'white' : 'black';
            this.oppcolor = this.username === this.wplayer ? 'black' : 'white';
        }

        // players[0] is top player, players[1] is bottom player
        this.players = [
            this.mycolor === 'white' ? this.bplayer : this.wplayer,
            this.mycolor === 'white' ? this.wplayer : this.bplayer,
        ];
        this.titles = [
            this.mycolor === 'white' ? this.btitle : this.wtitle,
            this.mycolor === 'white' ? this.wtitle : this.btitle,
        ];
        this.ratings = [
            this.mycolor === 'white' ? this.brating : this.wrating,
            this.mycolor === 'white' ? this.wrating : this.brating,
        ];
        this.patrons = [
            this.mycolor === 'white' ? this.bpatron : this.wpatron,
            this.mycolor === 'white' ? this.wpatron : this.bpatron,
        ];

        this.result = '*';
        const parts = this.fullfen.split(' ');

        this.turnColor = parts[1] === 'w' ? 'white' : 'black';
        this.suffix = '';

        this.chessground.set({
            animation: {
                enabled: (localStorage.animation === undefined || localStorage.animation === 'true') && !this.fog,
            },
            movable: {
                showDests: localStorage.showDests === undefined || localStorage.showDests === 'true',
            },
        });

        this.steps.push({
            fen: this.fullfen,
            move: undefined,
            check: false,
            turnColor: this.turnColor,
        });

        this.setDests();

        this.keyboardHelpOpen = false;
        this.onGameKeyboardHelpKeyDown = (event: KeyboardEvent) => {
            if (!this.keyboardHelpOpen) return;

            if (event.key === 'Escape' || isKeyboardHelpShortcut(event)) {
                event.preventDefault();
                event.stopPropagation();
                this.closeKeyboardHelp();
                return;
            }

            if (event.key === 'Tab') return;

            event.preventDefault();
            event.stopPropagation();
        };

        Mousetrap.bind('left', () => selectMove(this, this.ply - 1, this.plyVari));
        Mousetrap.bind('right', () => selectMove(this, this.ply + 1, this.plyVari));
        Mousetrap.bind('up', () => selectMove(this, 0));
        Mousetrap.bind('down', () => selectMove(this, this.steps.length - 1));
        Mousetrap.bind('enter', () => this.skipGating());
        Mousetrap.bind('f', () => this.toggleOrientation());
        Mousetrap.bind('?', () => this.helpDialog());

        if (this.variant.name === 'alice' && aliceBoardEl) {
            this.initAliceSplitBoard(aliceBoardEl, model);
            Mousetrap.bind('s', () => this.toggleAliceSplitBoards());
        }

        // Not every page navigates to a ply on load: a round at move 0 never does.
        this.updateBoardSummary(undefined);
    }

    private initAliceSplitBoard(el: HTMLElement, model: PyChessModel): void {
        this.aliceSplitBoard = Chessground(el, {
            fen: aliceBoardFen(this.fullfen, 'b'),
            orientation: this.mycolor,
            dimensions: this.variant.board.dimensions,
            notation: this.notation,
            kingRoles: this.variant.kingRoles,
            viewOnly: true,
        });
        boardSettings.updateScopedBoardStyle(this.variant, el);
        boardSettings.updateScopedPieceStyle(this.variant, el, model.initialFen || this.fullfen);

        const boardContainer = (el.closest('#aliceboard') as HTMLElement | null) ?? el;
        const activateBoard = () => {
            if (this.aliceSplitBoards) this.switchAliceBoards();
        };
        boardContainer.addEventListener('click', activateBoard);
        boardContainer.addEventListener('keydown', event => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            activateBoard();
        });

        this.aliceSplitBoards = localStorage.aliceSplitBoards === 'true';
        this.updateAliceSplitLayout();
        this.refreshAliceBoards();
    }

    private activeAliceBoard(): AliceBoardName {
        return this.mirrorBoard ? 'b' : 'a';
    }

    private inactiveAliceBoard(): AliceBoardName {
        return this.mirrorBoard ? 'a' : 'b';
    }

    displayFen(fen: string): string {
        if (this.variant.name !== 'alice') return fen;
        if (this.aliceSplitBoards) return aliceBoardFen(fen, this.activeAliceBoard());
        return this.mirrorBoard ? this.getAliceFen(fen) : fen;
    }

    syncAliceSplitBoard(fen: string, config: Config = {}): void {
        if (!this.aliceSplitBoard) return;
        this.aliceSplitBoard.set({
            ...config,
            fen: aliceBoardFen(fen, this.inactiveAliceBoard()),
            orientation: this.chessground.state.orientation,
        });
    }

    private refreshAliceBoards(): void {
        // Chessground stores the checked square, not just whether the side to move is in check.
        // Preserve the logical check state while making both grounds recompute that square from
        // their newly assigned pieces when boards A and B are switched.
        const check = !!(this.chessground.state.check?.length || this.aliceSplitBoard?.state.check?.length);
        this.chessground.set({ fen: this.displayFen(this.fullfen) as cg.FEN, check });
        if (this.aliceSplitBoard) {
            this.setDests();
            this.syncAliceSplitBoard(this.fullfen, { check });
            this.updateAliceBoardLabels();
            requestAnimationFrame(() => this.aliceSplitBoard?.redrawAll());
        }
    }

    private updateAliceSplitLayout(): void {
        document.querySelector('.round-app')?.classList.toggle('alice-split', this.aliceSplitBoards);
        this.updateAliceBoardLabels();

        const button = document.getElementById('alice-split');
        if (button) {
            button.setAttribute('aria-pressed', String(this.aliceSplitBoards));
            button.setAttribute(
                'title',
                this.aliceSplitBoards ? _('Show merged board (S)') : _('Show separate boards (S)'),
            );
        }
    }

    private updateAliceBoardLabels(): void {
        const mainboard = document.getElementById('mainboard');
        const otherBoard = document.getElementById('aliceboard');
        if (!mainboard || !otherBoard) return;

        const active = this.activeAliceBoard().toUpperCase();
        const inactive = this.inactiveAliceBoard().toUpperCase();
        mainboard.dataset.aliceBoard = active;
        otherBoard.dataset.aliceBoard = inactive;
        mainboard.setAttribute('aria-label', _('Alice board %1 (active)', active));
        otherBoard.setAttribute('aria-label', _('Alice board %1; click to activate', inactive));
    }

    toggleAliceSplitBoards(): void {
        if (!this.aliceSplitBoard) return;
        this.aliceSplitBoards = !this.aliceSplitBoards;
        localStorage.aliceSplitBoards = String(this.aliceSplitBoards);
        this.updateAliceSplitLayout();
        this.refreshAliceBoards();
    }

    override destroy(): void {
        this.closeKeyboardHelp();
        document.removeEventListener('keydown', this.onGameKeyboardHelpKeyDown, true);
        Mousetrap.unbind(['left', 'right', 'up', 'down', 'enter', 'f', '?', 's']);
        this.aliceSplitBoard?.destroy();
        super.destroy();
    }

    skipGating() {
        this.gating.skipGating();
    }

    helpDialog() {
        if (this.keyboardHelpOpen) {
            this.closeKeyboardHelp();
        } else {
            this.openKeyboardHelp();
        }
    }

    openKeyboardHelp() {
        this.keyboardHelpOpen = true;
        document.addEventListener('keydown', this.onGameKeyboardHelpKeyDown, true);
        showGameKeyboardHelp(this, buildGameKeyboardHelpSections(this));
    }

    closeKeyboardHelp() {
        if (!this.keyboardHelpOpen) return;
        this.keyboardHelpOpen = false;
        document.removeEventListener('keydown', this.onGameKeyboardHelpKeyDown, true);
        hideGameKeyboardHelp();
    }

    toggleOrientation(): void {
        super.toggleOrientation();
        this.aliceSplitBoard?.toggleOrientation();
    }

    flipped() {
        return this.variant.name === 'racingkings'
            ? this.chessground.state.orientation !== 'white'
            : this.chessground.state.orientation !== this.mycolor;
    }

    setDests() {
        // console.log("gameCtrl.setDests()");
        const legalMoves = this.ffishBoard
            .legalMoves()
            .split(' ')
            .filter(o => o);
        const fakeDrops = this.variant.name === 'ataxx';
        const pieces = this.chessground.state.boardState.pieces;
        const dests = moveDests(legalMoves as UCIMove[], fakeDrops, pieces, this.turnColor);
        if (this.variant.rules.gate || this.variant.name === 'jieqi') {
            for (const [orig, destArray] of dests) {
                if (orig && util.isKey(orig)) {
                    const origPiece = pieces.get(orig);
                    if (origPiece?.role === 'r-piece') {
                        // Remove rook takes king from the legal destinations
                        dests.set(
                            orig,
                            destArray.filter(dest => {
                                const destPiece = pieces.get(dest);
                                return !(
                                    destPiece &&
                                    destPiece.role === 'k-piece' &&
                                    origPiece.color === destPiece.color
                                );
                            }),
                        );
                    }
                    if (origPiece?.role === 'a-piece' && origPiece?.promoted) {
                        // Fake advisor can’t leave the palace
                        dests.set(
                            orig,
                            destArray.filter(dest => {
                                return !['c2', 'g2', 'c9', 'g9'].includes(dest);
                            }),
                        );
                    }
                }
            }
        }
        this.chessground.set({ movable: { dests: dests } });
        if (this.steps.length === 1) {
            this.chessground.set({ check: this.ffishBoard.isCheck() ? this.turnColor : false });
        }
    }

    abstract toggleSettings(): void;

    abstract doSendMove(move: string): void;

    // RoundController uses these hooks to disambiguate a local compound-move
    // cancel action from a takeback of moves already accepted by the server.
    onDuckInputStateChange(_active: boolean): void {}

    onArrowingInputStateChange(_active: boolean): void {}

    processInput(
        piece: cg.Piece,
        orig: cg.Orig,
        dest: cg.Key,
        meta: cg.MoveMetadata,
        lastSuffix?: string,
        lastInputType?: InputType,
    ): void {
        switch (lastInputType) {
            case undefined:
                this.suffix = '';
                this.gating.start(piece, orig, dest, meta);
                break;
            case 'gating':
                if (lastSuffix === '-') {
                    this.promotion.start(piece, orig, dest, meta);
                } else {
                    this.suffix += lastSuffix;
                    this.duck.start(piece, orig, dest, meta);
                }
                break;
            case 'promotion':
                this.suffix += lastSuffix;
                this.duck.start(piece, orig, dest, meta);
                break;
            case 'duck':
                this.suffix += lastSuffix;
                this.arrowing.start(piece, orig, dest, meta);
                break;
            case 'arrowing':
                this.suffix += lastSuffix;
                this.sendMove(orig, dest, this.suffix);
                break;
        }
    }

    sendMove(orig: cg.Orig, dest: cg.Key, promo: string) {
        this.doSendMove(cg2uci(orig + dest + promo));
    }

    getAliceFen(fen: string): string {
        if (!this.mirrorBoard) {
            return fen;
        } else {
            const placement = fen.split(' ')[0];
            let newPlacement: string[] = [];
            let mirrorPiece: boolean = false;
            for (const c of placement) {
                if ('12345678/'.includes(c)) {
                    newPlacement.push(c);
                } else {
                    if (c === '|') {
                        mirrorPiece = true;
                    } else {
                        if (mirrorPiece) {
                            newPlacement.push(c);
                            mirrorPiece = false;
                        } else {
                            newPlacement.push('|');
                            newPlacement.push(c);
                        }
                    }
                }
            }
            return newPlacement.join('');
        }
    }

    switchAliceBoards(): void {
        this.mirrorBoard = !this.mirrorBoard;
        this.refreshAliceBoards();
    }

    goPly(ply: number, _plyVari = 0) {
        // console.log("gameCtrl.goPly()");
        const step = this.steps[ply];
        if (step === undefined) return;

        const lastMove = uci2LastMove(step.move);
        let capture = false;
        if (lastMove) {
            // 960 king takes rook castling is not capture
            // TODO Defer this logic to ffish.js
            const piece = this.chessground.state.boardState.pieces.get(lastMove[1] as cg.Key);
            capture =
                (piece !== undefined && piece.role !== '_-piece' && step.san?.slice(0, 2) !== 'O-') ||
                step.san?.slice(1, 2) === 'x';
        }

        const fen = this.displayFen(step.fen);
        this.chessground.set({
            fen: this.fog ? fogFen(fen) : fen,
            turnColor: step.turnColor,
            movable: {
                color: step.turnColor,
            },
            check: this.fog ? false : step.check,
            lastMove: this.fog ? undefined : lastMove,
        });
        this.syncAliceSplitBoard(step.fen, {
            turnColor: step.turnColor,
            check: step.check,
            lastMove,
        });
        animatePassMove(this.chessground, this.variant.rules.pass && !this.fog, lastMove);

        // turnColor have to be actualized before setDests() !!!
        this.turnColor = step.turnColor;

        this.setDests();

        this.fullfen = step.fen;
        this.suffix = '';
        this.duck.cancel();
        this.arrowing.cancel();

        if (this.variant.ui.counting) {
            [this.vmiscInfoW, this.vmiscInfoB] = updateCount(
                step.fen,
                document.getElementById('misc-infow') as HTMLElement,
                document.getElementById('misc-infob') as HTMLElement,
            );
        }

        if (this.variant.ui.materialPoint) {
            [this.vmiscInfoW, this.vmiscInfoB] = updatePoint(
                this.variant,
                step.fen,
                document.getElementById('misc-infow') as HTMLElement,
                document.getElementById('misc-infob') as HTMLElement,
            );
        }

        if (ply === this.ply + 1) {
            sound.moveSound(this.variant, capture);
            if (step.check) sound.check();
        }

        this.ply = ply;
        this.updateBoardSummary(step.san);
    }

    // A page without a game (a bare analysis board) has no status to report.
    updateBoardSummary(lastMove: string | undefined): void {
        if (this.gameId) this.boardSummary.setStatus(result(this.variant, this.status, this.result));
        this.boardSummary.setPosition(this.chessground.state.boardState, lastMove);
    }

    doSend = (message: JSONObject) => {
        // console.log("---> doSend():", message);
        this.sock.send(JSON.stringify(message));
    };

    protected onMove = () => {
        return (orig: cg.Key, dest: cg.Key, capturedPiece?: cg.Piece) => {
            const isEnPassant =
                capturedPiece === undefined &&
                this.chessground.state.boardState.pieces.get(dest)?.role === 'p-piece' &&
                orig[0] !== dest[0] &&
                this.variant.rules.enPassant;

            sound.moveSound(this.variant, capturedPiece !== undefined || isEnPassant);
        };
    };

    protected onDrop = () => {
        return (piece: cg.Piece, _dest: cg.Key) => {
            if (piece.role) sound.moveSound(this.variant, false);
        };
    };

    protected onSelect = () => {
        let lastTime = performance.now();
        let lastKey: cg.Key | undefined;
        return (key: cg.Key) => {
            if (this.arrowing.inputState === 'move') {
                this.arrowing.onSelect(key);
                return;
            }
            if (this.chessground.state.movable.dests === undefined) return;

            const curTime = performance.now();

            if (this.chessground.state.stats.ctrlKey || (lastKey === key && curTime - lastTime < 500)) {
                if (this.chessground.state.movable.dests.get(key)?.includes(key)) {
                    const piece = this.chessground.state.boardState.pieces.get(key)!;
                    if (this.variant.name === 'sittuyin') {
                        // TODO make this more generic
                        // Sittuyin in place promotion on Ctrl or double click
                        // console.log("In place promotion", key);
                        this.chessground.setPieces(
                            new Map([
                                [
                                    key,
                                    {
                                        color: piece.color,
                                        role: 'f-piece',
                                        promoted: true,
                                    },
                                ],
                            ]),
                        );
                        this.chessground.state.movable.dests = undefined;
                        this.chessground.selectSquare(key);
                        sound.moveSound(this.variant, false);
                        this.processInput(piece, key, key, { premove: false }, 'f', 'promotion');
                    } else if ((this.chessground.state.stats.ctrlKey || this.dblClickPass) && this.variant.rules.pass) {
                        // Janggi or ataxx pass move
                        this.pass(key);
                    }
                }
                lastKey = undefined;
            } else {
                lastKey = key;
                lastTime = curTime;
            }
        };
    };

    protected pass = (passKey?: cg.Key) => {
        if (
            this.turnColor === this.chessground.state.movable.color ||
            this.chessground.state.movable.color === 'both'
        ) {
            if (!passKey) {
                const pieces = this.chessground.state.boardState.pieces;
                const dests = this.chessground.state.movable.dests;
                for (const [k, p] of pieces) {
                    if (p.color === this.turnColor && dests?.get(k)?.includes(k)) {
                        passKey = k;
                        break;
                    }
                }
            }
            if (passKey) {
                // prevent calling pass() again by selectSquare() -> onSelect()
                this.chessground.unselect();
                animatePassMove(this.chessground, this.variant.rules.pass, [passKey, passKey], true);
                sound.moveSound(this.variant, false);
                this.sendMove(passKey, passKey, '');
            }
        }
    };

    /**
     * Custom variant-specific logic to be triggered on move and alter state of board/pocket depending on variant rules.
     */
    protected onUserMove(orig: cg.Key, dest: cg.Key, meta: cg.MoveMetadata) {
        if (this.duck.inputState === 'move') {
            this.duck.finish(dest);
            return;
        }
        if (this.arrowing.inputState === 'move') {
            this.arrowing.finish(dest);
            return;
        }
        if (this.variant.name === 'ataxx' && adjacent(orig, dest)) {
            this.sendMove('P@', dest, '');
            return;
        }
        this.preaction = meta.premove;
        const pieces = this.chessground.state.boardState.pieces;
        let moved = pieces.get(dest);
        // Fix king to rook 960 castling case
        if (moved === undefined) moved = { role: 'k-piece', color: this.mycolor } as cg.Piece;

        // chessground doesn't know about en passant, so we have to remove the captured pawn manually
        this.performEnPassant(meta, moved, orig, dest, pieces, this.chessground, this.variant, this.mycolor);
        // add the captured piece to the pocket
        // chessground doesn't know what piece to revert a captured promoted piece into, so it needs to be handled here
        if (this.variant.pocket?.captureToHand && meta.captured) {
            const piece = {
                role: unpromotedRole(this.variant, meta.captured),
                color: util.opposite(meta.captured.color),
            };
            this.chessground.changePocket(piece, 1);
            this.chessground.state.dom.redraw();
        }

        this.processInput(moved, orig, dest, meta);
        this.preaction = false;
    }

    public performEnPassant(
        meta: cg.MoveMetadata,
        moved: cg.Piece,
        orig: cg.Key,
        dest: cg.Key,
        pieces: cg.Pieces,
        chessground: Api,
        variant: Variant,
        mycolor: cg.Color,
    ) {
        if (
            meta.captured === undefined &&
            moved !== undefined &&
            moved.role === 'p-piece' &&
            orig[0] !== dest[0] &&
            variant.rules.enPassant
        ) {
            const pos = util.key2pos(dest),
                pawnKey = util.pos2key([pos[0], pos[1] + (mycolor === 'white' ? -1 : 1)]);
            meta.captured = pieces.get(pawnKey);
            chessground.setPieces(new Map([[pawnKey, undefined]]));
        }
    }

    /**
     * Variant specific logic for when dropping a piece from pocket is performed
     */
    protected onUserDrop(piece: cg.Piece, dest: cg.Key, meta: cg.MoveMetadata) {
        this.preaction = meta.premove;
        const role = piece.role;
        this.processInput(piece, util.dropOrigOf(role), dest, meta);
        this.preaction = false;
    }

    private onMsgSpectators = (msg: MsgSpectators) => {
        const container = document.getElementById('spectators') as HTMLElement;
        if (container) {
            this.spectatorsContainer = patch(
                this.spectatorsContainer ?? container,
                h('under-left#spectators', renderSpectators(msg.spectators)),
            );
        }
    };


    private onMsgChat = (msg: MsgChat) => {
        if (
            (this.spectator && msg.room === 'spectator') ||
            (!this.spectator && msg.room !== 'spectator') ||
            msg.user.length === 0
        ) {
            chatMessage(msg.user, msg.message, 'roundchat', msg.time);
        }
    };

    private onMsgFullChat = (msg: MsgFullChat) => {
        const container = document.getElementById('messages') as HTMLElement;
        if (container) {
            // To prevent multiplication of messages we have to remove old messages div first
            replayingChat('roundchat');
            patch(container, h('div#messages-clear'));
            // then create a new one
            patch(document.getElementById('messages-clear') as HTMLElement, h('div#messages', { attrs: { role: 'none' } }));
            msg.lines.forEach(line => {
                if (
                    (this.spectator && line.room === 'spectator') ||
                    (!this.spectator && line.room !== 'spectator') ||
                    line.user.length === 0
                ) {
                    chatMessage(line.user, line.message, 'roundchat', line.time);
                }
            });
        }
    };

    private onMsgGameNotFound = (msg: MsgGameNotFound) => {
        void alertDialog({ text: _('Requested game %1 not found!', msg['gameId']) });
        window.location.assign(this.home);
    };

    private onMsgShutdown = (msg: MsgShutdown) => {
        void alertDialog({ text: msg.message });
    };

    protected onMessage(evt: MessageEvent) {
        // console.log("<+++ onMessage():", evt.data);
        if (evt.data === '/n') return;
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
            case 'spectators':
                this.onMsgSpectators(msg);
                break;
            case 'roundchat':
                this.onMsgChat(msg);
                break;
            case 'fullchat':
                this.onMsgFullChat(msg);
                break;
            case 'game_not_found':
                this.onMsgGameNotFound(msg);
                break;
            case 'shutdown':
                this.onMsgShutdown(msg);
                break;
            case 'logout':
                this.doSend({ type: 'logout' });
                break;
        }
    }
}
