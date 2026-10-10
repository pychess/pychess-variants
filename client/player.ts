import { h, VNode } from 'snabbdom';

import { aiDisplayName, aiLevel } from './result';
import { _ } from './i18n';
import { displayUsername, userLink } from './user';

// A player bar. `id` identifies the bar's presence icon, and by default also names
// its root element. The bughouse round seat views override `root`: their bars sit in
// a page-layout slot whose element carries classes and an id of its own, and whose
// tag must not vary per board — so there the root selector and the icon id diverge.
export function player(
    id: string,
    title: string,
    name: string,
    rating: string,
    level: number,
    online = false,
    root = 'round-' + id,
    patron = false,
    variant = '',
): VNode {
    const playerName = aiDisplayName(name, variant);
    const displayName = displayUsername(playerName);
    return h(root, [
        h('div.player-data', [
            h('i-side#' + id + '.icon', {
                class: {
                    online,
                    offline: !online,
                    'icon-online': online && !patron,
                    'icon-offline': !online && !patron,
                    'icon-patron-wing': patron,
                },
                attrs: patron ? { title: _('PyChess Patron') } : {},
            }),
            h('player', [
                userLink(playerName, [
                    title !== '' ? h('player-title', title + ' ') : '',
                    displayName + aiLevel(playerName, level),
                ]),
                h('rating', title !== 'BOT' ? rating : ''),
            ]),
        ]),
    ]);
}
