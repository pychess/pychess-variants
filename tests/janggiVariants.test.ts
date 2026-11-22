import fs from 'node:fs';
import path from 'node:path';
import { afterAll, beforeAll, expect, test } from '@jest/globals';
import type { FairyStockfish } from 'ffish-es6';
import { read } from 'chessgroundx/fen';

import { getJanggiPoints } from '../client/chess';
import { premoveForVariant } from '../client/premove';
import { result } from '../client/result';
import { updatePoint } from '../client/info';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

const names = ['janggi', 'janggitraditional', 'janggimodern', 'janggicasual'] as const;
const position = '9/4k4/9/p8/9/4P4/9/9/4K4/R8 w - - 0 1';
let ffish: FairyStockfish;
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
    for (const name of names.slice(1)) {
        registerCataloguedVariant({
            name, displayName: name, source: 'fairy-stockfish-builtin', fsfBuiltinVariant: name,
            ini: '', baseVariant: 'janggi', clientVariant: 'janggi',
            width: 9, height: 10, startFen: VARIANTS.janggi.startFen,
            pieces: ['k', 'a', 'c', 'r', 'b', 'n', 'p'], kingRoles: ['k'], promotionRoles: [],
            promotionOrder: [], promotionType: 'regular', rulesPass: true,
            pieceFamilyOverride: 'janggi', boardFamilyOverride: 'janggi9x10',
        });
    }
});
afterAll(() => names.slice(1).forEach(unregisterCataloguedVariant));

test.each(names)('%s uses Janggi boards, pieces, notation, setup and pass controls', name => {
    const variant = VARIANTS[name];
    expect(variant.boardFamily).toBe('janggi9x10');
    expect(variant.pieceFamily).toBe('janggi');
    expect(variant.notation).toBe(VARIANTS.janggi.notation);
    expect(variant.colors).toEqual({ first: 'Blue', second: 'Red' });
    expect(variant.rules).toMatchObject({ setup: true, pass: true, defaultTimeControl: 'byoyomi' });
    const counted = name === 'janggi' || name === 'janggimodern';
    expect(variant.ui.materialPoint).toBe(counted ? 'janggi' : undefined);
    expect(result(variant, 12, counted ? '0-1' : '1/2-1/2')).toBe(counted ? 'Point counting • Red won' : 'Draw');
    if (counted) {
        expect(result(variant, 13, '0-1')).toBe('Point counting • Red won');
        document.body.innerHTML = '<div id="misc-infow"></div><div id="misc-infob"></div>';
        updatePoint(variant, variant.startFen, document.getElementById('misc-infow')!, document.getElementById('misc-infob')!);
        expect(document.getElementById('misc-infow')!.textContent).toBe('72');
        expect(document.getElementById('misc-infob')!.textContent).toBe('73.5');
        expect(document.getElementById('misc-infow')!.classList).toContain('text-color-blue');
        expect(document.getElementById('misc-infob')!.classList).toContain('text-color-red');
    }
});

test.each(names)('%s uses its native bikjang and consecutive pass rules in WASM', name => {
    const board = new ffish.Board(name, position);
    const bikjang = name === 'janggi' || name === 'janggitraditional';
    const counted = name === 'janggi' || name === 'janggimodern';
    try {
        expect(board.push('e5d5')).toBe(true);
        expect(board.isBikjang()).toBe(bikjang);
        expect(board.legalMoves().split(' ').includes('a7a6')).toBe(!bikjang);
        expect(board.push('e9e9')).toBe(true);
        expect(board.isGameOver(false)).toBe(bikjang);
        board.pop();
        expect(board.push('e9d9')).toBe(true);
        expect(board.isGameOver(false)).toBe(false);
        board.pop();
        board.pop();
        expect(board.fen()).toBe(position);
        expect(board.push('e2e2')).toBe(true);
        expect(board.push('e9e9')).toBe(true);
        expect(board.isGameOver(false)).toBe(true);
        expect(board.result()).toBe(counted ? '1-0' : '1/2-1/2');
        expect(getJanggiPoints(board.fen().split(' ')[0])).toEqual([15, 3.5]);
    } finally {
        board.delete();
    }
});

test.each(names)('%s retains the Janggi premove geometry', name => {
    const board = new ffish.Board(name);
    try {
        const state = read(board.fen(), { width: 9, height: 10 });
        const premove = premoveForVariant(name, false, { width: 9, height: 10 });
        for (const [key, piece] of state.pieces) {
            if (piece.color !== 'white') continue;
            expect(premove(state, key, false)).toEqual(
                premoveForVariant('janggi', false, { width: 9, height: 10 })(state, key, false),
            );
        }
    } finally {
        board.delete();
    }
});
