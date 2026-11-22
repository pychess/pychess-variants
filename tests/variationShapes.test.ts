import { expect, test } from '@jest/globals';
import type { DrawShape } from 'chessgroundx/draw';
import { read } from 'chessgroundx/fen';
import type { BoardDimensions, Color } from 'chessgroundx/types';

import type { AnalysisTreeNode } from '../client/analysis/analysisTree';
import { hiliteVariations, shapesFromVariation } from '../client/analysis/variationShapes';

function board(fen = 'start', dimensions: BoardDimensions = { width: 8, height: 8 }, turnColor: Color = 'white') {
    return { dimensions, boardState: read(fen, dimensions), turnColor };
}

function node(move: string, fen = '8/8/8/8/8/8/8/8', san = move): AnalysisTreeNode {
    return { id: move, path: move, ply: 1, children: [], step: { move, fen, san, turnColor: 'black', check: false } };
}

const forks = [node('e2e4'), node('d2d4')];

test('forks use Lichess brushes, outlines and below-piece stacking; a single continuation has no fork arrows', () => {
    const shapes = hiliteVariations(forks, 'd2d4', [], board());
    expect(shapes).toEqual([
        { orig: 'e2', dest: 'e4', brush: 'variation', modifiers: { hilite: '#aaa' }, below: true },
        { orig: 'd2', dest: 'd4', brush: 'variation', modifiers: { hilite: '#3291ff' }, below: true },
    ]);
    expect(hiliteVariations(forks.slice(0, 1), 'e2e4', [], board())).toEqual([]);
    expect(hiliteVariations(forks, 'e2e4', [], board(), true).map(s => s.brush)).toEqual(['paleGreen', 'paleRed']);
});

test('an overlapping engine arrow stays above pieces and keeps its width; selection never mutates cached PV shapes', () => {
    const engine: DrawShape[] = [{ orig: 'e2', dest: 'e4', brush: 'paleGreen', modifiers: { lineWidth: 9 } }];
    const selected = hiliteVariations(forks, 'e2e4', engine, board());
    expect(selected[0]).toEqual({ ...engine[0], modifiers: { lineWidth: 9, hilite: 'white' } });
    expect(selected).toHaveLength(2);
    expect(selected[0].below).toBeUndefined();
    expect(hiliteVariations(forks, 'd2d4', engine, board())[0].modifiers?.hilite).toBeUndefined();
    expect(engine[0].modifiers).toEqual({ lineWidth: 9 });
});

test.each([
    ['a10i10', { width: 9, height: 10 }, 'a:', 'i:'],
    ['a:i:', { width: 9, height: 10 }, 'a:', 'i:'],
    ['a16p16', { width: 16, height: 16 }, 'a@', 'p@'],
    ['a@p@', { width: 16, height: 16 }, 'a@', 'p@'],
] as const)('variant move %s uses board dimensions without orientation arithmetic', (move, dimensions, orig, dest) => {
    expect(shapesFromVariation(node(move), board('start', dimensions), 'variation')[0]).toMatchObject({ orig, dest });
});

test.each(['a11i10', 'j1a1', '0000', '(none)', 'garbage'])('out-of-board or malformed move %s is not drawn', move => {
    expect(shapesFromVariation(node(move), board('start', { width: 9, height: 10 }), 'variation')).toEqual([]);
});

test('drops use the resolved fairy role and only selected drops get outlines', () => {
    const drop = node('+P@a3', '8/8/8/8/8/+P7/8/8');
    const shapes = hiliteVariations([forks[0], drop], 'e2e4', [], board());
    expect(shapes[1]).toMatchObject({ orig: 'a3', brush: 'variation', modifiers: { hilite: undefined }, below: true });
    expect(shapes[2].piece).toMatchObject({ role: 'pp-piece', color: 'white', scale: 0.8 });
    expect(hiliteVariations([forks[0], drop], drop.path, [], board())[1].modifiers?.hilite).toBe('#3291ff');
});

test('promotions and shogi promotions use the resulting position, while gating is not mistaken for promotion', () => {
    const promotion = node('a7a8q', 'Q7/8/8/8/8/8/8/8');
    expect(shapesFromVariation(promotion, board('8/P7/8/8/8/8/8/8'), 'variation')[1].piece?.role).toBe('q-piece');
    const shogi = node('a7a8+', '+P7/8/8/8/8/8/8/8');
    expect(shapesFromVariation(shogi, board('8/P7/8/8/8/8/8/8'), 'variation')[1].piece?.role).toBe('pp-piece');
    const gating = node('e1e2h', '8/8/8/8/8/8/4K3/4H3');
    expect(shapesFromVariation(gating, board('8/8/8/8/8/8/8/4K3'), 'variation')).toHaveLength(1);
});

test('compound wall moves retain their extra target even when the primary arrow overlaps a PV', () => {
    const compound = node('a2a3,a3h8');
    const other = node('b2b3');
    const engine: DrawShape[] = [{ orig: 'a2', dest: 'a3', brush: 'paleGreen' }];
    expect(hiliteVariations([compound, other], compound.path, engine, board())).toContainEqual({
        orig: 'h8',
        brush: 'variation',
        modifiers: { hilite: '#3291ff' },
        below: true,
    });
});

test('pass moves keep their source as a circle and overlays keep labels and custom anchors', () => {
    expect(shapesFromVariation(node('e1e1'), board(), 'variation')[0]).toMatchObject({ orig: 'e1', dest: 'e1' });
    const overlay: DrawShape = {
        orig: 'e2',
        dest: 'e4',
        customSvg: { html: '<circle/>', center: 'dest' },
        label: { text: '!' },
    };
    const shapes = hiliteVariations(forks, 'e2e4', [overlay], board());
    expect(shapes[0]).toEqual(overlay);
    expect(shapes).toHaveLength(3);
});
