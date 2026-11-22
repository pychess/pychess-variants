import { afterEach, expect, jest, test } from '@jest/globals';

import { addOrSelectChild, createAnalysisTree, mergeServerAdvice } from '../client/analysis/analysisTree';
import type { GameController } from '../client/gameCtrl';
import type { Step } from '../client/messages';
import { selectMove, updateMovelist } from '../client/movelist';

afterEach(() => {
    document.body.innerHTML = '';
    jest.restoreAllMocks();
});

function rect(top: number, height: number): DOMRect {
    return { top, bottom: top + height, height } as DOMRect;
}

test.each(['inner', 'outer'])('navigation scrolls the %s container using viewport geometry', scroller => {
    document.body.innerHTML =
        '<div class="movelist-block"><div id="movelist"><line><move ply="1">e4</move></line></div></div>';
    const list = document.getElementById('movelist')!;
    const block = list.parentElement!;
    const active = list.querySelector<HTMLElement>('move')!;
    Object.defineProperty(list, 'scrollHeight', { value: scroller === 'inner' ? 1000 : 200 });
    Object.defineProperty(list, 'clientHeight', { value: 200 });
    const container = scroller === 'inner' ? list : block;
    container.scrollTop = 400;
    jest.spyOn(container, 'getBoundingClientRect').mockReturnValue(rect(100, 200));
    jest.spyOn(active, 'getBoundingClientRect').mockReturnValue(rect(500, 20));
    // offsetTop belongs to the positioned variation line, not the scroll panel.
    Object.defineProperty(active, 'offsetTop', { value: 0 });
    const ctrl = {
        ply: 1,
        steps: [{}, {}],
        goPly: jest.fn(),
    } as unknown as GameController;

    selectMove(ctrl, 1);

    expect(container.scrollTop).toBe(710);
    expect((scroller === 'inner' ? block : list).scrollTop).toBe(0);
    expect(active.classList.contains('active')).toBe(true);
});

test('returning to the initial position scrolls to the top', () => {
    document.body.innerHTML = '<div id="movelist"></div>';
    const list = document.getElementById('movelist')!;
    list.scrollTop = 400;
    selectMove({ ply: 0, steps: [{}], goPly: jest.fn() } as unknown as GameController, 0);
    expect(list.scrollTop).toBe(0);
});

test.each(['inner', 'outer'])('a tree redraw preserves %s scrolling without navigation', scroller => {
    document.body.innerHTML =
        '<div class="movelist-block"><div id="movelist" class="tview2"><move>e4</move></div></div>';
    const list = document.getElementById('movelist')!;
    const block = list.parentElement!;
    jest.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function (this: HTMLElement) {
        return this.id === 'movelist' && scroller === 'inner' ? 1000 : 200;
    });
    jest.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(200);
    const container = scroller === 'inner' ? list : block;
    container.scrollTop = 400;
    const root = { fen: 'start w - - 0 1', turnColor: 'white', san: '' } as Step;
    const tree = createAnalysisTree([root]);
    const ctrl = {
        analysisTree: tree,
        hasAnalysisTree: () => true,
        ply: 0,
        status: -1,
    } as unknown as GameController;

    updateMovelist(ctrl, true, false);

    const newList = document.getElementById('movelist')!;
    expect((scroller === 'inner' ? newList : block).scrollTop).toBe(400);
});

test('tree selectMove keeps ordinary analysis navigation unchanged without an extension', () => {
    document.body.innerHTML = '<div id="movelist"></div>';
    const steps = [
        { fen: 'start w - - 0 1', turnColor: 'white', san: '' },
        { fen: 's1 b - - 0 1', move: 'e2e4', turnColor: 'black', san: 'e4' },
    ] as Step[];
    const tree = createAnalysisTree(steps);
    const goPly = jest.fn();
    const activateTreePly = jest.fn();
    const ctrl = {
        steps,
        status: -1,
        result: '*',
        ply: 1,
        plyVari: 0,
        variant: { name: 'chess' },
        fog: false,
        mycolor: 'white',
        spectator: true,
        analysisTree: tree,
        hasAnalysisTree: () => true,
        isTreeInlineNotation: () => false,
        getTreeActivePath: () => tree.root.children[0].path,
        goPly,
        activateTreePly,
    } as unknown as GameController;

    selectMove(ctrl, 1);

    expect(goPly).toHaveBeenCalledWith(1, 0);
    expect(activateTreePly).not.toHaveBeenCalled();
});

test('tree selectMove routes navigation through the policy-aware active-line controller', () => {
    const activateTreePly = jest.fn();
    const ctrl = {
        hasAnalysisTree: () => true,
        analysisExtension: {},
        activateTreePly,
    } as unknown as GameController;

    selectMove(ctrl, 3);

    expect(activateTreePly).toHaveBeenCalledWith(3);
});

test('tree visibility policy omits hidden continuations from the rendered movelist', () => {
    document.body.innerHTML = '<div id="movelist"></div>';
    const steps = [
        { fen: 'start w - - 0 1', turnColor: 'white', san: '' },
        { fen: 's1 b - - 0 1', move: 'e2e4', turnColor: 'black', san: 'e4' },
        { fen: 's2 w - - 0 1', move: 'e7e5', turnColor: 'white', san: 'e5' },
    ] as Step[];
    const tree = createAnalysisTree(steps);
    const hiddenPath = tree.root.children[0].children[0].path;
    const ctrl = {
        steps,
        status: -1,
        result: '*',
        ply: 1,
        plyVari: 0,
        variant: { name: 'chess' },
        fog: false,
        mycolor: 'white',
        spectator: true,
        analysisTree: tree,
        analysisExtension: { isTreeNodeVisible: (node: { path: string }) => node.path !== hiddenPath },
        hasAnalysisTree: () => true,
        isTreeInlineNotation: () => false,
        getTreeActivePath: () => tree.root.children[0].path,
        activateTreePath: () => undefined,
    } as unknown as GameController;

    updateMovelist(ctrl, true, false, false);

    expect([...document.querySelectorAll('#movelist move:not(.empty)')].map(node => node.textContent)).toEqual(['e4']);
});

test.each([false, true])('server analysis can be hidden and restored in inline mode %s', inline => {
    document.body.innerHTML = '<div id="movelist"></div>';
    const steps = [
        { fen: 'start w - - 0 1', turnColor: 'white', san: '' },
        {
            fen: 'after b - - 0 1',
            move: 'e2e4',
            turnColor: 'black',
            san: 'e4',
            scoreStr: '-2.5',
            analysis: {
                s: { cp: -250 },
                advice: {
                    nag: 4,
                    comment: 'Blunder. d4 was best.',
                    variation: [{ fen: 'better b - - 0 1', move: 'd2d4', turnColor: 'black', san: 'd4' }],
                },
            },
        },
    ] as Step[];
    const tree = createAnalysisTree(steps);
    const move = tree.root.children[0];
    move.annotations!.comments.push({ id: 'authored', author: 'Player', text: 'My plan' });
    move.annotations!.nags.push(1);
    const ctrl = {
        steps,
        analysisTree: tree,
        hasAnalysisTree: () => true,
        isTreeInlineNotation: () => inline,
        ply: 1,
        status: -1,
        showServerAnalysis: true,
    } as unknown as GameController & { showServerAnalysis: boolean };

    updateMovelist(ctrl, true, false, false);
    expect(document.getElementById('movelist')!.textContent).toContain('??');
    expect(document.getElementById('movelist')!.textContent).toContain('-2.5');
    expect(document.getElementById('movelist')!.textContent).toContain('d4');

    ctrl.showServerAnalysis = false;
    updateMovelist(ctrl, true, false, false);
    const hidden = document.getElementById('movelist')!.textContent!;
    expect(hidden).not.toContain('??');
    expect(hidden).not.toContain('-2.5');
    expect(hidden).not.toContain('d4');
    expect(hidden).not.toContain('Blunder');
    expect(hidden).toContain('e4!');
    expect(hidden).toContain('My plan');
    expect(move.step.analysis?.advice?.nag).toBe(4);

    // Results arriving after the switch was disabled stay hidden.
    mergeServerAdvice(tree, 1, steps[1].analysis);
    updateMovelist(ctrl, true, false, false);
    expect(document.getElementById('movelist')!.textContent).not.toContain('Blunder');

    ctrl.showServerAnalysis = true;
    updateMovelist(ctrl, true, false, false);
    expect(document.getElementById('movelist')!.textContent).toContain('??');
    expect(document.getElementById('movelist')!.textContent).toContain('-2.5');
    expect(document.getElementById('movelist')!.textContent).toContain('Blunder');
});

test('server advice preserves a player-created continuation when analysis is hidden', () => {
    const steps = [
        { fen: 'start w - - 0 1', turnColor: 'white', san: '' },
        { fen: 'after b - - 0 1', move: 'e2e4', turnColor: 'black', san: 'e4' },
    ] as Step[];
    const tree = createAnalysisTree(steps);
    const alternative = { fen: 'better b - - 0 1', move: 'd2d4', turnColor: 'black', san: 'd4' } as Step;
    const path = addOrSelectChild(tree, '', alternative, false);
    mergeServerAdvice(tree, 1, { s: { cp: -250 }, advice: { nag: 4, comment: 'Blunder', variation: [alternative] } });
    expect(tree.byPath.get(path)!.serverAnalysis).toBeUndefined();
});
