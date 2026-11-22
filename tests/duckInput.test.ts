import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import * as cg from 'chessgroundx/types';

import { GameController } from '../client/gameCtrl';
import { DuckInput } from '../client/input/duck';

describe('Duck move controls', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="undo"></div><button id="takeback"></button>';
    });

    test('shows Cancel piece move only during duck placement and temporarily hides takeback', () => {
        const piece: cg.Piece = { role: 'p-piece', color: 'white' };
        const processInput = jest.fn();
        const ctrl = {
            variant: { rules: { duck: true }, kingRoles: ['k-piece'] },
            legalMoves: jest.fn(() => ['a2a3,a3b3']),
            chessground: {
                state: { boardState: { pieces: new Map<cg.Key, cg.Piece>([['a3', piece]]) } },
                set: jest.fn(),
                selectSquare: jest.fn(),
            },
            processInput,
            undo: jest.fn(),
            onDuckInputStateChange: (active: boolean) => {
                (document.getElementById('takeback') as HTMLElement).hidden = active;
            },
        } as unknown as GameController;
        const input = new DuckInput(ctrl);

        const meta: cg.MoveMetadata = { premove: true };
        input.start(piece, 'a2', 'a3', meta);

        expect(input.inputState).toBe('move');
        expect(meta.premove).toBe(false);
        expect((document.getElementById('undo') as HTMLButtonElement).title).toBe('Cancel piece move');
        expect((document.getElementById('takeback') as HTMLElement).hidden).toBe(true);

        input.finish('b3');

        expect(input.inputState).toBeUndefined();
        expect(document.getElementById('undo')?.tagName).toBe('DIV');
        expect((document.getElementById('takeback') as HTMLElement).hidden).toBe(false);
        expect(processInput).toHaveBeenCalledWith(piece, 'a2', 'a3', { premove: false }, ',a3b3', 'duck');
    });
});
