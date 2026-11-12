import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, expect, test } from '@jest/globals';
import type * as cg from 'chessgroundx/types';
import type { FairyStockfish } from 'ffish-es6';
import { read } from 'chessgroundx/fen';

import { premoveForVariant } from '../client/premove';
import { validFen } from '../client/chess';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS, PIECE_FAMILIES } from '../client/variants';
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
    const board = new ffish.Board('wolf');
    const startFen = board.fen();
    board.delete();
    registerCataloguedVariant({
        name: 'wolf',
        displayName: 'Wolf Chess',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'wolf',
        ini: '',
        baseVariant: '',
        clientVariant: 'chess',
        width: 8,
        height: 10,
        startFen,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 's', 'w', 'f', '+p'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p', 's'],
        promotionOrder: ['q', 'w', 'f', 'r', 'b', '+'],
        pieceFamilyOverride: 'wolf',
        betzaPieces: { w: 'RN', f: 'BN', n: 'NN', s: 'fKifmnD', '+p': 'NNQ', p: 'fmWfceFifmnD' },
    });
});
afterEach(() => unregisterCataloguedVariant('wolf'));

test('Wolf uses an 8-file, 10-rank board and its complete Alfaerie family', () => {
    expect(VARIANTS.wolf.board.dimensions).toEqual({ width: 8, height: 10 });
    expect(VARIANTS.wolf.pieceFamily).toBe('wolf');
    expect(PIECE_FAMILIES.wolf.pieceCSS).toEqual(['alfaerie']);
    expect(VARIANTS.wolf.pieceNames['+p']).toBe('elephant');
    expect(validFen(VARIANTS.wolf, VARIANTS.wolf.startFen)).toBe(true);
});

test.each(['w', 'f', 'n', 's', '+p'] as const)('%s has correct legal moves within its premove envelope', letter => {
    const fen = `7k/8/8/8/8/3${letter.toUpperCase()}4/8/8/8/7K w - - 0 1`;
    const board = new ffish.Board('wolf', fen);
    try {
        const state = read(fen, { width: 8, height: 10 });
        const premoves = premoveForVariant('wolf', false, { width: 8, height: 10 })(state, 'd5', false);
        const targets = board
            .legalMoves()
            .split(' ')
            .filter(m => m.startsWith('d5'))
            .map(m => m.slice(2).replace('10', ':'));
        expect(targets.length).toBeGreaterThan(0);
        for (const target of targets) expect(premoves).toContain(target);
        if (letter === 'n') expect(targets).toContain('f9');
        if (letter === '+p') expect(targets).toContain('h5');
    } finally {
        board.delete();
    }
});

test('All Wolf roles, including the elephant aliases, have both source and generated artwork', () => {
    const css = fs.readFileSync('static/piece/wolf/alfaerie.css', 'utf8');
    const generated = fs.readFileSync('static/piece-css/wolf/alfaerie.css', 'utf8');
    for (const color of ['white', 'black'])
        for (const role of ['k', 'q', 'r', 'b', 'p', 'w', 'f', 's', 'n', 'pp', 'e']) {
            expect(css).toContain(`piece.${role}-piece.${color}`);
            expect(generated).toContain(`piece.${role}-piece.${color}`);
        }
    expect(generated).not.toContain('invisible.svg');
    const pieces: cg.Pieces = read('+P6k/8/8/8/8/8/8/8/8/7K', { width: 8, height: 10 }).pieces;
    expect(pieces.get('a:')?.role).toBe('pp-piece');
});
