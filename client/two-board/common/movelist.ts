import { h, VNode } from 'snabbdom';

import { _ } from '@/i18n';
import type AnalysisControllerBughouse from '../analysis/analysisCtrl';
import { result } from '../../result';
import { patch } from '../../document';
import { TwoBoardController } from '../twoBoardCtrl';
import { Step, StepChat } from '../../messages';
import { displayUsername, isAnonUsername } from '@/user';
import { AnalysisTreeNode, nodeAtPath, parentPath } from '../../analysis/analysisTree';
import { bugMovePrefix } from '../analysis/analysisTreeTwoBoards';
import { ariaHiddenAttr } from '../../accessibility/aria';

type TreeDiscloseState = undefined | 'expanded' | 'collapsed';
type TreeMenuIconClass =
    | 'icon-arrow-up-right'
    | 'icon-arrow-down-right'
    | 'icon-check'
    | 'icon-download'
    | 'icon-plus-square'
    | 'icon-clipboard'
    | 'icon-trash-o';
type MoveGlyphClass = 'good' | 'mistake' | 'brilliant' | 'blunder' | 'interesting' | 'inaccuracy';

interface ParsedTreeMove {
    san: string;
    glyph?: {
        text: string;
        cls: MoveGlyphClass;
    };
}

function asTreeCtrl(ctrl: TwoBoardController): AnalysisControllerBughouse | undefined {
    const treeCtrl = ctrl as AnalysisControllerBughouse;
    return treeCtrl.tree?.hasAnalysisTree() ? treeCtrl : undefined;
}

// Owns the #movelist element's retained vnode so callers never need a VNode/
// HTMLElement-typed field of their own. Constructed before the page's DOM
// exists (and before the controller does) — the placeholder it builds here is
// the same vnode object embedded by analysis.ts/round.ts, so once the page's
// top-level patch() runs, this.vnode's .elm is populated with no id lookup
// needed. Two update modes mirror the two ways the movelist is rendered: the
// analysis/tree path diffs incrementally against the last patch (preserving
// scroll position and DOM identity across tree navigation), while the round/
// legacy path always re-fetches the container fresh (round code elsewhere
// resets #movelist's DOM directly between calls, so trusting a stale retained
// vnode there would be wrong).
export class MovelistView {
    private vnode: VNode | HTMLElement;

    /* THE READER'S CURSOR: which ply is being shown.
     *
     * PRIVATE, and that is the point. This lived on `TwoBoardController` until 2026-09-07 with a
     * comment asking everyone to assign it only through `setCursor()`. A comment is not an
     * invariant: `analysisCtrl.onMsgBoard()` wrote it directly, as a scratch variable for "where
     * should the tree open", and nothing could stop it. Here the compiler stops it.
     *
     * Read it through `ply()`; move it through `showPly()` / `selectMove()`, which repaint what
     * follows from it. `setCursor()` moves it alone, for the one caller whose boards are already
     * up to date. */
    private cursor = 0;

    constructor() {
        this.vnode = h('div#movelist');
    }

    placeholder(): VNode {
        return this.vnode as VNode;
    }

    ply(): number {
        return this.cursor;
    }

    private patchVnode(newVnode: VNode): void {
        this.vnode = patch(this.vnode, newVnode);
    }

    private replaceVnode(newVnode: VNode, clearChildrenFirst = false): void {
        const container = document.getElementById('movelist') as HTMLElement;
        if (clearChildrenFirst) {
            while (container.lastChild) container.removeChild(container.lastChild);
        }
        this.vnode = patch(container, newVnode);
    }

    /** THE SELECTED PLY CHANGED — the cursor moves and the boards follow.
     *
     * Every way of navigating a game ends here: a click in the list, an arrow key, a click on a chat
     * message, a node in the analysis tree. The cursor and the "did we step forward by one" test live
     * here because they are properties of the SELECTION, not of either board; the repaint is handed
     * back to the page through `renderPly`, because a round page and an analysis page show a ply very
     * differently and only they know about engines, clocks and variations.
     *
     * SEPARATE FROM `selectMove` ON PURPOSE. This does not touch the list's own presentation. The
     * analysis tree drives its redraw itself, behind a `redrawMovelist` flag it owns, so routing it
     * through `selectMove` would redraw twice and override a decision it had deliberately made. */
    showPly(ctrl: TwoBoardController, ply: number): void {
        const steppedForward = ply === this.cursor + 1;
        this.setCursor(ply);
        ctrl.renderPly(ply, steppedForward);
    }

    /** IS THE READER FOLLOWING THE GAME, or looking at something earlier?
     *
     *  The move list's own question, answered from its own cursor and the controller's steps. Every
     *  view that must not be repainted under a reader who has scrolled away asks this: the boards when
     *  a move arrives, the scroll position, the playability of a board being rendered.
     *
     *  NOT THE SAME QUESTION AS "is this message the next ply", which is about the GAME and is answered
     *  by comparing the message against `steps.length`. The two were one expression until 2026-09-07 —
     *  the message was compared against the CURSOR, which answered both at once and neither by name —
     *  and separating them is what scenarios R2 and T8 exist to hold apart. */
    isAtEnd(ctrl: TwoBoardController): boolean {
        return this.cursor === ctrl.steps.length - 1;
    }

    /** MOVE THE CURSOR AND NOTHING ELSE.
     *
     *  Used when the boards have ALREADY been brought up to date by some other path — a move message
     *  repaints the one board that moved and splices the partner's pocket, which is a different and
     *  cheaper operation than `renderPly()`'s repaint of both boards from a step. Rendering twice for
     *  one move would be wasteful; rendering the wrong way would be wrong.
     *
     *  It exists so that the cursor is ONLY ever assigned inside this file, which is what makes "the
     *  move list owns the cursor" a fact rather than an intention. */
    setCursor(ply: number): void {
        this.cursor = ply;
    }

    selectMove(ctrl: TwoBoardController, ply: number): void {
        const treeCtrl = asTreeCtrl(ctrl);
        if (treeCtrl) {
            if (ply < 0) return;
            this.showPly(ctrl, ply);
            this.render(ctrl, true, false);
            this.scrollToPly(ctrl);
            return;
        }

        if (ply < 0 || ply > ctrl.steps.length - 1) {
            return;
        }

        this.showPly(ctrl, ply);
        this.activatePly();
        this.scrollToPly(ctrl);
    }

    selectMainlineMove(ctrl: TwoBoardController, ply: number): void {
        const treeCtrl = asTreeCtrl(ctrl);
        if (treeCtrl) {
            treeCtrl.tree.activateTreeMainlinePly(ply);
            return;
        }
        this.selectMove(ctrl, ply);
    }

    private activatePly(): void {
        const active = document.querySelector('move-bug.active');
        if (active) {
            const p = active.getAttribute('ply');
            active.classList.remove('active');
            document
                .querySelectorAll('move-bug[_ply="' + p + '"]')
                .forEach(v => v.setAttribute('style', 'display: none;'));
        }

        const elPly = document.querySelector(`move-bug[ply="${this.cursor}"]`);
        if (elPly) elPly.classList.add('active');
        document
            .querySelectorAll('move-bug[_ply="' + this.cursor + '"]')
            .forEach(v => v.setAttribute('style', 'display: block;'));
    }

    private scrollToPly(ctrl: TwoBoardController): void {
        if (ctrl.steps.length < 9) return;
        const movelistEl = document.getElementById('movelist') as HTMLElement;
        const plyEl = movelistEl.querySelector('move-bug.active, vari-move.active') as HTMLElement | null;

        let st: number | undefined = undefined;

        if (this.cursor === 0) st = 0;
        else if (this.isAtEnd(ctrl)) st = 99999;
        else if (plyEl) st = plyEl.offsetTop - movelistEl.offsetHeight / 2 + plyEl.offsetHeight / 2;

        if (st !== undefined) movelistEl.scrollTop = st;
    }

    scrollToActiveMove(): void {
        const movelistEl = document.getElementById('movelist') as HTMLElement | null;
        if (!movelistEl) return;
        const el = movelistEl.querySelector('move-bug.active, vari-move.active') as HTMLElement | null;
        if (!el) return;
        const inView =
            el.offsetTop >= movelistEl.scrollTop &&
            el.offsetTop + el.offsetHeight <= movelistEl.scrollTop + movelistEl.clientHeight;
        if (!inView) movelistEl.scrollTop = el.offsetTop - movelistEl.offsetHeight / 2 + el.offsetHeight / 2;
    }

    createButtons(ctrl: TwoBoardController): void {
        const container = document.getElementById('move-controls') as HTMLElement;

        const selectVariationBound = (goToStart: boolean) => {
            const treeCtrl = asTreeCtrl(ctrl);
            if (treeCtrl) {
                const target = goToStart ? treeCtrl.tree.getTreeLineStartPath() : treeCtrl.tree.getTreeLineEndPath();
                treeCtrl.tree.activateTreePath(target);
                return;
            }
            this.selectMove(ctrl, goToStart ? 0 : ctrl.steps.length - 1);
        };

        let buttons = [
            h(
                'button',
                {
                    on: { click: () => ctrl.flipBoards() },
                    props: { title: _('Flip boards') },
                },
                [h('i.icon.icon-refresh', ariaHiddenAttr())],
            ),
            h(
                'button',
                {
                    on: { click: () => ctrl.switchBoards() },
                    props: { title: _('Switch boards') },
                },
                [h('i.icon.icon-exchange', ariaHiddenAttr())],
            ),
            h('button', { on: { click: () => selectVariationBound(true) }, props: { title: _('First move') } }, [
                h('i.icon.icon-fast-backward', ariaHiddenAttr()),
            ]),
            h(
                'button',
                {
                    on: {
                        click: () => {
                            const treeCtrl = asTreeCtrl(ctrl);
                            if (treeCtrl) {
                                treeCtrl.tree.activateTreePath(treeCtrl.tree.getTreeParentPath());
                            } else {
                                this.selectMove(ctrl, this.cursor - 1);
                            }
                        },
                    },
                    props: { title: _('Previous move') },
                },
                [h('i.icon.icon-step-backward', ariaHiddenAttr())],
            ),
            h(
                'button',
                {
                    on: {
                        click: () => {
                            const treeCtrl = asTreeCtrl(ctrl);
                            if (treeCtrl) {
                                const target = treeCtrl.tree.getTreeMainChildPath();
                                if (target !== undefined) treeCtrl.tree.activateTreePath(target);
                            } else {
                                this.selectMove(ctrl, this.cursor + 1);
                            }
                        },
                    },
                    props: { title: _('Next move') },
                },
                [h('i.icon.icon-step-forward', ariaHiddenAttr())],
            ),
            h('button', { on: { click: () => selectVariationBound(false) }, props: { title: _('Last move') } }, [
                h('i.icon.icon-fast-forward', ariaHiddenAttr()),
            ]),
        ];
        patch(container, h('div#btn-controls-top.btn-controls', buttons));
    }

    render(ctrl: TwoBoardController, full = true, activate = true, needResult = true): void {
        const treeCtrl = asTreeCtrl(ctrl);
        if (treeCtrl) {
            const displayedMainline = treeCtrl.tree.analysisTree
                ? getDisplayedMainlineNodes(treeCtrl.tree.analysisTree)
                : [];
            const rootChildren = treeCtrl.tree.analysisTree?.root.children[0]?.forceVariation
                ? treeCtrl.tree.analysisTree.root.children
                : (treeCtrl.tree.analysisTree?.root.children.slice(1) ?? []);

            /* "IS THERE ANYTHING TO SHOW?" IS A QUESTION ABOUT THE TREE, not about `ctrl.steps`.
               `steps` is the RECORDED game's mainline, and the blank analysis board has no recorded
               game: its one seeded step is the start position and every move the reader explores is
               a tree node, never a step. Asking `steps.length <= 1` there answered "nothing to show"
               after any number of moves, so the movelist stayed empty on that page while the tree
               behind it was correct — moves played, the board advanced, and nothing was listed.

               The three tests together still say "empty" for the case this guard was written for: a
               game not yet started, whose tree has no children either. */
            if (ctrl.steps.length <= 1 && displayedMainline.length === 0 && rootChildren.length === 0) {
                this.patchVnode(h('div#movelist', { class: { 'bug-analysis-tree': true } }));
                return;
            }

            const moves: VNode[] = [];
            let lastColIdx = 0;
            let didWeRenderVariSectionAfterLastMove = false;
            let didWeRenderChatSectionAfterLastMove = false;

            if (treeCtrl.tree.analysisTree && !treeCtrl.tree.analysisTree.root.collapsed) {
                moves.push(...renderTreeVariationRows(treeCtrl, rootChildren));
            }

            for (const mainlineNode of displayedMainline) {
                const step = mainlineNode.step;
                const ply = mainlineNode.ply;
                const move = step.san;
                if (move === null) continue;

                const colIdx =
                    step.boardName === 'a' ? (step.turnColor === 'black' ? 1 : 2) : step.turnColor === 'black' ? 3 : 4;

                if (didWeRenderVariSectionAfterLastMove) {
                    fillWithEmpty(moves, colIdx - 1);
                    didWeRenderVariSectionAfterLastMove = false;
                } else {
                    const countOfEmptyCellsToAdd =
                        colIdx > lastColIdx ? colIdx - lastColIdx - 1 : 4 + colIdx - lastColIdx - 1;
                    fillWithEmpty(moves, countOfEmptyCellsToAdd);
                }

                if (didWeRenderChatSectionAfterLastMove) {
                    fillWithEmpty(moves, lastColIdx, '.ch', '' + (ply - 1), 'display: none');
                    didWeRenderChatSectionAfterLastMove = false;
                }
                lastColIdx = colIdx;

                const currentline = mainlineNode
                    ? treePathContains(mainlineNode.path, treeCtrl.tree.getTreeActivePath())
                    : false;
                const theoretical =
                    mainlineNode?.mainlinePly === undefined ||
                    (mainlineNode?.mainlinePly !== undefined &&
                        isTheoreticalMove(mainlineNode.mainlinePly, ctrl.status, treeCtrl.recordedMainlinePly));
                const recorded = !!mainlineNode && mainlineNode.mainlinePly !== undefined && !theoretical;
                const moveEl = mainlineNode ? renderTreeMoveText('', move) : [h('san', move)];
                const scoreStr = step['scoreStr'] ?? '';
                moveEl.push(h('eval#ply' + ply, scoreStr));
                let chats: VNode | undefined = undefined;
                if (step.chat) {
                    const chatMessages: VNode[] = [];
                    for (const x of step.chat) {
                        const time = formatChatMessageTime(x);
                        const m = x.message.replace('!bug!', '');
                        const displayUser = displayUsername(x.username);
                        const userNode = isAnonUsername(x.username)
                            ? h('span', displayUser)
                            : h(
                                  'a',
                                  {
                                      attrs: { href: '/@/' + x.username },
                                      class: { 'user-link': true },
                                  },
                                  displayUser,
                              );
                        chatMessages.push(
                            h('li.message', [
                                h('div.time', time),
                                h('user', userNode),
                                x.message.indexOf('!bug') > -1 ? h('div.bugchat.' + m, []) : h('div', [x.message]),
                            ]),
                        );
                    }
                    chats = h('ol.bugchatpopup.chat', chatMessages);
                    didWeRenderChatSectionAfterLastMove = true;
                }

                const branchPoint =
                    treeCtrl.tree.analysisTree && mainlineNode
                        ? (nodeAtPath(treeCtrl.tree.analysisTree, parentPath(mainlineNode.path)) ??
                          treeCtrl.tree.analysisTree.root)
                        : undefined;
                const disclosureButton =
                    branchPoint && branchPoint.children.length > 1
                        ? h('button.disclosure', {
                              class: { expanded: !branchPoint.collapsed },
                              on: {
                                  click: (event: MouseEvent) => {
                                      event.stopPropagation();
                                      treeCtrl.tree.toggleTreeCollapsed(branchPoint.path);
                                  },
                              },
                          })
                        : undefined;
                moves.push(h('move-bug.counter', getLocalMoveNum(step)));
                moves.push(
                    h(
                        'move-bug',
                        {
                            class: {
                                active: mainlineNode?.path === treeCtrl.tree.getTreeActivePath(),
                                currentline,
                                selected: mainlineNode?.path === treeCtrl.tree.getTreeSelectedChildPath(),
                                recorded,
                                theoretical,
                                branchpoint: !!mainlineNode && mainlineNode.children.length > 1,
                                haschat: !!step.chat,
                            },
                            attrs: { ply: ply },
                            on: {
                                click: () => this.selectMainlineMove(ctrl, ply),
                                contextmenu: (event: MouseEvent) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    if (mainlineNode)
                                        treeCtrl.tree.openTreeContextMenu(
                                            mainlineNode.path,
                                            event.clientX,
                                            event.clientY,
                                        );
                                },
                            },
                        },
                        disclosureButton ? [disclosureButton, ...moveEl] : moveEl,
                    ),
                );
                if (chats) moves.push(chats);

                const variationChildren = mainlineNode.children[0]?.forceVariation
                    ? mainlineNode.children
                    : mainlineNode.children.slice(1);
                if (variationChildren.length > 0 && !mainlineNode.collapsed) {
                    moves.push(...renderTreeVariationRows(treeCtrl, variationChildren));
                    didWeRenderVariSectionAfterLastMove = true;
                }

                if (mainlineNode.children[0]?.forceVariation) break;
            }

            if (ctrl.status >= 0 && needResult) {
                const teams = ctrl.seats.teams;
                const teamFirst = teams[0].name(displayUsername);
                const teamSecond = teams[1].name(displayUsername);
                moves.push(h('div.result', ctrl.result));
                moves.push(
                    h('div.status', result(ctrl.boardA.variant, ctrl.status, ctrl.result, teamFirst, teamSecond)),
                );
            }
            const contextMenu = renderTreeContextMenu(treeCtrl);
            if (contextMenu) moves.push(contextMenu);

            // diff against the retained vnode so snabbdom updates the list in place;
            // patching from a fresh element lookup would recreate the whole list and
            // reset its scroll position on every tree action
            this.patchVnode(h('div#movelist', { class: { 'bug-analysis-tree': true } }, moves));
            if (activate) this.scrollToPly(ctrl);
            return;
        }

        const plyFrom = full ? 1 : ctrl.steps.length - 1;
        if (plyFrom === 0) return; // that is the very initial message with single dummy step. No moves yet

        const plyTo = ctrl.steps.length;

        const moves: VNode[] = [];
        const prevPly = ctrl.steps[plyFrom - 1];
        let lastColIdx =
            plyFrom === 1
                ? 0
                : prevPly.boardName === 'a'
                  ? prevPly.turnColor === 'white' /*black made the move*/
                      ? 2
                      : 1
                  : prevPly.turnColor === 'white' /*black made the move*/
                    ? 4
                    : 3;
        let didWeRenderVariSectionAfterLastMove = false;
        let didWeRenderChatSectionAfterLastMove = false;

        for (let ply = plyFrom; ply < plyTo; ply++) {
            const move = ctrl.steps[ply].san;
            if (move === null) continue;

            const colIdx =
                ctrl.steps[ply].boardName === 'a'
                    ? ctrl.steps[ply].turnColor === 'black' /*meaning move was made by white and now black's turn*/
                        ? 1
                        : 2
                    : ctrl.steps[ply].turnColor === 'black'
                      ? 3
                      : 4;

            if (didWeRenderVariSectionAfterLastMove) {
                fillWithEmpty(moves, colIdx - 1);
                didWeRenderVariSectionAfterLastMove = false;
            } else {
                const countOfEmptyCellsToAdd =
                    colIdx > lastColIdx ? colIdx - lastColIdx - 1 : 4 + colIdx - lastColIdx - 1;
                fillWithEmpty(moves, countOfEmptyCellsToAdd);
            }

            if (didWeRenderChatSectionAfterLastMove) {
                // todo: this is really ugly solution for padding ply elems when chat div breaks the list
                //       and tbh the similar padding solution for variations is not best either - consider some
                //       other layout where these things can be done more natural, without all those dummy padding elements
                fillWithEmpty(moves, lastColIdx, '.ch', '' + (ply - 1), 'display: none');
                didWeRenderChatSectionAfterLastMove = false;
            }
            lastColIdx = colIdx;

            const moveEl = [h('san', move)];
            const scoreStr = ctrl.steps[ply]['scoreStr'] ?? '';
            moveEl.push(h('eval#ply' + ply, scoreStr));
            var chats: VNode | undefined = undefined;
            if (ctrl.steps[ply].chat) {
                const chatMessages: VNode[] = [];
                for (let x of ctrl.steps[ply].chat!) {
                    const time = formatChatMessageTime(x);
                    const m = x.message.replace('!bug!', '');
                    const displayUser = displayUsername(x.username);
                    const userNode = isAnonUsername(x.username)
                        ? h('span', displayUser)
                        : h(
                              'a',
                              {
                                  attrs: { href: '/@/' + x.username },
                                  class: { 'user-link': true },
                              },
                              displayUser,
                          );
                    const v = h('li.message', [
                        h('div.time', time),
                        h('user', userNode),
                        x.message.indexOf('!bug') > -1 ? h('div.bugchat.' + m, []) : h('div', [x.message]),
                    ]);

                    chatMessages.push(v /*h("div", +" "+x.username+": "+x.message)*/);
                }
                /*moveEl.push(h('bugchat#ply' + ply, [ h("img", { attrs: { src: '/static/icons/bugchatmove.svg' } })]));*/
                chats = h('ol.bugchatpopup.chat', chatMessages);
                didWeRenderChatSectionAfterLastMove = true;
            }

            moves.push(h('move-bug.counter', getLocalMoveNum(ctrl.steps[ply])));

            const el = h(
                'move-bug',
                {
                    class: {
                        active: ply === plyTo - 1 && activate,
                        haschat: !!ctrl.steps[ply].chat,
                    },
                    attrs: { ply: ply },
                    on: { click: () => this.selectMove(ctrl, ply) },
                },
                moveEl,
            );

            moves.push(el);
            if (chats) moves.push(chats);
        }

        if (ctrl.status >= 0 && needResult) {
            const teams = ctrl.seats.teams;
            const teamFirst = teams[0].name(displayUsername);
            const teamSecond = teams[1].name(displayUsername);
            moves.push(h('div.result', ctrl.result));
            moves.push(h('div.status', result(ctrl.boardA.variant, ctrl.status, ctrl.result, teamFirst, teamSecond)));
        }

        this.replaceVnode(h('div#movelist', moves), full);

        if (activate) {
            this.activatePly();
            this.scrollToPly(ctrl);
        }
    }

    renderResult(ctrl: TwoBoardController): void {
        if (ctrl.status < 0) return;

        // Prevent to render it twice
        const resultEl = document.querySelector('.result');
        if (resultEl) return;

        const teams = ctrl.seats.teams;
        const teamFirst = teams[0].name();
        const teamSecond = teams[1].name();

        this.replaceVnode(
            h('div#movelist', [
                h('div.result', ctrl.result),
                h('div.status', result(ctrl.boardA.variant, ctrl.status, ctrl.result, teamFirst, teamSecond)),
            ]),
        );
        (document.getElementById('movelist') as HTMLElement).scrollTop = 99999;
    }
}

function fillWithEmpty(
    moves: VNode[],
    countOfEmptyCellsToAdd: number,
    cls: string = '',
    ply: string = '',
    style: string = '',
) {
    for (let i = 0; i < countOfEmptyCellsToAdd; i++) {
        moves.push(h('move-bug.counter' + cls, { attrs: { _ply: ply, style: style } }));
        const el = h('move-bug' + cls, { attrs: { _ply: ply, style: style } });
        moves.push(el);
    }
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

function renderTreeMoveText(prefix: string, move: string | undefined): VNode[] {
    const parsed = parseTreeMove(move);
    const sanText = prefix ? `${prefix} ${parsed.san}` : parsed.san;
    const nodes: VNode[] = [h('san', sanText)];

    if (parsed.glyph) {
        nodes.push(h(`glyph.${parsed.glyph.cls}`, parsed.glyph.text));
    }

    return nodes;
}

function isTheoreticalMove(ply: number, status: number, recordedMainlinePly: number | undefined) {
    return status >= 0 && recordedMainlinePly !== undefined && ply > recordedMainlinePly;
}

function treeDiscloseState(node: AnalysisTreeNode): TreeDiscloseState {
    if (node.children.length < 2) return undefined;
    return node.collapsed ? 'collapsed' : 'expanded';
}

function renderTreeVariationMove(
    ctrl: AnalysisControllerBughouse,
    node: AnalysisTreeNode,
    disclosureParentPath = '',
    disclosureState?: TreeDiscloseState,
): VNode {
    const activePath = ctrl.tree.getTreeActivePath();
    const currentline = treePathContains(node.path, activePath);
    const recordedMainlinePly = ctrl.recordedMainlinePly;
    const theoretical =
        node.mainlinePly === undefined ||
        (node.mainlinePly !== undefined && isTheoreticalMove(node.mainlinePly, ctrl.status, recordedMainlinePly));
    const recorded = node.mainlinePly !== undefined && !theoretical;
    const disclosureButton = disclosureState
        ? h('button.disclosure', {
              class: { expanded: disclosureState === 'expanded' },
              on: {
                  click: (event: MouseEvent) => {
                      event.stopPropagation();
                      ctrl.tree.toggleTreeCollapsed(disclosureParentPath);
                  },
              },
          })
        : undefined;

    return h(
        'vari-move',
        {
            class: {
                active: node.path === ctrl.tree.getTreeActivePath(),
                selected: node.path === ctrl.tree.getTreeSelectedChildPath(),
                currentline,
                recorded,
                theoretical,
                branchpoint: node.children.length > 1,
            },
            attrs: { ply: node.ply, 'data-path': node.path },
            on: {
                click: () => ctrl.tree.activateTreePath(node.path),
                contextmenu: (event: MouseEvent) => {
                    event.preventDefault();
                    event.stopPropagation();
                    ctrl.tree.openTreeContextMenu(node.path, event.clientX, event.clientY);
                },
            },
        },
        [disclosureButton, ...renderTreeMoveText(bugMovePrefix(node.step), node.step.san)],
    );
}

function renderTreeVariationSequence(ctrl: AnalysisControllerBughouse, nodes: AnalysisTreeNode[]): VNode[] {
    const [child, ...siblings] = nodes;
    if (!child) return [];

    const moves: VNode[] = [];
    let current: AnalysisTreeNode | undefined = child;
    let branchSiblings = siblings;
    let currentParentPath = parentPath(child.path);
    let currentParentDisclose = ctrl.tree.analysisTree
        ? treeDiscloseState(nodeAtPath(ctrl.tree.analysisTree, currentParentPath) ?? ctrl.tree.analysisTree.root)
        : undefined;

    while (current) {
        moves.push(renderTreeVariationMove(ctrl, current, currentParentPath, currentParentDisclose));
        if (currentParentDisclose !== 'collapsed') {
            branchSiblings.forEach(sideline => {
                moves.push(h('inline', renderTreeVariationSequence(ctrl, [sideline])));
            });
        }
        branchSiblings = [];
        if (!current.collapsed) {
            current.children.slice(1).forEach(sideline => {
                moves.push(h('inline', renderTreeVariationSequence(ctrl, [sideline])));
            });
        }
        currentParentPath = current.path;
        currentParentDisclose = treeDiscloseState(current);
        current = current.children[0];
    }

    return moves;
}

function renderTreeVariationRows(ctrl: AnalysisControllerBughouse, nodes: AnalysisTreeNode[]): VNode[] {
    return nodes.map((node, idx) =>
        h(`vari#tree-vari-${idx}-${node.path.replace(/\./g, '-')}`, { class: { 'tree-variation': true } }, [
            ...renderTreeVariationSequence(ctrl, [node]),
        ]),
    );
}

function getDisplayedMainlineNodes(tree: { root: AnalysisTreeNode }): AnalysisTreeNode[] {
    const nodes: AnalysisTreeNode[] = [];
    let current = tree.root.children[0];
    while (current && !current.forceVariation) {
        nodes.push(current);
        current = current.children[0];
    }
    return nodes;
}

function renderTreeContextMenu(ctrl: AnalysisControllerBughouse): VNode | undefined {
    const menu = ctrl.tree.getTreeContextMenu();
    if (!menu) return undefined;

    const current = ctrl.tree.getTreeNodeAtPath(menu.path);
    if (!current) return undefined;

    const onMainline = ctrl.tree.pathIsTreeMainline(menu.path) && !ctrl.tree.pathIsTreeForcedVariation(menu.path);
    const canPromote = ctrl.tree.canPromoteTreeVariation(menu.path);
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
        const container = el.offsetParent as HTMLElement | null;
        if (!container) return;

        const minLeft = container.scrollLeft + 4;
        const maxLeft = container.scrollLeft + container.clientWidth - el.offsetWidth - 4;
        const minTop = container.scrollTop + 4;
        const maxTop = container.scrollTop + container.clientHeight - el.offsetHeight - 4;

        el.style.left = `${Math.max(minLeft, Math.min(menu.x, maxLeft))}px`;
        el.style.top = `${Math.max(minTop, Math.min(menu.y, maxTop))}px`;
    };

    if (canPromote) {
        actions.push(
            action('icon-arrow-up-right', _('Promote variation'), () => ctrl.tree.promoteTreeVariation(menu.path, false)),
        );
    }

    if (!onMainline) {
        actions.push(action('icon-check', _('Make main line'), () => ctrl.tree.promoteTreeVariation(menu.path, true)));
    }

    if (menu.path && onMainline) {
        actions.push(
            action('icon-arrow-down-right', _('Convert to variation'), () =>
                ctrl.tree.forceTreeVariation(menu.path, true),
            ),
        );
    }

    if (ctrl.tree.someTreeCollapsed(false)) {
        actions.push(action('icon-download', _('Collapse all'), () => ctrl.tree.collapseAllTree()));
    }

    if (ctrl.tree.someTreeCollapsed(true)) {
        actions.push(action('icon-plus-square', _('Expand all'), () => ctrl.tree.expandAllTree()));
    }

    actions.push(
        action('icon-clipboard', onMainline ? _('Copy main line PGN') : _('Copy variation PGN'), () =>
            ctrl.tree.copyTreeLinePgn(menu.path),
        ),
    );

    if (menu.path) {
        actions.push(action('icon-trash-o', _('Delete from here'), () => ctrl.tree.deleteTreeNode(menu.path)));
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
        [h('div.title', `${bugMovePrefix(current.step)} ${current.step.san ?? _('Start position')}`), ...actions],
    );
}

export function getLocalMoveNum(step: Step) {
    return Math.floor(step.boardName === 'a' ? (step.plyA! + 1) / 2 : (step.plyB! + 1) / 2);
}

export function formatChatMessageTime(x: StepChat) {
    const min = Math.floor(x.time / 60000);
    const sec = Math.floor((x.time - min * 60000) / 1000);
    const millis = x.time - min * 60000 - sec * 1000;
    const time = min + ':' + sec.toString().padStart(2, '0') + '.' + millis.toString().padStart(3, '0');
    return time;
}
