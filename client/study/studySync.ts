import type { DrawShape } from 'chessgroundx/draw';

import { updateMovelist } from '../movelist';
import {
    deleteNodePath,
    forceVariationAt,
    nodeAtPath,
    parentPath,
    promoteNodePath,
    type AnalysisAnnotations,
    type AnalysisTreeNode,
} from '../analysis/analysisTree';
import type { AnalysisController } from '../analysis/analysisCtrl';
import type { Ceval } from '../messages';
import type {
    AnalysisExtension,
    AnalysisExtensionFactory,
    AnalysisMoveApplication,
    AnalysisNavigationOrigin,
    AnalysisPositionChange,
} from '../analysis/analysisExtension';
import type { JSONObject, StudyChapterMode, StudyChapterPreview, StudyChapterStatus, StudyServerEval } from '../types';
import {
    mergeStudyNodeIntoAnalysisTree,
    mergeStudyTreeIntoAnalysisTree,
    reconcileStudyNodeIntoAnalysisTree,
    analysisAnnotationsFromStudy,
    analysisTreeFromStudy,
    isStudyNodeId,
    newStudyNodeId,
    parseStudyAnnotations,
    parseStudyGamebook,
    refreshStudyMainline,
    studyAnnotationsFromAnalysis,
    studyTreeFromAnalysisTree,
    type StudyAnnotationsDto,
    type StudyGamebookDto,
    type StudyTreeDto,
    type StudyTreeNodeDto,
} from './studyTree';
import { renderStudyChapterPgn, type StudyPgnChapterData, type StudyPgnContext } from './studyPgn';
import type { StudySessionPolicy } from './studyMode';
import { StudyConcealController } from './studyConceal';
import type { StudyGamebookPlayback } from './studyGamebookPlayback';
import type { StudyPracticeSession } from './studyPractice';

const STUDY_SOCKET_TYPES = new Set([
    'study_user_connected',
    'study_chapter_sync',
    'study_members',
    'study_likes',
    'study_topics',
    'study_chapters',
    'study_chapter_content',
    'study_position',
    'study_conceal',
    'study_analysis_progress',
    'study_analysis_unavailable',
    'study_add_node',
    'study_delete_node',
    'study_promote_variation',
    'study_force_variation',
    'study_set_shapes',
    'study_set_comment',
    'study_set_nags',
    'study_clear_annotations',
    'study_set_gamebook',
    'study_set_description',
    'study_set_tags',
    'study_error',
    'study_reload',
]);

const POSITION_ANNOTATION_MUTATIONS = new Set([
    'study_set_shapes',
    'study_set_comment',
    'study_set_nags',
    'study_clear_annotations',
]);

type StudyMutationType =
    | 'study_add_node'
    | 'study_delete_node'
    | 'study_promote_variation'
    | 'study_force_variation'
    | 'study_set_shapes'
    | 'study_set_comment'
    | 'study_set_nags'
    | 'study_clear_annotations'
    | 'study_set_gamebook'
    | 'study_set_description'
    | 'study_set_tags';

const GAMEBOOK_SCRIPT_MUTATIONS = new Set<StudyMutationType>([
    'study_add_node',
    'study_delete_node',
    'study_promote_variation',
    'study_set_comment',
    'study_clear_annotations',
    'study_set_gamebook',
]);

type PendingMutation = {
    type: StudyMutationType;
    chapterId: string;
    clientOpId: string;
    body: JSONObject;
    sent: boolean;
};

export type StudyMemberRole = 'read' | 'write';

export interface StudyAnnotationState {
    path: string;
    annotations: StudyAnnotationsDto;
    description: string;
    tags: Record<string, string>;
}

export interface StudySyncOptions {
    socket?: AnalysisExtension['socket'];
    studyId: string;
    chapterId: string;
    revision: number;
    snapshotToken?: string;
    roomSnapshotToken?: string;
    snapshotVerified?: boolean;
    tree?: StudyTreeDto;
    orientation?: 'white' | 'black';
    mode?: StudyChapterMode;
    description?: string;
    tags?: Record<string, string>;
    studyName?: string;
    chapterName?: string;
    chapterOrder?: number;
    owner?: string;
    home?: string;
    variant?: string;
    chess960?: boolean;
    initialFen?: string;
    variantIni?: string;
    createdAt?: string;
    serverEval?: StudyServerEval | null;
    onInitialTreeLoaded?: () => void;
    onAnnotationStateChanged?: (state: StudyAnnotationState) => void;
    onReloadRequired?: (reason: string) => void;
    memberRole?: StudyMemberRole;
    onMembersChanged?: (members: Record<string, StudyMemberRole>) => void;
    onLikesChanged?: (likes: number) => void;
    onTopicsChanged?: (topics: string[]) => void;
    onChaptersChanged?: (chapters: StudyChapterPreview[], sharedChapter: string, sharedPath: string) => void;
    onLocalPathChanged?: (path: string, origin: AnalysisNavigationOrigin) => void;
    onSharedPositionChanged?: (chapterId: string, path: string) => void;
    onConcealChanged?: (concealPly: number, revision: number) => void;
    concealPly?: number;
    onServerEvalChanged?: (serverEval: StudyServerEval | undefined) => void;
    onServerAnalysisVisibilityChanged?: () => void;
    onServerAnalysisUnavailable?: (reason: string) => void;
    onGamebookScriptChanged?: () => void;
    onOrientationChanged?: (orientation: 'white' | 'black') => void;
    opIdFactory?: () => string;
    syncIdFactory?: () => string;
    contextMenuActions?: AnalysisExtension['contextMenuActions'];
    renderMoveListEnd?: AnalysisExtension['renderMoveListEnd'];
    renderMoveListFooter?: AnalysisExtension['renderMoveListFooter'];
    writable?: boolean;
    recording?: boolean;
    policy?: StudySessionPolicy;
    rootOnlyPreview?: boolean;
}

function record(message: unknown): Record<string, unknown> | undefined {
    if (message === null || typeof message !== 'object' || Array.isArray(message)) return undefined;
    return message as Record<string, unknown>;
}

function asStringRecord(value: unknown): Record<string, string> | undefined {
    const data = record(value);
    if (!data) return undefined;
    const result: Record<string, string> = {};
    for (const [key, entry] of Object.entries(data)) {
        if (typeof entry !== 'string') return undefined;
        result[key] = entry;
    }
    return result;
}

function remapPathPrefix(path: string, fromPath: string, toPath: string): string {
    if (path === fromPath) return toPath;
    return path.startsWith(`${fromPath}.`) ? `${toPath}${path.slice(fromPath.length)}` : path;
}

function asStringArray(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) return undefined;
    const result: string[] = [];
    for (const entry of value) {
        if (typeof entry !== 'string' || !entry) return undefined;
        result.push(entry);
    }
    return result;
}

function asStudyChapterStatus(value: unknown): StudyChapterStatus | undefined {
    return value === '1-0' || value === '0-1' || value === '½-½' || value === '*' ? value : undefined;
}

function asStudyChapterPreviews(value: unknown): StudyChapterPreview[] | undefined {
    if (!Array.isArray(value) || value.length === 0) return undefined;
    const chapters: StudyChapterPreview[] = [];
    const ids = new Set<string>();
    for (const entry of value) {
        const chapter = record(entry);
        const mode: StudyChapterMode | undefined =
            chapter?.mode === undefined
                ? 'normal'
                : chapter.mode === 'normal' ||
                    chapter.mode === 'practice' ||
                    chapter.mode === 'conceal' ||
                    chapter.mode === 'gamebook'
                  ? chapter.mode
                  : undefined;
        if (
            !chapter ||
            typeof chapter.id !== 'string' ||
            !chapter.id ||
            ids.has(chapter.id) ||
            typeof chapter.name !== 'string' ||
            !Number.isInteger(chapter.order) ||
            (chapter.order as number) < 1 ||
            (chapter.orientation !== 'white' && chapter.orientation !== 'black') ||
            !mode ||
            (chapter.concealPly !== undefined &&
                (!Number.isInteger(chapter.concealPly) || (chapter.concealPly as number) < 0)) ||
            (mode !== 'conceal' && chapter.concealPly !== undefined) ||
            (chapter.status !== undefined && asStudyChapterStatus(chapter.status) === undefined) ||
            (chapter.descriptionPinned !== undefined && typeof chapter.descriptionPinned !== 'boolean')
        )
            return undefined;
        ids.add(chapter.id);
        chapters.push({
            id: chapter.id,
            name: chapter.name,
            order: chapter.order as number,
            orientation: chapter.orientation,
            mode,
            ...(chapter.status === undefined ? {} : { status: asStudyChapterStatus(chapter.status) }),
            ...(mode === 'conceal' ? { concealPly: (chapter.concealPly as number | undefined) ?? 0 } : {}),
            ...(chapter.descriptionPinned === undefined ? {} : { descriptionPinned: chapter.descriptionPinned }),
        });
    }
    return chapters;
}

function asStudyMembers(value: unknown): Record<string, 'read' | 'write'> | undefined {
    const data = record(value);
    if (!data) return undefined;
    const result: Record<string, 'read' | 'write'> = {};
    for (const [username, role] of Object.entries(data)) {
        if (!username || (role !== 'read' && role !== 'write')) return undefined;
        result[username] = role;
    }
    return result;
}

function asStudyServerEval(value: unknown): StudyServerEval | undefined {
    const data = record(value);
    if (!data || typeof data.path !== 'string' || typeof data.done !== 'boolean') return undefined;
    if (data.pending !== undefined && typeof data.pending !== 'boolean') return undefined;
    if (typeof data.requestedAt !== 'string' || !Array.isArray(data.analysis)) return undefined;
    const analysis: StudyServerEval['analysis'] = [];
    for (const raw of data.analysis) {
        if (raw === null) {
            analysis.push(null);
            continue;
        }
        const step = record(raw);
        const score = record(step?.s);
        if (!step || !score) return undefined;
        if (score.cp !== undefined && (typeof score.cp !== 'number' || !Number.isFinite(score.cp))) return undefined;
        if (score.mate !== undefined && (typeof score.mate !== 'number' || !Number.isFinite(score.mate)))
            return undefined;
        if (score.cp === undefined && score.mate === undefined) return undefined;
        if (step.d !== undefined && (!Number.isInteger(step.d) || (step.d as number) < 0)) return undefined;
        if (step.p !== undefined && typeof step.p !== 'string') return undefined;
        analysis.push({
            s: {
                ...(score.cp !== undefined ? { cp: score.cp as number } : {}),
                ...(score.mate !== undefined ? { mate: score.mate as number } : {}),
            },
            ...(step.d !== undefined ? { d: step.d as number } : {}),
            ...(step.p !== undefined ? { p: step.p as string } : {}),
        });
    }
    return {
        path: data.path,
        done: data.done,
        ...(data.pending !== undefined ? { pending: data.pending } : {}),
        requestedAt: data.requestedAt,
        analysis,
    };
}

function asStudyTreeNode(value: unknown): StudyTreeNodeDto | undefined {
    const node = record(value);
    if (!node) return undefined;
    if (!isStudyNodeId(node.id)) return undefined;
    if (node.parentId !== null && !isStudyNodeId(node.parentId)) return undefined;
    if (!Number.isInteger(node.order) || (node.order as number) < 0) return undefined;
    if (typeof node.move !== 'string' || !node.move) return undefined;
    if (typeof node.fen !== 'string' || !node.fen) return undefined;
    if (node.turnColor !== 'white' && node.turnColor !== 'black') return undefined;
    if (typeof node.check !== 'boolean') return undefined;
    if (node.san !== undefined && typeof node.san !== 'string') return undefined;
    if (node.sanSAN !== undefined && typeof node.sanSAN !== 'string') return undefined;
    if (node.forceVariation !== undefined && typeof node.forceVariation !== 'boolean') return undefined;
    let clocks: StudyTreeNodeDto['clocks'];
    if (node.clocks !== undefined) {
        if (
            !Array.isArray(node.clocks) ||
            node.clocks.length !== 2 ||
            node.clocks.some(value => typeof value !== 'number' || !Number.isFinite(value) || value < 0)
        )
            return undefined;
        clocks = [node.clocks[0] as number, node.clocks[1] as number];
    }

    let evalScore: StudyTreeNodeDto['eval'];
    if (node.eval !== undefined) {
        const rawEval = record(node.eval);
        if (!rawEval) return undefined;
        if (rawEval.cp !== undefined && !Number.isInteger(rawEval.cp)) return undefined;
        if (rawEval.mate !== undefined && !Number.isInteger(rawEval.mate)) return undefined;
        if (rawEval.cp === undefined && rawEval.mate === undefined) return undefined;
        evalScore = {
            ...(rawEval.cp !== undefined ? { cp: rawEval.cp as number } : {}),
            ...(rawEval.mate !== undefined ? { mate: rawEval.mate as number } : {}),
        };
    }

    let annotations: StudyAnnotationsDto | undefined;
    if (node.annotations !== undefined) {
        try {
            annotations = parseStudyAnnotations(node.annotations);
        } catch {
            return undefined;
        }
    }
    let gamebook: StudyGamebookDto | undefined;
    if (node.gamebook !== undefined) {
        try {
            gamebook = parseStudyGamebook(node.gamebook);
        } catch {
            return undefined;
        }
    }

    return {
        id: node.id,
        parentId: node.parentId,
        order: node.order as number,
        move: node.move,
        fen: node.fen,
        turnColor: node.turnColor,
        check: node.check,
        san: node.san as string | undefined,
        sanSAN: node.sanSAN as string | undefined,
        forceVariation: node.forceVariation as boolean | undefined,
        clocks,
        annotations,
        gamebook,
        eval: evalScore,
    };
}

function asStudyTree(value: unknown): StudyTreeDto | undefined {
    const tree = record(value);
    if (!tree || !Array.isArray(tree.nodes)) return undefined;
    const nodes: StudyTreeNodeDto[] = [];
    const ids = new Set<string>();
    for (const rawNode of tree.nodes) {
        const node = asStudyTreeNode(rawNode);
        if (!node || ids.has(node.id)) return undefined;
        ids.add(node.id);
        nodes.push(node);
    }

    let rootAnnotations: StudyAnnotationsDto | undefined;
    if (tree.rootAnnotations !== undefined) {
        try {
            rootAnnotations = parseStudyAnnotations(tree.rootAnnotations);
        } catch {
            return undefined;
        }
    }
    let rootGamebook: StudyGamebookDto | undefined;
    if (tree.rootGamebook !== undefined) {
        try {
            rootGamebook = parseStudyGamebook(tree.rootGamebook);
        } catch {
            return undefined;
        }
    }
    return {
        nodes,
        ...(rootAnnotations ? { rootAnnotations } : {}),
        ...(rootGamebook ? { rootGamebook } : {}),
    };
}

function emptyAnnotations(): StudyAnnotationsDto {
    return { shapes: [], comments: [], nags: [] };
}

function cloneAnnotations(value: AnalysisAnnotations | undefined): StudyAnnotationsDto {
    return studyAnnotationsFromAnalysis(value) ?? emptyAnnotations();
}

function withGamebookField(
    value: StudyGamebookDto | undefined,
    field: 'hint' | 'deviation',
    rawValue: string,
): StudyGamebookDto | undefined {
    const next: StudyGamebookDto = { ...value };
    const text = rawValue.trim();
    if (text) next[field] = text;
    else delete next[field];
    return next.hint === undefined && next.deviation === undefined ? undefined : next;
}

function gamebookOrUndefined(value: StudyGamebookDto): StudyGamebookDto | undefined {
    return value.hint === undefined && value.deviation === undefined ? undefined : { ...value };
}

function simpleShapes(shapes: DrawShape[]): StudyAnnotationsDto['shapes'] {
    const brushes = new Set(['green', 'red', 'blue', 'yellow']);
    return shapes
        .filter(shape => !shape.piece && !shape.customSvg && typeof shape.orig === 'string')
        .map(shape => ({
            orig: shape.orig,
            ...(shape.dest ? { dest: shape.dest } : {}),
            brush: (brushes.has(shape.brush ?? 'green') ? (shape.brush ?? 'green') : 'green') as
                | 'green'
                | 'red'
                | 'blue'
                | 'yellow',
        }));
}

export class StudyAnalysisExtension implements AnalysisExtension {
    readonly socket?: AnalysisExtension['socket'];
    readonly socketTarget: string;
    readonly treeStorageKey: string;
    readonly contextMenuActions?: AnalysisExtension['contextMenuActions'];
    readonly renderMoveListEnd?: AnalysisExtension['renderMoveListEnd'];
    readonly renderMoveListFooter?: AnalysisExtension['renderMoveListFooter'];
    private readonly idleWaiters = new Set<{ resolve: () => void; reject: () => void }>();
    private currentRevision: number;
    private connected = false;
    private openedOnce = false;
    private reconnecting = false;
    private reloadRequested = false;
    private initialTreeLoaded = false;
    private description: string;
    private tags: Record<string, string>;
    private serverEval?: StudyServerEval;
    private readonly pending: PendingMutation[] = [];
    private readonly onReloadRequired: (reason: string) => void;
    private readonly onAnnotationStateChanged?: (state: StudyAnnotationState) => void;
    private readonly opIdFactory: () => string;
    private readonly syncIdFactory: () => string;
    private readonly syncWaiters = new Map<
        string,
        {
            chapterId: string;
            snapshotToken: string;
            roomSnapshotToken?: string;
            resolve: (matches: boolean) => void;
            reject: () => void;
        }
    >();
    private streamReady: boolean;
    private writable: boolean;
    private memberRole?: StudyMemberRole;
    private recording: boolean;
    private policy?: StudySessionPolicy;
    private conceal?: StudyConcealController;
    private gamebookPlayback?: StudyGamebookPlayback;
    private practiceSession?: StudyPracticeSession;
    private suppressLocalPath = false;
    private pendingSharedPosition?: { chapterId: string; path: string };

    constructor(
        private readonly ctrl: AnalysisController,
        private readonly options: StudySyncOptions,
    ) {
        if (!Number.isInteger(options.revision) || options.revision < 0) {
            throw new Error('Study revision must be a non-negative integer');
        }
        this.socket = options.socket;
        this.currentRevision = options.revision;
        this.description = options.description ?? '';
        this.tags = { ...options.tags };
        this.serverEval = options.serverEval ?? undefined;
        if (options.orientation) {
            ctrl.mycolor = options.orientation;
            ctrl.oppcolor = options.orientation === 'white' ? 'black' : 'white';
        }
        this.socketTarget = `wsstudy/${options.studyId}`;
        this.treeStorageKey = `study:${options.studyId}:${options.chapterId}`;
        this.onReloadRequired = options.onReloadRequired ?? (() => window.location.reload());
        this.onAnnotationStateChanged = options.onAnnotationStateChanged;
        this.contextMenuActions = options.contextMenuActions;
        this.renderMoveListEnd = options.renderMoveListEnd;
        this.renderMoveListFooter = options.renderMoveListFooter;
        this.opIdFactory = options.opIdFactory ?? newStudyNodeId;
        this.syncIdFactory = options.syncIdFactory ?? newStudyNodeId;
        this.streamReady = options.snapshotVerified === true || !options.snapshotToken;
        this.writable = options.writable ?? true;
        this.memberRole = options.memberRole ?? (this.writable ? 'write' : undefined);
        this.policy = options.policy;
        if (options.policy && options.concealPly !== undefined) {
            this.conceal = new StudyConcealController(ctrl, options.concealPly, options.policy);
        }
        this.recording = this.writable && (this.policy?.recording ?? options.recording ?? true);
    }

    whenIdle(timeoutMs = 10000): Promise<void> {
        if (this.reloadRequested) return Promise.reject(new Error('Study needs to reload.'));
        if (!this.pending.length) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const done = (error?: Error) => {
                clearTimeout(timer);
                this.idleWaiters.delete(waiter);
                if (error) reject(error);
                else resolve();
            };
            const waiter = {
                resolve: () => done(),
                reject: () => done(new Error('Study changes could not be saved.')),
            };
            const timer = setTimeout(waiter.reject, timeoutMs);
            this.idleWaiters.add(waiter);
        });
    }

    get revision(): number {
        return this.currentRevision;
    }

    get pendingCount(): number {
        return this.pending.length;
    }

    verifySnapshot(chapterId: string, snapshotToken: string, roomSnapshotToken?: string): Promise<boolean> {
        if (!this.connected || this.reloadRequested || !chapterId || !snapshotToken) {
            return Promise.reject(new Error('Study socket is not ready for snapshot verification.'));
        }
        const requestId = this.syncIdFactory();
        if (!requestId || this.syncWaiters.has(requestId)) {
            return Promise.reject(new Error('Could not create a Study snapshot verification request.'));
        }
        return new Promise((resolve, reject) => {
            const timer = window.setTimeout(() => {
                this.syncWaiters.delete(requestId);
                reject(new Error('Study snapshot verification timed out.'));
            }, 5000);
            this.syncWaiters.set(requestId, {
                chapterId,
                snapshotToken,
                roomSnapshotToken,
                resolve: matches => {
                    window.clearTimeout(timer);
                    this.syncWaiters.delete(requestId);
                    resolve(matches);
                },
                reject: () => {
                    window.clearTimeout(timer);
                    this.syncWaiters.delete(requestId);
                    reject(new Error('Study snapshot verification was interrupted.'));
                },
            });
            this.ctrl.doSend({
                type: 'study_sync_chapter',
                studyId: this.options.studyId,
                chapterId,
                requestId,
            });
        });
    }

    get isRecording(): boolean {
        return this.recording;
    }

    setRecording(recording: boolean): void {
        this.recording = this.writable && (this.policy?.recording ?? recording);
        if (!this.recording) this.pendingSharedPosition = undefined;
    }

    setPolicy(policy: StudySessionPolicy, restoreRecording = true): void {
        const evaluationDisplay = this.policy?.tools.evaluationDisplay ?? true;
        const presentationChanged = this.policy?.tools.fullTree !== policy.tools.fullTree;
        this.policy = policy;
        this.conceal?.setPolicy(policy);
        this.recording = restoreRecording && this.writable && policy.recording;
        if (!this.recording || !policy.canPublishSharedPosition) this.pendingSharedPosition = undefined;
        if (evaluationDisplay !== policy.tools.evaluationDisplay) {
            if (!policy.tools.evaluationDisplay) this.clearServerEval();
            else this.applyServerEval();
        }
        if (presentationChanged) {
            this.ctrl.closeTreeContextMenu?.();
            this.restoreCurrentShapes();
            updateMovelist(this.ctrl, true, false);
        }
        this.ctrl.refreshLocalAnalysisAvailabilityForAntiCheat?.();
    }

    setGamebookPlayback(playback: StudyGamebookPlayback | undefined): void {
        this.gamebookPlayback?.destroy();
        this.gamebookPlayback = playback;
    }

    setPracticeSession(session: StudyPracticeSession | undefined): void {
        this.practiceSession?.destroy();
        this.practiceSession = session;
    }

    beforeMoveApplied(move: AnalysisMoveApplication): boolean | void {
        if (this.options.rootOnlyPreview) return false;
        if (this.practiceSession) return this.practiceSession.beforeMoveApplied(move);
        return this.gamebookPlayback?.beforeMoveApplied(move);
    }

    boardInput(context: { turnColor: 'white' | 'black' }): 'white' | 'black' | false {
        if (this.options.rootOnlyPreview) return false;
        if (this.practiceSession) return this.practiceSession.boardInput(context.turnColor);
        return this.gamebookPlayback?.boardInput(context.turnColor) ?? context.turnColor;
    }

    onPositionChanged(change: AnalysisPositionChange): void {
        this.practiceSession?.onPositionChanged(change);
        this.gamebookPlayback?.onPositionChanged(change);
        // AnalysisController refreshes the chessground position after onPathChanged().
        // Re-apply Study drawings once that board update has completed, matching lila's
        // showGround() ordering. Practice/gamebook playback own their board shapes.
        if (!this.practiceSession && !this.gamebookPlayback) this.restoreCurrentShapes();
    }

    canActivatePath(path: string, origin: AnalysisNavigationOrigin): boolean {
        if (this.options.rootOnlyPreview) {
            if (path === (this.ctrl.analysisPath ?? '')) return true;
            return origin === 'reset' && path === '';
        }
        if (this.practiceSession && !this.practiceSession.canActivatePath(path, origin)) return false;
        if (this.gamebookPlayback && !this.gamebookPlayback.canActivatePath(path, origin)) return false;
        return this.conceal?.canActivatePath(path, origin) ?? true;
    }

    isTreeNodeVisible(node: AnalysisTreeNode): boolean {
        if (this.options.rootOnlyPreview) return node.path === '';
        if (this.gamebookPlayback && !this.gamebookPlayback.isTreeNodeVisible(node)) return false;
        return this.conceal?.isTreeNodeVisible(node) ?? true;
    }

    isTreeNodeConcealed(node: AnalysisTreeNode): boolean {
        return this.conceal?.isTreeNodeConcealed(node) ?? false;
    }

    areTreeNodeAnnotationsVisible(node: AnalysisTreeNode): boolean {
        if (this.options.rootOnlyPreview || this.practiceSession || this.policy?.training) return false;
        if (this.gamebookPlayback && !this.gamebookPlayback.areTreeNodeAnnotationsVisible()) return false;
        return this.conceal?.areTreeNodeAnnotationsVisible(node) ?? true;
    }

    allowTreeContextMenu(): boolean {
        if (this.options.rootOnlyPreview) return false;
        if (this.practiceSession && !this.practiceSession.allowTreeContextMenu()) return false;
        if (this.gamebookPlayback && !this.gamebookPlayback.allowTreeContextMenu()) return false;
        return this.conceal?.allowTreeContextMenu() ?? true;
    }

    sharePosition(chapterId: string, path: string): boolean {
        if (this.policy?.canPublishSharedPosition === false) return false;
        if (!this.connected || !this.writable || !this.recording || this.reloadRequested || !chapterId) return false;
        this.pendingSharedPosition = { chapterId, path };
        this.pumpSharedPosition();
        return true;
    }

    resetConcealment(): boolean {
        if (!this.connected || !this.writable || this.reloadRequested || this.pending.length) return false;
        this.ctrl.doSend({
            type: 'study_reset_conceal',
            studyId: this.options.studyId,
            chapterId: this.options.chapterId,
            expectedRevision: this.currentRevision,
        });
        return true;
    }

    followSharedPath(path: string): boolean {
        if (this.policy?.canFollowSharedPosition === false) return false;
        const tree = this.ctrl.analysisTree;
        if (!tree || !nodeAtPath(tree, path)) return false;
        this.suppressLocalPath = true;
        try {
            this.ctrl.activateTreePath(path, true, 'shared-position');
        } finally {
            this.suppressLocalPath = false;
        }
        return true;
    }

    get annotationState(): StudyAnnotationState {
        const node = this.currentNode();
        return {
            path: this.ctrl.analysisPath ?? '',
            annotations: cloneAnnotations(node?.annotations),
            description: this.description,
            tags: { ...this.tags },
        };
    }

    get pgnStudy(): StudyPgnContext | undefined {
        const { studyName, owner, home } = this.options;
        if (!studyName || !owner || !home) return undefined;
        return { id: this.options.studyId, name: studyName, owner, home };
    }

    get pgnChapter(): StudyPgnChapterData | undefined {
        const { chapterName, chapterOrder, variant, initialFen, orientation } = this.options;
        if (!chapterName || !Number.isInteger(chapterOrder) || !variant || !initialFen || !orientation)
            return undefined;
        const tree =
            this.policy?.session === 'gamebook-preview'
                ? this.options.tree
                : this.initialTreeLoaded && this.ctrl.analysisTree
                  ? studyTreeFromAnalysisTree(this.ctrl.analysisTree)
                  : this.options.tree;
        if (!tree) return undefined;
        return {
            id: this.options.chapterId,
            name: chapterName,
            order: chapterOrder as number,
            variant,
            chess960: this.options.chess960 ?? false,
            initialFen,
            orientation,
            mode: this.options.mode ?? 'normal',
            description: this.description === '-' ? '' : this.description,
            tags: { ...this.tags },
            tree,
            ...(this.options.variantIni ? { variantIni: this.options.variantIni } : {}),
            ...(this.options.createdAt ? { createdAt: this.options.createdAt } : {}),
        };
    }

    getPgn(): string | undefined {
        const study = this.pgnStudy;
        const chapter = this.pgnChapter;
        return study && chapter ? renderStudyChapterPgn(study, chapter) : undefined;
    }

    updateChapterMetadata(chapter: StudyChapterPreview): void {
        if (chapter.id !== this.options.chapterId) return;
        this.options.chapterName = chapter.name;
        this.options.chapterOrder = chapter.order;
        this.options.orientation = chapter.orientation;
        this.options.mode = chapter.mode;
        if (this.ctrl.chessground.state.orientation !== chapter.orientation) this.ctrl.toggleOrientation();
    }

    onOrientationChanged(): void {
        this.options.onOrientationChanged?.(this.ctrl.chessground.state.orientation);
    }

    onInitialBoardLoaded(): void {
        if (!this.options.tree) return;
        const rootStep = this.ctrl.steps[0];
        if (!rootStep) {
            this.requestReload('missing_root_position');
            return;
        }
        try {
            const tree = analysisTreeFromStudy(rootStep, this.options.tree);
            this.ctrl.tree.loadAnalysisTree(tree);
            this.initialTreeLoaded = true;
            this.options.onInitialTreeLoaded?.();
            this.refreshPreferredMainline();
            this.applyServerEval();
            if (this.options.rootOnlyPreview && this.ctrl.analysisPath !== '') {
                this.ctrl.activateTreePath('', true, 'reset');
            }
            this.restoreCurrentShapes();
            this.notifyAnnotationState();
            updateMovelist(this.ctrl, true, false);
            this.ctrl.refreshPgnView?.();
        } catch {
            this.requestReload('invalid_initial_tree');
        }
    }

    onSocketOpen(): void {
        this.connected = true;
        if (this.openedOnce && this.reconnecting) {
            this.requestReload('reconnected');
            return;
        }
        this.openedOnce = true;
        this.reconnecting = false;
        if (this.options.snapshotToken && !this.options.snapshotVerified) {
            this.streamReady = false;
            void this.verifySnapshot(this.options.chapterId, this.options.snapshotToken, this.options.roomSnapshotToken)
                .then(matches => {
                    if (!matches) {
                        this.requestReload('snapshot_stale');
                        return;
                    }
                    this.streamReady = true;
                    this.pump();
                    this.pumpSharedPosition();
                })
                .catch(() => this.requestReload('snapshot_sync_failed'));
            return;
        }
        this.streamReady = true;
        this.pump();
        this.pumpSharedPosition();
    }

    onSocketReconnect(): void {
        this.connected = false;
        if (this.openedOnce) this.reconnecting = true;
    }

    onSocketClose(): void {
        this.connected = false;
    }

    onDestroy(): void {
        this.practiceSession?.destroy();
        this.practiceSession = undefined;
        this.gamebookPlayback?.destroy();
        this.gamebookPlayback = undefined;
        this.connected = false;
        this.pendingSharedPosition = undefined;
        [...this.idleWaiters].forEach(waiter => waiter.reject());
        this.idleWaiters.clear();
        [...this.syncWaiters.values()].forEach(waiter => waiter.reject());
        this.syncWaiters.clear();
    }

    onPathChanged(
        path = this.ctrl.analysisPath ?? '',
        _previousPath = '',
        origin: AnalysisNavigationOrigin = 'user-navigation',
    ): void {
        this.restoreCurrentShapes();
        this.notifyAnnotationState();
        if (!this.suppressLocalPath) this.options.onLocalPathChanged?.(path, origin);
    }

    onShapesChanged(shapes: DrawShape[]): void {
        if (this.gamebookPlayback) {
            this.gamebookPlayback.onShapesChanged();
            return;
        }
        const node = this.currentNode();
        if (!node) {
            this.requestReload('missing_tree_position');
            return;
        }
        const annotations = cloneAnnotations(node.annotations);
        annotations.shapes = simpleShapes(shapes);
        node.annotations = analysisAnnotationsFromStudy(annotations);
        this.notifyAnnotationState();
        const shapePayload: JSONObject[] = annotations.shapes.map(shape => {
            const payload: JSONObject = { orig: shape.orig, brush: shape.brush };
            if (shape.dest) payload.dest = shape.dest;
            return payload;
        });
        this.enqueue('study_set_shapes', { path: node.path, shapes: shapePayload });
    }

    addComment(text: string): string | undefined {
        const trimmed = text.trim();
        if (!trimmed) return undefined;
        const commentId = newStudyNodeId();
        this.setComment(commentId, trimmed);
        return commentId;
    }

    setComment(commentId: string, text: string, path = this.ctrl.analysisPath ?? ''): void {
        const node = this.ctrl.analysisTree && nodeAtPath(this.ctrl.analysisTree, path);
        if (!node || !isStudyNodeId(commentId)) return;
        const annotations = cloneAnnotations(node.annotations);
        annotations.comments = annotations.comments.filter(comment => comment.id !== commentId);
        if (text.trim()) {
            annotations.comments.push({ id: commentId, author: this.ctrl.username, text: text.trim() });
        }
        node.annotations = analysisAnnotationsFromStudy(annotations);
        if (path === (this.ctrl.analysisPath ?? '')) this.notifyAnnotationState();
        updateMovelist(this.ctrl, true, false);
        this.enqueue('study_set_comment', { path: node.path, commentId, text });
    }

    setNags(nags: number[]): void {
        const node = this.currentNode();
        if (!node) return;
        const annotations = cloneAnnotations(node.annotations);
        annotations.nags = [...new Set(nags.filter(nag => Number.isInteger(nag) && nag >= 1 && nag <= 255))];
        node.annotations = analysisAnnotationsFromStudy(annotations);
        this.notifyAnnotationState();
        updateMovelist(this.ctrl, true, false);
        this.enqueue('study_set_nags', { path: node.path, nags: annotations.nags });
    }

    clearAnnotations(): void {
        const node = this.currentNode();
        if (!node) return;
        node.annotations = undefined;
        node.gamebook = undefined;
        this.ctrl.chessground.setShapes([]);
        this.notifyAnnotationState();
        updateMovelist(this.ctrl, true, false);
        this.enqueue('study_clear_annotations', { path: node.path });
    }

    setGamebook(field: 'hint' | 'deviation', value: string, path = this.ctrl.analysisPath ?? ''): void {
        if (!this.writable || !this.recording || this.reloadRequested) return;
        const tree = this.ctrl.analysisTree;
        if (!tree) return;
        const node = nodeAtPath(tree, path);
        if (!node) return;
        node.gamebook = withGamebookField(node.gamebook, field, value);
        this.enqueue('study_set_gamebook', { path: node.path, field, value });
    }

    setDescription(description: string): void {
        if (!this.writable || this.reloadRequested) return;
        this.description = description;
        this.notifyAnnotationState();
        this.enqueue('study_set_description', { description }, false);
    }

    setTags(tags: Record<string, string>): void {
        if (!this.writable || this.reloadRequested) return;
        this.tags = { ...tags };
        this.notifyAnnotationState();
        this.enqueue('study_set_tags', { tags }, false);
    }

    requestServerAnalysis(): void {
        if (this.policy?.tools.serverAnalysis === false || !this.connected || !this.writable) return;
        this.ctrl.doSend({
            type: 'study_request_analysis',
            studyId: this.options.studyId,
            chapterId: this.options.chapterId,
        });
    }

    onEngineLine(line: string): boolean {
        return this.practiceSession?.onEngineLine(line) ?? false;
    }

    onComputerSearchAvailabilityChanged(): void {
        this.practiceSession?.refreshAvailability();
    }

    allowComputerSearch(): boolean {
        if (this.options.rootOnlyPreview) return false;
        return this.policy?.tools.computerSearch ?? true;
    }

    allowVariationArrows(): boolean {
        // Lila suppresses forks for the entire Practice/Conceal chapter, including
        // author views, and during gamebook playback. Never disclose lesson answers.
        return (
            !this.options.rootOnlyPreview &&
            !this.practiceSession &&
            !this.gamebookPlayback &&
            !this.conceal &&
            this.policy?.tools.fullTree !== false &&
            !this.policy?.session.startsWith('conceal') &&
            !this.policy?.session.startsWith('practice')
        );
    }

    isGamebookEditor(): boolean {
        return this.policy?.session === 'gamebook-author' || this.policy?.session === 'gamebook-analysis';
    }

    onEvaluation(): boolean {
        if (this.options.rootOnlyPreview) return false;
        return this.policy?.tools.evaluationDisplay ?? true;
    }

    onServerAnalysisVisibilityChanged(): void {
        this.options.onServerAnalysisVisibilityChanged?.();
    }

    onNodeAdded(parentPath: string, node: AnalysisTreeNode): void {
        if (!node.step.move || !isStudyNodeId(node.id)) {
            this.requestReload('invalid_local_node');
            return;
        }
        this.refreshPreferredMainline();
        this.ctrl.refreshPgnView?.();
        this.enqueue('study_add_node', {
            parentPath,
            move: node.step.move,
            nodeId: node.id,
        });
    }

    onNodeDeleted(path: string): void {
        this.refreshPreferredMainline();
        this.ctrl.refreshPgnView?.();
        this.enqueue('study_delete_node', { path });
    }

    onVariationPromoted(path: string, toMainline: boolean): void {
        this.refreshPreferredMainline();
        this.ctrl.refreshPgnView?.();
        this.enqueue('study_promote_variation', { path, toMainline });
    }

    onVariationForced(path: string, force: boolean): void {
        this.refreshPreferredMainline();
        this.ctrl.refreshPgnView?.();
        this.enqueue('study_force_variation', { path, force });
    }

    private updateConcealPly(concealPly: number, revision: number): void {
        this.options.concealPly = concealPly;
        this.conceal?.setConcealPly(concealPly);
        this.ctrl.setAutoShapes?.();
        updateMovelist(this.ctrl, true, false);
        this.options.onConcealChanged?.(concealPly, revision);
    }

    onSocketMessage(type: string, message: unknown): boolean {
        if (!STUDY_SOCKET_TYPES.has(type)) return false;
        const data = record(message);
        if (!data || data.type !== type) {
            this.requestReload('invalid_socket_message');
            return true;
        }

        if (type === 'study_user_connected') {
            if (data.studyId !== this.options.studyId) {
                this.requestReload('wrong_study');
                return true;
            }
            const roomSnapshotToken = data.roomSnapshotToken;
            if (roomSnapshotToken !== undefined && typeof roomSnapshotToken !== 'string') {
                this.requestReload('invalid_room_snapshot');
                return true;
            }
            if (
                this.options.roomSnapshotToken &&
                roomSnapshotToken !== undefined &&
                roomSnapshotToken !== this.options.roomSnapshotToken
            ) {
                this.requestReload('study_snapshot_stale');
            }
            return true;
        }

        if (type === 'study_chapter_sync') {
            if (data.studyId !== this.options.studyId || typeof data.requestId !== 'string') {
                this.requestReload('invalid_chapter_sync');
                return true;
            }
            const waiter = this.syncWaiters.get(data.requestId);
            if (!waiter) return true;
            if (data.chapterId !== waiter.chapterId) {
                waiter.reject();
                this.requestReload('invalid_chapter_sync');
                return true;
            }
            const revision = data.revision;
            const snapshotToken = data.snapshotToken;
            const roomSnapshotToken = data.roomSnapshotToken;
            if (
                (revision !== null && (!Number.isInteger(revision) || (revision as number) < 0)) ||
                (snapshotToken !== null && typeof snapshotToken !== 'string') ||
                (roomSnapshotToken !== null && typeof roomSnapshotToken !== 'string')
            ) {
                waiter.reject();
                this.requestReload('invalid_chapter_sync');
                return true;
            }
            waiter.resolve(
                snapshotToken === waiter.snapshotToken &&
                    (waiter.roomSnapshotToken === undefined || roomSnapshotToken === waiter.roomSnapshotToken),
            );
            return true;
        }

        if (data.studyId !== this.options.studyId) {
            this.requestReload('wrong_study');
            return true;
        }

        if (type === 'study_analysis_progress') {
            if (data.chapterId !== this.options.chapterId) return true;
            const serverEval = asStudyServerEval(data.serverEval);
            const studyTree = data.tree === undefined ? undefined : asStudyTree(data.tree);
            if (!serverEval || (data.tree !== undefined && !studyTree)) {
                this.requestReload('invalid_server_analysis');
                return true;
            }
            const practiceOwnsTree = Boolean(this.practiceSession);
            if (studyTree && this.initialTreeLoaded && !practiceOwnsTree) {
                const tree = this.ctrl.analysisTree;
                if (!tree || !mergeStudyTreeIntoAnalysisTree(tree, studyTree)) {
                    this.requestReload('invalid_server_analysis_tree');
                    return true;
                }
                this.refreshPreferredMainline();
            } else if (studyTree && !this.initialTreeLoaded) {
                this.options.tree = studyTree;
            }
            this.serverEval = serverEval;
            // Lichess practice owns a disposable local tree whose authored Study
            // continuations are removed before play. Keep authoritative Fishnet
            // snapshots out of that attempt tree; leaving practice reloads the
            // chapter and restores the canonical tree and its server analysis.
            if (!practiceOwnsTree) {
                this.applyServerEval();
                this.ctrl.refreshPgnView?.();
            }
            this.options.onServerEvalChanged?.(serverEval);
            return true;
        }

        if (type === 'study_analysis_unavailable') {
            if (data.chapterId !== this.options.chapterId) return true;
            if (typeof data.reason !== 'string') {
                this.requestReload('invalid_server_analysis_status');
                return true;
            }
            if (data.reason === 'fishnet_failed') {
                this.serverEval = undefined;
                this.clearServerEval();
                this.options.onServerEvalChanged?.(undefined);
            }
            this.options.onServerAnalysisUnavailable?.(data.reason);
            return true;
        }

        if (type === 'study_chapters') {
            const chapters = asStudyChapterPreviews(data.chapters);
            if (
                !chapters ||
                typeof data.sharedChapter !== 'string' ||
                !data.sharedChapter ||
                !chapters.some(chapter => chapter.id === data.sharedChapter) ||
                typeof data.sharedPath !== 'string'
            ) {
                this.requestReload('invalid_chapter_list');
                return true;
            }
            this.options.onChaptersChanged?.(chapters, data.sharedChapter, data.sharedPath);
            return true;
        }

        if (type === 'study_chapter_content') {
            if (
                typeof data.chapterId !== 'string' ||
                !Number.isInteger(data.revision) ||
                (data.revision as number) < 0 ||
                typeof data.description !== 'string'
            ) {
                this.requestReload('invalid_chapter_content');
                return true;
            }
            if (data.chapterId !== this.options.chapterId) return true;
            if (data.revision !== this.currentRevision + 1) {
                this.requestReload('revision_mismatch');
                return true;
            }
            if (!this.pending.some(pending => pending.type === 'study_set_description')) {
                this.description = data.description;
                this.notifyAnnotationState();
            }
            this.currentRevision = data.revision as number;
            return true;
        }

        if (type === 'study_position') {
            if (typeof data.chapterId !== 'string' || typeof data.path !== 'string') {
                this.requestReload('invalid_shared_position');
                return true;
            }
            this.options.onSharedPositionChanged?.(data.chapterId, data.path);
            return true;
        }

        if (type === 'study_conceal') {
            if (
                typeof data.chapterId !== 'string' ||
                typeof data.path !== 'string' ||
                !Number.isInteger(data.concealPly) ||
                (data.concealPly as number) < 0 ||
                !Number.isInteger(data.revision) ||
                (data.revision as number) < 0
            ) {
                this.requestReload('invalid_conceal_state');
                return true;
            }
            if (data.chapterId === this.options.chapterId) {
                const revision = data.revision as number;
                if (revision < this.currentRevision || revision > this.currentRevision + 1) {
                    this.requestReload('revision_mismatch');
                    return true;
                }
                this.currentRevision = revision;
                this.updateConcealPly(data.concealPly as number, this.currentRevision);
            }
            this.options.onSharedPositionChanged?.(data.chapterId, data.path);
            return true;
        }

        if (type === 'study_likes') {
            if (!Number.isInteger(data.likes) || (data.likes as number) < 0) {
                this.requestReload('invalid_likes');
                return true;
            }
            this.options.onLikesChanged?.(data.likes as number);
            return true;
        }

        if (type === 'study_topics') {
            const topics = asStringArray(data.topics);
            if (!topics) {
                this.requestReload('invalid_topics');
                return true;
            }
            this.options.onTopicsChanged?.(topics);
            return true;
        }

        if (type === 'study_members') {
            const members = asStudyMembers(data.members);
            if (!members) {
                this.requestReload('invalid_members');
                return true;
            }
            const nextRole = members[this.ctrl.username];
            const membershipChanged = nextRole !== this.memberRole;
            this.memberRole = nextRole;
            this.writable = nextRole === 'write';
            if (!this.writable) {
                this.recording = false;
                this.pendingSharedPosition = undefined;
            }
            this.options.onMembersChanged?.(members);
            // Read membership can gate computer analysis, cloning and sharing even
            // when write access stays false. Reload only when this viewer's own role
            // changes so the complete capability set is rebuilt from server state.
            if (membershipChanged) this.requestReload('member_access_changed');
            return true;
        }

        if (type === 'study_error' || type === 'study_reload') {
            this.requestReload(typeof data.reason === 'string' ? data.reason : type);
            return true;
        }

        if (data.chapterId !== this.options.chapterId) return true;
        if (!this.isAcceptedMutation(type, data)) {
            this.requestReload('invalid_mutation_ack');
            return true;
        }
        if (data.concealPly !== undefined && (!Number.isInteger(data.concealPly) || (data.concealPly as number) < 0)) {
            this.requestReload('invalid_conceal_state');
            return true;
        }

        const pending = this.pending[0];
        if (pending && data.clientOpId === pending.clientOpId) {
            this.acceptOwnMutation(pending, data);
        } else {
            // The server sequences all Study mutations and broadcasts them in that
            // order. A remote operation may therefore arrive while our optimistic
            // operation is still waiting for its acknowledgement. Apply the remote
            // revision first; the already-sent local operation is safely rebased by
            // the server against the latest authoritative tree.
            this.applyRemoteMutation(type as StudyMutationType, data);
        }
        return true;
    }

    private currentNode(): AnalysisTreeNode | undefined {
        const tree = this.ctrl.analysisTree;
        if (!tree) return undefined;
        return nodeAtPath(tree, this.ctrl.analysisPath ?? '');
    }

    private notifyAnnotationState(): void {
        this.onAnnotationStateChanged?.(this.annotationState);
        this.ctrl.refreshPgnView?.();
        this.ctrl.setAutoShapes?.();
    }

    private restoreCurrentShapes(): void {
        const node = this.currentNode();
        this.ctrl.chessground.setShapes(
            this.options.rootOnlyPreview || this.conceal?.areBoardShapesVisible() === false
                ? []
                : (node?.annotations?.shapes ?? []),
        );
    }

    private setPositionAnnotations(path: string, annotations: StudyAnnotationsDto): boolean {
        const tree = this.ctrl.analysisTree;
        if (!tree) return false;
        const node = nodeAtPath(tree, path);
        if (!node) return false;
        node.annotations = analysisAnnotationsFromStudy(annotations);
        if (path === (this.ctrl.analysisPath ?? '')) {
            this.restoreCurrentShapes();
            this.notifyAnnotationState();
        }
        updateMovelist(this.ctrl, true, false);
        return true;
    }

    private setPositionGamebook(path: string, gamebook: StudyGamebookDto): boolean {
        const tree = this.ctrl.analysisTree;
        if (!tree) return false;
        const node = nodeAtPath(tree, path);
        if (!node) return false;
        node.gamebook = gamebookOrUndefined(gamebook);
        if (path === (this.ctrl.analysisPath ?? '')) this.notifyAnnotationState();
        return true;
    }

    private enqueue(type: StudyMutationType, body: JSONObject, requiresRecording = true): void {
        if (!this.writable || (requiresRecording && !this.recording) || this.reloadRequested) return;
        const clientOpId = this.opIdFactory();
        if (!clientOpId) {
            this.requestReload('invalid_client_operation_id');
            return;
        }
        this.pending.push({ type, chapterId: this.options.chapterId, clientOpId, body, sent: false });
        this.pump();
    }

    private pump(): void {
        if (!this.connected || !this.streamReady || this.reloadRequested) return;
        const pending = this.pending[0];
        if (!pending) {
            this.pumpSharedPosition();
            return;
        }
        if (pending.sent) return;
        pending.sent = true;
        this.ctrl.doSend({
            type: pending.type,
            studyId: this.options.studyId,
            chapterId: pending.chapterId,
            clientOpId: pending.clientOpId,
            expectedRevision: this.currentRevision,
            ...pending.body,
        });
    }

    private pumpSharedPosition(): void {
        if (
            !this.connected ||
            !this.streamReady ||
            !this.writable ||
            !this.recording ||
            this.reloadRequested ||
            this.pending.length ||
            !this.pendingSharedPosition
        )
            return;
        const position = this.pendingSharedPosition;
        this.pendingSharedPosition = undefined;
        this.ctrl.doSend({
            type: 'study_set_position',
            studyId: this.options.studyId,
            chapterId: position.chapterId,
            path: position.path,
            ...(position.chapterId === this.options.chapterId ? { expectedRevision: this.currentRevision } : {}),
        });
    }

    private isAcceptedMutation(type: string, data: Record<string, unknown>): boolean {
        return (
            type !== 'study_user_connected' &&
            type !== 'study_error' &&
            type !== 'study_reload' &&
            typeof data.clientOpId === 'string' &&
            Number.isInteger(data.revision) &&
            (data.revision as number) >= 0 &&
            typeof data.changed === 'boolean'
        );
    }

    private acceptOwnMutation(pending: PendingMutation, data: Record<string, unknown>): void {
        if (data.type !== pending.type) {
            this.requestReload('operation_mismatch');
            return;
        }
        const expectedRevision = this.currentRevision + (data.changed ? 1 : 0);
        if (data.revision !== expectedRevision) {
            this.requestReload('revision_mismatch');
            return;
        }

        if (pending.type === 'study_add_node') {
            const node = asStudyTreeNode(data.node);
            const localNodeId = pending.body.nodeId;
            const parent = pending.body.parentPath;
            if (typeof localNodeId !== 'string' || typeof parent !== 'string' || !node || !this.ctrl.analysisTree) {
                this.requestReload('invalid_add_ack');
                return;
            }
            const localPath = parent ? `${parent}.${localNodeId}` : localNodeId;
            const canonicalPath = parent ? `${parent}.${node.id}` : node.id;
            if (data.path !== canonicalPath || node.move !== pending.body.move) {
                this.requestReload('invalid_add_ack');
                return;
            }
            if (node.id !== localNodeId && data.changed) {
                this.requestReload('node_canonicalized');
                return;
            }
            const reconciled = reconcileStudyNodeIntoAnalysisTree(this.ctrl.analysisTree, parent, localNodeId, node);
            if (!reconciled || reconciled.localPath !== localPath || reconciled.canonicalPath !== canonicalPath) {
                this.requestReload('tree_mismatch');
                return;
            }
            if (canonicalPath !== localPath) this.remapCanonicalizedPath(localPath, canonicalPath);
            this.restorePendingTreeMutations(this.pending.slice(1));
            const canonicalNode = nodeAtPath(this.ctrl.analysisTree, canonicalPath);
            if (canonicalNode) {
                let annotations = parseStudyAnnotations(node.annotations ?? {});
                annotations = this.overlayPendingAnnotations(canonicalPath, annotations, this.pending.slice(1));
                canonicalNode.annotations = analysisAnnotationsFromStudy(annotations);
                let gamebook = parseStudyGamebook(node.gamebook ?? {});
                gamebook = this.overlayPendingGamebook(canonicalPath, gamebook, this.pending.slice(1));
                canonicalNode.gamebook = gamebookOrUndefined(gamebook);
            }
            this.refreshPreferredMainline();
            updateMovelist(this.ctrl, true, false);
            this.ctrl.refreshPgnView?.();
        } else if (POSITION_ANNOTATION_MUTATIONS.has(pending.type)) {
            const path = data.path;
            if (typeof path !== 'string') {
                this.requestReload('invalid_annotation_ack');
                return;
            }
            let annotations: StudyAnnotationsDto;
            try {
                annotations = parseStudyAnnotations(data.annotations);
            } catch {
                this.requestReload('invalid_annotation_ack');
                return;
            }
            annotations = this.overlayPendingAnnotations(path, annotations, this.pending.slice(1));
            if (!this.setPositionAnnotations(path, annotations)) {
                this.requestReload('tree_mismatch');
                return;
            }
            if (pending.type === 'study_clear_annotations') {
                let gamebook: StudyGamebookDto;
                try {
                    gamebook = parseStudyGamebook(data.gamebook);
                } catch {
                    this.requestReload('invalid_gamebook_ack');
                    return;
                }
                gamebook = this.overlayPendingGamebook(path, gamebook, this.pending.slice(1));
                if (!this.setPositionGamebook(path, gamebook)) {
                    this.requestReload('tree_mismatch');
                    return;
                }
            }
        } else if (pending.type === 'study_set_gamebook') {
            const path = data.path;
            if (typeof path !== 'string') {
                this.requestReload('invalid_gamebook_ack');
                return;
            }
            let gamebook: StudyGamebookDto;
            try {
                gamebook = parseStudyGamebook(data.gamebook);
            } catch {
                this.requestReload('invalid_gamebook_ack');
                return;
            }
            gamebook = this.overlayPendingGamebook(path, gamebook, this.pending.slice(1));
            if (!this.setPositionGamebook(path, gamebook)) {
                this.requestReload('tree_mismatch');
                return;
            }
        } else if (pending.type === 'study_set_description') {
            if (typeof data.description !== 'string') {
                this.requestReload('invalid_description_ack');
                return;
            }
            this.description = data.description;
            this.notifyAnnotationState();
        } else if (pending.type === 'study_set_tags') {
            const tags = asStringRecord(data.tags);
            if (!tags) {
                this.requestReload('invalid_tags_ack');
                return;
            }
            this.tags = tags;
            this.notifyAnnotationState();
        }

        this.currentRevision = data.revision as number;
        if (typeof data.concealPly === 'number') this.updateConcealPly(data.concealPly, this.currentRevision);
        this.pending.shift();
        if (!this.pending.length) for (const waiter of this.idleWaiters) waiter.resolve();
        this.pump();
    }

    private applyRemoteMutation(type: StudyMutationType, data: Record<string, unknown>): void {
        if (!data.changed || data.revision !== this.currentRevision + 1) {
            this.requestReload('revision_mismatch');
            return;
        }
        if (this.practiceSession) {
            // Practice follows lichess's disposable-tree model: collaborative Study
            // edits may advance the authoritative revision, but they must not be
            // merged into the local game attempt. Writers leave practice through a
            // full chapter reload, which picks up every skipped canonical mutation.
            if (type === 'study_set_description') {
                if (typeof data.description !== 'string') {
                    this.requestReload('invalid_remote_description');
                    return;
                }
                this.description = data.description;
                this.notifyAnnotationState();
            } else if (type === 'study_set_tags') {
                const tags = asStringRecord(data.tags);
                if (!tags) {
                    this.requestReload('invalid_tags_ack');
                    return;
                }
                this.tags = tags;
                this.notifyAnnotationState();
            }
            this.currentRevision = data.revision as number;
            if (typeof data.concealPly === 'number') this.updateConcealPly(data.concealPly, this.currentRevision);
            return;
        }
        const tree = this.ctrl.analysisTree;
        if (!tree) {
            this.requestReload('missing_tree');
            return;
        }

        if (type === 'study_add_node') {
            const parentPathValue = data.parentPath;
            const path = data.path;
            const node = asStudyTreeNode(data.node);
            if (typeof parentPathValue !== 'string' || typeof path !== 'string' || !node) {
                this.requestReload('invalid_remote_add');
                return;
            }
            const attachedPath = mergeStudyNodeIntoAnalysisTree(tree, parentPathValue, node);
            if (attachedPath !== path) {
                this.requestReload('tree_mismatch');
                return;
            }
        } else if (type === 'study_delete_node') {
            const path = data.path;
            if (typeof path !== 'string' || !path || !nodeAtPath(tree, path)) {
                this.requestReload('tree_mismatch');
                return;
            }
            const activePath = this.ctrl.analysisPath;
            const nextPath = activePath === path || activePath.startsWith(`${path}.`) ? parentPath(path) : activePath;
            deleteNodePath(tree, path);
            this.refreshPreferredMainline();
            if (nextPath !== activePath) this.ctrl.activateTreePath(nextPath, true, 'reset');
        } else if (type === 'study_promote_variation') {
            const path = data.path;
            const toMainline = data.toMainline;
            if (typeof path !== 'string' || typeof toMainline !== 'boolean' || !nodeAtPath(tree, path)) {
                this.requestReload('tree_mismatch');
                return;
            }
            promoteNodePath(tree, path, toMainline);
        } else if (type === 'study_force_variation') {
            const path = data.path;
            const force = data.force;
            if (typeof path !== 'string' || typeof force !== 'boolean' || !nodeAtPath(tree, path)) {
                this.requestReload('tree_mismatch');
                return;
            }
            forceVariationAt(tree, path, force);
        } else if (POSITION_ANNOTATION_MUTATIONS.has(type)) {
            const path = data.path;
            if (typeof path !== 'string') {
                this.requestReload('invalid_remote_annotation');
                return;
            }
            let annotations: StudyAnnotationsDto;
            try {
                annotations = parseStudyAnnotations(data.annotations);
            } catch {
                this.requestReload('invalid_remote_annotation');
                return;
            }
            annotations = this.overlayPendingAnnotations(path, annotations, this.pending);
            if (!this.setPositionAnnotations(path, annotations)) {
                this.requestReload('tree_mismatch');
                return;
            }
            if (type === 'study_clear_annotations') {
                let gamebook: StudyGamebookDto;
                try {
                    gamebook = parseStudyGamebook(data.gamebook);
                } catch {
                    this.requestReload('invalid_remote_gamebook');
                    return;
                }
                gamebook = this.overlayPendingGamebook(path, gamebook, this.pending);
                if (!this.setPositionGamebook(path, gamebook)) {
                    this.requestReload('tree_mismatch');
                    return;
                }
            }
        } else if (type === 'study_set_gamebook') {
            const path = data.path;
            if (typeof path !== 'string') {
                this.requestReload('invalid_remote_gamebook');
                return;
            }
            let gamebook: StudyGamebookDto;
            try {
                gamebook = parseStudyGamebook(data.gamebook);
            } catch {
                this.requestReload('invalid_remote_gamebook');
                return;
            }
            gamebook = this.overlayPendingGamebook(path, gamebook, this.pending);
            if (!this.setPositionGamebook(path, gamebook)) {
                this.requestReload('tree_mismatch');
                return;
            }
        } else if (type === 'study_set_description') {
            if (typeof data.description !== 'string') {
                this.requestReload('invalid_remote_description');
                return;
            }
            if (!this.pending.some(pending => pending.type === 'study_set_description')) {
                this.description = data.description;
                this.notifyAnnotationState();
            }
        } else if (type === 'study_set_tags') {
            const tags = asStringRecord(data.tags);
            if (!tags) {
                this.requestReload('invalid_remote_tags');
                return;
            }
            if (!this.pending.some(pending => pending.type === 'study_set_tags')) {
                this.tags = tags;
                this.notifyAnnotationState();
            }
        }

        this.refreshPreferredMainline();
        this.currentRevision = data.revision as number;
        if (typeof data.concealPly === 'number') this.updateConcealPly(data.concealPly, this.currentRevision);
        if (!POSITION_ANNOTATION_MUTATIONS.has(type) && this.allowVariationArrows()) this.ctrl.setAutoShapes?.();
        updateMovelist(this.ctrl, true, false);
        this.ctrl.refreshPgnView?.();
        if (this.gamebookPlayback && GAMEBOOK_SCRIPT_MUTATIONS.has(type)) {
            this.gamebookPlayback.suspendForScriptReload();
            this.options.onGamebookScriptChanged?.();
        }
    }

    private remapCanonicalizedPath(localPath: string, canonicalPath: string): void {
        for (const queued of this.pending.slice(1)) {
            for (const field of ['path', 'parentPath'] as const) {
                const value = queued.body[field];
                if (typeof value === 'string') queued.body[field] = remapPathPrefix(value, localPath, canonicalPath);
            }
        }
        if (this.pendingSharedPosition) {
            this.pendingSharedPosition.path = remapPathPrefix(
                this.pendingSharedPosition.path,
                localPath,
                canonicalPath,
            );
        }

        const activePath = this.ctrl.analysisPath ?? '';
        const nextActivePath = remapPathPrefix(activePath, localPath, canonicalPath);
        if (nextActivePath !== activePath && nodeAtPath(this.ctrl.analysisTree!, nextActivePath)) {
            this.suppressLocalPath = true;
            try {
                this.ctrl.activateTreePath(nextActivePath, true, 'reset');
            } finally {
                this.suppressLocalPath = false;
            }
        }
    }

    private restorePendingTreeMutations(pendingMutations: PendingMutation[]): void {
        const tree = this.ctrl.analysisTree;
        if (!tree) return;
        for (const queued of pendingMutations) {
            const path = queued.body.path;
            if (typeof path !== 'string') continue;
            if (queued.type === 'study_delete_node') {
                if (nodeAtPath(tree, path)) deleteNodePath(tree, path);
            } else if (queued.type === 'study_promote_variation') {
                if (nodeAtPath(tree, path)) promoteNodePath(tree, path, queued.body.toMainline === true);
            } else if (queued.type === 'study_force_variation') {
                if (nodeAtPath(tree, path)) forceVariationAt(tree, path, queued.body.force === true);
            }
        }
    }

    private overlayPendingAnnotations(
        path: string,
        base: StudyAnnotationsDto,
        pendingMutations: PendingMutation[],
    ): StudyAnnotationsDto {
        let annotations: StudyAnnotationsDto = {
            shapes: base.shapes.map(shape => ({ ...shape })),
            comments: base.comments.map(comment => ({ ...comment })),
            nags: [...base.nags],
        };
        for (const queued of pendingMutations) {
            if (queued.body.path !== path) continue;
            if (queued.type === 'study_clear_annotations') annotations = emptyAnnotations();
            else if (queued.type === 'study_set_comment') {
                const id = queued.body.commentId as string;
                annotations.comments = annotations.comments.filter(comment => comment.id !== id);
                const text = (queued.body.text as string).trim();
                if (text) annotations.comments.push({ id, author: this.ctrl.username, text });
            } else if (queued.type === 'study_set_nags') annotations.nags = queued.body.nags as number[];
            else if (queued.type === 'study_set_shapes')
                annotations.shapes = parseStudyAnnotations({ shapes: queued.body.shapes }).shapes;
        }
        return annotations;
    }

    private overlayPendingGamebook(
        path: string,
        base: StudyGamebookDto,
        pendingMutations: PendingMutation[],
    ): StudyGamebookDto {
        let gamebook: StudyGamebookDto | undefined = gamebookOrUndefined(base);
        for (const queued of pendingMutations) {
            if (queued.body.path !== path) continue;
            if (queued.type === 'study_clear_annotations') {
                gamebook = undefined;
                continue;
            }
            if (queued.type !== 'study_set_gamebook') continue;
            const field = queued.body.field;
            const value = queued.body.value;
            if ((field !== 'hint' && field !== 'deviation') || typeof value !== 'string') continue;
            gamebook = withGamebookField(gamebook, field, value);
        }
        return gamebook ?? {};
    }

    private refreshPreferredMainline(): void {
        const tree = this.ctrl.analysisTree;
        if (!tree) return;
        this.ctrl.steps = refreshStudyMainline(tree);
        // A Study line is an editable preferred line, not the immutable recorded
        // mainline of a finished game. Tree node metadata remains authoritative.
        this.ctrl.recordedMainlinePly = undefined;
        if (this.serverEval && this.currentMainlinePath() !== this.serverEval.path) {
            this.serverEval = undefined;
            this.clearServerEval();
            this.options.onServerEvalChanged?.(undefined);
        } else {
            // Canonical node replacements rebuild Step objects. Re-apply persisted
            // Study evals (and any still-valid live server-analysis overlay) so an
            // unrelated annotation/tree acknowledgement cannot make evals disappear.
            this.applyServerEval();
        }
    }

    private currentMainlinePath(): string {
        const tree = this.ctrl.analysisTree;
        if (!tree) return '';
        let node = tree.root;
        while (node.children[0] && !node.children[0].forceVariation) node = node.children[0];
        return node.path;
    }

    private applyTreeEvals(): void {
        if (this.policy?.tools.evaluationDisplay === false) return;
        const tree = this.ctrl.analysisTree;
        if (!tree) return;
        for (const node of tree.byPath.values()) {
            if (!node.eval) continue;
            node.step.analysis = node.eval;
            node.step.ceval = node.eval;
            node.step.scoreStr = this.ctrl.buildScoreStr(node.step.turnColor === 'black' ? 'b' : 'w', node.eval);
        }
    }

    private clearServerEval(): void {
        const clear = (step: { analysis?: Ceval; ceval?: Ceval; scoreStr?: string }): void => {
            step.analysis = undefined;
            step.ceval = undefined;
            step.scoreStr = undefined;
        };
        for (const step of this.ctrl.steps) clear(step);
        for (const node of this.ctrl.analysisTree?.byPath.values() ?? []) clear(node.step);
        this.applyTreeEvals();
        updateMovelist(this.ctrl, true, false);
    }

    private applyServerEval(): void {
        this.clearServerEval();
        if (this.policy?.tools.evaluationDisplay === false) return;
        const serverEval = this.serverEval;
        if (!serverEval || this.currentMainlinePath() !== serverEval.path) return;
        for (let ply = 0; ply < Math.min(this.ctrl.steps.length, serverEval.analysis.length); ply++) {
            const stored = serverEval.analysis[ply];
            if (!stored) continue;
            const ceval: Ceval = {
                s: stored.s,
                d: stored.d ?? 0,
                ...(stored.p ? { p: stored.p } : {}),
            };
            const step = this.ctrl.steps[ply];
            step.analysis = ceval;
            step.ceval = ceval;
            step.scoreStr = this.ctrl.buildScoreStr(step.turnColor === 'black' ? 'b' : 'w', ceval);
        }
        updateMovelist(this.ctrl, true, false);
    }

    private requestReload(reason: string): void {
        if (this.reloadRequested) return;
        this.reloadRequested = true;
        for (const waiter of this.idleWaiters) waiter.reject();
        for (const waiter of this.syncWaiters.values()) waiter.reject();
        this.syncWaiters.clear();
        this.connected = false;
        this.onReloadRequired(reason);
    }
}

export function studyAnalysisExtension(options: StudySyncOptions): AnalysisExtensionFactory {
    return ctrl => new StudyAnalysisExtension(ctrl, options);
}
