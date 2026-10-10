import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { GameController } from './gameCtrl';
import { result } from './result';
import { patch } from './document';
import { AnalysisTreeNode } from './analysis/analysisTree';
import type { AnalysisContext } from './analysis/analysisContext';
import type { AnalysisExtension } from './analysis/analysisExtension';
import { GLYPHS } from './analysis/glyphs';
import { renderLinkifiedText } from './richTextEnhance';

type TreeCtrl = GameController & {
    analysisTree?: { root: AnalysisTreeNode };
    analysisContext?: AnalysisContext;
    analysisExtension?: AnalysisExtension;
    hasAnalysisTree?: () => boolean;
    isTreeInlineNotation?: () => boolean;
    isTreeDisclosureMode?: () => boolean;
    getTreeActivePath?: () => string;
    activateTreePath?: (path: string) => void;
    activateTreePly?: (ply: number) => void;
    activateTreeMainlinePly?: (ply: number) => void;
    getTreeSelectedChildPath?: () => string | undefined;
    toggleTreeCollapsed?: (path: string) => void;
    getTreeLineStartPath?: () => string;
    getTreeLineEndPath?: () => string;
    getTreeParentPath?: () => string;
    getTreeMainChildPath?: () => string | undefined;
    getTreeNodeAtPath?: (path: string) => AnalysisTreeNode | undefined;
    getTreeContextMenu?: () => { path: string; x: number; y: number } | undefined;
    openTreeContextMenu?: (path: string, clientX: number, clientY: number) => void;
    closeTreeContextMenu?: () => void;
    copyTreeLinePgn?: (path: string) => void;
    pathIsTreeMainline?: (path: string) => boolean;
    pathIsTreeForcedVariation?: (path: string) => boolean;
    canPromoteTreeVariation?: (path: string) => boolean;
    promoteTreeVariation?: (path: string, toMainline: boolean) => void;
    forceTreeVariation?: (path: string, force: boolean) => void;
    someTreeCollapsed?: (collapsed: boolean) => boolean;
    collapseAllTree?: () => void;
    expandAllTree?: () => void;
    deleteTreeNode?: (path: string) => void;
};

type TreeDiscloseState = undefined | 'expanded' | 'collapsed';
type MoveGlyphClass = 'good' | 'mistake' | 'brilliant' | 'blunder' | 'interesting' | 'inaccuracy';
type TreeMenuIconClass =
    | 'icon-arrow-up-right'
    | 'icon-arrow-down-right'
    | 'icon-check'
    | 'icon-download'
    | 'icon-plus-square'
    | 'icon-clipboard'
    | 'icon-trash-o';

interface ParsedTreeMove {
    san: string;
    glyph?: {
        text: string;
        cls: MoveGlyphClass;
    };
}

function treeNodeVisible(ctrl: TreeCtrl, node: AnalysisTreeNode): boolean {
    return ctrl.analysisExtension?.isTreeNodeVisible?.(node) !== false;
}

function treeNodeConcealed(ctrl: TreeCtrl, node: AnalysisTreeNode): boolean {
    return ctrl.analysisExtension?.isTreeNodeConcealed?.(node) === true;
}

function treeNodeAnnotationsVisible(ctrl: TreeCtrl, node: AnalysisTreeNode): boolean {
    return ctrl.analysisExtension?.areTreeNodeAnnotationsVisible?.(node) !== false;
}

function visibleTreeChildren(ctrl: TreeCtrl, node: AnalysisTreeNode): AnalysisTreeNode[] {
    return node.children.filter(child => treeNodeVisible(ctrl, child));
}

function treeDiscloseState(node: AnalysisTreeNode): TreeDiscloseState {
    if (node.children.length < 2) return undefined;
    return node.collapsed ? 'collapsed' : 'expanded';
}

function treePathContains(outerPath: string, innerPath: string | undefined): boolean {
    if (innerPath === undefined) return false;
    return innerPath === outerPath || innerPath.startsWith(`${outerPath}.`);
}

function parseTreeMove(move: string | undefined): ParsedTreeMove {
    if (!move || move === '?') return { san: move ?? '' };

    const match = move.match(/^(.*?)(\?\?|!!|!\?|\?!|!|\?)$/);
    if (!match) return { san: move };

    const [, san, glyphText] = match;
    const glyphClass: Record<string, MoveGlyphClass> = {
        '!': 'good',
        '?': 'mistake',
        '!!': 'brilliant',
        '??': 'blunder',
        '!?': 'interesting',
        '?!': 'inaccuracy',
    };

    return {
        san,
        glyph: {
            text: glyphText,
            cls: glyphClass[glyphText],
        },
    };
}

const NAG_GLYPHS: Record<number, { text: string; cls: MoveGlyphClass }> = {
    1: { text: '!', cls: 'good' },
    2: { text: '?', cls: 'mistake' },
    3: { text: '!!', cls: 'brilliant' },
    4: { text: '??', cls: 'blunder' },
    5: { text: '!?', cls: 'interesting' },
    6: { text: '?!', cls: 'inaccuracy' },
};

function renderTreeMoveText(move: string | undefined, nags: number[] = []): VNode[] {
    const parsed = parseTreeMove(move);
    const nodes: VNode[] = [h('san', parsed.san)];

    if (parsed.glyph) {
        nodes.push(h(`glyph.${parsed.glyph.cls}`, parsed.glyph.text));
    }
    for (const nag of nags) {
        const glyph = NAG_GLYPHS[nag];
        nodes.push(
            glyph
                ? h(`glyph.${glyph.cls}`, glyph.text)
                : h('glyph', GLYPHS.find(glyph => glyph.id === nag)?.symbol ?? `$${nag}`),
        );
    }

    return nodes;
}

function asTreeCtrl(ctrl: GameController): TreeCtrl | undefined {
    const treeCtrl = ctrl as TreeCtrl;
    return treeCtrl.hasAnalysisTree?.() ? treeCtrl : undefined;
}

function clearActiveMoveHighlight() {
    document.querySelectorAll('move.active, vari-move.active').forEach(el => el.classList.remove('active'));
}

export function selectMove(ctrl: GameController, ply: number, _plyVari = 0): void {
    //console.log("selectMove()", ply);

    const treeCtrl = asTreeCtrl(ctrl);
    if (treeCtrl) {
        if (ply < 0) return;
        if (treeCtrl.analysisExtension) {
            treeCtrl.activateTreePly?.(ply);
        } else {
            // Keep ordinary analysis navigation byte-for-byte in spirit: without an
            // extension, browsing a shallower ply must not replace the selected tree line.
            ctrl.goPly(ply, 0);
            updateMovelist(ctrl, true, false);
            scrollToPly(ctrl);
        }
        return;
    }

    if (ply < 0 || ply > ctrl.steps.length - 1) {
        return;
    }

    ctrl.goPly(ply, 0);
    activatePly(ctrl);
    scrollToPly(ctrl);
}

export function selectMainlineMove(ctrl: GameController, ply: number): void {
    const treeCtrl = asTreeCtrl(ctrl);
    if (treeCtrl?.activateTreeMainlinePly) {
        treeCtrl.activateTreeMainlinePly(ply);
        return;
    }
    selectMove(ctrl, ply, 0);
}

function activatePly(ctrl: GameController) {
    //console.log('activatePly()', ctrl.ply, ctrl.plyVari);
    clearActiveMoveHighlight();

    const elPly = document.querySelector(`move[ply="${ctrl.ply}"]`);
    if (elPly) elPly.classList.add('active');
}

function movelistScrollContainer(movelist: HTMLElement): HTMLElement {
    const block = movelist.closest<HTMLElement>('.movelist-block');
    return movelist.scrollHeight > movelist.clientHeight || !block ? movelist : block;
}

function scrollToPly(ctrl: GameController) {
    const movelistEl = document.getElementById('movelist') as HTMLElement;
    const scrollEl = movelistScrollContainer(movelistEl);
    const plyEl = movelistEl.querySelector('move.active') as HTMLElement | null;

    if (ctrl.ply === 0) scrollEl.scrollTop = 0;
    else if (plyEl) {
        // Adapted from lila's treeView autoScroll: viewport rectangles also
        // handle variation moves whose offset parent is a nested tree line.
        const move = plyEl.getBoundingClientRect();
        const view = scrollEl.getBoundingClientRect();
        const visibleTop = Math.max(view.top, 0);
        const visibleHeight = Math.max(0, Math.min(view.bottom, window.innerHeight) - visibleTop);
        scrollEl.scrollTop += move.top - visibleTop - (visibleHeight - move.height) / 2;
    }
}

export function isTheoreticalMove(ply: number, status: number, recordedMainlinePly: number | undefined) {
    // In finished games, moves beyond the persisted game tail are analysis-only.
    return status >= 0 && recordedMainlinePly !== undefined && ply > recordedMainlinePly;
}

export function getFastMoveSelection(
    _plyVari: number,
    _variLength: number | undefined,
    mainLineLastPly: number,
    goToStart: boolean,
) {
    return {
        ply: goToStart ? 0 : mainLineLastPly,
        plyVari: 0,
    };
}

export function createMovelistButtons(ctrl: GameController) {
    const container = document.getElementById('move-controls') as HTMLElement;

    const selectVariationBound = (goToStart: boolean) => {
        const treeCtrl = asTreeCtrl(ctrl);
        if (treeCtrl) {
            const target = goToStart ? treeCtrl.getTreeLineStartPath?.() : treeCtrl.getTreeLineEndPath?.();
            if (target !== undefined) treeCtrl.activateTreePath?.(target);
            return;
        }
        const target = getFastMoveSelection(0, undefined, ctrl.steps.length - 1, goToStart);
        selectMove(ctrl, target.ply, target.plyVari);
    };

    // The icon font's glyph would otherwise be read as the button's name, hiding the title.
    const hidden = () => ({ attrs: { 'aria-hidden': 'true' } });

    let buttons = [
        h('button', { on: { click: () => ctrl.toggleOrientation() }, props: { title: _('Flip board') } }, [
            h('i.icon.icon-refresh', hidden()),
        ]),
        h('button', { on: { click: () => selectVariationBound(true) }, props: { title: _('First move') } }, [
            h('i.icon.icon-fast-backward', hidden()),
        ]),
        h(
            'button',
            {
                on: {
                    click: () => {
                        const treeCtrl = asTreeCtrl(ctrl);
                        if (treeCtrl) {
                            const target = treeCtrl.getTreeParentPath?.();
                            if (target !== undefined) treeCtrl.activateTreePath?.(target);
                        } else selectMove(ctrl, ctrl.ply - 1, 0);
                    },
                },
                props: { title: _('Previous move') },
            },
            [h('i.icon.icon-step-backward', hidden())],
        ),
        h(
            'button',
            {
                on: {
                    click: () => {
                        const treeCtrl = asTreeCtrl(ctrl);
                        if (treeCtrl) {
                            const target = treeCtrl.getTreeMainChildPath?.();
                            if (target !== undefined) treeCtrl.activateTreePath?.(target);
                        } else selectMove(ctrl, ctrl.ply + 1, 0);
                    },
                },
                props: { title: _('Next move') },
            },
            [h('i.icon.icon-step-forward', hidden())],
        ),
        h('button', { on: { click: () => selectVariationBound(false) }, props: { title: _('Last move') } }, [
            h('i.icon.icon-fast-forward', hidden()),
        ]),
    ];
    if (ctrl.variant.name === 'alice') {
        buttons.push(
            h('button#alice', { on: { click: () => ctrl.switchAliceBoards() }, props: { title: _('Switch boards') } }, [
                h('i.icon.icon-exchange', hidden()),
            ]),
        );
        if (ctrl.aliceSplitBoard) {
            buttons.push(
                h(
                    'button#alice-split',
                    {
                        attrs: { 'aria-pressed': String(ctrl.aliceSplitBoards) },
                        on: { click: () => ctrl.toggleAliceSplitBoards() },
                        props: {
                            title: ctrl.aliceSplitBoards ? _('Show merged board (S)') : _('Show separate boards (S)'),
                        },
                    },
                    [h('span.alice-split-icon', hidden(), '▥')],
                ),
            );
        }
    }

    if ('localEngine' in ctrl) {
        buttons.push(
            h(
                'button#bars',
                {
                    on: { click: () => ctrl.toggleSettings() },
                    props: { title: _('Menu') },
                    attrs: {
                        'aria-expanded': String(
                            document.querySelector<HTMLElement>('div.analysis-settings')?.style.display === 'flex',
                        ),
                    },
                },
                [h('i.icon.icon-bars', hidden())],
            ),
        );
    } else {
        if (ctrl.corr && ctrl.variant.name !== 'fogofwar') {
            const url = ctrl.home + '/corranalysis/' + ctrl.gameId + `?ply=${ctrl.ply + 1}`;
            buttons.push(
                h(
                    'button#corr',
                    { on: { click: () => window.location.assign(url) }, props: { title: _('Analysis board') } },
                    [h('i.icon.icon-microscope', hidden())],
                ),
            );
        }
    }

    ctrl.moveControls = patch(container, h('div#btn-controls-top.btn-controls', buttons));
}

// Like lila's treeView: comments interrupt the mainline columns, flow with
// variations, preserve authored line breaks, and safely autolink URLs.
function renderTreeComments(ctrl: TreeCtrl, node: AnalysisTreeNode): VNode[] {
    if (!treeNodeAnnotationsVisible(ctrl, node)) return [];
    return (node.annotations?.comments ?? []).map(comment =>
        h(
            'comment.tree-comment',
            {
                class: { conceal: treeNodeConcealed(ctrl, node) },
                attrs: { title: comment.sourceAuthor ? `PGN: ${comment.sourceAuthor}` : comment.author },
            },
            renderLinkifiedText(comment.text),
        ),
    );
}

function renderTreeMove(
    ctrl: TreeCtrl,
    path: string,
    node: AnalysisTreeNode,
    rootTurnColor: string,
    firstInVariation: boolean,
    isMainline: boolean,
    parentPath = '',
    parentDisclose?: TreeDiscloseState,
): VNode {
    const move =
        ctrl.fog && ctrl.status < 0 && (node.step.turnColor === ctrl.mycolor || ctrl.spectator) ? '?' : node.step.san;
    const activePath = ctrl.getTreeActivePath?.();
    const isWhiteMove = node.step.turnColor === 'black';
    let prefix = '';
    if (rootTurnColor === 'black' && node.ply === 1) {
        prefix = '1... ';
    } else if (isWhiteMove) {
        prefix = `${Math.ceil((node.ply + 1) / 2)}. `;
    } else if (firstInVariation) {
        prefix = `${Math.floor((node.ply + 1) / 2)}... `;
    }

    const scoreStr = node.step.scoreStr ?? '';
    const evalNode = node.mainlinePly !== undefined ? h(`eval#ply${node.mainlinePly}`, scoreStr) : h('eval', scoreStr);

    const recordedMainlinePly = (ctrl as GameController & { recordedMainlinePly?: number }).recordedMainlinePly;
    const theoretical =
        node.mainlinePly === undefined ||
        (node.mainlinePly !== undefined && isTheoreticalMove(node.mainlinePly, ctrl.status, recordedMainlinePly));
    const currentline = treePathContains(path, activePath);
    const recorded = node.mainlinePly !== undefined && !theoretical;
    const showDisclosureButtons = ctrl.isTreeDisclosureMode?.() ?? false;
    const disclosureButton =
        parentDisclose && showDisclosureButtons
            ? h('button.disclosure', {
                  class: { expanded: parentDisclose === 'expanded' },
                  on: {
                      click: (event: MouseEvent) => {
                          event.stopPropagation();
                          ctrl.toggleTreeCollapsed?.(parentPath);
                      },
                  },
              })
            : undefined;

    return h(
        'move',
        {
            class: {
                active: path === ctrl.getTreeActivePath?.(),
                currentline,
                selected: path === ctrl.getTreeSelectedChildPath?.(),
                recorded,
                theoretical,
                conceal: treeNodeConcealed(ctrl, node),
                branchpoint: visibleTreeChildren(ctrl, node).length > 1,
                sideline: !isMainline,
                'tree-node': true,
                mainline: isMainline,
            },
            attrs: { 'data-path': path },
            on: {
                click: () => ctrl.activateTreePath?.(path),
                contextmenu: (event: MouseEvent) => {
                    event.preventDefault();
                    event.stopPropagation();
                    ctrl.openTreeContextMenu?.(path, event.clientX, event.clientY);
                },
            },
        },
        [
            disclosureButton,
            prefix ? h('index', prefix) : undefined,
            ...renderTreeMoveText(move, treeNodeAnnotationsVisible(ctrl, node) ? node.annotations?.nags : undefined),
            evalNode,
        ],
    );
}

function renderTreeBranch(
    ctrl: TreeCtrl,
    node: AnalysisTreeNode,
    branchSiblings: AnalysisTreeNode[],
    firstInVariation: boolean,
    rootTurnColor: string,
    isMainline: boolean,
    parentPath: string,
    parentDisclose: TreeDiscloseState,
): VNode[] {
    // Inline mode is the simplest renderer: walk the preferred continuation and
    // emit each sideline as a parenthesized inline fragment at the branch point.
    const out: VNode[] = [];
    let current: AnalysisTreeNode | undefined = node;
    let isFirst = firstInVariation;
    let currentParentPath = parentPath;
    let currentParentDisclose = parentDisclose;
    let currentBranchSiblings = branchSiblings;

    while (current) {
        const currentNode: AnalysisTreeNode = current;
        if (isMainline && currentNode.forceVariation) {
            if (currentParentDisclose !== 'collapsed') {
                [currentNode, ...currentBranchSiblings].forEach(sideline => {
                    out.push(
                        h(
                            'inline',
                            renderTreeBranch(
                                ctrl,
                                sideline,
                                [],
                                true,
                                rootTurnColor,
                                false,
                                currentParentPath,
                                undefined,
                            ),
                        ),
                    );
                });
            }
            break;
        }
        out.push(
            renderTreeMove(
                ctrl,
                currentNode.path,
                currentNode,
                rootTurnColor,
                isFirst,
                isMainline,
                currentParentPath,
                currentParentDisclose,
            ),
        );
        out.push(...renderTreeComments(ctrl, currentNode));
        if (currentParentDisclose !== 'collapsed') {
            currentBranchSiblings.forEach(sideline => {
                out.push(
                    h(
                        'inline',
                        renderTreeBranch(ctrl, sideline, [], true, rootTurnColor, false, currentParentPath, undefined),
                    ),
                );
            });
        }

        currentParentPath = currentNode.path;
        const visibleChildren = visibleTreeChildren(ctrl, currentNode);
        currentParentDisclose = treeDiscloseState({ ...currentNode, children: visibleChildren });
        currentBranchSiblings = visibleChildren.slice(1);
        current = visibleChildren[0];
        isFirst = false;
    }

    return out;
}

function renderTreeMovelist(ctrl: TreeCtrl): VNode[] {
    const root = ctrl.analysisTree!.root;
    const rootTurnColor = root.step.turnColor;
    const moves: VNode[] = treeNodeVisible(ctrl, root) ? renderTreeComments(ctrl, root) : [];
    const rootChildren = visibleTreeChildren(ctrl, root);
    const mainline = rootChildren[0];
    const rootDisclose = treeDiscloseState({ ...root, children: rootChildren });
    if (mainline)
        moves.push(
            ...renderTreeBranch(ctrl, mainline, rootChildren.slice(1), false, rootTurnColor, true, '', rootDisclose),
        );
    return moves;
}

interface TreeColumnArgs {
    isMainline: boolean;
    rootTurnColor: string;
    parentNode: AnalysisTreeNode;
    parentPath: string;
    parentDisclose?: TreeDiscloseState;
    // When true, a sideline is compact enough to stay inside parentheses.
    parenthetical?: boolean;
    firstInVariation?: boolean;
    // Once a sideline row has started, deeper sub-variations should keep flowing
    // inline inside that row so wrapping behaves like wrapped text, not nested grids.
    flowInline?: boolean;
}

function hasBranching(ctrl: TreeCtrl, node: AnalysisTreeNode, depth: number): boolean {
    const children = visibleTreeChildren(ctrl, node);
    if (children.length > 1) return true;
    if (depth <= 1) return false;
    return children.some(child => hasBranching(ctrl, child, depth - 1));
}

function isParentheticalVariation(ctrl: TreeCtrl, node: AnalysisTreeNode): boolean {
    // Match the Lichess heuristic closely: only keep a variation inline when there
    // is a single secondary branch and that branch is not itself heavily branching.
    const children = visibleTreeChildren(ctrl, node);
    const second = children[1];
    const third = children[2];
    return third === undefined && second !== undefined && !hasBranching(ctrl, second, 6);
}

function nextTreeColumnArgs(
    ctrl: TreeCtrl,
    node: AnalysisTreeNode,
    args: TreeColumnArgs,
    isMainline = false,
): TreeColumnArgs {
    return {
        isMainline,
        rootTurnColor: args.rootTurnColor,
        parentNode: node,
        parentPath: node.path,
        parentDisclose: args.parentDisclose,
        parenthetical: isParentheticalVariation(ctrl, node),
        firstInVariation: false,
        flowInline: args.flowInline,
    };
}

function renderTreeColumnMove(
    ctrl: TreeCtrl,
    path: string,
    node: AnalysisTreeNode,
    isMainline: boolean,
    parentPath = '',
    parentDisclose?: TreeDiscloseState,
): VNode {
    const move =
        ctrl.fog && ctrl.status < 0 && (node.step.turnColor === ctrl.mycolor || ctrl.spectator) ? '?' : node.step.san;
    const activePath = ctrl.getTreeActivePath?.();
    const scoreStr = node.step.scoreStr ?? '';
    const evalNode = node.mainlinePly !== undefined ? h(`eval#ply${node.mainlinePly}`, scoreStr) : h('eval', scoreStr);

    const recordedMainlinePly = (ctrl as GameController & { recordedMainlinePly?: number }).recordedMainlinePly;
    const theoretical =
        node.mainlinePly === undefined ||
        (node.mainlinePly !== undefined && isTheoreticalMove(node.mainlinePly, ctrl.status, recordedMainlinePly));
    const currentline = treePathContains(path, activePath);
    const recorded = node.mainlinePly !== undefined && !theoretical;
    const showDisclosureButtons = ctrl.isTreeDisclosureMode?.() ?? false;
    const disclosureButton =
        parentDisclose && showDisclosureButtons
            ? h('button.disclosure', {
                  class: { expanded: parentDisclose === 'expanded' },
                  on: {
                      click: (event: MouseEvent) => {
                          event.stopPropagation();
                          ctrl.toggleTreeCollapsed?.(parentPath);
                      },
                  },
              })
            : undefined;

    return h(
        'move',
        {
            class: {
                active: path === ctrl.getTreeActivePath?.(),
                currentline,
                selected: path === ctrl.getTreeSelectedChildPath?.(),
                recorded,
                theoretical,
                conceal: treeNodeConcealed(ctrl, node),
                branchpoint: visibleTreeChildren(ctrl, node).length > 1,
                sideline: !isMainline,
                'tree-node': true,
                mainline: isMainline,
            },
            attrs: { 'data-path': path },
            on: {
                click: () => ctrl.activateTreePath?.(path),
                contextmenu: (event: MouseEvent) => {
                    event.preventDefault();
                    event.stopPropagation();
                    ctrl.openTreeContextMenu?.(path, event.clientX, event.clientY);
                },
            },
        },
        [
            disclosureButton,
            ...renderTreeMoveText(move, treeNodeAnnotationsVisible(ctrl, node) ? node.annotations?.nags : undefined),
            evalNode,
        ],
    );
}

function renderTreeLineSequence(ctrl: TreeCtrl, nodes: AnalysisTreeNode[], args: TreeColumnArgs): VNode[] {
    // Column mode still reuses inline fragments inside a sideline row. The split between
    // `renderTreeLineSequence` and `renderTreeVariationLines` is what lets us switch
    // between "same flowing row" and "start a new branch row" at each branching point.
    const [child, ...siblings] = nodes.filter(node => treeNodeVisible(ctrl, node));
    if (!child) return [];

    const currentParentDisclose = args.parentDisclose;
    const moves: VNode[] = [];

    moves.push(
        renderTreeMove(
            ctrl,
            child.path,
            child,
            args.rootTurnColor,
            args.firstInVariation ?? true,
            false,
            args.parentPath,
            currentParentDisclose,
        ),
    );

    moves.push(...renderTreeComments(ctrl, child));

    if (currentParentDisclose !== 'collapsed' && (args.parenthetical || args.flowInline) && siblings.length > 0) {
        moves.push(renderTreeVariationLines(ctrl, siblings, args));
    }

    if (child.children.length > 0) {
        const childArgs = {
            ...nextTreeColumnArgs(ctrl, child, args, false),
            parentDisclose: treeDiscloseState({ ...child, children: visibleTreeChildren(ctrl, child) }),
        };
        const visibleChildren = visibleTreeChildren(ctrl, child);
        if (args.flowInline || visibleChildren.length < 2 || childArgs.parenthetical) {
            moves.push(...renderTreeLineSequence(ctrl, visibleChildren, childArgs));
        } else {
            moves.push(renderTreeVariationLines(ctrl, visibleChildren, childArgs));
        }
    }

    if (currentParentDisclose !== 'collapsed' && !args.parenthetical && !args.flowInline && siblings.length > 0) {
        moves.push(renderTreeVariationLines(ctrl, siblings, args));
    }

    return moves;
}

function renderTreeVariationLines(ctrl: TreeCtrl, lines: AnalysisTreeNode[], args: TreeColumnArgs): VNode {
    lines = lines.filter(node => treeNodeVisible(ctrl, node));
    // Only direct sibling alternatives become separate rows in column mode.
    // Once inside one of those rows, deeper sub-variations continue inline so the
    // row wraps naturally at panel boundaries like a long notation string.
    if (!args.isMainline && (args.parenthetical || args.flowInline)) {
        return h(
            'inline',
            renderTreeLineSequence(ctrl, lines, {
                ...args,
                isMainline: false,
                parentDisclose: undefined,
                firstInVariation: true,
                flowInline: true,
            }),
        );
    }

    return h(
        'lines',
        lines.map(line =>
            h('line', [
                h('branch'),
                ...renderTreeLineSequence(ctrl, [line], {
                    ...args,
                    isMainline: false,
                    parentDisclose: undefined,
                    firstInVariation: true,
                    flowInline: true,
                }),
            ]),
        ),
    );
}

function renderTreeColumnNodes(ctrl: TreeCtrl, nodes: AnalysisTreeNode[], args: TreeColumnArgs): VNode[] {
    // Top-level column mode preserves the traditional "move number / white / black"
    // rhythm, but hands side branches off to `interrupt -> lines -> line` blocks.
    const [child, ...siblings] = nodes.filter(node => treeNodeVisible(ctrl, node));
    const out: VNode[] = [];
    if (!child) return out;

    const isWhiteMove = child.step.turnColor === 'black';
    const currentParentDisclose = args.parentDisclose;

    if (args.isMainline && child.forceVariation) {
        if (currentParentDisclose === 'collapsed') return out;
        return [h('interrupt', [renderTreeVariationLines(ctrl, [child, ...siblings], args)])];
    }

    if (isWhiteMove) {
        out.push(h('index', `${Math.ceil(child.ply / 2)}`));
    }

    out.push(renderTreeColumnMove(ctrl, child.path, child, args.isMainline, args.parentPath, currentParentDisclose));

    const comments = renderTreeComments(ctrl, child);
    if (currentParentDisclose !== 'collapsed' && (siblings.length > 0 || comments.length > 0)) {
        if (isWhiteMove) out.push(h('move.empty', '...'));
        out.push(
            h('interrupt', [...comments, ...(siblings.length ? [renderTreeVariationLines(ctrl, siblings, args)] : [])]),
        );
        if (isWhiteMove && visibleTreeChildren(ctrl, child).length > 0) {
            out.push(h('index', `${Math.ceil(child.ply / 2)}`));
            out.push(h('move.empty', '...'));
        }
    }

    const visibleChildren = visibleTreeChildren(ctrl, child);
    if (visibleChildren.length > 0) {
        out.push(
            ...renderTreeColumnNodes(ctrl, visibleChildren, {
                ...nextTreeColumnArgs(ctrl, child, args, true),
                parentDisclose: treeDiscloseState({ ...child, children: visibleTreeChildren(ctrl, child) }),
            }),
        );
    }

    return out;
}

function renderTreeColumnMovelist(ctrl: TreeCtrl): VNode[] {
    const root = ctrl.analysisTree!.root;
    const comments = treeNodeVisible(ctrl, root) ? renderTreeComments(ctrl, root) : [];
    const moves: VNode[] = comments.length ? [h('interrupt', comments)] : [];
    const rootChildren = visibleTreeChildren(ctrl, root);

    if (root.step.turnColor === 'black' && rootChildren[0]) {
        moves.push(h('index', '1'));
        moves.push(h('move.empty', '...'));
    }

    moves.push(
        ...renderTreeColumnNodes(ctrl, rootChildren, {
            isMainline: true,
            rootTurnColor: root.step.turnColor,
            parentNode: root,
            parentPath: '',
            parentDisclose: treeDiscloseState({ ...root, children: rootChildren }),
            firstInVariation: false,
            flowInline: false,
        }),
    );

    return moves;
}

function renderTreeContextMenu(ctrl: TreeCtrl): VNode | undefined {
    const menu = ctrl.getTreeContextMenu?.();
    if (!menu) return undefined;

    const current = ctrl.getTreeNodeAtPath?.(menu.path);
    if (!current || !treeNodeVisible(ctrl, current)) return undefined;

    const onMainline =
        (ctrl.pathIsTreeMainline?.(menu.path) ?? true) && !(ctrl.pathIsTreeForcedVariation?.(menu.path) ?? false);
    const canPromote = ctrl.canPromoteTreeVariation?.(menu.path) ?? false;
    const actions: VNode[] = [];
    const action = (iconClass: TreeMenuIconClass, text: string, onClick: () => void) =>
        h(
            'button',
            {
                on: { click: onClick },
            },
            [h(`i.icon.${iconClass}`), h('span', text)],
        );
    const positionMenu = (el: HTMLElement) => {
        const margin = 4;
        const maxLeft = Math.max(margin, window.innerWidth - el.offsetWidth - margin);
        const maxTop = Math.max(margin, window.innerHeight - el.offsetHeight - margin);

        el.style.left = `${Math.max(margin, Math.min(menu.x, maxLeft))}px`;
        el.style.top = `${Math.max(margin, Math.min(menu.y, maxTop))}px`;
    };

    if (canPromote) {
        actions.push(
            action('icon-arrow-up-right', _('Promote variation'), () => ctrl.promoteTreeVariation?.(menu.path, false)),
        );
    }

    if (!onMainline) {
        actions.push(action('icon-check', _('Make main line'), () => ctrl.promoteTreeVariation?.(menu.path, true)));
    }

    if (menu.path && onMainline) {
        actions.push(
            action('icon-arrow-down-right', _('Convert to variation'), () =>
                ctrl.forceTreeVariation?.(menu.path, true),
            ),
        );
    }

    if (ctrl.someTreeCollapsed?.(false)) {
        actions.push(action('icon-download', _('Collapse all'), () => ctrl.collapseAllTree?.()));
    }

    if (ctrl.someTreeCollapsed?.(true)) {
        actions.push(action('icon-plus-square', _('Expand all'), () => ctrl.expandAllTree?.()));
    }

    actions.push(...(ctrl.analysisExtension?.contextMenuActions?.(menu.path) ?? []));

    actions.push(
        action('icon-clipboard', onMainline ? _('Copy main line PGN') : _('Copy variation PGN'), () =>
            ctrl.copyTreeLinePgn?.(menu.path),
        ),
    );

    if (menu.path) {
        actions.push(action('icon-trash-o', _('Delete from here'), () => ctrl.deleteTreeNode?.(menu.path)));
    }

    return h(
        'div.tree-context-menu',
        {
            hook: {
                insert: vnode => positionMenu(vnode.elm as HTMLElement),
                postpatch: (_oldVnode, vnode) => positionMenu(vnode.elm as HTMLElement),
            },
            on: {
                click: (event: MouseEvent) => event.stopPropagation(),
            },
        },
        [h('div.title', current.step.san ?? _('Start position')), ...actions],
    );
}

export function updateMovelist(ctrl: GameController, full = true, activate = true, needResult = true) {
    const treeCtrl = asTreeCtrl(ctrl);
    if (treeCtrl) {
        const inlineNotation = treeCtrl.isTreeInlineNotation?.() ?? false;
        const moves = inlineNotation ? renderTreeMovelist(treeCtrl) : renderTreeColumnMovelist(treeCtrl);
        const contextMenu = renderTreeContextMenu(treeCtrl);
        if (ctrl.status >= 0 && needResult && treeCtrl.analysisContext?.capabilities.gamePanels !== false) {
            moves.push(h('div.result', ctrl.result));
            moves.push(h('div.status', result(ctrl.variant, ctrl.status, ctrl.result)));
        }
        const moveListEnd = treeCtrl.analysisExtension?.renderMoveListEnd?.() ?? [];
        moves.push(...moveListEnd);
        const footer = treeCtrl.analysisExtension?.renderMoveListFooter?.() ?? [];
        const footerContainer = document.getElementById('movelist-footer');
        if (!footerContainer) moves.push(...footer);
        if (contextMenu) moves.push(contextMenu);
        const container = document.getElementById('movelist') as HTMLElement;
        const scrollTop = movelistScrollContainer(container).scrollTop;
        if (full) {
            while (container.lastChild) {
                container.removeChild(container.lastChild);
            }
        }
        ctrl.vmovelist = patch(
            container,
            h(
                'div#movelist',
                {
                    class: {
                        tview2: true,
                        'tview2-inline': inlineNotation,
                        'tview2-column': !inlineNotation,
                        'analysis-tree': true,
                    },
                },
                moves,
            ),
        );
        if (footerContainer) {
            while (footerContainer.lastChild) {
                footerContainer.removeChild(footerContainer.lastChild);
            }
            patch(footerContainer, h('div#movelist-footer', footer));
        }
        if (activate) scrollToPly(ctrl);
        else movelistScrollContainer(ctrl.vmovelist.elm as HTMLElement).scrollTop = scrollTop;
        return;
    }

    const plyFrom = full ? 1 : ctrl.steps.length - 1;
    const plyTo = ctrl.steps.length;

    const moves: VNode[] = [];

    const blackStarts = ctrl.steps[0].turnColor === 'black';
    if (blackStarts && plyFrom === 1) {
        moves.push(h('move.counter', 1));
        moves.push(h('move', '...'));
    }

    for (let ply = plyFrom; ply < plyTo; ply++) {
        const move =
            ctrl.fog && ctrl.status < 0 && (ctrl.steps[ply].turnColor === ctrl.mycolor || ctrl.spectator)
                ? '?'
                : ctrl.steps[ply].san;
        if (move === null) continue;

        const whiteMove = ctrl.steps[ply].turnColor === 'black';
        const moveEl = [h('san', move)];
        const scoreStr = ctrl.steps[ply]['scoreStr'] ?? '';
        moveEl.push(h('eval#ply' + ply, scoreStr));

        if (whiteMove) moves.push(h('move.counter', Math.ceil((ply + 1) / 2)));

        const el = h(
            'move',
            {
                class: {
                    active: ply === plyTo - 1 && activate,
                    theoretical: isTheoreticalMove(
                        ply,
                        ctrl.status,
                        (ctrl as GameController & { recordedMainlinePly?: number }).recordedMainlinePly,
                    ),
                },
                attrs: { ply: ply },
                on: { click: () => selectMove(ctrl, ply) },
            },
            moveEl,
        );

        moves.push(el);
    }

    if (ctrl.status >= 0 && needResult) {
        moves.push(h('div.result', ctrl.result));
        moves.push(h('div.status', result(ctrl.variant, ctrl.status, ctrl.result)));
    }

    const container = document.getElementById('movelist') as HTMLElement;
    if (full) {
        while (container.lastChild) {
            container.removeChild(container.lastChild);
        }
    }
    ctrl.vmovelist = patch(container, h('div#movelist', moves));

    if (activate) {
        activatePly(ctrl);
        scrollToPly(ctrl);
    }
}

export function updateResult(ctrl: GameController) {
    if (ctrl.status < 0) return;

    // Prevent to render it twice
    const resultEl = document.querySelector('.result');
    if (resultEl) return;

    const container = document.getElementById('movelist') as HTMLElement;
    ctrl.vmovelist = patch(
        container,
        h('div#movelist', [
            h('div.result', ctrl.result),
            h('div.status', result(ctrl.variant, ctrl.status, ctrl.result)),
        ]),
    );
    container.scrollTop = 99999;
}
