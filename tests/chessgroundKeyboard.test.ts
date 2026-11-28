import { describe, expect, test } from '@jest/globals';
import { h } from 'snabbdom';
import { Chessground } from 'chessgroundx/chessground';
import type { Api } from 'chessgroundx/api';
import type * as cg from 'chessgroundx/types';

import { ChessgroundKeyboard } from '../client/accessibility/chessgroundKeyboard';
import { BoardSummaryView } from '../client/accessibility/boardSummary';
import { patch } from '../client/document';
import { VARIANTS } from '../client/variants';

// The layer as the round page places it, beside a real chessground.
function board(): { chessground: Api; keyboard: ChessgroundKeyboard; layer: () => HTMLElement } {
    document.body.innerHTML = '<div id="cg"></div><div id="layer"></div>';
    const variant = VARIANTS['chess'];
    const chessground = Chessground(document.getElementById('cg')!, {
        fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        dimensions: variant.board.dimensions,
    });
    const keyboard = new ChessgroundKeyboard(variant, '');
    patch(document.getElementById('layer')!, h('div', [keyboard.boardView()]));
    keyboard.attach(chessground, new BoardSummaryView(variant, ''));
    keyboard.update();
    return { chessground, keyboard, layer: () => document.querySelector<HTMLElement>('.cg-keyboard')! };
}

const buttons = (layer: HTMLElement) => [...layer.querySelectorAll<HTMLButtonElement>('button')];
const label = (layer: HTMLElement, key: string) =>
    layer.querySelector(`[data-spot="${key}"]`)!.getAttribute('aria-label');

// Every square says what chessground holds there: its name alone when empty, else name and piece.
function expectLabelsMatch(chessground: Api, layer: HTMLElement) {
    for (const button of buttons(layer)) {
        const key = button.dataset.spot as cg.Key;
        const text = button.getAttribute('aria-label')!;
        if (chessground.state.boardState.pieces.has(key)) expect(text.startsWith(`${key} `)).toBe(true);
        else expect(text).toBe(key);
    }
}

describe('ChessgroundKeyboard', () => {
    test("labels match chessground's state after a move and after a flip", () => {
        const { chessground, keyboard, layer } = board();
        expectLabelsMatch(chessground, layer());

        chessground.move('e2', 'e4');
        keyboard.update();
        expect(label(layer(), 'e2')).toBe('e2');
        expect(label(layer(), 'e4')).toMatch(/^e4 White pawn$/i);
        expectLabelsMatch(chessground, layer());

        chessground.toggleOrientation();
        keyboard.update();
        expect(label(layer(), 'e4')).toMatch(/^e4 White pawn$/i);
        expectLabelsMatch(chessground, layer());
    });

    test('orientation: squares read from the top as the player sees them, and Up is away from them', () => {
        const { chessground, keyboard, layer } = board();
        const order = () => buttons(layer()).map(b => b.dataset.spot);
        const up = (from: string) => {
            layer().querySelector<HTMLElement>(`[data-spot="${from}"]`)!.focus();
            document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
            return (document.activeElement as HTMLElement).dataset.spot;
        };

        expect(order().slice(0, 2)).toEqual(['a8', 'b8']);
        expect(order().at(-1)).toBe('h1');
        expect(up('e2')).toBe('e3');

        chessground.toggleOrientation();
        keyboard.update();
        expect(order().slice(0, 2)).toEqual(['h1', 'g1']);
        expect(order().at(-1)).toBe('a8');
        expect(up('e2')).toBe('e1');
    });
});
