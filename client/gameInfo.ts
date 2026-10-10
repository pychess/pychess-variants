import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { colorIcon } from './chess';
import { aiDisplayName, aiLevel, gameType, renderRdiff } from './result';
import { timeago } from './datetime';
import { alternateStartName, timeControlStr } from './view';
import { PyChessModel } from './types';
import { VARIANTS, variantKey } from './variants';
import { displayUsername, userLink } from './user';

export function gameInfo(model: PyChessModel): VNode {
    // console.log("roundView model=", model);
    const variant = VARIANTS[model.variant];
    const chess960 = model.chess960 === 'True';
    const dataIcon = variant.icon(chess960);
    const tc = timeControlStr(model['base'], model['inc'], model['byo'], model['corr'] === 'True' ? model['base'] : 0);
    const altStartName = alternateStartName(variant, model.initialFen);
    const startFen = model.initialFen.replace(/\+/g, '.');
    const sections = [
        h('section', [
            h('div.info0.icon', { attrs: { 'data-icon': dataIcon } }, [
                h('div.info2', [
                    h('div.tc', [
                        tc + ' • ' + gameType(model['rated']) + ' • ',
                        h(
                            'a.user-link',
                            {
                                attrs: {
                                    target: '_blank',
                                    href: '/variants/' + variantKey(model.variant, chess960),
                                },
                            },
                            variant.displayName(chess960),
                        ),
                    ]),
                    h('div', altStartName ? altStartName : ''),
                    h(
                        'div',
                        Number(model['status']) >= 0
                            ? h('info-date', { attrs: { timestamp: model['date'] } }, timeago(model['date']))
                            : _('Playing right now'),
                    ),
                ]),
            ]),
            h('div.player-data', [
                h('i-side.icon', { class: { [colorIcon(model.variant, variant.colors.first)]: true } }),
                h('player', [playerInfo(model, 'w')]),
            ]),
            h('div.player-data', [
                h('i-side.icon', { class: { [colorIcon(model.variant, variant.colors.second)]: true } }),
                h('player', [playerInfo(model, 'b')]),
            ]),
        ]),
    ];
    if (model['posnum'] >= 0) {
        sections.push(
            h('section', [
                h('div.posnum', [
                    _('Start position: '),
                    h(
                        'a',
                        {
                            attrs: {
                                target: '_blank',
                                href: '/analysis/' + model['variant'] + '?fen=' + startFen,
                            },
                        },
                        model['posnum'],
                    ),
                ]),
            ]),
        );
    }
    if (model['tournamentId']) {
        sections.push(
            h('section', [
                h('div.tourney', [
                    h(
                        'a.icon.icon-trophy',
                        { attrs: { href: '/tournament/' + model['tournamentId'] } },
                        model['tournamentname'],
                    ),
                ]),
            ]),
        );
    }
    if (model['simulId']) {
        sections.push(
            h('section', [
                h('div.tourney', [
                    h(
                        'a.icon.icon-target',
                        { attrs: { href: '/simul/' + model['simulId'] } },
                        model['simulname'] || _('Simul'),
                    ),
                ]),
            ]),
        );
    }
    return h('div.game-info', sections);
}

function playerInfo(model: PyChessModel, color: string) {
    const username = model[color === 'w' ? 'wplayer' : 'bplayer'];
    const title = model[color === 'w' ? 'wtitle' : 'btitle'];
    const level = model.level;
    const rating = model[color === 'w' ? 'wrating' : 'brating'];
    const rdiff = model[color === 'w' ? 'wrdiff' : 'brdiff'];
    const berserk = model[color === 'w' ? 'wberserk' : 'bberserk'];
    const playerName = aiDisplayName(username, model.variant);
    const displayName = displayUsername(playerName);

    return userLink(playerName, [
        title !== '' ? h('player-title', title + ' ') : '',
        displayName + aiLevel(username, level) + (title !== 'BOT' ? ' (' + rating + ') ' : ''),
        model['status'] < 1 || model['rated'] !== '1' ? h('rdiff#' + color + 'rdiff') : renderRdiff(rdiff),
        berserk === 'True' ? h('icon.icon-berserk') : h('berserk#' + color + 'berserk'),
    ]);
}
