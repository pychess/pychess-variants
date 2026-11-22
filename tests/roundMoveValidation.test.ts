import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { MsgMove } from '../client/messages';
import { pendingMoveStorageKey } from '../client/pendingMove';

type MethodMap = Record<string, (...args: any[]) => any>;
type SentMessage = { type: string; [key: string]: unknown };

jest.unstable_mockModule('chessgroundx', () => ({
    Chessground: jest.fn(),
}));

const { RoundController } = await import('../client/roundCtrl');
const roundProto = RoundController.prototype as unknown as MethodMap;

function callRoundMethod(ctx: Record<string, unknown>, name: string, ...args: unknown[]): unknown {
    return roundProto[name].call(ctx, ...args);
}

beforeEach(() => {
    localStorage.clear();
});

describe('round move validation', () => {
    test('rejects stale move only after clock calculation, then requests board sync', () => {
        const callOrder: string[] = [];
        const sent: SentMessage[] = [];
        const persistPendingMove = jest.fn();

        const ctrl = {
            gameId: 'game-stale',
            clearDialog: jest.fn(),
            corr: false,
            flipped: () => false,
            base: 5,
            ply: 12,
            clocks: [
                { duration: 180000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
                {
                    duration: 179500,
                    pause: jest.fn(() => callOrder.push('pause')),
                    setTime: jest.fn(),
                    start: jest.fn(),
                },
            ],
            mycolor: 'white',
            berserked: { wberserk: false, bberserk: false },
            inc: 2,
            byoyomi: false,
            preaction: false,
            clocktimes: [180000, 179500],
            ffishBoard: {
                legalMoves: jest.fn(() => {
                    callOrder.push('legalMoves');
                    return 'a2a3 b2b3';
                }),
            },
            clearLocalMoveQueueState: jest.fn(),
            doSend: jest.fn((msg: SentMessage) => sent.push(msg)),
            persistPendingMove,
            clockOn: false,
            oppcolor: 'black',
        } as unknown as Record<string, unknown>;

        callRoundMethod(ctrl, 'doSendMove', 'f7f8k');

        expect(callOrder).toEqual(['pause', 'legalMoves']);
        expect(ctrl.clearLocalMoveQueueState).toHaveBeenCalledTimes(1);
        expect(persistPendingMove).not.toHaveBeenCalled();
        expect(sent).toEqual([{ type: 'board', gameId: 'game-stale' }]);
    });

    test('rejects exact atomic960 stale king move from post-castle white-to-move position', () => {
        const sent: SentMessage[] = [];
        const persistPendingMove = jest.fn();

        const ctrl = {
            gameId: 'izcDGthV',
            clearDialog: jest.fn(),
            corr: false,
            flipped: () => false,
            base: 5,
            // Local client is still on Black's decision point before move 20.
            ply: 19,
            clocks: [
                { duration: 181000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
                { duration: 179000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
            ],
            mycolor: 'black',
            berserked: { wberserk: false, bberserk: false },
            inc: 3,
            byoyomi: false,
            preaction: false,
            clocktimes: [181000, 179000],
            ffishBoard: {
                // Authoritative local rules engine is already on the logged post-castle
                // white-to-move FEN, where c8b7 is no longer legal.
                legalMoves: jest.fn(
                    () =>
                        'a2a3 c2c3 d2d3 f2f3 h2h3 b3b4 a2a4 c2c4 d2d4 f2f4 h2h4 g3f1 g3h1 g3e2 g3e4 g3f5 g3h5 b1a1 b1b2 g1f1 g1h1 e8e2 e8e3 e8e4 e8b5 e8e5 e8h5 e8c6 e8e6 e8g6 e8d7 e8e7 e8f7 e8d8 e8f8 e8g8 e8h8 c1d1 c1b2 c1b1',
                ),
            },
            clearLocalMoveQueueState: jest.fn(),
            doSend: jest.fn((msg: SentMessage) => sent.push(msg)),
            persistPendingMove,
            clockOn: false,
            oppcolor: 'white',
        } as unknown as Record<string, unknown>;

        callRoundMethod(ctrl, 'doSendMove', 'c8b7');

        expect(ctrl.clearLocalMoveQueueState).toHaveBeenCalledTimes(1);
        expect(persistPendingMove).not.toHaveBeenCalled();
        expect(sent).toEqual([{ type: 'board', gameId: 'izcDGthV' }]);
    });

    test('takeback-style local queue clear removes stale premove state and blocks stale resend', () => {
        const gameId = 'game-antichess';
        const key = pendingMoveStorageKey(gameId);
        const pending: MsgMove = {
            type: 'move',
            gameId,
            move: 'f7f8k',
            clocks: [12000, 11000],
            ply: 32,
        };
        localStorage.setItem(key, JSON.stringify(pending));

        const sent: SentMessage[] = [];
        const persistPendingMove = jest.fn();
        const cancelPremove = jest.fn();
        const unsetPremove = jest.fn();

        const ctrl = {
            gameId,
            lastMaybeSentMsgMove: pending,
            chessground: { cancelPremove },
            promotion: { dismiss: jest.fn() },
            unsetPremove,
            pendingMoveStorageKey: roundProto.pendingMoveStorageKey,
            clearPendingMoveCache: roundProto.clearPendingMoveCache,
            clearLocalMoveQueueState: roundProto.clearLocalMoveQueueState,
            clearDialog: jest.fn(),
            corr: false,
            flipped: () => false,
            base: 0,
            ply: 31,
            clocks: [
                { duration: 12000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
                { duration: 11000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
            ],
            mycolor: 'white',
            berserked: { wberserk: false, bberserk: false },
            inc: 3,
            byoyomi: false,
            preaction: false,
            clocktimes: [12000, 11000],
            ffishBoard: { legalMoves: jest.fn(() => 'a2a3 h2h3') },
            doSend: jest.fn((msg: SentMessage) => sent.push(msg)),
            persistPendingMove,
            clockOn: false,
            oppcolor: 'black',
        } as unknown as Record<string, unknown>;

        // takeback and board-takeback paths both use this helper to invalidate local queued move intent.
        callRoundMethod(ctrl, 'clearLocalMoveQueueState');

        expect(cancelPremove).toHaveBeenCalledTimes(1);
        expect(unsetPremove).toHaveBeenCalledTimes(1);
        expect((ctrl.promotion as { dismiss: ReturnType<typeof jest.fn> }).dismiss).toHaveBeenCalledTimes(1);
        expect(ctrl.lastMaybeSentMsgMove).toBeUndefined();
        expect(localStorage.getItem(key)).toBeNull();

        callRoundMethod(ctrl, 'doSendMove', 'f7f8k');

        expect(sent).toEqual([{ type: 'board', gameId }]);
        expect(sent.some(msg => msg.type === 'move')).toBe(false);
        expect(persistPendingMove).not.toHaveBeenCalled();
    });

    test('sends current board positionId with move payload', () => {
        const sent: SentMessage[] = [];
        const persistPendingMove = jest.fn();
        const onMoveSubmitted = jest.fn();

        const ctrl = {
            gameId: 'game-position',
            positionId: 'pos-19',
            clearDialog: jest.fn(),
            corr: false,
            flipped: () => false,
            base: 5,
            ply: 19,
            clocks: [
                { duration: 181000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
                { duration: 179000, pause: jest.fn(), setTime: jest.fn(), start: jest.fn() },
            ],
            mycolor: 'white',
            berserked: { wberserk: false, bberserk: false },
            inc: 3,
            byoyomi: false,
            preaction: false,
            clocktimes: [181000, 179000],
            ffishBoard: { legalMoves: jest.fn(() => 'e2e4') },
            clearLocalMoveQueueState: jest.fn(),
            doSend: jest.fn((msg: SentMessage) => sent.push(msg)),
            persistPendingMove,
            clockOn: false,
            oppcolor: 'black',
            ongoingRoundGames: { onMoveSubmitted },
        } as unknown as Record<string, unknown>;

        callRoundMethod(ctrl, 'doSendMove', 'e2e4');

        expect(persistPendingMove).toHaveBeenCalledWith({
            type: 'move',
            gameId: 'game-position',
            move: 'e2e4',
            clocks: [179000, 181000],
            ply: 20,
            positionId: 'pos-19',
        });
        expect(sent).toEqual([
            {
                type: 'move',
                gameId: 'game-position',
                move: 'e2e4',
                clocks: [179000, 181000],
                ply: 20,
                positionId: 'pos-19',
            },
        ]);
        expect(onMoveSubmitted).toHaveBeenCalledWith(20);
    });
});
