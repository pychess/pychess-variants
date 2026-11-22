import type { VNode } from 'snabbdom';
import type { WebsocketHeartbeatJs } from '../socket/socket';
import type { DrawShape } from 'chessgroundx/draw';

import type { AnalysisTreeNode } from './analysisTree';
import type { AnalysisController } from './analysisCtrl';

export type AnalysisNavigationOrigin =
    | 'user-navigation'
    | 'played-move'
    | 'automated-reply'
    | 'shared-position'
    | 'reset';

export interface AnalysisMoveApplication {
    move: string;
    origin: Extract<AnalysisNavigationOrigin, 'played-move' | 'automated-reply'>;
    path: string;
}

export interface AnalysisPositionChange {
    origin: AnalysisNavigationOrigin;
    path: string;
    previousPath: string;
    ply: number;
    fen: string;
    node?: AnalysisTreeNode;
}

export interface AnalysisEvaluationDelivery {
    source: 'local' | 'server' | 'stored';
    ply: number;
    fen: string;
    ceval?: import('../messages').Ceval;
    scoreStr?: string;
}

export interface AnalysisBoardInputContext {
    path: string;
    ply: number;
    turnColor: 'white' | 'black';
}

// Optional behavior layered on top of the shared analysis host. Study will use this
// seam for persistence/synchronization while ordinary analysis leaves it undefined.
export interface AnalysisExtension {
    // Extensions such as Study can replace the ordinary round socket with their own
    // transport while reusing AnalysisController's heartbeat/message plumbing.
    socketTarget?: string;
    socket?: WebsocketHeartbeatJs;
    treeStorageKey?: string;
    onSocketOpen?(): void;
    onSocketReconnect?(): void;
    onSocketClose?(): void;
    getPgn?(): string | undefined;
    // Extension-owned content appended to the scrollable move list.
    // Study uses this for the Lichess-style next-chapter action.
    renderMoveListEnd?(): VNode[];
    // Extension-owned controls fixed below the scrolling move list.
    // Study uses this for Lichess-style fork choices.
    renderMoveListFooter?(): VNode[];
    contextMenuActions?(path: string): VNode[];
    onInitialBoardLoaded?(): void;
    onOrientationChanged?(): void;
    beforeMoveApplied?(move: AnalysisMoveApplication): boolean | void;
    canActivatePath?(path: string, origin: AnalysisNavigationOrigin): boolean;
    onPathChanged?(path: string, previousPath: string, origin: AnalysisNavigationOrigin): void;
    onPositionChanged?(change: AnalysisPositionChange): void;
    boardInput?(context: AnalysisBoardInputContext): 'white' | 'black' | 'both' | false;
    onEvaluation?(evaluation: AnalysisEvaluationDelivery): boolean | void;
    /** Refresh extension-owned analysis panels after the display preference changes. */
    onServerAnalysisVisibilityChanged?(): void;
    /** Consume browser-engine output owned by an extension-specific bounded search. */
    onEngineLine?(line: string): boolean;
    /** Re-check extension-owned engine work after permission/readiness changes. */
    onComputerSearchAvailabilityChanged?(): void;
    allowComputerSearch?(): boolean;
    /** Match Lichess allowLines(): training and concealed chapters hide forks. */
    allowVariationArrows?(): boolean;
    isGamebookEditor?(): boolean;
    isTreeNodeVisible?(node: AnalysisTreeNode): boolean;
    isTreeNodeConcealed?(node: AnalysisTreeNode): boolean;
    areTreeNodeAnnotationsVisible?(node: AnalysisTreeNode): boolean;
    allowTreeContextMenu?(): boolean;
    onShapesChanged?(shapes: DrawShape[]): void;
    onNodeAdded?(parentPath: string, node: AnalysisTreeNode): void;
    onNodeDeleted?(path: string): void;
    onVariationPromoted?(path: string, toMainline: boolean): void;
    onVariationForced?(path: string, force: boolean): void;
    onSocketMessage?(type: string, message: unknown): boolean;
    onDestroy?(): void;
}

export type AnalysisExtensionFactory = (ctrl: AnalysisController) => AnalysisExtension;
