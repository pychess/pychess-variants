import { h, VNode } from 'snabbdom';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { _ } from '@/i18n';
import { patch } from '@/document';
import { ranksUCI } from '@/chess';
import { Variant } from '@/variants';
import { BoardName } from '@/types';
import { pieceName } from '@/pieceNames';

// How urgently a page's live regions speak: a round interrupts, analysis waits for a pause.
export type Politeness = 'assertive' | 'polite';

const COLORS: cg.Color[] = ['white', 'black'];

function elementId(boardName: BoardName): string {
    return boardName === '' ? 'board-summary' : `board-summary-${boardName}`;
}

// The variant's own square names, so the Pieces lines agree with the move list.
function squareName(key: cg.Key, notation: cg.Notation, bd: cg.BoardDimensions): string {
    const [file, rank] = util.key2pos(key);
    switch (notation) {
        case cg.Notation.SHOGI_ARBNUM: // files from the right, ranks from the top: "76"
            return `${bd.width - file}${bd.height - rank}`;
        case cg.Notation.JANGGI: // rank from the top (10th is 0), then file: "83"
            return `${(bd.height - rank) % 10}${file + 1}`;
        default:
            return cg.files[file] + ranksUCI[rank];
    }
}

function bySquare(a: cg.Key, b: cg.Key): number {
    const [fa, ra] = util.key2pos(a);
    const [fb, rb] = util.key2pos(b);
    return fa - fb || ra - rb;
}

/** The position, last move and game status as text for screen readers, visually hidden. */
export class BoardSummaryView {
    private vnode: VNode | HTMLElement | undefined;
    private live: Politeness = 'polite';
    private boardState: cg.BoardState | undefined;
    private lastMove: string | undefined;
    private status: string | undefined;

    constructor(
        private readonly variant: Variant,
        private readonly boardName: BoardName,
    ) {}

    /** The page decides where the summary goes and how urgently it speaks. */
    static placeholder(boardName: BoardName, live: Politeness): VNode {
        return h(`div#${elementId(boardName)}.sr-only`, { attrs: { 'data-live': live } });
    }

    setPosition(boardState: cg.BoardState, lastMove: string | undefined): void {
        this.boardState = boardState;
        this.lastMove = lastMove;
        this.redraw();
    }

    setStatus(status: string): void {
        this.status = status;
        this.redraw();
    }

    private redraw(): void {
        if (this.vnode === undefined) {
            const el = document.getElementById(elementId(this.boardName));
            if (el === null) return; // this page has no summary
            this.live = el.dataset.live === 'assertive' ? 'assertive' : 'polite';
            this.vnode = el;
        }
        this.vnode = patch(this.vnode, this.render());
    }

    private squareName(key: cg.Key): string {
        return squareName(key, this.variant.notation, this.variant.board.dimensions);
    }

    private colorName(color: cg.Color): string {
        return _(color === 'white' ? this.variant.colors.first : this.variant.colors.second);
    }

    // Roles in the variant's own piece order, anything else (promoted pieces) after it.
    private orderedRoles(color: cg.Color, roles: Iterable<cg.Role>): cg.Role[] {
        const order = this.variant.pieceRow[color];
        const rank = (role: cg.Role) => {
            const i = order.indexOf(role);
            return i === -1 ? order.length : i;
        };
        return [...new Set(roles)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    }

    private piecesByColor(color: cg.Color): VNode[] {
        const squares = new Map<cg.Role, cg.Key[]>();
        for (const [key, piece] of this.boardState?.pieces ?? []) {
            if (piece.color !== color) continue;
            squares.set(piece.role, [...(squares.get(piece.role) ?? []), key]);
        }
        return this.orderedRoles(color, squares.keys()).map(role =>
            h(
                'p',
                `${pieceName(this.variant, role, color)}: ${squares
                    .get(role)!
                    .sort(bySquare)
                    .map(key => this.squareName(key))
                    .join(', ')}`,
            ),
        );
    }

    private pocketByColor(color: cg.Color): VNode[] {
        const pocket = this.boardState?.pockets?.[color];
        if (pocket === undefined) return [];
        const roles = [...pocket.keys()].filter(role => (pocket.get(role) ?? 0) > 0);
        return this.orderedRoles(color, roles).map(role =>
            h('p', `${pieceName(this.variant, role, color)}: ${pocket.get(role)}`),
        );
    }

    private render(): VNode {
        // A two-board page heads each board's summary, so the sections sit one level lower.
        const titled = this.boardName !== '';
        const section = titled ? 'h3' : 'h2';
        const side = titled ? 'h4' : 'h3';
        const region = { 'aria-live': this.live, 'aria-atomic': 'true' };

        const byColor = (title: string, rows: (color: cg.Color) => VNode[]) => [
            h(section, title),
            // "Pieces: White", not just "White": headings are also heard out of order, in a list.
            ...COLORS.map(color => h('div', [h(side, `${title}: ${this.colorName(color)}`), ...rows(color)])),
        ];

        return h(`div#${elementId(this.boardName)}.sr-only`, { attrs: { 'data-live': this.live } }, [
            ...(titled ? [h('h2', `${_('Board')} ${this.boardName.toUpperCase()}`)] : []),
            ...byColor(_('Pieces'), color => this.piecesByColor(color)),
            ...(this.variant.pocket ? byColor(_('Pockets'), color => this.pocketByColor(color)) : []),
            h(section, _('Last move')),
            h('p', { attrs: region }, this.lastMove ?? _('Initial position')),
            ...(this.status === undefined
                ? []
                : [h(section, _('Status')), h('p', { attrs: { role: 'status', ...region } }, this.status)]),
        ]);
    }
}
