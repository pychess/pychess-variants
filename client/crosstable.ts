import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { CrossTable } from './messages';
import { displayUsername, userLink } from './user';

export function crosstableView(ctable: CrossTable, gameId: string) {
    const s1 = ctable.s1,
        s2 = ctable.s2,
        games = ctable.r;
    let rows: VNode[];
    if (games.length < 20) {
        rows = [h('fill')];
    } else {
        rows = [];
    }
    rows = rows.concat(
        games.map(game => {
            const ref = game.slice(0, -1);
            const scores: Record<string, string[]> = { '+': ['1', '0'], '-': ['0', '1'] };
            const [r1, r2] = scores[game.slice(-1)] ?? ['½', '½'];
            const label = `${_('Open game')}: ${r1}–${r2}`;
            const link = (s: string) =>
                h(
                    'a.info-result',
                    {
                        class: { win: s === '1', lose: s === '0', draw: s === '½' },
                        attrs: { href: '/' + ref, 'aria-label': label },
                    },
                    s,
                );
            return h('povs', { class: { current: gameId === ref } }, [link(r1), link(r2)]);
        }),
    );

    const names = ctable._id.split('/');
    const p1 = userLink(names[0], displayUsername(names[0]), { className: '' });
    const p2 = userLink(names[1], displayUsername(names[1]), { className: '' });

    rows.push(h('div.ct-users', [p1, p2]));

    let lt1, lt2, half;
    half = s1 % 10 === 5 ? '½' : '';
    lt1 = s1 === 5 ? '' : Math.floor(s1 / 10);
    lt2 = s2 === 5 ? '' : Math.floor(s2 / 10);
    if (s1 === s2) {
        lt1 = lt2 = h('span.info-result', lt1 + half);
    } else if (s1 > s2) {
        lt1 = h('span.info-result.win', lt1 + half);
        lt2 = h('span.info-result.lose', lt2 + half);
    } else {
        lt1 = h('span.info-result.lose', lt1 + half);
        lt2 = h('span.info-result.win', lt2 + half);
    }

    rows.push(h('div.ct-score', [lt1, lt2]));

    return h(
        'div.ctable-container',
        { attrs: { id: 'panel-3', role: 'tabpanel', tabindex: '0', 'aria-labelledby': 'tab-3' } },
        [h('div.crosstable', rows)],
    );
}
