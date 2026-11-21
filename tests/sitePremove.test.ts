import fs from 'node:fs';
import path from 'node:path';
import { beforeAll, describe, expect, test } from '@jest/globals';
import { writeBoard } from 'chessgroundx/fen';
import { premove } from 'chessgroundx/premove';
import type * as cg from 'chessgroundx/types';
import { allKeys, opposite, roleOf } from 'chessgroundx/util';
import type { FairyStockfish } from 'ffish-es6';

import { premoveForVariant, unregisterCataloguedPremove } from '../client/premove';
import { variantsIni } from '../client/variantsIni';

const dimensions: cg.BoardDimensions = { width: 9, height: 9 };
const roles: cg.Letter[] = ['k', 'p', 'n', 'r', 'l', 'a', 'c', 'g', 'y', 'f', 't', '+p', '+g', '+y', '+f', '+t'];
let ffish: FairyStockfish;

beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
    // Remove check restrictions so the engine exposes movement geometry alone.
    // The commoner retains the king's movement without making it royal.
    ffish.loadVariantConfig(`${variantsIni}\n[yokai-geometry:yokai]\nking = -\ncommoner = k\n`);
});

function board(letter: cg.Letter, color: cg.Color, key: cg.Key = 'e5'): cg.BoardState {
    return { pieces: new Map([[key, { role: roleOf(letter), color }]]) };
}

describe('Yokai site premoves', () => {
    test.each(roles)('%s matches engine quiet/capture geometry for both colors, including board edges', letter => {
        const generate = premoveForVariant('yokai', false, dimensions);
        const engine = new ffish.Board('yokai-geometry');
        try {
            for (const color of ['white', 'black'] as const) {
                for (const origin of ['e5', 'a1', 'i9'] as const) {
                    const state = board(letter, color, origin);
                    const position = () => `${writeBoard(state.pieces, dimensions)}[-] ${color[0]} - - 0 1`;
                    engine.setFen(position());
                    const destinations = new Set(
                        engine
                            .legalMoves()
                            .split(' ')
                            .filter(move => move.startsWith(origin))
                            .map(move => move.slice(2, 4)),
                    );
                    // Capture-only components need a target. Test each square
                    // independently so no other piece blocks its sliding ray.
                    for (const target of allKeys(dimensions)) {
                        if (target === origin) continue;
                        state.pieces.set(target, { role: 'p-piece', color: opposite(color) });
                        engine.setFen(position());
                        if (
                            engine
                                .legalMoves()
                                .split(' ')
                                .some(move => move.startsWith(origin + target))
                        ) {
                            destinations.add(target);
                        }
                        state.pieces.delete(target);
                    }
                    expect({ color, origin, destinations: new Set(generate(state, origin, true)) }).toEqual({
                        color,
                        origin,
                        destinations,
                    });
                }
            }
        } finally {
            engine.delete();
        }
    });

    test('Kitsune offers both quiet rook and capture bishop destinations regardless of current occupancy', () => {
        const state = board('f', 'white');
        state.pieces.set('e6', { role: 'p-piece', color: 'white' });
        state.pieces.set('f6', { role: 'p-piece', color: 'black' });
        const destinations = premoveForVariant('yokai', false, dimensions)(state, 'e5', false);
        expect(destinations).toHaveLength(32);
        expect(destinations).toEqual(expect.arrayContaining(['e6', 'e9', 'i9', 'a1', 'e1', 'a5']));
        expect(destinations).not.toContain('f7');
    });

    test('catalogued cleanup does not remove a site definition', () => {
        const generate = () => premoveForVariant('yokai', false, dimensions)(board('n', 'white'), 'e5', false);
        const before = generate();
        unregisterCataloguedPremove('yokai');
        expect(generate()).toEqual(before);
        expect(new Set(before)).toEqual(new Set(['a5', 'b5', 'c5', 'd5', 'f5', 'g5', 'h5', 'i5']));
    });
});

test.each(['chess', 'shogi', 'cannonshogi', 'kyotoshogi'])('%s keeps chessgroundx premoves', variant => {
    for (const letter of ['k', 'p', 'r', '+p'] as const) {
        const state = board(letter, 'white');
        expect(premoveForVariant(variant, false, dimensions)(state, 'e5', true)).toEqual(
            premove(variant, false, dimensions)(state, 'e5', true),
        );
    }
});
