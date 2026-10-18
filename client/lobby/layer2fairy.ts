import { h } from 'snabbdom';

import { _ } from '../i18n';
import { VARIANTS } from '../variants';
import { patch } from '../document';
import { LobbyController } from '../lobby';
import { goBackToLayer1 } from './util';
import { layer3variant } from './layer3';

export function layer2fairy(lobbyCtrl: LobbyController, containerId: string, showBack: boolean = true): void {
    const assetUrl = lobbyCtrl.assetURL;
    const infoItems = [
        h('h4', _('Fairy Piece Variants')),
        h('div.generic-image-container.fourarmykings', [
            h('img', { attrs: { src: assetUrl + '/images/4FairyPieces.svg', alt: '' } }),
        ]),
        h(
            'p.variant-category-description',
            _('These variants have new pieces to try! Many of them have larger boards, and some also have new rules.'),
        ),
    ];

    if (showBack) {
        infoItems.push(
            h(
                'h5#fairyl2back',
                {
                    class: { icon: true, 'icon-reply': true },
                    on: { click: () => goBackToLayer1(lobbyCtrl, 'layer2fairycont') },
                },
                _('Go Back'),
            ),
        );
    }

    const layer2cont = h('div#layer2fairycont.layer-2-container.fairy-grid', [
        h('button.layer-2-category generic-variant-info.generic-fairy', [h('div.layer-two-category-info', infoItems)]),
        h('div.button-grid', [
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'shatranj') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['shatranj'].icon() } }),
                        h('h3', VARIANTS['shatranj'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'capablanca') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['capablanca'].icon() } }),
                        h('h3', VARIANTS['capablanca'].displayName()),
                        h('div.icon', { attrs: { 'data-icon': 'V' } }),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'capahouse') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['capahouse'].icon() } }),
                        h('h3', VARIANTS['capahouse'].displayName()),
                        h('div.icon', { attrs: { 'data-icon': 'V' } }),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'dragon') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['dragon'].icon() } }),
                        h('h3', VARIANTS['dragon'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'seirawan') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['seirawan'].icon() } }),
                        h('h3', VARIANTS['seirawan'].displayName()),
                        h('div.icon', { attrs: { 'data-icon': 'V' } }),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'shouse') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['shouse'].icon() } }),
                        h('h3', VARIANTS['shouse'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'shako') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['shako'].icon() } }),
                        h('h3', VARIANTS['shako'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'grand') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['grand'].icon() } }),
                        h('h3', VARIANTS['grand'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'grandhouse') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['grandhouse'].icon() } }),
                        h('h3', VARIANTS['grandhouse'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'shogun') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['shogun'].icon() } }),
                        h('h3', VARIANTS['shogun'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'hoppelpoppel') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['hoppelpoppel'].icon() } }),
                        h('h3', VARIANTS['hoppelpoppel'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2fairycont', lobbyCtrl, 'mansindam') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['mansindam'].icon() } }),
                        h('h3', VARIANTS['mansindam'].displayName()),
                    ]),
                ],
            ),
        ]),
    ]);

    const container = document.getElementById(containerId) as HTMLElement;
    if (container) patch(container, layer2cont);
}
