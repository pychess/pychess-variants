import { afterEach, expect, test } from '@jest/globals';

import { boardSettings } from '../client/boardSettings';
import {
    CataloguedVariantClientDocument,
    cataloguedCompatiblePieceFamily,
    PIECE_FAMILIES,
    registerCataloguedVariant,
    unregisterCataloguedVariant,
    VARIANTS,
} from '../client/variants';

const variantNames = [
    'testbuiltindefault',
    'testlettersdefault',
    'testcustomdefault',
    'testcustompiecelettersdefault',
    'testpromotedcustomdefault',
    'testpromotedkingroles',
    'testfsfnightriderletters',
    'testfsfcentaurletters',
    'testfsfalmostcapa',
    'testfsfgrandcapa',
    'testfsfpieceoptioncapa',
    'testfsfthreekingsstandard',
    'testreformedcourieroverride',
    'testcentauroverride',
    'testmakrukwall',
    'testdecimalshogiimagelayer',
    'testamazonspieces',
    'testopulentpieces',
];

function register(meta: CataloguedVariantClientDocument) {
    registerCataloguedVariant(meta);
    return VARIANTS[meta.name];
}

afterEach(() => {
    variantNames.forEach(name => {
        unregisterCataloguedVariant(name);
        delete localStorage[`${name}-piece`];
        delete boardSettings.settings[`${name}-piece`];
    });
});

test('catalogued variants with a compatible built-in piece family default to that family', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testbuiltindefault',
        displayName: 'Test Built-in Default',
        tooltip: 'Catalogued variant',
        ini: '[testbuiltindefault:chess]',
        startFen: '8/8/8/8/8/8/8/K6k w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'p'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(variant.pieceFamily).toBe(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true }));
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe(PIECE_FAMILIES[variant.pieceFamily].pieceCSS[0]);
});

test('catalogued wall pieces are marked when both board and piece families are built in', () => {
    const variant = register({
        name: 'testmakrukwall',
        displayName: 'Test Makruk Wall',
        tooltip: 'Catalogued variant',
        ini: '[testmakrukwall:makruk]',
        baseVariant: 'makruk',
        startFen: '8/8/6**/**4*m/M*4**/**6/8/8 w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['m', 's', 'n'],
        kingRoles: [],
        promotionType: 'regular',
        promotionRoles: ['s'],
        promotionOrder: ['n'],
    });
    const board = document.createElement('div');
    const wrap = document.createElement('div');
    board.className = `${variant.boardFamily} ${variant.pieceFamily}`;
    board.appendChild(wrap);
    document.body.appendChild(board);

    expect(variant.boardFamily).toBe('makruk8x8');
    expect(variant.pieceFamily).toBe('makruk');

    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('catalogued-piece-variant')).toBe(true);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(true);

    boardSettings.updateScopedPieceStyle(VARIANTS.makruk, wrap);
    expect(board.classList.contains('catalogued-piece-variant')).toBe(false);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);
});

test('catalogued variants without a compatible built-in piece family default to letters', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testlettersdefault',
        displayName: 'Test Letters Default',
        tooltip: 'Catalogued variant',
        ini: '[testlettersdefault:chess]',
        startFen: '8/8/8/8/8/8/8/K6k w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'x'],
        kingRoles: ['k'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBeUndefined();
    expect(variant.pieceFamily).toBe(`catalogued-${variant.name}`);
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('letters');
});

test('catalogued variants with a custom piece set still default to that custom set', () => {
    const variant = register({
        name: 'testcustomdefault',
        displayName: 'Test Custom Default',
        tooltip: 'Catalogued variant',
        ini: '[testcustomdefault:chess]',
        startFen: '8/8/8/8/8/8/8/K6k w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'p'],
        kingRoles: ['k'],
        hasPieceSet: true,
        pieceSetRevision: 'r1',
    });

    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('custom-r1');

    const board = document.createElement('div');
    const wrap = document.createElement('div');
    board.className = `${variant.boardFamily} ${variant.pieceFamily}`;
    board.appendChild(wrap);
    document.body.appendChild(board);

    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('catalogued-piece-variant')).toBe(true);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);

    board.remove();
});

test('catalogued variants can explicitly use the shared courier piece family', () => {
    const variant = register({
        name: 'testreformedcourieroverride',
        displayName: 'Test Reformed Courier Override',
        tooltip: 'Catalogued variant',
        ini: `[testreformedcourieroverride]
king = k
pawn = p
rook = r
knight = n
bishop = b
queen = q
centaur = d
customPiece1 = a:AF
customPiece2 = m:DK`,
        startFen: 'rnabmqkdbanr/pppppppppppp/12/12/12/12/PPPPPPPPPPPP/RNABMQKDBANR w KQkq - 0 1',
        width: 12,
        height: 8,
        pieces: ['k', 'p', 'r', 'n', 'b', 'q', 'd', 'a', 'm'],
        kingRoles: ['k'],
        pieceFamilyOverride: 'courier',
    });

    expect(variant.pieceFamily).toBe('courier');
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('courier');
});

test('catalogued Opulent defaults to its complete Alfaerie piece set and keeps letter pieces available', () => {
    const variant = register({
        name: 'testopulentpieces',
        displayName: 'Opulent Chess',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'opulent',
        ini: '',
        baseVariant: 'grand',
        startFen: 'rw6wr/clbnqknbla/pppppppppp/10/10/10/10/PPPPPPPPPP/CLBNQKNBLA/RW6WR w - - 0 1',
        width: 10,
        height: 10,
        pieces: ['p', 'r', 'n', 'b', 'q', 'k', 'a', 'c', 'w', 'l'],
        kingRoles: ['k'],
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'a', 'c', 'n', 'w', 'l'],
        pieceFamilyOverride: 'opulent',
    });

    expect(variant.pieceFamily).toBe('opulent');
    expect(PIECE_FAMILIES.opulent.pieceCSS).toEqual(['opulent', 'disguised']);
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('opulent');

    boardSettings.getSettings('PieceStyle', variant.pieceFamily, '', variant).value = 1;
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('disguised');
});

test('catalogued Amazons offers classic, arrow, and disguised piece styles with correct wall handling', () => {
    const variant = register({
        name: 'testamazonspieces',
        displayName: 'Test Amazons Pieces',
        tooltip: 'Catalogued variant',
        ini: '[testamazonspieces:amazons]',
        startFen: '3q2q3/10/10/q8q/10/10/Q8Q/10/10/Q*4Q3 w - - 0 1',
        width: 10,
        height: 10,
        pieces: ['q'],
        kingRoles: [],
        pieceFamilyOverride: 'amazons',
        rulesArrowing: true,
    });
    const board = document.createElement('div');
    const wrap = document.createElement('div');
    board.className = `${variant.boardFamily} ${variant.pieceFamily}`;
    board.appendChild(wrap);
    document.body.appendChild(board);

    expect(variant.pieceFamily).toBe('amazons');
    expect(PIECE_FAMILIES.amazons.pieceCSS).toEqual(['classic', 'arrow', 'disguised']);
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('classic');

    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('catalogued-piece-wall-artwork')).toBe(true);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);

    boardSettings.getSettings('PieceStyle', variant.pieceFamily, '', variant).value = 1;
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('arrow');
    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('piece-style-amazons-arrow')).toBe(true);
    expect(board.classList.contains('catalogued-piece-wall-artwork')).toBe(true);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);

    boardSettings.getSettings('PieceStyle', variant.pieceFamily, '', variant).value = 2;
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('disguised');
    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('piece-style-amazons-disguised')).toBe(true);
    expect(board.classList.contains('catalogued-piece-wall-artwork')).toBe(false);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);

    board.remove();
});

test('catalogued variants can explicitly use Centaur pieces with Archbishop and Chancellor', () => {
    const variant = register({
        name: 'testcentauroverride',
        displayName: 'Test Centaur Override',
        tooltip: 'Catalogued variant',
        ini: `[testcentauroverride:chess]
archbishop = a
chancellor = c
centaur = g`,
        startFen: 'rnabqkcg/pppppppp/8/8/8/8/PPPPPPPP/RNABQKCG w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 'a', 'c', 'g'],
        kingRoles: ['k'],
        pieceFamilyOverride: 'centaur',
    });

    expect(variant.pieceFamily).toBe('centaur');
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('centaur0');
});

test('catalogued variants using an image-layer piece style do not get a base-image fallback', () => {
    const variant = register({
        name: 'testdecimalshogiimagelayer',
        displayName: 'Test Decimal Shogi Image Layer',
        tooltip: 'Catalogued variant',
        ini: '[testdecimalshogiimagelayer:shogi]',
        baseVariant: 'shogi',
        startFen: '10/10/10/10/10/10/10/10/10/K8k w - - 0 1',
        width: 10,
        height: 10,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 'l', 's', 'g'],
        kingRoles: ['k'],
        pieceFamilyOverride: 'decimalshogi',
    });
    const board = document.createElement('div');
    const wrap = document.createElement('div');
    board.className = `${variant.boardFamily} ${variant.pieceFamily}`;
    board.appendChild(wrap);
    document.body.appendChild(board);

    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('shogik');

    boardSettings.updateScopedPieceStyle(variant, wrap);
    expect(board.classList.contains('catalogued-piece-variant')).toBe(true);
    expect(board.classList.contains('catalogued-missing-piece-fallback')).toBe(false);

    board.remove();
});

test('catalogued variants needing custom piece roles default to letters instead of matching by role letter only', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testcustompiecelettersdefault',
        displayName: 'Test Custom Piece Letters Default',
        tooltip: 'Catalogued variant',
        ini: `[testcustompiecelettersdefault]
pawn = p
knight = n
customPiece1 = e:FA
rook = r
customPiece2 = g:BWD
king = k
promotionPieceTypes = gren
doubleStep = false
castling = false
stalemateValue = loss`,
        startFen: 'rnegkenr/pppppppp/8/8/8/8/PPPPPPPP/RNEGKENR w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'r', 'n', 'p', 'e', 'g'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['g', 'r', 'e', 'n'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBeUndefined();
    expect(variant.pieceFamily).toBe(`catalogued-${variant.name}`);
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('letters');
});

test('catalogued variants with custom promoted target pieces default to letters', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testpromotedcustomdefault',
        displayName: 'Test Promoted Custom Default',
        tooltip: 'Catalogued variant',
        ini: `[testpromotedcustomdefault]
king = k
pawn = p
customPiece1 = z:WAD
promotedPieceType = p:z`,
        startFen: '8/8/8/8/8/8/P7/K6k w - - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'p'],
        kingRoles: ['k'],
        promotionType: 'shogi',
        promotionRoles: ['p'],
        promotionOrder: ['+', ''],
        showPromoted: true,
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBeUndefined();
    expect(variant.pieceFamily).toBe(`catalogued-${variant.name}`);
    expect(boardSettings.pieceCSS(variant.pieceFamily, variant)).toBe('letters');
});

test('catalogued variants mark shogi-style promoted kings as king roles', () => {
    const variant = register({
        name: 'testpromotedkingroles',
        displayName: 'Test Promoted King Roles',
        tooltip: 'Catalogued variant',
        ini: `[testpromotedkingroles:chess]
extinctionValue = loss
extinctionPieceTypes = jk
extinctionPseudoRoyal = true
mandatoryPiecePromotion = true
promotedPieceType = n:y b:y p:z r:o q:a k:j
promotionPieceTypes = -`,
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p'],
        kingRoles: ['k'],
        promotionType: 'shogi',
        promotionRoles: ['n', 'b', 'p', 'r', 'q', 'k'],
        promotionOrder: ['+', ''],
        showPromoted: true,
    });

    expect(variant.kingRoles).toContain('k-piece');
    expect(variant.kingRoles).toContain('pk-piece');
});

test('FSF built-in Nightrider identity does not match standard knight letters', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfnightriderletters',
        displayName: 'Test FSF Nightrider Letters',
        tooltip: 'Catalogued variant',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'nightrider',
        baseVariant: 'chess',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'n'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBeUndefined();
    expect(variant.pieceFamily).toBe(`catalogued-${variant.name}`);
});

test('FSF built-in Centaur identity does not match Capablanca chancellor letters', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfcentaurletters',
        displayName: 'Test FSF Centaur Letters',
        tooltip: 'Catalogued variant',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'centaur',
        baseVariant: 'capablanca',
        startFen: 'rncbqkbnr/ppppppppp/9/9/9/9/PPPPPPPPP/RNCBQKBNR w KQkq - 0 1',
        width: 9,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 'c'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['c', 'q', 'r', 'b', 'n'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBeUndefined();
    expect(variant.pieceFamily).toBe(`catalogued-${variant.name}`);
});

test('FSF built-in Almost keeps using Capablanca pieces for Chancellor', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfalmostcapa',
        displayName: 'Test FSF Almost Capa',
        tooltip: 'Catalogued variant',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'almost',
        baseVariant: 'chess',
        startFen: 'rnbckbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBCKBNR w KQkq - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'r', 'b', 'n', 'p', 'c'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['c', 'r', 'b', 'n'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBe('capa');
    expect(variant.pieceFamily).toBe('capa');
});

test('FSF-inherited Grand keeps using Capablanca pieces for Archbishop and Chancellor', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfgrandcapa',
        displayName: 'Test FSF Grand Capa',
        tooltip: 'Catalogued variant',
        ini: '[testfsfgrandcapa:grand]',
        baseVariant: 'grand',
        startFen: 'r8r/1nbqkcabn1/pppppppppp/10/10/10/10/PPPPPPPPPP/1NBQKCABN1/R8R w - - 0 1',
        width: 10,
        height: 10,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 'a', 'c'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'n', 'a', 'c'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBe('capa');
    expect(variant.pieceFamily).toBe('capa');
});

test('FSF built-in piece option names can opt into compatible piece families', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfpieceoptioncapa',
        displayName: 'Test FSF Piece Option Capa',
        tooltip: 'Catalogued variant',
        ini: `[testfsfpieceoptioncapa:chess]
archbishop = a
chancellor = c`,
        baseVariant: 'chess',
        startFen: 'rnabqkbcnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNABQKBCNR w KQkq - 0 1',
        width: 10,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p', 'a', 'c'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'n', 'a', 'c'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBe('capa');
    expect(variant.pieceFamily).toBe('capa');
});

test('catalogued piece family override bypasses conservative identity detection', () => {
    const meta: CataloguedVariantClientDocument = {
        name: 'testfsfthreekingsstandard',
        displayName: 'Test FSF Three Kings Standard',
        tooltip: 'Catalogued variant',
        ini: '',
        source: 'fairy-stockfish-builtin',
        fsfBuiltinVariant: 'threekings',
        pieceFamilyOverride: 'standard',
        baseVariant: 'chess',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        width: 8,
        height: 8,
        pieces: ['k', 'q', 'r', 'b', 'n', 'p'],
        kingRoles: ['k'],
        promotionType: 'regular',
        promotionRoles: ['p'],
        promotionOrder: ['q', 'r', 'b', 'n'],
    };
    const variant = register(meta);

    expect(cataloguedCompatiblePieceFamily(meta, { ignoreCustomPieceSet: true })).toBe('standard');
    expect(variant.pieceFamily).toBe('standard');
});
