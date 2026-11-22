import { expect, jest, test } from '@jest/globals';

jest.unstable_mockModule('chessgroundx', () => ({ Chessground: jest.fn() }));

const { AnalysisController } = await import('../client/analysis/analysisCtrl');

test('analysis delegates unknown websocket messages to the optional extension', () => {
    const onSocketMessage = jest.fn(() => true);
    const ctrl = Object.create(AnalysisController.prototype) as InstanceType<typeof AnalysisController> & {
        analysisExtension: { onSocketMessage: typeof onSocketMessage };
    };
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { onSocketMessage },
        configurable: true,
    });

    (ctrl as any).onMessage(
        new MessageEvent('message', {
            data: JSON.stringify({ type: 'study_node_added', path: '01.02' }),
        }),
    );

    expect(onSocketMessage).toHaveBeenCalledWith('study_node_added', {
        type: 'study_node_added',
        path: '01.02',
    });
});

test('analysis session generation cancels stale callbacks and runs registered cleanup', () => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.destroyed = false;
    ctrl.analysisSessionGeneration = 0;
    ctrl.analysisSessionCleanups = new Set<() => void>();
    const cleanup = jest.fn();

    const first = ctrl.beginAnalysisSession();
    expect(ctrl.isAnalysisSessionCurrent(first)).toBe(true);
    ctrl.addAnalysisSessionCleanup(first, cleanup);

    const second = ctrl.beginAnalysisSession();
    expect(cleanup).toHaveBeenCalledTimes(1);
    expect(ctrl.isAnalysisSessionCurrent(first)).toBe(false);
    expect(ctrl.isAnalysisSessionCurrent(second)).toBe(true);

    const staleCleanup = jest.fn();
    ctrl.addAnalysisSessionCleanup(first, staleCleanup);
    expect(staleCleanup).toHaveBeenCalledTimes(1);
});

test('completed position applies board-input policy before notifying the extension', () => {
    const calls: string[] = [];
    const chessground = {
        set: jest.fn(() => calls.push('board')),
    };
    const onPositionChanged = jest.fn(() => calls.push('position'));
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.tree = { analysisPath: '01', analysisTree: undefined };
    ctrl.ply = 1;
    ctrl.turnColor = 'black';
    ctrl.fullfen = 'fen-after';
    ctrl.chessground = chessground;
    ctrl.setAutoShapes = jest.fn(() => calls.push('shapes'));
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: {
            boardInput: jest.fn(() => false),
            onPositionChanged,
        },
        configurable: true,
    });

    ctrl.completeAnalysisPositionChange('played-move', '', '01');

    expect(chessground.set).toHaveBeenCalledWith({ movable: { color: undefined } });
    expect(onPositionChanged).toHaveBeenCalledWith({
        origin: 'played-move',
        path: '01',
        previousPath: '',
        ply: 1,
        fen: 'fen-after',
        node: undefined,
    });
    expect(calls).toEqual(['board', 'position', 'shapes']);
});

test('evaluation delivery can be observed and suppress ordinary presentation', () => {
    const onEvaluation = jest.fn(() => false);
    const ctrl = Object.create(AnalysisController.prototype) as any;
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { onEvaluation },
        configurable: true,
    });
    const delivery = {
        source: 'local' as const,
        ply: 4,
        fen: 'position',
        ceval: { d: 12, multipv: 1, p: 'e2e4', s: { cp: 23 } },
        scoreStr: '0.2',
    };

    expect(ctrl.shouldDisplayAnalysisEvaluation(delivery)).toBe(false);
    expect(onEvaluation).toHaveBeenCalledWith(delivery);
});

test('hiding server analysis suppresses stored and server scores while allowing local evaluations', () => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    const onEvaluation = jest.fn(() => true);
    Object.defineProperty(ctrl, 'analysisExtension', { value: { onEvaluation } });
    const evaluation = { ply: 1, fen: 'position', ceval: { s: { cp: 23 } }, scoreStr: '0.2' };
    ctrl.showServerAnalysis = false;
    for (const source of ['stored', 'server']) {
        expect(ctrl.shouldDisplayAnalysisEvaluation({ ...evaluation, source })).toBe(false);
    }
    expect(ctrl.shouldDisplayAnalysisEvaluation({ ...evaluation, source: 'local' })).toBe(true);
    expect(onEvaluation).toHaveBeenCalledTimes(3);
    ctrl.showServerAnalysis = true;
    expect(ctrl.shouldDisplayAnalysisEvaluation({ ...evaluation, source: 'stored' })).toBe(true);
});

test('move application can be rejected before the analysis board is mutated', () => {
    const beforeMoveApplied = jest.fn(() => false);
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.variant = { replayOnly: false };
    ctrl.tree = {
        analysisPath: '01',
        hasAnalysisTree: () => true,
    };
    ctrl.activateTreePath = jest.fn();
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { beforeMoveApplied },
        configurable: true,
    });

    expect(ctrl.applyAnalysisMove('e2e4', 'played-move')).toBe(false);
    expect(beforeMoveApplied).toHaveBeenCalledWith({ move: 'e2e4', origin: 'played-move', path: '01' });
    expect(ctrl.activateTreePath).toHaveBeenCalledWith('01', true, 'reset');
});

test('replay-only analysis rejects moves before touching native boards', () => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.variant = { replayOnly: true };
    expect(ctrl.applyAnalysisMove('a3a4+')).toBe(false);
});

test('extension can disable local computer search independently of ordinary analysis capability', () => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { allowComputerSearch: () => false },
        configurable: true,
    });

    expect(ctrl.isLocalAnalysisAllowedByExtension()).toBe(false);

    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { allowComputerSearch: () => true },
        configurable: true,
    });
    expect(ctrl.isLocalAnalysisAllowedByExtension()).toBe(true);
});

test('extension session suspension stops the engine without overwriting the saved engine preference', () => {
    localStorage.localAnalysis = 'true';
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.localAnalysis = true;
    ctrl.lastBroadcastLocalAnalysisFen = 'position';
    ctrl.vpvlines = undefined;
    ctrl.engineStop = jest.fn();

    ctrl.suspendLocalAnalysisForExtension();

    expect(ctrl.localAnalysis).toBe(false);
    expect(ctrl.lastBroadcastLocalAnalysisFen).toBeUndefined();
    expect(ctrl.engineStop).toHaveBeenCalledTimes(1);
    expect(localStorage.localAnalysis).toBe('true');
});

test('fork composition filters invisible children and keeps hover, PV and manual drawing ownership separate', () => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    const child = (move: string, serverAnalysis = false) => ({
        path: move,
        serverAnalysis,
        children: [],
        step: { move, fen: '8/8/8/8/8/8/8/8', turnColor: 'black', check: false },
    });
    const children = [child('e2e4'), child('d2d4'), child('c2c4', true), child('b2b4')];
    ctrl.tree = { analysisPath: '', getTreeNodeAtPath: () => ({ children }), getTreeMainChildPath: () => 'd2d4' };
    ctrl.chessground = {
        state: { dimensions: { width: 8, height: 8 }, boardState: { pieces: new Map() }, turnColor: 'white' },
        setAutoShapes: jest.fn(),
        setShapes: jest.fn(),
    };
    ctrl.autoShapes = [[{ orig: 'e2', dest: 'e4', brush: 'paleGreen', modifiers: { lineWidth: 14 } }]];
    ctrl.variationArrows = true;
    ctrl.showServerAnalysis = false;
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { isTreeNodeVisible: (node: any) => node.path !== 'b2b4' },
        configurable: true,
    });
    ctrl.setAutoShapes();
    expect(ctrl.chessground.setAutoShapes.mock.lastCall[0]).toHaveLength(2);
    expect(ctrl.chessground.setAutoShapes.mock.lastCall[0][1]).toMatchObject({ orig: 'd2', below: true });
    ctrl.setVariationHover('d2d4');
    expect(ctrl.chessground.setAutoShapes.mock.lastCall[0][0]).toMatchObject({
        orig: 'd2',
        brush: 'paleBlue',
        modifiers: { hilite: 'white' },
    });
    ctrl.setVariationHover();
    expect(ctrl.chessground.setAutoShapes.mock.lastCall[0][0]).toMatchObject({
        orig: 'e2',
        brush: 'paleGreen',
        modifiers: { lineWidth: 14 },
    });
    ctrl.variationArrows = false;
    ctrl.setAutoShapes();
    expect(ctrl.chessground.setAutoShapes.mock.lastCall[0]).toEqual(ctrl.autoShapes.flat());
    expect(ctrl.chessground.setShapes).not.toHaveBeenCalled();
});

test.each(['embed', 'fog', 'puzzle'])('%s boards retain their existing auto-shapes without adding forks', mode => {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl[mode] = true;
    ctrl.autoShapes = [[{ orig: 'e2', dest: 'e4', brush: 'paleGreen' }]];
    ctrl.chessground = { setAutoShapes: jest.fn() };
    ctrl.setAutoShapes();
    expect(ctrl.chessground.setAutoShapes).toHaveBeenCalledWith(ctrl.autoShapes[0]);
});
