import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, expect, jest, test } from '@jest/globals';
import { read } from 'chessgroundx/fen';
import type * as cg from 'chessgroundx/types';
import type { Api } from 'chessgroundx/api';
import type { FairyStockfish } from 'ffish-es6';

import { validFen } from '../client/chess';
import { GameController } from '../client/gameCtrl';
import { premoveForVariant } from '../client/premove';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

let ffish: FairyStockfish;
const dimensions = { width: 8, height: 8 };
const initial = '7p/7p/8/8/8/2Pp4/8/8 w - - 0 1';
const moves = ['c3d4', 'h7h6', 'd4e5', 'h6h5', 'e5f6', 'h5g4', 'f6g7', 'g4f3', 'g7h8'];
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});
beforeEach(() => {
    const board = new ffish.Board('breakthrough');
    const startFen = board.fen();
    board.delete();
    registerCataloguedVariant({
        name: 'breakthrough',
        displayName: 'Breakthrough',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'breakthrough',
        baseVariant: '',
        clientVariant: 'chess',
        startFen,
        width: 8,
        height: 8,
        pieces: ['p'],
        kingRoles: [],
        boardFamilyOverride: 'standard8x8',
        pieceFamilyOverride: 'standard',
        betzaPieces: { p: 'fmWfF' },
    });
});
afterEach(() => unregisterCataloguedVariant('breakthrough'));

test('Breakthrough uses standard chess boards and pawns without en passant or check rules', () => {
    const variant = VARIANTS.breakthrough;
    expect(variant.boardFamily).toBe('standard8x8');
    expect(variant.pieceFamily).toBe('standard');
    expect(variant.ui.boardMark).toBe('campmate');
    expect(VARIANTS.chess.ui.boardMark).toBe('');
    expect(variant.kingRoles).toEqual([]);
    expect(variant.rules.enPassant).toBe(false);
    expect(VARIANTS.chess.rules.enPassant).toBe(true);
    expect(variant.pocket).toBeUndefined();
    expect(variant.ui.materialPoint).toBeUndefined();
    expect(validFen(variant, variant.startFen)).toBe(true);
    const state = { pieces: new Map<cg.Key, cg.Piece>([['d4', { role: 'p-piece', color: 'white' }]]) };
    const premoves = premoveForVariant('breakthrough', false, dimensions);
    expect(new Set(premoves(state, 'd4', false))).toEqual(new Set(['c5', 'd5', 'e5']));
    state.pieces.set('d4', { role: 'p-piece', color: 'black' });
    expect(new Set(premoves(state, 'd4', false))).toEqual(new Set(['c3', 'd3', 'e3']));
});

test('A quiet diagonal move does not remove an adjacent enemy pawn', () => {
    const variant = VARIANTS.breakthrough;
    const pieces = read(initial, dimensions).pieces;
    const meta: cg.MoveMetadata = {};
    const setPieces = jest.fn();
    GameController.prototype.performEnPassant(
        meta,
        { role: 'p-piece', color: 'white' },
        'c3',
        'd4',
        pieces,
        { setPieces } as unknown as Api,
        variant,
        'white',
    );
    expect(setPieces).not.toHaveBeenCalled();
    expect(meta.captured).toBeUndefined();
    const board = new ffish.Board('breakthrough', initial);
    try {
        for (const [ply, move] of moves.entries()) {
            expect(board.push(move)).toBe(true);
            expect(board.result()).toBe(ply === moves.length - 1 ? '1-0' : '*');
        }
        const final = read(board.fen(), dimensions).pieces;
        expect(final.get('d3')).toEqual({ role: 'p-piece', color: 'black' });
        expect(final.get('h8')).toEqual({ role: 'p-piece', color: 'white' });
        expect(board.legalMoves()).toBe('');
        board.pop();
        expect(board.result()).toBe('*');
    } finally {
        board.delete();
    }
});

test.each([
    ['w', 'a7a8', '1-0'],
    ['w', 'a7b8', '1-0'],
    ['b', 'h2h1', '0-1'],
    ['b', 'h2g1', '0-1'],
])('Reaching the goal rank with %s %s wins without promotion', (side, move, result) => {
    const board = new ffish.Board('breakthrough', `8/P7/8/8/8/8/7p/8 ${side} - - 0 1`);
    try {
        expect(board.legalMoves().split(' ')).toContain(move);
        expect(board.push(move)).toBe(true);
        expect(board.result()).toBe(result);
        expect(read(board.fen(), dimensions).pieces.get(move.slice(2))?.role).toBe('p-piece');
    } finally {
        board.delete();
    }
});
