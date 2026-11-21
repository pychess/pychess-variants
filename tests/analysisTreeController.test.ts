import { beforeAll, beforeEach, expect, jest, test } from '@jest/globals';

import { Step } from '../client/messages';

const updateMovelistMock = jest.fn();
const keyBindings = new Map<string, (event?: KeyboardEvent) => void>();
const bindMock = jest.fn((keys: string | string[], callback: (event?: KeyboardEvent) => void) => {
    (Array.isArray(keys) ? keys : [keys]).forEach(key => keyBindings.set(key, callback));
});

jest.unstable_mockModule('../client/movelist', () => ({
    updateMovelist: updateMovelistMock,
}));

jest.unstable_mockModule('mousetrap', () => ({
    bind: bindMock,
}));

let AnalysisTreeController: typeof import('../client/analysis/analysisTreeCtrl').AnalysisTreeController;

beforeAll(async () => {
    ({ AnalysisTreeController } = await import('../client/analysis/analysisTreeCtrl'));
});

function makeStep(fen: string, move: string | undefined, turnColor: 'white' | 'black', san: string): Step {
    return {
        fen,
        move,
        check: false,
        turnColor,
        san,
        sanSAN: san,
    };
}

function steps4() {
    return [
        makeStep('start w - - 0 1', undefined, 'white', ''),
        makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
        makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
        makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
    ];
}

function stubCtrl(steps: Step[], gameId = 'abcd1234') {
    return {
        steps,
        plyVari: 0,
        ply: 0,
        gameId,
        variant: { name: 'chess' },
        recordedMainlinePly: undefined as number | undefined,
        goPly: jest.fn(),
        completeAnalysisPositionChange: jest.fn(),
        setAutoShapes: jest.fn(),
        ffishBoard: {
            setFen: jest.fn(),
            sanMove: jest.fn((move: string) => move),
        },
    };
}

let localStorageData: Record<string, string>;

beforeEach(() => {
    updateMovelistMock.mockClear();
    bindMock.mockClear();
    keyBindings.clear();
    localStorageData = {};
    Object.defineProperty(global, 'localStorage', {
        value: new Proxy(
            {},
            {
                get: (_target, key: string) => localStorageData[key],
                set: (_target, key: string, value: string) => {
                    localStorageData[key] = value;
                    return true;
                },
            },
        ),
        configurable: true,
    });
});

test('builds the persisted mainline and activates the requested ply', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);

    tree.initAnalysisTreeAtPly(2);

    expect(tree.hasAnalysisTree()).toBe(true);
    expect(tree.getTreeCurrentNode()?.step.san).toBe('e5');
    expect(tree.getTreeNodeList().map(node => node.step.san)).toEqual(['', 'e4', 'e5']);
    expect(ctrl.goPly).toHaveBeenCalledWith(2, 0);
});

test('tree navigation requests scrolling to the newly selected move', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(0);
    updateMovelistMock.mockClear();

    tree.activateTreeMainlinePly(3);

    expect(ctrl.goPly).toHaveBeenLastCalledWith(3, 0);
    // The default activate=true keeps the selected move visible.
    expect(updateMovelistMock).toHaveBeenLastCalledWith(ctrl);
});

test('active-line ply navigation preserves a selected variation', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    const c5 = tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'))!;
    tree.activateTreePath(c5.childPath);

    tree.activateTreePly(1);
    expect(tree.getTreeActivePath()).toBe(branchParent);

    tree.activateTreePly(2);
    expect(tree.getTreeActivePath()).toBe(c5.childPath);
    expect(tree.getTreeCurrentNode()?.step.san).toBe('c5');
});

test('playing a saved server-analysis variation makes it visible with server analysis disabled', () => {
    const ctrl = { ...stubCtrl(steps4()), showServerAnalysis: false };
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const parent = tree.getTreeActivePath();
    const serverStep = makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5');
    const first = tree.recordMove(serverStep)!;
    const serverNode = tree.getTreeNodeAtPath(first.childPath)!;
    serverNode.serverAnalysis = true;
    expect(tree.getTreeMainChildPath()).not.toBe(first.childPath);

    const played = tree.recordMove(serverStep)!;
    expect(played.childPath).toBe(first.childPath);
    expect(serverNode.serverAnalysis).toBe(false);
    expect(tree.getTreeNodeAtPath(parent)!.children.filter(node => node.path === played.childPath)).toHaveLength(1);
    expect(tree.getTreeMainChildPath()).toBe(tree.getTreeNodeAtPath(parent)!.children[0].path);

    // Navigating to the saved advice alone must not count as playing it.
    serverNode.serverAnalysis = true;
    tree.activateTreePath(first.childPath);
    expect(serverNode.serverAnalysis).toBe(true);
});

test('records nested variations without extending persisted steps', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const before = ctrl.steps.length;

    const c5 = tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'))!;
    tree.activateTreePath(c5.childPath);
    const nf3 = tree.recordMove(makeStep('v2 b - - 0 1', 'g1f3', 'black', 'Nf3'))!;
    tree.activateTreePath(nf3.childPath);

    expect(c5.extendedMainline).toBe(false);
    expect(nf3.extendedMainline).toBe(false);
    expect(ctrl.steps).toHaveLength(before);
    expect(tree.getTreeNodeList().map(node => node.step.san)).toEqual(['', 'e4', 'c5', 'Nf3']);
});

test('records a move at the mainline tail and preserves mainline bookkeeping', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(3);

    const e6 = makeStep('s4 w - - 0 1', 'e7e6', 'white', 'e6');
    const recorded = tree.recordMove(e6)!;

    expect(recorded.extendedMainline).toBe(true);
    expect(ctrl.steps.at(-1)).toBe(e6);
    expect(ctrl.recordedMainlinePly).toBe(4);
    expect(tree.getTreeNodeAtPath(recorded.childPath)?.mainlinePly).toBe(4);
});

test('promotes, forces and deletes branches while keeping the active path valid', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();

    const c5 = tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'))!;
    tree.activateTreePath(branchParent);
    const e6 = tree.recordMove(makeStep('v2 w - - 0 1', 'e7e6', 'white', 'e6'))!;

    tree.promoteTreeVariation(e6.childPath, false);
    expect(tree.getTreeNodeAtPath(branchParent)?.children.map(node => node.step.san)).toEqual(['e6', 'e5', 'c5']);

    tree.forceTreeVariation(e6.childPath, true);
    expect(tree.pathIsTreeForcedVariation(e6.childPath)).toBe(true);

    tree.activateTreePath(c5.childPath);
    const nf3 = tree.recordMove(makeStep('v3 b - - 0 1', 'g1f3', 'black', 'Nf3'))!;
    tree.activateTreePath(nf3.childPath);
    tree.deleteTreeNode(c5.childPath);

    expect(tree.getTreeActivePath()).toBe(branchParent);
    expect(tree.getTreeNodeAtPath(c5.childPath)).toBeUndefined();
});

function addBranchAtPlyOne(tree: InstanceType<typeof AnalysisTreeController>) {
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'));
    tree.activateTreePath('');
    return branchParent;
}

test('collapsed paths persist per game and can be expanded again', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    const branchParent = addBranchAtPlyOne(tree);

    tree.toggleTreeCollapsed(branchParent);
    expect(tree.someTreeCollapsed(true)).toBe(true);

    const ctrl2 = stubCtrl(steps4());
    const tree2 = new AnalysisTreeController(ctrl2 as any);
    addBranchAtPlyOne(tree2);
    expect(tree2.someTreeCollapsed(true)).toBe(true);

    tree2.expandAllTree();
    expect(tree2.someTreeCollapsed(true)).toBe(false);
});

test('context menu keeps viewport coordinates and closes cleanly', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const path = tree.getTreeActivePath();

    tree.openTreeContextMenu(path, 321, 456);
    expect(tree.getTreeContextMenu()).toEqual({ path, x: 321, y: 456 });

    tree.closeTreeContextMenu();
    expect(tree.getTreeContextMenu()).toBeUndefined();
});

test('keyboard fork selection and right navigation use the extracted tree state', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'));
    tree.activateTreePath(branchParent);

    keyBindings.get('up')?.(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
    expect(tree.treeForkIndex).toBe(1);
    expect(ctrl.setAutoShapes).toHaveBeenCalledTimes(1);

    keyBindings.get('right')?.();
    expect(tree.getTreeCurrentNode()?.step.san).toBe('c5');
});

test('extension observes successful tree mutations without duplicate add notifications', () => {
    const extension = {
        onNodeAdded: jest.fn(),
        onNodeDeleted: jest.fn(),
        onVariationPromoted: jest.fn(),
        onVariationForced: jest.fn(),
    };
    const ctrl = { ...stubCtrl(steps4()), analysisExtension: extension };
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    const c5Step = makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5');

    const c5 = tree.recordMove(c5Step)!;
    expect(extension.onNodeAdded).toHaveBeenCalledTimes(1);
    expect(extension.onNodeAdded).toHaveBeenCalledWith(branchParent, tree.getTreeNodeAtPath(c5.childPath));

    tree.recordMove(c5Step);
    expect(extension.onNodeAdded).toHaveBeenCalledTimes(1);

    tree.promoteTreeVariation(c5.childPath, false);
    expect(extension.onVariationPromoted).toHaveBeenCalledWith(c5.childPath, false);

    tree.forceTreeVariation(c5.childPath, true);
    expect(extension.onVariationForced).toHaveBeenCalledWith(c5.childPath, true);

    tree.deleteTreeNode(c5.childPath);
    expect(extension.onNodeDeleted).toHaveBeenCalledWith(c5.childPath);
});

test('extension receives explicit navigation origins and can veto each route independently', () => {
    const extension = {
        canActivatePath: jest.fn((_path: string, _origin: string) => true),
        onPathChanged: jest.fn(),
    };
    const ctrl = { ...stubCtrl(steps4()), analysisExtension: extension };
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    const c5 = tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'))!;

    extension.onPathChanged.mockClear();
    extension.canActivatePath.mockImplementation((_path, origin) => origin !== 'user-navigation');
    tree.activateTreePath(c5.childPath);
    expect(tree.getTreeActivePath()).toBe(branchParent);
    expect(extension.canActivatePath).toHaveBeenLastCalledWith(c5.childPath, 'user-navigation');
    expect(extension.onPathChanged).not.toHaveBeenCalled();

    tree.activateTreePath(c5.childPath, false, 'played-move');
    expect(tree.getTreeActivePath()).toBe(c5.childPath);
    expect(extension.canActivatePath).toHaveBeenLastCalledWith(c5.childPath, 'played-move');
    expect(extension.onPathChanged).toHaveBeenCalledWith(c5.childPath, branchParent, 'played-move');

    extension.onPathChanged.mockClear();
    tree.deleteTreeNode(c5.childPath);
    expect(tree.getTreeActivePath()).toBe(branchParent);
    expect(extension.onPathChanged).toHaveBeenCalledWith(branchParent, c5.childPath, 'reset');
});

test('played existing child still produces a completed-position notification', () => {
    const ctrl = stubCtrl(steps4());
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const branchParent = tree.getTreeActivePath();
    const existing = tree.getTreeNodeAtPath(`${branchParent}.02`);
    expect(existing?.step.move).toBe('e7e5');

    ctrl.completeAnalysisPositionChange.mockClear();
    const recorded = tree.recordMove(existing!.step)!;
    expect(recorded.childPath).toBe(existing!.path);

    tree.activateTreePath(recorded.childPath, false, 'played-move');
    expect(ctrl.completeAnalysisPositionChange).toHaveBeenCalledWith('played-move', branchParent, existing!.path);
});

test('extension can suppress the analysis tree context menu', () => {
    const extension = { allowTreeContextMenu: jest.fn(() => false) };
    const ctrl = { ...stubCtrl(steps4()), analysisExtension: extension };
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const path = tree.getTreeActivePath();

    tree.openTreeContextMenu(path, 10, 20);

    expect(extension.allowTreeContextMenu).toHaveBeenCalled();
    expect(tree.getTreeContextMenu()).toBeUndefined();
});

test('fork selection and right navigation skip hidden server and lesson continuations', () => {
    const ctrl = {
        ...stubCtrl(steps4()),
        showServerAnalysis: false,
        analysisExtension: { isTreeNodeVisible: (node: any) => node.step.move !== 'd7d5' },
    };
    const tree = new AnalysisTreeController(ctrl as any);
    tree.initAnalysisTreeAtPly(1);
    const parent = tree.getTreeActivePath();
    const original = tree.getTreeCurrentNode()!.children[0];
    original.serverAnalysis = true;
    tree.recordMove(makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'));
    tree.recordMove(makeStep('v2 w - - 0 1', 'd7d5', 'white', 'd5'));
    tree.recordMove(makeStep('v3 w - - 0 1', 'g8f6', 'white', 'Nf6'));
    tree.activateTreePath(parent);
    expect(tree.getTreeMainChildPath()).toBe(tree.getTreeCurrentNode()!.children[1].path);
    tree.selectTreeFork('next');
    keyBindings.get('right')?.();
    expect(tree.getTreeCurrentNode()?.step.move).toBe('g8f6');
});
