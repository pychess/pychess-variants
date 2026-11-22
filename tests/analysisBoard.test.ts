import { beforeEach, expect, jest, test } from '@jest/globals';
import type { MsgBoard, Step } from '../client/messages';

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

test('server-analysis visibility refreshes variation arrows once per toggle during local analysis', () => {
    const ctrl = controller();
    const children = ['e2e4', 'd2d4'].map((move, index) => ({
        path: move,
        serverAnalysis: index === 1,
        children: [],
        step: { move, fen: '8/8/8/8/8/8/8/8', turnColor: 'black', check: false },
    }));
    const engineArrow = { orig: 'g1', dest: 'f3', brush: 'paleGreen' };
    const setAutoShapes = jest.fn();
    Object.assign(ctrl, {
        localAnalysis: true,
        showServerAnalysis: true,
        variationArrows: true,
        analysisContext: { capabilities: { positionEvaluation: true } },
        autoShapes: [[engineArrow]],
        tree: {
            analysisPath: '',
            getTreeNodeAtPath: () => ({ children }),
            getTreeMainChildPath: () => 'e2e4',
        },
        chessground: {
            state: { dimensions: { width: 8, height: 8 }, boardState: { pieces: new Map() }, turnColor: 'white' },
            setAutoShapes,
        },
    });
    ctrl.setAutoShapes();
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(3);

    setAutoShapes.mockClear();
    ctrl.setServerAnalysisVisibility(false);
    expect(setAutoShapes).toHaveBeenCalledTimes(1);
    expect(setAutoShapes.mock.lastCall?.[0]).toEqual([engineArrow]);

    setAutoShapes.mockClear();
    ctrl.setServerAnalysisVisibility(true);
    expect(setAutoShapes).toHaveBeenCalledTimes(1);
    expect(setAutoShapes.mock.lastCall?.[0]).toContainEqual(
        expect.objectContaining({ orig: 'd2', dest: 'd4', below: true }),
    );
    expect(ctrl.autoShapes).toEqual([[engineArrow]]);
    expect(ctrl.localAnalysis).toBe(true);
});

function annotatedController() {
    const ctrl = controller();
    const current = {
        path: 'e2e4',
        children: [],
        step: { move: 'e2e4', san: 'e4', fen: '8/8/8/8/4P3/8/8/8', turnColor: 'black', check: false } as Step,
        annotations: { nags: [1, 146], shapes: [], comments: [] },
    };
    const engineArrow = { orig: 'g8', dest: 'f6', brush: 'paleGreen' };
    const setAutoShapes = jest.fn();
    const setShapes = jest.fn();
    Object.assign(ctrl, {
        localAnalysis: true,
        showServerAnalysis: true,
        variationArrows: false,
        showMoveAnnotationsOnBoard: true,
        analysisContext: { mode: 'study', capabilities: { positionEvaluation: true } },
        autoShapes: [[engineArrow]],
        tree: { analysisPath: 'e2e4', getTreeNodeAtPath: (path: string) => (path ? current : undefined) },
        chessground: {
            state: { dimensions: { width: 8, height: 8 }, kingRoles: ['k-piece'] },
            setAutoShapes,
            setShapes,
        },
    });
    return { ctrl, current, engineArrow, setAutoShapes, setShapes };
}

test('move annotation preference toggles board glyphs during local analysis without changing NAGs or other drawings', () => {
    const { ctrl, current, engineArrow, setAutoShapes, setShapes } = annotatedController();
    ctrl.setAutoShapes();
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(3);
    ctrl.showMoveAnnotationsOnBoard = false;
    ctrl.setAutoShapes();
    expect(setAutoShapes.mock.lastCall?.[0]).toEqual([engineArrow]);
    ctrl.showMoveAnnotationsOnBoard = true;
    ctrl.setAutoShapes();
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(3);
    expect(current.annotations.nags).toEqual([1, 146]);
    expect(ctrl.autoShapes).toEqual([[engineArrow]]);
    expect(setShapes).not.toHaveBeenCalled();
});

test('server visibility refreshes glyphs during local analysis and keeps human Study glyphs visible', () => {
    const { ctrl, current, engineArrow, setAutoShapes } = annotatedController();
    current.step.analysis = { s: { cp: -100 }, advice: { nag: 1 } } as any;
    ctrl.setServerAnalysisVisibility(false);
    expect(setAutoShapes).toHaveBeenCalledTimes(1);
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(2);
    ctrl.setServerAnalysisVisibility(true);
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(3);
    Object.assign(ctrl, { analysisContext: { mode: 'standalone', capabilities: {} } });
    ctrl.setServerAnalysisVisibility(false);
    expect(setAutoShapes.mock.lastCall?.[0]).toEqual([engineArrow]);
});

test('annotation visibility is independent of fork visibility and keeps playback hints intact', () => {
    const { ctrl, engineArrow, setAutoShapes } = annotatedController();
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: {
            allowVariationArrows: () => false,
            areTreeNodeAnnotationsVisible: () => true,
        },
        configurable: true,
    });
    ctrl.setAutoShapes();
    expect(setAutoShapes.mock.lastCall?.[0]).toHaveLength(3);
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: {
            allowVariationArrows: () => false,
            areTreeNodeAnnotationsVisible: () => false,
        },
    });
    ctrl.completeAnalysisPositionChange('reset', '', 'e2e4');
    expect(setAutoShapes.mock.lastCall?.[0]).toEqual([engineArrow]);
});
