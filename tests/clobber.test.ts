import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, expect, test } from '@jest/globals';
import { read } from 'chessgroundx/fen';
import type * as cg from 'chessgroundx/types';
import type { FairyStockfish } from 'ffish-es6';

import { validFen, getAtaxxPoints, uci2cg } from '../client/chess';
import { premoveForVariant } from '../client/premove';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

const names = ['clobber', 'clobber10'] as const;
let ffish: FairyStockfish;
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});
afterEach(() => names.forEach(unregisterCataloguedVariant));

function register(name: (typeof names)[number]) {
    const board = new ffish.Board(name);
    const startFen = board.fen();
    board.delete();
    registerCataloguedVariant({
        name,
        displayName: name,
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: name,
        baseVariant: name === 'clobber10' ? 'clobber' : '',
        clientVariant: 'chess',
        width: name === 'clobber' ? 5 : 10,
        height: name === 'clobber' ? 6 : 10,
        startFen,
        pieces: ['p'],
        kingRoles: [],
        pieceFamilyOverride: 'ataxx',
        betzaPieces: { p: 'cW' },
        ...(name === 'clobber10' ? { boardFamilyOverride: 'standard10x10' } : {}),
    });
    return VARIANTS[name];
}

test.each(names)('%s uses discs and the correct board geometry without material scores', name => {
    const variant = register(name);
    expect(variant.pieceFamily).toBe('ataxx');
    expect(variant.board.dimensions).toEqual(name === 'clobber' ? { width: 5, height: 6 } : { width: 10, height: 10 });
    expect(variant.boardFamily).toBe(name === 'clobber' ? 'catalogued5x6' : 'standard10x10');
    expect(variant.kingRoles).toEqual([]);
    expect(variant.pocket).toBeUndefined();
    expect(variant.rules.pass).toBe(false);
    expect(variant.ui.materialPoint).toBeUndefined();
    expect(variant.colors).toEqual(VARIANTS.ataxx.colors);
    expect(validFen(variant, variant.startFen)).toBe(true);
    expect(getAtaxxPoints(variant.startFen.split(' ')[0])).toEqual(name === 'clobber' ? [15, 15] : [50, 50]);
    const pieces = new Map([['c3', { role: 'p-piece', color: 'white' }]] as const);
    const premoves = premoveForVariant(name, false, variant.board.dimensions);
    expect(new Set(premoves({ pieces }, 'c3', false))).toEqual(new Set(['b3', 'd3', 'c2', 'c4']));
});

test.each(names)('%s only permits orthogonal captures, including edge moves without promotion', name => {
    const variant = register(name);
    const board = new ffish.Board(name);
    try {
        const initial = board.fen();
        const before = read(initial, variant.board.dimensions).pieces;
        const moves = board.legalMoves().split(' ');
        for (const move of moves) {
            const cgMove = uci2cg(move);
            const from = cgMove.slice(0, 2) as cg.Key;
            const to = cgMove.slice(2, 4) as cg.Key;
            expect(cgMove.length).toBe(4);
            expect(
                Math.abs(from.charCodeAt(0) - to.charCodeAt(0)) + Math.abs(from.charCodeAt(1) - to.charCodeAt(1)),
            ).toBe(1);
            expect(before.get(to)?.color).toBe('black');
            expect(board.push(move)).toBe(true);
            const after = read(board.fen(), variant.board.dimensions).pieces;
            expect(after.size).toBe(before.size - 1);
            expect(after.get(from)).toBeUndefined();
            expect(after.get(to)).toEqual({ role: 'p-piece', color: 'white' });
            board.pop();
            expect(board.fen()).toBe(initial);
        }
    } finally {
        board.delete();
    }
});

test.each(names)('%s loses when blocked even with more discs remaining', name => {
    register(name);
    const width = name === 'clobber' ? 5 : 10,
        height = name === 'clobber' ? 6 : 10;
    const fen =
        [
            'p' + (width - 1),
            ...Array<string>(height - 3).fill(String(width)),
            '2p' + (width - 3),
            'Pp' + (width - 2),
        ].join('/') + ' w - - 0 1';
    const board = new ffish.Board(name, fen);
    try {
        expect(board.legalMoves()).toBe('a1b1');
        expect(board.push('a1b1')).toBe(true);
        expect(board.legalMoves()).toBe('');
        expect(board.result()).toBe('1-0');
        expect(getAtaxxPoints(board.fen().split(' ')[0])).toEqual([1, 2]);
    } finally {
        board.delete();
    }
});
