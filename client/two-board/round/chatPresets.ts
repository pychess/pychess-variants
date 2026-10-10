import { h, VNode } from 'snabbdom';
import * as cg from 'chessgroundx/types';

import { _, N_ } from '@/i18n';
import { pieceName } from '@/pieceNames';
import { Variant } from '../../variants';

// The bughouse chat presets: the grid of "need a knight", "don't trade", "my bad"
// buttons a player uses to tell their partner something without typing it.
//
// This used to be rendered from inside `client/chat.ts`, the chat view shared by
// every page, which imported this module and branched on whether the controller
// was a bughouse round controller. A shared view reaching into one page's module
// to decide what to draw. Nothing about these buttons belongs to chat except that
// clicking one sends a message.
//
// A widget in the house shape — one composed view, built once — so the page can
// put it wherever a layout wants it, rather than wherever the chat view's own
// flex box happens to put it.
//
// TWO-STEP INITIALISATION, and it is a real ordering constraint rather than an
// awkwardness to design around. Everything these buttons LOOK like comes from the
// variant: the pocket roles decide which pieces get a "need" and a "don't give"
// pair, and the tells are fixed. So they are built in the constructor. But
// clicking one has to send, and only the round controller can send — and the
// controller is constructed in the round app's `insert` hook, which runs after
// the view it is being inserted into has been built. The widget therefore cannot
// have a sender when it renders, and is given one afterwards by `wire()`.
//
// Between the page's patch and that call, a click does nothing at all. That gap
// is a few milliseconds inside the same task in which the page becomes visible,
// so queueing a click for later delivery would be machinery for a case that
// cannot occur — but discarding is a decision, not an oversight.
// The presets that are not about a piece, in the order their buttons appear.
const TELLS: Readonly<Record<string, string>> = {
    sit: N_('Sit/stall'),
    go: N_('Go/hurry'),
    trade: N_('Trades are good'),
    notrade: N_("Don't trade"),
    mate: N_('I have checkmate'),
    ok: N_('OK'),
    no: N_('No'),
    mb: N_('My bad'),
    nvm: N_('Nevermind'),
    nice: N_('Nice'),
};

/** What a preset says, by the name it is sent as: "Need queen" for `q`, "Don't give knight" for `non`. */
export function presetLabel(variant: Variant, name: string): string | undefined {
    if (name in TELLS) return _(TELLS[name]);
    for (const role of variant.pocket?.roles.white ?? []) {
        const letter = role.charAt(0);
        if (name === letter) return _('Need %1', pieceName(variant, role, 'white'));
        if (name === 'no' + letter) return _("Don't give %1", pieceName(variant, role, 'white'));
    }
    return undefined;
}

export class ChatPresetsView {
    // TWO PARTS, each holding TWO SETS of five buttons.
    //
    // The four sets are the four rows the single grid always drew: what to ask
    // for, what not to give, and the tells in two halves. Splitting them lets the
    // layout place each part where there is room for it, one at a time, instead of
    // moving all twenty buttons or none.
    //
    // The two sets inside a part are laid out so they sit side by side when the
    // part is wide enough for both and stack when it is not — so a part that has
    // dropped into the width under the board shows its ten buttons on one row,
    // and the same part beside the board shows them as two rows of five, which is
    // what they have always looked like. Nothing forces the fit: the wrap decides,
    // so there is no width that has to be computed and kept true.
    //
    // A set is never broken up. Five buttons on one row is the unit, because the
    // ask/don't-give pair is piece-aligned — column i is piece i, so "need a
    // knight" sits above "don't give a knight" whenever the two sets are stacked.
    private readonly vnodes: VNode[];

    // set by wire(); until then a click is discarded
    private send: ((message: string) => void) | undefined;

    constructor(variant: Variant) {
        const roles: cg.Role[] = [...variant.pocket!.roles.white];

        const button = (name: string) => this.button(name, presetLabel(variant, name)!);
        const need = roles.map(role => button(role.charAt(0)));
        const dontGive = roles.map(role => button('no' + role.charAt(0)));
        const tells = Object.keys(TELLS).map(button);

        // The tells split in half rather than by meaning: the two halves are the
        // two rows they already occupied, so nothing moves relative to today.
        const half = Math.ceil(tells.length / 2);

        this.vnodes = [
            this.part(roles.length, [need, dontGive]),
            this.part(half, [tells.slice(0, half), tells.slice(half)]),
        ];
    }

    // One part: two sets that wrap against each other. --setColumns drives each
    // set's column count in the stylesheet, and is the role count for the piece
    // sets so that they stay piece-aligned.
    private part(setColumns: number, sets: VNode[][]): VNode {
        return h(
            'div.chatpresets',
            { style: { '--setColumns': String(setColumns) } },
            sets.map(set => h('div.chatpresets-set', set)),
        );
    }

    // The message a preset sends is its own name with the `!bug!` marker, which is
    // how the receiving side recognises a preset rather than typed text.
    private button(name: string, title: string): VNode {
        return h(
            `button.bugchat.${name}`,
            { on: { click: () => this.send?.(`!bug!${name}`) }, props: { title } },
            [],
        );
    }

    // The parts, in the order they are meant to be mounted. The caller decides
    // where each one goes; this only says which are which.
    parts(): VNode[] {
        return this.vnodes;
    }

    // Step two. The function handed in MUST be the one chat itself uses, so that a
    // preset is reported and delivered exactly as typing the same text would be —
    // assembling the message envelope here would be a second definition of what a
    // chat message is, and `selfReport` is easy to forget.
    wire(send: (message: string) => void): void {
        this.send = send;
    }
}
