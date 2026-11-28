import { h, VNode } from 'snabbdom';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import * as Mousetrap from 'mousetrap';

import { boardSettings } from '@/boardSettings';
import type { GameController } from '@/gameCtrl';
import { cg2uci, uci2cg } from '@/chess';
import { selectMove } from '@/movelist';
import { patch } from '@/document';
import { _ } from '@/i18n';
import { BoardName } from '@/types';
import { sound } from '@/sound';

const placeholderId = (boardName: BoardName) => 'keyboard-move' + (boardName ? '-' + boardName : '');

/** Where a page wants the move input; empty until the board's controller fills it. */
export function keyboardMovePlaceholder(boardName: BoardName): VNode {
    return h(`div#${placeholderId(boardName)}`);
}

/** `m`, as lichess's: the next move input after the focused one, so on a two-board page it alternates. */
function focusNextKeyboardMove(): void {
    const inputs = [...document.querySelectorAll<HTMLInputElement>('.keyboard-move input')];
    inputs[(inputs.indexOf(document.activeElement as HTMLInputElement) + 1) % inputs.length]?.focus();
}

/** Lichess's typed commands, each offered only by a page that can do it. */
export type KeyboardMoveCommand = 'clock' | 'who' | 'draw' | 'resign' | 'zerk' | 'next' | 'upv' | 'downv';

/** A command's action; a text it returns is read out. */
export type KeyboardMoveCommands = Partial<Record<KeyboardMoveCommand, () => string | void>>;

/** What the text typed so far asks for. Squares and moves are in Fairy-Stockfish's UCI. */
export type Typed =
    | { kind: 'move'; uci: string }
    | { kind: 'select'; key: string }
    | { kind: 'wait' }
    | { kind: 'wrong' };

/** The legal moves under every spelling the input accepts, in the position being typed into. */
interface MoveTable {
    readonly spellings: readonly (readonly [string, string])[];
    // Algebraic notation: check marks are noise, '=' before a promotion piece is optional, a lone
    // square selects it, and ICCF digits are squares. In shogi and xiangqi notation '+' and '='
    // carry meaning and digits are already squares.
    readonly algebraic: boolean;
    readonly width: number;
    readonly height: number;
}

/**
 * Lichess's rules (keyboardSubmit.ts) over a table of legal moves, so that every variant's own
 * notation works: a move is played once the text names it and nothing longer; a lone square is
 * selected, so UCI is typed as two squares; '0' is 'O' in castling; 'x' is optional.
 */
export function parseTyped(typed: string, table: MoveTable, selected: string | undefined, force: boolean): Typed {
    let text = typed.trim();
    if (text === '') return { kind: 'wait' };
    if (/^[0o](-[0o]){1,2}$/i.test(text)) text = text.replace(/[0o]/gi, 'O');
    if (table.algebraic && table.width === 8 && table.height === 8 && /^([1-8]{2}){1,2}[1-4]?$/.test(text)) {
        text = iccfToUci(text);
    }
    const norm = (s: string) => normalise(s, table);
    // With a square selected, a square is its destination first: "b1" then "c3" is the knight, not c3.
    const tries = [text];
    if (selected !== undefined) {
        if (table.algebraic && isSquare(text, table)) tries.unshift(selected + text);
        else tries.push(selected + text);
    }
    if (text.startsWith('@')) tries.push('P' + text);
    for (const t of tries) {
        const uci = lookup(t, table);
        if (uci === undefined) continue;
        const longer = table.spellings.some(([s]) => norm(s) !== norm(t) && norm(s).startsWith(norm(t)));
        return longer && !force ? { kind: 'wait' } : { kind: 'move', uci };
    }
    if (table.algebraic && isSquare(text, table)) {
        // A square that begins a move's SAN ("b8" of "b8=Q"), or on a board of ten ranks "a1" of
        // "a10", may still become more. UCI spellings do not count: they start with the origin.
        const more = isSquare(text + '0', table) || table.spellings.some(([s, u]) => s !== u && norm(s).startsWith(norm(text)));
        return more && !force ? { kind: 'wait' } : { kind: 'select', key: text };
    }
    const started = tries.some(t => table.spellings.some(([s]) => norm(s).startsWith(norm(t))));
    return started ? { kind: 'wait' } : { kind: 'wrong' };
}

// Any case, and in algebraic notation without '='.
function normalise(s: string, table: MoveTable): string {
    return (table.algebraic ? s.replace(/=/g, '') : s).toLowerCase();
}

// Exact spelling first, so "Bc6" is the bishop and "bc6" the pawn; then normalised, if that is one move.
function lookup(text: string, table: MoveTable): string | undefined {
    const exact = table.spellings.find(([s]) => s === text);
    if (exact) return exact[1];
    const n = normalise(text, table);
    const any = new Set(table.spellings.filter(([s]) => normalise(s, table) === n).map(([, u]) => u));
    return any.size === 1 ? [...any][0] : undefined;
}

function isSquare(text: string, table: MoveTable): boolean {
    const m = /^([a-z])(\d{1,2})$/.exec(text);
    if (!m) return false;
    const rank = Number(m[2]);
    return m[1].charCodeAt(0) - 97 < table.width && rank >= 1 && rank <= table.height && !m[2].startsWith('0');
}

// ICCF: files as digits, then an optional promotion digit (1 queen, 2 rook, 3 bishop, 4 knight).
function iccfToUci(digits: string): string {
    const file = (d: string) => String.fromCharCode(96 + Number(d));
    let uci = file(digits[0]) + digits[1];
    if (digits.length >= 4) uci += file(digits[2]) + digits[3];
    if (digits.length === 5) uci += 'qrbn'[Number(digits[4]) - 1];
    return uci;
}

/**
 * Typing moves, lichess's keyboard move input: shown only while the "Input moves with the keyboard"
 * board setting is on. The controller builds it once its board exists; it fills the page's
 * placeholder, if the page has one.
 */
export class KeyboardMove {
    private vnode: VNode | undefined;
    private readonly boardName: BoardName;
    // The last answer read out; a trailing no-break space alternates so the same answer twice is
    // still announced.
    private notice = '';

    constructor(private readonly ctrl: GameController) {
        this.boardName = ctrl.boardName;
        const el = document.getElementById(placeholderId(this.boardName));
        if (!el) return;
        this.vnode = patch(el, this.view());
        // False stops the 'm' from being typed into the input it focuses.
        Mousetrap.bind('m', () => {
            focusNextKeyboardMove();
            return false;
        });
    }

    /** Whether the page shows the input now (for the help dialog). */
    active(): boolean {
        return this.vnode !== undefined && !!boardSettings.settings['keyboardMove'].value;
    }

    /** A legal move of the current position as [SAN, UCI], for the help dialog to show. */
    example(): [string, string] | undefined {
        const move = this.table().spellings.find(([s, u]) => s !== u);
        return move && [move[0], move[1]];
    }

    /** After every change of position: text typed ahead is played once it is legal, as lichess's. */
    positionChanged(): void {
        this.submit(false, true);
    }

    private input(): HTMLInputElement | null {
        return (this.vnode?.elm as HTMLElement | undefined)?.querySelector('input') ?? null;
    }

    private submit(force: boolean, yourMove = false): void {
        const input = this.input();
        if (!input) return;
        // As lichess: red, with the error sound once as the text turns wrong. Also aria-invalid,
        // which lichess lacks, so that a screen reader can tell.
        const wrong = this.interpret(input, force, yourMove);
        if (wrong && !input.classList.contains('wrong')) sound.error();
        input.classList.toggle('wrong', wrong);
        input.setAttribute('aria-invalid', String(wrong));
    }

    // In lichess's order: '/' goes to the chat, "resign" is waited for before any move (so "r" is not
    // yet a rook), then moves, then the other commands. Commands work on either side's turn.
    // True when the text can become nothing: no legal move and no command starts with it.
    private interpret(input: HTMLInputElement, force: boolean, yourMove: boolean): boolean {
        if (input.value === '') {
            if (force) this.ctrl.confirmPendingMove();
            return false;
        }
        if (input.value.includes('/')) {
            input.value = '';
            document.getElementById('chat-entry')?.focus();
            return false;
        }
        const commands: Record<string, () => string | void> = {
            ...this.ctrl.keyboardMoveCommands(),
            help: () => this.ctrl.openKeyboardHelp(),
            '?': () => this.ctrl.openKeyboardHelp(),
        };
        const word = input.value.trim().toLowerCase();
        const run = (name: string) => {
            input.value = '';
            const said = commands[name]();
            if (said) this.say(said);
            return false;
        };
        if (commands.resign && 'resign'.startsWith(word)) return word === 'resign' && run('resign');
        const state = this.ctrl.chessground.state;
        const canMove = state.movable.color === 'both' || state.movable.color === state.turnColor;
        if (canMove) {
            const selected = state.selectable.selected;
            const typed = parseTyped(input.value, this.table(), selected !== undefined && util.isKey(selected) ? cg2uci(selected) : undefined, force);
            if (typed.kind === 'move' || typed.kind === 'select') {
                input.value = '';
                if (typed.kind === 'move') this.play(typed.uci);
                else this.select(uci2cg(typed.key) as cg.Key);
                return false;
            }
            if (typed.kind === 'wait') return false;
        }
        if (word in commands) return run(word);
        if (Object.keys(commands).some(name => name.startsWith(word))) return false;
        // Typed ahead and still wrong once the turn came: dropped, as lichess's.
        if (yourMove) {
            input.value = '';
            sound.error();
            return false;
        }
        return canMove;
    }

    // Escape leaves; the arrows step through the moves as the page's own arrows do (which do not
    // reach an input); 'm' in an empty input goes on to the next one.
    private onKeydown(e: KeyboardEvent): void {
        const input = e.target as HTMLInputElement;
        const ctrl = this.ctrl;
        const step: Record<string, () => void> = {
            ArrowLeft: () => selectMove(ctrl, ctrl.ply - 1, ctrl.plyVari),
            ArrowRight: () => selectMove(ctrl, ctrl.ply + 1, ctrl.plyVari),
            ArrowUp: () => selectMove(ctrl, 0),
            ArrowDown: () => selectMove(ctrl, ctrl.steps.length - 1),
        };
        if (e.key === 'Escape') input.blur();
        else if (e.key in step) {
            e.preventDefault();
            step[e.key]();
        } else if (e.key === 'm' && input.value === '') {
            e.preventDefault();
            focusNextKeyboardMove();
        }
    }

    private say(text: string): void {
        this.notice = this.notice.endsWith('\u00a0') ? text : `${text}\u00a0`;
        this.redraw();
    }

    private select(key: cg.Key): void {
        const chessground = this.ctrl.chessground;
        if (chessground.state.selectable.selected === key) chessground.cancelMove();
        else chessground.selectSquare(key, true);
    }

    // As a click does, so premoves, the correspondence confirm, sounds and the extra inputs all apply.
    private play(uci: string): void {
        const chessground = this.ctrl.chessground;
        chessground.cancelMove();
        const drop = /^([A-Z+]+)@(.+)$/.exec(uci);
        if (drop) {
            const role = `${drop[1].toLowerCase()}-piece` as cg.Role;
            chessground.selectPocket({ role, color: chessground.state.turnColor });
            chessground.selectSquare(uci2cg(drop[2]) as cg.Key);
            return;
        }
        const [, orig, dest, suffix] = /^([a-z]\d+)([a-z]\d+)(.*)$/.exec(uci)!;
        const origKey = uci2cg(orig) as cg.Key;
        const moved = chessground.state.boardState.pieces.get(origKey)?.role;
        chessground.selectSquare(origKey);
        chessground.selectSquare(uci2cg(dest) as cg.Key);
        chessground.cancelMove();
        // chessgroundx runs its move callbacks in a 1ms timeout, so a chooser exists only after that.
        setTimeout(() => this.choose(suffix, moved), 1);
    }

    // The promotion or gating choice the typed move already named.
    private choose(suffix: string, moved: cg.Role | undefined): void {
        const chooser = this.ctrl.chessground.state.dom.elements.container.querySelector('#extension_choice');
        for (const square of chooser?.querySelectorAll<HTMLElement>('square') ?? []) {
            const role = [...(square.firstElementChild?.classList ?? [])].find(c => c.endsWith('-piece'));
            const named =
                suffix === '+'
                    ? role !== undefined && role !== moved
                    : suffix === '' || suffix === '='
                      ? role === moved || role === undefined
                      : role === `${suffix.toLowerCase()}-piece`;
            if (named) return square.click();
        }
    }

    /** The current position's legal moves, by SAN in the variant's notation, SAN without 'x', and UCI. */
    private table(): MoveTable {
        const board = this.ctrl.ffishBoard;
        const notation = this.ctrl.variant.notation;
        const algebraic = notation === cg.Notation.ALGEBRAIC || notation === cg.Notation.THAI_ALGEBRAIC;
        const spellings: [string, string][] = [];
        for (const uci of board.legalMoves().split(' ').filter(Boolean)) {
            let san = board.sanMove(uci, this.ctrl.notationAsObject);
            if (algebraic) san = san.replace(/[+#]+$/, '');
            spellings.push([san, uci], [uci, uci]);
            if (san.includes('x')) spellings.push([san.replace('x', ''), uci]);
        }
        const { width, height } = this.ctrl.variant.board.dimensions;
        return { spellings, algebraic, width, height };
    }

    /** After the setting changes. */
    redraw(): void {
        if (this.vnode) this.vnode = patch(this.vnode, this.view());
    }

    private view(): VNode {
        const id = placeholderId(this.boardName);
        if (!boardSettings.settings['keyboardMove'].value) return h(`div#${id}`);
        // The key goes in a <kbd>, so it is substituted after translating.
        const [before, after] = _('Press %1 to focus', '\u0000').split('\u0000');
        const label = this.boardName
            ? `${_('Your move')}: ${_('Board')} ${this.boardName.toUpperCase()}`
            : _('Your move');
        // Both lines are always there; CSS shows the help only while the input has focus, so it can
        // also be the input's description.
        return h(`div#${id}.keyboard-move`, [
            h('input', {
                on: {
                    keyup: (e: KeyboardEvent) => e.isTrusted && this.submit(e.key === 'Enter'),
                    keydown: (e: KeyboardEvent) => this.onKeydown(e),
                },
                attrs: {
                    spellcheck: 'false',
                    autocomplete: 'off',
                    'aria-label': label,
                    'aria-describedby': `${id}-help`,
                },
            }),
            h('strong', [before, h('kbd', 'm'), after]),
            h(`em#${id}-help`, _('Enter SAN (Nc3) or UCI (b1c3) moves, type ? to learn more')),
            h('p.sr-only', { attrs: { 'aria-live': 'assertive', 'aria-atomic': 'true' } }, this.notice),
        ]);
    }
}
