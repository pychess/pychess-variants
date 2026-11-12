import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, expect, jest, test } from '@jest/globals';
import type * as cg from 'chessgroundx/types';
import type { FairyStockfish } from 'ffish-es6';

import { capturedRole, unpromotedRole } from '../client/chess';
import { GameController } from '../client/gameCtrl';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

let ffish: FairyStockfish;
const initialFen = '7k/6P1/8/8/8/8/K7/6r1[] w - - 0 1';

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
        name: 'loop',
        displayName: 'Loop Chess',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'loop',
        baseVariant: 'crazyhouse',
        ini: '',
        width: 8,
        height: 8,
        startFen: VARIANTS.crazyhouse.startFen,
        pieces: ['p', 'n', 'b', 'r', 'q', 'k'],
        kingRoles: ['k'],
        captureToHand: true,
        pocketRoles: ['p', 'n', 'b', 'r', 'q'],
        dropLoop: true,
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'n'],
        showPromoted: true,
    });
});

afterEach(() => {
    unregisterCataloguedVariant('loop-child-test');
    unregisterCataloguedVariant('loop');
});

test.each(['q', 'r', 'b', 'n'] as const)('Loop keeps a promoted %s through capture, drop and undo', role => {
    for (const variantName of ['loop', 'crazyhouse']) {
        const board = new ffish.Board(variantName, initialFen);
        try {
            expect(board.push(`g7g8${role}`)).toBe(true);
            const promotedFen = board.fen(true);
            expect(promotedFen).toContain(`${role.toUpperCase()}~`);
            expect(board.push('g1g8')).toBe(true);
            const pocketRole = variantName === 'loop' ? role : 'p';
            expect(board.pocket(false)).toBe(pocketRole);
            expect(
                capturedRole(VARIANTS[variantName], {
                    role: `${role}-piece`,
                    color: 'white',
                    promoted: true,
                }),
            ).toBe(`${pocketRole}-piece`);
            expect(board.push('a2a3')).toBe(true);
            expect(board.push(`${pocketRole.toUpperCase()}@e5`)).toBe(true);
            expect(board.pocket(false)).toBe('');
            board.pop();
            expect(board.pocket(false)).toBe(pocketRole);
            board.pop();
            board.pop();
            expect(board.fen(true)).toBe(promotedFen);
        } finally {
            board.delete();
        }
    }
});

test.each(['loop', 'crazyhouse'])('%s updates the local pocket correctly before server acknowledgement', name => {
    const captured: cg.Piece = { role: 'q-piece', color: 'white', promoted: true };
    const changePocket = jest.fn();
    const ctrl = Object.assign(Object.create(GameController.prototype), {
        variant: VARIANTS[name],
        mycolor: 'black',
        duck: { inputState: '' },
        arrowing: { inputState: '' },
        chessground: {
            state: {
                boardState: { pieces: new Map([['g8', { role: 'r-piece', color: 'black' }]]) },
                dom: { redraw: jest.fn() },
            },
            changePocket,
        },
        processInput: jest.fn(),
    }) as { onUserMove(orig: cg.Key, dest: cg.Key, meta: cg.MoveMetadata): void };
    ctrl.onUserMove('g1', 'g8', { captured });
    expect(changePocket).toHaveBeenCalledWith(
        {
            role: name === 'loop' ? 'q-piece' : 'p-piece',
            color: 'black',
        },
        1,
    );
    // Editing/demotion still refers to the original pawn, independent of capture rules.
    expect(unpromotedRole(VARIANTS[name], captured)).toBe('p-piece');
});

test.each([undefined, 'false', 'true'])('Loop derivatives inherit capture rules and respect dropLoop=%s', option => {
    registerCataloguedVariant({
        name: 'loop-child-test',
        displayName: 'Loop derivative',
        ini: `[loop-child-test:loop]\n${option === undefined ? '' : `dropLoop = ${option}`}`,
        baseVariant: 'loop',
        pocketRoles: ['p', 'n', 'b', 'r', 'q'],
        width: 8,
        height: 8,
        startFen: initialFen,
        pieces: ['p', 'n', 'b', 'r', 'q', 'k'],
        kingRoles: ['k'],
    });
    expect(VARIANTS['loop-child-test'].pocket?.dropLoop).toBe(option !== 'false');
});
