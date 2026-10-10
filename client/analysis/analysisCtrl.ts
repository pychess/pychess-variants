import { h, VNode } from 'snabbdom';

import * as Mousetrap from 'mousetrap';

import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { DrawShape } from 'chessgroundx/draw';

import { _ } from '../i18n';
import { sound } from '../sound';
import { uci2LastMove, uci2cg, getTurnColor } from '../chess';
import { crosstableView } from '../crosstable';
import { chatView } from '../chat';
import { createMovelistButtons, updateMovelist, selectMove } from '../movelist';
import { povChances } from './winningChances';
import { copyTextToClipboard } from '../clipboard';
import { analysisChart } from './analysisChart';
import { movetimeChart } from './movetimeChart';
import { renderClocks } from './analysisClock';
import { materializeGameHistory } from './gameHistory';
import { copyBoardToPNG } from '../png';
import { boardSettings } from '../boardSettings';
import { nnueLookupContextForVariant, officialNnueNetwork } from '../nnueManifest';
import { loadNnueFile, loadOfficialNnueFile, removeObsoleteOfficialNnue } from '../nnueStorage';
import { patch, downloadPgnText } from '../document';
import { variantsIni } from '../variantsIni';
import { Chart } from 'highcharts';
import { PyChessModel } from '../types';
import { Ceval, MsgBoard, MsgUserConnected, Step, CrossTable } from '../messages';
import { MsgAnalysis, MsgAnalysisBoard } from './analysisType';
import { GameController } from '../gameCtrl';
import { analysisSettings, EngineSettings } from './analysisSettings';
import { setAriaTabClick } from '../view';
import { createWebsocket } from '@/socket/webSocketUtils';
import { setPocketRowCssVars } from '../pocketRow';
import { updateCount, updatePoint } from '../info';
import { fogFen, variantConfigIni } from '../variants';
import { hideKeyboardHelp, isKeyboardHelpShortcut, showKeyboardHelp } from './keyboardHelp';
import { PvHoverPreview } from './pvHoverPreview';
import { alertDialog } from '../alertDialog';
import { confirmDialog } from '../confirmDialog';
import { animatePassMove } from '../passMove';
import { mergeServerAdvice, renderFullTreePgnMoveText, renderNodeAnnotations } from './analysisTree';
import { AnalysisTreeController } from './analysisTreeCtrl';
import { analysisContext, type AnalysisContext } from './analysisContext';
import type {
    AnalysisExtension,
    AnalysisEvaluationDelivery,
    AnalysisExtensionFactory,
    AnalysisMoveApplication,
    AnalysisNavigationOrigin,
} from './analysisExtension';
import {
    CEVAL_ACTIVE_ROUNDS_STORAGE_KEY,
    CEVAL_DISABLE_STORAGE_KEY,
    buildCevalPositionPayload,
    hasActiveEligibleLiveGame,
    publishCevalPosition,
} from '../antiCheat';

const EVAL_REGEX = new RegExp(
    '' +
        /^info depth (\d+) seldepth \d+ multipv (\d+) /.source +
        /score (cp|mate) ([-\d]+) /.source +
        /(?:(upper|lower)bound )?nodes (\d+) nps \S+ /.source +
        /(?:hashfull \d+ )?(?:tbhits \d+ )?time (\S+) /.source +
        /pv (.+)/.source,
);

const maxDepth = 18;
const emptySan = '\xa0';

export function titleCase(words: string) {
    return words
        .split(' ')
        .map(w => w.substring(0, 1).toUpperCase() + w.substring(1).toLowerCase())
        .join(' ');
}

export class AnalysisController extends GameController {
    vpgn: VNode;
    vscore: VNode | HTMLElement;
    vinfo: VNode | HTMLElement;
    vpvlines: VNode[] | HTMLElement[];
    settings: boolean;
    uci_usi: string;
    plyVari: number;
    UCImovelist: string[];
    analysisChart: Chart;
    movetimeChart: Chart;
    chartFunctions: any[];
    recordedMainlinePly?: number;
    localEngine: boolean;
    localAnalysis: boolean;
    maxDepth: number;
    isAnalysisBoard: boolean;
    isEngineReady: boolean;
    arrow: boolean;
    multipv: number;
    threads: number;
    hash: number;
    nnue: boolean;
    readonly nnueDownloadRoot: string;
    evalFile: string;
    uciOk: boolean;
    nnueOk: boolean;
    importedBy: string;
    embed: boolean;
    puzzle: boolean;
    ongoing: boolean;
    fsfDebug: boolean;
    fsfError: string[];
    fsfEngineBoard: any; // used to convert pv UCI move list to SAN
    variantSupportedByFSF: boolean;
    autoShapes: DrawShape[][];
    lastBroadcastLocalAnalysisFen?: string;
    inlineNotation: boolean;
    disclosureMode: boolean;
    readonly tree: AnalysisTreeController;
    readonly analysisContext: AnalysisContext;
    readonly analysisExtension?: AnalysisExtension;
    keyboardHelpOpen: boolean;
    private readonly onKeyboardHelpShortcutKeyDown: (event: KeyboardEvent) => void;
    private readonly onKeyboardHelpKeyDown: (event: KeyboardEvent) => void;
    private readonly pvHoverPreview: PvHoverPreview;
    private awaitingStopReadyok: boolean;
    private pendingGoAfterStopReadyok: boolean;
    private fsfOriginalPrompt?: typeof window.prompt;
    private fsfInputQueue: string[];
    private loadedNnueFilename?: string;
    private lastRoundBoardSnapshot?: string;
    private destroyed = false;
    private analysisSessionGeneration = 0;
    private readonly analysisSessionCleanups = new Set<() => void>();
    private engineConfigReady?: Promise<void>;
    private resolveEngineConfig?: () => void;
    private readonly onEngineBoardUnload = () => this.fsfEngineBoard?.delete();

    constructor(el: HTMLElement, model: PyChessModel, extensionFactory?: AnalysisExtensionFactory) {
        super(
            el,
            model,
            model.fen,
            document.getElementById('pocket0') as HTMLElement,
            document.getElementById('pocket1') as HTMLElement,
            '',
        );
        this.analysisContext = analysisContext(model);
        this.tree = new AnalysisTreeController(this);
        this.analysisExtension = extensionFactory?.(this);
        this.pvHoverPreview = new PvHoverPreview(this.variant);
        this.fsfError = [];
        // Compatibility properties for existing callers. New mode-specific code should
        // prefer analysisContext/capabilities instead of recomputing these combinations.
        this.embed = this.analysisContext.embed;
        this.puzzle = this.analysisContext.puzzle;
        this.isAnalysisBoard = this.analysisContext.analysisBoard;
        if (this.analysisContext.capabilities.resizableCharts) {
            this.chartFunctions = [analysisChart, movetimeChart];
        }

        const onOpen = () => {
            if (this.embed) {
                this.doSend({ type: 'embed_user_connected', gameId: this.gameId });
            } else if (!this.isAnalysisBoard) {
                this.doSend({ type: 'game_user_connected', username: this.username, gameId: this.gameId });
            }
        };

        this.ongoing = this.analysisContext.ongoing;

        // is local stockfish.wasm engine supported at all
        this.localEngine = false;

        // is local engine analysis enabled? (the switch)
        this.localAnalysis =
            localStorage.localAnalysis !== undefined &&
            this.analysisContext.capabilities.localAnalysisAllowed &&
            !this.isLocalAnalysisBlockedByAntiCheat() &&
            this.isLocalAnalysisAllowedByExtension() &&
            localStorage.localAnalysis === 'true';

        // UCI isready/readyok
        this.isEngineReady = false;

        // ply where current interactive analysis variation line starts in the main line
        this.plyVari = 0;

        // used for interactive analysis go command
        this.UCImovelist = [];

        this.settings = true;
        this.dblClickPass = true;

        this.arrow = localStorage.arrow === undefined ? true : localStorage.arrow === 'true';
        const infiniteAnalysis =
            localStorage.infiniteAnalysis === undefined ? false : localStorage.infiniteAnalysis === 'true';
        this.maxDepth = infiniteAnalysis ? 99 : maxDepth;
        this.multipv = localStorage.multipv === undefined ? 1 : parseInt(localStorage.multipv);
        this.evalFile =
            localStorage[`${this.variant.name}-nnue`] === undefined ? '' : localStorage[`${this.variant.name}-nnue`];
        this.threads = localStorage.threads === undefined ? 1 : parseInt(localStorage.threads);
        this.hash = localStorage.hash === undefined ? 16 : parseInt(localStorage.hash);
        this.nnue = localStorage.nnue === undefined ? true : localStorage.nnue === 'true';
        this.nnueDownloadRoot = model.nnueDownloadRoot;
        this.fsfDebug = localStorage.fsfDebug === undefined ? false : localStorage.fsfDebug === 'true';
        this.inlineNotation = localStorage.inlineNotation === 'true';
        this.disclosureMode = localStorage.disclosureMode === 'true';
        // This flag is browser/WASM-only. Do not use it to gate fishnet play or
        // server-side analysis; those engines can support a different variant set.
        this.variantSupportedByFSF = false;
        this.uciOk = false;
        this.nnueOk = false;
        this.importedBy = '';
        this.lastBroadcastLocalAnalysisFen = undefined;
        this.keyboardHelpOpen = false;
        this.awaitingStopReadyok = false;
        this.pendingGoAfterStopReadyok = false;
        this.fsfInputQueue = [];
        this.onKeyboardHelpShortcutKeyDown = (event: KeyboardEvent) => {
            if (this.keyboardHelpOpen || !isKeyboardHelpShortcut(event)) return;

            const target = event.target;
            if (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]'))
                return;

            event.preventDefault();
            event.stopPropagation();
            this.openKeyboardHelp();
        };
        this.onKeyboardHelpKeyDown = (event: KeyboardEvent) => {
            if (!this.keyboardHelpOpen) return;

            const isShortcutToggle = isKeyboardHelpShortcut(event);
            if (event.key === 'Escape' || isShortcutToggle) {
                event.preventDefault();
                event.stopPropagation();
                this.closeKeyboardHelp();
                return;
            }

            if (event.key === 'Tab') return;

            event.preventDefault();
            event.stopPropagation();
        };

        if (this.analysisContext.capabilities.localAnalysisAllowed) {
            window.addEventListener('storage', this.onAntiCheatStorage);
            this.refreshLocalAnalysisAvailabilityForAntiCheat();
        }
        document.addEventListener('keydown', this.onKeyboardHelpShortcutKeyDown, true);

        this.chessground.set({
            orientation: this.variant.name === 'racingkings' ? 'white' : this.mycolor,
            turnColor: this.turnColor,
            movable: {
                free: false,
                color: this.turnColor,
                events: {
                    after: (orig, dest, meta) => this.onUserMove(orig, dest, meta),
                    afterNewPiece: (piece, dest, meta) => this.onUserDrop(piece, dest, meta),
                },
            },
            events: {
                move: this.onMove(),
                dropNewPiece: this.onDrop(),
                select: this.onSelect(),
            },
            drawable: {
                onChange: shapes => this.analysisExtension?.onShapesChanged?.(shapes),
            },
        });

        if (this.hasPockets) {
            setPocketRowCssVars(this);
        }

        if (this.analysisContext.capabilities.gamePanels) {
            this.ctableContainer = document.getElementById('panel-3') as HTMLElement;
            if (model['ct']) {
                this.ctableContainer = patch(this.ctableContainer, h('panel-3'));
                this.ctableContainer = patch(
                    this.ctableContainer,
                    crosstableView(model['ct'] as CrossTable, this.gameId),
                );
            }
        }

        createMovelistButtons(this);
        this.vmovelist = document.getElementById('movelist') as HTMLElement;

        if (this.analysisContext.capabilities.roundChat) {
            patch(document.getElementById('roundchat') as HTMLElement, chatView(this, 'roundchat'));
        }

        if (this.analysisContext.capabilities.engineTools) {
            const engineSettings = new EngineSettings(this);
            const et = document.querySelector('.engine-toggle') as HTMLElement;
            patch(et, engineSettings.view());

            this.vscore = document.getElementById('score') as HTMLElement;
            this.vinfo = document.getElementById('info') as HTMLElement;
            this.vpvlines = Array(5)
                .fill(null)
                .map((_, i) => document.querySelector(`.pvbox :nth-child(${i + 1})`) as HTMLElement);
            this.pvHoverPreview.init(
                document.querySelector('div.pvbox') as HTMLElement | null,
                this.fullfen,
                this.chessground.state.orientation,
            );

            if (!this.puzzle) {
                (document.querySelector('div.feedback') as HTMLElement).style.display = 'none';
                const pgn = this.isAnalysisBoard ? this.getPgn() : this.pgn;
                this.renderFENAndPGN(pgn);
            }
        }

        if (this.variant.ui.materialPoint) {
            const miscW = document.getElementById('misc-infow') as HTMLElement;
            const miscB = document.getElementById('misc-infob') as HTMLElement;
            miscW.style.textAlign = 'right';
            miscB.style.textAlign = 'left';
            miscW.style.width = '100px';
            miscB.style.width = '100px';

            patch(document.getElementById('misc-info-center') as HTMLElement, h('div#misc-info-center', '-'));
            (document.getElementById('misc-info') as HTMLElement).style.justifyContent = 'space-around';

            [this.vmiscInfoW, this.vmiscInfoB] = updatePoint(this.variant, this.fullfen, miscW, miscB);
        }

        if (this.variant.ui.counting) {
            (document.getElementById('misc-infow') as HTMLElement).style.textAlign = 'center';
            (document.getElementById('misc-infob') as HTMLElement).style.textAlign = 'center';
        }

        const analysisTabs = document.querySelector<HTMLElement>('.analysis-tabs');
        if (analysisTabs) setAriaTabClick('analysis_tab', analysisTabs);

        if (this.analysisContext.capabilities.analysisTabs && analysisTabs) {
            const initialEl = analysisTabs.querySelector<HTMLElement>('[data-initial="true"]');
            if (initialEl) {
                initialEl.setAttribute('aria-selected', 'true');
                const controls = initialEl.getAttribute('aria-controls');
                const panel = controls ? document.getElementById(controls) : null;
                if (panel) panel.style.display = 'block';
            }

            const menuEl = document.getElementById('bars');
            if (menuEl) menuEl.style.display = 'block';
        }
        if (this.isAnalysisBoard) {
            const analysisTabs = document.querySelector<HTMLElement>('.analysis-tabs');
            const pgnContainer = document.querySelector<HTMLElement>('.pgn-container');
            if (analysisTabs) analysisTabs.style.display = 'none';
            if (pgnContainer) pgnContainer.style.display = 'block';
        }

        if (this.analysisExtension?.socket) {
            this.sock = this.analysisExtension.socket;
        } else if (this.analysisExtension?.socketTarget) {
            this.sock = createWebsocket(
                this.analysisExtension.socketTarget,
                () => this.analysisExtension?.onSocketOpen?.(),
                () => this.analysisExtension?.onSocketReconnect?.(),
                () => this.analysisExtension?.onSocketClose?.(),
                (e: MessageEvent) => this.onMessage(e),
            );
        } else if (this.analysisContext.capabilities.usesRoundSocket) {
            this.sock = createWebsocket(
                'wsr/' + this.gameId,
                onOpen,
                () => {},
                () => {},
                (e: MessageEvent) => this.onMessage(e),
            );
        }

        // Every analysis page already includes its board/history. Render it even
        // when the round socket is delayed or unavailable; chat and server analysis
        // can connect independently of move navigation and local analysis.
        if (typeof model.board !== 'string') {
            this.onMsgBoard(model.board);
            this.analysisExtension?.onInitialBoardLoaded?.();
        }
        // Standalone analysis starts from a FEN without a board/history payload.
        // It still needs a tree so new moves can branch from earlier positions.
        if (this.analysisContext.mode === 'standalone' && !this.hasAnalysisTree()) {
            this.initAnalysisTreeAtPly(this.ply);
            updateMovelist(this, true, false);
        }

        setTimeout(() => {
            const container = document.getElementById('movelist');
            if (!this.destroyed && container && this.hasAnalysisTree()) updateMovelist(this, true, false);
        }, 0);

        analysisSettings.ctrl = this;

        Mousetrap.bind('p', () =>
            copyTextToClipboard(`${this.fullfen};variant ${this.variant.name};site ${model.home}/${this.gameId}\n`),
        );

        const gaugeEl = document.getElementById('gauge');
        if (this.variant.name !== 'racingkings' && this.mycolor === 'black') gaugeEl?.classList.add('flipped');

        this.autoShapes = [];
    }

    override destroy(): void {
        this.cancelAnalysisSession();
        this.analysisExtension?.onDestroy?.();
        this.engineStop();
        this.destroyed = true;
        this.restoreFsfPrompt();
        window.removeEventListener('storage', this.onAntiCheatStorage);
        window.removeEventListener('beforeunload', this.onEngineBoardUnload);
        document.removeEventListener('keydown', this.onKeyboardHelpShortcutKeyDown, true);
        document.removeEventListener('keydown', this.onKeyboardHelpKeyDown, true);
        this.fsfEngineBoard?.delete();
        this.fsfEngineBoard = undefined;
        this.pvHoverPreview.destroy();
        this.tree.destroy();
        Mousetrap.unbind('p');
        super.destroy();
    }

    helpDialog() {
        if (this.keyboardHelpOpen) {
            this.closeKeyboardHelp();
        } else {
            this.openKeyboardHelp();
        }
    }

    openKeyboardHelp() {
        this.keyboardHelpOpen = true;
        document.addEventListener('keydown', this.onKeyboardHelpKeyDown, true);
        showKeyboardHelp(this);
    }

    closeKeyboardHelp() {
        if (!this.keyboardHelpOpen) return;
        this.keyboardHelpOpen = false;
        document.removeEventListener('keydown', this.onKeyboardHelpKeyDown, true);
        hideKeyboardHelp();
    }

    get analysisTree() {
        return this.tree.analysisTree;
    }

    get analysisPath() {
        return this.tree.analysisPath;
    }

    get treeForkIndex() {
        return this.tree.treeForkIndex;
    }

    get treeContextMenu() {
        return this.tree.treeContextMenu;
    }

    hasAnalysisTree() {
        return this.tree.hasAnalysisTree();
    }

    isTreeInlineNotation() {
        return this.inlineNotation;
    }

    isTreeDisclosureMode() {
        return this.disclosureMode;
    }

    initAnalysisTreeAtPly(ply: number) {
        this.tree.initAnalysisTreeAtPly(ply);
    }

    getTreeActivePath() {
        return this.tree.getTreeActivePath();
    }

    getTreeCurrentNode() {
        return this.tree.getTreeCurrentNode();
    }

    getTreeNodeList() {
        return this.tree.getTreeNodeList();
    }

    getTreeMainlineEndPath() {
        return this.tree.getTreeMainlineEndPath();
    }

    getTreeLineStartPath() {
        return this.tree.getTreeLineStartPath();
    }

    getTreeLineEndPath() {
        return this.tree.getTreeLineEndPath();
    }

    getTreeParentPath() {
        return this.tree.getTreeParentPath();
    }

    getTreeMainChildPath() {
        return this.tree.getTreeMainChildPath();
    }

    getTreeNodeAtPath(path: string) {
        return this.tree.getTreeNodeAtPath(path);
    }

    pathIsTreeMainline(path: string) {
        return this.tree.pathIsTreeMainline(path);
    }

    pathIsTreeForcedVariation(path: string) {
        return this.tree.pathIsTreeForcedVariation(path);
    }

    getTreeNodeListForPath(path: string) {
        return this.tree.getTreeNodeListForPath(path);
    }

    canPromoteTreeVariation(path: string) {
        return this.tree.canPromoteTreeVariation(path);
    }

    someTreeCollapsed(collapsed: boolean) {
        return this.tree.someTreeCollapsed(collapsed);
    }

    getTreeSelectedChildPath() {
        return this.tree.getTreeSelectedChildPath();
    }

    getTreeContextMenu() {
        return this.tree.getTreeContextMenu();
    }

    openTreeContextMenu(path: string, clientX: number, clientY: number) {
        this.tree.openTreeContextMenu(path, clientX, clientY);
    }

    closeTreeContextMenu() {
        this.tree.closeTreeContextMenu();
    }

    copyTreeLinePgn(path: string) {
        this.tree.copyTreeLinePgn(path);
    }

    collapseAllTree() {
        this.tree.collapseAllTree();
    }

    expandAllTree() {
        this.tree.expandAllTree();
    }

    promoteTreeVariation(path: string, toMainline: boolean) {
        this.tree.promoteTreeVariation(path, toMainline);
    }

    forceTreeVariation(path: string, force: boolean) {
        this.tree.forceTreeVariation(path, force);
    }

    deleteTreeNode(path: string) {
        this.tree.deleteTreeNode(path);
    }

    getTreePreviousBranchPath() {
        return this.tree.getTreePreviousBranchPath();
    }

    getTreeNextBranchPath() {
        return this.tree.getTreeNextBranchPath();
    }

    getTreeStepLinePath(which: 'prev' | 'next') {
        return this.tree.getTreeStepLinePath(which);
    }

    selectTreeFork(which: 'prev' | 'next') {
        return this.tree.selectTreeFork(which);
    }

    toggleTreeCollapsed(path: string) {
        this.tree.toggleTreeCollapsed(path);
    }

    activateTreePly(ply: number) {
        this.tree.activateTreePly(ply);
    }

    activateTreeMainlinePly(ply: number) {
        this.tree.activateTreeMainlinePly(ply);
    }

    private getTreeNodeForPly(ply: number) {
        return this.tree.getTreeNodeForPly(ply);
    }

    activateTreePath(path: string, redrawMovelist = true, origin: AnalysisNavigationOrigin = 'user-navigation') {
        this.tree.activateTreePath(path, redrawMovelist, origin);
    }

    beginAnalysisSession(): number {
        this.cancelAnalysisSession();
        return this.analysisSessionGeneration;
    }

    isAnalysisSessionCurrent(generation: number): boolean {
        return !this.destroyed && generation === this.analysisSessionGeneration;
    }

    addAnalysisSessionCleanup(generation: number, cleanup: () => void): () => void {
        if (!this.isAnalysisSessionCurrent(generation)) {
            cleanup();
            return () => {};
        }
        this.analysisSessionCleanups.add(cleanup);
        return () => this.analysisSessionCleanups.delete(cleanup);
    }

    cancelAnalysisSession(): void {
        this.analysisSessionGeneration += 1;
        const cleanups = [...this.analysisSessionCleanups];
        this.analysisSessionCleanups.clear();
        cleanups.forEach(cleanup => cleanup());
    }

    completeAnalysisPositionChange(
        origin: AnalysisNavigationOrigin,
        previousPath: string,
        path = this.analysisPath ?? '',
    ): void {
        const boardInput = this.analysisExtension?.boardInput?.({
            path,
            ply: this.ply,
            turnColor: this.turnColor,
        });
        if (boardInput !== undefined) {
            this.chessground.set({ movable: { color: boardInput === false ? undefined : boardInput } });
        }
        this.analysisExtension?.onPositionChanged?.({
            origin,
            path,
            previousPath,
            ply: this.ply,
            fen: this.fullfen,
            node: this.analysisTree ? this.getTreeNodeAtPath(path) : undefined,
        });
    }

    shouldDisplayAnalysisEvaluation(evaluation: AnalysisEvaluationDelivery): boolean {
        return this.analysisExtension?.onEvaluation?.(evaluation) !== false;
    }

    toggleSettings() {
        const menuEl = document.getElementById('bars') as HTMLElement;
        const settingsEl = document.querySelector('div.analysis-settings') as HTMLElement;
        const toolsEl = document.querySelector('div.analysis-tools') as HTMLElement;
        if (settingsEl.style.display === 'flex') {
            toolsEl.style.display = 'flex';
            settingsEl.style.display = 'none';
            menuEl.classList.toggle('active', false);
            menuEl.setAttribute('aria-expanded', 'false');
        } else {
            toolsEl.style.display = 'none';
            settingsEl.style.display = 'flex';
            menuEl.classList.toggle('active', true);
            menuEl.setAttribute('aria-expanded', 'true');
        }
    }

    isLocalAnalysisBlockedByAntiCheat(): boolean {
        return this.analysisContext.capabilities.localAnalysisAllowed && hasActiveEligibleLiveGame();
    }

    isLocalAnalysisAllowedByExtension(): boolean {
        return this.analysisExtension?.allowComputerSearch?.() !== false;
    }

    refreshLocalAnalysisAvailabilityForAntiCheat() {
        const blocked = this.isLocalAnalysisBlockedByAntiCheat();
        const extensionAllowed = this.isLocalAnalysisAllowedByExtension();
        if (blocked) this.disableLocalAnalysisForAntiCheat();
        else if (!extensionAllowed) this.suspendLocalAnalysisForExtension();

        const engineToggle = document.getElementById('engine-enabled') as HTMLInputElement | null;
        if (engineToggle !== null) {
            engineToggle.disabled =
                !this.analysisContext.capabilities.localAnalysisAllowed ||
                blocked ||
                !extensionAllowed ||
                !this.localEngine ||
                !this.isEngineReady ||
                !this.variantSupportedByFSF;
        }
        this.analysisExtension?.onComputerSearchAvailabilityChanged?.();
    }

    nnueIni(data?: Uint8Array) {
        if (!this.evalFile || !this.localEngine || !window.fsf) {
            this.nnueOk = false;
            return;
        }
        this.nnueOk = false;
        this.refreshNnueIndicator();
        void this.loadNnueIntoEngine(this.evalFile, data).catch(error =>
            console.error('Failed to load NNUE file:', error),
        );
    }

    nnueClear() {
        const restartAnalysis = this.localAnalysis && this.isEngineReady;
        if (restartAnalysis) this.engineStop();

        if (this.loadedNnueFilename && window.fsf) {
            try {
                window.fsf.FS.unlink('/' + this.loadedNnueFilename);
            } catch {
                // The in-memory file may already have been removed.
            }
        }

        this.loadedNnueFilename = undefined;
        this.nnueOk = false;
        this.refreshNnueIndicator();
        if (restartAnalysis) this.engineGo();
    }

    refreshNnueIndicator() {
        const nnueEl = document.querySelector('.nnue') as HTMLElement | null;
        if (!nnueEl) return;

        const active = this.nnue && this.nnueOk && this.evalFile !== '';
        const title = active
            ? _('Multi-threaded WebAssembly (with NNUE evaluation)')
            : _('Multi-threaded WebAssembly (classical evaluation)');
        patch(nnueEl, h('span.nnue', { props: { title: title } }, active ? 'NNUE' : 'HCE'));
    }

    private async loadNnueIntoEngine(filename: string, data?: Uint8Array): Promise<void> {
        const network = officialNnueNetwork(this.variant.name, nnueLookupContextForVariant(this.variant));
        const obsolete = await removeObsoleteOfficialNnue(this.variant.name, network);
        if (this.destroyed) return;
        if (obsolete === filename) {
            localStorage[`${this.variant.name}-nnue`] = '';
            this.evalFile = '';
            this.nnueOk = false;
            this.refreshNnueIndicator();
            return;
        }

        const nnueData =
            data ??
            (network?.file === filename
                ? await loadOfficialNnueFile(this.variant.name, network)
                : await loadNnueFile(this.variant.name, filename));
        if (this.destroyed) return;
        if (!nnueData) {
            this.nnueOk = false;
            this.refreshNnueIndicator();
            return;
        }

        const restartAnalysis = this.localAnalysis && this.isEngineReady;
        if (restartAnalysis) this.engineStop();

        if (this.loadedNnueFilename && this.loadedNnueFilename !== filename) {
            try {
                window.fsf.FS.unlink('/' + this.loadedNnueFilename);
            } catch {
                // The old in-memory file may already have been removed.
            }
        }

        const fsFilename = '/' + filename;
        window.fsf.FS.writeFile(fsFilename, nnueData);
        console.log('Loaded to fsf.FS:', fsFilename);
        this.loadedNnueFilename = filename;
        this.nnueOk = true;

        this.refreshNnueIndicator();

        if (restartAnalysis) this.engineGo();
    }

    pvboxIni() {
        if (this.localAnalysis) this.engineStop();
        this.pvHoverPreview.hide();
        this.clearPvlines();
        if (this.localAnalysis) this.engineGo();
    }

    pvView(i: number, pv: VNode | undefined) {
        if (i >= 0) {
            if (this.vpvlines === undefined) this.pvboxIni();
            this.vpvlines[i] = patch(
                this.vpvlines[i],
                h(
                    `div#pv${i + 1}.pv`,
                    {
                        on: {
                            mouseleave: () => this.pvHoverPreview.scheduleHide(),
                        },
                    },
                    pv,
                ),
            );
        }
    }

    clearPvlines() {
        this.pvHoverPreview.hide();
        for (let i = 4; i >= 0; i--) {
            if (i + 1 <= this.multipv && this.localAnalysis) {
                this.vpvlines[i] = patch(this.vpvlines[i], h(`div#pv${i + 1}.pv`, [h('pvline', h('pvline', '-'))]));
            } else {
                this.vpvlines[i] = patch(this.vpvlines[i], h(`div#pv${i + 1}`));
            }
        }
    }

    toggleOrientation() {
        super.toggleOrientation();
        this.pvHoverPreview.onOrientationChange();
        boardSettings.updateDropSuggestion();
        document.getElementById('gauge')?.classList.toggle('flipped');
        const clocktimes = this.steps[1]?.clocks;
        if (clocktimes !== undefined) {
            renderClocks(this);
        }
        if (this.hasPockets) {
            setPocketRowCssVars(this);
        }
        this.analysisExtension?.onOrientationChanged?.();
    }

    private drawAnalysisChart = (withRequest: boolean) => {
        const element = document.getElementById('request-analysis') as HTMLElement;
        if (element !== null) element.style.display = 'none';

        if (withRequest) {
            if (this.anon) {
                void alertDialog({ text: _('You need an account to do that.') });
                return;
            }
            // Server-side analysis is a fishnet capability and is deliberately
            // independent from the browser/WASM engine below. The server decides
            // whether an active worker can analyze this particular variant.
            this.doSend({ type: 'analysis', username: this.username, gameId: this.gameId });
            const loaderEl = document.getElementById('loader') as HTMLElement;
            loaderEl.style.display = 'block';
        }
        const chartEl = document.getElementById('chart-analysis') as HTMLElement;
        chartEl.style.display = 'block';
        analysisChart(this);
    };

    checkStatus(msg: MsgBoard | MsgAnalysisBoard) {
        if ((msg.gameId !== this.gameId && !this.isAnalysisBoard) || this.embed) return;
        if (('status' in msg && msg.status >= 0) || this.isAnalysisBoard) {
            // Save finished game full pgn sent by server
            if ('pgn' in msg && msg.pgn !== undefined) this.pgn = msg.pgn;
            // but on analysis page we always present pgn move list leading to current shown position!
            const pgn = this.isAnalysisBoard ? this.getPgn() : this.pgn;

            if ('uci_usi' in msg) {
                this.uci_usi = msg.uci_usi;
            }

            this.renderFENAndPGN(pgn);

            if (!this.isAnalysisBoard) selectMove(this, this.ply);
        }
    }

    private renderFENAndPGN(pgn: string) {
        if (!this.analysisContext.capabilities.positionMetadata) return;

        let container = document.getElementById('copyfen') as HTMLElement | null;
        if (container !== null) {
            const buttons = [
                h(
                    'a.i-pgn',
                    {
                        attrs: { href: '#' },
                        on: {
                            click: (e: Event) => {
                                e.preventDefault();
                                downloadPgnText('pychess-variants_' + this.gameId);
                            },
                        },
                    },
                    [
                        h(
                            'i',
                            {
                                props: { title: _('Download game to PGN file') },
                                class: { icon: true, 'icon-download': true },
                            },
                            _('Download PGN'),
                        ),
                    ],
                ),
                h(
                    'a.i-pgn',
                    {
                        attrs: { href: '#' },
                        on: {
                            click: (e: Event) => {
                                e.preventDefault();
                                copyTextToClipboard(this.uci_usi);
                            },
                        },
                    },
                    [
                        h(
                            'i',
                            {
                                props: { title: _('Copy USI/UCI to clipboard') },
                                class: { icon: true, 'icon-clipboard': true },
                            },
                            _('Copy UCI/USI'),
                        ),
                    ],
                ),
                h(
                    'a.i-pgn',
                    {
                        attrs: { href: '#' },
                        on: {
                            click: (e: Event) => {
                                e.preventDefault();
                                copyBoardToPNG(this.fullfen);
                            },
                        },
                    },
                    [
                        h(
                            'i',
                            {
                                props: { title: _('Download position to PNG image file') },
                                class: { icon: true, 'icon-download': true },
                            },
                            _('PNG image'),
                        ),
                    ],
                ),
                h('div#imported'),
            ];
            patch(container, h('div.pgnbuttons', buttons));
        }

        const e = document.getElementById('fullfen') as HTMLInputElement | null;
        if (e !== null) e.value = this.fullfen;

        container = document.getElementById('pgntext');
        if (container !== null) this.vpgn = patch(container, h('div#pgntext', pgn));
    }

    private async deleteGame() {
        const confirmed = await confirmDialog({
            text: _('Are you sure you want to delete this game?'),
            confirmText: _('Delete game'),
            cancelText: _('Cancel'),
            danger: true,
        });
        if (!confirmed) return;
        this.doSend({ type: 'delete', gameId: this.gameId });
    }

    onMsgBoard(msg: MsgBoard) {
        if (msg.gameId !== this.gameId) return;

        if (this.analysisContext.capabilities.usesRoundSocket) {
            // The socket repeats the page's snapshot on connect/reconnect. Do not
            // rebuild the tree and discard local variations for an unchanged board.
            const snapshot = JSON.stringify(msg);
            if (snapshot === this.lastRoundBoardSnapshot) return;
            this.lastRoundBoardSnapshot = snapshot;
        }

        msg = materializeGameHistory(msg, this.ffish, this.notationAsObject);

        this.importedBy = msg.by;
        // Enable to delete imported games
        if (this.rated === '2' && this.importedBy === this.username) {
            const importedEl = document.getElementById('imported') as HTMLElement;
            patch(
                importedEl,
                h(
                    'a.i-pgn',
                    {
                        attrs: { href: '#' },
                        on: {
                            click: (e: Event) => {
                                e.preventDefault();
                                this.deleteGame();
                            },
                        },
                    },
                    [
                        h(
                            'i',
                            { props: { title: _('Delete game') }, class: { icon: true, 'icon-trash-o': true } },
                            _('Delete game'),
                        ),
                    ],
                ),
            );
        }

        // console.log("got board msg:", msg);
        this.fullfen = msg.fen;
        this.turnColor = getTurnColor(msg.fen); // turnColor have to be actualized before setDests() !!!

        this.setDests();

        this.result = msg.result;
        this.status = msg.status;

        if (msg.steps.length > 1) {
            this.steps = [];
            msg.steps.forEach(step => {
                if (step.analysis !== undefined) {
                    step.ceval = step.analysis;
                    const scoreStr = this.buildScoreStr(step.turnColor === 'white' ? 'w' : 'b', step.analysis);
                    step.scoreStr = scoreStr;
                }
                this.steps.push(step);
            });
            this.recordedMainlinePly = msg.steps.length - 1;
            this.initAnalysisTreeAtPly(Math.min(this.ply, this.steps.length - 1));
            updateMovelist(this, true, false);

            if (this.steps[0].analysis === undefined) {
                if (this.analysisContext.capabilities.serverAnalysisRequest) {
                    const el = document.getElementById('request-analysis') as HTMLElement;
                    el.style.display = 'flex';
                    patch(
                        el,
                        h('div#request-analysis', [
                            h(
                                'button.request-analysis.button-primary',
                                { on: { click: () => this.drawAnalysisChart(true) } },
                                [
                                    h(
                                        'i',
                                        {
                                            props: { title: _('Request Computer Analysis') },
                                            class: { icon: true, 'icon-bar-chart': true },
                                        },
                                        _('Request Analysis'),
                                    ),
                                ],
                            ),
                        ]),
                    );
                }
            } else {
                this.vinfo = patch(this.vinfo, h('info#info', '-'));
                this.drawAnalysisChart(false);
            }
            const clocktimes = this.steps[1]?.clocks;
            if (clocktimes !== undefined && this.analysisContext.capabilities.moveTimeChart) {
                patch(document.getElementById('anal-clock-top') as HTMLElement, h('div.anal-clock.top'));
                patch(document.getElementById('anal-clock-bottom') as HTMLElement, h('div.anal-clock.bottom'));
                renderClocks(this);

                const cmt = document.getElementById('chart-movetime') as HTMLElement;
                cmt.style.display = 'block';
                movetimeChart(this);
            }
        } else {
            if (msg.ply === this.steps.length) {
                const step: Step = {
                    fen: msg.fen,
                    move: msg.lastMove,
                    check: msg.check,
                    turnColor: this.turnColor,
                    san: msg.steps[0].san,
                };
                this.steps.push(step);
                updateMovelist(this);
            }
        }

        if (!this.hasAnalysisTree() && this.steps.length >= 1) {
            this.initAnalysisTreeAtPly(Math.min(this.ply, this.steps.length - 1));
            updateMovelist(this, true, false);
        }

        const lastMove = uci2LastMove(msg.lastMove);
        const step = this.steps[this.steps.length - 1];
        let capture = false;
        if (lastMove) {
            const piece = this.chessground.state.boardState.pieces.get(lastMove[1] as cg.Key);
            capture =
                (piece !== undefined && piece.role !== '_-piece' && step.san?.slice(0, 2) !== 'O-') ||
                step.san?.slice(1, 2) === 'x';
        }
        if (msg.steps.length === 1 && lastMove && (this.turnColor === this.mycolor || this.spectator)) {
            sound.moveSound(this.variant, capture);
        }
        this.checkStatus(msg);

        if (this.ply > 0) {
            if (this.hasAnalysisTree()) this.activateTreePath(this.analysisPath, false, 'reset');
            else selectMove(this, this.ply);
        }
    }

    onFSFline = (line: string) => {
        if (this.destroyed) return;
        if (this.fsfDebug) console.debug('--->', line);

        if (this.analysisExtension?.onEngineLine?.(line)) return;
        if (this.ongoing) return;

        if (line.startsWith('info')) {
            const error = 'info string ERROR: ';
            if (line.startsWith(error)) {
                this.fsfError.push(line.slice(error.length));
                if (line.includes('terminated')) {
                    const suggestion = _('Try browser page reload.');
                    this.fsfError.push('');
                    this.fsfError.push(suggestion);
                    const errorMsg = this.fsfError.join('\n');
                    void alertDialog({ text: errorMsg });
                    return;
                }
            }
        }

        if (line.startsWith('option name UCI_Variant')) {
            if (!line.includes(this.engineVariant)) {
                console.log('This variant is NOT supported by Fairy-Stockfish!');
                return;
            } else {
                this.variantSupportedByFSF = true;
            }
        }

        if (line.includes('uciok')) {
            this.uciOk = true;
            this.restoreFsfPrompt();
            this.resolveEngineConfig?.();
            this.resolveEngineConfig = undefined;
            this.engineConfigReady = undefined;
        }

        if (line.includes('readyok')) {
            this.isEngineReady = true;
            if (this.awaitingStopReadyok) {
                this.awaitingStopReadyok = false;
                if (this.pendingGoAfterStopReadyok && this.localAnalysis) {
                    this.pendingGoAfterStopReadyok = false;
                    this.engineGo();
                }
            }
        }

        if (line.startsWith('Fairy-Stockfish')) {
            this.loadVariantsIntoFsfEngine();
        }

        if (!this.localEngine && this.uciOk && this.variantSupportedByFSF) {
            this.localEngine = true;
            this.fsfEngineBoard = new this.ffish.Board(this.engineVariant, this.fullfen, this.chess960);
            this.fsfPostMessage('isready');

            if (this.evalFile) this.nnueIni();

            window.addEventListener('beforeunload', this.onEngineBoardUnload);

            if (this.localAnalysis) this.pvboxIni();
        }

        this.refreshLocalAnalysisAvailabilityForAntiCheat();

        if (!this.localAnalysis || !this.isEngineReady || this.awaitingStopReadyok) return;

        const matches = line.match(EVAL_REGEX);
        if (!matches) {
            if (line.includes('mate 0')) this.clearPvlines();
            return;
        }

        const depth = parseInt(matches[1]),
            multiPv = parseInt(matches[2]),
            isMate = matches[3] === 'mate',
            povEv = parseInt(matches[4]),
            evalType = matches[5],
            nodes = parseInt(matches[6]),
            elapsedMs: number = parseInt(matches[7]),
            moves = matches[8];
        //console.log("---", depth, multiPv, isMate, povEv, evalType, nodes, elapsedMs, moves);

        // A stopped search can still emit trailing info lines from the previous
        // position. Ignore PVs whose first move is illegal in the currently shown FEN.
        if (!this.pvStartsLegalInCurrentPosition(moves)) return;

        // Sometimes we get #0. Let's just skip it.
        if (isMate && !povEv) return;

        // For now, ignore most upperbound/lowerbound messages.
        // The exception is for multiPV, sometimes non-primary PVs
        // only have an upperbound.
        // See: https://github.com/ddugovic/Stockfish/issues/228
        if (evalType && multiPv === 1) return;

        let score;
        if (isMate) {
            score = { mate: povEv };
        } else {
            score = { cp: povEv };
        }
        const knps = nodes / elapsedMs;
        if (this.lastBroadcastLocalAnalysisFen !== this.fullfen) {
            publishCevalPosition(buildCevalPositionPayload(this.variant.name, this.chess960, this.fullfen));
            this.lastBroadcastLocalAnalysisFen = this.fullfen;
        }
        const msg: MsgAnalysis = {
            type: 'local-analysis',
            ply: this.ply,
            color: this.turnColor.slice(0, 1),
            ceval: { d: depth, multipv: multiPv, p: moves, s: score, k: knps },
        };
        this.onMsgAnalysis(msg);
    };

    onMoreDepth = () => {
        this.maxDepth = 99;
        this.engineStop();
        this.engineGo();
    };

    makePvMove(pv_line: string) {
        const move = pv_line.split(' ')[0];
        this.doSendMove(move);
    }

    shapeFromMove(pv_idx: number, pv_move: string, turnColor: cg.Color) {
        const atPos = pv_move.indexOf('@');
        // drop
        if (atPos > -1) {
            const d = pv_move.slice(atPos + 1, atPos + 3) as cg.Key;
            const dropPieceRole = util.roleOf(pv_move.slice(0, atPos) as cg.Letter);

            this.autoShapes[pv_idx] = [
                {
                    orig: d,
                    brush: 'paleGreen',
                    piece: {
                        color: turnColor,
                        role: dropPieceRole,
                    },
                },
                { orig: d, brush: 'paleGreen' },
            ];
        } else {
            // arrow
            const o = pv_move.slice(0, 2) as cg.Key;
            const d = pv_move.slice(2, 4) as cg.Key;
            this.autoShapes[pv_idx] = [
                { orig: o, dest: d, brush: 'paleGreen', piece: undefined, modifiers: { lineWidth: 14 - pv_idx * 2.5 } },
            ];

            // duck / Amazons arrow blocker
            if ((this.variant.rules.duck || this.variant.rules.arrowing) && pv_move.includes(',')) {
                this.autoShapes[pv_idx].push({
                    orig: pv_move.slice(-2) as cg.Key,
                    brush: 'paleGreen',
                    piece: {
                        color: turnColor,
                        role: '_-piece',
                    },
                });
            }

            // TODO: gating, promotion
        }
        const shapes = this.autoShapes.flat();
        this.chessground.setAutoShapes(shapes);
    }

    private drawEvalScoreAndGauge = (ceval: Ceval | undefined, scoreStr: string | undefined, turnColor: cg.Color) => {
        const gaugeEl = document.getElementById('gauge') as HTMLElement | null;
        if (gaugeEl) {
            const fillEl = gaugeEl.querySelector('div.fill') as HTMLElement | null;
            if (fillEl && ceval !== undefined) {
                const score = ceval.s;
                if (score !== undefined) {
                    const ev = povChances(turnColor, score);
                    fillEl.style.height = String(100 - (ev + 1) * 50) + '%';
                } else {
                    fillEl.style.height = '50%';
                }
            }
        }

        this.vscore = patch(this.vscore, h('score#score', ceval === undefined ? '' : scoreStr));
    };

    /**
     * Study computer-practice owns the shared browser engine with bounded searches.
     * Surface its current-position score in the normal engine header and gauge
     * without rendering the PV/arrow, which would reveal the practice answer.
     */
    drawPracticeEval = (ceval: Ceval, turnColor: cg.Color) => {
        const scoreStr = this.buildScoreStr(turnColor === 'black' ? 'b' : 'w', ceval);
        this.drawEvalScoreAndGauge(ceval, scoreStr, turnColor);
    };

    // Updates PV, score, gauge and the best move arrow
    drawEval = (ceval: Ceval | undefined, scoreStr: string | undefined, turnColor: cg.Color) => {
        const pvlineIdx = ceval && ceval.multipv ? ceval.multipv - 1 : 0;
        // Render PV line
        if (ceval?.p !== undefined && this.multipv > 0) {
            let pvSan: string | VNode | VNode[] = ceval.p;
            // Prefer the controller's live board state for PV SAN conversion.
            // In post-puzzle analysis it stays aligned with client-created moves,
            // while the separate engine helper board can lag behind that state.
            const sanBoard = this.ffishBoard ?? this.fsfEngineBoard;
            if (sanBoard) {
                try {
                    // `fsfEngineBoard` is initialized asynchronously after local-engine handshake.
                    // On initial page load, server-side analysis can arrive before that happens.
                    // Falling back to `ffishBoard` avoids showing raw UCI coordinates until user
                    // clicks a move and triggers another redraw.
                    if (this.localAnalysis && !this.variant.twoBoards) {
                        const rendered = this.pvHoverPreview.renderPvSanLine({
                            pvLine: ceval.p,
                            sanBoard,
                            fullfen: this.fullfen,
                            notationAsObject: this.notationAsObject,
                            getOrientation: () => this.chessground.state.orientation,
                        });
                        if (rendered.length > 0) {
                            pvSan = rendered;
                        } else {
                            sanBoard.setFen(this.fullfen);
                            pvSan = sanBoard.variationSan(ceval.p, this.notationAsObject);
                        }
                    } else {
                        sanBoard.setFen(this.fullfen);
                        pvSan = sanBoard.variationSan(ceval.p, this.notationAsObject);
                    }
                    if (typeof pvSan === 'string' && pvSan === '') pvSan = emptySan;
                } catch {
                    pvSan = emptySan;
                }
            }
            if (pvSan !== emptySan) {
                pvSan = h('pv-san', { on: { click: () => this.makePvMove(ceval.p as string) } }, pvSan);
                this.pvView(
                    pvlineIdx,
                    h('pvline', [this.multipv > 1 && this.localAnalysis ? h('strong', scoreStr) : '', pvSan]),
                );
            }
        } else if (ceval === undefined) {
            this.pvView(pvlineIdx, h('pvline', this.localAnalysis ? h('pvline', '-') : ''));
        }

        // Render gauge and main score value for first PV line only
        if (pvlineIdx === 0) {
            this.drawEvalScoreAndGauge(ceval, scoreStr, turnColor);

            if (ceval?.d !== undefined) {
                const info = [h('span', _('Depth') + ' ' + String(ceval.d) + '/' + this.maxDepth)];
                if (ceval.k) {
                    if (ceval.d === this.maxDepth && this.maxDepth !== 99) {
                        info.push(
                            h('a.icon.icon-plus-square', {
                                attrs: { href: '#', 'aria-label': _('Go deeper') },
                                props: { title: _('Go deeper') },
                                on: {
                                    click: (e: Event) => {
                                        e.preventDefault();
                                        this.onMoreDepth();
                                    },
                                },
                            }),
                        );
                    } else if (ceval.d !== 99) {
                        info.push(h('span', ', ' + Math.round(ceval.k) + ' knodes/s'));
                    }
                }
                this.vinfo = patch(this.vinfo, h('info#info', ''));
                this.vinfo = patch(this.vinfo, h('info#info', info));
            } else {
                this.vinfo = patch(this.vinfo, h('info#info', _('in local browser')));
            }
        }

        if (ceval?.p !== undefined) {
            // console.log("ARROW", this.arrow);
            if (this.arrow) {
                const pv_move = uci2cg(ceval.p.split(' ')[0]);
                this.shapeFromMove(pvlineIdx, pv_move, turnColor);
            }
        }
    };

    // Updates chart and score in movelist
    drawServerEval = (ply: number, scoreStr?: string) => {
        if (ply > 0) {
            const evalEl = document.getElementById('ply' + String(ply)) as HTMLElement;
            if (evalEl) patch(evalEl, h('eval#ply' + String(ply), scoreStr));
        }

        if (this.analysisContext.capabilities.evalCharts) {
            analysisChart(this);
            const hc = this.analysisChart;
            if (hc !== undefined) {
                const hcPt = hc.series[0].data[ply];
                if (hcPt !== undefined) hcPt.select();
            }
        }
    };

    /** True when extension-owned bounded searches may safely take over the shared engine. */
    isPracticeEngineIdle(): boolean {
        return !this.awaitingStopReadyok && !this.pendingGoAfterStopReadyok;
    }

    engineStop = () => {
        // Keep the toggle enabled, but still synchronize restart sequencing.
        // We wait for the matching `readyok` before sending the next `position/go`
        // so stale PV output from the previous position does not flood the UI.
        this.awaitingStopReadyok = true;
        this.pendingGoAfterStopReadyok = false;
        this.fsfPostMessage('stop');
        this.fsfPostMessage('isready');
    };

    engineGo = () => {
        if (!this.variantSupportedByFSF) return;
        if (this.awaitingStopReadyok) {
            this.pendingGoAfterStopReadyok = true;
            return;
        }
        this.pendingGoAfterStopReadyok = false;
        this.lastBroadcastLocalAnalysisFen = undefined;

        // A Study keeps the engine alive while switching chapters and variants.
        this.fsfPostMessage('setoption name UCI_Variant value ' + this.engineVariant);
        this.fsfPostMessage('setoption name UCI_Chess960 value ' + this.chess960);
        if (this.evalFile === '' || !this.nnueOk || !this.nnue) {
            this.fsfPostMessage('setoption name Use NNUE value false');
        } else {
            this.fsfPostMessage('setoption name Use NNUE value true');
            this.fsfPostMessage('setoption name EvalFile value ' + this.evalFile);
        }

        this.fsfPostMessage('setoption name Hash value ' + this.hash);

        this.fsfPostMessage('setoption name Threads value ' + this.threads);

        this.fsfPostMessage('setoption name MultiPV value ' + this.multipv);

        let position: string = 'position fen ' + this.fullfen;
        if (this.UCImovelist.length > 0) {
            position = 'position fen ' + this.steps[0].fen + ' moves ' + this.UCImovelist.join(' ');
        }
        this.fsfPostMessage(position);

        if (this.maxDepth >= 99) {
            this.fsfPostMessage('go depth 99');
        } else {
            this.fsfPostMessage('go movetime 90000 depth ' + this.maxDepth);
        }
    };

    fsfPostMessage(msg: string, debug = true) {
        if (this.destroyed) return;
        if (window.fsf === undefined) {
            // At very first time we may have to wait for fsf module to initialize
            setTimeout(this.fsfPostMessage.bind(this), 100, msg, debug);
        } else {
            if (debug && this.fsfDebug) console.debug('<---', msg);
            window.fsf.postMessage(msg);
        }
    }

    loadVariantsIntoFsfEngine() {
        if (this.destroyed || this.engineConfigReady) return;
        this.engineConfigReady = new Promise(resolve => {
            this.resolveEngineConfig = resolve;
        });
        const config = variantConfigIni(variantsIni, this.variant.name);
        const marker = 'PYCHESS_VARIANTS_INI_EOF_' + Date.now();
        const lines = config.replace(/\r\n/g, '\n').split('\n');

        // The current fairy-stockfish.wasm shell falls back to window.prompt()
        // when C++ reads stdin. A here-doc `load <<MARKER` therefore needs a
        // prompt shim that returns one config line per read. Posting those lines
        // with postMessage does not satisfy this stdin path and the browser shows
        // the default "Input:" prompt instead.
        this.installFsfPromptQueue([...lines, marker]);
        if (this.fsfDebug) console.debug('<---', '... variants.ini content queued for prompt stdin ...');
        this.fsfPostMessage('load <<' + marker);
        this.fsfPostMessage('uci');
    }

    async whenEngineConfigured(): Promise<void> {
        if (!this.engineConfigReady) return;
        let timer: ReturnType<typeof setTimeout> | undefined;
        try {
            await Promise.race([
                this.engineConfigReady,
                new Promise<never>((_, reject) => {
                    timer = setTimeout(() => reject(new Error('Engine configuration is still loading.')), 10000);
                }),
            ]);
        } finally {
            clearTimeout(timer);
        }
    }

    installFsfPromptQueue(lines: string[]) {
        if (this.fsfOriginalPrompt === undefined) this.fsfOriginalPrompt = window.prompt;
        this.fsfInputQueue = lines;
        window.prompt = ((message?: string, defaultValue?: string): string => {
            const line = this.fsfInputQueue.shift();
            if (line !== undefined) return line;

            // Do not show the browser's modal prompt. Unexpected empty stdin is
            // safer than blocking the analysis page with an "Input:" dialog.
            if (this.fsfDebug) {
                console.warn('Fairy-Stockfish requested unexpected stdin input:', message, defaultValue);
            }
            return '';
        }) as typeof window.prompt;
    }

    restoreFsfPrompt() {
        if (this.fsfOriginalPrompt !== undefined) {
            window.prompt = this.fsfOriginalPrompt;
            this.fsfOriginalPrompt = undefined;
        }
        this.fsfInputQueue = [];
    }

    private pvStartsLegalInCurrentPosition(pvLine: string) {
        const firstMove = pvLine.split(' ')[0];
        if (!firstMove) return false;

        const validationBoard = this.fsfEngineBoard ?? this.ffishBoard;
        if (!validationBoard) return false;

        validationBoard.setFen(this.fullfen);
        try {
            // Using the legal move list avoids `push()` warnings in the console when
            // stale PV lines from the previous search race with the new board state.
            return validationBoard.legalMoves().split(' ').includes(firstMove);
        } catch {
            return false;
        }
    }

    private suspendLocalAnalysis(): void {
        const wasEnabled = this.localAnalysis;
        this.localAnalysis = false;
        this.lastBroadcastLocalAnalysisFen = undefined;
        if (wasEnabled) {
            this.engineStop();
            if (this.vpvlines !== undefined) this.clearPvlines();
        }

        const engineToggle = document.getElementById('engine-enabled') as HTMLInputElement | null;
        if (engineToggle !== null) engineToggle.checked = false;
    }

    suspendLocalAnalysisForExtension(): void {
        this.suspendLocalAnalysis();
    }

    disableLocalAnalysisForAntiCheat() {
        localStorage.localAnalysis = 'false';
        this.suspendLocalAnalysis();
    }

    private onAntiCheatStorage = (event: StorageEvent) => {
        if (event.storageArea !== localStorage) return;
        if (event.key === CEVAL_DISABLE_STORAGE_KEY) {
            this.disableLocalAnalysisForAntiCheat();
        } else if (event.key !== CEVAL_ACTIVE_ROUNDS_STORAGE_KEY) {
            return;
        }

        this.refreshLocalAnalysisAvailabilityForAntiCheat();
    };

    goPly(ply: number, plyVari = 0) {
        if (this.hasAnalysisTree() && plyVari === 0) {
            // Tree mode reads the active node directly instead of projecting a side line into `steps`.
            // We resolve the selected tree node first, then hydrate the existing board,
            // clocks, eval and PGN widgets from that node's step payload.
            const node = this.getTreeNodeForPly(ply);
            if (!node) return;

            const step = node.step;
            const lastMove = uci2LastMove(step.move);
            let capture = false;
            if (lastMove) {
                const piece = this.chessground.state.boardState.pieces.get(lastMove[1] as cg.Key);
                capture =
                    (piece !== undefined && piece.role !== '_-piece' && step.san?.slice(0, 2) !== 'O-') ||
                    step.san?.slice(1, 2) === 'x';
            }

            const fen = this.mirrorBoard ? this.getAliceFen(step.fen) : step.fen;
            this.chessground.set({
                fen: this.fog ? fogFen(fen) : fen,
                turnColor: step.turnColor,
                movable: {
                    color: step.turnColor,
                },
                check: this.fog ? false : step.check,
                lastMove: this.fog ? undefined : lastMove,
            });
            animatePassMove(this.chessground, this.variant.rules.pass && !this.fog, lastMove);
            this.updateBoardSummary(step.san);

            this.turnColor = step.turnColor;
            this.setDests();
            this.fullfen = step.fen;
            this.suffix = '';
            this.duck.cancel();
            this.arrowing.cancel();

            if (this.variant.ui.counting) {
                [this.vmiscInfoW, this.vmiscInfoB] = updateCount(
                    step.fen,
                    document.getElementById('misc-infow') as HTMLElement,
                    document.getElementById('misc-infob') as HTMLElement,
                );
            }

            if (this.variant.ui.materialPoint) {
                [this.vmiscInfoW, this.vmiscInfoB] = updatePoint(
                    this.variant,
                    step.fen,
                    document.getElementById('misc-infow') as HTMLElement,
                    document.getElementById('misc-infob') as HTMLElement,
                );
            }

            if (ply === this.ply + 1) {
                sound.moveSound(this.variant, capture);
                if (step.check) sound.check();
            }
            this.ply = ply;
            this.plyVari = 0;

            if (this.localAnalysis) {
                this.engineStop();
                this.clearPvlines();
            }

            if (this.embed) return;

            const clocktimes = this.steps[1]?.clocks;
            if (clocktimes !== undefined) {
                renderClocks(this);
                const hc = this.movetimeChart;
                if (hc !== undefined && node.mainlinePly !== undefined) {
                    const idx = step.turnColor === 'white' ? 1 : 0;
                    const turn = (node.mainlinePly + 1) >> 1;
                    const hcPt = hc.series[idx].data[turn - 1];
                    if (hcPt !== undefined) hcPt.select();
                }
            }
            if (this.ffishBoard) {
                this.ffishBoard.setFen(this.fullfen);
                this.setDests();
            }

            if (this.analysisContext.capabilities.positionEvaluation) {
                this.autoShapes = Array.from({ length: this.multipv }, () => []);
                this.chessground.setAutoShapes([]);
                const displayEvaluation =
                    (step.ceval === undefined && step.scoreStr === undefined) ||
                    this.shouldDisplayAnalysisEvaluation({
                        source: 'stored',
                        ply,
                        fen: step.fen,
                        ceval: step.ceval,
                        scoreStr: step.scoreStr,
                    });
                if (displayEvaluation) {
                    this.drawEval(step.ceval, step.scoreStr, step.turnColor);
                    if (node.mainlinePly !== undefined) this.drawServerEval(node.mainlinePly, step.scoreStr);
                }
            }

            this.updateUCImoves();
            if (this.localAnalysis) this.engineGo();

            if (this.analysisContext.capabilities.positionMetadata) {
                const e = document.getElementById('fullfen') as HTMLInputElement;
                e.value = this.fullfen;

                if (this.isAnalysisBoard) {
                    this.vpgn = patch(this.vpgn, h('div#pgntext', this.getPgn()));
                } else {
                    const histPly = node.mainlinePly ?? ply;
                    const hist = this.home + '/' + this.gameId + '?ply=' + histPly.toString();
                    window.history.replaceState({}, '', hist);
                }
            }

            return;
        }

        super.goPly(ply, 0);

        if (this.localAnalysis) {
            this.engineStop();
            this.clearPvlines();
        }

        if (this.embed) return;

        const step = this.steps[ply];

        const clocktimes = this.steps[1]?.clocks;
        if (clocktimes !== undefined) {
            renderClocks(this);
            const hc = this.movetimeChart;
            if (hc !== undefined) {
                const idx = step.turnColor === 'white' ? 1 : 0;
                const turn = (ply + 1) >> 1;
                const hcPt = hc.series[idx].data[turn - 1];
                if (hcPt !== undefined) hcPt.select();
            }
        }
        if (this.ffishBoard) {
            this.ffishBoard.setFen(this.fullfen);
            this.setDests();
        }

        if (this.analysisContext.capabilities.positionEvaluation) {
            this.autoShapes = Array.from({ length: this.multipv }, () => []);
            this.chessground.setAutoShapes([]);
            const displayEvaluation =
                (step.ceval === undefined && step.scoreStr === undefined) ||
                this.shouldDisplayAnalysisEvaluation({
                    source: 'stored',
                    ply,
                    fen: step.fen,
                    ceval: step.ceval,
                    scoreStr: step.scoreStr,
                });
            if (displayEvaluation) {
                this.drawEval(step.ceval, step.scoreStr, step.turnColor);
                this.drawServerEval(ply, step.scoreStr);
            }
        }

        this.updateUCImoves();
        if (this.localAnalysis) this.engineGo();

        if (this.analysisContext.capabilities.positionMetadata) {
            const e = document.getElementById('fullfen') as HTMLInputElement;
            e.value = this.fullfen;

            if (this.isAnalysisBoard) {
                this.vpgn = patch(this.vpgn, h('div#pgntext', this.getPgn()));
            } else {
                const hist = this.home + '/' + this.gameId + '?ply=' + ply.toString();
                window.history.replaceState({}, '', hist);
            }
        }
    }

    updateUCImoves() {
        this.UCImovelist = [];

        if (this.hasAnalysisTree()) {
            // In tree mode the active UCI sequence is simply the breadcrumb from root
            // to the selected node. This keeps engine analysis aligned with the branch
            // the user is currently exploring.
            const nodeList = this.getTreeNodeList();
            nodeList.slice(1).forEach(node => {
                if (node.step.move) this.UCImovelist.push(node.step.move);
            });
            return;
        }

        for (let ply = 1; ply <= this.ply; ply++) {
            if (this.steps[ply]?.move) this.UCImovelist.push(this.steps[ply].move!);
        }
    }

    refreshPgnView() {
        if (!this.analysisContext.capabilities.engineTools) return;
        const container = document.getElementById('pgntext');
        if (!container) return;
        this.vpgn = patch(this.vpgn ?? container, h('div#pgntext', this.getPgn()));
    }

    getPgn() {
        const extensionPgn = this.analysisExtension?.getPgn?.();
        if (extensionPgn !== undefined) return extensionPgn;

        const moves: string[] = [];
        let moveCounter: string = '';
        let whiteMove: boolean = true;
        let blackStarts: boolean = this.steps[0].turnColor === 'black';

        // Imported game steps has no 'sanSAN' so we have to compute it
        let sanSANneeded = false;

        if (this.steps.length > 1 && this.steps[1]['sanSAN'] == undefined) {
            sanSANneeded = true;
            const startFEN = this.steps[0].fen;
            this.ffishBoard.setFen(startFEN);
        }

        if (this.hasAnalysisTree()) {
            this.tree.ensureTreeSanSan();
        } else
            for (let ply = 1; ply <= this.ply; ply++) {
                if (blackStarts && ply === 1) {
                    moveCounter = '1...';
                } else {
                    whiteMove = this.steps[ply].turnColor === 'black';
                    moveCounter = whiteMove ? Math.ceil((ply + 1) / 2) + '.' : '';
                }
                if (sanSANneeded) {
                    this.steps[ply]['sanSAN'] = this.ffishBoard.sanMove(this.steps[ply].move!);
                    this.ffishBoard.push(this.steps[ply].move!);
                }
                moves.push(moveCounter + this.steps[ply]['sanSAN']);
            }

        if (this.hasAnalysisTree()) {
            moves.push(
                renderFullTreePgnMoveText(this.analysisTree!, node => node.step.sanSAN ?? '', renderNodeAnnotations),
            );
        }

        if (sanSANneeded || this.hasAnalysisTree()) {
            this.ffishBoard.setFen(this.fullfen);
        }

        const moveText = moves.join(' ');

        const today = new Date().toISOString().substring(0, 10).replace(/-/g, '.');

        const event = '[Event "?"]';
        const site = `[Site "${this.home}/analysis/${this.variant.name}"]`;
        const date = `[Date "${today}"]`;
        const white = '[White "?"]';
        const black = '[Black "?"]';
        const result = '[Result "*"]';
        const variant = `[Variant "${titleCase(this.variant.name)}"]`;
        const fen = `[FEN "${this.steps[0].fen}"]`;
        const setup = '[SetUp "1"]';

        return `${event}\n${site}\n${date}\n${white}\n${black}\n${result}\n${variant}\n${fen}\n${setup}\n\n${moveText} *\n`;
    }

    doSendMove(move: string) {
        this.applyAnalysisMove(move, 'played-move');
    }

    applyAnalysisMove(move: string, origin: AnalysisMoveApplication['origin'] = 'played-move'): boolean {
        const previousPath = this.analysisPath ?? '';
        if (this.analysisExtension?.beforeMoveApplied?.({ move, origin, path: previousPath }) === false) {
            if (this.hasAnalysisTree()) this.activateTreePath(previousPath, true, 'reset');
            else {
                this.goPly(this.ply, 0);
                this.completeAnalysisPositionChange('reset', previousPath, '');
            }
            return false;
        }

        const san = this.ffishBoard.sanMove(move, this.notationAsObject);
        const sanSAN = this.ffishBoard.sanMove(move);

        // Instead of sending moves to the server we can get new FEN and dests from ffishjs
        this.ffishBoard.push(move);
        const fen = this.ffishBoard.fen();
        const parts = fen.split(' ');
        // turnColor have to be actualized before setDests() !!!
        this.turnColor = parts[1] === 'w' ? 'white' : 'black';

        this.setDests();

        const newPly = this.ply + 1;

        const msg: MsgAnalysisBoard = {
            gameId: this.gameId,
            fen: this.ffishBoard.fen(this.variant.ui.showPromoted, 0),
            ply: newPly,
            lastMove: move,
            bikjang: this.ffishBoard.isBikjang(),
            check: this.ffishBoard.isCheck(),
        };

        this.onMsgAnalysisBoard(msg);

        const step = {
            fen: msg.fen,
            move: msg.lastMove,
            check: msg.check,
            turnColor: this.turnColor,
            san: san,
            sanSAN: sanSAN,
        };

        // `activateTreePath()` already refreshes board state, UCI move list and engine
        // analysis for tree mode, so we must not kick off a second `engineGo()` here.
        let treeActivated = false;
        if (this.hasAnalysisTree()) {
            const recorded = this.tree.recordMove(step);
            if (recorded) {
                if (recorded.extendedMainline) this.checkStatus(msg);
                this.tree.activateTreePath(recorded.childPath, true, origin);
                treeActivated = true;
            }
        } else {
            this.steps.push(step);
            this.ply = this.steps.length - 1;
            updateMovelist(this);
            this.checkStatus(msg);
            this.updateBoardSummary(san);
            this.completeAnalysisPositionChange(origin, previousPath, '');
        }

        if (!treeActivated) {
            this.updateUCImoves();
            if (this.localAnalysis) this.engineGo();
        }

        if (this.analysisContext.capabilities.positionMetadata) {
            const e = document.getElementById('fullfen') as HTMLInputElement;
            e.value = this.fullfen;

            if (this.isAnalysisBoard || this.result == '*') {
                this.vpgn = patch(this.vpgn, h('div#pgntext', this.getPgn()));
            }
        }

        if (this.variant.ui.materialPoint) {
            [this.vmiscInfoW, this.vmiscInfoB] = updatePoint(this.variant, msg.fen, this.vmiscInfoW, this.vmiscInfoB);
        }
        return true;
    }

    onMsgAnalysisBoard(msg: MsgAnalysisBoard) {
        // console.log("got analysis_board msg:", msg);
        if (msg.gameId !== this.gameId) return;
        if (this.localAnalysis) this.engineStop();
        if (this.analysisContext.capabilities.positionEvaluation) this.clearPvlines();

        this.fullfen = msg.fen;
        this.ply = msg.ply;

        const parts = msg.fen.split(' ');
        this.turnColor = parts[1] === 'w' ? 'white' : 'black';

        const lastMove = uci2LastMove(msg.lastMove);
        this.chessground.set({
            fen: this.fullfen,
            turnColor: this.turnColor,
            lastMove,
            check: msg.check,
            movable: {
                color: this.turnColor,
            },
        });
        animatePassMove(this.chessground, this.variant.rules.pass, lastMove);

        if (msg.check) sound.check();
    }

    buildScoreStr = (color: string, analysis: Ceval) => {
        const score = analysis['s'];
        let scoreStr = '';
        let ceval: number;
        if (score['mate'] !== undefined) {
            ceval = score['mate'];
            const sign = (color === 'b' && Number(ceval) > 0) || (color === 'w' && Number(ceval) < 0) ? '-' : '';
            scoreStr = '#' + sign + Math.abs(Number(ceval));
        } else if (score['cp'] !== undefined) {
            ceval = score['cp'];
            let nscore = Number(ceval) / 100.0;
            if (color === 'b') nscore = -nscore;
            scoreStr = nscore.toFixed(1);
        }
        return scoreStr;
    };

    private onMsgAnalysis = (msg: MsgAnalysis) => {
        if (msg['ceval']['s'] === undefined) return;

        const scoreStr = this.buildScoreStr(msg.color, msg.ceval);
        const displayEvaluation = this.shouldDisplayAnalysisEvaluation({
            source: msg.type === 'local-analysis' ? 'local' : 'server',
            ply: msg.ply,
            fen: this.fullfen,
            ceval: msg.ceval,
            scoreStr,
        });

        // Server side analysis message
        if (msg.type === 'analysis') {
            this.steps[msg.ply].analysis = msg.ceval;
            this.steps[msg.ply]['ceval'] = msg.ceval;
            this.steps[msg.ply]['scoreStr'] = scoreStr;

            if (
                this.steps.every(step => {
                    return step.scoreStr !== undefined;
                })
            ) {
                const element = document.getElementById('loader-wrapper') as HTMLElement;
                element.style.display = 'none';
            }
            if (this.analysisTree && mergeServerAdvice(this.analysisTree, Number(msg.ply), msg.ceval)) {
                updateMovelist(this, true, false);
            }
            if (msg.pgn !== undefined) {
                this.pgn = msg.pgn;
                this.renderFENAndPGN(this.pgn);
            }
            if (displayEvaluation) this.drawServerEval(msg.ply, scoreStr);
        } else if (displayEvaluation) {
            const turnColor = msg.color === 'w' ? 'white' : 'black';
            this.drawEval(msg.ceval, scoreStr, turnColor);
        }
    };

    // User running a fishnet worker asked new server side analysis with chat message: !analysis
    private onMsgRequestAnalysis = () => {
        this.steps.forEach(step => {
            step.analysis = undefined;
            step.ceval = undefined;
            step.scoreStr = undefined;
        });
        this.drawAnalysisChart(true);
    };

    private onMsgUserConnected = (msg: MsgUserConnected) => {
        this.username = msg['username'];
    };

    private onMsgDeleted = () => {
        window.location.assign(this.home + '/@/' + this.username + '/import');
    };

    protected onMessage(evt: MessageEvent) {
        // console.log("<+++ onMessage():", evt.data);
        super.onMessage(evt);

        if (evt.data === '/n') return;
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
            case 'board':
                this.onMsgBoard(msg);
                break;
            case 'analysis_board':
                this.onMsgAnalysisBoard(msg);
                break;
            case 'analysis':
                this.onMsgAnalysis(msg);
                break;
            case 'embed_user_connected':
            case 'game_user_connected':
                this.onMsgUserConnected(msg);
                break;
            case 'request_analysis':
                this.onMsgRequestAnalysis();
                break;
            case 'deleted':
                this.onMsgDeleted();
                break;
            default:
                this.analysisExtension?.onSocketMessage?.(msg.type, msg);
                break;
        }
    }
}
