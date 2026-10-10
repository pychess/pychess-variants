import { expect, jest, test } from '@jest/globals';
import type { Api } from 'chessgroundx/api';
import type { GameController as GameControllerType } from '../client/gameCtrl';

import { aliceBoardFen } from '../client/aliceBoard';

jest.unstable_mockModule('../client/chat', () => ({
    chatMessage: jest.fn(),
    replayingChat: jest.fn(),
}));

const { GameController } = await import('../client/gameCtrl');

test('moves the Alice check marker with the checked king when switching boards', () => {
    const fen = '4|k3/8/8/8/8/8/8/4K3 w - - 0 1';
    const mainSet = jest.fn();
    const splitSet = jest.fn();
    const redrawAll = jest.fn();

    const ctrl = Object.assign(Object.create(GameController.prototype), {
        mirrorBoard: false,
        fullfen: fen,
        variant: { name: 'alice' },
        aliceSplitBoards: true,
        chessground: {
            state: { check: ['e1'], orientation: 'white' },
            set: mainSet,
        },
        aliceSplitBoard: {
            state: { check: undefined },
            set: splitSet,
            redrawAll,
        } as unknown as Api,
        setDests: jest.fn(),
    }) as unknown as GameControllerType;

    const originalRequestAnimationFrame = window.requestAnimationFrame;
    window.requestAnimationFrame = jest.fn(() => 0);

    ctrl.switchAliceBoards();

    expect(ctrl.mirrorBoard).toBe(true);
    expect(mainSet).toHaveBeenCalledWith({ fen: aliceBoardFen(fen, 'b'), check: true });
    expect(splitSet).toHaveBeenCalledWith({
        fen: aliceBoardFen(fen, 'a'),
        orientation: 'white',
        check: true,
    });

    window.requestAnimationFrame = originalRequestAnimationFrame;
});
