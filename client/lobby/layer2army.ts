import { h } from 'snabbdom';

import { _ } from '../i18n';
import { VARIANTS, variantGroups } from '../variants';
import { LobbyController } from '../lobby';
import { patch } from '../document';
import { goBackToLayer1 } from './util';
import { layer3variant } from './layer3';

export function layer2army(lobbyCtrl: LobbyController, containerId: string, showBack: boolean = true): void {
    const assetUrl = lobbyCtrl.assetURL;
    const armyVariants = new Set(variantGroups.army.variants);
    const infoItems = [
        h('h4', _('New Army Variants')),
        h('div.generic-image-container.fourarmykings', [
            h('img', { attrs: { src: assetUrl + '/images/4ArmyKings.svg', alt: '' } }),
        ]),
        h(
            'p.variant-category-description',
            _(
                'These variants have new armies with completely new pieces! Most of these variants pit these armies against the standard Chess army.',
            ),
        ),
    ];

    if (showBack) {
        infoItems.push(
            h(
                'h5#armyl2back',
                {
                    class: { icon: true, 'icon-reply': true },
                    on: { click: () => goBackToLayer1(lobbyCtrl, 'layer2armycont') },
                },
                _('Go Back'),
            ),
        );
    }

    const layer2cont = h('div#layer2armycont.layer-2-container.fairy-grid', [
        h('button.layer-2-category generic-variant-info.generic-fairy', [h('div.layer-two-category-info', infoItems)]),
        h('div.button-grid', [
            ...(armyVariants.has('cwda')
                ? [
                      h(
                          'button.layer-2-category',
                          { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'cwda') } },
                          [
                              h('div.variant-title-l2', [
                                  h('div.icon', { attrs: { 'data-icon': VARIANTS['cwda'].icon(false) } }),
                                  h('h3', VARIANTS['cwda'].displayName()),
                              ]),
                          ],
                      ),
                  ]
                : []),
            h('button.layer-2-category', { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'orda') } }, [
                h('div.variant-title-l2', [
                    h('div.icon', { attrs: { 'data-icon': VARIANTS['orda'].icon(false) } }),
                    h('h3', VARIANTS['orda'].displayName()),
                ]),
            ]),
            h('button.layer-2-category', { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'khans') } }, [
                h('div.variant-title-l2', [
                    h('div.icon', { attrs: { 'data-icon': VARIANTS['khans'].icon(false) } }),
                    h('h3', VARIANTS['khans'].displayName()),
                ]),
            ]),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'empire') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['empire'].icon(false) } }),
                        h('h3', VARIANTS['empire'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'ordamirror') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['ordamirror'].icon(false) } }),
                        h('h3', VARIANTS['ordamirror'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'shinobiplus') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['shinobiplus'].icon(false) } }),
                        h('h3', VARIANTS['shinobiplus'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'synochess') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['synochess'].icon(false) } }),
                        h('h3', VARIANTS['synochess'].displayName()),
                    ]),
                ],
            ),
            h('button.layer-2-category', { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'chak') } }, [
                h('div.variant-title-l2', [
                    h('div.icon', { attrs: { 'data-icon': VARIANTS['chak'].icon(false) } }),
                    h('h3', VARIANTS['chak'].displayName()),
                ]),
            ]),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'chennis') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['chennis'].icon(false) } }),
                        h('h3', VARIANTS['chennis'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'spartan') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['spartan'].icon(false) } }),
                        h('h3', VARIANTS['spartan'].displayName()),
                    ]),
                ],
            ),
            h(
                'button.layer-2-category',
                { on: { click: () => layer3variant('layer2armycont', lobbyCtrl, 'xiangfu') } },
                [
                    h('div.variant-title-l2', [
                        h('div.icon', { attrs: { 'data-icon': VARIANTS['xiangfu'].icon(false) } }),
                        h('h3', VARIANTS['xiangfu'].displayName()),
                    ]),
                ],
            ),
        ]),
    ]);

    const container = document.getElementById(containerId) as HTMLElement;
    if (container) patch(container, layer2cont);
}
