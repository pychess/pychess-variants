import { h, VNode } from 'snabbdom';

import { _ } from '../../i18n';
import { patch } from '../../document';
import { ariaHiddenAttr } from '../../accessibility/aria';
import { ChatController, chatView } from '../../chat';
import { swap } from '../twoBoardCtrl';
import { RoundSeatViews } from './roundSeatView';
import { isOutsidePartnerStack, markBoardRoles } from '../common/boardRoles';

// What an offer control is currently showing. Named for what the VIEWER may do rather
// than for who sent what: `offering` means my side asked and is waiting, `offered` means
// the answer is mine to give.
//
// In bughouse "my side" is a TEAM, not a player. Both members of the team that offered a
// draw show `offering` — the one who pressed the button is just the one who pressed it —
// and both opponents show `offered`. For a resignation the team is split: the player who
// asked shows `offering`, their partner shows `offered` and is the one who may confirm.
//
// This is the whole state machine for offers. It lives here, in the thing that draws
// them, because an offer has no place of its own on the page — it IS a look its own
// control wears, so there is nothing to hold state for beyond what these three fields
// decide to paint.
export type OfferState = 'rest' | 'offering' | 'offered';

// Owns the round page's game-controls (#game-controls) and end-of-game
// (.bug-gameover) retained vnodes, plus the other ad-hoc DOM rendering
// `roundCtrl.ts` previously did inline. RoundControllerBughouse holds one instance
// instead of raw VNode fields, and calls its methods instead of
// document.*/patch()/h() directly.
//
// There is no `vdialog` any more. #offer-dialog was a strip spanning the whole app
// below both boards, holding a draw prompt, a rematch prompt or one of two "offer
// sent" messages — an answer drawn nowhere near the control that asked the
// question. Every one of those states is now a look on the control itself, which
// left the element with nothing to hold, so it and its `toolsB` grid area are gone.
export class RoundControlsView {
    private gameControls: VNode | HTMLElement;
    // The end-of-game controls have their own element among the parts. They used to
    // be patched over `gameControls`, which is the strip beside the tab list sized
    // for two icon buttons — three wide text buttons never belonged there.
    private gameOverControls: VNode | HTMLElement;

    private drawOffer: OfferState = 'rest';
    private rematchOffer: OfferState = 'rest';
    private resignOffer: OfferState = 'rest';

    // Both control groups are now repainted whenever an offer changes, so what they
    // need in order to be drawn has to outlive the call that first drew them. Held
    // as the arguments they arrived as, rather than as loose fields, so a repaint
    // cannot draw a button wired to a handler from a different game state.
    private gameControlsSpec?: {
        spectator: boolean;
        onDraw: () => void;
        onResign: () => void;
        onAcceptDraw: () => void;
    };
    private gameOverSpec?: {
        spectator: boolean;
        onRematch: () => void;
        onAcceptRematch: () => void;
        onCancelRematch: () => void;
        onNewOpponent: () => void;
        onAnalysis: () => void;
    };
    // The VIEW REMATCH link, as state rather than as a raw insertBefore. It used to
    // be spliced into `.bug-gameover` outside snabbdom's knowledge, which was safe
    // only while that element was never patched again — and it is now patched every
    // time an offer changes.
    private onViewRematch?: () => void;

    constructor() {
        this.gameControls = document.getElementById('game-controls') as HTMLElement;
        this.gameOverControls = document.querySelector('.bug-gameover') as HTMLElement;
    }

    setDrawOffer(state: OfferState): void {
        this.drawOffer = state;
        this.paintGameControls();
    }

    setResignOffer(state: OfferState): void {
        this.resignOffer = state;
        this.paintGameControls();
    }

    setRematchOffer(state: OfferState): void {
        this.rematchOffer = state;
        this.paintGameOverControls();
    }

    setViewRematch(onViewRematch: () => void): void {
        this.onViewRematch = onViewRematch;
        this.paintGameOverControls();
    }

    renderInitialGameControls(
        spectator: boolean,
        onDraw: () => void,
        onResign: () => void,
        onAcceptDraw: () => void,
    ): void {
        this.gameControlsSpec = { spectator, onDraw, onResign, onAcceptDraw };
        this.gameControls = document.getElementById('game-controls') as HTMLElement;
        this.paintGameControls();
    }

    /* The draw button in whichever of its three looks the offer state calls for. Size,
       position and glyph are identical in all three, deliberately: `.bug-round-tools-bar
       .btn-controls button` sizes these at two thirds of a board square BECAUSE they are
       reached for under time pressure, and a state that moved or resized the target would
       undo the one thing that rule exists to guarantee. Only colour and what a press does
       change, so it reads as one button that has changed its mind rather than as a
       different button appearing.

       `disabled` for the offering state rather than a class of our own: site.css already
       dims a disabled button's icon and withholds the hover colour, so the pending look is
       the site's own idiom and costs no new declarations.

       An empty `div` where #count used to be. That button was rendered and then patched
       away one line later — `patch(document.getElementById('count'), h('div'))` — so an
       empty div is exactly what it already became. Written directly because this element is
       now repainted whenever an offer changes, and a render-then-destroy pair only works
       once. Nothing is lost: no code on this page ever sent a `count` message. */
    private paintGameControls(): void {
        const spec = this.gameControlsSpec;
        if (!spec) return;
        if (spec.spectator) {
            this.gameControls = patch(this.gameControls, h('div.btn-controls'));
            return;
        }
        const drawOffered = this.drawOffer === 'offered';
        const drawWaiting = this.drawOffer === 'offering';
        // The partner of a player who asked to resign. Their press ENDS THE GAME, where at
        // rest the same press would only have asked — which is why the lit state cannot be
        // carried by colour alone. See `#resign.resign-confirm` in bughouse.css.
        const resignConfirm = this.resignOffer === 'offered';
        const resignWaiting = this.resignOffer === 'offering';
        const buttons = [
            h('div'),
            h(
                'button#draw',
                {
                    class: { 'draw-offered': drawOffered },
                    attrs: drawWaiting ? { disabled: true } : {},
                    on: { click: drawOffered ? spec.onAcceptDraw : spec.onDraw },
                    props: { title: drawOffered ? _('Accept draw') : _('Offer draw') },
                },
                // The label is always in the DOM and hidden by width, never by `display: none`
                // — toolsPlacement.ts measures what it WOULD take before deciding whether both
                // fit, and a `display: none` element measures zero, so the question could never
                // be asked. It says `Draw`, not what the title says: the title changes with the
                // offer state and this must not, or the button would resize under a player
                // reaching for it, which is the one thing its fixed size exists to prevent.
                [h('i', ariaHiddenAttr(), '½'), h('span.control-label', _('Draw'))],
            ),
            h(
                'button#resign',
                {
                    class: { 'resign-confirm': resignConfirm },
                    attrs: resignWaiting ? { disabled: true } : {},
                    on: { click: spec.onResign },
                    props: { title: resignConfirm ? _('Confirm resignation') : _('Resign') },
                },
                [
                    h('i', { class: { icon: true, 'icon-flag-o': true }, ...ariaHiddenAttr() }),
                    h('span.control-label', _('Resign')),
                ],
            ),
        ];
        this.gameControls = patch(this.gameControls, h('div.btn-controls', buttons));
    }

    renderGameOverControls(
        spectator: boolean,
        onRematch: () => void,
        onAcceptRematch: () => void,
        onCancelRematch: () => void,
        onNewOpponent: () => void,
        onAnalysis: () => void,
    ): void {
        // Draw and Resign go, because they no longer apply. Their strip stays: it
        // shares a row with the tab list, and emptying the element rather than
        // removing it is what keeps that row where it is.
        this.gameControlsSpec = undefined;
        this.drawOffer = 'rest';
        this.resignOffer = 'rest';
        this.gameControls = patch(this.gameControls, h('div#game-controls'));

        this.gameOverSpec = { spectator, onRematch, onAcceptRematch, onCancelRematch, onNewOpponent, onAnalysis };
        this.paintGameOverControls();
    }

    /* The rematch control is one button wearing three labels — REMATCH, CANCEL REMATCH
       while my own offer stands, ACCEPT REMATCH in green when someone else's does. Its
       place in the column never changes, so NEW OPPONENT and ANALYSIS BOARD never move.

       Unlike the draw and resign controls this one is a WIDE TEXT button, so it can say
       which of the three it is rather than relying on colour. The green on ACCEPT is
       there to match the draw control's meaning of green — this press ends something —
       not because the label needs help.

       `.newopp.viewrematch` rather than the bare `.newopp` this used to be spliced in
       as. Two siblings with the same selector are told apart by position alone under
       snabbdom's keyless diff, and this element is now repainted rather than inserted
       once, so the two would swap their text the first time an offer changed. */
    private paintGameOverControls(): void {
        const spec = this.gameOverSpec;
        if (!spec) return;

        const buttons: VNode[] = [];
        if (this.onViewRematch) {
            buttons.push(h('button.newopp.viewrematch', { on: { click: this.onViewRematch } }, _('VIEW REMATCH')));
        }
        if (!spec.spectator) {
            // ONE control, three labels. There is no DECLINE: declining a rematch is
            // simply not accepting it, and a button whose only job is to do nothing is
            // a button that has to be explained. What was missing instead was a way for
            // the OFFERER to take their offer back, which is what the middle state now
            // does — so the state that used to be inert is the one that acts.
            const offered = this.rematchOffer === 'offered';
            const offering = this.rematchOffer === 'offering';
            buttons.push(
                h(
                    'button.rematch',
                    {
                        class: { accept: offered, cancel: offering },
                        on: { click: offered ? spec.onAcceptRematch : offering ? spec.onCancelRematch : spec.onRematch },
                    },
                    offered ? _('ACCEPT REMATCH') : offering ? _('CANCEL REMATCH') : _('REMATCH'),
                ),
            );
            buttons.push(h('button.newopp', { on: { click: spec.onNewOpponent } }, _('NEW OPPONENT')));
        }
        buttons.push(h('button.analysis', { on: { click: spec.onAnalysis } }, _('ANALYSIS BOARD')));
        // `.bug-gameover` only. It used to also wear `btn-controls after`, which are
        // site.css's classes: they brought the button styling, but with it
        // `grid-area: game-controls` and `flex-flow: column nowrap` at a specificity
        // this page then had to fight. Owning the six declarations is cheaper than
        // owning that argument.
        this.gameOverControls = patch(this.gameOverControls, h('div.bug-gameover', buttons));
    }
}

// Marks the page as having a finished game, for the rules that depend on it — the
// presets are hidden, and the end-of-game controls take the place they leave.
//
// A class rather than each rule asking the controller, because what changes is
// presentational and belongs in the stylesheet; and on `.round-app.bug` rather than
// on the body because that is the element the layout rules are already keyed to.
//
// Covers a page opened on an already-finished game as well as a result arriving
// mid-game: the controller reaches its game-over handler in both cases.
export function markGameOver(): void {
    document.querySelector('.round-app.bug')?.classList.add('game-over');
}

export function renderRoundChat(ctrl: ChatController): void {
    patch(document.getElementById('bugroundchat') as HTMLElement, chatView(ctrl, 'bugroundchat', { chatHeader: false }));
}

export function resetMovelistDom(): void {
    const container = document.getElementById('movelist') as HTMLElement;
    patch(container, h('div#movelist'));
}

// clears the gating/promotion widget left over the ground when the game ends by timeout
export function clearExtensionChoice(): void {
    const container = document.getElementById('extension_choice') as HTMLElement;
    if (container instanceof Element) patch(container, h('extension'));
}

export function clearAbortIndicator(): void {
    const container = document.getElementById('abort') as HTMLElement;
    if (container) patch(container, h('div'));
}

// `insertRematchButton` is gone. It spliced a VIEW REMATCH button into
// `.bug-gameover` with insertBefore, outside snabbdom's knowledge — safe only while
// that element was never patched again, which stopped being true the moment an
// offer became something drawn there. It is `RoundControlsView.setViewRematch()`
// now, which records the link and repaints, so the button survives every later
// paint instead of being silently discarded by the next one.

// Seat rearrangement for flipBoards()/switchBoards(). Both work on seat strips —
// the element holding one seat's pocket, clock and name — but on different parts
// of them, because the two operations are not the same kind of move.
//
// FLIP exchanges the two seats of a board between its strips, and must leave the
// pockets where they are: chessgroundx's toggleOrientation() calls redrawAll(),
// which re-renders each pocket for the new orientation in place, so the top
// pocket element always holds the top player's pocket. Moving the elements as
// well would apply the exchange twice and show each player the wrong pocket.
export function swapSeatBlocksForFlip(views: RoundSeatViews): void {
    swap(views.a[0].blockElement(), views.a[1].blockElement());
    swap(views.b[0].blockElement(), views.b[1].blockElement());
}

// SWITCH exchanges board A's strips with board B's, pocket and seat together, by
// moving them between the two columns. This is what used to be a grid-area swap
// on the seat blocks plus a DOM swap of the pocket elements; one strip carries both.
export function swapSeatStripsForSwitch(views: RoundSeatViews): void {
    swap(views.a[0].stripElement(), views.b[0].stripElement());
    swap(views.a[1].stripElement(), views.b[1].stripElement());
}

// The boards themselves, the same way.
//
// NOT twoBoardCtrl's switchBoardElements(), which swaps the two boards' inline
// grid-area. That works only while both boards are children of one grid, which is
// still true on the analysis page and is why that function stays as it is. On this
// page the right column is `.partner-and-tools`, so the two boards are in different
// containers and an inline area naming the other column's track resolves against a
// grid that does not define it — the board is then auto-placed. Position is the
// whole of the state now, and the stylesheet reads it with `>` selectors.
export function swapBoardsForSwitch(): void {
    const mainboard = document.getElementById('mainboard');
    const bugboard = document.getElementById('bugboard');
    if (mainboard && bugboard) swap(mainboard, bugboard);
}

// Which board and which strips are the viewer's own, and which the partner's, as
// classes CSS can select on. Nothing else carries this: `.bug` is board IDENTITY —
// roundSeatView sets it from `board === 'b'` — so it is the partner's for a board-A
// player and the viewer's own for a board-B player.
//
// Read from WHICH COLUMN the element is in. That is the same thing the stylesheet
// keys its grid areas off, so there is exactly one source of truth and a switch
// cannot leave the two disagreeing. It replaces reading the effective grid area,
// which stopped being meaningful once the two columns became two containers: an
// inline area is no longer written by anything, and a class-based one names a track
// that only its own container defines.
//
// The viewer's own side is the left column, which is the round app itself; the
// partner's is the wrapper. Call it after the initial placement and again after
// every swap.
//
// Both boards and strips need it: a mode that draws the partner smaller has to size
// each element from the role's scale, and keying that off `#mainboard`/`#bugboard`
// would give a board-A player the partner's size on their own board.
export function markRoles(views: RoundSeatViews): void {
    // The seat strips are this page's alone — the analysis page has no strips, only
    // absolutely positioned clock overlays on the board — so this half stays here.
    for (const board of ['a', 'b'] as const) {
        for (const position of [0, 1] as const) {
            const el = views[board][position].stripElement();
            const own = isOutsidePartnerStack(el);
            el.classList.toggle('own-seat', own);
            el.classList.toggle('partner-seat', !own);
        }
    }
    // The board half is shared with the analysis page — see common/boardRoles.ts.
    markBoardRoles(isOutsidePartnerStack);
}
