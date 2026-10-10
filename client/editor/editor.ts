import { h, VNode } from 'snabbdom';

import { _ } from '@/i18n';
import { PyChessModel } from '@/types';
import { twoBoarsVariants, selectVariant, VARIANTS, validVariant } from '@/variants';
import { EditorController } from './editorCtrl';

function runEditor(vnode: VNode, model: PyChessModel) {
    const el = vnode.elm as HTMLElement;
    new EditorController(el, model);
}

export function editorView(model: PyChessModel): VNode[] {
    const setVariant = (isInput: boolean) => {
        let e;
        e = document.getElementById('variant') as HTMLSelectElement;
        const variant = e.options[e.selectedIndex].value;
        if (isInput) window.location.assign('/editor/' + validVariant(variant));
    };

    const vVariant = model.variant || 'chess';
    const variant = VARIANTS[vVariant];

    return [
        h('main.editor-app', [
            h('aside.sidebar-first', [
                h('div.container', [
                    h('div', [
                        h('label', { attrs: { for: 'variant' } }, _('Variant')),
                        selectVariant(
                            'variant',
                            vVariant,
                            () => setVariant(true),
                            () => setVariant(false),
                            twoBoarsVariants,
                            model.gameCategory,
                        ) /*todo:bughouse editor not implemented*/,
                    ]),
                ]),
            ]),

            h('div.pocket-wrapper.top', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [h('div.cg-wrap.pocket', [h('div#pieces0')])]),
            ]),
            h(`selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`, [
                h('div.cg-wrap.' + variant.board.cg, { hook: { insert: vnode => runEditor(vnode, model) } }),
            ]),
            h('div.pocket-wrapper.bot', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [h('div.cg-wrap.pocket', [h('div#pieces1')])]),
            ]),

            h('div.pocket-top', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [
                    h('div.cg-wrap.pocket', [h('div#pocket0.pocketrow')]),
                ]),
            ]),
            h('div#editor-button-container'),
            h('div.pocket-bot', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [
                    h('div.cg-wrap.pocket', [h('div#pocket1.pocketrow')]),
                ]),
            ]),
            h('under-board', [h('input#fen')]),
        ]),
    ];
}
