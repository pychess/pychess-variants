import { afterEach, expect, jest, test } from '@jest/globals';
import type { Api } from 'chessgroundx/api';
import { Chessground } from 'chessgroundx/chessground';

import { boardSettings } from '../client/boardSettings';
import { patch } from '../client/document';
import { mountCataloguedStartBoards } from '../client/communityVariants';
import {
    BOARD_FAMILIES,
    CataloguedVariantClientDocument,
    cataloguedCompatibleBoardFamily,
    registerCataloguedVariant,
    unregisterCataloguedVariant,
    VARIANTS,
} from '../client/variants';

const variantNames = [
    'testshogiboarddefault',
    'testmakrukboardoverride',
    'testboarddimensionfallback',
    'testcustomboardoverride',
    'testcustomboardpreview',
    'testshogiboardpreview',
    'testyarishogiboardoverride',
    'testclientvariantboarddefault',
    'judkins',
    'testshogi10x10',
];
const originalIntersectionObserver = window.IntersectionObserver;

function register(meta: CataloguedVariantClientDocument) {
    registerCataloguedVariant(meta);
    return VARIANTS[meta.name];
}

afterEach(() => {
    document.body.textContent = '';
    document.head.querySelectorAll<HTMLElement>('[id*="catalogued-test"]').forEach(element => element.remove());
    variantNames.forEach(name => {
        const variant = VARIANTS[name];
        unregisterCataloguedVariant(name);
        delete localStorage[`${name}-board`];
        delete boardSettings.settings[`${name}-board`];
        if (variant?.boardFamily.startsWith('catalogued')) delete localStorage[`${variant.boardFamily}-board`];
    });
    if (originalIntersectionObserver) window.IntersectionObserver = originalIntersectionObserver;
    else Reflect.deleteProperty(window, 'IntersectionObserver');
});

test.each([false, true])('10x10 Shogi variants share the rectangular-cell board (uploaded board: %s)', hasBoard => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testshogi10x10',
        displayName: 'Test 10x10 Shogi',
        ini: '[testshogi10x10:shogi]\nmaxFile = 10\nmaxRank = 10',
        baseVariant: 'shogi',
        width: 10,
        height: 10,
        startFen: '9k/10/10/10/10/10/10/10/10/K9[] w - - 0 1',
        pieces: ['k'],
        kingRoles: ['k'],
        hasBoard,
    };
    const variant = register(meta);
    expect(cataloguedCompatibleBoardFamily(meta)).toBe('shogi10x10');
    expect(variant.board.cg).toBe('cg-shogi10x10');
    expect(variant.hasBoard).toBe(hasBoard);
    expect(boardSettings.boardCSS(variant.boardFamily, variant)).toBe('shogi10x10.svg');
});

test('an uploaded Shogi board can switch to wood and back, including newly mounted boards', () => {
    const variant = register({
        name: 'testshogi10x10',
        displayName: 'Test 10x10 Shogi',
        ini: '[testshogi10x10:shogi]',
        baseVariant: 'shogi',
        width: 10,
        height: 10,
        startFen: '9k/10/10/10/10/10/10/10/10/K9[] w - - 0 1',
        pieces: ['k'],
        kingRoles: ['k'],
        hasBoard: true,
        boardRevision: 'uploaded-r1',
    });
    boardSettings.assetURL = '/static';
    document.body.innerHTML =
        '<div class="shogi10x10"><div class="cg-wrap"></div></div><div id="board-settings"></div>';
    const board = document.querySelector<HTMLElement>('.shogi10x10')!;
    boardSettings.updateScopedBoardStyle(variant, board);
    const setting = boardSettings.getSettings('BoardStyle', variant.boardFamily, '', variant);
    patch(document.getElementById('board-settings')!, setting.view());

    const custom = document.getElementById('board0') as HTMLInputElement;
    const wood = document.getElementById('board1') as HTMLInputElement;
    expect(custom.checked).toBe(true);
    expect(custom.disabled).toBe(false);
    expect(wood).not.toBeNull();
    expect(document.querySelector<HTMLLabelElement>('label[for="board1"]')?.style.backgroundImage).toContain(
        'Shogi10x10Wood.svg',
    );

    wood.click();
    expect(setting.value).toBe(1);
    expect(board.classList.contains('board-style-builtin')).toBe(true);
    expect(board.style.getPropertyValue('--board-image')).toBe('url(/static/images/board/Shogi10x10Wood.svg)');
    const preview = document.createElement('div');
    preview.className = variant.boardFamily;
    document.body.appendChild(preview);
    boardSettings.updateScopedBoardStyle(variant, preview);
    expect(preview.classList.contains('board-style-builtin')).toBe(true);
    expect(preview.style.getPropertyValue('--board-image')).toBe(board.style.getPropertyValue('--board-image'));

    custom.click();
    expect(setting.value).toBe(0);
    for (const target of [board, preview]) {
        expect(target.classList.contains('board-style-builtin')).toBe(false);
        expect(target.style.getPropertyValue('--board-image')).toBe('');
    }
    // Keep the uploaded CSS loaded so its thumbnail and re-selection still work.
    expect(document.getElementById('board-set-catalogued-testshogi10x10')?.getAttribute('href')).toBe(
        '/api/catalogued-variants/testshogi10x10/board-css.css?v=uploaded-r1',
    );
});

test('catalogued variants inherit a dimension-compatible board family from their base variant', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testshogiboarddefault',
        displayName: 'Test Shogi Board Default',
        ini: '[testshogiboarddefault:shogi]',
        baseVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatibleBoardFamily(meta)).toBe('shogi9x9');
    expect(variant.boardFamily).toBe('shogi9x9');
    expect(boardSettings.boardCSS(variant.boardFamily, variant)).toBe(BOARD_FAMILIES.shogi9x9.boardCSS[0]);
});

test('clientVariant can provide board defaults without changing engine inheritance', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testclientvariantboarddefault',
        displayName: 'Test Client Variant Board Default',
        ini: '',
        baseVariant: '',
        clientVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatibleBoardFamily(meta)).toBe('shogi9x9');
    expect(variant.boardFamily).toBe('shogi9x9');
});

test('Judkins uses a 6x6 shogi board and all standard shogi piece styles', () => {
    const variant = register({
        name: 'judkins',
        displayName: 'Judkins Shogi',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'judkins',
        ini: '',
        baseVariant: '',
        clientVariant: 'shogi',
        boardFamilyOverride: 'shogi6x6',
        startFen: 'rbnsgk/5p/6/6/P5/KGSNBR[-] w 0 1',
        width: 6,
        height: 6,
        pieces: ['k', 'g', 'r', 'b', 's', 'n', 'p'],
        kingRoles: ['k'],
        pocketRoles: ['p', 'n', 's', 'g', 'b', 'r'],
        captureToHand: true,
        promotionType: 'shogi',
        promotionRoles: ['p', 'n', 's', 'b', 'r'],
        promotionOrder: ['+', ''],
    });

    expect(variant.boardFamily).toBe('shogi6x6');
    expect(variant.board.dimensions).toEqual({ width: 6, height: 6 });
    expect(boardSettings.boardCSS(variant.boardFamily, variant)).toBe('judkins.svg');
    expect(variant.pieceFamily).toBe('shogi');
    expect(variant.pieceCSSExclude).toEqual([]);
    expect(variant.promotion.order).toEqual(['+', '']);
    expect(variant.promotion.roles).toContain('n-piece');
    expect(variant.pocket?.roles.white).toContain('n-piece');
    expect(variant.rules.defaultTimeControl).toBe('byoyomi');
});

test('an explicit board family override takes precedence over base-variant detection', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testmakrukboardoverride',
        displayName: 'Test Makruk Board Override',
        ini: '[testmakrukboardoverride:chess]',
        baseVariant: 'chess',
        boardFamilyOverride: 'makruk8x8',
        startFen: '8/8/8/8/8/8/8/8 w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatibleBoardFamily(meta)).toBe('makruk8x8');
    expect(variant.boardFamily).toBe('makruk8x8');
});

test('dimension-incompatible base and override board families fall back to a generated checkerboard', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testboarddimensionfallback',
        displayName: 'Test Board Dimension Fallback',
        ini: '[testboarddimensionfallback:chess]\nmaxFile = 10',
        baseVariant: 'chess',
        boardFamilyOverride: 'makruk8x8',
        startFen: '10/10/10/10/10/10/10/10 w - - 0 1',
        width: 10,
        height: 8,
        pieces: ['k'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatibleBoardFamily(meta)).toBeUndefined();
    expect(variant.boardFamily).toBe('catalogued10x8');
});

test('the yarishogi board family is available for 7x9 catalogued variants', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testyarishogiboardoverride',
        displayName: 'Test Yarishogi Board Override',
        ini: '[testyarishogiboardoverride:shogi]\nmaxFile = 7\nmaxRank = 9',
        baseVariant: 'shogi',
        boardFamilyOverride: 'shogi7x9',
        startFen: '7/7/7/7/7/7/7/7/7 w - - 0 1',
        width: 7,
        height: 9,
        pieces: ['k'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatibleBoardFamily(meta)).toBe('shogi7x9');
    expect(variant.boardFamily).toBe('shogi7x9');
    expect(boardSettings.boardCSS(variant.boardFamily, variant)).toBe('YariPlain.svg');
});

test('uploaded custom boards retain priority while preserving the selected fallback family', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testcustomboardoverride',
        displayName: 'Test Custom Board Override',
        ini: '[testcustomboardoverride:chess]',
        baseVariant: 'chess',
        boardFamilyOverride: 'makruk8x8',
        startFen: '8/8/8/8/8/8/8/8 w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k'],
        kingRoles: ['k'],
        hasBoard: true,
        boardRevision: 'r1',
    };
    const variant = register(meta);

    expect(variant.hasBoard).toBe(true);
    expect(variant.boardFamily).toBe('makruk8x8');
});

test('rules and community previews mount read-only Chessgrounds with the detected styles', () => {
    register({
        name: 'testshogiboardpreview',
        displayName: 'Test Shogi Board Preview',
        ini: '[testshogiboardpreview:shogi]',
        baseVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k', 'p'],
        kingRoles: ['k'],
        pocketRoles: ['p'],
        captureToHand: true,
    });
    document.body.innerHTML = `
        <div class="catalogued-start-board-preview" data-variant="testshogiboardpreview"></div>`;

    const createChessground = jest.fn(() => ({ state: {} }) as Api) as unknown as typeof Chessground;
    const bindResize = jest.fn(() => () => undefined);

    mountCataloguedStartBoards('/static', createChessground, bindResize);

    const preview = document.querySelector<HTMLElement>('.catalogued-start-board-preview');
    const boardWrap = preview?.querySelector<HTMLElement>('.cg-wrap');
    expect(preview?.dataset.chessgroundMounted).toBe('true');
    expect(preview?.classList.contains('shogi9x9')).toBe(true);
    expect(preview?.classList.contains('shogi')).toBe(true);
    expect(preview?.classList.contains('with-pockets')).toBe(true);
    expect(preview?.style.getPropertyValue('--catalogued-board-ranks')).toBe('9');
    expect(preview?.dataset.boardVariant).toBe('testshogiboardpreview');
    expect(preview?.dataset.pieceVariant).toBe('testshogiboardpreview');
    expect(preview?.style.getPropertyValue('--board-image')).toBe('url(/static/images/board/shogi.svg)');
    expect(boardWrap?.classList.contains('cg-576')).toBe(true);
    expect(boardWrap?.classList.contains('mini')).toBe(true);
    expect(createChessground).toHaveBeenCalledWith(
        boardWrap,
        expect.objectContaining({
            fen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
            dimensions: { width: 9, height: 9 },
            coordinates: false,
            viewOnly: true,
            addDimensionsCssVarsTo: preview,
            pocketRoles: VARIANTS.testshogiboardpreview.pocket?.roles,
            animation: { enabled: false },
        }),
    );
    expect(bindResize).toHaveBeenCalledTimes(1);
});

test('community previews fetch only their missing definition before mounting', async () => {
    const originalFetch = globalThis.fetch;
    const name = 'lazy-community-preview';
    const fetchMetadata = jest.fn(async () => ({
        ok: true,
        json: async () => ({ variants: [{
            name, ini: `[${name}:chess]`, baseVariant: 'chess',
            startFen: '4k3/8/8/8/8/8/8/4K3 w - - 0 1', width: 8, height: 8, pieces: ['k'],
        }] }),
    } as Response));
    globalThis.fetch = fetchMetadata as typeof fetch;
    document.body.innerHTML = `<a class="catalogued-start-board-preview" data-variant="${name}"></a>`;
    const createChessground = jest.fn(() => ({ state: {} }) as Api) as unknown as typeof Chessground;
    try {
        mountCataloguedStartBoards('/static', createChessground, () => () => undefined);
        // Wait for the metadata request and the asynchronous preview mount.
        await new Promise(resolve => setTimeout(resolve, 0));
        expect(fetchMetadata).toHaveBeenCalledWith(`/api/catalogued-variants?name=${name}`);
        expect(document.querySelector<HTMLElement>('.catalogued-start-board-preview')?.dataset.chessgroundMounted).toBe('true');
        expect(createChessground).toHaveBeenCalledTimes(1);
    } finally {
        globalThis.fetch = originalFetch;
        unregisterCataloguedVariant(name);
    }
});

test('pocket variants render both pocket rows around the starting board', () => {
    register({
        name: 'testshogiboardpreview',
        displayName: 'Test Shogi Pocket Preview',
        ini: '[testshogiboardpreview:shogi]',
        baseVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9[Pp] w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k', 'p'],
        kingRoles: ['k'],
        pocketRoles: ['p'],
        captureToHand: true,
    });
    document.body.innerHTML = `
        <div class="catalogued-start-board-preview" data-variant="testshogiboardpreview"></div>`;
    let chessground: Api | undefined;
    const createChessground = ((element, config) => {
        chessground = Chessground(element, config);
        return chessground;
    }) as typeof Chessground;

    mountCataloguedStartBoards('/static', createChessground, jest.fn(() => () => undefined));

    expect(document.querySelector('pockettop.pocket.top piece[data-color="black"]')?.getAttribute('data-nb')).toBe(
        '1',
    );
    expect(
        document.querySelector('pocketbottom.pocket.bottom piece[data-color="white"]')?.getAttribute('data-nb'),
    ).toBe('1');
    chessground?.destroy();
});

test('a catalogue preview is mounted only once', () => {
    register({
        name: 'testshogiboardpreview',
        displayName: 'Test Shogi Board Preview',
        ini: '[testshogiboardpreview:shogi]',
        baseVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k'],
        kingRoles: ['k'],
    });
    document.body.innerHTML = `
        <div class="catalogued-start-board-preview" data-variant="testshogiboardpreview"></div>`;
    const createChessground = jest.fn(() => ({ state: {} }) as Api) as unknown as typeof Chessground;
    const bindResize = jest.fn(() => () => undefined);

    mountCataloguedStartBoards('/static', createChessground, bindResize);
    mountCataloguedStartBoards('/static', createChessground, bindResize);

    expect(createChessground).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll('.cg-wrap')).toHaveLength(1);
});

test('off-screen catalogue previews wait until they approach the viewport', () => {
    register({
        name: 'testshogiboardpreview',
        displayName: 'Test Shogi Board Preview',
        ini: '[testshogiboardpreview:shogi]',
        baseVariant: 'shogi',
        startFen: '9/9/9/9/9/9/9/9/9 w - - 0 1',
        width: 9,
        height: 9,
        pieces: ['k'],
        kingRoles: ['k'],
    });
    document.body.innerHTML = `
        <div class="catalogued-start-board-preview" data-variant="testshogiboardpreview"></div>`;
    const preview = document.querySelector<HTMLElement>('.catalogued-start-board-preview')!;
    const createChessground = jest.fn(() => ({ state: {} }) as Api) as unknown as typeof Chessground;
    const bindResize = jest.fn(() => () => undefined);
    const observe = jest.fn();
    const unobserve = jest.fn();
    let callback: IntersectionObserverCallback = () => undefined;
    window.IntersectionObserver = jest.fn(intersectionCallback => {
        callback = intersectionCallback;
        return { observe, unobserve } as unknown as IntersectionObserver;
    }) as unknown as typeof IntersectionObserver;

    mountCataloguedStartBoards('/static', createChessground, bindResize);
    expect(observe).toHaveBeenCalledWith(preview);
    expect(createChessground).not.toHaveBeenCalled();

    callback([{ isIntersecting: true, target: preview } as IntersectionObserverEntry], {} as IntersectionObserver);

    expect(unobserve).toHaveBeenCalledWith(preview);
    expect(createChessground).toHaveBeenCalledTimes(1);
});

test('uploaded board and piece CSS are loaded for starting-position previews', () => {
    register({
        name: 'testcustomboardpreview',
        displayName: 'Test Custom Board Preview',
        ini: '[testcustomboardpreview:chess]',
        baseVariant: 'chess',
        startFen: '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k'],
        kingRoles: ['k'],
        hasBoard: true,
        boardRevision: 'board-r1',
        hasPieceSet: true,
        pieceSetRevision: 'piece-r2',
    });
    document.body.innerHTML = `
        <a class="catalogued-start-board-preview" data-variant="testcustomboardpreview"></a>`;
    const createChessground = jest.fn(() => ({ state: {} }) as Api) as unknown as typeof Chessground;
    const bindResize = jest.fn(() => () => undefined);

    mountCataloguedStartBoards('/static', createChessground, bindResize);

    const preview = document.querySelector<HTMLElement>('.catalogued-start-board-preview');
    expect(preview?.classList.contains('piece-style-catalogued-testcustomboardpreview-custom')).toBe(true);
    expect(preview?.dataset.boardVariant).toBe('testcustomboardpreview');
    expect(preview?.querySelector('.cg-wrap')?.getAttribute('aria-hidden')).toBe('true');
    expect(document.getElementById('board-set-catalogued-testcustomboardpreview')?.getAttribute('href')).toBe(
        '/api/catalogued-variants/testcustomboardpreview/board-css.css?v=board-r1',
    );
    expect(
        document.getElementById('piece-set-catalogued-testcustomboardpreview-custom-piece-r2')?.getAttribute('href'),
    ).toBe('/api/catalogued-variants/testcustomboardpreview/piece-css.css?v=piece-r2');
});
