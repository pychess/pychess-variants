import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, expect, test } from '@jest/globals';
import type { FairyStockfish } from 'ffish-es6';

import { getCounting, validFen } from '../client/chess';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

let ffish: FairyStockfish;
const initial = '4k3/8/8/P7/8/8/3R4/4K3 w - - 0 1';
const moves = ['a5a6m', 'e8f8', 'd2d3', 'f8g8', 'd3g3'];
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});
beforeEach(() => {
    const board = new ffish.Board('karouk');
    const startFen = board.fen();
    board.delete();
    registerCataloguedVariant({
        name: 'karouk',
        displayName: 'Kar Ouk',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'karouk',
        baseVariant: 'cambodian',
        clientVariant: 'cambodian',
        startFen,
        width: 8,
        height: 8,
        pieces: ['p', 'r', 'n', 's', 'm', 'k'],
        kingRoles: ['k'],
        boardFamilyOverride: 'makruk8x8',
        pieceFamilyOverride: 'makruk',
        promotionRoles: ['p'],
        promotionOrder: ['m'],
        showPromoted: true,
        showCheckCounters: true,
    });
});
afterEach(() => unregisterCataloguedVariant('karouk'));

test('Kar Ouk uses Cambodian pieces, promotion, automatic counting, and first-check badges', () => {
    const variant = VARIANTS.karouk;
    expect(variant.boardFamily).toBe('makruk8x8');
    expect(variant.pieceFamily).toBe('makruk');
    expect(variant.ui.counting).toBe('automatic');
    expect(VARIANTS.cambodian.ui.counting).toBe('makruk');
    expect(variant.ui.showCheckCounters).toBe(true);
    expect(variant.startFen.split(' ')[4]).toBe('1+1');
    expect(validFen(variant, variant.startFen)).toBe(true);
    expect(variant.promotion.order).toEqual(['m']);
});

test('The king and met retain their Cambodian opening leaps', () => {
    const board = new ffish.Board('karouk');
    try {
        for (const move of ['e3e4', 'd6d5', 'e1e3', 'e8g7', 'd1b2']) expect(board.push(move)).toBe(true);
        expect(board.fen().split(' ')[2]).toBe('d');
        expect(board.result()).toBe('*');
    } finally {
        board.delete();
    }
});

test('Promotion works and the first check wins before checkmate', () => {
    const board = new ffish.Board('karouk', initial),
        cambodian = new ffish.Board('cambodian', initial);
    try {
        for (const [ply, move] of moves.entries()) {
            expect(board.push(move)).toBe(true);
            expect(cambodian.push(move)).toBe(true);
            expect(board.result()).toBe(ply === moves.length - 1 ? '1-0' : '*');
        }
        expect(board.fen(true).split(' ')[4]).toBe('0+1');
        expect(board.fen(true)).toContain('M~');
        expect(cambodian.legalMoves().length).toBeGreaterThan(0);
        board.pop();
        expect(board.fen().split(' ')[4]).toBe('1+1');
    } finally {
        board.delete();
        cambodian.delete();
    }
});

test('A check counter does not displace the Cambodian draw-count ply', () => {
    expect(getCounting('4k3/8/8/8/8/8/3R4/4K3 w - 30 1+1 30 16')).toEqual([30, 30, 'w', 'piece']);
    expect(getCounting('4k3/8/8/8/8/8/3R4/4K3 w - 30 30 16')).toEqual([30, 30, 'w', 'piece']);
    const board = new ffish.Board('karouk', '4k3/8/8/8/8/8/3R4/4K3 w - 30 1+1 30 16');
    try {
        expect(board.push('d2d3')).toBe(true);
        expect(board.result(true)).toBe('1/2-1/2');
    } finally {
        board.delete();
    }
});
