import { expect, jest, test } from '@jest/globals';

import { displayUsername, isAnonUsername, userLink } from '../client/user';
import { gameInfo } from '../client/gameInfo';
import { disabledVariantsForCreateMode, VARIANTS } from '../client/variants';
import { Seek } from '../client/lobbyType';

jest.unstable_mockModule('@/lobby', () => ({
    disableCorr: () => {},
    LobbyController: class {},
}));

function collectText(node: any): string {
    if (node === null || node === undefined) {
        return '';
    }
    if (typeof node === 'string' || typeof node === 'number') {
        return String(node);
    }
    if (Array.isArray(node)) {
        return node.map(collectText).join('');
    }
    if (typeof node === 'object') {
        let text = '';
        if (node.text) {
            text += node.text;
        }
        if (node.children) {
            text += collectText(node.children);
        }
        return text;
    }
    return '';
}

test('anon usernames are masked and not linked', () => {
    const anonName = 'Anon–abcd1234';
    expect(isAnonUsername(anonName)).toBe(true);
    expect(displayUsername(anonName)).toBe('Anonymous');

    const anonNode = userLink(anonName, displayUsername(anonName));
    expect(anonNode.sel).toBe('span');

    const realNode = userLink('RealUser', 'RealUser');
    expect(realNode.sel).toBe('a');
});

test('anon usernames are masked in seeks', async () => {
    const anonName = 'Anon–seek1234';
    const seek: Seek = {
        user: anonName,
        variant: 'bughouse',
        color: 'w',
        fen: '',
        base: 3,
        inc: 0,
        byoyomi: 0,
        day: 0,
        chess960: false,
        rated: false,
        bot: false,
        rating: 1500,
        seekID: 'seek-1',
        target: '',
        title: '',
        bugPlayer1: '',
        player2: '',
        bugPlayer2: '',
    };

    const ctrl = {
        username: 'OtherUser',
        anon: false,
        seekTitle: () => null,
        challengeIcon: () => null,
        tooltip: () => null,
        mode: () => '',
    } as any;

    const { seekViewBughouse } = await import('../client/two-board/lobby');
    const vnode = seekViewBughouse(ctrl, seek);
    const text = collectText(vnode);
    expect(text).toContain('Anonymous');
    expect(text).not.toContain(anonName);
});

test('anon usernames are masked in game info', () => {
    const anonName = 'Anon–game1234';
    const model = {
        variant: 'chess',
        chess960: 'False',
        base: 3,
        inc: 0,
        byo: 0,
        corr: 'False',
        rated: '0',
        initialFen: VARIANTS.chess.startFen,
        posnum: -1,
        status: 0,
        date: new Date().toISOString(),
        wplayer: anonName,
        wtitle: '',
        wrating: '1500',
        wrdiff: 0,
        wberserk: 'False',
        bplayer: 'RealUser',
        btitle: '',
        brating: '1500',
        brdiff: 0,
        bberserk: 'False',
        level: 0,
        tournamentId: '',
        tournamentname: '',
    } as any;

    const vnode = gameInfo(model);
    const text = collectText(vnode);
    expect(text).toContain('Anonymous');
    expect(text).not.toContain(anonName);
});

test('two-board variants are disabled for targeted game creation', async () => {
    expect(disabledVariantsForCreateMode('createGame', 'Invite-friend', false)).toContain('bughouse');
    expect(disabledVariantsForCreateMode('createGame', 'berado88', false)).toContain('bughouse');
    expect(disabledVariantsForCreateMode('createGame', '', false)).not.toContain('bughouse');
});

test('play with AI only statically disables variants without a supported server engine path', async () => {
    const disabled = disabledVariantsForCreateMode('playAI', '', false);
    expect(disabled).not.toContain('alice');
    expect(disabled).toContain('fogofwar');
    expect(disabled).toContain('jieqi');
});

test('external bot capabilities distinguish normal and 960 variants', async () => {
    const supported = new Set(['alice', 'crazyhouse960']);
    const disabled = disabledVariantsForCreateMode('playBOT', 'Alice-Stockfish', false, supported);

    expect(disabled).not.toContain('alice');
    expect(disabled).not.toContain('crazyhouse');
    expect(disabled).toContain('chess');
    expect(disabled).toContain('atomic');
    expect(disabled).toContain('bughouse');
});
