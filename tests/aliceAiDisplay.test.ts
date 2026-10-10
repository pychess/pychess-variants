import { expect, test } from '@jest/globals';

import { gameInfo } from '../client/gameInfo';
import { player } from '../client/player';
import { VARIANTS } from '../client/variants';

function collectText(node: any): string {
    if (node === null || node === undefined) return '';
    if (typeof node === 'string' || typeof node === 'number') return String(node);
    if (Array.isArray(node)) return node.map(collectText).join('');
    if (typeof node === 'object') {
        return (node.text ? String(node.text) : '') + (node.children ? collectText(node.children) : '');
    }
    return '';
}

test('Alice game info labels the built-in AI as Alice-Stockfish', () => {
    const model = {
        variant: 'alice',
        chess960: 'False',
        base: 3,
        inc: 2,
        byo: 0,
        corr: 'False',
        rated: '0',
        initialFen: VARIANTS.alice.startFen,
        posnum: -1,
        status: 1,
        date: new Date().toISOString(),
        wplayer: 'Human',
        wtitle: '',
        wrating: '1500?',
        wrdiff: 0,
        wberserk: 'False',
        bplayer: 'Fairy-Stockfish',
        btitle: 'BOT',
        brating: '1500?',
        brdiff: 0,
        bberserk: 'False',
        level: 1,
        tournamentId: '',
        tournamentname: '',
    } as any;

    const text = collectText(gameInfo(model));
    expect(text).toContain('Alice-Stockfish level 1');
    expect(text).not.toContain('Fairy-Stockfish level 1');
});

test('Alice round player bar uses the Alice engine display name', () => {
    const text = collectText(player('player0', 'BOT', 'Fairy-Stockfish', '', 1, false, undefined, false, 'alice'));

    expect(text).toContain('Alice-Stockfish level 1');
    expect(text).not.toContain('Fairy-Stockfish level 1');
});
