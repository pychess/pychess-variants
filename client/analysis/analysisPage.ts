import { h, type VNode } from 'snabbdom';

import { _ } from '../i18n';
import type { ColorName } from '../chess';
import type { PyChessModel } from '../types';
import { VARIANTS } from '../variants';
import { gaugeSideColors } from '../variantColor';
import { analysisSettings } from './analysisSettings';
import { BoardSummaryView } from '../accessibility/boardSummary';
import { pageHeading, srHeading } from '../view';

export type AnalysisPageParts = {
    side: VNode | VNode[];
    underboard: VNode | VNode[];
    mountBoard: (vnode: VNode, model: PyChessModel) => void;
    ongoing: boolean;
    boardTop?: VNode;
    boardBottom?: VNode;
    toolsAfterMoves?: VNode | VNode[];
};

/**
 * Shared single-board analysis shell.
 *
 * The board, engine/movelist tools, controls, pockets and spectators belong to
 * generic analysis. Page modes provide only their page-specific sidebar,
 * under-board content and controller mount. Study can therefore reuse this
 * shell without teaching the generic renderer about Study-specific UI.
 */
export function renderAnalysisPage(model: PyChessModel, parts: AnalysisPageParts): VNode[] {
    const variant = VARIANTS[model.variant];
    const isOngoingGame = parts.ongoing;

    return [
        /* THE PAGE'S MAIN LANDMARK IS THIS ELEMENT, not a wrapper around it. `#main-wrap` is a grid
           whose only named area is `main`, and `.analysis-app` is the item that claims it
           (`analysis.css:10`) -- so wrapping this in a `<main>` would put an unplaced element
           between the grid and its item and drop the board out of its area. Changing the TAG keeps
           the class, the grid placement and the DOM depth exactly as they were.

           Before this, the analysis, editor and puzzle pages exposed only `banner` and
           `complementary`: a screen reader's landmark jump landed in the sidebar and the board
           belonged to no region at all. The round pages have had `main` all along
           (`main.ts:212`). */
        h('main.analysis-app', [
            pageHeading(),
            h('aside.sidebar-first', parts.side),
            h(`selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`, [
                parts.boardTop ?? h('div#anal-clock-top'),
                h('div.cg-wrap.' + variant.board.cg, {
                    hook: { insert: vnode => parts.mountBoard(vnode, model) },
                }),
                parts.boardBottom ?? h('div#anal-clock-bottom'),
            ]),
            isOngoingGame ? '' : gauge(variant.colors),
            h('div.pocket-top', [
                h('div.' + variant.pieceFamily + '.' + model.variant, [
                    h('div.cg-wrap.pocket', [h('div#pocket0.pocketrow')]),
                ]),
            ]),
            analysisTools(isOngoingGame, parts.toolsAfterMoves),
            analysisSettings.view(variant),
            h('div#move-controls'),
            h('div.pocket-bot', [
                h('div.' + variant.pieceFamily + '.' + model.variant, [
                    h('div.cg-wrap.pocket', [h('div#pocket1.pocketrow')]),
                ]),
            ]),
            h('under-left#spectators'),
            h('under-board', parts.underboard),
            BoardSummaryView.placeholder('', 'polite'),
        ]),
    ];
}

export function analysisTools(isOngoingGame: boolean = false, afterMoves?: VNode | VNode[]) {
    const afterMovesNodes = afterMoves ? (Array.isArray(afterMoves) ? afterMoves : [afterMoves]) : [];
    return h('div.analysis-tools', [
        isOngoingGame
            ? ''
            : h('div#ceval', [
                  h('div.engine', [
                      h('score#score', ''),
                      h('div.info', [
                          'Fairy-Stockfish 14+ ',
                          h(
                              'span.nnue',
                              { props: { title: _('Multi-threaded WebAssembly (classical evaluation)') } },
                              'HCE',
                          ),
                          h('br'),
                          h('info#info', _('in local browser')),
                      ]),
                      h('div.engine-toggle'),
                  ]),
              ]),
        isOngoingGame ? '' : h('div.pvbox', [h('div#pv1'), h('div#pv2'), h('div#pv3'), h('div#pv4'), h('div#pv5')]),
        srHeading('h2', _('Moves')),
        h('div.movelist-block', [h('div#movelist')]),
        h('div#movelist-footer'),
        ...afterMovesNodes,
        h('div#misc-info', [h('div#misc-infow'), h('div#misc-info-center'), h('div#misc-infob')]),
        isOngoingGame
            ? ''
            : h('div.feedback', [
                  h('div.player'),
                  h('div.view-hint', [h('a.button.hint')]),
                  h('div.view-solution', [h('a.button.solution')]),
              ]),
    ]);
}

export function gauge(colors: { first: ColorName; second: ColorName }, id: string = 'gauge', extraClass?: string) {
    const sideColors = gaugeSideColors(colors);
    return h(
        'div#' + id + (extraClass ? '.' + extraClass : ''),
        {
            attrs: {
                style: `--analysis-gauge-first: ${sideColors.first}; --analysis-gauge-second: ${sideColors.second};`,
            },
        },
        [
            h('div.fill', { props: { style: 'height: 50%;' } }),
            h('div.tick', { props: { style: 'height: 12.5%;' } }),
            h('div.tick', { props: { style: 'height: 25%;' } }),
            h('div.tick', { props: { style: 'height: 37.5%;' } }),
            h('div.tick.zero', { props: { style: 'height: 50%;' } }),
            h('div.tick', { props: { style: 'height: 62.5%;' } }),
            h('div.tick', { props: { style: 'height: 75%;' } }),
            h('div.tick', { props: { style: 'height: 87.5%;' } }),
        ],
    );
}
