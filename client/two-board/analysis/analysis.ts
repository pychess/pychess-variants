import { h, VNode } from 'snabbdom';
import { BoardSummaryView } from '../../accessibility/boardSummary';
import { pageHeading } from '../../view';

import { _ } from '../../i18n';
import { GameInfoView } from '../common/gameInfo';
import { VARIANTS, selectVariant, validVariant } from '../../variants';

import { renderTimeago } from '../../datetime';
import { BugBoardName, PyChessModel } from '../../types';
import AnalysisControllerBughouse from './analysisCtrl';
import { gauge } from '@/analysis';
import { TabbedPanels, TabPanelDef } from '../common/tabs';
import { registerStandingTab } from '../common/toolsPlacement';
import { trackSquareUnit } from '../squareUnit';
import { boardZoom } from '@/boardSettings';
import { ownBoardName } from '../common/boardRoles';
import { twoBoardSeats } from '../common/seatConfiguration';
import { MovelistView } from '../common/movelist';
import { EngineController } from './engine';
import { PgnView } from './pgn';
import { AnalysisClockView } from './analysisClock';
import { AnalysisSeatView } from './analysisSeatView';
import { MovetimeChartView } from './movetimeChart';

/** The blank analysis board's variant picker, the content of its VARIANT tab.
 *
 * Only that build has one: a real game's variant is the game's, and its tools column carries
 * Info and Chat where this one carries this. What used to be one `leftSide()` answering both
 * cases is two declarations at the tab list now, so neither branch has to ask which page it
 * is on. */
function variantSelector(model: PyChessModel): VNode {
    const setVariant = (isInput: boolean) => {
        const e = document.getElementById('variant') as HTMLSelectElement;
        const variant = e.options[e.selectedIndex].value;
        if (isInput) {
            window.location.assign('/analysis/' + validVariant(variant));
        }
    };

    return h('div.container', [
        h('div', [
            h('label', { attrs: { for: 'variant' } }, _('Variant')),
            selectVariant(
                'variant',
                model.variant || 'chess',
                () => setVariant(true),
                () => setVariant(false),
                [],
                model.gameCategory,
            ),
        ]),
    ]);
}

function createBoards(
    mainboardVNode: VNode,
    bugboardVNode: VNode,
    mainboardPocket0: VNode,
    mainboardPocket1: VNode,
    bugboardPocket0: VNode,
    bugboardPocket1: VNode,
    model: PyChessModel,
    movelistView: MovelistView,
    gameInfoView: GameInfoView,
    engine: EngineController,
    pgnView: PgnView,
    clockView: AnalysisClockView,
    seatView: AnalysisSeatView,
    movetimeChartView: MovetimeChartView,
) {
    /*this.ctrl = */ const ctrl = new AnalysisControllerBughouse(
        mainboardVNode.elm as HTMLElement,
        mainboardPocket0.elm as HTMLElement,
        mainboardPocket1.elm as HTMLElement,
        bugboardVNode.elm as HTMLElement,
        bugboardPocket0.elm as HTMLElement,
        bugboardPocket1.elm as HTMLElement,
        model,
        movelistView,
        gameInfoView,
        engine,
        pgnView,
        clockView,
        seatView,
        movetimeChartView,
    );
    window['onFSFline'] = ctrl.engine.onFSFline;
}

export function analysisView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant];
    const isAnalysisBoard = model['gameId'] === '';

    /* MUST run before the boards are constructed, for the same reason it must on the round
       page: the grid tracks reference the published unit with no fallback, so chessgroundx
       has to measure a wrap that is already at its final size. Publish it late and the
       boards move under an already-memoized `bounds`, and every click lands on the wrong
       square.

       The zoom is passed in rather than read inside squareUnit.ts, which must not import
       boardSettings — boardSettings calls back into it when a slider moves, and the two
       importing each other is a module-evaluation cycle. */
    trackSquareUnit({
        a: boardZoom(VARIANTS[model.variant].boardFamily, 'a'),
        b: boardZoom(VARIANTS[model.variant].boardFamily, 'b'),
    });

    renderTimeago();

    const onClickFullfen = () => {
        const el = document.getElementById('fullfen') as HTMLInputElement;
        el.focus();
        el.select();
    };

    let mainboardVNode: VNode,
        bugboardVNode: VNode,
        mainboardPocket0: VNode,
        mainboardPocket1: VNode,
        bugboardPocket0: VNode,
        bugboardPocket1: VNode;

    /* Which board is the viewer's own. Decided from seats, so a player of this game gets
       their own board in the main position — left in landscape, bottom in portrait — and
       anyone who did not play gets board A. The round page has no need of it, because its
       switch does the placing.

       Declared HERE, above the views, because the engine needs it too: its PV columns, its two
       scores and its two gauges are all keyed to which board sits where, and the tools panel
       below is built before the stacks are. */
    const ownBoard = ownBoardName(twoBoardSeats(model, model.username));

    const movelistView = new MovelistView();
    const gameInfoView = new GameInfoView();
    const engine = new EngineController(model.chess960 === 'True', ownBoard);
    const pgnView = new PgnView();
    const clockView = new AnalysisClockView();
    const seatView = new AnalysisSeatView();
    const movetimeChartView = new MovetimeChartView();

    /* THE TOOLS COLUMN, as a tabbed panel beside the boards.
       Three tabs, and the grouping is the decision worth stating:

       MOVES holds the movelist, the move controls AND the whole engine — its switches,
       its name panel, its principal variation and #misc-info. They are one activity,
       reading the game, and splitting the evaluation from the move it evaluates would
       make a reader choose which half to look at.

       IT IS ONE TAB IN THREE PARTS, and the two statements do not conflict. A PART is the
       smallest thing this page can PLACE — a named grid area holds one item, so a single
       panel can only ever be in one place at a time. Selecting a tab shows every one of its
       parts, so the reader still has the evaluation beside the move it evaluates however the
       parts are arranged; what the split buys is that the engine box and the button row can
       go somewhere the movelist cannot follow. Both are content-height and read at a glance,
       which is what zone A — the band the shorter board frees, measured empty at 701x829 — has
       room for. The rule for when they actually go there is a separate change; this one only
       makes them separable.

       INFO is the game information that used to sit bottom-left.

       CHAT is #roundchat, which is in this page's markup and renders nowhere visible.
       It is given a tab so it becomes observable and can then be judged — not because
       its home is decided. Deleting it would settle its fate without anyone ever having
       seen it. */
    /* ONE TABBED PANEL FOR THE WHOLE PAGE.
       There used to be two: this one beside the boards, and a second under them holding the move
       chart and FEN & PGN. Two switchers meant two places to look for a thing that is not on
       screen, and the lower one cost the page a full-width row of its own — which is what put the
       chart below the fold in every mode. Merged, the page has one place where everything that is
       not a board lives.

       The tabs are declared as data rather than inline, because the page mounts one panel per tab
       and that list has to follow the declarations. It used to mount `panel(0,0)`, `panel(1,0)`,
       `panel(2,0)` by hand, which was already wrong for the blank analysis board: that build
       declares only ONE tab, and `panel(1, 0)` on a one-tab widget is an index error. */
    const toolPanels: TabPanelDef[] = [
            {
                label: _('Moves'),
                /* THE RECORD, THE BUTTONS, AND THE ENGINE BOX — three parts, and this order is
                   the DROP QUEUE's, not a matter of reading pleasure. Zone A grows upwards from
                   the bottom row of the strip, so a part's row is its place in the queue: the
                   first to leave must be in the last row and whatever never leaves must be in the
                   first. The move list never leaves — it is the one part useless in a band four
                   squares tall — so it holds row 1; the engine box leaves before the controls,
                   being the taller of the two, so it sits below them. See the `zoneTools` rules in
                   `bughouse.css` and the droppable list in `analysisCtrl.ts`.

                   Each boundary is drawn where the thing behind it is one whole:

                   The ENGINE is its switch, both boards' numbers, its name, both PV columns and
                   the Multiple-lines control that decides how many lines there are. The control
                   belongs with the lines it counts, which is why the pv box comes with it rather
                   than staying with the movelist.

                   The RECORD is the movelist block and #misc-info, which is the movelist's own
                   footer on the single-board page and empty on this one.

                   The CONTROLS are the six buttons: flip, switch, start, back, forward, end.
                   They act on the position, not on the list, and they are the one part here whose
                   whole content is a row — 100.8px wide and 40px tall, which is why a narrow band
                   can take them. */
                parts: [
                    {
                        panelClass: 'analysis-moves-panel',
                        content: [
                            h('div.movelist-block', [movelistView.placeholder()]),
                            h('div#misc-info', [
                                h('div#misc-infow'),
                                h('div#misc-info-center'),
                                h('div#misc-infob'),
                            ]),
                        ],
                    },
                    {
                        panelClass: 'analysis-controls-panel',
                        content: [h('div#move-controls')],
                    },
                    {
                        panelClass: 'analysis-engine-panel',
                        content: [h('div#ceval', [engine.renderPanel()]), engine.pvPanel()],
                    },
                ],
            },
            /* The two builds differ here, and each gets the tabs its page actually has.
               A real game has game info and chat; the blank analysis board
               (`/analysis/<variant>`, no gameId) has neither — what it has is the variant
               selector, and VARIANT is its tab.

               It is a tab because the tools column is where everything that is not a board
               lives, and the selector was the last thing outside it. Sitting in the app's
               grid instead, it had no area of its own: the templates here name
               `ownstack stack zoneTools1/2 zoneA zoneB` and nothing else, so `gameinfo`
               and `uleft` were UNKNOWN names and grid put each in an implicit track of its
               own. On a real game both elements are empty and those tracks measure 0px,
               which is why this went unseen; on the blank board the selector gave one of
               them a size and it took 261.6px of column and 82.7px of row away from the
               tracks the boards are sized against. The boards then overlapped. */
            ...(isAnalysisBoard
                ? [{ label: _('Variant'), parts: [{ content: [variantSelector(model)] }] }]
                : [
                      {
                          label: _('Info'),
                          /* The spectator list, in the same home the round page gives it and for
                             the reasons recorded there. This page cannot even receive one — it
                             opens no websocket at all — so the placeholder is here for parity
                             rather than for content, and it costs a template nothing now. */
                          parts: [
                              {
                                  // the round page's panel, named the same way and for the same
                                  // reason: game info above the watchers, not beside them
                                  panelClass: 'info-panel',
                                  content: [gameInfoView.placeholder(), h('spectators#spectators')],
                              },
                          ],
                      },
                      { label: _('Chat'), parts: [{ content: [h('div#roundchat')] }] },
                  ]),
        /* MOVE TIMES IS A GAME'S TAB, not this page's. The blank board has no recorded game
           behind it — it is somewhere to explore lines — so there are no move times to chart
           and the tab would open on an empty box. `movetimeChart()` agrees already: the
           controller only calls it for a board message carrying more than one step, which the
           blank board never receives. The tab and the chart element it mounts now come and go
           together, on the one flag.

           `chart-container` and `fenpgn-panel` keep their classes: the chart's is what
           analysis.css sizes, and the pgn one mirrors that file's `#panel-4` rule for the
           single-board page. */
        ...(isAnalysisBoard
            ? []
            : [
                  {
                      label: _('Move times'),
                      parts: [{ panelClass: 'chart-container', content: [movetimeChartView.placeholder()] }],
                  },
              ]),
        {
            label: _('FEN & PGN'),
            parts: [
                {
                    panelClass: 'fenpgn-panel',
                    content: [
                        h('div#fentext', [
                            h('strong', 'BFEN'),
                            h('input#fullfen', {
                                attrs: { readonly: true, spellcheck: false },
                                on: { click: onClickFullfen },
                            }),
                        ]),
                        ...pgnView.placeholders(),
                    ],
                },
            ],
        },
    ];

    /* A CLOCK IS A GAME'S, like Move times above. The blank board has no game behind it, so
       there are no clock values to show and the four slots rendered as empty discs around the
       boards. `renderClocks()` was never going to fill them: it reads `clocks`/`clocksB` off the
       current step, and neither the seeded start step nor a step this page builds while
       exploring carries either — so on this build the slots stay as they are mounted, forever.
       Not mounting them is the same statement, made once here. */
    const clockSlots = (top: () => VNode, bottom: () => VNode) =>
        isAnalysisBoard ? { top: [], bottom: [] } : { top: [top()], bottom: [bottom()] };
    const mainClocks = clockSlots(() => clockView.topPlaceholder(), () => clockView.bottomPlaceholder());
    const bugClocks = clockSlots(() => clockView.bugTopPlaceholder(), () => clockView.bugBottomPlaceholder());

    /* Built once and placed by `ownBoard` below, rather than written twice inline. Each
       board element keeps its IDENTITY id — #mainboard is board A whoever plays on it —
       while its POSITION is chosen here and its role marked from that position. */
    const mainboardSel = h(
        `selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
        [
            ...mainClocks.top,
            h('div.cg-wrap.' + variant.board.cg, {
                hook: { insert: vnode => (mainboardVNode = vnode) },
            }),
            ...mainClocks.bottom,
        ],
    );
    const bugboardSel = h(
        `selection#bugboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
        [
            ...bugClocks.top,
            h('div.cg-wrap.' + variant.board.cg, {
                hook: { insert: vnode => (bugboardVNode = vnode) },
            }),
            ...bugClocks.bottom,
        ],
    );
    const gaugeOwn = gauge(variant.colors);
    const gaugePartnerEl = gauge(variant.colors, 'gaugePartner', 'flipped');

    /* WHICH BOARD IS WHICH, said once per board.
       The stacks are placed by ROLE — the viewer's own board goes left in landscape, bottom in
       portrait — so nothing on the page states a board's IDENTITY, and identity is what the
       engine's PV columns, the pockets, the movelist and the game record are all keyed to. The
       letter goes in the gauge's own column, immediately under it, so it reads as belonging to
       the board the gauge reports on rather than to the seam between the two. */
    const boardLabel = (board: BugBoardName) => h('div.board-label', board.toUpperCase());

    const pocket = (cls: string, id: string, keep: (vnode: VNode) => void) =>
        h('div.' + cls, [
            h('div.' + variant.pieceFamily + '.twoboards', [
                h('div.cg-wrap.pocket', [h('div#' + id, { hook: { insert: keep } })]),
            ]),
        ]);
    const pocketA0 = pocket('pocket-top', 'pocket00', v => (mainboardPocket0 = v));
    const pocketA1 = pocket('pocket-bot', 'pocket01', v => (mainboardPocket1 = v));
    const pocketB0 = pocket('pocket-top-partner', 'pocket10', v => (bugboardPocket0 = v));
    const pocketB1 = pocket('pocket-bot-partner', 'pocket11', v => (bugboardPocket1 = v));

    /* A SEAT STRIP: one seat's pocket beside its player bar, as a single stack row.
       The round page's element, class for class, so the strip skeleton and the whole
       of the name's own sizing machinery apply here without a second copy — see the
       `.seat-strip0, .seat-strip1` block in bughouse.css.

       It carries a POSITION class and a ROLE class and nothing else. Position says
       which end of its board it is (0 = top), which is what decides whether the name
       leaves the row upwards or downwards. Role says whose board it belongs to, and
       comes from the stack it is being built into — never from the board's identity,
       which is board A for a board-B player's own board.

       The player bar arrives empty: `AnalysisSeatView` patches it once the controller
       exists, keyed by physical position, exactly as the clocks are. */
    const partnerBoard: BugBoardName = ownBoard === 'a' ? 'b' : 'a';
    const strip = (position: 0 | 1, role: 'own' | 'partner', board: BugBoardName, pocketVNode: VNode) =>
        h(`div.seat-strip${position}.${role}-seat`, [pocketVNode, seatView.placeholder(board, position)]);

    /* THE PARTNER'S BOARD IS A TAB, AND IT IS DETACHED FROM THE FIRST FRAME — the same statement
       the round page makes, in the same words, because it is the same board in the same predicament.
       Detached it is absent from the strip and always drawn, which is every home but the last
       resort; there the tools have nowhere left to go and take the board's own column, and the
       board takes its turn in it as a tab.
       THE GAUGE AND THE LABEL COME WITH IT. They are part of the stack, not neighbours of it — the
       gauge is a term in this page's width formula, the 0.31 of `8.31` squares — so a home that
       hides the board must hide them too, or they are left beside whatever replaced it.
       Declared HERE rather than beside the other tabs above because a tab holds its content, and
       this content is the board: `strip`, the board selections and the gauge do not exist until
       this point in the view. The widget is therefore constructed here too. */
    /* FIRST IN THE STRIP, NOT LAST. A tab's position in the strip is its position in this list, and
       the partner's board is the one tab that is a BOARD: where the strip shows it at all — the last
       resort, and nowhere else — it is what the reader is looking for, so it goes at the head of the
       row rather than after four panels. `unshift` because the content has to be built first: the
       strips, the board selections and the gauge do not exist until this point in the view. */
    toolPanels.unshift({
        label: _('Partner board'),
        detached: true,
        parts: [
            {
                panelClass: 'bug-partner-stack',
                /* `grid`, AND THE VALUE MATTERS MORE HERE THAN ANYWHERE ELSE ON THE PAGE.
                   A part's display is written as an INLINE style, so it beats the stylesheet: this
                   one word decides what `.analysis-app.bug .bug-partner-stack` is allowed to be.
                   This page's stacks are TWO-COLUMN GRIDS — board over pockets in the first column,
                   the gauge parked in the board's row in the second — and the first column is
                   `calc(var(--bug-stack-sq) * 8)`, which is where the partner board's width comes
                   from.

                   It said `block` for a while, copied from the round page, where a stack really is
                   block flow. The consequence was not a stack laid out differently; it was a stack
                   with NO DEFINITE WIDTH. `.cg-wrap` resolves its height from percentage padding
                   against its own width, so board B stopped following `--bug-sq-b` and instead took
                   whatever its grid area gave it — the app's `auto` track, whose base is the seat
                   strip's max-content. Measured at 1276x430: columns 354.6 / 225.1 / 679.1 with
                   board A at 341 and board B at 225, the partner's gauge 225 wide and ZERO tall in
                   block flow, and the partner's pockets 213 (5 squares, sized from the variable as
                   intended) beside a 225 board. Flipping this one value: 354.6 / 354.6 / 549.6,
                   both boards 341, the gauge back in the board's row — and the tools still 550 wide.
                   The partner board being smaller than the viewer's own is a DECISION this page has
                   yet to take; it was not this. */
                display: 'grid',
                content: [
                    strip(0, 'partner', partnerBoard, ownBoard === 'a' ? pocketB0 : pocketA0),
                    ownBoard === 'a' ? bugboardSel : mainboardSel,
                    strip(1, 'partner', partnerBoard, ownBoard === 'a' ? pocketB1 : pocketA1),
                    gaugePartnerEl,
                    boardLabel(partnerBoard),
                ],
            },
        ],
    });
    const PARTNER_BOARD_TAB = 0;
    const toolsTabs = new TabbedPanels('analysis-tools', toolPanels, _('Analysis tools'));
    registerStandingTab(toolsTabs, PARTNER_BOARD_TAB);

    return [
        pageHeading(),
        h(
            'div.analysis-app.bug',
            {
                hook: {
                    insert: () => {
                        createBoards(
                            mainboardVNode,
                            bugboardVNode,
                            mainboardPocket0,
                            mainboardPocket1,
                            bugboardPocket0,
                            bugboardPocket1,
                            model,
                            movelistView,
                            gameInfoView,
                            engine,
                            pgnView,
                            clockView,
                            seatView,
                            movetimeChartView,
                        );
                    },
                },
            },
            [
                /* NOTHING BUT THE STACKS AND THE TOOLS IS A CHILD OF THIS GRID. The blank
                   board's variant selector used to be, wrapped in `.bug-game-info`, and it
                   is a tab of the tools panel now — see the tab declarations above for what
                   that wrapper cost. Anything added here in future needs an area in EVERY
                   template below, or it lands in an implicit track and silently steals the
                   boards' space. */
                /* TWO STACKS, mirroring the round page. Each is pocket / board / pocket in
                   block flow — the same ten rows the round page's square unit is computed
                   over, which measurement confirmed this page already has: the analysis
                   clocks are absolutely positioned overlays on the board and add no height.

                   The stacks carry the round page's own class names deliberately. That is
                   what lets `isOutsidePartnerStack()` answer here unchanged, and what makes
                   the coordinate machinery keyed to `.bug-own-stack, .bug-partner-stack`
                   apply without a second copy.

                   WHICH board goes in which stack is decided by seats — see
                   `ownBoardName()` — so a player always finds their own board in the main
                   position, and anyone who did not play gets board A there. */
                /* THE GAUGE GOES INSIDE THE STACK, in the board's own row.
                   It was a sibling of the stack at first, which placed it correctly
                   left-to-right but not vertically: the stack is pocket / board / pocket,
                   so a sibling spans all three and the gauge ran the pocket's height taller
                   at each end. Inside the stack it occupies the BOARD's row and stretches
                   to exactly the board's height — by construction, with no arithmetic and
                   nothing to keep in step when a pocket changes size. */
                h('div.bug-own-stack', [
                    strip(0, 'own', ownBoard, ownBoard === 'a' ? pocketA0 : pocketB0),
                    ownBoard === 'a' ? mainboardSel : bugboardSel,
                    strip(1, 'own', ownBoard, ownBoard === 'a' ? pocketA1 : pocketB1),
                    gaugeOwn,
                    boardLabel(ownBoard),
                ]),
                /* THE PARTNER'S STACK AND THE TOOLS, siblings of the viewer's stack. They were
                   wrapped in `div.partner-and-tools` — the round page's element, reused here —
                   until every mode dissolved it. Landscape always did, with `display: contents`;
                   portrait was the last mode to keep it as a box, and when it stopped, an element
                   with no box anywhere was a level of nesting nothing read. Both pages lost it
                   together, as they gained it together. */
                // The stack IS the panel — `panelClass` put `.bug-partner-stack` on the wrapper
                // rather than inside it, so nothing gained a level and the grid area it has
                // always occupied is still declared on the same element.
                toolsTabs.panel(PARTNER_BOARD_TAB, 0),
                /* Derived from the declarations above, so a tab can be added, made
                   conditional, or gain a part without a second list to keep in step. The
                   board's tab is index 0 and mounted above, so the slice starts at 1 and the
                   widget is asked for `t + 1`.
                   Every tab but the board's: that one is mounted above, in the column, which is
                   the whole point of a detached tab — the widget says whether a part is shown,
                   never where.

                   A TAB OF SEVERAL PARTS IS MOUNTED AS ONE GROUP, and the group is the grid
                   item its single panel used to be. Two items assigned the same named area do
                   not stack, they OVERLAP, so parts that still share a home have to be one
                   item — and the group takes the area the panel took in every home this page
                   has, which is why declaring the parts moves nothing on screen.

                   The element is the PAGE'S, not the widget's: the widget builds no container
                   around a tab's parts, deliberately, because that container is exactly what a
                   mode wanting one part elsewhere has to dissolve. The round page's
                   `.bug-presets-group` is the same element with its default the other way
                   round — dissolved everywhere, a box only in zone B, where two preset rows
                   must be one item to span both boards. Here the box is the default because
                   all three parts are still in the column together; the mode that relocates
                   one of them is what will dissolve it. */
                h('div.bug-parts', [
                    ...toolPanels.slice(PARTNER_BOARD_TAB + 1).map((panel, index) => {
                        const t = index + PARTNER_BOARD_TAB + 1;
                        const parts = panel.parts.map((_part, p) => toolsTabs.panel(t, p));
                        return parts.length === 1 ? parts[0] : h('div.bug-tool-group', parts);
                    }),
                    toolsTabs.tabList(),
                ]),
            ],
        ),
        BoardSummaryView.placeholder('a', 'polite'),
        BoardSummaryView.placeholder('b', 'polite'),
    ];
}
