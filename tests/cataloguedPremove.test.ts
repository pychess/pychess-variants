import { afterEach, describe, expect, test } from '@jest/globals';

import { createBetzaPremove } from '@pychess/betza';
import { premove } from 'chessgroundx/premove';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { premoveForVariant, registerCataloguedPremove, unregisterCataloguedPremove } from '../client/premove';

const dimensions: cg.BoardDimensions = { width: 8, height: 8 };

function board(...pieces: [cg.Key, cg.Letter, cg.Color][]): cg.BoardState {
    return {
        pieces: new Map(pieces.map(([key, letter, color]) => [key, { role: util.roleOf(letter), color }])),
    };
}

describe('catalogued variant premoves', () => {
    afterEach(() => unregisterCataloguedPremove('betza-test'));

    test('site variants continue to use chessgroundx premoves unchanged', () => {
        const state = board(['e1', 'k', 'white'], ['a1', 'r', 'white'], ['h1', 'r', 'white']);
        const expected = premove('chess', false, dimensions)(state, 'e1', true);
        const actual = premoveForVariant('chess', false, dimensions)(state, 'e1', true);
        expect(actual).toEqual(expected);
    });

    test('custom pieces use full Betza geometry and ignore current blockers', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:fRffN',
        });
        const state = board(['d4', 'z', 'white'], ['d5', 'p', 'white']);
        const destinations = new Set(premoveForVariant('betza-test', false, dimensions)(state, 'd4', false));

        expect(destinations).toEqual(new Set(['d5', 'd6', 'd7', 'd8', 'c6', 'e6']));
    });

    test('catalogued Fairy-Stockfish built-in pieces use server-resolved Betza movement', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: 'capablanca',
            ini: '',
            betzaPieces: { j: 'BN' },
        });
        const state = board(['d4', 'j', 'white']);
        const destinations = premoveForVariant('betza-test', false, dimensions)(state, 'd4', false);
        const expected = createBetzaPremove('BN')({ origin: [3, 3], color: 'white', board: dimensions }).map(
            position => util.pos2key([position[0], position[1]]),
        );

        expect(new Set(destinations)).toEqual(new Set(expected));
    });

    test('clientVariant controls fallback without changing engine baseVariant', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: '',
            clientVariant: 'shatranj',
            ini: '',
            betzaPieces: { b: 'B' },
        });

        const pawnState = board(['e2', 'p', 'white']);
        const pawnDestinations = premoveForVariant('betza-test', false, dimensions)(pawnState, 'e2', false);
        expect(new Set(pawnDestinations)).toEqual(new Set(['d3', 'e3', 'f3']));

        const bishopState = board(['d4', 'b', 'white']);
        const bishopDestinations = premoveForVariant('betza-test', false, dimensions)(bishopState, 'd4', false);
        const expectedBishop = createBetzaPremove('B')({ origin: [3, 3], color: 'white', board: dimensions }).map(
            position => util.pos2key([position[0], position[1]]),
        );
        expect(new Set(bishopDestinations)).toEqual(new Set(expectedBishop));
    });

    test('Okisaki Shogi overrides Shogi knight and lance premoves on a 10x10 board', () => {
        const largeBoard: cg.BoardDimensions = { width: 10, height: 10 };
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: '',
            clientVariant: 'shogi',
            ini: '',
            betzaPieces: { l: 'vR', n: 'N' },
        });
        const moves = premoveForVariant('betza-test', false, largeBoard);
        const knight = moves(board(['e5', 'n', 'white']), 'e5', false);
        expect(new Set(knight)).toEqual(new Set(['c4', 'c6', 'd3', 'd7', 'f3', 'f7', 'g4', 'g6']));
        const lance = moves(board(['e5', 'l', 'white']), 'e5', false);
        expect(new Set(lance)).toEqual(new Set(['e1', 'e2', 'e3', 'e4', 'e6', 'e7', 'e8', 'e9', 'e:']));
    });

    test('premoveVariant can refine the general client fallback', () => {
        const largeBoard: cg.BoardDimensions = { width: 10, height: 10 };
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: '',
            clientVariant: 'chess',
            premoveVariant: 'grand',
            ini: '',
        });

        const state = board(['e3', 'p', 'white']);
        const destinations = premoveForVariant('betza-test', false, largeBoard)(state, 'e3', false);
        expect(new Set(destinations)).toEqual(new Set(['d4', 'e4', 'f4', 'e5']));
    });

    test('Betza pawn overrides can remove or extend double-step premoves', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: '',
            clientVariant: 'chess',
            ini: '',
            betzaPieces: { p: 'fmWfceF' },
        });
        const noDouble = premoveForVariant('betza-test', false, dimensions)(board(['e2', 'p', 'white']), 'e2', false);
        expect(new Set(noDouble)).toEqual(new Set(['d3', 'e3', 'f3']));

        registerCataloguedPremove({
            name: 'betza-test',
            source: 'fairy-stockfish-builtin',
            baseVariant: '',
            clientVariant: 'chess',
            ini: '',
            betzaPieces: { p: 'fmWfceFfmnD' },
        });
        const torpedo = premoveForVariant('betza-test', false, dimensions)(board(['e4', 'p', 'white']), 'e4', false);
        expect(new Set(torpedo)).toEqual(new Set(['d5', 'e5', 'f5', 'e6']));
    });

    test('directional custom movement rotates for black', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:flN',
        });
        const state = board(['d4', 'z', 'black']);
        const destinations = premoveForVariant('betza-test', false, dimensions)(state, 'd4', false);

        expect(new Set(destinations)).toEqual(new Set(['f3']));
    });

    test('inherited pieces fall back to the base site variant', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:W',
        });
        const state = board(['e2', 'p', 'white']);
        const destinations = premoveForVariant('betza-test', false, dimensions)(state, 'e2', false);

        expect(new Set(destinations)).toEqual(new Set(['d3', 'e3', 'f3', 'e4']));
    });

    test('custom king geometry keeps castling-only base premoves', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\nking = k:W',
        });
        const state = board(['e1', 'k', 'white'], ['a1', 'r', 'white'], ['h1', 'r', 'white']);
        const destinations = new Set(premoveForVariant('betza-test', false, dimensions)(state, 'e1', true));

        expect(destinations).toEqual(new Set(['d1', 'f1', 'e2', 'a1', 'c1', 'g1', 'h1']));
    });

    test('custom king with a non-k role keeps castling-only base premoves', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\nking = g:W',
        });
        const state = board(['e1', 'g', 'white'], ['a1', 'r', 'white'], ['h1', 'r', 'white']);
        const destinations = new Set(premoveForVariant('betza-test', false, dimensions)(state, 'e1', true));

        expect(destinations).toEqual(new Set(['d1', 'f1', 'e2', 'a1', 'c1', 'g1', 'h1']));
    });

    test('fixed promotion mappings can reuse a custom target movement', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: ['[betza-test:chess]', 'customPiece1 = z:W', 'promotedPieceType = p:z'].join('\n'),
        });
        const state = board(['d4', '+p', 'white']);
        const destinations = premoveForVariant('betza-test', false, dimensions)(state, 'd4', false);

        expect(new Set(destinations)).toEqual(new Set(['c4', 'e4', 'd3', 'd5']));
    });

    test('unsupported syntax is handled by the same permissive full parser', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:mXR',
        });
        const state = board(['d4', 'z', 'white']);
        const destinations = premoveForVariant('betza-test', false, dimensions)(state, 'd4', false);

        expect(new Set(destinations)).toEqual(
            new Set(['a4', 'b4', 'c4', 'e4', 'f4', 'g4', 'h4', 'd1', 'd2', 'd3', 'd5', 'd6', 'd7', 'd8']),
        );
    });

    test('unknown-only custom notation creates an immobile premove piece', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:X',
        });
        const state = board(['d4', 'z', 'white']);

        expect(premoveForVariant('betza-test', false, dimensions)(state, 'd4', false)).toEqual([]);
    });

    test('empty custom notation creates an immobile premove piece', () => {
        registerCataloguedPremove({
            name: 'betza-test',
            source: 'user',
            baseVariant: 'chess',
            ini: '[betza-test:chess]\ncustomPiece1 = z:',
        });
        const state = board(['d4', 'z', 'white']);

        expect(premoveForVariant('betza-test', false, dimensions)(state, 'd4', false)).toEqual([]);
    });

    test('package-level compile API is available to other clients', () => {
        const premoveFunction = createBetzaPremove('N');
        expect(premoveFunction({ origin: [3, 3], color: 'white', board: dimensions })).toHaveLength(8);
    });
});
