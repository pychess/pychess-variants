import * as Mousetrap from 'mousetrap';

import { copyTextToClipboard } from '../clipboard';
import { Step } from '../messages';
import { updateMovelist } from '../movelist';
import {
    addOrSelectChild,
    AnalysisTree,
    type AnalysisTreeNode,
    branchStartPath,
    canPromoteVariation,
    createAnalysisTree,
    currentLineEndPath,
    deleteNodePath,
    extendPath,
    forceVariationAt,
    getNodeList,
    mainlineEndPath,
    mainlinePathAtPly,
    nextBranchPath,
    nodeAtPath,
    parentPath,
    pathIsForcedVariation,
    previousBranchPath,
    promoteNodePath,
    renderLinePgnMoveText,
    setCollapsedFrom,
    someCollapsedFrom,
    stepLinePath,
} from './analysisTree';
import type { AnalysisController } from './analysisCtrl';
import type { AnalysisNavigationOrigin } from './analysisExtension';

const TREE_COLLAPSED_STORAGE_KEY = 'analysisTreeCollapsedPaths';

// Owns the mutable single-board analysis-tree state and navigation behavior.
// Board/FEN/evaluation rendering remains on AnalysisController; this controller
// calls back into goPly() whenever selecting a tree node changes the active position.
export class AnalysisTreeController {
    analysisTree?: AnalysisTree;
    analysisPath: string;
    treeForkIndex: number;
    treeContextMenu?: { path: string; x: number; y: number };
    private navigationLinePath: string;
    private readonly onTreeContextMenuDocumentClick: (event: MouseEvent) => void;

    constructor(private readonly ctrl: AnalysisController) {
        this.analysisPath = '';
        this.treeForkIndex = 0;
        this.navigationLinePath = '';
        this.onTreeContextMenuDocumentClick = (event: MouseEvent) => {
            const target = event.target as HTMLElement | null;
            if (target?.closest('.tree-context-menu')) return;
            this.closeTreeContextMenu();
        };
        this.bindTreeKeys();
    }

    destroy(): void {
        document.removeEventListener('click', this.onTreeContextMenuDocumentClick, false);
        Mousetrap.unbind([
            'left',
            'right',
            'up',
            'down',
            '0',
            'home',
            '$',
            'end',
            'shift+left',
            'shift+right',
            'shift+up',
            'shift+down',
        ]);
    }

    private bindTreeKeys() {
        Mousetrap.bind('left', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreeParentPath();
            if (target !== this.analysisPath) this.activateTreePath(target);
        });
        Mousetrap.bind('right', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreeMainChildPath();
            if (target) this.activateTreePath(target);
        });
        Mousetrap.bind(['up', '0', 'home'], (event?: KeyboardEvent) => {
            if (!this.hasAnalysisTree()) return;
            if (event?.key === 'ArrowUp' && this.selectTreeFork('prev')) return;
            this.activateTreePath('');
        });
        Mousetrap.bind(['down', '$', 'end'], (event?: KeyboardEvent) => {
            if (!this.hasAnalysisTree()) return;
            if (event?.key === 'ArrowDown' && this.selectTreeFork('next')) return;
            this.activateTreePath(this.getTreeMainlineEndPath());
        });
        Mousetrap.bind('shift+left', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreePreviousBranchPath();
            if (target !== this.analysisPath) this.activateTreePath(target);
        });
        Mousetrap.bind('shift+right', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreeNextBranchPath();
            if (target !== this.analysisPath) this.activateTreePath(target);
        });
        Mousetrap.bind('shift+up', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreeStepLinePath('prev');
            if (target !== this.analysisPath) this.activateTreePath(target);
        });
        Mousetrap.bind('shift+down', () => {
            if (!this.hasAnalysisTree()) return;
            const target = this.getTreeStepLinePath('next');
            if (target !== this.analysisPath) this.activateTreePath(target);
        });
    }

    hasAnalysisTree() {
        return this.analysisTree !== undefined;
    }

    initAnalysisTreeAtPly(ply: number) {
        if (this.ctrl.steps.length === 0) return;
        this.analysisTree = createAnalysisTree(this.ctrl.steps);
        this.navigationLinePath = '';
        this.applyTreeCollapsedPaths();
        const initialPath = mainlinePathAtPly(this.analysisTree, ply);
        this.revealTreePath(initialPath);
        this.activateTreePath(initialPath, false, 'reset');
    }

    loadAnalysisTree(tree: AnalysisTree, path: string = '') {
        this.analysisTree = tree;
        this.analysisPath = '';
        this.navigationLinePath = '';
        this.treeForkIndex = 0;
        this.treeContextMenu = undefined;
        this.applyTreeCollapsedPaths();
        this.revealTreePath(path);
        this.activateTreePath(path, false, 'reset');
    }

    getTreeActivePath() {
        return this.analysisPath;
    }

    getTreeCurrentNode() {
        if (!this.analysisTree) return undefined;
        return nodeAtPath(this.analysisTree, this.analysisPath);
    }

    getTreeNodeList() {
        if (!this.analysisTree) return [];
        return getNodeList(this.analysisTree, this.analysisPath);
    }

    getTreeNodeListForPath(path: string) {
        if (!this.analysisTree) return [];
        return getNodeList(this.analysisTree, path);
    }

    getTreeMainlineEndPath() {
        if (!this.analysisTree) return '';
        return mainlineEndPath(this.analysisTree);
    }

    getTreeLineStartPath() {
        if (!this.analysisTree) return '';
        return branchStartPath(this.analysisTree, this.analysisPath);
    }

    getTreeLineEndPath() {
        if (!this.analysisTree) return '';
        return currentLineEndPath(this.analysisTree, this.analysisPath);
    }

    getTreeParentPath() {
        return parentPath(this.analysisPath);
    }

    getTreeMainChildPath() {
        const children = this.visibleChildren();
        return children[this.treeForkIndex]?.path ?? children[0]?.path;
    }

    private visibleChildren(): AnalysisTreeNode[] {
        return (
            this.getTreeCurrentNode()?.children.filter(
                child =>
                    !(this.ctrl.showServerAnalysis === false && child.serverAnalysis) &&
                    this.ctrl.analysisExtension?.isTreeNodeVisible?.(child) !== false,
            ) ?? []
        );
    }

    getTreeSelectedChildPath() {
        return this.treeForkIndex > 0 ? this.getTreeMainChildPath() : undefined;
    }

    getTreeNodeAtPath(path: string) {
        if (!this.analysisTree) return undefined;
        return nodeAtPath(this.analysisTree, path);
    }

    pathIsTreeMainline(path: string) {
        if (!this.analysisTree) return true;
        return getNodeList(this.analysisTree, path).every((node, idx) => idx === 0 || node.mainlinePly !== undefined);
    }

    pathIsTreeForcedVariation(path: string) {
        if (!this.analysisTree) return false;
        return pathIsForcedVariation(this.analysisTree, path);
    }

    canPromoteTreeVariation(path: string) {
        if (!this.analysisTree) return false;
        return canPromoteVariation(this.analysisTree, path);
    }

    someTreeCollapsed(collapsed: boolean) {
        if (!this.analysisTree) return false;
        return someCollapsedFrom(this.analysisTree, collapsed);
    }

    getTreeContextMenu() {
        return this.treeContextMenu;
    }

    openTreeContextMenu(path: string, clientX: number, clientY: number) {
        if (this.ctrl.analysisExtension?.allowTreeContextMenu?.() === false) return;
        this.treeContextMenu = { path, x: clientX, y: clientY };
        document.addEventListener('click', this.onTreeContextMenuDocumentClick, false);
        updateMovelist(this.ctrl, true, false);
    }

    closeTreeContextMenu() {
        if (!this.treeContextMenu) return;
        this.treeContextMenu = undefined;
        document.removeEventListener('click', this.onTreeContextMenuDocumentClick, false);
        updateMovelist(this.ctrl, true, false);
    }

    copyTreeLinePgn(path: string) {
        if (!this.analysisTree) return;
        this.ensureTreeSanSan();
        const onMainline = this.pathIsTreeMainline(path) && !this.pathIsTreeForcedVariation(path);
        copyTextToClipboard(
            renderLinePgnMoveText(
                this.analysisTree,
                onMainline ? extendPath(this.analysisTree, path, true) : path,
                node => node.step.sanSAN ?? '',
            ),
        );
        this.closeTreeContextMenu();
    }

    collapseAllTree() {
        if (!this.analysisTree) return;
        setCollapsedFrom(this.analysisTree, '', true);
        this.saveTreeCollapsedPaths();
        this.closeTreeContextMenu();
    }

    expandAllTree() {
        if (!this.analysisTree) return;
        setCollapsedFrom(this.analysisTree, '', false);
        this.saveTreeCollapsedPaths();
        this.closeTreeContextMenu();
    }

    promoteTreeVariation(path: string, toMainline: boolean) {
        if (!this.analysisTree) return;
        const changed = nodeAtPath(this.analysisTree, path) !== undefined;
        promoteNodePath(this.analysisTree, path, toMainline);
        if (changed) this.ctrl.analysisExtension?.onVariationPromoted?.(path, toMainline);
        if (this.ctrl.analysisExtension?.allowVariationArrows?.() !== false) this.ctrl.setAutoShapes();
        updateMovelist(this.ctrl, true, false);
        this.closeTreeContextMenu();
    }

    forceTreeVariation(path: string, force: boolean) {
        if (!this.analysisTree) return;
        const changed = nodeAtPath(this.analysisTree, path) !== undefined;
        forceVariationAt(this.analysisTree, path, force);
        this.activateTreePath(path, true, 'reset');
        if (changed) this.ctrl.analysisExtension?.onVariationForced?.(path, force);
    }

    deleteTreeNode(path: string) {
        if (!this.analysisTree || !path) return;
        const changed = nodeAtPath(this.analysisTree, path) !== undefined;
        const nextPath =
            this.analysisPath === path || this.analysisPath.startsWith(`${path}.`)
                ? parentPath(path)
                : this.analysisPath;
        deleteNodePath(this.analysisTree, path);
        this.revealTreePath(nextPath);
        this.saveTreeCollapsedPaths();
        this.activateTreePath(nextPath, true, 'reset');
        if (changed) this.ctrl.analysisExtension?.onNodeDeleted?.(path);
        this.closeTreeContextMenu();
    }

    getTreePreviousBranchPath() {
        if (!this.analysisTree) return this.analysisPath;
        return previousBranchPath(this.analysisTree, this.analysisPath);
    }

    getTreeNextBranchPath() {
        if (!this.analysisTree) return this.analysisPath;
        const node = this.getTreeCurrentNode();
        const selected = this.visibleChildren()[this.treeForkIndex];
        return nextBranchPath(this.analysisTree, this.analysisPath, selected ? node!.children.indexOf(selected) : 0);
    }

    getTreeStepLinePath(which: 'prev' | 'next') {
        if (!this.analysisTree) return this.analysisPath;
        return stepLinePath(this.analysisTree, this.analysisPath, which);
    }

    selectTreeFork(which: 'prev' | 'next') {
        const children = this.visibleChildren();
        if (children.length < 2) return false;

        const delta = which === 'next' ? 1 : -1;
        this.treeForkIndex = (children.length + this.treeForkIndex + delta) % children.length;
        if (this.ctrl.analysisExtension?.allowVariationArrows?.() !== false) this.ctrl.setAutoShapes();
        updateMovelist(this.ctrl, true, false);
        return true;
    }

    toggleTreeCollapsed(path: string) {
        if (!this.analysisTree) return;
        const node = nodeAtPath(this.analysisTree, path);
        if (!node || node.children.length < 2) return;

        node.collapsed = !node.collapsed;
        if (node.collapsed) {
            const mainChildPath = node.children[0]?.path;
            if (this.analysisPath !== path && mainChildPath && !this.analysisPath.startsWith(mainChildPath)) {
                this.activateTreePath(path, false, 'reset');
            }
        }
        this.revealTreePath(this.analysisPath);
        this.saveTreeCollapsedPaths();
        updateMovelist(this.ctrl, true, false);
    }

    activateTreePly(ply: number) {
        if (!this.analysisTree) return;
        const rememberedNode = getNodeList(this.analysisTree, this.navigationLinePath).find(node => node.ply === ply);
        this.activateTreePath(rememberedNode?.path ?? mainlinePathAtPly(this.analysisTree, ply));
    }

    activateTreeMainlinePly(ply: number) {
        if (!this.analysisTree) return;
        this.activateTreePath(mainlinePathAtPly(this.analysisTree, ply));
    }

    getTreeNodeForPly(ply: number) {
        if (!this.analysisTree) return undefined;

        const nodeOnActivePath = this.getTreeNodeList().find(node => node.ply === ply);
        if (nodeOnActivePath) return nodeOnActivePath;

        return undefined;
    }

    activateTreePath(path: string, redrawMovelist = true, origin: AnalysisNavigationOrigin = 'user-navigation') {
        if (!this.analysisTree) return;
        const node = nodeAtPath(this.analysisTree, path);
        if (!node) return;
        if (path !== this.analysisPath && this.ctrl.analysisExtension?.canActivatePath?.(path, origin) === false)
            return;

        const previousPath = this.analysisPath;
        if (
            origin !== 'user-navigation' ||
            (path !== this.navigationLinePath && !this.navigationLinePath.startsWith(path ? `${path}.` : ''))
        ) {
            this.navigationLinePath = path;
        }
        this.treeForkIndex = 0;
        this.treeContextMenu = undefined;
        document.removeEventListener('click', this.onTreeContextMenuDocumentClick, false);
        this.setAnalysisPath(path, origin);
        this.revealTreePath(path);
        this.ctrl.plyVari = 0;
        this.ctrl.goPly(node.ply, 0);
        this.ctrl.completeAnalysisPositionChange(origin, previousPath, path);

        if (redrawMovelist) updateMovelist(this.ctrl);
    }

    recordMove(step: Step): { childPath: string; extendedMainline: boolean } | undefined {
        const tree = this.analysisTree;
        if (!tree) return undefined;

        const currentNode = this.getTreeCurrentNode() ?? tree.root;
        const followMainlineMove = currentNode.children[0]?.step.move;
        const extendsMainlineTail =
            this.analysisPath === this.getTreeMainlineEndPath() &&
            currentNode.mainlinePly !== undefined &&
            currentNode.mainlinePly === this.ctrl.steps.length - 1;
        const extendedMainline = extendsMainlineTail && followMainlineMove === undefined;
        const parentPath = this.analysisPath;
        const previousChildPaths = new Set(currentNode.children.map(child => child.path));
        const childPath = addOrSelectChild(
            tree,
            parentPath,
            step,
            extendedMainline,
            extendsMainlineTail ? this.ctrl.steps.length : undefined,
        );

        // A move played by the user owns the reused variation, even if it was
        // originally introduced by server advice. Keep its existing descendants
        // and annotations, but do not hide this move with server analysis.
        const playedNode = nodeAtPath(tree, childPath);
        if (playedNode) playedNode.serverAnalysis = false;

        if (extendedMainline) {
            this.ctrl.steps.push(step);
            this.ctrl.recordedMainlinePly = this.ctrl.steps.length - 1;
        }

        if (!previousChildPaths.has(childPath)) {
            const child = nodeAtPath(tree, childPath);
            if (child) this.ctrl.analysisExtension?.onNodeAdded?.(parentPath, child);
        }

        return { childPath, extendedMainline };
    }

    ensureTreeSanSan() {
        if (!this.analysisTree) return;

        const visit = (parentFen: string, nodes: AnalysisTree['root']['children']) => {
            nodes.forEach(node => {
                if (node.step.sanSAN === undefined && node.step.move !== undefined) {
                    this.ctrl.ffishBoard.setFen(parentFen);
                    node.step.sanSAN = this.ctrl.ffishBoard.sanMove(node.step.move);
                }
                visit(node.step.fen, node.children);
            });
        };

        visit(this.ctrl.steps[0].fen, this.analysisTree.root.children);
    }

    private setAnalysisPath(path: string, origin: AnalysisNavigationOrigin) {
        const previousPath = this.analysisPath;
        this.analysisPath = path;
        if (previousPath !== path) this.ctrl.analysisExtension?.onPathChanged?.(path, previousPath, origin);
    }

    private treeCollapsedStorageKey() {
        const scope =
            this.ctrl.analysisExtension?.treeStorageKey ?? (this.ctrl.gameId || `analysis:${this.ctrl.variant.name}`);
        return `${TREE_COLLAPSED_STORAGE_KEY}:${scope}`;
    }

    private applyTreeCollapsedPaths() {
        if (!this.analysisTree) return;
        let collapsedPaths: string[] = [];
        try {
            collapsedPaths = JSON.parse(localStorage[this.treeCollapsedStorageKey()] ?? '[]');
        } catch {
            collapsedPaths = [];
        }
        collapsedPaths.forEach(path => {
            const node = nodeAtPath(this.analysisTree!, path);
            if (node) node.collapsed = true;
        });
    }

    private saveTreeCollapsedPaths() {
        if (!this.analysisTree) return;
        const collapsedPaths: string[] = [];
        const visit = (node: AnalysisTree['root']) => {
            if (node.collapsed) collapsedPaths.push(node.path);
            node.children.forEach(visit);
        };
        visit(this.analysisTree.root);
        localStorage[this.treeCollapsedStorageKey()] = JSON.stringify(collapsedPaths);
    }

    private revealTreePath(path: string) {
        if (!this.analysisTree) return;
        getNodeList(this.analysisTree, path)
            .slice(0, -1)
            .forEach(node => {
                node.collapsed = false;
            });
    }
}
