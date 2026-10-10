import { h, VNode } from 'snabbdom';

import { RoundController } from './roundCtrl';
import { gameInfo } from './gameInfo';
import { renderTimeago } from './datetime';
import { VARIANTS } from './variants';
import { PyChessModel } from './types';
import { BoardSummaryView } from './accessibility/boardSummary';

function runGround(vnode: VNode, model: PyChessModel, aliceBoardVNode?: VNode) {
    const el = vnode.elm as HTMLElement;
    const ctrl = new RoundController(el, model, aliceBoardVNode?.elm as HTMLElement | undefined);
    const cg = ctrl.chessground;
    window['cg'] = cg;
}

export function roundView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant];
    const isAlice = variant.name === 'alice';
    let mainboardVNode: VNode;
    let aliceBoardVNode: VNode | undefined;

    renderTimeago();

    return [
        h('aside.sidebar-first', [gameInfo(model), h('div#roundchat')]),
        h(
            'div.round-app',
            {
                class: { 'alice-round': isAlice },
                hook: { insert: () => runGround(mainboardVNode, model, aliceBoardVNode) },
            },
            [
                h(`selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`, [
                    h('div.cg-wrap.' + variant.board.cg, {
                        hook: { insert: vnode => (mainboardVNode = vnode) },
                    }),
                ]),
                !isAlice
                    ? ''
                    : h(
                          `selection#aliceboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
                          { attrs: { role: 'button', tabindex: '0' } },
                          [
                              h('div.cg-wrap.' + variant.board.cg, {
                                  hook: { insert: vnode => (aliceBoardVNode = vnode) },
                              }),
                          ],
                      ),
                h('div#janggi-setup-buttons'),
                h('div.material.material-top.' + variant.pieceFamily + '.disabled'),
                h('div.pocket-top', [
                    h('div.' + variant.pieceFamily + '.' + model['variant'], [
                        h('div.cg-wrap.pocket', [h('div#pocket0.pocketrow')]),
                    ]),
                ]),
                h('div.info-wrap0', [
                    h('div.clock-wrap', [h('div#clock0'), h('div#more-time'), h('div#berserk0')]),
                    h('div#misc-info0'),
                ]),
                h('div#expiration-top'),
                h('round-player0#rplayer0'),
                h('div#move-controls'),
                h('div.movelist-block', [h('div#movelist')]),
                h('div#offer-dialog'),
                h('div#game-controls'),
                h('round-player1#rplayer1'),
                h('div#expiration-bottom'),
                h('div.info-wrap1', [h('div.clock-wrap', [h('div#clock1'), h('div#berserk1')]), h('div#misc-info1')]),
                h('div.pocket-bot', [
                    h('div.' + variant.pieceFamily + '.' + model['variant'], [
                        h('div.cg-wrap.pocket', [h('div#pocket1.pocketrow')]),
                    ]),
                ]),
                h('div.material.material-bottom.' + variant.pieceFamily + '.disabled'),
            ],
        ),
        h('under-left#spectators'),
        h('under-board', [h('div.ctable-container'), h('div.games-container')]),
        BoardSummaryView.placeholder('', 'assertive'),
    ];
}
