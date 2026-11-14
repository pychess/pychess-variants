import { h, VNode } from 'snabbdom';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { Api } from 'chessgroundx/api';

import { _ } from '@/i18n';
import { patch } from '@/document';
import { pieceName, Variant } from '@/variants';
import { BoardName } from '@/types';
import { pocketShape } from '@/pocketRow';
import { sound } from '@/sound';
import { BoardSummaryView, colorName, squareName } from './boardSummary';

const ARROWS: Record<string, [number, number]> = {
    ArrowUp: [0, 1],
    ArrowDown: [0, -1],
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
};

type PocketPosition = 'top' | 'bottom';

// Where the cursor can be: a board square ("e4") or a role in a pocket ("white/n-piece"). Not ':',
// which is chessground's rank 10 ("e:").
type Spot = string;

const pocketSpot = (color: cg.Color, role: cg.Role): Spot => `${color}/${role}`;

function parsePocketSpot(spot: Spot): cg.Piece | undefined {
    const [color, role] = spot.split('/');
    return role === undefined ? undefined : { color: color as cg.Color, role: role as cg.Role };
}

/**
 * Keyboard access to a chessgroundx board: one button per square, laid over the board, and one per
 * pocket role, laid over the pockets.
 *
 * TEMPORARY. Its proper home is chessgroundx itself, to be proposed upstream. It sits beside
 * `.cg-wrap`, never inside it, because chessgroundx empties that element on every flip.
 */
export class ChessgroundKeyboard {
    private chessground: Api | undefined;
    private summary: BoardSummaryView | undefined;
    private boardVNode: VNode | undefined;
    private pocketVNodes: Partial<Record<PocketPosition, VNode>> = {};
    // The one spot Tab reaches. Until the player first focuses the board it follows the side at
    // the bottom, which a round page sets only after the first paint; after that it stays put.
    private cursor: Spot | undefined;
    private visited = false;
    // The square a pocket was entered from, to return to.
    private pocketOrigin: cg.Key | undefined;
    // A move's squares: when a promotion or gating chooser closes the cursor returns to where the
    // piece went, or, if the chooser was cancelled, to where it came from.
    private moveOrig: cg.Key | undefined;
    private moveDest: cg.Key | undefined;
    private lastSound = 0;
    // What the board last said in answer to a key (l, t, m). A trailing no-break space alternates so the
    // same answer twice is still announced.
    private notice = '';

    constructor(
        private readonly variant: Variant,
        private readonly boardName: BoardName,
        // Its heading's level: lower under a page's own section (the forum captcha).
        private readonly level = 2,
    ) {}

    /** The square buttons; the page puts this beside the board's `.cg-wrap`. */
    boardView(): VNode {
        const view = this.renderBoard();
        // The controller may have attached first (it is built in the board's own insert hook), so
        // the layer paints once it is in place.
        view.data!.hook = {
            insert: vnode => {
                this.boardVNode = vnode;
                this.update();
            },
        };
        return view;
    }

    /** One pocket's role buttons; the page puts this beside that pocket's row (`#pocket0`, `#pocket1`). */
    pocketView(position: PocketPosition): VNode {
        const view = this.renderPocket(position);
        view.data!.hook = {
            insert: vnode => {
                this.pocketVNodes[position] = vnode;
                this.update();
            },
        };
        return view;
    }

    attach(chessground: Api, summary: BoardSummaryView): void {
        this.chessground = chessground;
        this.summary = summary;
    }

    update(): void {
        if (this.boardVNode === undefined || this.chessground === undefined) return;
        if (!this.visited) this.cursor = this.startSquare(this.chessground.state);
        // A flip moves the buttons, which drops focus; it goes back to the cursor.
        const focused = this.views().some(view => view.contains(document.activeElement));
        this.boardVNode = patch(this.boardVNode, this.renderBoard());
        for (const position of ['top', 'bottom'] as const) {
            const vnode = this.pocketVNodes[position];
            if (vnode !== undefined) this.pocketVNodes[position] = patch(vnode, this.renderPocket(position));
        }
        if (focused) this.focusCursor();
    }

    private onFocus(e: FocusEvent): void {
        const spot = (e.target as HTMLElement).dataset.spot;
        if (spot === undefined) return;
        this.visited = true;
        this.cursor = spot;
    }

    // Leaving the board from a pocket leaves the tab stop on the square the pocket was entered
    // from, so the board's place in the Tab order never moves.
    private onBlur(e: FocusEvent): void {
        const next = e.relatedTarget as HTMLElement | null;
        if (next !== null && this.views().some(view => view.contains(next))) return;
        if (this.cursor !== undefined && parsePocketSpot(this.cursor) && this.pocketOrigin !== undefined) {
            this.cursor = this.pocketOrigin;
            this.update();
        }
    }

    // Keys the board handles never reach Mousetrap on document, so they do not also step the move list.
    private onKey(e: KeyboardEvent): void {
        // Enter and Space activate the button (a click, below); Mousetrap binds Enter on document.
        if (e.key === 'Enter' || e.key === ' ') {
            e.stopPropagation();
            return;
        }
        const chooser = this.chooser();
        // Escape cancels a chooser, as a click outside its choices does.
        if (e.key === 'Escape' && chooser !== undefined) {
            e.stopPropagation();
            chooser.el.click();
            this.closeChooser(this.moveOrig);
            return;
        }
        if (e.altKey || e.ctrlKey || e.metaKey) return;
        const command = this.command(e);
        if (command === undefined) return;
        e.preventDefault();
        e.stopPropagation();
        if (typeof command === 'string') return this.say(command);
        const next = command();
        // While a chooser is open the cursor moves only between its choices; leaving never cancels.
        if (next === undefined || (chooser !== undefined && !chooser.choices.has(next as cg.Key))) {
            this.play(() => sound.outOfBound());
            return;
        }
        this.cursor = next;
        this.update();
        this.focusCursor();
    }

    // A button's click comes from Enter, Space, or a screen reader activating it; never the mouse,
    // which the layer lets through. It does what a click on that square or pocket piece does.
    private onActivate(e: MouseEvent): void {
        const spot = (e.target as HTMLElement).dataset.spot;
        if (spot === undefined || this.chessground === undefined) return;
        const open = this.chooser();
        if (open !== undefined) {
            open.choices.get(spot as cg.Key)?.el.click();
            this.closeChooser(this.moveDest);
            return;
        }
        this.cursor = spot;
        const piece = parsePocketSpot(spot);
        if (piece === undefined) {
            const selected = this.chessground.state.selectable.selected;
            this.moveOrig = selected !== undefined && util.isKey(selected) ? selected : undefined;
            this.moveDest = spot as cg.Key;
            this.chessground.selectSquare(spot as cg.Key);
            if (this.chessground.state.selectable.selected === spot) this.play(() => sound.confirmation());
            // A promotion or gating chooser opens on the move: go to its first choice. chessgroundx
            // runs its move callbacks in a 1ms timeout, so the chooser exists only after that.
            setTimeout(() => {
                const chooser = this.chooser();
                if (chooser === undefined) return;
                const [first, { label }] = chooser.choices.entries().next().value!;
                // A promotion's first choice covers the square just moved to, so focus stays and
                // only the name changes, which a reader does not repeat (measured in Orca): say it.
                if (first === this.cursor) this.say(label);
                this.cursor = first;
                this.update();
                this.focusCursor();
            }, 1);
            return;
        }
        // Gating variants never drop: their pocket pieces enter only by gating.
        const count = this.chessground.state.boardState.pockets?.[piece.color].get(piece.role) ?? 0;
        if (!this.variant.rules.gate && count > 0) this.chessground.selectPocket(piece);
        const selected = this.chessground.state.selectable.selected;
        const picked = selected !== undefined && util.isPiece(selected) && util.samePiece(selected, piece);
        this.play(picked ? () => sound.confirmation() : () => sound.error());
    }

    // The board's keys, as lichess's: what to say, or where the cursor goes (undefined: nowhere,
    // which bumps). Keys the board does not use are left to the page (f flips, ? is help).
    private command(e: KeyboardEvent): string | (() => Spot | undefined) | undefined {
        const arrow = ARROWS[e.key];
        if (arrow !== undefined) return e.shiftKey ? undefined : () => this.step(arrow);
        const key = e.key.toLowerCase();
        if (key === 'l' && !e.shiftKey) return this.summary?.lastMoveText() || undefined;
        if (key === 't' && !e.shiftKey) return this.summary?.clockText() || undefined;
        if (key === 'm' && !e.shiftKey) return this.legalMoves();
        // 1-9 and 0 (the tenth) go to that rank in the cursor's file; with Shift, that file in its
        // rank. By the key's place, so Shift does not change the character on any layout.
        const digit = /^Digit(\d)$/.exec(e.code)?.[1];
        if (digit !== undefined) return () => this.jumpToLine(digit === '0' ? 9 : Number(digit) - 1, e.shiftKey);
        // A piece letter goes to the next piece of that kind, either colour, in reading order;
        // with Shift, the previous one.
        const role = `${key}-piece` as cg.Role;
        const pieceRow = this.variant.pieceRow;
        if (pieceRow.white.includes(role) || pieceRow.black.includes(role)) {
            return () => this.jumpToPiece(role, e.shiftKey ? -1 : 1);
        }
        return undefined;
    }

    private say(text: string): void {
        this.notice = this.notice.endsWith('\u00a0') ? text : `${text}\u00a0`;
        this.update();
    }

    // The cursor's piece's moves, or a pocket role's drops: "d4, d5 Black pawn". Only for a side
    // that can move now; a finished game keeps its last dests.
    private legalMoves(): string {
        const state = this.chessground?.state;
        const spot = this.cursor;
        const pocket = spot === undefined ? undefined : parsePocketSpot(spot);
        const piece = pocket ?? (spot === undefined ? undefined : state?.boardState.pieces.get(spot as cg.Key));
        const mover = state?.movable.color;
        const own = piece !== undefined && (mover === 'both' || mover === piece.color);
        const orig = pocket === undefined ? (spot as cg.Key) : util.dropOrigOf(pocket.role);
        const dests = own ? state?.movable.dests?.get(orig) : undefined;
        if (dests === undefined || dests.length === 0) return _('No legal moves');
        return dests.map(key => this.squareLabel(key)).join(', ');
    }

    // From a pocket, relative to the square it was entered from: pick a piece, then jump to the drop.
    private jumpToLine(index: number, file: boolean): Spot | undefined {
        const from = this.cursor !== undefined && parsePocketSpot(this.cursor) ? this.pocketOrigin : this.cursor;
        if (from === undefined) return undefined;
        const { width, height } = this.variant.board.dimensions;
        const [f, r] = util.key2pos(from as cg.Key);
        if (index >= (file ? width : height)) return undefined;
        return util.pos2key(file ? [index, r] : [f, index]);
    }

    private jumpToPiece(role: cg.Role, direction: 1 | -1): Spot | undefined {
        const pieces = this.chessground?.state.boardState.pieces;
        const keys = this.squares().filter(key => pieces?.get(key)?.role === role);
        if (keys.length === 0) return undefined;
        const i = keys.indexOf(this.cursor as cg.Key);
        // From the cursor, wrapping; off a piece of that kind, the first (or last) one.
        if (i === -1) return direction === 1 ? keys[0] : keys[keys.length - 1];
        return keys[(i + direction + keys.length) % keys.length];
    }

    // As lichess does: at most one cue per 100ms, so a held arrow at the edge does not machine-gun.
    private play(cue: () => void): void {
        const now = performance.now();
        if (now - this.lastSound < 100) return;
        this.lastSound = now;
        cue();
    }

    private closeChooser(to: cg.Key | undefined): void {
        this.cursor = to ?? this.moveDest ?? this.cursor;
        this.update();
        this.focusCursor();
    }

    // The promotion or gating chooser pychess draws over board squares (client/input/promotion.ts,
    // gating.ts), keyed by the square each choice covers, in the order drawn. Undefined when none is
    // open. It is read from that DOM: each choice is a `square` placed by top/left percentages.
    private chooser(): { el: HTMLElement; choices: Map<cg.Key, { el: HTMLElement; label: string }> } | undefined {
        const state = this.chessground?.state;
        const el = state?.dom.elements.container.querySelector<HTMLElement>('#extension_choice');
        if (state === undefined || el === null || el === undefined) return undefined;
        const gating = el.classList.contains('top') || el.classList.contains('bottom');
        const moved = this.moveDest === undefined ? undefined : state.boardState.pieces.get(this.moveDest)?.role;
        const { width, height } = this.variant.board.dimensions;
        const asWhite = state.orientation === 'white';
        const choices = new Map<cg.Key, { el: HTMLElement; label: string }>();
        for (const square of el.querySelectorAll<HTMLElement>('square')) {
            const col = Math.round(parseFloat(square.style.left) / (100 / width));
            const row = Math.round(parseFloat(square.style.top) / (100 / height));
            const key = util.pos2key(asWhite ? [col, height - 1 - row] : [width - 1 - col, row]);
            const piece = square.firstElementChild;
            const role = [...(piece?.classList ?? [])].find(c => c.endsWith('-piece')) as cg.Role | undefined;
            const color: cg.Color = piece?.classList.contains('white') ? 'white' : 'black';
            const name = role === undefined ? '' : pieceName(this.variant, role, color);
            const label = gating
                ? role === undefined
                    ? _('No gating')
                    : _('Gate %1', name)
                : role === moved
                  ? _('Do not promote')
                  : _('Promote to %1', name);
            choices.set(key, { el: square, label });
        }
        return choices.size === 0 ? undefined : { el, choices };
    }

    // This board's own elements: a two-board page has a second layer.
    private views(): HTMLElement[] {
        return [this.boardVNode, this.pocketVNodes.top, this.pocketVNodes.bottom]
            .map(view => view?.elm as HTMLElement | undefined)
            .filter(el => el !== undefined);
    }

    private focusCursor(): void {
        for (const view of this.views()) {
            const el = view.querySelector<HTMLElement>(`[data-spot="${this.cursor}"]`);
            if (el) return el.focus();
        }
    }

    // Arrows follow the orientation: Up is always away from the player. Right past the board's right
    // edge enters a pocket, as both are drawn right of the board: the mover's own, or by half when
    // both colours move (analysis); anywhere else past the edge, nothing moves. In a pocket,
    // Left/Right step through the roles as drawn, and Left past the first goes back to the board.
    private step([df, dr]: [number, number]): Spot | undefined {
        if (this.cursor === undefined || this.chessground === undefined) return undefined;
        const state = this.chessground.state;
        const sign = state.orientation === 'white' ? 1 : -1;
        const { width, height } = this.variant.board.dimensions;

        const piece = parsePocketSpot(this.cursor);
        if (piece !== undefined) {
            const roles = this.variant.pocket!.roles[piece.color];
            const i = roles.indexOf(piece.role) + df;
            if (dr !== 0 || i >= roles.length) return undefined;
            return i < 0 ? this.pocketOrigin : pocketSpot(piece.color, roles[i]);
        }

        const [file, rank] = util.key2pos(this.cursor as cg.Key);
        const target: cg.Pos = [file + sign * df, rank + sign * dr];
        const off = target[0] < 0 || target[0] >= width || target[1] < 0 || target[1] >= height;
        if (!off) return util.pos2key(target);
        // Not where the page draws no pockets (the forum captcha).
        if (df !== 1 || !this.variant.pocket || this.pocketVNodes.bottom === undefined) return undefined;
        const mover = state.movable.color;
        const lowerHalf = (sign === 1 ? rank : height - 1 - rank) < height / 2;
        const color =
            mover === 'white' || mover === 'black'
                ? mover
                : lowerHalf
                  ? state.orientation
                  : util.opposite(state.orientation);
        this.pocketOrigin = this.cursor as cg.Key;
        return pocketSpot(color, this.variant.pocket.roles[color][0]);
    }

    // The king of the side at the bottom, else that side's bottom-left square.
    private startSquare(state: Api['state']): cg.Key {
        const color = state.orientation;
        for (const [key, piece] of state.boardState.pieces) {
            if (piece.color === color && this.variant.kingRoles.includes(piece.role)) return key;
        }
        const { width, height } = this.variant.board.dimensions;
        return util.pos2key(color === 'white' ? [0, 0] : [width - 1, height - 1]);
    }

    // "e4 White pawn"; an empty square is just its name. Squares in the variant's own notation.
    private squareLabel(key: cg.Key): string {
        const square = squareName(key, this.variant.notation, this.variant.board.dimensions);
        const piece = this.chessground?.state.boardState.pieces.get(key);
        if (piece === undefined) return square;
        return `${square} ${colorName(this.variant, piece.color)} ${pieceName(this.variant, piece.role, piece.color)}`;
    }

    // "White pocket: knight, 2"; a role with none left is still a stop, so the positions never shift.
    private pocketLabel(color: cg.Color, role: cg.Role): string {
        const count = this.chessground?.state.boardState.pockets?.[color].get(role) ?? 0;
        return `${_('%1 pocket', colorName(this.variant, color))}: ${pieceName(this.variant, role, color)}, ${count}`;
    }

    private button(spot: Spot, label: string): VNode {
        return h('button', {
            key: spot,
            attrs: {
                type: 'button',
                tabindex: spot === this.cursor ? '0' : '-1',
                'data-spot': spot,
                'aria-label': label,
            },
        });
    }

    private handlers() {
        return {
            focusin: (e: FocusEvent) => this.onFocus(e),
            focusout: (e: FocusEvent) => this.onBlur(e),
            keydown: (e: KeyboardEvent) => this.onKey(e),
            click: (e: MouseEvent) => this.onActivate(e),
        };
    }

    // Rows top to bottom as the player sees them, so the reading order follows the screen.
    private renderBoard(): VNode {
        const choices = this.chooser()?.choices;
        const { width, height } = this.variant.board.dimensions;
        const suffix = this.boardName === '' ? '' : `-${this.boardName}`;
        // .sr-only is absolutely positioned, so the heading takes no grid cell.
        const heading = `${_('Board')} ${this.boardName.toUpperCase()}`.trim();
        const children: VNode[] = [
            h(`h${this.level}.sr-only`, { key: 'heading' }, heading),
            ...this.squares().map(key => this.button(key, choices?.get(key)?.label ?? this.squareLabel(key))),
            h('p.sr-only', { key: 'notice', attrs: { 'aria-live': 'assertive', 'aria-atomic': 'true' } }, this.notice),
        ];
        return h(
            'div.cg-keyboard',
            {
                // Keyed, so a page patching its board from plain DOM (a study chapter switch)
                // replaces this layer rather than reusing an element with the old one's listeners.
                key: 'cg-keyboard',
                on: this.handlers(),
                style: {
                    // A board no page sizes (the forum captcha) is its wrapper's size.
                    width: `var(--cg-width${suffix}, 100%)`,
                    height: `var(--cg-height${suffix}, 100%)`,
                    gridTemplateColumns: `repeat(${width}, 1fr)`,
                    gridTemplateRows: `repeat(${height}, 1fr)`,
                },
            },
            children,
        );
    }

    // Every square, rows top to bottom as the player sees them.
    private squares(): cg.Key[] {
        const { width, height } = this.variant.board.dimensions;
        const asWhite = (this.chessground?.state.orientation ?? 'white') === 'white';
        const keys: cg.Key[] = [];
        for (let row = 0; row < height; row++) {
            for (let col = 0; col < width; col++) {
                keys.push(util.pos2key(asWhite ? [col, height - 1 - row] : [width - 1 - col, row]));
            }
        }
        return keys;
    }

    // Laid out like chessgroundx's pocket row (`pocketShape`), which shows the top player's
    // opponent at the top.
    private renderPocket(position: PocketPosition): VNode {
        const key = `cg-keyboard-${position}`;
        if (!this.variant.pocket) return h('div.cg-keyboard-pocket', { key });
        const orientation = this.chessground?.state.orientation ?? 'white';
        const color = position === 'top' ? util.opposite(orientation) : orientation;
        const { width, height } = this.variant.board.dimensions;
        const { pieceRows, pocketLength } = pocketShape(this.variant, color);
        const suffix = this.boardName !== '';
        return h(
            'div.cg-keyboard-pocket',
            {
                key,
                on: this.handlers(),
                // The two-board pages size their pockets per layout and their wrapper to the pocket.
                style: {
                    width: suffix ? '100%' : `calc(var(--cg-width) / ${width} * ${pocketLength})`,
                    height: suffix ? '100%' : `calc(var(--cg-height) / ${height} * ${pieceRows})`,
                    gridTemplateColumns: `repeat(${pocketLength}, 1fr)`,
                    gridTemplateRows: `repeat(${pieceRows}, 1fr)`,
                },
            },
            this.variant.pocket.roles[color].map(role =>
                this.button(pocketSpot(color, role), this.pocketLabel(color, role)),
            ),
        );
    }
}
