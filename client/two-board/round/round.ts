import { h, VNode } from 'snabbdom';

import { VARIANTS } from '../../variants';
import { GameInfoView } from '../common/gameInfo';
import { SpectatorsView } from '../common/spectatorsView';
import { renderTimeago } from '../../datetime';
import { PyChessModel } from '../../types';
import { RoundControllerBughouse } from './roundCtrl';
import { MovelistView } from '../common/movelist';
import { RoundSeatView, RoundSeatViews } from './roundSeatView';
import { trackSquareUnit } from '../squareUnit';
import { boardZoom } from '@/boardSettings';
import { TabbedPanels } from '../common/tabs';
import { BoardSummaryView } from '../../accessibility/boardSummary';
import { registerStandingTab } from '../common/toolsPlacement';

// The partner board's position in the tab list below — FIRST. Named because two places need it and
// a tab's index is also its id.
//
// First rather than last because it is the one tab that is a BOARD: where the strip shows it at all
// — the last resort, and nowhere else — it is what the reader is looking for, so it heads the row
// instead of following three panels.
const PARTNER_BOARD_TAB = 0;
/* The tab the spectator list is in, and therefore the tab that carries their count. Named for the
   same reason the board's index is: an index into the list below reads as nothing at the call
   site, and the two are the only ones anything outside that list has to know. */
const INFO_TAB = 3;
import { ChatPresetsView } from './chatPresets';
import { twoBoardSeats } from '../common/seatConfiguration';
import { _ } from '../../i18n';

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
    spectatorsView: SpectatorsView,
    seatViews: RoundSeatViews,
    chatPresetsView: ChatPresetsView | undefined,
) {
    /*this.ctrl = */ /*const ctrl = */ new RoundControllerBughouse(
        mainboardVNode.elm as HTMLElement,
        mainboardPocket0.elm as HTMLElement,
        mainboardPocket1.elm as HTMLElement,
        bugboardVNode.elm as HTMLElement,
        bugboardPocket0.elm as HTMLElement,
        bugboardPocket1.elm as HTMLElement,
        model,
        movelistView,
        gameInfoView,
        spectatorsView,
        seatViews,
        chatPresetsView,
    );
    // window['onFSFline'] = ctrl.onFSFline;
}

export function roundView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant];

    // Ordering is load-bearing: the short-landscape grid sizes its board tracks
    // from --bug-sq, so the property must exist before createBoards() runs.
    // chessgroundx memoizes its hit-test bounds when a board is constructed, and
    // nothing observes a board that merely moves — so a board built against a
    // grid that changes afterwards keeps stale bounds and mis-resolves clicks.
    //
    // The zoom is passed in rather than read there, because the unit is quantised
    // at the scale the board will draw at and squareUnit.ts must not depend on
    // boardSettings — boardSettings calls back into it when a slider moves, and the
    // two importing each other is a module-evaluation cycle. Read from the setting
    // rather than from `--zoom-a`, which nothing has written this early: the
    // stylesheet default is 100 while the board is about to be drawn at 80.
    const boardFamily = variant.boardFamily;
    trackSquareUnit({ a: boardZoom(boardFamily, 'a'), b: boardZoom(boardFamily, 'b') });

    renderTimeago();

    let mainboardVNode: VNode,
        bugboardVNode: VNode,
        mainboardPocket0: VNode,
        mainboardPocket1: VNode,
        bugboardPocket0: VNode,
        bugboardPocket1: VNode;

    const movelistView = new MovelistView();
    const gameInfoView = new GameInfoView();
    const spectatorsView = new SpectatorsView();

    // A spectator has no partner to tell anything, so they get no presets — the
    // same condition the shared chat view used to apply, asked here instead, and
    // through the same seat logic the controller will use rather than a second
    // copy of it. When there are none, the Chat tab simply has one part.
    const chatPresetsView = twoBoardSeats(model, model.username).isSpectator()
        ? undefined
        : new ChatPresetsView(variant);

    const seatViews: RoundSeatViews = {
        a: [new RoundSeatView(0, 'a'), new RoundSeatView(1, 'a')],
        b: [new RoundSeatView(0, 'b'), new RoundSeatView(1, 'b')],
    };

    // One pocket per seat, handed to that seat's strip. The element itself still
    // belongs to the caller — chessgroundx is constructed against it below — but
    // where it sits is the strip's business, not the grid's.
    const pocket = (cls: string, id: string, keep: (vnode: VNode) => void): VNode =>
        h(`div.${cls}`, [
            h('div.' + variant.pieceFamily + '.twoboards', [
                h('div.cg-wrap.pocket', [h(`div#${id}`, { hook: { insert: keep } })]),
            ]),
        ]);

    const pocketA0 = pocket('pocket-top', 'pocket00', vnode => (mainboardPocket0 = vnode));
    const pocketA1 = pocket('pocket-bot', 'pocket01', vnode => (mainboardPocket1 = vnode));
    const pocketB0 = pocket('pocket-top-partner', 'pocket10', vnode => (bugboardPocket0 = vnode));
    const pocketB1 = pocket('pocket-bot-partner', 'pocket11', vnode => (bugboardPocket1 = vnode));

    // Each panel holds exactly one existing element, embedded as it is defined
    // elsewhere — their own `grid-area` declarations come along and are simply
    // inert now that they are panel children rather than grid items, the same way
    // the pockets' were when seats became strips. Every one is still rendered and
    // patched by its own owner, which is why they are embedded rather than rebuilt.
    const roundTabs = new TabbedPanels(
        'round-tabs',
        [
            /* THE PARTNER'S BOARD IS A TAB, AND IT IS DETACHED FROM THE FIRST FRAME.
               Detached it is absent from the strip and always drawn, which is the board in every
               home but one — so declaring it here changes nothing on screen today. What it buys is
               the LAST RESORT: on a viewport with no room for the tools anywhere, the strip claims
               the board's column and the board takes its turn there as a tab. That is one call to
               `setDetached`, with no element created, moved or destroyed, which matters because the
               home is chosen from the viewport and flips while a window is being dragged.
               `display: block` because a stack is block flow — strip, board, strip — and the
               widget's default of `flex` would relayout it every time it was shown. */
            {
                label: _('Partner board'),
                detached: true,
                parts: [
                    {
                        panelClass: 'bug-partner-stack',
                        display: 'block',
                        content: [
                            seatViews.b[0].view(pocketB0),
                            h(
                                `selection#bugboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
                                [
                                    h('div.cg-wrap.' + variant.board.cg, {
                                        hook: { insert: vnode => (bugboardVNode = vnode) },
                                    }),
                                ],
                            ),
                            seatViews.b[1].view(pocketB1),
                        ],
                    },
                ],
            },
            // one part each for now: splitting a tab across places is what the
            // widget newly allows, and which tabs should be split is a separate
            // change — chat's two pieces are produced together inside the shared
            // chatView(), so dividing them is a change about chat, not about tabs
            // Two parts: the chat view, and the presets beside it. They are
            // mounted adjacent for now, so nothing moves on screen — but either
            // can be placed on its own, which is why the presets were pulled out
            // of the chat view in the first place.
            {
                label: _('Chat'),
                parts: [
                    { content: [h('div#bugroundchat')] },
                    // One part per preset group, so each can be placed on its own
                    // and they flow into the space under the board one at a time.
                    ...(chatPresetsView
                        ? chatPresetsView.parts().map((part, i) => ({
                              panelClass: `chatpresets-panel.chatpresets-panel-${i + 1}`,
                              content: [part],
                          }))
                        : []),
                ],
            },
            {
                label: _('Moves'),
                /* THE RECORD AND THE BUTTONS, two parts, as the analysis page's Moves tab already
                   is — and for the same reason. A part is what the cascade can move; nested inside
                   one panel the buttons were unreachable, so a band with room for them went unused
                   however wide it was. The order is the drop queue's: the list never leaves, being
                   useless in a band a few squares tall, so it holds the slot that never drops.
                   The buttons take the second preset panel's slot. The two never coexist — the
                   presets belong to the Chat tab and these to the Moves tab — which is the same
                   sharing the end-of-game controls already have with the first preset panel. */
                parts: [
                    {
                        panelClass: 'round-moves-panel',
                        content: [h('div.movelist-block', [movelistView.placeholder()])],
                    },
                    { panelClass: 'round-controls-panel', content: [h('div#move-controls')] },
                ],
            },
            {
                label: _('Info'),
                /* THE SPECTATOR LIST LIVES HERE, not in a row of the page's grid. As
                   `under-left#spectators` it was a child of `main.round.bug` claiming a `uleft`
                   area, which every template then had to name: a row of its own in tall landscape
                   and in portrait, a `display: none` in the two modes that could not afford it,
                   and — on the analysis page, where the same element sat inside the app — implicit
                   tracks whose gaps took 30px off the tools. An element nobody has ever seen cost
                   four rules and a guarantee.
                   Inside a tab panel it is laid out by the panel and named by no template at all.
                   The tag is its own name now rather than a position in a grid that no longer has
                   a place for it, and `SpectatorsView` owns the node: the socket's `spectators`
                   message reaches it through the controller.

                   THE PANEL IS NAMED so it can be a COLUMN. Its two parts are the game info and
                   the list of watchers, one under the other — a panel is `display: flex` by
                   default here, which put them side by side and left the game info competing for
                   width with a list that is usually empty. */
                parts: [
                    {
                        panelClass: 'info-panel',
                        content: [gameInfoView.placeholder(), spectatorsView.placeholder()],
                    },
                ],
            },
        ],
        _('Round tabs'),
    );
    // The strip may claim it; until then it is simply the board, drawn where it always was.
    registerStandingTab(roundTabs, PARTNER_BOARD_TAB);
    // AFTER the strip is built, because the strip is built from the widget's own placeholder.
    // `INFO_TAB` is that tab's index in the list above; the label is the one it was declared with.
    spectatorsView.countIn(roundTabs, INFO_TAB, _('Info'));

    return [
        h(
            'div.round-app.bug',
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
                            spectatorsView,
                            seatViews,
                            chatPresetsView,
                        );
                    },
                },
            },
            [
                // The viewer's own board and its two strips as one unit, exactly as the
                // partner's are grouped in `.partner-and-tools`. They used to be three
                // separate items of the app's grid, stacked by three named rows —
                // which is a grid doing, for one board, what a container already does
                // for the other. The asymmetry cost more than the rows: anything a
                // stack needs, from the room a board's coordinates want to the height
                // a name takes when it leaves its strip, had to be expressed twice,
                // once as tracks here and once inside the group there. Now both boards
                // are the same kind of thing and each carries its own arrangement.
                //
                // Order is the arrangement: strip, board, strip, in block flow.
                h('div.bug-own-stack', [
                    seatViews.a[0].view(pocketA0),
                    h(`selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`, [
                        h('div.cg-wrap.' + variant.board.cg, {
                            hook: { insert: vnode => (mainboardVNode = vnode) /*runGround(vnode, model)*/ },
                        }),
                    ]),
                    seatViews.a[1].view(pocketA1),
                ]),
                // The draw/rematch prompt used to be here, as `.bug-offer-dialog`
                // holding `#offer-dialog` in its own full-width `toolsB` row below
                // both boards. An offer is now a look on the control that made it —
                // the draw button turns green to be accepted, the rematch button is
                // replaced in place by an accept/decline pair — so there is nothing
                // left for a strip to hold, and the row went with the element.
                // The tools column is this page's own element, carrying its
                // `grid-area: tools` and the `min-width: 0` that makes the column
                // yield before a board is pushed off screen; the widget supplies
                // only the two parts inside it. Panels first, so the tablist reads
                // as a bottom tab bar. Mounting them apart is possible and is the
                // point of the widget's shape, but this layout wants them together.
                //
                // The bar shares that bottom row between the tablist and the game
                // controls. #game-controls is only a placeholder here — roundControls
                // finds it by id after this patch and renders the draw and resign
                // buttons into it — so this moves where they sit and nothing else.
                // They are in this column because the row below the boards cannot be
                // reached in short landscape: they measured at y=546.67 in a 551px
                // viewport that does not scroll, leaving no way to resign a game.
                // Each tab's panels are mounted individually now that the widget
                // groups nothing. All of them land here for the moment, so the
                // column looks exactly as it did; a later change is free to mount
                // one of them somewhere else entirely.
                // THE PARTNER'S STACK AND THE TOOLS, as siblings of the viewer's stack rather
                // than inside a wrapper of their own. `div.partner-and-tools` held them until the
                // day every mode dissolved it: it was `display: contents` in landscape from the
                // start, portrait stopped being the exception, and an element with no box in any
                // mode is a level of nesting that nothing reads.
                //
                // What it used to buy, and where that went: a grid track is sized by its widest
                // item and never by two items side by side, so "the right board plus the tools"
                // once had to be ONE item to size a column. The flattened templates size that
                // column from the stack's own track instead, which is why the wrapper could go.
                // The board and its two strips are grouped; the tab parts are
                // not. That is the whole arrangement in one line.
                //
                // These three are one unit — they move together on a switch and
                // size together — and three siblings cannot be floated as one
                // thing, so the group has to exist for the board to be the
                // fixed shape the parts arrange themselves around.
                // The stack IS the panel — `panelClass` put `.bug-partner-stack` on the
                // wrapper rather than inside it, so nothing gained a level and the grid area
                // it has always occupied is still declared on the same element.
                roundTabs.panel(PARTNER_BOARD_TAB, 0),
                // The parts. Grouped only so that portrait has something to
                // place: there the tools are one block in their own grid area,
                // and free-standing parts auto-placed into the partner board's
                // rows, which left the chat 20.7px tall.
                //
                // The landscape modes make this element `display: contents`, so
                // it forms no box and each part is placed individually by the
                // column — which is what lets one of them take the space under a
                // shrunken board. Each mode dissolves whichever container it
                // does not want: landscape this one, portrait the two around it.
                h('div.bug-parts', [
                    roundTabs.panel(1, 0),
                    // The two preset rows, grouped. `display: contents` everywhere except
                    // zone B, so normally they are placed individually exactly as before
                    // and this element is not in the layout at all.
                    //
                    // It exists for the one arrangement that needs both of them to be ONE
                    // item: a named grid area is a single rectangle and holds a single
                    // item, so twenty buttons can only share a row under both boards if
                    // the twenty are inside one box. In zone B the group becomes that box.
                    ...(chatPresetsView
                        ? [h('div.bug-presets-group', [roundTabs.panel(1, 1), roundTabs.panel(1, 2)])]
                        : []),
                    roundTabs.panel(2, 0),
                    // The Moves tab's SECOND part, and it has to be mounted by hand because this
                    // page mounts panels by index where the analysis page maps over `parts`.
                    // Declaring a part the view never mounts is silent: the element simply is not
                    // there, and `#move-controls` -- which `movelist.ts` finds by id -- went with it.
                    roundTabs.panel(2, 1),
                    roundTabs.panel(3, 0),
                    // Where the end-of-game controls are rendered, empty until
                    // there is a result. It belongs to no tab — it must show
                    // whichever tab is selected — so it is a sibling of the
                    // parts rather than one of them, and it takes the place the
                    // presets vacate at the same moment.
                    h('div.bug-gameover'),
                    h('div.bug-round-tools-bar', [roundTabs.tabList(), h('div#game-controls')]),
                ]),
                // h('div.material.material-bottom.' + variant.pieceFamily + '.disabled'),
            ],
        ),
        // NO `under-board`. It was carried over from the one-board round view and nothing on this
        // page has ever filled it: `.ctable-container` and `#janggi-setup-buttons` are populated by
        // `client/roundCtrl.ts`, the ONE-board controller, and this page runs
        // `RoundControllerBughouse extends TwoBoardController`, which never touches either. The
        // two-board ANALYSIS page emits no `under-board` and wants for nothing, which is the same
        // point made twice.
        //
        // Two empty divs are not free. The `main.round.bug` shell gave them a 34px row plus two
        // 11px gaps below the app, so in short landscape the document came out 603px against a
        // 551px viewport — 52px hanging off the bottom, unseen only because `body`'s
        // `overflow-y: hidden` propagates to the viewport. Portrait and tall landscape each
        // carried a `display: none` to buy that space back; with the element gone, all three
        // modes are the same and those rules are deleted.
        //
        // NO `aside.sidebar-first` EITHER, and no shell to hold one. The one-board page fills that
        // aside with the game info and the chat; this page moved both into tabs and kept the empty
        // box, which was the only reason `main.round.bug` needed a grid at all — two children to
        // place instead of one. It also announced an empty `complementary` landmark to anyone
        // navigating by landmark, which is worse than free. The app is the wrapper's only child
        // now, on both pages, and the wrapper is the `<main>`.
        //
        // A crosstable here would be worth having — the stylesheet's comments call its absence a
        // cost. But it was never a cost this markup was paying: nothing was ever drawn in it, so
        // building one is a feature, not the restoration of something these lines provided.
        BoardSummaryView.placeholder('a', 'assertive'),
        BoardSummaryView.placeholder('b', 'assertive'),
    ];
}
