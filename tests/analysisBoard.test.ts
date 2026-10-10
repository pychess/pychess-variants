import { beforeEach, expect, jest, test } from '@jest/globals';
import type { MsgBoard } from '../client/messages';

jest.unstable_mockModule('chessgroundx', () => ({ Chessground: jest.fn() }));
jest.unstable_mockModule('../client/movelist', () => ({
    updateMovelist: jest.fn(),
    createMovelistButtons: jest.fn(),
    selectMove: jest.fn(),
    selectMainlineMove: jest.fn(),
}));
const { AnalysisController } = await import('../client/analysis/analysisCtrl');

const root = { fen: '8/8/8/8/8/8/8/K6k w - - 0 1', turnColor: 'white', check: false };
function board(): MsgBoard {
    return {
        gameId: 'game1234',
        fen: '8/8/8/8/8/8/K7/7k b - - 1 1',
        steps: [root, { ...root, fen: '8/8/8/8/8/8/K7/7k b - - 1 1', turnColor: 'black', san: 'Ka2' }],
        lastMove: '',
        result: '1-0',
        status: 3,
    } as MsgBoard;
}

beforeEach(() => jest.clearAllMocks());

function controller() {
    return Object.assign(Object.create(AnalysisController.prototype), {
        gameId: 'game1234',
        analysisContext: { capabilities: { usesRoundSocket: true } },
        steps: [root],
        ply: 0,
        setDests: jest.fn(),
        initAnalysisTreeAtPly: jest.fn(),
        hasAnalysisTree: () => true,
        checkStatus: jest.fn(),
    }) as InstanceType<typeof AnalysisController>;
}

test('repeated round snapshots leave the loaded history and local tree intact', () => {
    const ctrl = controller();
    ctrl.onMsgBoard(board());
    const loadedSteps = ctrl.steps;
    expect(loadedSteps).toHaveLength(2);
    ctrl.onMsgBoard(board());
    expect(ctrl.steps).toBe(loadedSteps);
    expect(ctrl.initAnalysisTreeAtPly).toHaveBeenCalledTimes(1);
});

test('a changed round snapshot is still processed', () => {
    const ctrl = controller();
    ctrl.onMsgBoard(board());
    const changed = board();
    changed.result = '1/2-1/2';
    ctrl.onMsgBoard(changed);
    expect(ctrl.result).toBe('1/2-1/2');
    expect(ctrl.initAnalysisTreeAtPly).toHaveBeenCalledTimes(2);
});

test('compact finished history loads once and survives the repeated socket snapshot', () => {
    const ctrl = controller();
    const fen = '8/8/8/8/8/8/K7/7k b - - 1 1';
    const deleteBoard = jest.fn();
    Object.assign(ctrl, {
        ffish: {
            Board: class {
                sanMove() { return 'Ka2'; }
                push() { return true; }
                fen() { return fen; }
                isCheck() { return false; }
                delete = deleteBoard;
            },
        },
    });
    const snapshot = {
        ...board(),
        steps: [{ ...root }],
        history: {
            variant: 'chess', chess960: false, moves: ['a1a2'],
            showPromoted: false, countStarted: 0, usi: false,
        },
    } as MsgBoard;
    ctrl.onMsgBoard(snapshot);
    expect(ctrl.steps[1].fen).toBe(fen);
    expect(ctrl.steps[1].san).toBe('Ka2');
    expect(snapshot.steps).toHaveLength(1);
    const loadedSteps = ctrl.steps;
    ctrl.onMsgBoard(JSON.parse(JSON.stringify(snapshot)));
    expect(ctrl.steps).toBe(loadedSteps);
    expect(ctrl.initAnalysisTreeAtPly).toHaveBeenCalledTimes(1);
    expect(deleteBoard).toHaveBeenCalledTimes(1);
});
