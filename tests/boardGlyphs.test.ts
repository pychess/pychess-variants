import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeAll, expect, test } from '@jest/globals';
import { glyphToSvg } from 'chessgroundx/glyph';
import type { BoardDimensions } from 'chessgroundx/types';

import type { AnalysisTreeNode } from '../client/analysis/analysisTree';
import { annotationShapes, visibleNags } from '../client/analysis/glyphs';

const board = { dimensions: { width: 8, height: 8 } as BoardDimensions, kingRoles: ['k-piece'] as const };
const svgs = glyphToSvg(4);
function node(move: string | undefined, fen = '8/8/8/8/8/8/8/8', san = 'e4', nags = [1]): AnalysisTreeNode {
    return {
        id: 'move',
        path: move ?? '',
        ply: 1,
        children: [],
        step: { move, fen, san, turnColor: 'black', check: false },
        annotations: { nags, shapes: [], comments: [] },
    };
}
function annotations(current: AnalysisTreeNode, dimensions: BoardDimensions = board.dimensions) {
    return annotationShapes(
        current,
        undefined,
        { ...board, kingRoles: [...board.kingRoles], dimensions },
        current.annotations?.nags ?? [],
    );
}

test('uses upstream SVGs, four-glyph limit and reversed stack order without mutating numeric NAGs', () => {
    const current = node('e2e4', undefined, 'e4', [1, 14, 146, 40, 32]);
    const shapes = annotations(current);
    expect(shapes.map(shape => shape.orig)).toEqual(['e4', 'e4', 'e4', 'e4']);
    expect(shapes.map(shape => (typeof shape.customSvg === 'object' ? shape.customSvg.html : undefined))).toEqual([
        svgs['→'](3),
        svgs['N'](2),
        svgs['⩲'](1),
        svgs['!'](0),
    ]);
    expect(shapes.every(shape => shape.below === undefined)).toBe(true);
    expect(current.annotations?.nags).toEqual([1, 14, 146, 40, 32]);
});

test('unknown NAGs use the existing PGN text with Lichess label fallback, without changing storage', () => {
    const current = node('e2e4', undefined, 'e4', [200]);
    expect(annotations(current)).toEqual([
        { orig: 'e4', brush: undefined, customSvg: undefined, label: { text: '$200', fill: 'purple' } },
    ]);
    expect(current.annotations?.nags).toEqual([200]);
});

test.each([
    ['+P@a3', 'a3'],
    ['a7a8q', 'a8'],
    ['e1e1', 'e1'],
    ['a2a3,a3h8', 'a3'],
])('move %s attaches its NAG to the primary destination %s', (move, dest) => {
    expect(annotations(node(move))[0].orig).toBe(dest);
});

test.each([
    ['a9i10', { width: 9, height: 10 }, 'i:'],
    ['a15p16', { width: 16, height: 16 }, 'p@'],
] as const)('move %s uses the full board dimensions', (move, dimensions, dest) => {
    expect(annotations(node(move), dimensions)[0].orig).toBe(dest);
});

test('root NAGs and unrecognized/out-of-board moves have no board badge', () => {
    for (const move of [undefined, '0000', 'a1i1', 'a1a17']) expect(annotations(node(move))).toEqual([]);
});

test('keeps existing custom SVGs and check-counter badges in their own stack slots', () => {
    const current = node('e1e2', '8/8/8/8/8/8/4K3/8', 'Ke2');
    const existing = { orig: 'e2' as const, customSvg: { html: '<circle/>', center: 'dest' as const } };
    const shapes = annotationShapes(
        current,
        undefined,
        { ...board, kingRoles: ['k-piece'], drawable: { checkCounters: { white: '2', black: '3' } } },
        [1],
        [existing],
    );
    expect(shapes[0].customSvg).toEqual({ html: svgs['!'](2) });
    expect(existing.customSvg).toEqual({ html: '<circle/>', center: 'dest' });
    const withCounter = annotationShapes(
        current,
        undefined,
        {
            ...board,
            kingRoles: ['k-piece'],
            drawable: { checkCounters: { white: '2', black: '3' } },
        },
        [1, 14, 146, 40],
    );
    expect(withCounter).toHaveLength(3);
    expect(withCounter[0].customSvg).toEqual({ html: svgs['N'](3) });
});

test('server visibility uses the same generated-advice filtering as the move list', () => {
    const current = node('e2e4', undefined, 'e4', [2, 146]);
    current.step.analysis = { s: { cp: -100 }, advice: { nag: 2 } } as any;
    expect(visibleNags(current, true)).toEqual([2, 146]);
    expect(visibleNags(current, false)).toEqual([146]);
    expect(current.annotations?.nags).toEqual([2, 146]);
});

let ffish: any;
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({ wasmBinary: readFileSync(resolve('node_modules/ffish-es6/ffish.wasm')), printErr: () => {} });
});

test.each([
    ['chess', '4k3/8/8/8/8/8/8/4K2R w K - 0 1', false, 'e1g1', 8, 'g1'],
    ['chess', '4k3/8/8/8/8/8/8/6KR w H - 0 1', true, 'g1h1', 8, 'g1'],
    ['chess', '4k3/8/8/8/8/8/8/1RK5 w B - 0 1', true, 'c1b1', 8, 'c1'],
    ['chess', '4k2r/8/8/8/8/8/8/4K3 b k - 0 1', false, 'e8g8', 8, 'g8'],
    ['capablanca', '5k4/10/10/10/10/10/10/5K3R w K - 0 1', false, 'f1i1', 10, 'i1'],
] as const)(
    'engine-resolved %s castling %s lands on the actual royal square',
    (variant, fen, chess960, move, width, dest) => {
        const engine = new ffish.Board(variant, fen, chess960);
        try {
            expect(engine.legalMoves().split(' ')).toContain(move);
            const san = engine.sanMove(move);
            expect(san).toMatch(/^O-O/);
            engine.push(move);
            const current = node(move, engine.fen(), san);
            current.step.sanSAN = san;
            current.step.san = 'variant display notation';
            const parent = node(undefined, fen);
            parent.step.turnColor = fen.split(' ')[1] === 'w' ? 'white' : 'black';
            expect(
                annotationShapes(current, parent, { dimensions: { width, height: 8 }, kingRoles: ['k-piece'] }, [1])[0]
                    .orig,
            ).toBe(dest);
        } finally {
            engine.delete();
        }
    },
);

test('castling placement uses configured nonstandard royal roles', () => {
    const parent = node(undefined, '4l3/8/8/8/8/8/8/4L2R');
    parent.step.turnColor = 'white';
    const current = node('e1h1', '4l3/8/8/8/8/8/8/5RL1', 'O-O');
    expect(
        annotationShapes(current, parent, { dimensions: board.dimensions, kingRoles: ['l-piece'] }, [1])[0].orig,
    ).toBe('g1');
});
