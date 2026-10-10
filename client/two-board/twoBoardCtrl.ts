import * as cg from 'chessgroundx/types';

import { uci2LastMove } from '../chess';
import { Step } from '../messages';
import { BugBoardName, PyChessModel } from '../types';
import { Variant, VARIANTS } from '../variants';
import { boardSettings } from '@/boardSettings';
import { ChessgroundController } from '@/cgCtrl';
import { GameControllerBughouse } from './common/gameCtrl';
import { MovelistView } from './common/movelist';
import { GameInfoView } from './common/gameInfo';
import { Seat } from './common/seat';
import { SeatConfiguration, twoBoardSeats } from './common/seatConfiguration';
import { ownBoardName } from './common/boardRoles';
import { result } from '../result';
import { displayUsername } from '@/user';

// Shared core of the two bughouse page controllers (RoundControllerBughouse and
// AnalysisControllerBughouse): owns the two boards and the state/logic both need.
// Round-only concerns (socket, clocks, offers, chat) and analysis-only concerns
// (engine, analysis tree, PGN) live in the subclasses.
export abstract class TwoBoardController {
    boardA: GameControllerBughouse;
    boardB: GameControllerBughouse;

    model: PyChessModel;
    gameId: string;
    username: string;
    seats: SeatConfiguration<Seat>;
    variant: Variant;
    base: number;
    inc: number;
    status: number;
    result: string;
    readonly home: string;

    steps: Step[];

    /* NO READER'S CURSOR HERE. It is `MovelistView`'s private field — read with
     * `movelistView.ply()`, moved with `movelistView.showPly()` / `selectMove()` / `setCursor()`.
     *
     * It lived here until 2026-09-07, public, with a comment asking callers to assign it only
     * through `setCursor()`. Two things went wrong that being private prevents. The analysis
     * controller wrote it directly, using it as a scratch variable to carry "where should the tree
     * open" from one end of `onMsgBoard()` to the other — a value that is not a cursor. And it
     * started life `undefined` despite its `number` type, because the round page read
     * `ply === undefined` to mean "no board message yet": a second meaning stacked on a field that
     * already had one. Both are gone.
     *
     * `plyA`/`plyB` DO belong here: they are the two boards' move counts, stamped onto every step
     * by `stampStepPlys`, and have nothing to do with what the reader is looking at. */
    plyA: number = 0;
    plyB: number = 0;

    movelistView: MovelistView;
    settings: boolean;

    abstract sendMove: (b: GameControllerBughouse, move: string) => void;
    /* "GO TO PLY N" IS ONE OPERATION AND IT BELONGS TO THE MOVE LIST, which is the only thing
     * that changes the selection — a click in the list, an arrow key, a click on a chat message,
     * a node in the analysis tree. Both pages' `goPly` are now one line delegating to
     * `movelistView.showPly()`, which owns the cursor and the stepped-forward test, and calls back
     * into `renderPly` for the part only the page knows: WHICH boards to repaint, with what
     * playability, and what else to drive (the engine, the clocks, the PGN on analysis).
     *
     * `goPly` survives as the name every caller already uses, and because the shared move list
     * must be able to say "show this ply" without knowing which page it is on. */
    abstract goPly: (ply: number) => void;

    /** Repaint the boards for a ply. Page-specific; called only by `movelistView.showPly()`.
     *  `steppedForward` is the move list's answer to "did we advance exactly one ply", which is
     *  what decides whether a move sound plays — it needs the cursor's OLD value, so the caller
     *  works it out rather than each page re-deriving it.
     *
     *  NO `plyVari`. The variation index is a single-board concept: in `client/movelist.ts` a
     *  reader can select a move inside a variation and it is passed through. Nothing in the
     *  two-board code has ever passed anything but 0 — every call site said `goPly(ply, 0)` — so
     *  it was a parameter the round page ignored and the analysis page tested against a constant. */
    abstract renderPly: (ply: number, steppedForward: boolean) => void;

    // Default flip/switch: just re-orient/re-position the two boards. RoundControllerBughouse
    // overrides both to additionally move its player-bar/clock DOM around, calling
    // super.flipBoards()/super.switchBoards() rather than duplicating the board-level logic.
    flipBoards(): void {
        this.boardA.toggleOrientation();
        this.boardB.toggleOrientation();
    }

    switchBoards(): void {
        switchBoards(this);
    }

    constructor(
        el1: HTMLElement,
        el1Pocket1: HTMLElement,
        el1Pocket2: HTMLElement,
        el2: HTMLElement,
        el2Pocket1: HTMLElement,
        el2Pocket2: HTMLElement,
        model: PyChessModel,
        movelistView: MovelistView,
        gameInfoView: GameInfoView,
    ) {
        this.model = model;
        this.home = model.home;
        this.gameId = model['gameId'] as string;
        this.username = model['username'];
        this.variant = VARIANTS[model.variant];
        this.base = Number(model['base']);
        this.inc = Number(model['inc']);
        this.status = Number(model['status']);
        this.settings = true;
        this.steps = [];

        this.seats = twoBoardSeats(model, this.username);

        this.boardA = new GameControllerBughouse(el1, el1Pocket1, el1Pocket2, 'a', model);
        this.boardB = new GameControllerBughouse(el2, el2Pocket1, el2Pocket2, 'b', model);
        this.boardA.partnerCC = this.boardB;
        this.boardB.partnerCC = this.boardA;
        this.boardA.parent = this;
        this.boardB.parent = this;

        this.movelistView = movelistView;
        this.movelistView.createButtons(this);

        // not retained: the panel is rendered once from this controller's state and
        // never updated again, so nothing needs a reference to it afterwards
        gameInfoView.render(this);
        this.updateBoardSummaryStatus();
    }

    /** SAN of the latest move on one board, as of the ply the move list shows. */
    lastSanOn(boardName: BugBoardName): string | undefined {
        for (let ply = this.movelistView.ply(); ply > 0; ply--) {
            const step = this.steps[ply];
            if (step?.boardName === boardName) return step.san;
        }
        return undefined;
    }

    // The game status is the same on both boards, so only the viewer's own board reports it.
    protected updateBoardSummaryStatus(): void {
        if (this.gameId === '') return;
        const teams = this.seats.teams;
        const text = result(
            this.variant,
            this.status,
            this.result,
            teams[0].name(displayUsername),
            teams[1].name(displayUsername),
        );
        const own = ownBoardName(this.seats) === 'a' ? this.boardA : this.boardB;
        own.boardSummary.setStatus(text);
    }

    protected stampStepPlys = (step: Step, idx: number): void => {
        if (idx > 0) {
            //skip first dummy element
            if (step.boardName === 'a') {
                this.plyA++;
            } else {
                this.plyB++;
            }
        }
        step.plyA = this.plyA;
        step.plyB = this.plyB;
        this.steps.push(step);
    };

    protected stepCapture = (step: Step, board: GameControllerBughouse, move: cg.Orig[] | undefined): boolean => {
        if (!move) return false;
        // 960 king takes rook castling is not capture
        // TODO defer this logic to ffish.js
        return (
            (board.chessground.state.boardState.pieces.get(move[1] as cg.Key) !== undefined &&
                step.san?.slice(0, 2) !== 'O-') ||
            step.san?.slice(1, 2) === 'x'
        );
    };

    protected goPlyCore = (step: Step) => {
        const board = step.boardName === 'a' ? this.boardA : this.boardB;

        const fen = step.boardName === 'a' ? step.fen : step.fenB;
        const fenPartner = step.boardName === 'b' ? step.fen : step.fenB;

        const move = step.boardName === 'a' ? uci2LastMove(step.move) : uci2LastMove(step.moveB);
        const movePartner = step.boardName === 'b' ? uci2LastMove(step.move) : uci2LastMove(step.moveB);

        return { board, fen, fenPartner, move, movePartner };
    };
}

export function swap(nodeA: HTMLElement, nodeB: HTMLElement) {
    const parentA = nodeA.parentNode;
    const siblingA = nodeA.nextSibling === nodeB ? nodeA : nodeA.nextSibling;

    // Move `nodeA` to before the `nodeB`
    nodeB.parentNode!.insertBefore(nodeA, nodeB);

    // Move `nodeB` to before the sibling of `nodeA`
    parentA!.insertBefore(nodeB, siblingA);
}

// The board halves of a switch, without the surrounding furniture — each page
// arranges that differently. The round page groups a seat's pocket with its clock
// and name in a strip and moves strips; the analysis page places pockets on their
// own, so switchBoards() below moves those elements directly.
export function switchBoardElements() {
    // todo: not sure if best implementation below
    //       it manipulates the DOM directly switching places of elements identified by whether they are
    //       main/second board, instead of keeping info about the switch and rendering boards on elements
    //       called left/right
    let mainboardVNode = document.getElementById('mainboard');
    let bugboardVNode = document.getElementById('bugboard');

    let a = mainboardVNode!.style.gridArea || 'board';
    mainboardVNode!.style.gridArea = bugboardVNode!.style.gridArea || 'boardPartner';
    bugboardVNode!.style.gridArea = a;
}

export function redrawBoards(ctrl: TwoBoardController) {
    ctrl.boardA.chessground.redrawAll();
    ctrl.boardB.chessground.redrawAll();
}

/**
 * Forget both boards' memoised rects, so the next read measures the page as it now is.
 *
 * chessgroundx maps every click through a memoised `getBoundingClientRect()` and refreshes it on
 * exactly two signals: its own `ResizeObserver`, which fires when a board CHANGES SIZE, and
 * `window.resize` / `scroll`, which clear the memo. A board that MOVES without resizing sends
 * neither — and this layout moves boards for reasons of its own: zooming the other column
 * narrows the first grid track, a username takes a line of its own and pushes the board down
 * inside its stack, a tools part drops into a zone and the rows shift. Measured on a live game:
 * board B sitting at y=80.7 against a memo saying 100.3, a 19.6px error on a 20.7px square, and a
 * right-click one square below the top edge produced no shape at all because the pixel mapped
 * outside the board chessground believed in.
 *
 * CLEARING, NOT RE-MEASURING, and that is what makes this safe. It writes nothing, touches no
 * element and cannot wake an observer, so it starts no cascade — where `updateBounds()` sets the
 * container's size and could. It also needs no ordering: the rect is recomputed at the next READ,
 * which is the click, by which time the arrangement has certainly settled. An attempt to measure
 * on the next frame instead had to guess when the placement passes were done, and could memoise
 * the very geometry it was trying to replace.
 */
export function clearBoardBounds(ctrl: TwoBoardController): void {
    ctrl.boardA.chessground.state.dom.bounds.clear();
    ctrl.boardB.chessground.state.dom.bounds.clear();
}

export function switchBoards(ctrl: TwoBoardController) {
    switchBoardElements();

    let mainboardPocket0 = document.getElementById('pocket00');
    let mainboardPocket1 = document.getElementById('pocket01');
    let bugboardPocket0 = document.getElementById('pocket10');
    let bugboardPocket1 = document.getElementById('pocket11');

    swap(mainboardPocket0!, bugboardPocket0!);
    swap(mainboardPocket1!, bugboardPocket1!);

    redrawBoards(ctrl);
}

export function initBoardSettings(b1: ChessgroundController, b2: ChessgroundController, variant: Variant) {
    const boardFamily = variant.boardFamily;
    boardSettings.updateZoom(boardFamily, b1.boardName);
    boardSettings.updateZoom(boardFamily, b2.boardName);
}
