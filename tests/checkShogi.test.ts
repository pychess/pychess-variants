import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, expect, test } from '@jest/globals';
import type { FairyStockfish } from 'ffish-es6';

import { validFen } from '../client/chess';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

let ffish: FairyStockfish;
const initial = '4k4/9/9/9/9/9/2p6/2R6/4K4[] w - - 0 1';
const moves = ['c2c3', 'e9f9', 'P@a4', 'f9g9', 'c3c7+', 'g9h9', 'c7h7'];
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});
afterEach(() => unregisterCataloguedVariant('checkshogi'));

test('Check Shogi defaults omitted counters to 1+1 and uses the Shogi interface', () => {
    const board = new ffish.Board('checkshogi');
    try {
        const startFen = board.fen();
        expect(startFen.split(' ')[4]).toBe('1+1');
        registerCataloguedVariant({
            name: 'checkshogi',
            displayName: 'Check-Shogi',
            ini: '',
            source: 'fairy-stockfish-builtin',
            fsfBuiltinVariant: 'checkshogi',
            baseVariant: 'shogi',
            clientVariant: 'shogi',
            startFen,
            width: 9,
            height: 9,
            pieces: ['p', 'l', 'n', 's', 'g', 'b', 'r', 'k'],
            kingRoles: ['k'],
            pocketRoles: ['p', 'l', 'n', 's', 'g', 'b', 'r'],
            captureToHand: true,
            promotionType: 'shogi',
            promotionRoles: ['p', 'l', 'n', 's', 'b', 'r'],
            promotionOrder: ['+'],
            showPromoted: true,
            boardFamilyOverride: 'shogi9x9',
            pieceFamilyOverride: 'shogi',
            showCheckCounters: true,
        });
        const variant = VARIANTS.checkshogi;
        expect(variant.ui.showCheckCounters).toBe(true);
        expect(variant.boardFamily).toBe('shogi9x9');
        expect(variant.pieceFamily).toBe('shogi');
        expect(variant.rules.defaultTimeControl).toBe('byoyomi');
        expect(variant.pocket?.captureToHand).toBe(true);
        expect(variant.promotion.type).toBe('shogi');
        expect(validFen(variant, startFen)).toBe(true);
    } finally {
        board.delete();
    }
});

test('A first check ends Check Shogi even when ordinary Shogi has king escapes', () => {
    const board = new ffish.Board('checkshogi', initial);
    const shogi = new ffish.Board('shogi', initial);
    try {
        for (const [ply, move] of moves.entries()) {
            expect(board.push(move)).toBe(true);
            expect(shogi.push(move)).toBe(true);
            expect(board.result()).toBe(ply === moves.length - 1 ? '1-0' : '*');
        }
        const final = board.fen();
        expect(final.split(' ')[4]).toBe('0+1');
        expect(board.legalMoves()).toBe('');
        expect(shogi.legalMoves().length).toBeGreaterThan(0);
        board.pop();
        expect(board.result()).toBe('*');
        expect(board.fen().split(' ')[4]).toBe('1+1');
        expect(board.push(moves[moves.length - 1])).toBe(true);
        expect(board.fen()).toBe(final);
    } finally {
        board.delete();
        shogi.delete();
    }
});

test.each([
    ['4k4/9/9/9/9/9/9/9/4K4[P] w - - 0 1', 'P@e8', '0+1', '1-0'],
    ['4k4/9/9/9/9/9/9/9/4K4[p] b - - 0 1', 'P@e2', '1+0', '0-1'],
])('A checking drop wins from %s', (fen, move, counter, result) => {
    const board = new ffish.Board('checkshogi', fen);
    try {
        expect(board.push(move)).toBe(true);
        expect(board.fen().split(' ')[4]).toBe(counter);
        expect(board.result()).toBe(result);
    } finally {
        board.delete();
    }
});
