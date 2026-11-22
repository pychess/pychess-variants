import { beforeAll, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { forceVariationAt, promoteNodePath } from '../client/analysis/analysisTree';
import { Step } from '../client/messages';
import { addStudyNodeToAnalysisTree, analysisTreeFromStudy, type StudyTreeNodeDto } from '../client/study/studyTree';
import { studySessionPolicy } from '../client/study/studyMode';

const updateMovelistMock = jest.fn();
jest.unstable_mockModule('../client/movelist', () => ({
    updateMovelist: updateMovelistMock,
}));

let StudyAnalysisExtension: typeof import('../client/study/studySync').StudyAnalysisExtension;

beforeAll(async () => {
    ({ StudyAnalysisExtension } = await import('../client/study/studySync'));
});

function rootStep(): Step {
    return {
        fen: 'start w - - 0 1',
        check: false,
        turnColor: 'white',
        san: '',
        sanSAN: '',
    };
}

function e4Node(): StudyTreeNodeDto {
    return {
        id: 'StudyNode1',
        parentId: null,
        order: 0,
        move: 'e2e4',
        fen: 'e4 b - - 0 1',
        turnColor: 'black',
        check: false,
        san: 'e4',
        sanSAN: 'e4',
    };
}

function makeCtrl() {
    const tree = analysisTreeFromStudy(rootStep(), { nodes: [] });
    const ctrl: any = {
        analysisTree: tree,
        analysisPath: '',
        steps: [tree.root.step],
        recordedMainlinePly: undefined,
        doSend: jest.fn(),
        buildScoreStr: jest.fn((_color: string, ceval: any) =>
            ceval.s.cp !== undefined ? String(ceval.s.cp) : `#${ceval.s.mate}`,
        ),
        username: 'owner',
        chessground: { setShapes: jest.fn() },
        refreshLocalAnalysisAvailabilityForAntiCheat: jest.fn(),
    };
    ctrl.activateTreePath = jest.fn((path: string) => {
        ctrl.analysisPath = path;
    });
    return ctrl;
}

describe('Study analysis websocket synchronization', () => {
    beforeEach(() => updateMovelistMock.mockClear());

    test('effective session policy gates recording, sync, engine search and evaluation at the extension boundary', () => {
        const ctrl = makeCtrl();
        const policy = studySessionPolicy({
            mode: 'gamebook',
            canWrite: true,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
            override: 'preview',
        });
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            recording: true,
            policy,
            onReloadRequired: jest.fn(),
        });

        extension.onSocketOpen();
        ctrl.doSend.mockClear();

        expect(extension.isRecording).toBe(false);
        expect(extension.sharePosition('chapter1', '')).toBe(false);
        expect(extension.followSharedPath('')).toBe(false);
        expect(extension.allowComputerSearch()).toBe(false);
        expect(extension.onEvaluation()).toBe(false);
        extension.requestServerAnalysis();
        expect(ctrl.doSend).not.toHaveBeenCalled();
    });

    test('root-only embed preview blocks moves, navigation, annotations and engine work', () => {
        const ctrl = makeCtrl();
        const child = addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4Node());
        expect(child).not.toBeUndefined();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            rootOnlyPreview: true,
            onReloadRequired: jest.fn(),
        });

        expect(extension.boardInput({ turnColor: 'white' })).toBe(false);
        expect(extension.beforeMoveApplied({ move: 'e2e4', origin: 'played-move', path: '' })).toBe(false);
        expect(extension.canActivatePath('StudyNode1', 'user-navigation')).toBe(false);
        expect(extension.canActivatePath('', 'reset')).toBe(true);
        expect(extension.isTreeNodeVisible(ctrl.analysisTree.root)).toBe(true);
        expect(extension.isTreeNodeVisible(ctrl.analysisTree.byPath.get('StudyNode1'))).toBe(false);
        expect(extension.areTreeNodeAnnotationsVisible(ctrl.analysisTree.root)).toBe(false);
        expect(extension.allowTreeContextMenu()).toBe(false);
        expect(extension.allowComputerSearch()).toBe(false);
        expect(extension.onEvaluation()).toBe(false);

        extension.onPathChanged();
        expect(ctrl.chessground.setShapes).toHaveBeenLastCalledWith([]);
    });

    test('gamebook preview attempts stay local and do not advance revision or shared position', () => {
        const ctrl = makeCtrl();
        const policy = studySessionPolicy({
            mode: 'gamebook',
            canWrite: true,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
            override: 'preview',
        });
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 4,
            writable: true,
            policy,
            onReloadRequired: jest.fn(),
        });
        const playback = {
            destroy: jest.fn(),
            onShapesChanged: jest.fn(),
        } as any;
        extension.setGamebookPlayback(playback);
        extension.onSocketOpen();
        ctrl.doSend.mockClear();

        const local = { ...e4Node(), id: 'LocalTry01' };
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', local);
        extension.onNodeAdded('', ctrl.analysisTree.byPath.get('LocalTry01'));
        extension.onShapesChanged([{ orig: 'a1', dest: 'a2', brush: 'green' } as any]);

        expect(extension.sharePosition('chapter1', 'LocalTry01')).toBe(false);
        expect(extension.pendingCount).toBe(0);
        expect(extension.revision).toBe(4);
        expect(ctrl.doSend).not.toHaveBeenCalled();
        expect(playback.onShapesChanged).toHaveBeenCalledTimes(1);
    });

    test('remote lesson edits, mainline reorders and deletions suspend the attempt and request a fresh script', () => {
        const ctrl = makeCtrl();
        const e4 = e4Node();
        const d4: StudyTreeNodeDto = {
            ...e4Node(),
            id: 'StudyNode2',
            order: 1,
            move: 'd2d4',
            fen: 'd4 b - - 0 1',
            san: 'd4',
            sanSAN: 'd4',
        };
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4);
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', d4);
        const scriptChanged = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            onGamebookScriptChanged: scriptChanged,
            onReloadRequired: jest.fn(),
        });
        const playback = {
            destroy: jest.fn(),
            suspendForScriptReload: jest.fn(),
        } as any;
        extension.setGamebookPlayback(playback);

        extension.onSocketMessage('study_set_gamebook', {
            type: 'study_set_gamebook',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteHint',
            revision: 1,
            changed: true,
            path: '',
            gamebook: { hint: 'Look for the center.' },
        });
        extension.onSocketMessage('study_promote_variation', {
            type: 'study_promote_variation',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemotePromote',
            revision: 2,
            changed: true,
            path: 'StudyNode2',
            toMainline: true,
        });
        extension.onSocketMessage('study_delete_node', {
            type: 'study_delete_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteDelete',
            revision: 3,
            changed: true,
            path: 'StudyNode2',
        });

        expect(playback.suspendForScriptReload).toHaveBeenCalledTimes(3);
        expect(scriptChanged).toHaveBeenCalledTimes(3);
        expect(extension.revision).toBe(3);
        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['StudyNode1']);
    });

    test('restricted policy removes persisted evaluations before Study output is rendered', () => {
        const ctrl = makeCtrl();
        ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
        const policy = studySessionPolicy({
            mode: 'gamebook',
            canWrite: false,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
        });
        const node = {
            ...e4Node(),
            eval: { cp: 42 },
        };
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            tree: { nodes: [node] },
            policy,
            onReloadRequired: jest.fn(),
        });

        extension.onInitialBoardLoaded();

        expect(ctrl.steps[1].ceval).toBeUndefined();
        expect(ctrl.steps[1].analysis).toBeUndefined();
        expect(ctrl.steps[1].scoreStr).toBeUndefined();
    });

    test('updating policy clears effective REC immediately without changing the saved preference input', () => {
        const ctrl = makeCtrl();
        const normal = studySessionPolicy({
            mode: 'normal',
            canWrite: true,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
        });
        const preview = studySessionPolicy({
            mode: 'gamebook',
            canWrite: true,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
            override: 'preview',
        });
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            policy: normal,
            onReloadRequired: jest.fn(),
        });

        expect(extension.isRecording).toBe(true);
        extension.setPolicy(preview);

        expect(extension.isRecording).toBe(false);
        expect(ctrl.refreshLocalAnalysisAvailabilityForAntiCheat).toHaveBeenCalledTimes(1);

        extension.setPolicy(normal, false);
        expect(extension.isRecording).toBe(false);
        extension.setPolicy(normal);
        expect(extension.isRecording).toBe(true);
    });

    test('loads the persisted tree into the generic analysis host before editing', () => {
        const ctrl = makeCtrl();
        ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
        const initialTreeLoaded = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 4,
            tree: { nodes: [e4Node()] },
            orientation: 'black',
            onInitialTreeLoaded: initialTreeLoaded,
            onReloadRequired: jest.fn(),
        });

        extension.onInitialBoardLoaded();

        expect(ctrl.tree.loadAnalysisTree).toHaveBeenCalledTimes(1);
        expect(ctrl.analysisTree.root.children[0].id).toBe('StudyNode1');
        expect(ctrl.steps.map((step: Step) => step.move)).toEqual([undefined, 'e2e4']);
        expect(ctrl.mycolor).toBe('black');
        expect(ctrl.oppcolor).toBe('white');
        expect(extension.treeStorageKey).toBe('study:study001:chapter1');
        expect(initialTreeLoaded).toHaveBeenCalledTimes(1);
        expect(updateMovelistMock).toHaveBeenCalled();
    });

    test('applies persisted and live Study server analysis to the preferred mainline', () => {
        const ctrl = makeCtrl();
        ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
        const changed = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            tree: { nodes: [e4Node()] },
            serverEval: {
                path: 'StudyNode1',
                done: false,
                requestedAt: '2026-09-07T12:00:00+00:00',
                analysis: [
                    { s: { cp: 10 }, d: 14 },
                    { s: { cp: 25 }, d: 14 },
                ],
            },
            onServerEvalChanged: changed,
            onReloadRequired: jest.fn(),
        });

        extension.onInitialBoardLoaded();
        expect(ctrl.steps[0].ceval).toEqual({ s: { cp: 10 }, d: 14 });
        expect(ctrl.steps[1].ceval).toEqual({ s: { cp: 25 }, d: 14 });

        expect(
            extension.onSocketMessage('study_analysis_progress', {
                type: 'study_analysis_progress',
                studyId: 'study001',
                chapterId: 'chapter1',
                tree: {
                    nodes: [
                        {
                            ...e4Node(),
                            eval: { mate: 3 },
                            annotations: {
                                shapes: [],
                                comments: [{ id: 'EngineNote', author: 'PyChess', text: 'Blunder. d4 was best.' }],
                                nags: [4],
                            },
                        },
                        {
                            id: 'StudyNode2',
                            parentId: null,
                            order: 1,
                            move: 'd2d4',
                            fen: 'd4 b - - 0 1',
                            turnColor: 'black',
                            check: false,
                            san: 'd4',
                            sanSAN: 'd4',
                            eval: { cp: -18 },
                        },
                    ],
                },
                serverEval: {
                    path: 'StudyNode1',
                    done: true,
                    requestedAt: '2026-09-07T12:00:00+00:00',
                    analysis: [
                        { s: { cp: 12 }, d: 18 },
                        { s: { mate: 3 }, d: 18, p: 'e7e5' },
                    ],
                },
            }),
        ).toBe(true);
        expect(ctrl.steps[0].ceval).toEqual({ s: { cp: 12 }, d: 18 });
        expect(ctrl.steps[1].ceval).toEqual({ s: { mate: 3 }, d: 18, p: 'e7e5' });
        expect(ctrl.analysisTree.root.children.map((node: any) => node.step.move)).toEqual(['e2e4', 'd2d4']);
        expect(ctrl.analysisTree.root.children[0].annotations?.nags).toEqual([4]);
        expect(ctrl.analysisTree.root.children[1].step.ceval).toEqual({ s: { cp: -18 }, d: 0 });
        expect(ctrl.analysisTree.root.children[1].step.scoreStr).toBe('-18');
        expect(changed).toHaveBeenCalledWith(expect.objectContaining({ done: true }));
    });

    test('keeps authoritative Study updates out of an active disposable practice tree', () => {
        const ctrl = makeCtrl();
        ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
        const reload = jest.fn();
        const changed = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            tree: { nodes: [e4Node()] },
            onServerEvalChanged: changed,
            onReloadRequired: reload,
        });

        extension.onInitialBoardLoaded();
        for (const path of ctrl.analysisTree.byPath.keys()) if (path) ctrl.analysisTree.byPath.delete(path);
        ctrl.analysisTree.root.children = [];
        ctrl.steps.splice(1);

        const localAttempt: StudyTreeNodeDto = {
            ...e4Node(),
            id: 'LocalTry01',
            move: 'd2d4',
            fen: 'd4 b - - 0 1',
            san: 'd4',
            sanSAN: 'd4',
        };
        const localNode = addStudyNodeToAnalysisTree(ctrl.analysisTree, '', localAttempt)!;
        ctrl.steps.push(localNode.step);
        ctrl.analysisPath = localNode.path;
        extension.setPracticeSession({ destroy: jest.fn() } as any);

        expect(
            extension.onSocketMessage('study_analysis_progress', {
                type: 'study_analysis_progress',
                studyId: 'study001',
                chapterId: 'chapter1',
                tree: { nodes: [e4Node()] },
                serverEval: {
                    path: 'StudyNode1',
                    done: true,
                    requestedAt: '2026-09-20T12:00:00+00:00',
                    analysis: [
                        { s: { cp: 12 }, d: 18 },
                        { s: { cp: 20 }, d: 18 },
                    ],
                },
            }),
        ).toBe(true);
        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['LocalTry01']);
        expect(ctrl.analysisTree.root.children[0].step.ceval).toBeUndefined();
        expect(changed).toHaveBeenCalledWith(expect.objectContaining({ done: true }));

        const remoteNode: StudyTreeNodeDto = {
            ...e4Node(),
            id: 'StudyNode2',
            move: 'c2c4',
            fen: 'c4 b - - 0 1',
            san: 'c4',
            sanSAN: 'c4',
        };
        expect(
            extension.onSocketMessage('study_add_node', {
                type: 'study_add_node',
                studyId: 'study001',
                chapterId: 'chapter1',
                clientOpId: 'RemoteAdd',
                revision: 1,
                changed: true,
                parentPath: '',
                path: 'StudyNode2',
                node: remoteNode,
            }),
        ).toBe(true);
        expect(extension.revision).toBe(1);
        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['LocalTry01']);
        expect(reload).not.toHaveBeenCalled();
    });

    test('requests Study server analysis only for a connected writable client', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            onReloadRequired: jest.fn(),
        });

        extension.requestServerAnalysis();
        expect(ctrl.doSend).not.toHaveBeenCalled();
        extension.onSocketOpen();
        extension.requestServerAnalysis();
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_request_analysis',
            studyId: 'study001',
            chapterId: 'chapter1',
        });
    });

    test('restores persisted shapes on initial load and path navigation', () => {
        const ctrl = makeCtrl();
        ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
        const stateChanged = jest.fn();
        const node = {
            ...e4Node(),
            annotations: {
                shapes: [{ orig: 'e4', dest: 'e5', brush: 'red' as const }],
                comments: [],
                nags: [1],
            },
        };
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            tree: {
                rootAnnotations: {
                    shapes: [{ orig: 'd4', brush: 'blue' }],
                    comments: [],
                    nags: [],
                },
                nodes: [node],
            },
            onAnnotationStateChanged: stateChanged,
            onReloadRequired: jest.fn(),
        });

        extension.onInitialBoardLoaded();
        expect(ctrl.chessground.setShapes).toHaveBeenLastCalledWith([{ orig: 'd4', brush: 'blue' }]);

        ctrl.analysisPath = 'StudyNode1';
        extension.onPathChanged();
        expect(ctrl.chessground.setShapes).toHaveBeenLastCalledWith([{ orig: 'e4', dest: 'e5', brush: 'red' }]);

        // AnalysisController updates the board after the path callback. Chessground can
        // clear manual drawings while applying that new position, so Study must restore
        // them again from the now-active node after the position has settled.
        ctrl.chessground.setShapes([]);
        extension.onPositionChanged({
            origin: 'user-navigation',
            path: 'StudyNode1',
            previousPath: '',
            ply: 1,
            fen: node.fen,
            node: ctrl.analysisTree.byPath.get('StudyNode1'),
        });
        expect(ctrl.chessground.setShapes).toHaveBeenLastCalledWith([{ orig: 'e4', dest: 'e5', brush: 'red' }]);
        expect(stateChanged).toHaveBeenLastCalledWith(
            expect.objectContaining({ path: 'StudyNode1', annotations: expect.objectContaining({ nags: [1] }) }),
        );
    });

    test('queues a local drawing mutation and accepts the canonical server shape without echoing it', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
            opIdFactory: () => 'ShapeOp001',
        });
        extension.onSocketOpen();
        extension.onShapesChanged([
            { orig: 'e4', dest: 'e5', brush: 'red' },
            { orig: 'a1', brush: 'green', customSvg: '<svg />' },
        ]);

        expect(ctrl.doSend).toHaveBeenCalledTimes(1);
        expect(ctrl.doSend).toHaveBeenCalledWith({
            type: 'study_set_shapes',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'ShapeOp001',
            expectedRevision: 0,
            path: '',
            shapes: [{ orig: 'e4', dest: 'e5', brush: 'red' }],
        });

        extension.onSocketMessage('study_set_shapes', {
            type: 'study_set_shapes',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'ShapeOp001',
            revision: 1,
            changed: true,
            path: '',
            annotations: { shapes: [{ orig: 'e4', dest: 'e5', brush: 'red' }], comments: [], nags: [] },
        });

        expect(ctrl.chessground.setShapes).toHaveBeenCalledWith([{ orig: 'e4', dest: 'e5', brush: 'red' }]);
        expect(ctrl.doSend).toHaveBeenCalledTimes(1);
        expect(extension.revision).toBe(1);
        expect(reload).not.toHaveBeenCalled();
    });

    test('server-canonical comment acknowledgement replaces optimistic text and author', () => {
        const ctrl = makeCtrl();
        const states = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onAnnotationStateChanged: states,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'CommentOp1',
        });
        extension.onSocketOpen();
        extension.setComment('Comment001', ' local text ');
        expect(extension.annotationState.annotations.comments[0].text).toBe('local text');

        extension.onSocketMessage('study_set_comment', {
            type: 'study_set_comment',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'CommentOp1',
            revision: 1,
            changed: true,
            path: '',
            annotations: {
                shapes: [],
                comments: [{ id: 'Comment001', author: 'owner', text: 'canonical text' }],
                nags: [],
            },
        });

        expect(extension.annotationState.annotations.comments).toEqual([
            { id: 'Comment001', author: 'owner', text: 'canonical text' },
        ]);
        expect(states).toHaveBeenCalled();
    });

    test('saving a delayed comment targets its original path', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'CommentOp1',
        });
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4Node());
        ctrl.analysisPath = 'StudyNode1';
        extension.onSocketOpen();
        extension.setComment('Comment001', 'Root draft', '');
        expect(ctrl.analysisPath).toBe('StudyNode1');
        expect(ctrl.analysisTree.root.annotations.comments[0].text).toBe('Root draft');
        expect(extension.annotationState.annotations.comments).toEqual([]);
        expect(ctrl.doSend).toHaveBeenLastCalledWith(expect.objectContaining({ path: '', text: 'Root draft' }));
    });

    test('saving delayed gamebook text targets the captured path, field and value', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'GamebookOp1',
        });
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4Node());
        ctrl.analysisPath = 'StudyNode1';
        extension.onSocketOpen();

        extension.setGamebook('hint', 'Root lesson', '');
        ctrl.analysisPath = 'StudyNode1';

        expect(ctrl.analysisTree.root.gamebook).toEqual({ hint: 'Root lesson' });
        expect(ctrl.analysisTree.byPath.get('StudyNode1')?.gamebook).toBeUndefined();
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_gamebook',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'GamebookOp1',
            expectedRevision: 0,
            path: '',
            field: 'hint',
            value: 'Root lesson',
        });
    });

    test('clear annotations also clears lesson metadata and preserves a newer queued lesson edit', () => {
        const ctrl = makeCtrl();
        ctrl.analysisTree.root.annotations = {
            shapes: [],
            comments: [{ id: 'Comment001', author: 'owner', text: 'Root note' }],
            nags: [],
        };
        ctrl.analysisTree.root.gamebook = { hint: 'Old hint', deviation: 'Old fallback' };
        let op = 0;
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
            opIdFactory: () => `ClearGamebookOp${++op}`,
        });
        extension.onSocketOpen();
        ctrl.doSend.mockClear();

        extension.clearAnnotations();
        expect(ctrl.analysisTree.root.annotations).toBeUndefined();
        expect(ctrl.analysisTree.root.gamebook).toBeUndefined();
        expect(ctrl.doSend).toHaveBeenLastCalledWith(
            expect.objectContaining({ type: 'study_clear_annotations', clientOpId: 'ClearGamebookOp1', path: '' }),
        );

        extension.setGamebook('hint', 'New hint', '');
        expect(ctrl.analysisTree.root.gamebook).toEqual({ hint: 'New hint' });
        expect(extension.pendingCount).toBe(2);

        extension.onSocketMessage('study_clear_annotations', {
            type: 'study_clear_annotations',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'ClearGamebookOp1',
            revision: 1,
            changed: true,
            path: '',
            annotations: { shapes: [], comments: [], nags: [] },
            gamebook: {},
        });

        expect(ctrl.analysisTree.root.gamebook).toEqual({ hint: 'New hint' });
        expect(extension.pendingCount).toBe(1);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_gamebook',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'ClearGamebookOp2',
            expectedRevision: 1,
            path: '',
            field: 'hint',
            value: 'New hint',
        });
    });

    test('a remote clear-annotations broadcast removes both annotations and lesson metadata', () => {
        const ctrl = makeCtrl();
        ctrl.analysisTree.root.annotations = {
            shapes: [],
            comments: [{ id: 'Comment001', author: 'owner', text: 'Root note' }],
            nags: [1],
        };
        ctrl.analysisTree.root.gamebook = { hint: 'Root hint' };
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
        });

        extension.onSocketMessage('study_clear_annotations', {
            type: 'study_clear_annotations',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteClear1',
            revision: 1,
            changed: true,
            path: '',
            annotations: { shapes: [], comments: [], nags: [] },
            gamebook: {},
        });

        expect(ctrl.analysisTree.root.annotations).toBeUndefined();
        expect(ctrl.analysisTree.root.gamebook).toBeUndefined();
    });

    test('an older acknowledgement preserves newer comment and glyph edits', () => {
        const ctrl = makeCtrl();
        let op = 0;
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
            opIdFactory: () => `CommentOp${++op}`,
        });
        extension.onSocketOpen();
        extension.setComment('Comment001', 'First');
        extension.setComment('Comment001', 'Latest');
        extension.setNags([14, 146]);
        extension.onSocketMessage('study_set_comment', {
            type: 'study_set_comment',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'CommentOp1',
            revision: 1,
            changed: true,
            path: '',
            annotations: { comments: [{ id: 'Comment001', author: 'owner', text: 'First' }], shapes: [], nags: [] },
        });
        expect(extension.annotationState.annotations.comments[0].text).toBe('Latest');
        expect(extension.annotationState.annotations.nags).toEqual([14, 146]);
        expect(extension.pendingCount).toBe(2);
    });

    test('applies remote root annotations and chapter metadata without changing the active path', () => {
        const ctrl = makeCtrl();
        const e4 = e4Node();
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4);
        ctrl.analysisPath = 'StudyNode1';
        const states = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            description: 'old',
            onAnnotationStateChanged: states,
            onReloadRequired: jest.fn(),
        });

        extension.onSocketMessage('study_set_shapes', {
            type: 'study_set_shapes',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteShape',
            revision: 1,
            changed: true,
            path: '',
            annotations: { shapes: [{ orig: 'd4', brush: 'blue' }], comments: [], nags: [] },
        });
        expect(ctrl.analysisPath).toBe('StudyNode1');
        expect(ctrl.chessground.setShapes).not.toHaveBeenCalled();
        expect(ctrl.analysisTree.root.annotations?.shapes).toEqual([{ orig: 'd4', brush: 'blue' }]);

        extension.onSocketMessage('study_set_description', {
            type: 'study_set_description',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteDescription',
            revision: 2,
            changed: true,
            description: 'canonical description',
        });
        extension.onSocketMessage('study_set_tags', {
            type: 'study_set_tags',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteTags',
            revision: 3,
            changed: true,
            tags: { Event: 'Test' },
        });

        expect(extension.annotationState).toEqual(
            expect.objectContaining({ description: 'canonical description', tags: { Event: 'Test' } }),
        );
        expect(extension.revision).toBe(3);
        expect(states).toHaveBeenCalled();
    });

    test('serializes optimistic mutations behind revision acknowledgements', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const ids = ['Operation1', 'Operation2'];
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
            opIdFactory: () => ids.shift()!,
        });
        const node = e4Node();
        expect(addStudyNodeToAnalysisTree(ctrl.analysisTree, '', node)).toBe(node.id);

        extension.onSocketOpen();
        extension.onNodeAdded('', ctrl.analysisTree.root.children[0]);
        forceVariationAt(ctrl.analysisTree, node.id, true);
        extension.onVariationForced(node.id, true);

        expect(ctrl.doSend).toHaveBeenCalledTimes(1);
        expect(ctrl.doSend).toHaveBeenNthCalledWith(1, {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'Operation1',
            expectedRevision: 0,
            parentPath: '',
            move: 'e2e4',
            nodeId: 'StudyNode1',
        });
        expect(extension.pendingCount).toBe(2);

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'Operation1',
            revision: 1,
            changed: true,
            path: 'StudyNode1',
            parentPath: '',
            node,
        });

        expect(ctrl.doSend).toHaveBeenCalledTimes(2);
        expect(ctrl.doSend).toHaveBeenNthCalledWith(2, {
            type: 'study_force_variation',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'Operation2',
            expectedRevision: 1,
            path: 'StudyNode1',
            force: true,
        });
        expect(extension.revision).toBe(1);
        expect(reload).not.toHaveBeenCalled();
    });

    test('REC off still persists chapter metadata while keeping position annotations local', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            recording: false,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'MetadataOp',
        });
        extension.onSocketOpen();

        extension.setNags([1]);
        expect(extension.isRecording).toBe(false);
        expect(extension.pendingCount).toBe(0);
        expect(ctrl.doSend).not.toHaveBeenCalled();

        extension.setDescription('persistent chapter comment');
        expect(extension.pendingCount).toBe(1);
        expect(ctrl.doSend).toHaveBeenCalledWith(
            expect.objectContaining({ type: 'study_set_description', description: 'persistent chapter comment' }),
        );
    });

    test('practice playback can persist chapter metadata without enabling REC', () => {
        const ctrl = makeCtrl();
        const policy = studySessionPolicy({
            mode: 'practice',
            canWrite: true,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
        });
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            recording: true,
            policy,
            description: '',
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'PracticeMetadataOp',
        });
        extension.onSocketOpen();

        expect(extension.isRecording).toBe(false);
        extension.setDescription('Practice introduction');
        expect(ctrl.doSend).toHaveBeenCalledWith(
            expect.objectContaining({ type: 'study_set_description', description: 'Practice introduction' }),
        );
    });

    test('shared path waits for an optimistic tree mutation acknowledgement', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            recording: true,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'LocalOp1',
        });
        const node = e4Node();
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', node);
        extension.onSocketOpen();
        extension.onNodeAdded('', ctrl.analysisTree.root.children[0]);

        expect(extension.sharePosition('chapter1', 'StudyNode1')).toBe(true);
        expect(ctrl.doSend).toHaveBeenCalledTimes(1);

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalOp1',
            revision: 1,
            changed: true,
            path: 'StudyNode1',
            parentPath: '',
            node,
        });

        expect(ctrl.doSend).toHaveBeenCalledTimes(2);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_position',
            studyId: 'study001',
            chapterId: 'chapter1',
            path: 'StudyNode1',
            expectedRevision: 1,
        });
    });

    test('shared chapter switch does not invent a revision for a chapter that is not loaded', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 7,
            writable: true,
            recording: true,
            onReloadRequired: jest.fn(),
        });
        extension.onSocketOpen();

        expect(extension.sharePosition('chapter2', '')).toBe(true);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_position',
            studyId: 'study001',
            chapterId: 'chapter2',
            path: '',
        });
    });

    test('conceal broadcasts update reveal revision and authoritative shared position', () => {
        const ctrl = makeCtrl();
        const concealChanged = jest.fn();
        const sharedChanged = jest.fn();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 4,
            onConcealChanged: concealChanged,
            onSharedPositionChanged: sharedChanged,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_conceal', {
                type: 'study_conceal',
                studyId: 'study001',
                chapterId: 'chapter1',
                path: 'StudyNode1',
                concealPly: 1,
                revision: 5,
            }),
        ).toBe(true);
        expect(extension.revision).toBe(5);
        expect(concealChanged).toHaveBeenCalledWith(1, 5);
        expect(sharedChanged).toHaveBeenCalledWith('chapter1', 'StudyNode1');
        expect(reload).not.toHaveBeenCalled();
    });

    test('conceal reset is an explicit writable operation independent of REC', () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 9,
            writable: true,
            recording: false,
            onReloadRequired: jest.fn(),
        });
        extension.onSocketOpen();

        expect(extension.resetConcealment()).toBe(true);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_reset_conceal',
            studyId: 'study001',
            chapterId: 'chapter1',
            expectedRevision: 9,
        });
    });

    test('chapter-list messages deliver metadata and authoritative shared chapter without changing revision', () => {
        const ctrl = makeCtrl();
        const chaptersChanged = jest.fn();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 7,
            onChaptersChanged: chaptersChanged,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_chapters', {
                type: 'study_chapters',
                studyId: 'study001',
                sharedChapter: 'chapter2',
                sharedPath: '',
                chapters: [
                    {
                        id: 'chapter1',
                        name: 'Renamed chapter',
                        order: 1,
                        orientation: 'black',
                        mode: 'conceal',
                        status: '½-½',
                        concealPly: 3,
                        descriptionPinned: true,
                    },
                    { id: 'chapter2', name: 'Second', order: 2, orientation: 'white' },
                ],
            }),
        ).toBe(true);
        expect(chaptersChanged).toHaveBeenCalledWith(
            [
                {
                    id: 'chapter1',
                    name: 'Renamed chapter',
                    order: 1,
                    orientation: 'black',
                    mode: 'conceal',
                    status: '½-½',
                    concealPly: 3,
                    descriptionPinned: true,
                },
                { id: 'chapter2', name: 'Second', order: 2, orientation: 'white', mode: 'normal' },
            ],
            'chapter2',
            '',
        );
        expect(extension.revision).toBe(7);
        expect(reload).not.toHaveBeenCalled();
    });

    test('rejects chapter-list messages whose shared chapter is no longer present', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
        });

        extension.onSocketMessage('study_chapters', {
            type: 'study_chapters',
            studyId: 'study001',
            sharedChapter: 'deleted',
            sharedPath: '',
            chapters: [{ id: 'chapter1', name: 'Only', order: 1, orientation: 'white' }],
        });
        expect(reload).toHaveBeenCalledWith('invalid_chapter_list');
    });

    test('chapter-content messages advance revision and refresh the pinned description', () => {
        const ctrl = makeCtrl();
        const changed = jest.fn();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 7,
            description: 'old description',
            onAnnotationStateChanged: changed,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_chapter_content', {
                type: 'study_chapter_content',
                studyId: 'study001',
                chapterId: 'chapter1',
                revision: 8,
                description: '-',
            }),
        ).toBe(true);
        expect(extension.revision).toBe(8);
        expect(extension.annotationState.description).toBe('-');
        expect(changed).toHaveBeenLastCalledWith(expect.objectContaining({ description: '-' }));
        expect(reload).not.toHaveBeenCalled();

        extension.onSocketMessage('study_chapter_content', {
            type: 'study_chapter_content',
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 10,
            description: '',
        });
        expect(reload).toHaveBeenCalledWith('revision_mismatch');
    });

    test('chapter-content messages for other chapters do not change the current revision', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 7,
            description: 'current',
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_chapter_content', {
                type: 'study_chapter_content',
                studyId: 'study001',
                chapterId: 'chapter2',
                revision: 3,
                description: 'other chapter',
            }),
        ).toBe(true);
        expect(extension.revision).toBe(7);
        expect(extension.annotationState.description).toBe('current');
        expect(reload).not.toHaveBeenCalled();
    });

    test('shared position messages are delivered independently of chapter revisions', () => {
        const ctrl = makeCtrl();
        const sharedPosition = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 7,
            onSharedPositionChanged: sharedPosition,
            onReloadRequired: jest.fn(),
        });

        expect(
            extension.onSocketMessage('study_position', {
                type: 'study_position',
                studyId: 'study001',
                chapterId: 'chapter2',
                path: 'StudyNode1',
            }),
        ).toBe(true);
        expect(sharedPosition).toHaveBeenCalledWith('chapter2', 'StudyNode1');
        expect(extension.revision).toBe(7);
    });

    test('shared-position reload errors are honored even for another chapter', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
        });

        extension.onSocketMessage('study_reload', {
            type: 'study_reload',
            studyId: 'study001',
            chapterId: 'chapter2',
            reason: 'invalid_shared_position',
        });
        expect(reload).toHaveBeenCalledWith('invalid_shared_position');
    });

    test('read-only viewers receive remote changes without sending local mutations', async () => {
        const ctrl = makeCtrl();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            description: 'initial',
            writable: false,
            onReloadRequired: jest.fn(),
        });
        extension.onSocketOpen();

        extension.setDescription('local-only draft');
        expect(ctrl.doSend).not.toHaveBeenCalled();
        expect(extension.pendingCount).toBe(0);
        await expect(extension.whenIdle()).resolves.toBeUndefined();

        extension.onSocketMessage('study_set_description', {
            type: 'study_set_description',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteDescription',
            revision: 1,
            changed: true,
            description: 'owner update',
        });

        expect(extension.annotationState.description).toBe('owner update');
        expect(extension.revision).toBe(1);
        expect(ctrl.doSend).not.toHaveBeenCalled();
    });

    test('updates membership live and reloads when the current contributor loses write access', () => {
        const ctrl = makeCtrl();
        ctrl.username = 'writer';
        const reload = jest.fn();
        const membersChanged = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: true,
            memberRole: 'write',
            onMembersChanged: membersChanged,
            onReloadRequired: reload,
        });
        extension.onSocketOpen();

        expect(
            extension.onSocketMessage('study_members', {
                type: 'study_members',
                studyId: 'study001',
                members: { owner: 'write', writer: 'read' },
                revision: 1,
            }),
        ).toBe(true);

        expect(membersChanged).toHaveBeenCalledWith({ owner: 'write', writer: 'read' });
        expect(reload).toHaveBeenCalledWith('member_access_changed');
        extension.setDescription('must stay local');
        expect(ctrl.doSend).not.toHaveBeenCalled();
    });

    test('reloads when read membership changes even though write access stays false', () => {
        const addedCtrl = makeCtrl();
        addedCtrl.username = 'reader';
        const addedReload = jest.fn();
        const added = new StudyAnalysisExtension(addedCtrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            onReloadRequired: addedReload,
        });
        added.onSocketOpen();

        expect(
            added.onSocketMessage('study_members', {
                type: 'study_members',
                studyId: 'study001',
                members: { owner: 'write', reader: 'read' },
                revision: 1,
            }),
        ).toBe(true);
        expect(addedReload).toHaveBeenCalledWith('member_access_changed');

        const removedCtrl = makeCtrl();
        removedCtrl.username = 'reader';
        const removedReload = jest.fn();
        const removed = new StudyAnalysisExtension(removedCtrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            memberRole: 'read',
            onReloadRequired: removedReload,
        });
        removed.onSocketOpen();

        expect(
            removed.onSocketMessage('study_members', {
                type: 'study_members',
                studyId: 'study001',
                members: { owner: 'write' },
                revision: 1,
            }),
        ).toBe(true);
        expect(removedReload).toHaveBeenCalledWith('member_access_changed');
    });

    test('does not reload when only another Study member changes', () => {
        const ctrl = makeCtrl();
        ctrl.username = 'reader';
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            memberRole: 'read',
            onReloadRequired: reload,
        });
        extension.onSocketOpen();

        expect(
            extension.onSocketMessage('study_members', {
                type: 'study_members',
                studyId: 'study001',
                members: { owner: 'write', reader: 'read', contributor: 'write' },
                revision: 1,
            }),
        ).toBe(true);
        expect(reload).not.toHaveBeenCalled();
    });

    test('updates the Study like count from room broadcasts', () => {
        const likesChanged = jest.fn();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(makeCtrl(), {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onLikesChanged: likesChanged,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_likes', {
                type: 'study_likes',
                studyId: 'study001',
                likes: 7,
            }),
        ).toBe(true);

        expect(likesChanged).toHaveBeenCalledWith(7);
        expect(reload).not.toHaveBeenCalled();
    });

    test('updates Study topics from room broadcasts', () => {
        const topicsChanged = jest.fn();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(makeCtrl(), {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onTopicsChanged: topicsChanged,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_topics', {
                type: 'study_topics',
                studyId: 'study001',
                topics: ['King pawn', 'Endgame'],
            }),
        ).toBe(true);

        expect(topicsChanged).toHaveBeenCalledWith(['King pawn', 'Endgame']);
        expect(reload).not.toHaveBeenCalled();

        expect(
            extension.onSocketMessage('study_topics', {
                type: 'study_topics',
                studyId: 'study001',
                topics: ['valid', 7],
            }),
        ).toBe(true);
        expect(reload).toHaveBeenCalledWith('invalid_topics');
    });

    test('applies a remote node incrementally and advances the revision', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
        });

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'Remote1',
            revision: 1,
            changed: true,
            parentPath: '',
            path: 'StudyNode1',
            node: e4Node(),
        });

        expect(ctrl.analysisTree.root.children[0].id).toBe('StudyNode1');
        expect(ctrl.steps.map((step: Step) => step.move)).toEqual([undefined, 'e2e4']);
        expect(extension.revision).toBe(1);
        expect(updateMovelistMock).toHaveBeenCalled();
        expect(reload).not.toHaveBeenCalled();
    });

    test('merges a remote sibling while a local add is pending and accepts canonical ordering', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
            opIdFactory: () => 'LocalOp1',
        });
        const local = e4Node();
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', local);
        extension.onSocketOpen();
        extension.onNodeAdded('', ctrl.analysisTree.root.children[0]);

        const remote: StudyTreeNodeDto = {
            ...e4Node(),
            id: 'StudyNode2',
            order: 0,
            move: 'd2d4',
            fen: 'd4 b - - 0 1',
            san: 'd4',
            sanSAN: 'd4',
        };
        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteOp',
            revision: 1,
            changed: true,
            parentPath: '',
            path: 'StudyNode2',
            node: remote,
        });

        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['StudyNode2', 'StudyNode1']);
        expect(extension.revision).toBe(1);
        expect(extension.pendingCount).toBe(1);
        expect(reload).not.toHaveBeenCalled();

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalOp1',
            revision: 2,
            changed: true,
            parentPath: '',
            path: 'StudyNode1',
            node: { ...local, order: 1 },
        });

        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['StudyNode2', 'StudyNode1']);
        expect(extension.revision).toBe(2);
        expect(extension.pendingCount).toBe(0);
        expect(reload).not.toHaveBeenCalled();
    });

    test('reconciles a duplicate move id and continues queued descendant mutations', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const opIds = ['LocalE4Op', 'LocalE5Op', 'LocalNote'];
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
            opIdFactory: () => opIds.shift()!,
        });
        const localE4: StudyTreeNodeDto = { ...e4Node(), id: 'LocalNode1' };
        const localE5: StudyTreeNodeDto = {
            id: 'LocalNode2',
            parentId: 'LocalNode1',
            order: 0,
            move: 'e7e5',
            fen: 'e5 w - - 0 2',
            turnColor: 'white',
            check: false,
            san: 'e5',
            sanSAN: 'e5',
        };
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', localE4);
        addStudyNodeToAnalysisTree(ctrl.analysisTree, 'LocalNode1', localE5);
        ctrl.analysisPath = 'LocalNode1.LocalNode2';

        extension.onSocketOpen();
        extension.onNodeAdded('', ctrl.analysisTree.root.children[0]);
        extension.onNodeAdded('LocalNode1', ctrl.analysisTree.root.children[0].children[0]);
        extension.setComment('Comment001', 'Keep this note', 'LocalNode1.LocalNode2');

        expect(ctrl.doSend).toHaveBeenCalledTimes(1);
        expect(extension.pendingCount).toBe(3);

        const canonicalE4: StudyTreeNodeDto = { ...e4Node(), id: 'CanonNode1' };
        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteE4Op',
            revision: 1,
            changed: true,
            parentPath: '',
            path: 'CanonNode1',
            node: canonicalE4,
        });
        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['CanonNode1', 'LocalNode1']);

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalE4Op',
            revision: 1,
            changed: false,
            parentPath: '',
            path: 'CanonNode1',
            move: 'e2e4',
            node: canonicalE4,
        });

        expect(reload).not.toHaveBeenCalled();
        expect(extension.pendingCount).toBe(2);
        expect(ctrl.analysisTree.root.children.map((node: any) => node.id)).toEqual(['CanonNode1']);
        expect(ctrl.analysisTree.byPath.has('LocalNode1')).toBe(false);
        expect(ctrl.analysisTree.byPath.has('LocalNode1.LocalNode2')).toBe(false);
        expect(ctrl.analysisTree.byPath.get('CanonNode1.LocalNode2')?.step.move).toBe('e7e5');
        expect(ctrl.analysisPath).toBe('CanonNode1.LocalNode2');
        expect(ctrl.doSend).toHaveBeenCalledTimes(2);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalE5Op',
            expectedRevision: 1,
            parentPath: 'CanonNode1',
            move: 'e7e5',
            nodeId: 'LocalNode2',
        });

        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalE5Op',
            revision: 2,
            changed: true,
            parentPath: 'CanonNode1',
            path: 'CanonNode1.LocalNode2',
            move: 'e7e5',
            node: { ...localE5, parentId: 'CanonNode1' },
        });

        expect(ctrl.doSend).toHaveBeenCalledTimes(3);
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_comment',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalNote',
            expectedRevision: 2,
            path: 'CanonNode1.LocalNode2',
            commentId: 'Comment001',
            text: 'Keep this note',
        });
        expect(ctrl.analysisTree.byPath.get('CanonNode1.LocalNode2')?.annotations?.comments).toEqual([
            { id: 'Comment001', author: 'owner', text: 'Keep this note' },
        ]);

        extension.onSocketMessage('study_set_comment', {
            type: 'study_set_comment',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalNote',
            revision: 3,
            changed: true,
            path: 'CanonNode1.LocalNode2',
            annotations: {
                shapes: [],
                comments: [{ id: 'Comment001', author: 'owner', text: 'Keep this note' }],
                nags: [],
            },
        });

        expect(extension.pendingCount).toBe(0);
        expect(extension.revision).toBe(3);
        expect(reload).not.toHaveBeenCalled();
    });

    test('remaps queued gamebook text when a duplicate optimistic node is canonicalized', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const opIds = ['LocalE4Op', 'LocalLesson'];
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
            opIdFactory: () => opIds.shift()!,
        });
        const local: StudyTreeNodeDto = { ...e4Node(), id: 'LocalNode1' };
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', local);
        ctrl.analysisPath = 'LocalNode1';

        extension.onSocketOpen();
        extension.onNodeAdded('', ctrl.analysisTree.root.children[0]);
        extension.setGamebook('deviation', 'Try a different move', 'LocalNode1');

        expect(extension.pendingCount).toBe(2);
        expect(ctrl.analysisTree.byPath.get('LocalNode1')?.gamebook).toEqual({
            deviation: 'Try a different move',
        });

        const canonical: StudyTreeNodeDto = { ...e4Node(), id: 'CanonNode1' };
        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'RemoteE4Op',
            revision: 1,
            changed: true,
            parentPath: '',
            path: 'CanonNode1',
            node: canonical,
        });
        extension.onSocketMessage('study_add_node', {
            type: 'study_add_node',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalE4Op',
            revision: 1,
            changed: false,
            parentPath: '',
            path: 'CanonNode1',
            move: 'e2e4',
            node: canonical,
        });

        expect(reload).not.toHaveBeenCalled();
        expect(extension.pendingCount).toBe(1);
        expect(ctrl.analysisTree.byPath.has('LocalNode1')).toBe(false);
        expect(ctrl.analysisTree.byPath.get('CanonNode1')?.gamebook).toEqual({
            deviation: 'Try a different move',
        });
        expect(ctrl.analysisPath).toBe('CanonNode1');
        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_gamebook',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalLesson',
            expectedRevision: 1,
            path: 'CanonNode1',
            field: 'deviation',
            value: 'Try a different move',
        });

        extension.onSocketMessage('study_set_gamebook', {
            type: 'study_set_gamebook',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'LocalLesson',
            revision: 2,
            changed: true,
            path: 'CanonNode1',
            gamebook: { deviation: 'Try a different move' },
        });
        expect(extension.pendingCount).toBe(0);
        expect(extension.revision).toBe(2);
    });

    test('verifies the initial HTTP snapshot before sending queued mutations', async () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            snapshotToken: 'snapshot-a',
            roomSnapshotToken: 'room-a',
            onReloadRequired: reload,
            opIdFactory: () => 'CommentOp1',
            syncIdFactory: () => 'SyncOp1',
        });

        extension.onSocketOpen();
        expect(ctrl.doSend).toHaveBeenCalledWith({
            type: 'study_sync_chapter',
            studyId: 'study001',
            chapterId: 'chapter1',
            requestId: 'SyncOp1',
        });

        extension.setComment('Comment001', 'Queued before sync');
        expect(ctrl.doSend).toHaveBeenCalledTimes(1);

        extension.onSocketMessage('study_chapter_sync', {
            type: 'study_chapter_sync',
            studyId: 'study001',
            chapterId: 'chapter1',
            requestId: 'SyncOp1',
            revision: 0,
            snapshotToken: 'snapshot-a',
            roomSnapshotToken: 'room-a',
        });
        await Promise.resolve();

        expect(ctrl.doSend).toHaveBeenLastCalledWith({
            type: 'study_set_comment',
            studyId: 'study001',
            chapterId: 'chapter1',
            clientOpId: 'CommentOp1',
            expectedRevision: 0,
            path: '',
            commentId: 'Comment001',
            text: 'Queued before sync',
        });
        expect(reload).not.toHaveBeenCalled();
    });

    test('reloads instead of sending queued mutations when the initial snapshot is stale', async () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            snapshotToken: 'snapshot-old',
            roomSnapshotToken: 'room-old',
            onReloadRequired: reload,
            opIdFactory: () => 'CommentOp1',
            syncIdFactory: () => 'SyncOp1',
        });

        extension.onSocketOpen();
        extension.setComment('Comment001', 'Must not send stale');
        extension.onSocketMessage('study_chapter_sync', {
            type: 'study_chapter_sync',
            studyId: 'study001',
            chapterId: 'chapter1',
            requestId: 'SyncOp1',
            revision: 1,
            snapshotToken: 'snapshot-new',
            roomSnapshotToken: 'room-old',
        });
        await Promise.resolve();

        expect(reload).toHaveBeenCalledWith('snapshot_stale');
        expect(ctrl.doSend).toHaveBeenCalledTimes(1);
    });

    test('reloads when Study-wide state changed although the chapter snapshot still matches', async () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            snapshotToken: 'chapter-a',
            roomSnapshotToken: 'room-old',
            onReloadRequired: reload,
            syncIdFactory: () => 'SyncOp1',
        });

        extension.onSocketOpen();
        extension.onSocketMessage('study_chapter_sync', {
            type: 'study_chapter_sync',
            studyId: 'study001',
            chapterId: 'chapter1',
            requestId: 'SyncOp1',
            revision: 0,
            snapshotToken: 'chapter-a',
            roomSnapshotToken: 'room-new',
        });
        await Promise.resolve();

        expect(reload).toHaveBeenCalledWith('snapshot_stale');
    });

    test('initial room acknowledgement rejects stale Study-wide HTTP state', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            snapshotToken: 'chapter-a',
            roomSnapshotToken: 'room-old',
            onReloadRequired: reload,
            syncIdFactory: () => 'SyncOp1',
        });

        extension.onSocketOpen();
        extension.onSocketMessage('study_user_connected', {
            type: 'study_user_connected',
            studyId: 'study001',
            roomSnapshotToken: 'room-new',
        });

        expect(reload).toHaveBeenCalledWith('study_snapshot_stale');
    });

    test('reloads after a real websocket reconnect because broadcasts may have been missed', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: reload,
        });

        extension.onSocketOpen();
        extension.onSocketReconnect();
        extension.onSocketOpen();

        expect(reload).toHaveBeenCalledWith('reconnected');
    });

    test('ignores broadcasts for another chapter in the same Study room', () => {
        const ctrl = makeCtrl();
        const reload = jest.fn();
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 3,
            onReloadRequired: reload,
        });

        expect(
            extension.onSocketMessage('study_delete_node', {
                type: 'study_delete_node',
                studyId: 'study001',
                chapterId: 'chapter2',
                clientOpId: 'RemoteOp',
                revision: 99,
                changed: true,
                path: 'StudyNode1',
            }),
        ).toBe(true);
        expect(extension.revision).toBe(3);
        expect(reload).not.toHaveBeenCalled();
    });

    test('keeps generic mainline steps aligned after a Study promotion', () => {
        const ctrl = makeCtrl();
        const e4 = e4Node();
        const d4: StudyTreeNodeDto = {
            ...e4,
            id: 'StudyNode2',
            order: 1,
            move: 'd2d4',
            fen: 'd4 b - - 0 1',
            san: 'd4',
            sanSAN: 'd4',
        };
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4);
        addStudyNodeToAnalysisTree(ctrl.analysisTree, '', d4);
        ctrl.steps = [ctrl.analysisTree.root.step, ctrl.analysisTree.root.children[0].step];
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
            opIdFactory: () => 'PromoteOp',
        });

        promoteNodePath(ctrl.analysisTree, 'StudyNode2', true);
        extension.onVariationPromoted('StudyNode2', true);

        expect(ctrl.steps.map((step: Step) => step.move)).toEqual([undefined, 'd2d4']);
        expect(ctrl.analysisTree.root.children[0].mainlinePly).toBe(1);
        expect(ctrl.analysisTree.root.children[1].mainlinePly).toBeUndefined();
        expect(ctrl.recordedMainlinePly).toBeUndefined();
    });
});

test('chapter navigation waits until the pending mutation is acknowledged', async () => {
    const extension = new StudyAnalysisExtension(makeCtrl(), {
        studyId: 'study001',
        chapterId: 'chapter1',
        revision: 0,
        onReloadRequired: jest.fn(),
        opIdFactory: () => 'CommentOp1',
    });
    extension.onSocketOpen();
    extension.setComment('Comment001', 'Before switching');
    const saved = jest.fn();
    const idle = extension.whenIdle().then(saved);
    await Promise.resolve();
    expect(saved).not.toHaveBeenCalled();
    extension.onSocketMessage('study_set_comment', {
        type: 'study_set_comment',
        studyId: 'study001',
        chapterId: 'chapter1',
        clientOpId: 'CommentOp1',
        revision: 1,
        changed: true,
        path: '',
        annotations: {
            shapes: [],
            comments: [{ id: 'Comment001', author: 'owner', text: 'Before switching' }],
            nags: [],
        },
    });
    await idle;
    expect(saved).toHaveBeenCalledTimes(1);
});

test('unacknowledged edits prevent a chapter switch after the save timeout', async () => {
    jest.useFakeTimers();
    try {
        const extension = new StudyAnalysisExtension(makeCtrl(), {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            onReloadRequired: jest.fn(),
        });
        extension.setComment('Comment001', 'Offline edit');
        const assertion = expect(extension.whenIdle(100)).rejects.toThrow('could not be saved');
        jest.advanceTimersByTime(100);
        await assertion;
        expect(extension.pendingCount).toBe(1);
    } finally {
        jest.useRealTimers();
    }
});

test('conceal reader extension blocks hidden navigation until play or reveal', () => {
    const ctrl = makeCtrl();
    ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
    const e5: StudyTreeNodeDto = {
        id: 'StudyNode2',
        parentId: 'StudyNode1',
        order: 0,
        move: 'e7e5',
        fen: 'e5 w - - 0 1',
        turnColor: 'white',
        check: false,
        san: 'e5',
        sanSAN: 'e5',
    };
    const policy = studySessionPolicy({
        mode: 'conceal',
        canWrite: false,
        computerAllowed: true,
        savedRecording: true,
        savedSynchronization: false,
        activeGame: false,
    });
    const visibleShape = { orig: 'e4', dest: 'e5', brush: 'red' as const };
    const visible = {
        ...e4Node(),
        annotations: { shapes: [visibleShape], comments: [], nags: [] },
    };
    const extension = new StudyAnalysisExtension(ctrl, {
        studyId: 'study001',
        chapterId: 'chapter1',
        revision: 0,
        tree: { nodes: [visible, e5] },
        concealPly: 1,
        policy,
        writable: false,
        onReloadRequired: jest.fn(),
    });
    extension.onInitialBoardLoaded();
    ctrl.analysisPath = 'StudyNode1';
    extension.onPathChanged();
    const hidden = ctrl.analysisTree.byPath.get('StudyNode1.StudyNode2');

    expect(ctrl.chessground.setShapes).toHaveBeenLastCalledWith([visibleShape]);
    expect(hidden).toBeDefined();
    expect(extension.isTreeNodeVisible(hidden)).toBe(false);
    expect(extension.canActivatePath(hidden.path, 'user-navigation')).toBe(false);
    expect(extension.canActivatePath(hidden.path, 'played-move')).toBe(true);
    expect(extension.allowTreeContextMenu()).toBe(false);

    extension.onSocketMessage('study_conceal', {
        type: 'study_conceal',
        studyId: 'study001',
        chapterId: 'chapter1',
        path: hidden.path,
        concealPly: 2,
        revision: 1,
    });
    expect(extension.isTreeNodeVisible(hidden)).toBe(true);
    expect(extension.canActivatePath(hidden.path, 'user-navigation')).toBe(true);
});

test('conceal reader clears persisted evaluations from hidden sidelines and never records local guesses', () => {
    const ctrl = makeCtrl();
    ctrl.tree = { loadAnalysisTree: jest.fn((tree: unknown) => (ctrl.analysisTree = tree)) };
    const sideline: StudyTreeNodeDto = {
        ...e4Node(),
        id: 'StudyNode2',
        order: 1,
        move: 'd2d4',
        fen: 'd4 b - - 0 1',
        san: 'd4',
        sanSAN: 'd4',
        eval: { cp: 73 },
    };
    const mainline = { ...e4Node(), eval: { cp: 42 } };
    const policy = studySessionPolicy({
        mode: 'conceal',
        canWrite: false,
        computerAllowed: true,
        savedRecording: true,
        savedSynchronization: false,
        activeGame: false,
    });
    const extension = new StudyAnalysisExtension(ctrl, {
        studyId: 'study001',
        chapterId: 'chapter1',
        revision: 0,
        tree: { nodes: [mainline, sideline] },
        concealPly: 0,
        policy,
        writable: false,
        onReloadRequired: jest.fn(),
    });
    extension.onInitialBoardLoaded();

    for (const node of ctrl.analysisTree.byPath.values()) {
        expect(node.step.analysis).toBeUndefined();
        expect(node.step.ceval).toBeUndefined();
        expect(node.step.scoreStr).toBeUndefined();
    }

    extension.onSocketOpen();
    ctrl.doSend.mockClear();
    const attempted = ctrl.analysisTree.byPath.get('StudyNode1')!;
    extension.onNodeAdded('', attempted);
    expect(ctrl.doSend).not.toHaveBeenCalled();
});

test.each([
    ['normal', true, undefined, true, false],
    ['gamebook', true, undefined, true, true],
    ['gamebook', true, 'analysis', true, true],
    ['gamebook', true, 'preview', false, false],
    ['gamebook', false, undefined, false, false],
    ['practice', true, undefined, false, false],
    ['practice', true, 'analysis', false, false],
    ['conceal', true, undefined, false, false],
    ['conceal', false, undefined, false, false],
] as const)(
    'fork drawing policy for %s writer=%s override=%s follows Lichess allowLines',
    (mode, canWrite, override, allowed, gamebook) => {
        const policy = studySessionPolicy({
            mode,
            canWrite,
            override,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
        });
        const extension = new StudyAnalysisExtension(makeCtrl(), {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: canWrite,
            policy,
            onReloadRequired: jest.fn(),
        });
        expect(extension.allowVariationArrows()).toBe(allowed);
        expect(extension.isGamebookEditor()).toBe(gamebook);
    },
);

test('local and remote NAG edits and clears refresh current board annotations', () => {
    const ctrl = makeCtrl();
    ctrl.setAutoShapes = jest.fn();
    addStudyNodeToAnalysisTree(ctrl.analysisTree, '', e4Node());
    ctrl.analysisPath = 'StudyNode1';
    const extension = new StudyAnalysisExtension(ctrl, {
        studyId: 'study001',
        chapterId: 'chapter1',
        revision: 0,
        writable: true,
        recording: false,
        onReloadRequired: jest.fn(),
    });
    extension.onSocketOpen();
    ctrl.setAutoShapes.mockClear();
    extension.setNags([1]);
    expect(ctrl.setAutoShapes).toHaveBeenCalledTimes(1);
    extension.clearAnnotations();
    expect(ctrl.setAutoShapes).toHaveBeenCalledTimes(2);
    ctrl.setAutoShapes.mockClear();
    extension.onSocketMessage('study_set_nags', {
        type: 'study_set_nags',
        studyId: 'study001',
        chapterId: 'chapter1',
        clientOpId: 'RemoteNags1',
        revision: 1,
        changed: true,
        path: 'StudyNode1',
        annotations: { shapes: [], comments: [], nags: [14] },
    });
    expect(ctrl.setAutoShapes).toHaveBeenCalledTimes(1);
    expect(extension.annotationState.annotations.nags).toEqual([14]);
});

test.each(['practice', 'gamebook'] as const)(
    '%s playback suppresses authored glyphs before a runtime attaches',
    mode => {
        const ctrl = makeCtrl();
        const policy = studySessionPolicy({
            mode,
            canWrite: false,
            computerAllowed: true,
            savedRecording: true,
            savedSynchronization: true,
            activeGame: false,
        });
        const extension = new StudyAnalysisExtension(ctrl, {
            studyId: 'study001',
            chapterId: 'chapter1',
            revision: 0,
            writable: false,
            policy,
            onReloadRequired: jest.fn(),
        });
        expect(extension.areTreeNodeAnnotationsVisible(ctrl.analysisTree.root)).toBe(false);
    },
);
