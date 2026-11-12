import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, expect, test } from '@jest/globals';
import { read } from 'chessgroundx/fen';
import type { FairyStockfish } from 'ffish-es6';

import { premoveForVariant } from '../client/premove';
import { getAtaxxPoints, validFen } from '../client/chess';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

let ffish: FairyStockfish;
const names = ['flipello', 'flipello10', 'flipersi'] as const;

beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});
afterEach(() => names.forEach(unregisterCataloguedVariant));

function register(
    name: (typeof names)[number],
    source: 'user' | 'fairy-stockfish-builtin' = 'fairy-stockfish-builtin',
) {
    const board = new ffish.Board(name);
    const startFen = board.fen();
    board.delete();
    const size = name === 'flipello10' ? 10 : 8;
    registerCataloguedVariant({
        name,
        displayName: name,
        ini: '',
        source,
        fsfBuiltinVariant: name,
        baseVariant: name === 'flipello' ? 'flipersi' : name === 'flipello10' ? 'flipello' : '',
        clientVariant: 'chess',
        pieceFamilyOverride: 'ataxx',
        boardFamilyOverride: `standard${size}x${size}`,
        width: size,
        height: size,
        startFen,
        pieces: ['p'],
        kingRoles: [],
        pocketRoles: ['p'],
        captureToHand: false,
        rulesPass: name !== 'flipersi',
        betzaPieces: { p: '' },
    });
    return VARIANTS[name];
}

// Black cannot place; White can place on c1 after a forced pass.
function blocked(size: number) {
    return (
        [
            ...Array<string>(size - 2).fill('p'.repeat(size)),
            'pp1' + 'p'.repeat(size - 3),
            'Pp1' + 'p'.repeat(size - 3),
        ].join('/') + '[Pp] b - - 0 1'
    );
}

test.each(names)('%s accepts native reserves, remains kingless, and limits custom material', name => {
    const variant = register(name);
    expect(variant.pieceFamily).toBe('ataxx');
    expect(variant.ui.materialPoint).toBe('ataxx');
    expect(variant.colors).toEqual(VARIANTS.ataxx.colors);
    expect(getAtaxxPoints(variant.startFen.split(' ')[0])).toEqual(name === 'flipersi' ? [0, 0] : [2, 2]);
    const pieces = read('8/8/8/8/8/8/4P3/8', { width: 8, height: 8 }).pieces;
    expect(premoveForVariant(name, false, variant.board.dimensions)({ pieces }, 'e2', false)).toEqual([]);
    expect(variant.rules.pass).toBe(name !== 'flipersi');
    expect(validFen(variant, variant.startFen)).toBe(true);
    expect(validFen(variant, variant.startFen.replace('[', '[P'))).toBe(false);
    expect(validFen(variant, variant.startFen.replace('[', '[p'))).toBe(false);
    const untrusted = register(name, 'user');
    expect(untrusted.ui.materialPoint).toBeUndefined();
    expect(validFen(untrusted, untrusted.startFen)).toBe(false);
});

test.each(names)('%s placements flip discs and survive replay', name => {
    const variant = register(name);
    const board = new ffish.Board(name);
    try {
        const initial = board.fen();
        const opening = name === 'flipersi' ? ['P@d4', 'P@e4', 'P@d5', 'P@e5'] : [];
        for (const move of opening) expect(board.push(move)).toBe(true);
        if (name === 'flipersi') expect(read(initial, variant.board.dimensions).pieces.size).toBe(0);
        const move = name === 'flipello10' ? 'P@f4' : name === 'flipello' ? 'P@e3' : board.legalMoves().split(' ')[0];
        const before = read(board.fen(), variant.board.dimensions).pieces;
        expect(board.push(move)).toBe(true);
        const after = read(board.fen(), variant.board.dimensions).pieces;
        expect(after.size).toBe(before.size + 1);
        expect(getAtaxxPoints(board.fen().split(' ')[0])).toEqual([
            [...after.values()].filter(piece => piece.color === 'white').length,
            [...after.values()].filter(piece => piece.color === 'black').length,
        ]);
        expect([...before].some(([key, piece]) => after.get(key)?.color !== piece.color)).toBe(true);
        expect(validFen(variant, board.fen())).toBe(true);
        const final = board.fen();
        board.pop();
        expect(board.push(move)).toBe(true);
        expect(board.fen()).toBe(final);
    } finally {
        board.delete();
    }
});

test.each(names)('%s handles blocked players according to its pass rule', name => {
    register(name);
    const board = new ffish.Board(name, blocked(name === 'flipello10' ? 10 : 8));
    try {
        if (name === 'flipersi') {
            expect(board.legalMoves()).toBe('');
            expect(board.result()).toBe('0-1');
        } else {
            expect(board.legalMoves()).toBe('b1b1');
            expect(board.push('b1b1')).toBe(true);
            expect(board.legalMoves()).toBe('P@c1');
            expect(board.push('P@c1')).toBe(true);
            expect(board.result()).toBe('*');
            expect(board.push('d1d1')).toBe(true);
            expect(board.push('a1a1')).toBe(true);
            expect(board.result()).toBe('0-1');
        }
    } finally {
        board.delete();
    }
});
