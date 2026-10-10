import { h, VNode } from 'snabbdom';

import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { DrawShape } from 'chessgroundx/draw';

import ffishModule from 'ffish-es6';

import { _ } from '../../i18n';
import { patch } from '../../document';
import { uci2cg } from '../../chess';
import { variantConfigIni } from '../../variants';
import { variantsIni } from '../../variantsIni';
import { povChances } from '../../analysis/winningChances';
import { alertDialog } from '../../alertDialog';
import { NumberSettings } from '../../settings';
import { slider } from '../../view';
import { Ceval } from '../../messages';
import { MsgAnalysis } from '../../analysis/analysisType';
import { BugBoardName } from '../../types';
import type { GameControllerBughouse } from '../common/gameCtrl';
import type AnalysisControllerBughouse from './analysisCtrl';

// Engine evaluation for the bughouse analysis page: Fairy-Stockfish process
// wiring, UCI parsing, engine start/stop per board and PV/score/gauge/arrow
// rendering. Owned by the analysis controller as `ctrl.engine`; the controller
// type is imported type-only, so there is no runtime edge back into it.

const EVAL_REGEX = new RegExp(
    '' +
        /^info depth (\d+) seldepth \d+ multipv (\d+) /.source +
        /score (cp|mate) ([-\d]+) /.source +
        /(?:(upper|lower)bound )?nodes (\d+) nps \S+ /.source +
        /(?:hashfull \d+ )?(?:tbhits \d+ )?time (\S+) /.source +
        /pv (.+)/.source,
);

const maxDepth = 18;

/* THE ALTERNATING LADDER.
   One engine, two positions. Both boards are searched to the SAME target depth, then the target
   rises by a step and both are searched again — so neither board is ever far ahead of the other,
   and each visit starts from a hash that already holds its own previous search.

   `go` always restarts iterative deepening at depth 1, so nothing is literally resumed. What
   carries across a visit is the transposition table, which survives every `position` / `go`
   because this file never sends `ucinewgame` or `Clear Hash` — and must not start.

   A SLICE IS ONE PLY, NOT A STRETCH OF TIME. Each visit asks a board for exactly one depth more
   than it has already reached, and hands the engine over the moment that depth arrives. So the two
   boards advance in lockstep by the thing a reader actually compares — depth — and nothing here
   depends on a millisecond constant nobody measured.

   The earlier design sliced by time (`go depth N movetime 4000`) on the reasoning that two
   positions of unequal difficulty would otherwise spend wildly unequal wall-clock on a turn. They
   still do; that asymmetry belongs to the positions and a timer only hides it. What the timer
   actually produced, measured on `JJgZzLhJ`: board B never reached the shared target at all, so its
   rung kept rising underneath it — the target advanced on every wrap whether or not the board had
   achieved the previous one — and B re-searched an unreachable depth for ever at 10-12 while
   claiming to be climbing. A ladder that raises the rung a board did not reach is not a ladder.

   THE TARGET IS NOW PER BOARD and is simply "one more than you have": there is no shared rung to
   get out of step with a board's actual progress. BASE is only where a board's first visit starts,
   low enough to be quick and high enough not to waste visits on depths nobody reads.

   A slice that ends BELOW its target ended for a reason the engine chose — a forced mate, no legal
   moves — not because a clock ran out, so that board is finished and is not visited again. */
const ladderBaseDepth = 12;
const maxThreads = Math.max((navigator.hardwareConcurrency || 1) - 1, 1);

/* How many principal variations the engine reports, and the one engine setting this page puts on
   screen. The ceiling is 5 because that is what the single-board page's slider offers and the two
   share the stored value; the floor is 1 because nothing here renders zero lines — the
   single-board page's slider goes down to 0 and means it, this one does not. */
const maxMultiPv = 5;
const clampMultiPv = (n: number) => (Number.isFinite(n) ? Math.max(1, Math.min(maxMultiPv, n)) : 1);

/* A column's worth of empty line slots. Built at full height whatever MultiPV currently is, so
   raising the slider has somewhere to render into without rebuilding the panel; `clearPvlines()`
   is what empties the ones above the current setting. The id carries the board's IDENTITY because
   ids must be unique and `a`/`b` is what never moves — where the column SITS is decided in
   `pvPanel()`, from position. */
const pvSlots = (board: BugBoardName): VNode[] =>
    Array.from({ length: maxMultiPv }, (_v, i) => h(`div#pv-${board}-${i + 1}`));

/* BORROWED DROPS, and why they have to be rendered at all.
   Fairy-Stockfish searches drops of pieces a side does not hold yet, because in bughouse they
   arrive from the partner's board — a queen nobody holds now may well be in hand three plies from
   now. `ffish` judges legality against the pocket the FEN records and refuses, and `variationSan`
   is all-or-nothing: one such drop at ply 3 returned "" for the WHOLE line, which the panel then
   skipped, leaving the row on its placeholder or on a stale variation from an earlier depth.

   Measured on board A of `JJgZzLhJ`, pocket `[Bp]`: `P@f7 B@h5 Q@e5 e1d1` converted to "" because
   after the first two drops both pockets are empty and Black has no queen. Its first two plies
   convert perfectly well.

   So the line is walked a ply at a time, and a piece the mover does not hold is LENT to them for
   the length of the conversion — the board is a throwaway used for notation, never the position
   the engine or the page reasons about. The lent plies are marked so the reader can see which
   part of the line is a promise about the partner rather than a fact about this board. */
const lendPiece = (fen: string, piece: string, white: boolean): string => {
    const open = fen.indexOf('[');
    const close = fen.indexOf(']');
    if (open < 0 || close < open) return fen;
    return fen.slice(0, close) + (white ? piece.toUpperCase() : piece.toLowerCase()) + fen.slice(close);
};

/* The PIECE of a borrowed drop is marked, its square is not: `Q` is the part that depends on the
   partner, `@e5` is where it would go and is not in doubt. */
const sanNodes = (san: string, borrowed: boolean): (VNode | string)[] => {
    const at = san.indexOf('@');
    if (!borrowed || at <= 0) return [san];
    return [
        h('span.pv-borrowed', { attrs: { title: _('Not in the pocket — needs the partner') } }, san.slice(0, at)),
        san.slice(at),
    ];
};

export interface UciInfoEval {
    depth: number;
    multiPv: number;
    isMate: boolean;
    povEv: number;
    evalType: string;
    nodes: number;
    elapsedMs: number;
    moves: string;
}

export function parseUciInfoLine(line: string): UciInfoEval | undefined {
    const matches = line.match(EVAL_REGEX);
    if (!matches) return undefined;
    return {
        depth: parseInt(matches[1]),
        multiPv: parseInt(matches[2]),
        isMate: matches[3] === 'mate',
        povEv: parseInt(matches[4]),
        evalType: matches[5],
        nodes: parseInt(matches[6]),
        elapsedMs: parseInt(matches[7]),
        moves: matches[8],
    };
}

export function buildScoreStr(color: string, analysis: Ceval): string {
    const score = analysis['s'];
    let scoreStr = '';
    let ceval: number;
    if (score['mate'] !== undefined) {
        ceval = score['mate'];
        const sign = (color === 'b' && Number(ceval) > 0) || (color === 'w' && Number(ceval) < 0) ? '-' : '';
        scoreStr = '#' + sign + Math.abs(Number(ceval));
    } else if (score['cp'] !== undefined) {
        ceval = score['cp'];
        let nscore = Number(ceval) / 100.0;
        if (color === 'b') nscore = -nscore;
        scoreStr = nscore.toFixed(1);
    }
    return scoreStr;
}

export class EngineController {
    private ctrl!: AnalysisControllerBughouse;

    private vinput: VNode | HTMLElement;
    vscore: VNode | HTMLElement;
    vscorePartner: VNode | HTMLElement;
    /* ONE DEPTH READOUT PER BOARD. There was a single `#info`, patched by whichever board
       reported last — so with the alternating ladder the depth and the knodes/s flipped between
       two boards every slice, with nothing saying which board the number belonged to. Split, each
       one holds its board's last reading while the engine is away on the other. */
    vinfo: VNode | HTMLElement;
    vinfoPartner: VNode | HTMLElement;
    /* ONE COLUMN OF LINES PER BOARD, keyed by board identity. There was one list, patched by
       whichever board reported last — which with the alternating ladder meant the reader watched
       two different games' moves replace each other every slice, with nothing saying which was
       which. */
    private pvlines: Record<BugBoardName, (VNode | HTMLElement)[]>;

    maxDepth: number;

    // The alternating scheduler's state. `sliceBoard` is the board the engine is on right now;
    // undefined means it is on neither and a `bestmove` should not advance anything.
    private engineOn = false;
    private sliceBoard: GameControllerBughouse | undefined;
    // The depth the slice in flight was asked for. A search that ends below it ended on the
    // engine's own terms, which is what marks a board finished.
    private sliceTarget = 0;
    // UCI SEQUENCING, not bookkeeping: a `position` sent while a search is in flight is undefined
    // behaviour, so a restart has to wait for the running search's `bestmove`.
    private searching = false;
    private pendingStart: GameControllerBughouse | undefined;
    /* The depth each board's current search has reported. Meaningful only once that search has
       ENDED, when it is the depth the slice actually reached — mid-search it climbs from 1. A
       board whose finished slice reached the ceiling is done: `go depth 18` on a position already
       searched to 18 returns the same answer from the hash, so revisiting it spends the engine on
       a number nobody is waiting for and makes that board's own readout flicker between its speed
       and the Go-deeper button. */
    private depthReached: Record<BugBoardName, number> = { a: 0, b: 0 };
    // A board is finished when it has reached the ceiling, or when a slice of its own ended before
    // the depth it was asked for — there is nothing further to ask it.
    private finished: Record<BugBoardName, boolean> = { a: false, b: false };
    isEngineReady: boolean;

    ffish: any;
    notationAsObject: any;

    arrow: boolean;
    multipv: number;
    private readonly multipvSetting: MultiPvSetting;

    fsfDebug: boolean;
    fsfError: string[];
    fsfEngineBoard: any; // used to convert pv UCI move list to SAN
    private fsfOriginalPrompt?: typeof window.prompt;
    private fsfInputQueue: string[];

    /* `ownBoard` is the board this viewer played on, or `'a'` for anyone who did not — the same
       answer `analysis.ts` builds the page's two stacks from, so the panel and the boards cannot
       disagree about which side is which. */
    constructor(
        private readonly chess960: boolean,
        private readonly ownBoard: BugBoardName,
    ) {
        this.fsfDebug = true;
        this.fsfError = [];
        this.fsfInputQueue = [];

        // UCI isready/readyok
        this.isEngineReady = false;

        this.maxDepth = maxDepth;

        this.arrow = localStorage.arrow === undefined ? true : localStorage.arrow === 'true';
        // The setting IS the stored value now, rather than a second hand-rolled parse of the same
        // key: `multipv` in localStorage is what the single-board page's slider writes, so this
        // page was already honouring whatever was set over there — silently, with no way to see
        // it or change it from here. Exposing the slider makes that sharing visible.
        this.multipvSetting = new MultiPvSetting(this);
        this.multipv = clampMultiPv(this.multipvSetting.value);

        this.vinput = h('input#input', { props: { name: 'engine', type: 'checkbox' } });
        this.vscore = h('score#score', '');
        this.vscorePartner = h('score#scorePartner', '');
        this.vinfo = h('info#info', '');
        this.vinfoPartner = h('info#infoPartner', '');
        this.pvlines = { a: pvSlots('a'), b: pvSlots('b') };
    }

    // the whole engine panel is a single unit of this widget's own view — engine.ts
    // is part view, part controller (unlike the top-level analysisCtrl.ts/analysis.ts
    // split), so it owns this composed markup directly rather than exposing one
    // placeholder method per leaf element for analysis.ts to reassemble
    // ONE SWITCH, both boards. There were two, one per board, made mutually exclusive by
    // renderInput() — so a reader comparing the boards had to toggle and remember. The two scores
    // stay, one per board: they are what the single engine now keeps both of up to date.
    /* EACH BOARD'S NUMBERS IN ONE COLUMN: its evaluation, and under it the depth that
       evaluation was reached at. They belong together — a score without its depth cannot be
       judged, and under the alternating ladder one of the two scores is always the older one.

       The engine's name keeps the middle and is now static. It used to share `#info` with the
       depth line, which is why "in local browser" and "Depth 11/18" were alternatives rather than
       both being true; the depth has moved out to the two sides, so the name can simply say where
       the engine runs. */
    renderPanel(): VNode {
        return h('div.engine', [
            h('label.switch', [this.vinput as VNode, h('span#slider.sw-slider')]),
            h('div.engine-side.own-side', [this.vscore as VNode, this.vinfo as VNode]),
            h('div.infoBug', ['Fairy-Stockfish 11+', h('br'), _('in local browser')]),
            h('div.engine-side.partner-side', [this.vscorePartner as VNode, this.vinfoPartner as VNode]),
        ]);
    }

    /* The lines, and the one control that decides how many of them there are.
       It sits under the list rather than behind a toggle: the single-board page hides its
       MultiPV slider in a settings drawer because that drawer holds nine settings, and building
       the same drawer here to hold one would cost a hamburger, a second panel and a mode the
       reader has to leave. If Threads or Hash are ever exposed too, that is when a drawer earns
       its place. */
    /* THE COLUMNS ARE ORDERED BY POSITION, NOT BY IDENTITY. Left column is the board in the own
       stack — left in landscape, bottom in portrait — and right is the partner's, so each column
       stands under the board it evaluates. Keying this off `boardName === 'a'` would put board A
       on the left for a viewer who played on board B and whose own board is therefore on the
       right, which is the exact pairing `boardRoles.ts` exists to prevent. */
    pvPanel(): VNode {
        const partner: BugBoardName = this.ownBoard === 'a' ? 'b' : 'a';
        return h('div.pvbox', [
            h('div.pvcolumns', [
                h('div.pvcol.own-pv', this.pvlines[this.ownBoard] as VNode[]),
                h('div.pvcol.partner-pv', this.pvlines[partner] as VNode[]),
            ]),
            this.multipvSetting.view(),
        ]);
    }

    /* Called by the setting when the slider moves. `pvboxIni()` does the rest: it stops the
       ladder, blanks the lines that are about to be wrong, and restarts — and the restart is
       what re-sends `setoption name MultiPV`, which is only legal while the engine is idle. */
    onMultiPvChange = (value: number) => {
        this.multipv = clampMultiPv(value);
        this.pvboxIni();
    };

    // called once by the real controller, immediately after its own construction —
    // performs this widget's one ctrl-dependent initial render (the engine-toggle
    // checkboxes need ctrl.boardA/ctrl.boardB) and makes `ctrl` available to every
    // other method on this class from this point on
    attachCtrl(ctrl: AnalysisControllerBughouse): void {
        this.ctrl = ctrl;

        ffishModule().then((loadedModule: any) => {
            this.ffish = loadedModule;
            this.ffish.loadVariantConfig(
                variantConfigIni(variantsIni, this.ctrl.boardA.variant.name),
            );
            this.notationAsObject = this.notation2ffishjs(this.ctrl.boardA.variant.notation);
        });

        this.vinput = patch(this.vinput, h('input#input', this.renderInput()));
    }

    notation2ffishjs = (n: cg.Notation) => {
        switch (n) {
            case cg.Notation.ALGEBRAIC:
                return this.ffish.Notation.SAN;
            case cg.Notation.SHOGI_ARBNUM:
                return this.ffish.Notation.SHOGI_HODGES_NUMBER;
            case cg.Notation.JANGGI:
                return this.ffish.Notation.JANGGI;
            case cg.Notation.XIANGQI_ARBNUM:
                return this.ffish.Notation.XIANGQI_WXF;
            default:
                return this.ffish.Notation.SAN;
        }
    };

    // Both depth lines reset together: a restart invalidates both boards' readings at once,
    // which is not true of an ordinary slice ending.
    clearInfo = () => {
        this.vinfo = patch(this.vinfo, h('info#info', '-'));
        this.vinfoPartner = patch(this.vinfoPartner, h('info#infoPartner', '-'));
    };

    /* Writes one board's depth line and leaves the other board's alone — which is the whole
       point of there being two. */
    private setInfo = (isOwnBoard: boolean, content: VNode[] | string) => {
        if (isOwnBoard) this.vinfo = patch(this.vinfo, h('info#info', content));
        else this.vinfoPartner = patch(this.vinfoPartner, h('info#infoPartner', content));
    };

    pvboxIni() {
        this.engineStop();
        this.clearPvlines();
        if (this.engineOn) this.engineGo(this.ctrl.boardA);
    }

    pvView(board: BugBoardName, i: number, pv: VNode | undefined) {
        const lines = this.pvlines[board];
        lines[i] = patch(lines[i], h(`div#pv-${board}-${i + 1}.pv`, pv));
    }

    clearPvlines() {
        for (const board of ['a', 'b'] as const) {
            const lines = this.pvlines[board];
            for (let i = maxMultiPv - 1; i >= 0; i--) {
                if (i + 1 <= this.multipv && this.engineOn) {
                    lines[i] = patch(lines[i], h(`div#pv-${board}-${i + 1}.pv`, [h('pvline', h('pvline', '-'))]));
                } else {
                    lines[i] = patch(lines[i], h(`div#pv-${board}-${i + 1}`));
                }
            }
        }
    }

    // The engine is on for the PAGE, not for a board. `localAnalysis` is still per board
    // controller and both are set together, because analysisCtrl reads it to decide whether a
    // position change should stop and restart the engine — and that question is the same for both.
    private renderInput = () => {
        return {
            attrs: {
                disabled: false,
            },
            on: {
                change: () => {
                    this.engineOn = !this.engineOn;
                    this.ctrl.boardA.localAnalysis = this.engineOn;
                    this.ctrl.boardB.localAnalysis = this.engineOn;
                    if (this.engineOn) this.clearInfo();
                    this.pvboxIni();
                },
            },
        };
    };

    fsfPostMessage(msg: string) {
        if (this.fsfDebug) console.debug('<---', msg);
        window.fsf.postMessage(msg);
    }

    loadVariantsIntoFsfEngine() {
        const marker = 'PYCHESS_VARIANTS_INI_EOF_' + Date.now();
        const lines = variantConfigIni(variantsIni, this.ctrl.boardA.variant.name)
            .replace(/\r\n/g, '\n')
            .split('\n');
        this.installFsfPromptQueue([...lines, marker]);
        if (this.fsfDebug) console.debug('<---', '... variants.ini content queued for prompt stdin ...');
        this.fsfPostMessage('load <<' + marker);
        this.fsfPostMessage('uci');
    }

    installFsfPromptQueue(lines: string[]) {
        if (this.fsfOriginalPrompt === undefined) this.fsfOriginalPrompt = window.prompt;
        this.fsfInputQueue = lines;
        window.prompt = ((message?: string, defaultValue?: string): string => {
            const line = this.fsfInputQueue.shift();
            if (line !== undefined) return line;
            if (this.fsfDebug) {
                console.warn('Fairy-Stockfish requested unexpected stdin input:', message, defaultValue);
            }
            return '';
        }) as typeof window.prompt;
    }

    restoreFsfPrompt() {
        if (this.fsfOriginalPrompt !== undefined) {
            window.prompt = this.fsfOriginalPrompt;
            this.fsfOriginalPrompt = undefined;
        }
        this.fsfInputQueue = [];
    }

    onFSFline = (line: string) => {
        if (this.fsfDebug) console.debug('--->', line);

        if (line.startsWith('info')) {
            const error = 'info string ERROR: ';
            if (line.startsWith(error)) {
                this.fsfError.push(line.slice(error.length));
                if (line.includes('terminated')) {
                    const suggestion = _('Try browser page reload.');
                    this.fsfError.push('');
                    this.fsfError.push(suggestion);
                    const errorMsg = this.fsfError.join('\n');
                    void alertDialog({ text: errorMsg });
                    return;
                }
            }
        }

        // The only signal that a search has finished. Without it the ladder cannot advance: a
        // search that stops on its own is otherwise indistinguishable from one still running.
        if (line.startsWith('bestmove')) this.onSearchEnd();

        if (line.includes('uciok')) this.restoreFsfPrompt();

        if (line.includes('readyok')) this.isEngineReady = true;

        if (line.startsWith('Fairy-Stockfish')) {
            this.loadVariantsIntoFsfEngine();
        }

        // reuse renderInput (not a bare { attrs: { disabled: false } }) so the change
        // listener's `on` data is always present — patching a data-less vnode against
        // a retained old vnode that does carry `on` makes snabbdom's eventlisteners
        // module treat the listener as removed, not merely left unspecified
        this.vinput = patch(this.vinput, h('input#input', this.renderInput()));

        this.fsfEngineBoard = new this.ffish.Board(this.ctrl.variant.name, this.ctrl.boardA.fullfen, false);
        window.addEventListener('beforeunload', () => this.fsfEngineBoard.delete());

        if (!this.engineOn || !this.isEngineReady) return;

        const info = parseUciInfoLine(line);
        if (!info) {
            if (line.includes('mate 0')) this.clearPvlines();
            return;
        }
        const { depth, multiPv, isMate, povEv, evalType, nodes, elapsedMs, moves } = info;
        //console.log("---", depth, multiPv, isMate, povEv, evalType, nodes, elapsedMs, moves);

        // Sometimes we get #0. Let's just skip it.
        if (isMate && !povEv) return;

        // For now, ignore most upperbound/lowerbound messages.
        // The exception is for multiPV, sometimes non-primary PVs
        // only have an upperbound.
        // See: https://github.com/ddugovic/Stockfish/issues/228
        if (evalType && multiPv === 1) return;

        let score;
        if (isMate) {
            score = { mate: povEv };
        } else {
            score = { cp: povEv };
        }
        const knps = nodes / elapsedMs;
        // The board this `info` line is about is the one the engine is on RIGHT NOW. It used to be
        // derived as `boardA.localAnalysis ? boardA : boardB`, which only has an answer while at
        // most one board is enabled — with both on it silently means "board A", every time.
        const boardInAnalysis = this.sliceBoard ?? this.ctrl.boardA;
        this.depthReached[boardInAnalysis.boardName] = depth;
        const msg: MsgAnalysis = {
            type: 'local-analysis',
            ply: this.ctrl.movelistView.ply(),
            color: boardInAnalysis.turnColor.slice(0, 1),
            ceval: { d: depth, multipv: multiPv, p: moves, s: score, k: knps },
        };
        this.onMsgAnalysis(msg, boardInAnalysis);
    };

    engineStop = () => {
        this.isEngineReady = false;
        // Nothing may follow this search: clearing both is what stops the `bestmove` that `stop`
        // provokes from being read as "slice finished, start the next one".
        this.sliceBoard = undefined;
        this.pendingStart = undefined;
        this.fsfPostMessage('stop');
        this.fsfPostMessage('isready');
    };

    /* Start the ladder over, from the base depth, on `cc`.
       If a search is still in flight this cannot send `position` — that is undefined behaviour in
       UCI — so it asks the engine to stop and leaves the restart to the `bestmove` that follows. */
    engineGo = (cc: GameControllerBughouse) => {
        // A fresh ladder: nothing has been searched at the new ceiling or the new position yet.
        this.depthReached = { a: 0, b: 0 };
        this.finished = { a: false, b: false };
        if (this.searching) {
            this.pendingStart = cc;
            this.fsfPostMessage('stop');
            return;
        }
        this.sendEngineOptions();
        this.startSlice(cc);
    };

    /* Sent once per ladder rather than once per slice: none of these change between the two
       boards, and a `setoption` is only legal while the engine is idle anyway. */
    private sendEngineOptions = () => {
        if (this.chess960) {
            this.fsfPostMessage('setoption name UCI_Chess960 value true');
        }
        if (this.ctrl.variant.name !== 'chess') {
            this.fsfPostMessage('setoption name UCI_Variant value ' + this.ctrl.variant.name);
        }
        this.fsfPostMessage('setoption name Use NNUE value false');
        this.fsfPostMessage('setoption name Threads value ' + maxThreads);
        this.fsfPostMessage('setoption name MultiPV value ' + this.multipv);
        // Two positions share one table now, so it is sized for two. Left unset it was whatever
        // the wasm build defaults to, which is the smallest thing that would still work for one.
        this.fsfPostMessage('setoption name Hash value 128');
    };

    /* One visit to one board. The hash is NOT cleared between visits — that is the whole
       mechanism, see the ladder constants at the top of this file. */
    /* ONE PLY PER VISIT: this board's own achieved depth plus one, floored at the base so a first
       visit does not crawl up from 1, and capped at the ceiling. No `movetime` — the slice ends
       when the ply lands, which is the whole point of slicing by depth. */
    private startSlice = (cc: GameControllerBughouse) => {
        this.sliceBoard = cc;
        this.searching = true;
        this.fsfPostMessage('position fen ' + cc.fullfen);
        const achieved = this.depthReached[cc.boardName];
        this.sliceTarget = Math.min(Math.max(achieved + 1, ladderBaseDepth), this.maxDepth);
        this.fsfPostMessage(`go depth ${this.sliceTarget}`);
    };

    /* A search ended — either it reached the slice's target or it hit the cap. Hand the engine to
       the other board; when that brings us back to where the ladder started, raise the target.
       Both boards therefore always sit at the same rung, give or take the slice in progress. */
    private onSearchEnd = () => {
        this.searching = false;

        if (this.pendingStart) {
            const cc = this.pendingStart;
            this.pendingStart = undefined;
            this.sendEngineOptions();
            this.startSlice(cc);
            return;
        }

        if (!this.engineOn || !this.sliceBoard) return;

        /* Book the slice that just ended. Reaching the ceiling finishes a board; so does ending
           BELOW the depth asked for, which without a timer can only mean the engine had nothing
           more to give — a forced mate, or no legal move to search. */
        const justRan = this.sliceBoard.boardName;
        const achieved = this.depthReached[justRan];
        if (achieved >= this.maxDepth || achieved < this.sliceTarget) this.finished[justRan] = true;

        /* Only boards still worth visiting. */
        const live = ([this.ctrl.boardA, this.ctrl.boardB] as const).filter(cc => !this.isTopped(cc));

        /* BOTH TOPPED OUT: the engine goes idle rather than looping. There is nothing left to
           learn at this ceiling, and the only thing that can change is the ceiling itself — which
           is what the Go-deeper button does, and it restarts the ladder itself. The switch stays
           on; what stops is the scheduling. */
        if (live.length === 0) {
            this.sliceBoard = undefined;
            return;
        }

        /* Hand over after every ply. Each board's next target is its own achieved depth plus one,
           computed in `startSlice`, so there is no shared rung to keep in step. */
        this.startSlice(live.length === 1 ? live[0] : this.sliceBoard.partnerCC);
    };

    /* Read only from `onSearchEnd`, never mid-search: `depthReached` climbs from 1 while a search
       is in flight. */
    private isTopped = (cc: GameControllerBughouse) => this.finished[cc.boardName];

    // Raises the ladder's ceiling; the ladder itself restarts from the base and climbs to it.
    onMoreDepth = () => {
        this.maxDepth = 99;
        this.engineStop();
        this.engineGo(this.ctrl.boardA);
    };

    makePvMove(pv_line: string, cc: GameControllerBughouse) {
        const move = uci2cg(pv_line.split(' ')[0]);
        this.ctrl.sendMove(cc, move /*move.slice(0, 2) as cg.Orig, move.slice(2, 4) as cg.Key, move.slice(4, 5)*/);
    }

    // Updates PV, score, gauge and the best move arrow
    /* One variation, ply by ply, lending whatever the mover does not hold — see `lendPiece`.
       Returns the nodes to render, or an empty list if not even the first ply converts, which is
       the one case where the caller keeps whatever the row already showed. */
    private renderVariation = (fen: string, pv: string): (VNode | string)[] => {
        const out: (VNode | string)[] = [];
        if (!this.fsfEngineBoard) return out;
        try {
            this.fsfEngineBoard.setFen(fen);
            for (const uci of pv.split(' ')) {
                const white: boolean = this.fsfEngineBoard.turn();
                const moveNo: number = this.fsfEngineBoard.fullmoveNumber();
                const at = uci.indexOf('@');
                let borrowed = false;
                if (at > 0) {
                    const piece = uci.slice(0, at);
                    const held: string = this.fsfEngineBoard.pocket(white);
                    if (!held.toLowerCase().includes(piece.toLowerCase())) {
                        this.fsfEngineBoard.setFen(lendPiece(this.fsfEngineBoard.fen(), piece, white));
                        borrowed = true;
                    }
                }
                const san: string = this.fsfEngineBoard.sanMove(uci, this.notationAsObject);
                if (!san || !this.fsfEngineBoard.push(uci)) break;
                if (out.length > 0) out.push(' ');
                // Black leads the line with `12...`; White is numbered every time, as in a movelist.
                if (white) out.push(`${moveNo}. `);
                else if (out.length === 0) out.push(`${moveNo}...`);
                out.push(...sanNodes(san, borrowed));
            }
        } catch {
            return out;
        }
        return out;
    };

    drawEval = (
        ceval: Ceval | undefined,
        scoreStr: string | undefined,
        turnColor: cg.Color,
        boardInAnalysis: GameControllerBughouse,
    ) => {
        const pvlineIdx = ceval && ceval.multipv ? ceval.multipv - 1 : 0;

        // Render PV line
        if (ceval?.p !== undefined) {
            const variation = this.renderVariation(boardInAnalysis.fullfen, ceval.p as string);
            if (variation.length > 0) {
                const pvSan = h(
                    'pv-san',
                    { on: { click: () => this.makePvMove(ceval.p as string, boardInAnalysis) } },
                    variation,
                );
                this.pvView(
                    boardInAnalysis.boardName,
                    pvlineIdx,
                    h('pvline', [
                        this.multipv > 1 && this.engineOn ? h('strong', scoreStr) : '',
                        pvSan,
                    ]),
                );
            } else {
                /* Not even the first ply converted. The row is BLANKED rather than left alone:
                   left alone it keeps a variation from an earlier depth, which reads as current
                   and is the more misleading of the two. */
                this.pvView(boardInAnalysis.boardName, pvlineIdx, h('pvline', this.engineOn ? h('pvline', '-') : ''));
            }
        } else {
            this.pvView(boardInAnalysis.boardName, pvlineIdx, h('pvline', this.engineOn ? h('pvline', '-') : ''));
        }

        // Render gauge, arrow and main score value for first PV line only
        if (pvlineIdx > 0) return;

        let shapes0: DrawShape[] = [];
        boardInAnalysis.chessground.setAutoShapes(shapes0);

        /* BY POSITION, NOT BY IDENTITY. `#gauge` lives in the own stack and `#gaugePartner` in the
           partner stack, so asking `boardName == 'a'` painted board A's evaluation onto the gauge
           beside board B for any viewer who played on board B. Latent until someone opens their
           own game from that seat; the two-column PV list would have made it visible, one column
           disagreeing with the gauge right next to it. */
        const isOwnBoard = boardInAnalysis.boardName === this.ownBoard;
        const gaugeEl = document.getElementById(isOwnBoard ? 'gauge' : 'gaugePartner') as HTMLElement;
        if (gaugeEl && pvlineIdx === 0) {
            const fillEl = gaugeEl.querySelector('div.fill') as HTMLElement | undefined;
            if (fillEl && ceval !== undefined) {
                const score = ceval['s'];
                const color = turnColor;
                if (score !== undefined) {
                    const ev = povChances(color, score);
                    fillEl.style.height = String(100 - (ev + 1) * 50) + '%';
                } else {
                    fillEl.style.height = '50%';
                }
            }
        }

        if (ceval?.p !== undefined) {
            const pv_move = uci2cg(ceval.p.split(' ')[0]);
            // console.log("ARROW", this.arrow);
            if (this.arrow && pvlineIdx === 0) {
                const atPos = pv_move.indexOf('@');
                if (atPos > -1) {
                    const d = pv_move.slice(atPos + 1, atPos + 3) as cg.Key;
                    let color = turnColor;
                    const dropPieceRole = util.roleOf(pv_move.slice(0, atPos) as cg.Letter);

                    shapes0 = [
                        {
                            orig: d,
                            brush: 'paleGreen',
                            piece: {
                                color: color,
                                role: dropPieceRole,
                            },
                        },
                        { orig: d, brush: 'paleGreen' },
                    ];
                } else {
                    const o = pv_move.slice(0, 2) as cg.Key;
                    const d = pv_move.slice(2, 4) as cg.Key;
                    shapes0 = [{ orig: o, dest: d, brush: 'paleGreen', piece: undefined }];
                }
            }

            if (isOwnBoard) {
                this.vscore = patch(this.vscore, h('score#score', scoreStr));
            } else {
                this.vscorePartner = patch(this.vscorePartner, h('score#scorePartner', scoreStr));
            }

            const info = [h('span', _('Depth') + ' ' + String(ceval.d) + '/' + this.maxDepth)];
            if (ceval.k) {
                if (ceval.d === this.maxDepth && this.maxDepth !== 99) {
                    info.push(
                        h('a.icon.icon-plus-square', {
                            attrs: { href: '#', 'aria-label': _('Go deeper') },
                            props: { title: _('Go deeper') },
                            on: {
                                click: (e: Event) => {
                                    e.preventDefault();
                                    this.onMoreDepth();
                                },
                            },
                        }),
                    );
                } else if (ceval.d !== 99) {
                    // No leading comma: the two spans are separate LINES in the board's column
                    // now, not a phrase running across the panel's full width.
                    info.push(h('span', Math.round(ceval.k) + ' knodes/s'));
                }
            }
            this.setInfo(isOwnBoard, info);
        } else {
            if (isOwnBoard) {
                this.vscore = patch(this.vscore, h('score#score', ''));
            } else {
                this.vscorePartner = patch(this.vscorePartner, h('score#scorePartner', ''));
            }
            this.setInfo(isOwnBoard, '');
        }

        // console.log(shapes0);
        boardInAnalysis.chessground.set({
            drawable: { autoShapes: shapes0 },
        });
    };

    private onMsgAnalysis = (msg: MsgAnalysis, boardInAnalysis: GameControllerBughouse) => {
        // console.log(msg);
        if (msg['ceval']['s'] === undefined) return;
        const scoreStr = buildScoreStr(msg.color, msg.ceval);
        const turnColor = msg.color === 'w' ? 'white' : 'black';
        this.drawEval(msg.ceval, scoreStr, turnColor, boardInAnalysis);
    };
}

/* THE PAGE'S ONE ENGINE SETTING.
   `MultiPVSettings` in `client/analysis/analysisSettings.ts` cannot be reused as it stands: its
   `update()` reaches for `ctrl.multipv`, `ctrl.autoShapes` and `ctrl.chessground`, none of which
   this page has — `multipv` lives on this widget, and there are two chessgrounds. What is shared
   instead is the stored value: the key is deliberately still `multipv`, so a reader who set three
   lines on the single-board page still gets three here.

   `NumberSettings`' setter writes localStorage and then calls `update()`, so this class only has
   to hand the new value to the widget that owns the panel. */
class MultiPvSetting extends NumberSettings {
    private vrange: VNode | HTMLElement;

    constructor(private readonly engine: EngineController) {
        super('multipv', 1);
        this.vrange = h('div.multipv_range_value', this.readout());
    }

    private readout(): string {
        return `${clampMultiPv(this.value)} / ${maxMultiPv}`;
    }

    update(): void {
        this.vrange = patch(this.vrange, h('div.multipv_range_value', this.readout()));
        this.engine.onMultiPvChange(this.value);
    }

    /* The row is built here rather than in `pvPanel()` so that the control and the readout it
       has to keep in step stay in one place. `slider()` binds `input`, so this fires while the
       thumb is dragged; the engine restart that follows is idempotent and the last value wins. */
    view(): VNode {
        return h('div.labelled.multipv-setting', [
            ...slider(this, 'multipv', 1, maxMultiPv, 1, _('Multiple lines')),
            this.vrange as VNode,
        ]);
    }
}
