import type * as cg from 'chessgroundx/types';
import type { DrawShape } from 'chessgroundx/draw';
import * as util from 'chessgroundx/util';

import type { AnalysisController } from '../analysis/analysisCtrl';
import type {
    AnalysisMoveApplication,
    AnalysisNavigationOrigin,
    AnalysisPositionChange,
} from '../analysis/analysisExtension';
import {
    AnalysisPracticeEngine,
    type AnalysisPracticeEngineEvent,
    type AnalysisPracticeInfo,
    type AnalysisPracticeSearchOwner,
    type AnalysisPracticeUnavailableReason,
} from '../analysis/analysisPracticeEngine';
import { boardSettings } from '../boardSettings';
import { uci2cg } from '../chess';
import { _ } from '../i18n';
import type { Ceval } from '../messages';
import { sound } from '../sound';
import type { PracticeGoal } from '../types';
import {
    gradeStudyPracticeMove,
    studyPracticeMovesEquivalent,
    studyPracticeOutcomeText,
    type StudyPracticeEvaluation,
    type StudyPracticeFeedback,
} from './studyPracticeFeedback';
import {
    evaluateStudyPracticeGoal,
    PRACTICE_GOAL_MIN_DEPTH,
    studyPracticeMovePromotes,
    type StudyPracticeGoalDecision,
} from './studyPracticeGoal';

export type StudyPracticeUnavailableReason =
    | 'computer-disabled'
    | 'active-game'
    | Extract<
          AnalysisPracticeUnavailableReason,
          'unsupported' | 'engine-not-ready' | 'engine-error' | 'timeout' | 'drain-timeout'
      >;

export interface StudyPracticeMove {
    move: string;
    fen: string;
    path: string;
    by: 'human' | 'engine';
    san?: string;
    promotion?: boolean;
}

export type StudyPracticeState =
    | Readonly<{ kind: 'initializing' }>
    | Readonly<{ kind: 'human-turn' }>
    | Readonly<{ kind: 'evaluating-move' }>
    | Readonly<{ kind: 'engine-thinking' }>
    | Readonly<{ kind: 'paused'; liveKind: 'human-turn' | 'engine-thinking'; browseIndex: number }>
    | Readonly<{
          kind: 'ended';
          result?: string;
          feedback?: StudyPracticeFeedback;
          goalDecision?: Exclude<StudyPracticeGoalDecision, 'ongoing'>;
      }>
    | Readonly<{ kind: 'unavailable'; reason: StudyPracticeUnavailableReason; message?: string }>;

export type StudyPracticeAccess =
    | Readonly<{ available: true }>
    | Readonly<{ available: false; reason: 'computer-disabled' | 'active-game'; message?: string }>;

export interface StudyPracticeOptions {
    initialFen: string;
    learnerColor: 'white' | 'black';
    access(): StudyPracticeAccess;
    canAnalyse: boolean;
    onAnalyse?(): void;
    goal?: PracticeGoal;
    autoNext?(): boolean;
    hasNextChapter?: boolean;
    onComplete?(moves: number): void;
    onNextChapter?(): void;
    showNextChapterOnEnd?: boolean;
    onStateChange?(state: StudyPracticeState): void;
}

type PracticeBoard = {
    delete(): void;
    isGameOver(claimDraw?: boolean): boolean;
    isCheck(): boolean;
    legalMoves(): string;
    numberLegalMoves(): number;
    pop(): void;
    push(move: string): void;
    result(claimDraw?: boolean): string;
    sanMove(move: string): string;
};

const PRACTICE_FEEDBACK_NODES = 400_000;
const PRACTICE_SEARCH_NODES = 600_000;

type PositionEvaluation = StudyPracticeEvaluation & Readonly<{
    key: string;
    moves: readonly string[];
    bestSan?: string;
}>;

type SearchPurpose =
    | Readonly<{
          kind: 'evaluation';
          key: string;
          moves: readonly string[];
          turnColor: 'white' | 'black';
      }>
    | Readonly<{
          kind: 'reply';
          moves: readonly string[];
          turnColor: 'white' | 'black';
      }>;

interface PendingGrade {
    playedMove: string;
    parentMoves: readonly string[];
    childMoves: readonly string[];
    parentTurnColor: 'white' | 'black';
    childTurnColor: 'white' | 'black';
    parentPath: string;
    terminalResult?: string;
}

interface PracticeRetry {
    parentPath: string;
    bestMove: string;
}

function ownerKey(owner: AnalysisPracticeSearchOwner): string {
    return `${owner.session}:${owner.search}`;
}

function boardKey(ctrl: AnalysisController, value: string): cg.Key | undefined {
    if (value.length !== 2) return undefined;
    const key = value as cg.Key;
    const [file, rank] = util.key2pos(key);
    const dimensions = ctrl.chessground.state.dimensions;
    if (file < 0 || rank < 0 || file >= dimensions.width || rank >= dimensions.height) return undefined;
    return key;
}

/**
 * Disposable live-play session for Study "Practice with computer" chapters.
 *
 * The persisted Study tree is deliberately not the game source here. The session
 * starts from the chapter root FEN, replaces authored continuations with a local
 * attempt tree, and owns a second ffish Board whose uninterrupted move stack is
 * used for legality and terminal/result checks (including repetition-sensitive
 * rules). The browser engine receives the same root FEN + full attempt move list.
 */
export class StudyPracticeSession {
    private readonly engine: AnalysisPracticeEngine;
    private readonly panel: HTMLElement;
    private readonly status: HTMLElement;
    private historyBoard: PracticeBoard;
    private stateValue: StudyPracticeState = { kind: 'initializing' };
    private readonly history: StudyPracticeMove[] = [];
    private readonly paths: string[] = [''];
    private readonly evaluations = new Map<string, PositionEvaluation>();
    private readonly evaluationSearches = new Set<string>();
    private readonly goalEvaluationAttempts = new Set<string>();
    private readonly searchPurposes = new Map<string, SearchPurpose>();
    private livePath = '';
    private pendingGrade?: PendingGrade;
    private pendingGoalFeedback?: StudyPracticeFeedback;
    private lastRetry?: PracticeRetry;
    private launchingSearchPurpose?: SearchPurpose;
    private lastFeedback?: StudyPracticeFeedback;
    private hintLevel: 0 | 1 | 2 = 0;
    private applyingEngineReply = false;
    private autoNextTimer?: number;
    private destroyed = false;

    constructor(
        private readonly ctrl: AnalysisController,
        private readonly options: StudyPracticeOptions,
    ) {
        const tree = ctrl.analysisTree;
        if (!tree) throw new Error('Computer practice requires an analysis tree.');
        const tools = document.querySelector<HTMLElement>('.analysis-tools');
        if (!tools) throw new Error('Computer practice requires the analysis tools panel.');

        this.panel = document.createElement('section');
        this.panel.className = 'study-practice';
        this.panel.setAttribute('aria-label', _('Practice with computer'));
        this.panel.setAttribute('role', 'region');
        this.status = document.createElement('div');
        this.status.className = 'study-practice__status';
        this.status.setAttribute('aria-live', 'polite');
        this.status.setAttribute('aria-atomic', 'true');
        this.status.setAttribute('aria-busy', 'false');
        this.panel.append(this.status);
        tools.append(this.panel);

        this.historyBoard = this.createHistoryBoard();
        this.engine = new AnalysisPracticeEngine(
            {
                postMessage: command => this.ctrl.fsfPostMessage(command),
                availability: () =>
                    this.engineReady()
                        ? { available: true }
                        : { available: false, reason: 'engine-not-ready', message: _('Browser engine is not ready.') },
            },
            event => this.onEngineEvent(event),
        );

        // Ordinary infinite analysis and practice must never own the one browser
        // engine at the same time. This is local-only and does not change the user's
        // saved localAnalysis preference; a remounted normal analysis page restores it.
        this.ctrl.suspendLocalAnalysisForExtension();
        this.resetLocalAttemptTree();
        this.engine.beginSession();
        this.refreshAvailability();
    }

    get state(): StudyPracticeState {
        return this.stateValue;
    }

    get attemptHistory(): readonly StudyPracticeMove[] {
        return this.history.map(entry => ({ ...entry }));
    }

    beforeMoveApplied(move: AnalysisMoveApplication): boolean {
        if (this.destroyed) return false;
        if (move.origin === 'automated-reply')
            return this.applyingEngineReply && this.stateValue.kind === 'engine-thinking';
        return this.stateValue.kind === 'human-turn' && this.ctrl.turnColor === this.options.learnerColor;
    }

    boardInput(turnColor: 'white' | 'black'): 'white' | 'black' | false {
        if (this.destroyed || this.stateValue.kind !== 'human-turn' || turnColor !== this.options.learnerColor)
            return false;
        return this.options.learnerColor;
    }

    onPositionChanged(change: AnalysisPositionChange): void {
        if (this.destroyed) return;
        if (change.origin !== 'played-move' && change.origin !== 'automated-reply') {
            if (change.origin === 'user-navigation' && this.stateValue.kind === 'paused') {
                if (this.ctrl.turnColor === this.options.learnerColor) this.resumeFromPath(change.path);
                else this.render();
            } else if (this.stateValue.kind === 'paused') this.render();
            return;
        }

        const move = change.node?.step.move;
        if (!move) {
            this.setUnavailable('engine-error', _('Practice move history could not be reconstructed.'));
            return;
        }

        const by = change.origin === 'automated-reply' ? 'engine' : 'human';
        if ((by === 'human') !== (this.stateValue.kind === 'human-turn')) {
            this.setUnavailable('engine-error', _('Practice move ownership became inconsistent.'));
            return;
        }

        const parentMoves = this.history.map(entry => entry.move);
        const parentPath = change.previousPath;

        const legalMoves = this.legalMoves();
        if (!legalMoves.has(move)) {
            this.setUnavailable('engine-error', _('A practice move was rejected by the saved variant rules.'));
            return;
        }

        let san: string | undefined;
        try {
            san = this.historyBoard.sanMove(move);
            this.historyBoard.push(move);
        } catch (error) {
            this.setUnavailable('engine-error', error instanceof Error ? error.message : String(error));
            return;
        }
        const promotion = by === 'human' && studyPracticeMovePromotes(move, san);
        this.history.push({
            move,
            fen: change.fen,
            path: change.path,
            by,
            ...(san ? { san } : {}),
            ...(promotion ? { promotion: true } : {}),
        });
        this.paths.push(change.path);
        this.livePath = change.path;

        if (by === 'engine') {
            if (this.isTerminal()) {
                this.finishCurrentPosition();
                return;
            }
            if (this.ctrl.turnColor === this.options.learnerColor) this.enterHumanTurn();
            else this.startEngineReply();
            return;
        }

        this.hintLevel = 0;
        this.clearHintShapes();
        this.lastFeedback = undefined;
        this.lastRetry = undefined;
        this.pendingGrade = {
            playedMove: move,
            parentMoves,
            childMoves: this.history.map(entry => entry.move),
            parentTurnColor: this.options.learnerColor,
            childTurnColor: this.ctrl.turnColor,
            parentPath,
            ...(this.isTerminal() ? { terminalResult: this.gameResult() } : {}),
        };
        this.setState({ kind: 'evaluating-move' });
        this.continuePendingGrade();
    }

    canActivatePath(path: string, origin: AnalysisNavigationOrigin): boolean {
        if (this.destroyed) return false;
        if (origin === 'played-move' || origin === 'automated-reply') return true;
        if (origin === 'reset') return path === '' || path === this.livePath || this.stateValue.kind === 'paused';
        if (origin !== 'user-navigation' || !this.paths.includes(path)) return false;
        if (this.stateValue.kind === 'paused') return true;
        if (this.stateValue.kind === 'human-turn' || this.stateValue.kind === 'engine-thinking') {
            this.pause();
            return true;
        }
        if (this.stateValue.kind === 'ended') {
            const browseIndex = Math.max(0, this.paths.indexOf(this.ctrl.analysisPath ?? this.livePath));
            this.setState({
                kind: 'paused',
                liveKind: this.ctrl.turnColor === this.options.learnerColor ? 'human-turn' : 'engine-thinking',
                browseIndex,
            });
            return true;
        }
        return false;
    }

    allowTreeContextMenu(): boolean {
        return false;
    }

    /** Route engine lines before ordinary analysis consumes them. */
    onEngineLine(line: string): boolean {
        if (this.destroyed) return false;
        const consumed = this.engine.handleLine(line);
        if (!consumed && (line === 'readyok' || line.includes('uciok') || line.startsWith('option name UCI_Variant'))) {
            queueMicrotask(() => this.refreshAvailability());
        }
        return consumed;
    }

    refreshAvailability(): void {
        if (this.destroyed) return;
        // A timed-out stop/ready barrier means engine ownership is no longer
        // trustworthy. E1 deliberately fails closed here; only remounting the
        // page may construct a fresh adapter around the shared engine.
        if (this.stateValue.kind === 'unavailable' && this.stateValue.reason === 'drain-timeout') {
            this.render();
            return;
        }
        const access = this.options.access();
        if (!access.available) {
            this.engine.setBlocked('permission', access.message);
            this.setUnavailable(access.reason, access.message);
            return;
        }
        if (this.ctrl.variant.replayOnly) {
            this.engine.setBlocked('unsupported', _('This variant is available for historical replay only.'));
            this.setUnavailable('unsupported', _('This variant is available for historical replay only.'));
            return;
        }
        if (this.ctrl.variant.twoBoards) {
            this.engine.setBlocked('unsupported', _('Two-board variants are not supported by computer practice.'));
            this.setUnavailable('unsupported', _('Two-board variants are not supported by computer practice.'));
            return;
        }
        if (this.ctrl.uciOk && !this.ctrl.variantSupportedByFSF) {
            this.engine.setBlocked('unsupported', _('This variant is not supported by the browser engine.'));
            this.setUnavailable('unsupported', _('This variant is not supported by the browser engine.'));
            return;
        }
        if (!this.engineReady()) {
            this.setState({ kind: 'initializing' });
            return;
        }

        this.engine.setBlocked(null);
        if (this.isTerminal()) {
            this.finishCurrentPosition();
            return;
        }
        if (
            this.stateValue.kind === 'paused' ||
            this.stateValue.kind === 'ended' ||
            this.stateValue.kind === 'evaluating-move' ||
            this.stateValue.kind === 'engine-thinking'
        )
            return;
        if (this.ctrl.turnColor === this.options.learnerColor) this.enterHumanTurn();
        else this.startEngineReply();
    }

    pause(): boolean {
        if (this.destroyed) return false;
        if (this.stateValue.kind !== 'human-turn' && this.stateValue.kind !== 'engine-thinking') return false;
        const liveKind = this.stateValue.kind;
        this.engine.cancel();
        this.searchPurposes.clear();
        this.evaluationSearches.clear();
        const browseIndex = Math.max(0, this.paths.indexOf(this.ctrl.analysisPath ?? this.livePath));
        this.setState({ kind: 'paused', liveKind, browseIndex });
        return true;
    }

    resume(): boolean {
        if (this.destroyed || this.stateValue.kind !== 'paused') return false;
        if ((this.ctrl.analysisPath ?? '') !== this.livePath) this.ctrl.activateTreePath(this.livePath, true, 'reset');
        if (this.isTerminal()) {
            this.finishCurrentPosition();
            return true;
        }
        if (this.ctrl.turnColor === this.options.learnerColor) this.enterHumanTurn();
        else this.startEngineReply();
        return true;
    }

    private resumeFromPath(path: string): boolean {
        if (this.destroyed || this.stateValue.kind !== 'paused' || this.ctrl.turnColor !== this.options.learnerColor)
            return false;
        const targetIndex = this.paths.indexOf(path);
        if (targetIndex < 0) return false;

        // Lichess practice resumes immediately when the user jumps back to a
        // position where it is their turn. Rewind the private rules board and
        // logical attempt history to the selected position so a different move
        // can start a fresh branch instead of requiring a page reload.
        this.engine.beginSession();
        this.searchPurposes.clear();
        this.evaluationSearches.clear();
        this.goalEvaluationAttempts.clear();
        while (this.history.length > targetIndex) {
            try {
                this.historyBoard.pop();
            } catch (error) {
                this.setUnavailable('engine-error', error instanceof Error ? error.message : String(error));
                return false;
            }
            this.history.pop();
            this.paths.pop();
        }

        this.livePath = path;
        this.pendingGrade = undefined;
        this.pendingGoalFeedback = undefined;
        if (this.autoNextTimer !== undefined) window.clearTimeout(this.autoNextTimer);
        this.autoNextTimer = undefined;
        this.lastFeedback = undefined;
        this.lastRetry = undefined;
        this.hintLevel = 0;
        this.clearHintShapes();
        this.enterHumanTurn();
        return true;
    }

    browse(delta: -1 | 1): boolean {
        if (this.destroyed || this.stateValue.kind !== 'paused') return false;
        const current = this.paths.indexOf(this.ctrl.analysisPath ?? '');
        const next = Math.max(
            0,
            Math.min(this.paths.length - 1, (current < 0 ? this.paths.length - 1 : current) + delta),
        );
        const path = this.paths[next];
        if (path === undefined || path === (this.ctrl.analysisPath ?? '')) return false;
        this.ctrl.activateTreePath(path, true, 'user-navigation');
        if (this.stateValue.kind === 'paused') this.setState({ ...this.stateValue, browseIndex: next });
        return true;
    }

    hint(): boolean {
        if (this.destroyed || this.stateValue.kind !== 'human-turn') return false;
        this.hintLevel = this.hintLevel === 0 ? 1 : this.hintLevel === 1 ? 2 : 0;
        if (this.hintLevel > 0) this.ensureEvaluation(this.history.map(entry => entry.move), this.ctrl.turnColor);
        this.syncHintShapes();
        this.render();
        return true;
    }

    retryBestMove(): boolean {
        if (this.destroyed || !this.lastRetry || this.history.length === 0) return false;
        const { parentPath, bestMove } = this.lastRetry;
        const parentIndex = this.paths.indexOf(parentPath);
        if (parentIndex < 0 || this.history.length <= parentIndex) return false;

        this.engine.beginSession();
        this.searchPurposes.clear();
        this.evaluationSearches.clear();
        this.goalEvaluationAttempts.clear();
        while (this.history.length > parentIndex) {
            try {
                this.historyBoard.pop();
            } catch (error) {
                this.setUnavailable('engine-error', error instanceof Error ? error.message : String(error));
                return false;
            }
            this.history.pop();
            this.paths.pop();
        }

        this.livePath = parentPath;
        this.ctrl.activateTreePath(parentPath, true, 'reset');
        if ((this.ctrl.analysisPath ?? '') !== parentPath) {
            this.setUnavailable('engine-error', _('Practice could not return to the position before your move.'));
            return false;
        }

        const retryMove = this.resolveLegalBestMove(bestMove);
        if (!retryMove) {
            this.setUnavailable('engine-error', _('The suggested best move is no longer legal in this position.'));
            return false;
        }

        this.pendingGrade = undefined;
        this.pendingGoalFeedback = undefined;
        if (this.autoNextTimer !== undefined) window.clearTimeout(this.autoNextTimer);
        this.autoNextTimer = undefined;
        this.lastFeedback = undefined;
        this.lastRetry = undefined;
        this.hintLevel = 0;
        this.clearHintShapes();
        this.enterHumanTurn();
        if (!this.ctrl.applyAnalysisMove(retryMove, 'played-move')) {
            this.setUnavailable('engine-error', _('The suggested best move could not be applied.'));
            return false;
        }
        return true;
    }

    reset(): void {
        if (this.destroyed) return;
        this.engine.beginSession();
        this.searchPurposes.clear();
        this.evaluationSearches.clear();
        this.goalEvaluationAttempts.clear();
        this.evaluations.clear();
        this.pendingGrade = undefined;
        this.pendingGoalFeedback = undefined;
        if (this.autoNextTimer !== undefined) window.clearTimeout(this.autoNextTimer);
        this.autoNextTimer = undefined;
        this.lastFeedback = undefined;
        this.lastRetry = undefined;
        this.hintLevel = 0;
        this.clearHintShapes();
        this.ctrl.activateTreePath('', true, 'reset');
        this.resetLocalAttemptTree();
        this.historyBoard.delete();
        this.historyBoard = this.createHistoryBoard();
        this.history.length = 0;
        this.paths.splice(1);
        this.livePath = '';
        this.setState({ kind: 'initializing' });
        this.refreshAvailability();
    }

    destroy(): void {
        if (this.destroyed) return;
        this.destroyed = true;
        if (this.autoNextTimer !== undefined) window.clearTimeout(this.autoNextTimer);
        this.autoNextTimer = undefined;
        this.engine.destroy();
        this.historyBoard.delete();
        this.clearHintShapes();
        this.panel.remove();
    }

    private createHistoryBoard(): PracticeBoard {
        return new this.ctrl.ffish.Board(
            this.ctrl.engineVariant,
            this.options.initialFen,
            this.ctrl.chess960,
        ) as PracticeBoard;
    }

    private resetLocalAttemptTree(): void {
        const tree = this.ctrl.analysisTree;
        if (!tree) return;
        for (const path of tree.byPath.keys()) if (path) tree.byPath.delete(path);
        tree.root.children = [];
        tree.root.mainlinePly = 0;
        this.ctrl.steps.splice(1);
        this.ctrl.recordedMainlinePly = 0;
        if ((this.ctrl.analysisPath ?? '') !== '') this.ctrl.activateTreePath('', true, 'reset');
    }

    private legalMoves(): Set<string> {
        try {
            return new Set(this.historyBoard.legalMoves().split(' ').filter(Boolean));
        } catch {
            return new Set();
        }
    }

    private isTerminal(): boolean {
        try {
            return this.historyBoard.isGameOver(true);
        } catch {
            return false;
        }
    }

    private gameResult(): string | undefined {
        try {
            return this.historyBoard.result(true);
        } catch {
            return undefined;
        }
    }

    private learnerMoveCount(): number {
        return this.history.reduce((count, move) => count + (move.by === 'human' ? 1 : 0), 0);
    }

    private isCheckmate(): boolean {
        if (!this.isTerminal()) return false;
        try {
            return this.historyBoard.isCheck() && this.historyBoard.numberLegalMoves() === 0;
        } catch {
            return false;
        }
    }

    private currentMoveWasPromotion(): boolean {
        const move = this.history[this.history.length - 1];
        return move?.by === 'human' && move.promotion === true;
    }

    private goalDecision(feedback = this.lastFeedback): StudyPracticeGoalDecision {
        const goal = this.options.goal;
        if (!goal) return 'ongoing';
        return evaluateStudyPracticeGoal({
            goal,
            learnerColor: this.options.learnerColor,
            learnerMoves: this.learnerMoveCount(),
            checkmate: this.isCheckmate(),
            promotion: this.currentMoveWasPromotion(),
            ...(this.isTerminal() ? { terminalResult: this.gameResult() } : {}),
            ...(this.currentEvaluation() ? { evaluation: this.currentEvaluation() } : {}),
            ...(feedback ? { feedbackVerdict: feedback.verdict } : {}),
        });
    }

    private finish(
        feedback = this.lastFeedback,
        result = this.gameResult(),
        goalDecision?: Exclude<StudyPracticeGoalDecision, 'ongoing'>,
    ): void {
        this.engine.cancel();
        this.pendingGrade = undefined;
        this.pendingGoalFeedback = undefined;
        this.hintLevel = 0;
        this.clearHintShapes();
        this.setState({
            kind: 'ended',
            ...(result && result !== '*' ? { result } : {}),
            ...(feedback ? { feedback } : {}),
            ...(goalDecision ? { goalDecision } : {}),
        });
        if (goalDecision === 'success') {
            sound.practiceSuccess();
            this.options.onComplete?.(this.learnerMoveCount());
            if (this.options.autoNext?.() && this.options.hasNextChapter && this.options.onNextChapter) {
                this.autoNextTimer = window.setTimeout(() => {
                    this.autoNextTimer = undefined;
                    if (
                        !this.destroyed &&
                        this.stateValue.kind === 'ended' &&
                        this.stateValue.goalDecision === 'success'
                    )
                        this.options.onNextChapter?.();
                }, 1000);
            }
        } else if (goalDecision === 'failure') {
            sound.practiceFailure();
        }
    }

    private finishCurrentPosition(feedback = this.lastFeedback): void {
        if (!this.options.goal) {
            this.finish(feedback);
            return;
        }
        const decision = this.goalDecision(feedback);
        this.finish(feedback, this.gameResult(), decision === 'ongoing' ? 'failure' : decision);
    }

    private continuePendingGoal(): void {
        if (!this.options.goal || this.pendingGoalFeedback === undefined) return;
        const decision = this.goalDecision(this.pendingGoalFeedback);
        if (decision === 'indeterminate') {
            const moves = this.history.map(entry => entry.move);
            if (this.ensureGoalEvaluation(moves, this.ctrl.turnColor)) return;
        }

        const feedback = this.pendingGoalFeedback;
        this.pendingGoalFeedback = undefined;
        if (decision === 'ongoing') this.advanceAfterHumanMove();
        else this.finish(feedback, this.gameResult(), decision);
    }

    private engineReady(): boolean {
        return (
            this.ctrl.localEngine &&
            this.ctrl.isEngineReady &&
            this.ctrl.variantSupportedByFSF &&
            !this.ctrl.localAnalysis &&
            this.ctrl.isPracticeEngineIdle()
        );
    }

    private positionKey(moves: readonly string[]): string {
        return moves.join('\u0000');
    }

    private searchOptions() {
        return [
            { name: 'UCI_Variant', value: this.ctrl.engineVariant },
            { name: 'UCI_Chess960', value: this.ctrl.chess960 },
            { name: 'Use NNUE', value: false },
        ] as const;
    }

    private launchSearch(
        purpose: SearchPurpose,
        request: Parameters<AnalysisPracticeEngine['search']>[0],
    ): AnalysisPracticeSearchOwner {
        this.launchingSearchPurpose = purpose;
        const owner = this.engine.search(request);
        this.launchingSearchPurpose = undefined;
        if (this.engine.isCurrent(owner) && this.stateValue.kind !== 'unavailable') {
            this.searchPurposes.set(ownerKey(owner), purpose);
        }
        return owner;
    }

    private ensureEvaluation(moves: readonly string[], turnColor: 'white' | 'black'): void {
        if (this.destroyed || !this.engineReady()) return;
        const key = this.positionKey(moves);
        if (this.evaluations.has(key) || this.evaluationSearches.has(key)) return;
        this.evaluationSearches.add(key);
        this.launchSearch(
            { kind: 'evaluation', key, moves: [...moves], turnColor },
            {
                initialFen: this.options.initialFen,
                moves,
                budget: { type: 'nodes', value: PRACTICE_FEEDBACK_NODES },
                multiPv: 1,
                options: this.searchOptions(),
            },
        );
    }

    private ensureGoalEvaluation(moves: readonly string[], turnColor: 'white' | 'black'): boolean {
        if (this.destroyed) return false;
        const key = this.positionKey(moves);
        if (this.evaluationSearches.has(key)) return true;
        if (this.goalEvaluationAttempts.has(key) || !this.engineReady()) return false;

        // Goal evaluation requires depth >= PRACTICE_GOAL_MIN_DEPTH. A fixed node
        // budget can stop one iteration earlier, especially with multiple Threads,
        // so ask the engine for the exact reliability threshold once before giving up.
        this.goalEvaluationAttempts.add(key);
        this.evaluationSearches.add(key);
        this.launchSearch(
            { kind: 'evaluation', key, moves: [...moves], turnColor },
            {
                initialFen: this.options.initialFen,
                moves,
                budget: { type: 'depth', value: PRACTICE_GOAL_MIN_DEPTH },
                multiPv: 1,
                options: this.searchOptions(),
            },
        );
        return true;
    }

    private evaluationFor(moves: readonly string[]): PositionEvaluation | undefined {
        return this.evaluations.get(this.positionKey(moves));
    }

    private enterHumanTurn(): void {
        if (this.destroyed) return;
        if (this.stateValue.kind !== 'human-turn') {
            this.hintLevel = 0;
            this.clearHintShapes();
            this.setState({ kind: 'human-turn' });
        } else {
            this.render();
        }
        this.ensureEvaluation(this.history.map(entry => entry.move), this.ctrl.turnColor);
    }

    private continuePendingGrade(): void {
        const pending = this.pendingGrade;
        if (!pending || this.destroyed) return;

        const parent = this.evaluationFor(pending.parentMoves);
        if (!parent) {
            this.ensureEvaluation(pending.parentMoves, pending.parentTurnColor);
            return;
        }

        // A completed best-move match needs no numerical comparison. Likewise, an
        // exact terminal win cannot be improved upon. The pure grader handles both.
        if (pending.terminalResult) {
            this.completeGrade(
                gradeStudyPracticeMove({
                    learnerColor: this.options.learnerColor,
                    playedMove: pending.playedMove,
                    parent,
                    terminalResult: pending.terminalResult,
                    ...(parent.bestSan ? { bestSan: parent.bestSan } : {}),
                }),
            );
            return;
        }

        if (parent.bestMove && studyPracticeMovesEquivalent(parent.bestMove, pending.playedMove)) {
            this.completeGrade(
                gradeStudyPracticeMove({
                    learnerColor: this.options.learnerColor,
                    playedMove: pending.playedMove,
                    parent,
                    ...(parent.bestSan ? { bestSan: parent.bestSan } : {}),
                }),
            );
            return;
        }

        if (!parent.score || parent.bound) {
            this.completeGrade(
                gradeStudyPracticeMove({
                    learnerColor: this.options.learnerColor,
                    playedMove: pending.playedMove,
                    parent,
                    ...(parent.bestSan ? { bestSan: parent.bestSan } : {}),
                }),
            );
            return;
        }

        const child = this.evaluationFor(pending.childMoves);
        if (!child) {
            this.ensureEvaluation(pending.childMoves, pending.childTurnColor);
            return;
        }

        this.completeGrade(
            gradeStudyPracticeMove({
                learnerColor: this.options.learnerColor,
                playedMove: pending.playedMove,
                parent,
                child,
                ...(parent.bestSan ? { bestSan: parent.bestSan } : {}),
            }),
        );
    }

    private completeGrade(feedback: StudyPracticeFeedback): void {
        if (this.destroyed || !this.pendingGrade) return;
        const pending = this.pendingGrade;
        this.lastFeedback = feedback;
        this.lastRetry = feedback.bestMove
            ? { parentPath: pending.parentPath, bestMove: feedback.bestMove }
            : undefined;
        const terminalResult = pending.terminalResult;
        this.pendingGrade = undefined;
        if (terminalResult) {
            if (this.options.goal) this.finishCurrentPosition(feedback);
            else this.finish(feedback, terminalResult);
            return;
        }
        if (this.options.goal) {
            this.pendingGoalFeedback = feedback;
            this.continuePendingGoal();
            return;
        }
        this.advanceAfterHumanMove();
    }

    private advanceAfterHumanMove(): void {
        if (this.isTerminal()) {
            this.finishCurrentPosition();
            return;
        }
        if (this.ctrl.turnColor === this.options.learnerColor) this.enterHumanTurn();
        else this.startEngineReply();
    }

    private resolveLegalBestMove(bestMove: string): string | undefined {
        const legalMoves = this.legalMoves();
        if (legalMoves.has(bestMove)) return bestMove;
        return [...legalMoves].find(move => studyPracticeMovesEquivalent(move, bestMove));
    }

    private bestSanAt(moves: readonly string[], bestMove: string | null): string | undefined {
        if (!bestMove) return undefined;
        const board = this.createHistoryBoard();
        try {
            for (const move of moves) board.push(move);
            const legalMoves = new Set(board.legalMoves().split(' ').filter(Boolean));
            const canonical = legalMoves.has(bestMove)
                ? bestMove
                : [...legalMoves].find(move => studyPracticeMovesEquivalent(move, bestMove));
            return canonical ? board.sanMove(canonical) : undefined;
        } catch {
            return undefined;
        } finally {
            board.delete();
        }
    }

    private startEngineReply(): void {
        if (this.destroyed) return;
        const access = this.options.access();
        if (!access.available) {
            this.setUnavailable(access.reason, access.message);
            return;
        }
        if (!this.engineReady()) {
            this.setState({ kind: 'initializing' });
            return;
        }
        this.hintLevel = 0;
        this.clearHintShapes();
        this.setState({ kind: 'engine-thinking' });
        const moves = this.history.map(entry => entry.move);
        const turnColor = this.ctrl.turnColor;
        this.launchSearch(
            { kind: 'reply', moves, turnColor },
            {
                initialFen: this.options.initialFen,
                moves,
                budget: { type: 'nodes', value: PRACTICE_SEARCH_NODES },
                multiPv: 1,
                options: this.searchOptions(),
            },
        );
    }

    private showCurrentPositionEvaluation(purpose: SearchPurpose, info: AnalysisPracticeInfo): void {
        if (this.stateValue.kind === 'paused' || !info.score || info.depth === undefined) return;
        if (this.positionKey(purpose.moves) !== this.positionKey(this.history.map(entry => entry.move))) return;

        const ceval: Ceval = {
            d: info.depth,
            multipv: info.multiPv,
            s: { ...info.score },
            ...(info.pv.length > 0 ? { p: info.pv.join(' ') } : {}),
        };
        this.ctrl.drawPracticeEval(ceval, purpose.turnColor);
    }

    private onEngineEvent(event: AnalysisPracticeEngineEvent): void {
        if (this.destroyed || !this.engine.isCurrent(event.owner)) return;
        const key = ownerKey(event.owner);
        const purpose = this.searchPurposes.get(key) ?? this.launchingSearchPurpose;
        if (!purpose) return;
        if (event.type !== 'info') this.searchPurposes.delete(key);
        else this.showCurrentPositionEvaluation(purpose, event.info);

        if (event.type === 'unavailable') {
            if (event.reason === 'destroyed') return;
            if (purpose.kind === 'evaluation') {
                this.evaluationSearches.delete(purpose.key);
                if (event.reason === 'timeout') {
                    this.evaluations.set(purpose.key, {
                        key: purpose.key,
                        moves: purpose.moves,
                        turnColor: purpose.turnColor,
                    });
                    this.continuePendingGrade();
                    this.continuePendingGoal();
                    this.syncHintShapes();
                    this.render();
                    return;
                }
            }
            const reason = event.reason === 'permission' ? 'computer-disabled' : event.reason;
            this.setUnavailable(reason, event.message);
            return;
        }
        if (event.type !== 'bestmove') return;

        if (purpose.kind === 'evaluation') {
            this.evaluationSearches.delete(purpose.key);
            const bestSan = this.bestSanAt(purpose.moves, event.move);
            const evaluation: PositionEvaluation = {
                key: purpose.key,
                moves: purpose.moves,
                turnColor: purpose.turnColor,
                ...(event.info?.depth !== undefined ? { depth: event.info.depth } : {}),
                bestMove: event.move,
                ...(event.info?.score ? { score: event.info.score } : {}),
                ...(event.info?.bound ? { bound: event.info.bound } : {}),
                ...(bestSan ? { bestSan } : {}),
            };
            this.evaluations.set(purpose.key, evaluation);
            this.continuePendingGrade();
            this.continuePendingGoal();
            this.syncHintShapes();
            this.render();
            return;
        }

        if (this.stateValue.kind !== 'engine-thinking') return;
        if (!event.move) {
            if (this.isTerminal()) this.finishCurrentPosition();
            else this.setUnavailable('engine-error', _('The browser engine returned no legal move.'));
            return;
        }
        if (!this.legalMoves().has(event.move)) {
            this.setUnavailable('engine-error', _('The browser engine returned an illegal move.'));
            return;
        }

        this.applyingEngineReply = true;
        try {
            if (!this.ctrl.applyAnalysisMove(event.move, 'automated-reply')) {
                this.setUnavailable('engine-error', _('The browser engine move could not be applied.'));
            }
        } finally {
            this.applyingEngineReply = false;
        }
    }

    private setUnavailable(reason: StudyPracticeUnavailableReason, message?: string): void {
        this.engine.cancel();
        this.hintLevel = 0;
        this.clearHintShapes();
        this.setState({ kind: 'unavailable', reason, ...(message ? { message } : {}) });
    }

    private setState(state: StudyPracticeState): void {
        if (this.destroyed) return;
        this.stateValue = state;
        this.syncBoardInput();
        this.syncHintShapes();
        this.render();
        this.options.onStateChange?.(state);
    }

    private syncBoardInput(): void {
        const color = this.boardInput(this.ctrl.turnColor);
        this.ctrl.chessground.cancelPremove();
        this.ctrl.chessground.set({
            movable: { color: color === false ? undefined : color },
            premovable: { enabled: false },
        });
    }

    private currentEvaluation(): PositionEvaluation | undefined {
        return this.evaluationFor(this.history.map(entry => entry.move));
    }

    private syncHintShapes(): void {
        if (this.stateValue.kind !== 'human-turn' || this.hintLevel === 0) {
            this.clearHintShapes();
            return;
        }
        const bestMove = this.currentEvaluation()?.bestMove;
        if (!bestMove) {
            this.clearHintShapes();
            return;
        }
        const canonical = this.resolveLegalBestMove(bestMove) ?? bestMove;
        const shapes = this.hintShapes(canonical, this.hintLevel);
        this.ctrl.autoShapes = shapes.length ? [shapes] : [];
        this.ctrl.chessground.setAutoShapes(shapes);
    }

    private hintShapes(move: string, level: 1 | 2): DrawShape[] {
        let converted = uci2cg(move);
        if (converted.startsWith('+')) converted = converted.slice(1);
        const at = converted.indexOf('@');
        if (at >= 0) {
            const dest = boardKey(this.ctrl, converted.slice(at + 1, at + 3));
            return dest ? [{ orig: dest, brush: 'paleBlue' }] : [];
        }

        const primary = converted.split(',', 1)[0];
        const orig = boardKey(this.ctrl, primary.slice(0, 2));
        if (!orig) return [];
        if (level === 1) return [{ orig, brush: 'paleBlue' }];
        const dest = boardKey(this.ctrl, primary.slice(2, 4));
        if (!dest) return [{ orig, brush: 'paleBlue' }];
        const shapes: DrawShape[] = [
            { orig, dest, brush: 'paleBlue', piece: undefined, modifiers: { lineWidth: 14 } },
        ];
        if (converted.includes(',')) {
            const placement = boardKey(this.ctrl, converted.slice(-2));
            if (placement) shapes.push({ orig: placement, brush: 'paleBlue' });
        }
        return shapes;
    }

    private clearHintShapes(): void {
        this.ctrl.autoShapes = [];
        this.ctrl.chessground.setAutoShapes([]);
    }

    private feedbackTitle(feedback: StudyPracticeFeedback): string {
        switch (feedback.verdict) {
            case 'good':
                return _('Good move');
            case 'inaccuracy':
                return _('Inaccuracy');
            case 'mistake':
                return _('Mistake');
            case 'blunder':
                return _('Blunder');
            case 'unknown':
                return _('Move played');
        }
    }

    private feedbackMessage(feedback: StudyPracticeFeedback): string {
        if (feedback.verdict === 'good') return _('Good move.');
        if (feedback.verdict === 'unknown') return _('There was not enough engine information to grade this move.');
        return _('Approximate engine feedback: %1.', this.feedbackTitle(feedback));
    }

    private feedbackBestMessage(feedback: StudyPracticeFeedback): string | undefined {
        if (!feedback.bestMove) return undefined;
        const move = feedback.bestSan ?? feedback.bestMove;
        return feedback.verdict === 'good' ? _('Another strong move was %1.', move) : _('Best was %1.', move);
    }

    private outcomeMessage(result: string | undefined): string {
        switch (studyPracticeOutcomeText(result, this.options.learnerColor)) {
            case 'learner-win':
                return _('You won.');
            case 'computer-win':
                return _('The computer won.');
            case 'draw':
                return _('Draw.');
            case 'game-over':
                return result ? _('Game over: %1', result) : _('The position is terminal.');
        }
    }

    private render(): void {
        const state = this.stateValue;
        this.status.replaceChildren();

        const title = document.createElement('div');
        title.className = 'study-practice__title';
        title.textContent = _('Practice with computer');

        const feedback = document.createElement('div');
        feedback.className = 'study-practice__feedback';
        const player = document.createElement('div');
        player.className = 'study-practice__player';
        const mark = document.createElement('div');
        mark.className = `study-practice__mark ${this.ctrl.variant.pieceFamily}`;
        const instruction = document.createElement('div');
        instruction.className = 'study-practice__instruction';
        const heading = document.createElement('strong');
        const detail = document.createElement('div');
        detail.className = 'study-practice__detail';
        const actions = document.createElement('div');
        actions.className = 'study-practice__actions';

        const addText = (text: string) => {
            const line = document.createElement('span');
            line.textContent = text;
            detail.append(line);
        };
        const addButton = (label: string, action: () => void, primary = false) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `study-practice__action${primary ? ' primary' : ''}`;
            button.textContent = label;
            button.addEventListener('click', event => {
                const restoreKeyboardFocus = event.detail === 0 || document.activeElement === button;
                action();
                if (
                    restoreKeyboardFocus &&
                    !this.destroyed &&
                    !this.panel.contains(document.activeElement)
                )
                    this.status.querySelector<HTMLButtonElement>('.study-practice__action')?.focus();
            });
            actions.append(button);
        };
        const addTurnPiece = () => {
            const piece = document.createElement('piece');
            piece.classList.add(this.ctrl.variant.kingRoles[0] ?? 'k-piece', this.ctrl.turnColor);
            piece.setAttribute('aria-hidden', 'true');
            mark.append(piece);
            boardSettings.updateScopedPieceStyle(this.ctrl.variant, mark, this.ctrl.steps?.[0]?.fen ?? this.ctrl.fullfen);
        };
        const addOffMark = () => {
            mark.classList.add('off');
            mark.textContent = '!';
            mark.setAttribute('aria-hidden', 'true');
        };

        const commentFeedback = state.kind === 'ended' ? state.feedback : this.lastFeedback;
        this.panel.classList.remove('good', 'inaccuracy', 'mistake', 'blunder', 'unknown');
        if (commentFeedback) this.panel.classList.add(commentFeedback.verdict);

        this.status.setAttribute(
            'aria-busy',
            String(
                state.kind === 'initializing' ||
                    state.kind === 'evaluating-move' ||
                    state.kind === 'engine-thinking',
            ),
        );

        if (state.kind === 'initializing') {
            addTurnPiece();
            heading.textContent = _('Starting computer practice');
            addText(_('Waiting for the browser engine…'));
        } else if (state.kind === 'human-turn') {
            addTurnPiece();
            heading.textContent = _('Your turn');
            addButton(
                this.hintLevel === 0
                    ? _('Get a hint')
                    : this.hintLevel === 1
                      ? _('See best move')
                      : _('Hide best move'),
                () => this.hint(),
            );
        } else if (state.kind === 'evaluating-move') {
            addTurnPiece();
            heading.textContent = _('Computer is thinking…');
        } else if (state.kind === 'engine-thinking') {
            addTurnPiece();
            heading.textContent = _('Computer is thinking…');
        } else if (state.kind === 'paused') {
            addOffMark();
            heading.textContent = _('You browsed away');
            addButton(_('Resume practice'), () => this.resume(), true);
        } else if (state.kind === 'ended') {
            addTurnPiece();
            if (state.goalDecision === 'success') {
                heading.textContent = _('Success!');
                addText(_('Practice goal completed in %1 move(s).', String(this.learnerMoveCount())));
            } else if (state.goalDecision === 'failure') {
                heading.textContent = _('Practice goal not reached');
                addText(_('Try the exercise again.'));
            } else if (state.goalDecision === 'indeterminate') {
                heading.textContent = _('Result unclear');
                addText(_('The bounded browser engine could not evaluate the goal reliably.'));
                addButton(_('Retry'), () => this.reset(), true);
            } else {
                heading.textContent = state.result === '1-0' || state.result === '0-1' ? _('Checkmate') : _('Draw');
                addText(this.outcomeMessage(state.result));
            }
        } else {
            addOffMark();
            heading.textContent = _('Practice unavailable');
            addText(state.message ?? this.unavailableMessage(state.reason));
            if (state.reason !== 'drain-timeout')
                addButton(_('Retry'), () => this.refreshAvailability(), true);
        }

        if (this.options.canAnalyse && this.options.onAnalyse) addButton(_('Analysis'), this.options.onAnalyse);

        instruction.append(heading);
        if (detail.childNodes.length) instruction.append(detail);
        if (actions.childNodes.length) instruction.append(actions);
        player.append(mark, instruction);
        feedback.append(player);
        this.status.append(title, feedback);

        if (state.kind === 'ended' && this.options.showNextChapterOnEnd && this.options.onNextChapter) {
            const nextChapter = document.createElement('button');
            nextChapter.type = 'button';
            nextChapter.className = 'study-practice__next-chapter';
            const play = document.createElement('i');
            play.className = 'icon-play';
            play.setAttribute('aria-hidden', 'true');
            nextChapter.append(play, document.createTextNode(_('Next chapter')));
            nextChapter.addEventListener('click', () => this.options.onNextChapter?.());
            this.status.append(nextChapter);
        } else if (state.kind === 'evaluating-move') {
            const comment = document.createElement('div');
            comment.className = 'study-practice__comment waiting';
            const wait = document.createElement('span');
            wait.className = 'study-practice__wait';
            wait.textContent = _('Evaluating your move…');
            comment.append(wait);
            this.status.append(comment);
        } else if (commentFeedback) {
            const comment = document.createElement('div');
            comment.className = `study-practice__comment ${commentFeedback.verdict}`;
            const verdict = document.createElement('span');
            verdict.className = 'study-practice__verdict';
            verdict.textContent = this.feedbackTitle(commentFeedback);
            comment.append(verdict);

            if (commentFeedback.verdict === 'unknown') {
                const message = document.createElement('span');
                message.className = 'study-practice__best';
                message.textContent = this.feedbackMessage(commentFeedback);
                comment.append(message);
            }

            const best = this.feedbackBestMessage(commentFeedback);
            if (best) {
                const bestMove = document.createElement(this.lastRetry ? 'button' : 'span');
                bestMove.className = 'study-practice__best';
                bestMove.textContent = best;
                if (bestMove instanceof HTMLButtonElement) {
                    bestMove.type = 'button';
                    bestMove.addEventListener('click', () => this.retryBestMove());
                }
                comment.append(bestMove);
            }
            this.status.append(comment);
        }
    }

    private unavailableMessage(reason: StudyPracticeUnavailableReason): string {
        switch (reason) {
            case 'computer-disabled':
                return _('Computer analysis is disabled for this study.');
            case 'active-game':
                return _('Computer practice is unavailable while you have an active game.');
            case 'unsupported':
                return _('This variant is not supported by the browser engine.');
            case 'timeout':
                return _('The browser engine took too long to move.');
            case 'drain-timeout':
                return _('The browser engine could not safely restart. Reload the page to try again.');
            case 'engine-error':
                return _('The browser engine stopped unexpectedly.');
            case 'engine-not-ready':
                return _('Browser engine is not ready.');
        }
    }
}
