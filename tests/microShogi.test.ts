import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, expect, test } from '@jest/globals';
import { read } from 'chessgroundx/fen';
import type * as cg from 'chessgroundx/types';
import { roleOf } from 'chessgroundx/util';
import type { FairyStockfish } from 'ffish-es6';

import { premoveForVariant } from '../client/premove';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

const dimensions = { width: 4, height: 5 };
let ffish: FairyStockfish;

beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});

beforeEach(() => {
    registerCataloguedVariant({
        name: 'micro',
        displayName: 'Micro Shogi',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'micro',
        baseVariant: 'kyotoshogi',
        clientVariant: 'kyotoshogi',
        boardFamilyOverride: 'shogi4x5',
        pieceFamilyOverride: 'microshogi',
        width: 4,
        height: 5,
        startFen: 'kb+r+l/p3/4/3P/+L+RBK[-] w 0 1',
        pieces: ['p', 'l', 'b', 'r', 'k'],
        kingRoles: ['k'],
        pocketRoles: ['p', 'l', 'b', 'r'],
        captureToHand: true,
        promotionType: 'shogi',
        promotionRoles: ['p', 'l', 'b', 'r'],
        promotionOrder: ['+', ''],
        showPromoted: true,
        betzaPieces: { '+p': 'fN', '+l': 'FfW', '+b': 'WfF', '+r': 'WfF' },
    });
});

afterEach(() => unregisterCataloguedVariant('micro'));

function position(letter: string, dest: cg.Key, capture: boolean): string {
    const pieces = new Map<string, string>([
        ['a5', 'k'],
        ['d1', 'K'],
        ['b2', letter.toUpperCase()],
    ]);
    if (capture) pieces.set(dest, 'p');
    const ranks: string[] = [];
    for (let rank = 5; rank >= 1; rank--) {
        let row = '',
            empty = 0;
        for (const file of 'abcd') {
            const piece = pieces.get(file + rank);
            if (!piece) empty++;
            else {
                if (empty) row += empty;
                empty = 0;
                row += piece;
            }
        }
        if (empty) row += empty;
        ranks.push(row);
    }
    return ranks.join('/') + '[] w - - 0 1';
}

test.each([
    ['p', 'b3'],
    ['+p', 'a4'],
    ['l', 'b3'],
    ['+l', 'c3'],
    ['b', 'c3'],
    ['+b', 'b3'],
    ['r', 'b3'],
    ['+r', 'b3'],
] as const)('%s flips only on capture', (letter, dest) => {
    for (const capture of [false, true]) {
        const fen = position(letter, dest, capture);
        const board = new ffish.Board('micro', fen);
        try {
            const suffix = capture ? (letter.startsWith('+') ? '-' : '+') : '';
            const move = 'b2' + dest + suffix;
            expect(board.legalMoves().split(' ')).toContain(move);
            const initial = board.fen(true);
            expect(board.push(move)).toBe(true);
            const expected = capture ? (letter.startsWith('+') ? letter.slice(1) : '+' + letter) : letter;
            expect(read(board.fen(true), dimensions).pieces.get(dest)?.role).toBe(roleOf(expected as cg.Letter));
            board.pop();
            expect(board.fen(true)).toBe(initial);
        } finally {
            board.delete();
        }
    }
});

test.each(['p', 'l', 'b', 'r'] as const)('a captured %s can be dropped with either face up', letter => {
    const board = new ffish.Board('micro', 'k3/4/4/4/3K[PLBR] w - - 0 1');
    try {
        for (const promoted of [false, true]) {
            const move = (promoted ? '+' : '') + letter.toUpperCase() + '@b2';
            expect(board.legalMoves().split(' ')).toContain(move);
            expect(board.push(move)).toBe(true);
            expect(read(board.fen(true), dimensions).pieces.get('b2')?.role).toBe(
                roleOf(((promoted ? '+' : '') + letter) as cg.Letter),
            );
            board.pop();
        }
    } finally {
        board.delete();
    }
});

test.each([
    ['+p', ['a5', 'c5'], ['a1', 'c1']],
    ['+l', ['a2', 'c2', 'a4', 'b4', 'c4'], ['a2', 'b2', 'c2', 'a4', 'c4']],
    ['+b', ['a3', 'c3', 'b2', 'b4', 'a4', 'c4'], ['a3', 'c3', 'b2', 'b4', 'a2', 'c2']],
    ['+r', ['a3', 'c3', 'b2', 'b4', 'a4', 'c4'], ['a3', 'c3', 'b2', 'b4', 'a2', 'c2']],
] as const)('%s premoves use the Micro reverse face', (letter, white, black) => {
    const moves = premoveForVariant('micro', false, dimensions);
    for (const [color, expected] of [
        ['white', white],
        ['black', black],
    ] as const) {
        const state = { pieces: new Map<cg.Key, cg.Piece>([['b3', { role: roleOf(letter), color }]]) };
        expect(new Set(moves(state, 'b3', false))).toEqual(new Set(expected));
    }
    const pawn = { pieces: new Map<cg.Key, cg.Piece>([['b3', { role: 'p-piece', color: 'white' }]]) };
    expect(moves(pawn, 'b3', false)).toEqual(['b4']);
});

test('Micro uses a rectangular Shogi board and offers all three complete piece styles', () => {
    expect(VARIANTS.micro.board.dimensions).toEqual(dimensions);
    expect(VARIANTS.micro.boardFamily).toBe('shogi4x5');
    expect(VARIANTS.micro.pieceFamily).toBe('microshogi');
    expect(VARIANTS.micro.piece.pieceCSS).toEqual(['kanji', 'firi', 'disguised']);
});
