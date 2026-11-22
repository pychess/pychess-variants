import { expect, jest, test } from '@jest/globals';
import type { VNode } from 'snabbdom';

import type { PyChessModel } from '../client/types';

jest.unstable_mockModule('../client/main', () => ({ model: {} }));
jest.unstable_mockModule('chessgroundx', () => ({ Chessground: jest.fn() }));

const { lobbyView } = await import('../client/lobby');

const assetURL = 'https://cdn.jsdelivr.net/gh/pychess/pychess-variants@1.11.83/static';

function coverSource(image: string, image_src: string): unknown {
    const nodes = lobbyView({
        assetURL,
        anon: 'True',
        username: 'Viewer',
        gameCategory: 'all',
        puzzle: JSON.stringify({ v: 'chess', f: '8/8/8/8/8/8/8/8 w - - 0 1' }),
        corrGames: '[]',
        blogs: JSON.stringify([{ image, image_src, category: 'all' }]),
        timeline: '[]',
    } as PyChessModel);
    const pending: VNode[] = [...nodes];
    while (pending.length) {
        const node = pending.pop()!;
        if (node.sel === 'img') return node.data?.attrs?.src;
        for (const child of node.children ?? []) {
            if (typeof child === 'object' && child !== null) pending.push(child);
        }
    }
    throw new Error('Lobby blog cover was not rendered');
}

test.each([
    ['legacy local cover', '/images/engine.jpeg', '/static/images/engine.jpeg'],
    ['normalized local cover', '/static/images/engine.jpeg', '/static/images/engine.jpeg'],
    ['versioned CDN cover', assetURL + '/images/engine.jpeg', assetURL + '/images/engine.jpeg'],
    ['approved external cover', 'https://i.imgur.com/example.jpg', 'https://i.imgur.com/example.jpg'],
])('lobby uses the server-approved source for a %s', (_name, image, resolved) => {
    expect(coverSource(image, resolved)).toBe(resolved);
});

test.each(['', 'https://untrusted.example/image.jpg'])(
    'lobby uses the default cover when the server supplies no approved image for %s',
    image => {
        expect(coverSource(image, '')).toBe(assetURL + '/images/ublog-default-cover.svg');
    },
);
