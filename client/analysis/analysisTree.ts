import type { DrawShape } from 'chessgroundx/draw';

import type { Ceval, Step } from '../messages';

const ROOT_PATH = '';
const PATH_SEPARATOR = '.';

export interface AnalysisComment {
    id: string;
    author: string;
    text: string;
    /** Original PGN attribution. Kept separate from authenticated Study authorship. */
    sourceAuthor?: string;
    sourceAuthorId?: string;
}

export interface AnalysisAnnotations {
    shapes: DrawShape[];
    comments: AnalysisComment[];
    nags: number[];
}

export interface AnalysisGamebook {
    hint?: string;
    deviation?: string;
}

export interface AnalysisTreeNode {
    // Stable per-parent id segment used to build dotted paths like `01.0a.0b`.
    id: string;
    // Full path from the synthetic root to this node. This is the primary UI navigation key.
    path: string;
    // Logical ply in the explored tree, not necessarily the persisted game mainline ply.
    ply: number;
    step: Step;
    // Child[0] is always the preferred continuation for this node. Siblings are alternatives.
    children: AnalysisTreeNode[];
    collapsed?: boolean;
    forceVariation?: boolean;
    // Continuations created by saved computer advice, rather than by the player.
    serverAnalysis?: boolean;
    // Present only for nodes that still sit on the original persisted game mainline.
    mainlinePly?: number;
    // Study annotations and server-generated game analysis comments/NAGs.
    annotations?: AnalysisAnnotations;
    // Study interactive-lesson metadata. Ordinary analysis leaves this undefined.
    gamebook?: AnalysisGamebook;
    // Persisted server evaluation attached to a Study tree node. This is separate
    // from step.ceval, which can also hold transient local-engine analysis.
    eval?: Ceval;
}

export interface AnalysisTree {
    root: AnalysisTreeNode;
    // Fast random access by dotted path so UI navigation never has to re-walk the tree.
    byPath: Map<string, AnalysisTreeNode>;
    nextId: number;
    // Study trees can inject collision-resistant stable IDs while ordinary analysis
    // keeps the existing compact sequential path segments.
    nodeIdFactory?: () => string;
}

export interface TreePathProjection {
    // Paths stay on mainline until the first node with no `mainlinePly`.
    isMainline: boolean;
    // Mainline node where the current sideline branches off.
    anchorPath: string;
    anchorPly: number;
    // Ply of the currently selected node inside that projected line.
    targetPly: number;
    // Steps after the anchor, suitable for PGN/UCI generation of the active variation.
    variationSteps: Step[];
}

function joinPath(parentPath: string, id: string): string {
    return parentPath ? `${parentPath}${PATH_SEPARATOR}${id}` : id;
}

export function parentPath(path: string): string {
    const idx = path.lastIndexOf(PATH_SEPARATOR);
    if (idx < 0) return ROOT_PATH;
    return path.slice(0, idx);
}

function nextNodeId(tree: AnalysisTree): string {
    if (tree.nodeIdFactory) {
        for (let attempt = 0; attempt < 16; attempt++) {
            const id = tree.nodeIdFactory();
            if (!id || id.includes(PATH_SEPARATOR))
                throw new Error('Analysis tree node IDs must be non-empty path segments');
            const duplicate = Array.from(tree.byPath.values()).some(node => node.id === id);
            if (!duplicate) return id;
        }
        throw new Error('Analysis tree node ID factory repeatedly produced duplicate node IDs');
    }

    const id = tree.nextId.toString(36).padStart(2, '0');
    tree.nextId += 1;
    return id;
}

export function createAnalysisTree(steps: Step[], nodeIdFactory?: () => string): AnalysisTree {
    // The synthetic root owns the initial position and lets us treat root alternatives
    // exactly the same way as sub-variations deeper in the tree.
    const root: AnalysisTreeNode = {
        id: 'root',
        path: ROOT_PATH,
        ply: 0,
        step: steps[0],
        children: [],
        mainlinePly: 0,
    };

    const tree: AnalysisTree = {
        root,
        byPath: new Map([[ROOT_PATH, root]]),
        nextId: 1,
        nodeIdFactory,
    };

    let parent = root;
    for (let ply = 1; ply < steps.length; ply++) {
        const child = createChild(tree, parent, steps[ply], true, ply);
        parent.children.push(child);
        parent = child;
    }

    for (let ply = 1; ply < steps.length; ply++) {
        mergeServerAdvice(tree, ply, steps[ply].analysis);
    }
    return tree;
}

// Apply only explicitly supplied advice. Legacy eval/PV rows remain unchanged.
export function mergeServerAdvice(tree: AnalysisTree, ply: number, evaluation?: Ceval): boolean {
    const advice = evaluation?.advice;
    if (!advice) return false;
    const node = Array.from(tree.byPath.values()).find(candidate => candidate.mainlinePly === ply);
    if (!node) return false;
    const annotations = node.annotations ?? { shapes: [], comments: [], nags: [] };
    const commentId = `server-analysis-${ply}`;
    node.annotations = {
        shapes: annotations.shapes,
        comments: [
            ...annotations.comments.filter(comment => comment.id !== commentId),
            { id: commentId, author: 'PyChess', text: advice.comment },
        ],
        nags: annotations.nags.includes(advice.nag) ? annotations.nags : [...annotations.nags, advice.nag],
    };
    let path = parentPath(node.path);
    for (const step of advice.variation) {
        const sizeBefore = tree.byPath.size;
        path = addOrSelectChild(tree, path, { ...step }, false);
        if (tree.byPath.size > sizeBefore) tree.byPath.get(path)!.serverAnalysis = true;
    }
    return true;
}

export function renderNodeAnnotations(node: AnalysisTreeNode): string {
    const annotations = node.annotations;
    if (!annotations) return '';
    return [
        ...annotations.nags.map(nag => `$${nag}`),
        ...annotations.comments.map(comment => `{${comment.text.replace(/\\/g, '\\\\').replace(/}/g, '\\}')}}`),
    ].join(' ');
}

function createChild(
    tree: AnalysisTree,
    parent: AnalysisTreeNode,
    step: Step,
    asMainline: boolean,
    mainlinePly?: number,
): AnalysisTreeNode {
    const id = nextNodeId(tree);
    const path = joinPath(parent.path, id);
    const node: AnalysisTreeNode = {
        id,
        path,
        ply: parent.ply + 1,
        step,
        children: [],
        // Off-mainline nodes intentionally drop `mainlinePly`; that is how projection
        // later detects where a variation leaves the persisted game record.
        mainlinePly: asMainline ? mainlinePly : undefined,
    };
    tree.byPath.set(path, node);
    return node;
}

export function nodeAtPath(tree: AnalysisTree, path: string): AnalysisTreeNode | undefined {
    return tree.byPath.get(path);
}

export function getNodeList(tree: AnalysisTree, path: string): AnalysisTreeNode[] {
    // Returns the active breadcrumb from synthetic root to the requested node.
    const nodes: AnalysisTreeNode[] = [tree.root];
    if (!path) return nodes;

    const segments = path.split(PATH_SEPARATOR).filter(Boolean);
    let current = tree.root;
    for (const segment of segments) {
        const child = current.children.find(c => c.id === segment);
        if (!child) break;
        nodes.push(child);
        current = child;
    }

    return nodes;
}

export function mainlinePathAtPly(tree: AnalysisTree, ply: number): string {
    let current = tree.root;
    let path = ROOT_PATH;

    while (current.ply < ply && current.children[0]) {
        current = current.children[0];
        path = current.path;
    }

    return path;
}

export function mainlineEndPath(tree: AnalysisTree): string {
    return extendPath(tree, ROOT_PATH, true);
}

function pathFollowingFirstChildren(node: AnalysisTreeNode): string {
    let current = node;
    while (current.children[0]) current = current.children[0];
    return current.path;
}

export function currentLineEndPath(tree: AnalysisTree, path: string): string {
    // Mainline and sideline "end of line" mean different things:
    // for sidelines we only follow the preferred continuation from the selected node onward.
    const projection = projectPath(tree, path);
    if (projection.isMainline) return extendPath(tree, path, true);

    const node = nodeAtPath(tree, path);
    if (!node) return path;
    return pathFollowingFirstChildren(node);
}

export function projectPath(tree: AnalysisTree, path: string): TreePathProjection {
    // The UI still needs a "current line" view for buttons, PGN and engine position updates.
    // Projection maps an arbitrary tree path back to:
    // 1. the mainline anchor where the sideline begins, and
    // 2. the steps that make up the currently selected sideline.
    const nodeList = getNodeList(tree, path);
    const lastNode = nodeList[nodeList.length - 1] ?? tree.root;

    let firstOffMainlineIdx = -1;
    for (let i = 1; i < nodeList.length; i++) {
        if (nodeList[i].mainlinePly === undefined || nodeList[i].forceVariation) {
            firstOffMainlineIdx = i;
            break;
        }
    }

    if (firstOffMainlineIdx < 0) {
        return {
            isMainline: true,
            anchorPath: ROOT_PATH,
            anchorPly: 0,
            targetPly: lastNode.ply,
            variationSteps: [],
        };
    }

    const anchorIdx = firstOffMainlineIdx - 1;
    const anchorNode = nodeList[anchorIdx];
    const variationSteps = nodeList.slice(anchorIdx + 1).map(node => node.step);

    return {
        isMainline: false,
        anchorPath: anchorNode.path,
        anchorPly: anchorNode.ply,
        targetPly: lastNode.ply,
        variationSteps,
    };
}

export function branchStartPath(tree: AnalysisTree, path: string): string {
    const projection = projectPath(tree, path);
    return projection.isMainline ? ROOT_PATH : projection.anchorPath;
}

export function pathIsMainline(tree: AnalysisTree, path: string): boolean {
    return getNodeList(tree, path).every((node, idx) => idx === 0 || node.mainlinePly !== undefined);
}

export function pathIsForcedVariation(tree: AnalysisTree, path: string): boolean {
    return getNodeList(tree, path).some(node => !!node.forceVariation);
}

export function extendPath(tree: AnalysisTree, path: string, isMainline: boolean): string {
    let current = nodeAtPath(tree, path);
    while ((current = current?.children[0]) && !(isMainline && current.forceVariation)) {
        path = current.path;
    }
    return path;
}

export function stepLinePath(tree: AnalysisTree, fromPath: string, which: 'prev' | 'next'): string {
    let path = parentPath(fromPath);
    let parent = nodeAtPath(tree, path);
    let siblings = parent?.children ?? [];

    while (path && siblings.length < 2 && !pathIsMainline(tree, path)) {
        path = parentPath(path);
        parent = nodeAtPath(tree, path);
        siblings = parent?.children ?? [];
    }

    const idx = siblings.findIndex(
        child => fromPath === child.path || fromPath.startsWith(`${child.path}${PATH_SEPARATOR}`),
    );
    if (idx < 0) return fromPath;

    const target =
        which === 'next' ? (siblings[idx + 1] ?? siblings[0]) : (siblings[idx - 1] ?? siblings[siblings.length - 1]);
    return target?.path ?? fromPath;
}

export function previousBranchPath(tree: AnalysisTree, path: string): string {
    let currentPath = parentPath(path);
    let current = nodeAtPath(tree, currentPath);

    while (currentPath && current && current.children.length < 2) {
        currentPath = parentPath(currentPath);
        current = nodeAtPath(tree, currentPath);
    }

    return currentPath;
}

function exitVariationPath(tree: AnalysisTree, path: string): string {
    if (pathIsMainline(tree, path)) return path;

    let found = ROOT_PATH;
    getNodeList(tree, path)
        .slice(1, -1)
        .forEach(node => {
            if (node.children[1]) found = node.path;
        });
    return found || path;
}

export function nextBranchPath(tree: AnalysisTree, path: string, childIndex = 0): string {
    const node = nodeAtPath(tree, path);
    if (!node) return path;

    let child = node.children[childIndex] ?? node.children[0];

    while (child && child.children.length < 2) {
        child = child.children[0];
    }

    if (child) return child.path;
    if (pathIsMainline(tree, path)) return mainlineEndPath(tree);
    return exitVariationPath(tree, path);
}

export function addOrSelectChild(
    tree: AnalysisTree,
    parentPath: string,
    step: Step,
    preferMainline = false,
    mainlinePly?: number,
): string {
    const parent = nodeAtPath(tree, parentPath);
    if (!parent) return parentPath;

    // Reuse an existing child when the same move already exists from this position.
    // This keeps repeated clicks or engine lines from duplicating branches.
    const existing = parent.children.find(
        child =>
            child.step.move === step.move &&
            child.step.fen === step.fen &&
            child.step.moveB === step.moveB &&
            child.step.fenB === step.fenB,
    );
    if (existing) return existing.path;

    const child = createChild(tree, parent, step, preferMainline, mainlinePly);
    // Child[0] is treated everywhere else as the preferred continuation of a node.
    if (preferMainline) parent.children.unshift(child);
    else parent.children.push(child);

    return child.path;
}

export function canPromoteVariation(tree: AnalysisTree, path: string): boolean {
    const nodes = getNodeList(tree, path);
    for (let i = nodes.length - 2; i >= 0; i--) {
        const node = nodes[i + 1];
        const parent = nodes[i];
        if (parent.children[0]?.id !== node.id) return true;
    }
    return false;
}

export function promoteNodePath(tree: AnalysisTree, path: string, toMainline: boolean): void {
    const nodes = getNodeList(tree, path);
    for (let i = nodes.length - 2; i >= 0; i--) {
        const node = nodes[i + 1];
        const parent = nodes[i];
        if (parent.children[0]?.id !== node.id) {
            parent.children = [node, ...parent.children.filter(child => child.id !== node.id)];
            if (!toMainline) break;
        } else if (node.forceVariation) {
            node.forceVariation = false;
            if (!toMainline) break;
        }
    }
}

export function forceVariationAt(tree: AnalysisTree, path: string, force: boolean): void {
    tree.byPath.forEach(node => {
        node.forceVariation = false;
    });
    const node = nodeAtPath(tree, path);
    if (node) node.forceVariation = force;
}

function deleteBranchFromIndex(tree: AnalysisTree, nodes: AnalysisTreeNode[], idx: number): void {
    const node = nodes[idx];
    node.children.forEach(child => deleteBranchFromIndex(tree, [...nodes, child], nodes.length));
    tree.byPath.delete(node.path);
}

export function deleteNodePath(tree: AnalysisTree, path: string): void {
    if (!path) return;
    const nodes = getNodeList(tree, path);
    const node = nodes[nodes.length - 1];
    const parent = nodes[nodes.length - 2];
    if (!node || !parent) return;

    deleteBranchFromIndex(tree, nodes, nodes.length - 1);
    parent.children = parent.children.filter(child => child.id !== node.id);
}

export function someCollapsedFrom(tree: AnalysisTree, collapsed: boolean, from = ROOT_PATH): boolean {
    const start = nodeAtPath(tree, from);
    if (!start) return false;

    const visit = (node: AnalysisTreeNode): boolean => {
        if (!!node.collapsed === collapsed && node.children.length > 1) return true;
        return node.children.some(visit);
    };

    return visit(start);
}

export function setCollapsedFrom(tree: AnalysisTree, from: string, collapsed: boolean, thisBranchOnly = false): void {
    const start = nodeAtPath(tree, from);
    if (!start) return;

    const visit = (node: AnalysisTreeNode) => {
        if (node.children.length > 1) node.collapsed = collapsed;
        node.children.forEach((child, idx) => {
            if (!thisBranchOnly || idx === 0) visit(child);
        });
    };

    visit(start);
}

function movePrefix(node: AnalysisTreeNode, rootTurnColor: string, firstInVariation: boolean): string {
    const isWhiteMove = node.step.turnColor === 'black';
    if (rootTurnColor === 'black' && node.ply === 1) return '1...';
    if (isWhiteMove) return `${Math.ceil((node.ply + 1) / 2)}.`;
    if (firstInVariation) return `${Math.floor((node.ply + 1) / 2)}...`;
    return '';
}

function renderPgnSequence(
    nodes: AnalysisTreeNode[],
    rootTurnColor: string,
    firstInVariation: boolean,
    isMainline: boolean,
    getSan: (node: AnalysisTreeNode) => string,
    getSuffix?: (node: AnalysisTreeNode) => string,
): string[] {
    const [child, ...siblings] = nodes;
    if (!child) return [];

    const tokens: string[] = [];
    let current: AnalysisTreeNode | undefined = child;
    let isFirst = firstInVariation;
    let branchSiblings = siblings;

    while (current) {
        if (current.forceVariation && isMainline) {
            tokens.push(
                `(${renderPgnSequence([current, ...branchSiblings], rootTurnColor, true, false, getSan, getSuffix).join(' ')})`,
            );
            break;
        }

        const prefix = movePrefix(current, rootTurnColor, isFirst);
        const suffix = getSuffix?.(current);
        const move = prefix ? `${prefix} ${getSan(current)}` : getSan(current);
        tokens.push(suffix ? `${move} ${suffix}` : move);

        // Siblings represent alternative moves from the same parent position.
        branchSiblings.forEach(sideline => {
            tokens.push(`(${renderPgnSequence([sideline], rootTurnColor, true, false, getSan, getSuffix).join(' ')})`);
        });
        // Emit these alternatives after the move they replace, on the next
        // iteration. Emitting them here attaches them one ply too early in PGN.
        branchSiblings = current.children.slice(1);

        current = current.children[0];
        isFirst = false;
    }

    return tokens;
}

export function renderFullTreePgnMoveText(
    tree: AnalysisTree,
    getSan: (node: AnalysisTreeNode) => string,
    getSuffix?: (node: AnalysisTreeNode) => string,
): string {
    // PGN movetext is closest to the inline-notation renderer: a single token stream
    // with recursive parenthesized alternatives attached at each branch point.
    return renderPgnSequence(tree.root.children, tree.root.step.turnColor, false, true, getSan, getSuffix).join(' ');
}

function collectLineNodes(
    tree: AnalysisTree,
    path: string,
): {
    nodes: AnalysisTreeNode[];
    firstInVariation: boolean;
} {
    const projection = projectPath(tree, path);

    if (projection.isMainline) {
        const nodes: AnalysisTreeNode[] = [];
        let current = tree.root.children[0];
        while (current) {
            nodes.push(current);
            if (current.children[0]?.forceVariation) break;
            current = current.children[0];
        }
        return { nodes, firstInVariation: false };
    }

    const pathNodes = getNodeList(tree, path);
    const firstVariationIdx = pathNodes.findIndex(node => node.mainlinePly === undefined);
    const nodes = pathNodes.slice(firstVariationIdx);
    let current = nodes[nodes.length - 1];
    while (current?.children[0]) {
        current = current.children[0];
        nodes.push(current);
    }

    return { nodes, firstInVariation: true };
}

export function renderLinePgnMoveText(
    tree: AnalysisTree,
    path: string,
    getSan: (node: AnalysisTreeNode) => string,
): string {
    const { nodes, firstInVariation } = collectLineNodes(tree, path);
    return nodes
        .map((node, idx) => {
            const prefix = movePrefix(node, tree.root.step.turnColor, firstInVariation && idx === 0);
            return prefix ? `${prefix} ${getSan(node)}` : getSan(node);
        })
        .join(' ');
}
