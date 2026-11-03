import { h, VNode } from 'snabbdom';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { writeBoard } from 'chessgroundx/fen';

import { _, ngettext } from '@/i18n';
import { patch } from '@/document';
import { ranksUCI } from '@/chess';
import { pieceName, Variant } from '@/variants';
import { BoardName } from '@/types';
import { Clock } from '@/clock';

/** A clock reading in words, at the precision the clock shows: "29 minutes 36 seconds". */
export function spokenTime(millis: number): string {
    const total = Math.max(0, Math.floor(millis / 1000));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    const parts: string[] = [];
    if (days > 0) parts.push(ngettext('%1 day', '%1 days', days));
    if (hours > 0) parts.push(ngettext('%1 hour', '%1 hours', hours));
    if (days === 0 && minutes > 0) parts.push(ngettext('%1 minute', '%1 minutes', minutes));
    if (days === 0 && hours === 0 && (seconds > 0 || parts.length === 0))
        parts.push(ngettext('%1 second', '%1 seconds', seconds));
    return parts.join(' ');
}

// How urgently a page's live regions speak: a round interrupts, analysis waits for a pause.
export type Politeness = 'assertive' | 'polite';

const COLORS: cg.Color[] = ['white', 'black'];

// level: its top heading's, under the page's own (the forum captcha sits lower than a game page).
// lastMove: false where a position has no history (the forum captcha).
interface SummaryOptions {
    level?: number;
    lastMove?: boolean;
}

// A live region speaks only when its text changes, so the same words again (Nxd5 answered by Nxd5)
// get a trailing no-break space, added and dropped in turn.
function respoken(shown: string, text: string): string {
    return shown === text ? `${text}\u00a0` : text;
}

function elementId(boardName: BoardName): string {
    return boardName === '' ? 'board-summary' : `board-summary-${boardName}`;
}

// The variant's own square names, so the Pieces lines agree with the move list.
export function squareName(key: cg.Key, notation: cg.Notation, bd: cg.BoardDimensions): string {
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

export function colorName(variant: Variant, color: cg.Color): string {
    return _(color === 'white' ? variant.colors.first : variant.colors.second);
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
    private lastMoveShown = '';
    private pieces = '';
    private status: string | undefined;
    private clocks: Partial<Record<cg.Color, string>> = {};

    constructor(
        private readonly variant: Variant,
        private readonly boardName: BoardName,
        private readonly options: SummaryOptions = {},
    ) {}

    /** The page decides where the summary goes and how urgently it speaks. */
    static placeholder(boardName: BoardName, live: Politeness): VNode {
        return h(`div#${elementId(boardName)}.sr-only`, { attrs: { 'data-live': live } });
    }

    setPosition(boardState: cg.BoardState, lastMove: string | undefined): void {
        // A new move changes the pieces; a redraw, a flip or a bughouse pocket change does not.
        const pieces = writeBoard(boardState.pieces, this.variant.board.dimensions);
        const moved = pieces !== this.pieces;
        this.boardState = boardState;
        this.pieces = pieces;
        this.lastMove = lastMove;
        const text = this.lastMoveText();
        if (moved || this.lastMoveShown.trimEnd() !== text) this.lastMoveShown = respoken(this.lastMoveShown, text);
        this.redraw();
    }

    // Called on every clock repaint, so it redraws only when the spoken time changes.
    private setClock(color: cg.Color, millis: number): void {
        const text = spokenTime(millis);
        if (this.clocks[color] === text) return;
        this.clocks[color] = text;
        this.redraw();
    }

    // color() is asked on every repaint, so a board flip is followed.
    followClock(clock: Clock, color: () => cg.Color): void {
        clock.onRender(time => this.setClock(color(), time));
        this.setClock(color(), clock.duration);
    }

    /** What the "Last move" section says, for the board's `l` key; empty where there is none. */
    lastMoveText(): string {
        if (this.options.lastMove === false) return '';
        return this.lastMove ?? _('Initial position');
    }

    /** Both clocks in one line, for the board's `t` key; empty when the game has none. */
    clockText(): string {
        return this.clockLines().join(', ');
    }

    private clockLines(): string[] {
        return COLORS.filter(color => this.clocks[color] !== undefined).map(
            color => `${this.colorName(color)}: ${this.clocks[color]}`,
        );
    }

    // An event (a puzzle's "Best move!") is spoken even in the words the status already holds;
    // the game result is set again on every move and must not be.
    setStatus(status: string, event = false): void {
        this.status = event ? respoken(this.status ?? '', status) : status;
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
        return colorName(this.variant, color);
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
        const top = this.options.level ?? 2;
        const section = `h${titled ? top + 1 : top}`;
        const side = `h${titled ? top + 2 : top + 1}`;
        const region = { 'aria-live': this.live, 'aria-atomic': 'true' };

        const byColor = (title: string, rows: (color: cg.Color) => VNode[]) => [
            h(section, title),
            // "Pieces: White", not just "White": headings are also heard out of order, in a list.
            ...COLORS.map(color => h('div', [h(side, `${title}: ${this.colorName(color)}`), ...rows(color)])),
        ];

        return h(`div#${elementId(this.boardName)}.sr-only`, { attrs: { 'data-live': this.live } }, [
            // "Summary", so it is told apart from the keyboard board's own "Board A" heading.
            ...(titled ? [h(`h${top}`, `${_('Board')} ${this.boardName.toUpperCase()}: ${_('Summary')}`)] : []),
            ...byColor(_('Pieces'), color => this.piecesByColor(color)),
            ...(this.variant.pocket ? byColor(_('Pockets'), color => this.pocketByColor(color)) : []),
            ...(this.options.lastMove === false
                ? []
                : [h(section, _('Last move')), h('p', { attrs: region }, this.lastMoveShown)]),
            // role="timer" is never announced as it changes; the time is read when the reader gets there.
            ...(Object.keys(this.clocks).length === 0
                ? []
                : [
                      h(section, _('Time')),
                      ...this.clockLines().map(line => h('p', { attrs: { role: 'timer' } }, line)),
                  ]),
            ...(this.status === undefined
                ? []
                : [h(section, _('Status')), h('p', { attrs: { role: 'status', ...region } }, this.status)]),
        ]);
    }
}
