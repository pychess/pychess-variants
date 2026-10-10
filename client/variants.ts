import { h, InsertHook, VNode } from 'snabbdom';

import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { registerCataloguedPremove, unregisterCataloguedPremove } from './cataloguedPremove';

import {
    BoardMarkType,
    ColorName,
    CountingType,
    MaterialPointType,
    PieceSoundType,
    PromotionSuffix,
    PromotionType,
    TimeControlType,
    uci2LastMove,
} from './chess';
import { _, gameCategoryLabel } from './i18n';
import { calculateDiff, Equivalence, MaterialDiff } from './material';

export interface BoardFamily {
    readonly dimensions: cg.BoardDimensions;
    readonly cg: string;
    readonly boardCSS: string[];
}

export interface PieceFamily {
    readonly pieceCSS: string[];
    // These styles draw at least one piece on ::before so its artwork can rotate
    // without changing the piece element's chessground-owned transform. Applying
    // the missing-piece background to the element would show both images at once.
    readonly imageLayerCSS?: string[];
    // Styles that provide their own artwork for the role used by wall squares.
    // Catalogued variants otherwise receive the shared brick fallback.
    readonly wallCSS?: string[];
}

export type HiddenInfoMode = 'none' | 'fog' | 'covered_pieces';

export const BOARD_FAMILIES: Record<string, BoardFamily> = {
    ataxx7x7: { dimensions: { width: 7, height: 7 }, cg: 'cg-448', boardCSS: ['ataxx.svg', 'ataxx.png'] },
    standard8x8: {
        dimensions: { width: 8, height: 8 },
        cg: 'cg-512',
        boardCSS: [
            '8x8brown.svg',
            '8x8blue.svg',
            '8x8green.svg',
            '8x8maple.jpg',
            '8x8olive.jpg',
            '8x8santa.png',
            '8x8wood2.jpg',
            '8x8wood4.jpg',
            '8x8ic.svg',
            '8x8purple.svg',
            '8x8dobutsu.svg',
        ],
    },
    standard9x9: {
        dimensions: { width: 9, height: 9 },
        cg: 'cg-540',
        boardCSS: ['9x9mansindam.svg', '9x9brown.svg', '9x9blue.svg', '9x9green.svg', '9x9maple.jpg', '9x9olive.jpg'],
    },
    standard10x8: {
        dimensions: { width: 10, height: 8 },
        cg: 'cg-640',
        boardCSS: ['10x8brown.svg', '10x8blue.svg', '10x8green.svg', '10x8maple.jpg', '10x8olive.jpg'],
    },
    standard10x10: {
        dimensions: { width: 10, height: 10 },
        cg: 'cg-640-640',
        boardCSS: ['10x10brown.svg', '10x10blue.svg', '10x10green.svg', '10x10maple.jpg', '10x10olive.jpg'],
    },
    grand10x10: {
        dimensions: { width: 10, height: 10 },
        cg: 'cg-640-640',
        boardCSS: [
            'Grandboard.svg',
            '10x10brown.svg',
            '10x10blue.svg',
            '10x10green.svg',
            '10x10maple.jpg',
            '10x10mapleGrand.png',
        ],
    },
    makruk8x8: {
        dimensions: { width: 8, height: 8 },
        cg: 'cg-512',
        boardCSS: ['makruk2.svg', 'makruk.svg', 'makrukWhite.svg', 'makruk.jpg', 'makrukWood.png'],
    },
    sittuyin8x8: {
        dimensions: { width: 8, height: 8 },
        cg: 'cg-512',
        boardCSS: [
            'sittuyin2.svg',
            'sittuyin.svg',
            'sittuyin.jpg',
            'sittuyingreen.svg',
            'sittuyinGrainBrown.svg',
            'sittuyinWood.png',
        ],
    },
    shogi9x9: {
        dimensions: { width: 9, height: 9 },
        cg: 'cg-576',
        boardCSS: [
            'shogi.svg',
            'Shogiban1.png',
            'Shogiban2.png',
            'shogic.svg',
            'ShogiMaple.png',
            'ShogiGrayTexture.png',
            'ShogiSpace1.svg',
            'dobutsu.png',
            'ShogiOak.png',
            'CreepyOak.png',
        ],
    },
    shogi7x7: {
        dimensions: { width: 7, height: 7 },
        cg: 'cg-448-516',
        boardCSS: ['ToriPlain.svg', 'ToriWood.svg', 'ToriDaySky.svg', 'ToriNightSky.svg'],
    },
    shogi7x9: {
        dimensions: { width: 7, height: 9 },
        cg: 'cg-448-664',
        boardCSS: ['YariPlain.svg'],
    },
    shogi6x6: {
        dimensions: { width: 6, height: 6 },
        cg: 'cg-312',
        boardCSS: ['judkins.svg'],
    },
    shogi5x5: {
        dimensions: { width: 5, height: 5 },
        cg: 'cg-260',
        boardCSS: [
            'minishogi.svg',
            'MiniboardWood1.png',
            'MiniboardWood2.png',
            'MinishogiDobutsu.svg',
            'MinishogiDobutsu2.svg',
        ],
    },
    shogi5x6: {
        dimensions: { width: 5, height: 6 },
        cg: 'cg-260-360',
        boardCSS: ['gorogoro.svg', 'gorogoroboard.svg', 'gorogoro2.svg', 'GorogoroWood.png'],
    },
    shogi3x4: { dimensions: { width: 3, height: 4 }, cg: 'cg-156', boardCSS: ['dobutsuboard.svg', 'dobutsu3x4.svg'] },
    xiangqi9x10: {
        dimensions: { width: 9, height: 10 },
        cg: 'cg-576-640',
        boardCSS: [
            'xiangqi.svg',
            'xiangqic.svg',
            'xiangqiCTexture.png',
            'xiangqiPaper.png',
            'xiangqiWood.png',
            'xiangqiDark.svg',
            'xiangqiWikimedia.svg',
            'xiangqiLightWood.png',
            'xiangqiSand.svg',
        ],
    },
    xiangqi7x7: {
        dimensions: { width: 7, height: 7 },
        cg: 'cg-448',
        boardCSS: ['minixiangqi.svg', 'minixiangqiw.png', 'minixqlg.svg'],
    },
    janggi9x10: {
        dimensions: { width: 9, height: 10 },
        cg: 'cg-janggi',
        boardCSS: [
            'JanggiBrown.svg',
            'JanggiPaper.png',
            'JanggiWood.png',
            'JanggiDark.svg',
            'JanggiWoodDark.svg',
            'JanggiStone.svg',
        ],
    },
    shogun8x8: {
        dimensions: { width: 8, height: 8 },
        cg: 'cg-512',
        boardCSS: [
            'ShogunRed.svg',
            'ShogunRedShadow.svg',
            'ShogunMaple.png',
            'ShogunMaple2.png',
            'ShogunBlue.svg',
            'ShogunBlueShadow.svg',
            '8x8brown.svg',
            '8x8maple.jpg',
        ],
    },
    chak9x9: {
        dimensions: { width: 9, height: 9 },
        cg: 'cg-540',
        boardCSS: ['StandardChakBoard.svg', 'ColoredChakBoard.svg', 'ChakArt.jpg'],
    },
    chennis7x7: {
        dimensions: { width: 7, height: 7 },
        cg: 'cg-448',
        boardCSS: ['WimbledonBoard.svg', 'FrenchOpenBoard.svg', 'USOpenBoard.svg'],
    },
    xiangfu9x9: {
        dimensions: { width: 9, height: 9 },
        cg: 'cg-540',
        boardCSS: [
            'xiangfu-chess-board.svg',
            'xiangfu-chess-allblue.svg',
            'xiangfu-chess-blue.svg',
            'xiangfu-chess-island.svg',
            'xiangfu-blue-nobends.svg',
            'xiangfu-no-cross.svg',
            'xiangfu.svg',
            'xiangfu-guidelines.svg',
        ],
    },
    borderlands9x10: {
        dimensions: { width: 9, height: 10 },
        cg: 'cg-borderlands',
        boardCSS: ['borderlands-cobalt.svg'],
    },
};

export const PIECE_FAMILIES: Record<string, PieceFamily> = {
    amazons: { pieceCSS: ['classic', 'arrow', 'disguised'], wallCSS: ['classic', 'arrow'] },
    paradigm: { pieceCSS: ["paradigm0", "paradigm1", "paradigm2", "paradigm3", "disguised"] },
    ataxx: { pieceCSS: ['disguised', 'virus', 'zombie', 'cat-dog'] },
    standard: {
        pieceCSS: [
            'standard',
            'green',
            'alpha',
            'chess_kaneo',
            'santa',
            'maestro',
            'dubrovny',
            'atopdown',
            'luffy',
            'firi',
            'disguised',
        ],
    },
    capa: { pieceCSS: ['capa0', 'capa1', 'capa2', 'capa3', 'capa4', 'capa5', 'disguised'] },
    centaur: { pieceCSS: ['centaur0', 'centaur1', 'disguised'] },
    dragon: { pieceCSS: ['dragon1', 'dragon0', 'dragon2', 'disguised'] },
    seirawan: { pieceCSS: ['seir1', 'seir0', 'seir2', 'seir3', 'seir4', 'seir5', 'disguised'] },
    makruk: { pieceCSS: ['makrukwb', 'makrukwr', 'makruk', 'makruks', 'makruki', 'makrukc', 'disguised'] },
    sittuyin: {
        pieceCSS: ['sittuyins', 'sittuyinkagr', 'sittuyinkabr', 'sittuyinm', 'sittuyini', 'sittuyincb', 'disguised'],
    },
    asean: { pieceCSS: ['aseani', 'aseanm', 'aseanc', 'aseans', 'aseancb', 'disguised'] },
    shogi: {
        pieceCSS: [
            'shogik',
            'shogi',
            'shogiw',
            'shogip',
            'shogim',
            'shogip3d',
            'shogikw3d',
            'shogid',
            'shogiim',
            'shogio',
            'shogibw',
            'shogictbnw',
            'portk',
            'porti',
            'cz',
            'firi',
            'disguised',
        ],
        imageLayerCSS: ['shogik', 'shogi', 'cz'],
    },
    kyoto: {
        pieceCSS: ['kyoto', 'kyotok', 'kyotoks', 'kyotoi', 'kyotod', 'disguised'],
        imageLayerCSS: ['kyoto', 'kyotok', 'kyotoks'],
    },
    dobutsu: { pieceCSS: ['dobutsu', 'disguised'] },
    tori: {
        pieceCSS: ['torii', 'torik', 'torim', 'porti', 'cz', 'disguised'],
        imageLayerCSS: ['cz'],
    },
    cannonshogi: {
        pieceCSS: ['ctp3d', 'ctim', 'bnw', 'cz', 'czalt', 'firi', 'disguised'],
        imageLayerCSS: ['cz', 'czalt'],
    },
    xiangqi: {
        pieceCSS: [
            'lishu',
            'xiangqi2di',
            'xiangqi',
            'xiangqict3',
            'xiangqihnz',
            'xiangqict2',
            'lishuw',
            'xiangqict2w',
            'xiangqiwikim',
            'xiangqiKa',
            'xiangqittxqhnz',
            'xiangqittxqintl',
            'xiangqi2d',
            'xiangqihnzw',
            'eventhanzi',
            'eventhanziguided',
            'eventintl',
            'euro',
            'disguised',
        ],
    },
    janggi: {
        pieceCSS: [
            'janggihb',
            'janggihg',
            'janggiikak',
            'janggiikaw',
            'janggikak',
            'janggikaw',
            'janggiib',
            'janggiig',
            'disguised',
        ],
    },
    shatranj: { pieceCSS: ['shatranj0', 'shatranj1', 'disguised'] },
    courier: { pieceCSS: ['courier', 'disguised'] },
    shako: { pieceCSS: ['shako0', 'shako1', 'shako2', 'disguised'] },
    pemba: { pieceCSS: ['alfaerie', 'disguised'] },
    shogun: { pieceCSS: ['shogun6', 'shogun0', 'shogun1', 'shogun2', 'shogun3', 'shogun4', 'shogun5', 'disguised'] },
    orda: { pieceCSS: ['orda0', 'orda1', 'disguised'] },
    khans: { pieceCSS: ['khans0', 'khans1', 'disguised'] },
    synochess: {
        pieceCSS: ['synochess0', 'synochess1', 'synochess2', 'synochess3', 'synochess4', 'synochess5', 'disguised'],
    },
    hoppel: { pieceCSS: ['hoppel0', 'hoppel1', 'hoppel2', 'disguised'] },
    shinobi: { pieceCSS: ['shinobi0', 'shinobi1', 'disguised'] },
    empire: { pieceCSS: ['empire0', 'empire1', 'disguised'] },
    ordamirror: { pieceCSS: ['ordamirror0', 'ordamirror1', 'disguised'] },
    chak: { pieceCSS: ['chak0', 'ronin', 'chak1', 'chak2', 'disguised'] },
    chennis: { pieceCSS: ['chennis0', 'chennis1', 'chennis2', 'chennis3', 'chennis4', 'disguised'] },
    spartan: { pieceCSS: ['spartan0', 'spartan1', 'disguised'] },
    mansindam: { pieceCSS: ['mansindam2', 'mansindam1', 'mansindam3', 'mansindam4', 'mansindam5', 'disguised'] },
    xiangfu: { pieceCSS: ['eventintl', 'eventhanzi', 'eventhanziguided', 'disguised'] },
    borderlands: { pieceCSS: ['borderlands', 'disguised'] },
    yokai: { pieceCSS: ['yokai', 'disguised'] },
    perfect: { pieceCSS: ['perfect0', 'disguised'] },
    decimalshogi: {
        pieceCSS: ['shogik', 'disguised'],
        imageLayerCSS: ['shogik'],
    },
    cwda: { pieceCSS: ['cwda', 'couchtomato'] },
    letter: { pieceCSS: ['disguised'] },
};

// Keep canRated=true FENs in sync with server/rated_start.py.
export interface AlternateStart {
    readonly fen: string;
    readonly canRated: boolean;
}

type AlternateStartConfig = string | { readonly fen: string; readonly canRated?: boolean };

function alternateStarts(
    config: Record<string, AlternateStartConfig> | undefined,
): Record<string, AlternateStart> | undefined {
    if (config === undefined) return undefined;
    return Object.fromEntries(
        Object.entries(config).map(([name, start]) => [
            name,
            typeof start === 'string'
                ? { fen: start, canRated: false }
                : { fen: start.fen, canRated: start.canRated ?? false },
        ]),
    );
}

function normalizeStartFen(fen: string): string {
    return fen.trim().replace(/\s+/g, ' ');
}

export function canRateCustomStart(variant: Variant, fen: string): boolean {
    const normalizedFen = normalizeStartFen(fen);
    if (normalizedFen === '') return true;
    return Object.values(variant.alternateStart ?? {}).some(
        start => start.canRated && normalizeStartFen(start.fen) === normalizedFen,
    );
}

export function canRateStart(variant: Variant, fen: string): boolean {
    return variant.ratingEnabled && canRateCustomStart(variant, fen);
}

export interface Variant {
    readonly name: string;
    readonly _displayName: string;
    readonly _display960: string;
    readonly _displayName960?: string;
    readonly displayName: (chess960?: boolean) => string;
    readonly _tooltip: string;
    readonly tooltip: string;
    readonly chess960: boolean;
    readonly randomStart: boolean;
    readonly aiDisabled: boolean;
    readonly twoBoards: boolean;
    readonly ratingEnabled: boolean;
    readonly hiddenInfo: boolean;
    readonly hiddenInfoMode: HiddenInfoMode;
    readonly _icon: string;
    readonly _icon960: string;
    readonly icon: (chess960?: boolean) => string;
    readonly startFen: string;
    readonly boardFamily: keyof typeof BOARD_FAMILIES;
    readonly board: BoardFamily;
    readonly hasBoard: boolean;
    readonly boardRevision?: string;
    readonly notation: cg.Notation;
    readonly pieceFamily: keyof typeof PIECE_FAMILIES;
    readonly pieceCSSExclude: string[];
    readonly piece: PieceFamily;
    readonly colors: {
        readonly first: ColorName;
        readonly second: ColorName;
    };
    readonly pieceRow: Record<cg.Color, cg.Role[]>;
    readonly kingRoles: cg.Role[];
    readonly pocket?: {
        readonly roles: Record<cg.Color, cg.Role[]>;
        readonly captureToHand: boolean;
        readonly pieceNames?: Partial<Record<cg.Role, string>>;
    };
    readonly promotion: {
        readonly type: PromotionType;
        readonly order: PromotionSuffix[];
        readonly roles: cg.Role[];
        readonly strict?: {
            readonly isPromoted: (piece: cg.Piece, pos: cg.Pos) => boolean;
        };
        readonly autoPromoteable: boolean;
    };
    readonly rules: {
        readonly defaultTimeControl: TimeControlType;
        readonly enPassant: boolean;
        readonly gate: boolean;
        readonly duck: boolean;
        readonly arrowing: boolean;
        readonly pass: boolean;
        readonly setup: boolean;
        readonly noDrawOffer: boolean;
    };
    readonly material: {
        readonly showDiff: boolean;
        readonly initialDiff: MaterialDiff;
        readonly equivalences: Equivalence;
    };
    readonly ui: {
        readonly counting?: CountingType;
        readonly materialPoint?: MaterialPointType;
        readonly showPromoted: boolean;
        readonly pieceSound: PieceSoundType;
        readonly boardMark: BoardMarkType | '';
        readonly showCheckCounters: boolean;
    };
    readonly alternateStart?: Record<string, AlternateStart>;
    readonly cataloguedSource?: 'user' | 'fairy-stockfish-builtin';
    readonly nnueFingerprint?: string;
}

const pieceFamiliesWithMaterialDifferenceSupported = [
    'standard',
    'makruk',
    'sittuyin',
    'asean',
    'xiangqi',
    'janggi',
    'shatranj',
    'capa',
    'dragon',
    'seirawan',
    'shako',
    'hoppel',
    'orda',
    'khans',
    'synochess',
    'shinobi',
    'empire',
    'ordamirror',
    'chak',
    'spartan',
];

export function variant(config: VariantConfig): Variant {
    return {
        name: config.name,
        _displayName: config.displayName ?? config.name,
        _display960: config.display960 ?? '960',
        _displayName960: config.displayName960,
        displayName: function (chess960 = false) {
            if (chess960 && this._displayName960 !== undefined) return _(this._displayName960).toUpperCase();
            return _(this._displayName).toUpperCase() + (chess960 ? this._display960 : '');
        },
        _tooltip: config.tooltip,
        get tooltip() {
            return _(this._tooltip);
        },
        chess960: !!config.chess960,
        randomStart: !!config.randomStart,
        aiDisabled: !!config.aiDisabled,
        twoBoards: !!config.twoBoards,
        ratingEnabled: config.ratingEnabled ?? true,
        hiddenInfo: !!config.hiddenInfo,
        hiddenInfoMode: config.hiddenInfoMode ?? 'none',
        _icon: config.icon,
        _icon960: config.icon960 ?? config.icon,
        icon: function (chess960 = false) {
            return chess960 ? this._icon960 : this._icon;
        },
        startFen: config.startFen,
        boardFamily: config.boardFamily,
        board: BOARD_FAMILIES[config.boardFamily],
        hasBoard: !!config.hasBoard,
        boardRevision: config.boardRevision,
        pieceFamily: config.pieceFamily,
        pieceCSSExclude: config.pieceCSSExclude ?? [],
        notation: config.notation ?? cg.Notation.ALGEBRAIC,
        piece: PIECE_FAMILIES[config.pieceFamily],
        colors: config.colors ?? { first: 'White', second: 'Black' },
        pieceRow: Array.isArray(config.pieceRow)
            ? {
                  white: config.pieceRow.map(util.roleOf),
                  black: config.pieceRow.map(util.roleOf),
              }
            : {
                  white: config.pieceRow.white.map(util.roleOf),
                  black: config.pieceRow.black.map(util.roleOf),
              },
        kingRoles: (config.kingRoles ?? ['k']).map(util.roleOf),
        pocket: config.pocket
            ? {
                  roles: Array.isArray(config.pocket.roles)
                      ? {
                            white: config.pocket.roles.map(util.roleOf),
                            black: config.pocket.roles.map(util.roleOf),
                        }
                      : {
                            white: config.pocket.roles.white.map(util.roleOf),
                            black: config.pocket.roles.black.map(util.roleOf),
                        },
                  pieceNames: config.pocket?.pieceNames,
                  captureToHand: config.pocket.captureToHand,
              }
            : undefined,
        promotion: {
            type: config.promotion?.type ?? 'regular',
            order:
                config.promotion?.order ??
                (config.promotion?.type === 'shogi' ? ['+', ''] : ['q', 'c', 'e', 'a', 'h', 'n', 'r', 'b', 'p']),
            roles: (config.promotion?.roles ?? ['p']).map(util.roleOf),
            strict: config.promotion?.strict,
            get autoPromoteable() {
                return this.order.length > 2;
            },
        },
        rules: {
            defaultTimeControl: config.rules?.defaultTimeControl ?? 'incremental',
            enPassant: !!config.rules?.enPassant,
            gate: !!config.rules?.gate,
            duck: !!config.rules?.duck,
            arrowing: !!config.rules?.arrowing,
            pass: !!config.rules?.pass,
            setup: !!config.rules?.setup,
            noDrawOffer: !!config.rules?.noDrawOffer,
        },
        material: {
            // Jieqi needs material display for captured fake identities, so force it on.
            showDiff:
                config.name === 'jieqi' ||
                (!config.pocket?.captureToHand &&
                    !['ataxx', 'fogofwar', 'horde'].includes(config.name) &&
                    pieceFamiliesWithMaterialDifferenceSupported.includes(config.pieceFamily)),
            initialDiff: calculateDiff(
                config.startFen,
                BOARD_FAMILIES[config.boardFamily].dimensions,
                config.material?.equivalences ?? {},
                !!config.pocket?.captureToHand,
            ),
            equivalences: config.material?.equivalences ?? {},
        },
        ui: {
            counting: config.ui?.counting,
            materialPoint: config.ui?.materialPoint,
            showPromoted: config.ui?.showPromoted ?? false,
            pieceSound: config.ui?.pieceSound ?? 'regular',
            boardMark: config.ui?.boardMark ?? '',
            showCheckCounters: config.ui?.showCheckCounters ?? false,
        },
        alternateStart: alternateStarts(config.alternateStart),
        cataloguedSource: config.cataloguedSource,
        nnueFingerprint: config.nnueFingerprint,
    };
}

interface VariantConfig {
    // Name as defined in Fairy-Stockfish
    name: string;
    // Display name for use on the website (default: same as name)
    displayName?: string;
    // Display name postfix for variants having randomized start positions (default: '960')
    display960?: string;
    // Full display name override for randomized starts (default: base display name + display960)
    displayName960?: string;
    // Tooltip displayed when variant name is hovered
    tooltip: string;
    // Start FEN for use in some client-side calculations
    startFen: string;
    // Whether it is possible to play a randomized starting position (default: false)
    chess960?: boolean;
    // Community variants can always randomize new games without exposing a second variant key.
    randomStart?: boolean;
    // Whether Fairy-Stockfish AI is temporarily disabled for this catalogued variant
    aiDisabled?: boolean;
    // Identity metadata used to gate automatic NNUE for user-defined variants.
    cataloguedSource?: 'user' | 'fairy-stockfish-builtin';
    nnueFingerprint?: string;
    // Pocket pieces are added from an external source, usually from a second board (e.g., bughouse)
    twoBoards?: boolean;
    // Whether games contribute to user ratings and site leaderboards (default: true)
    ratingEnabled?: boolean;
    // Whether some information must be hidden from one or more viewers
    hiddenInfo?: boolean;
    // Representation family for hidden-information handling
    hiddenInfoMode?: HiddenInfoMode;
    // Icon letter in the site's font
    icon: string;
    // Icon of the 960 version (default: same as icon)
    icon960?: string;
    // Board appearance
    boardFamily: keyof typeof BOARD_FAMILIES;
    // Custom uploaded board SVG attached to a catalogued variant
    hasBoard?: boolean;
    boardRevision?: string;
    // Chessground coord/move notation (default: cg.Notation.ALGEBRAIC)
    notation?: cg.Notation;
    // Piece appearance
    pieceFamily: keyof typeof PIECE_FAMILIES;
    // Piece CSS files from the family that cannot render this variant
    pieceCSSExclude?: string[];
    // Color names of each side for accurate color representation
    colors?: {
        // (default: White)
        first: ColorName;
        // (default: Black)
        second: ColorName;
    };
    // Pieces on the editor's piece row
    // Use the record version if the pieces of each side are different
    pieceRow: cg.Letter[] | Record<cg.Color, cg.Letter[]>;
    // Pieces considered king for check marking (default: ['k'])
    kingRoles?: cg.Letter[];
    pocket?: {
        // Pieces in the pocket
        // Use the record version if the pieces of each side are different
        roles: cg.Letter[] | Record<cg.Color, cg.Letter[]>;
        // Translatable names of the pieces in the pocket (used for bug chat tooltip)
        pieceNames?: Partial<Record<cg.Role, string>>;
        // Whether captured pieces go to the pocket (Fairy's terminology)
        captureToHand: boolean;
    };
    promotion?: {
        // Promotion style
        // regular: (default) Pawns promote to one or more pieces (like chess)
        // shogi: Multiple pieces promote to another piece corresponding to it (like shogi)
        type: PromotionType;
        // Order of promotion choices to display, top choice will be chosen for auto-promote
        // (default: ["q", "c", "e", "a", "h", "n", "r", "b", "p"] for regular)
        // (default: ["+", ""] for shogi)
        order?: PromotionSuffix[];
        // Pieces that can promote (default: ['p'])
        roles?: cg.Letter[];
        // Whether a piece's promotion state strictly depends on its square (default: undefined)
        strict?: {
            // Returns true if and only if the given piece would be promoted on the given square
            isPromoted: (piece: cg.Piece, pos: cg.Pos) => boolean;
        };
    };
    // Miscellaneous rules useful for client-side processing
    // (default: false)
    rules?: {
        // Default time control (default: incremental)
        defaultTimeControl?: TimeControlType;
        // Chess's en passant
        enPassant?: boolean;
        // S-Chess gating
        gate?: boolean;
        // Duck Chess moving
        duck?: boolean;
        // Amazons-style arrow placement after moving a piece
        arrowing?: boolean;
        // Passing without moving a piece on board
        pass?: boolean;
        // Setup phase
        setup?: boolean;
        // Draw offer not allowed
        noDrawOffer?: boolean;
    };
    // Material equivalences for material diff calculation
    // ex. { 'pl-piece': 'r-piece' } means the "+L" piece is treated as the "R" piece for material diff
    material?: {
        equivalences?: Equivalence;
    };
    // UI display info
    ui?: {
        // SEA variants' counting (default: undefined)
        counting?: CountingType;
        // Material point (default: undefined)
        materialPoint?: MaterialPointType;
        // Promoted pieces need to be represented in the FEN even if it's not a drop variant (default: false)
        showPromoted?: boolean;
        // Sound of the piece moving (default: regular)
        pieceSound?: PieceSoundType;
        // Board marking for special squares (default: '')
        boardMark?: BoardMarkType;
        // Render the remaining check numbers on King pieces
        showCheckCounters?: boolean;
    };
    // Alternate starting positions, including handicaps. Plain FEN strings default to canRated=false.
    alternateStart?: Record<string, AlternateStartConfig>;
}

const CWDA_DEFAULT_FEN = 'dwackawd/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const CWDA_ARMY_BY_BACK_RANK = new Map<string, string>([
    ['rnbqkbnr', 'fide'],
    ['dwackawd', 'clobberers'],
    ['gihokhig', 'knights'],
    ['smfekfms', 'rookies'],
]);

const CWDA_PROFILE_BY_ARMIES = new Map<string, string>([
    ['dwackawd|rnbqkbnr', 'cwda-fide-clobberers'],
    ['gihokhig|rnbqkbnr', 'cwda-fide-knights'],
    ['rnbqkbnr|smfekfms', 'cwda-fide-rookies'],
    ['dwackawd', 'cwda-clobberers'],
    ['dwackawd|gihokhig', 'cwda-clobberers-knights'],
    ['dwackawd|smfekfms', 'cwda-clobberers-rookies'],
    ['gihokhig', 'cwda-knights'],
    ['gihokhig|smfekfms', 'cwda-knights-rookies'],
    ['smfekfms', 'cwda-rookies'],
]);

export function cwdaEngineVariant(initialFen: string): string {
    if (!initialFen) return 'cwda-fide-clobberers';
    const ranks = initialFen.trim().split(/\s+/)[0]?.split('/') ?? [];
    const armies = [ranks[0]?.toLowerCase(), ranks[ranks.length - 1]?.toLowerCase()]
        .filter((rank): rank is string => !!rank)
        .sort();
    return CWDA_PROFILE_BY_ARMIES.get([...new Set(armies)].join('|')) ?? 'cwda';
}

export function cwdaArmyClassNames(initialFen: string): string[] {
    if (!initialFen) return [];
    const ranks = initialFen.trim().split(/\s+/)[0]?.split('/') ?? [];
    const blackArmy = CWDA_ARMY_BY_BACK_RANK.get(ranks[0]?.toLowerCase());
    const whiteArmy = CWDA_ARMY_BY_BACK_RANK.get(ranks[ranks.length - 1]?.toLowerCase());
    return [blackArmy && `cwda-black-${blackArmy}`, whiteArmy && `cwda-white-${whiteArmy}`].filter(
        (className): className is string => !!className,
    );
}

export const VARIANTS: Record<string, Variant> = {
    borderlands: variant({
        name: 'borderlands',
        displayName: 'borderlands',
        tooltip: 'borderlands',
        startFen: 'a3s3a/1chesehc1/fw1wlw1wf/w1w1w1w1w/9/9/W1W1W1W1W/FW1WLW1WF/1CHESEHC1/A3S3A[MMmm] w - - 0 1',
        icon: ' 🌄',
        boardFamily: 'borderlands9x10',
        pieceFamily: 'borderlands',
        pieceRow: ['a', 'h', 's', 'c', 'e', 'f', 'w', 'g', 'm'],
        pocket: {
            roles: ['m'],
            captureToHand: false,
        },
        promotion: { type: 'regular', roles: [] },
    }),

    xiangfu: variant({
        name: 'xiangfu',
        displayName: 'xiang fu',
        tooltip: 'Martial arts Xiangqi.',
        startFen: '2rbm4/2cwn4/2+g1+g4/9/9/9/4+G1+G2/4NWC2/4MBR2[] w - 0 1',
        icon: '👊',
        boardFamily: 'xiangfu9x9',
        pieceFamily: 'xiangfu',
        pieceRow: ['+g', 'g', 'r', 'b', 'm', 'c', 'w', 'n'],
        pocket: {
            roles: ['g', 'r', 'b', 'm', 'c', 'w', 'n'],
            captureToHand: true,
        },
        promotion: { type: 'regular', roles: [] },
        kingRoles: ['+g'],
        alternateStart: {
            '': '',
            SwitchedRB: '2brm4/2cwn4/2+g1+g4/9/9/9/4+G1+G2/4NWC2/4MRB2[] w - 0 1',
        },
    }),

    ataxx: variant({
        name: 'ataxx',
        tooltip: 'Infection game.',
        startFen: 'P5p/7/7/7/7/7/p5P w 0 1',
        icon: '☣',
        boardFamily: 'ataxx7x7',
        pieceFamily: 'ataxx',
        colors: { first: 'Red', second: 'Blue' },
        pieceRow: ['p', '*'],
        rules: { pass: true },
        ui: { materialPoint: 'ataxx' },
        // Ataxx All 19 boards won https://www.youtube.com/watch?v=3VcAW6EKuvU
        alternateStart: {
            '': '',
            'Board 0': 'P5p/7/7/7/7/7/p5P w 0 1',
            'Board 1': 'P5p/7/3*3/2*1*2/3*3/7/p5P w 0 1',
            'Board 2': 'P5p/7/3*3/2***2/3*3/7/p5P w 0 1',
            'Board 3': 'P5p/7/2*1*2/7/2*1*2/7/p5P w 0 1',
            'Board 4': 'P5p/1*3*1/2*1*2/7/2*1*2/1*3*1/p5P w 0 1',
            'Board 5': 'P5p/7/2*1*2/3*3/2*1*2/7/p5P w 0 1',
            'Board 6': 'P2*2p/7/7/*5*/7/7/p2*2P w 0 1',
            'Board 7': 'P2*2p/3*3/7/**3**/7/3*3/p2*2P w 0 1',
            'Board 8': 'P2*2p/3*3/3*3/***1***/3*3/3*3/p2*2P w 0 1',
            'Board 9': 'P5p/2*1*2/1*3*1/7/1*3*1/2*1*2/p5P w 0 1',
            'Board 10': 'P2*2p/7/1*3*1/*5*/1*3*1/7/p2*2P w 0 1',
            'Board 11': 'P1*1*1p/7/*2*2*/7/*2*2*/7/p1*1*1P w 0 1',
            'Board 12': 'P1*1*1p/7/2*1*2/1*3*1/2*1*2/7/p1*1*1P w 0 1',
            'Board 13': 'P2*2p/2*1*2/1*3*1/*5*/1*3*1/2*1*2/p2*2P w 0 1',
            'Board 14': 'P1*1*1p/1*3*1/*5*/7/*5*/1*3*1/p1*1*1P w 0 1',
            'Board 15': 'P1*1*1p/7/*1*1*1*/7/*1*1*1*/7/p1*1*1P w 0 1',
            'Board 16': 'P2*2p/7/1**1**1/**3**/1**1**1/7/p2*2P w 0 1',
            'Board 17': 'P1*1*1p/2*1*2/*5*/*2*2*/*5*/2*1*2/p1*1*1P w 0 1',
            'Board 18': 'P5p/2*1*2/**1*1**/3*3/**1*1**/2*1*2/p5P w 0 1',
            'Board 19': 'P1***1p/7/**1*1**/*5*/**1*1**/7/p1***1P w 0 1',
        },
    }),

    chess: variant({
        name: 'chess',
        tooltip: "Chess, unmodified, as it's played by FIDE standards.",
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        chess960: true,
        icon: 'M',
        icon960: 'V',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
        alternateStart: {
            '': '',
            PawnsPushed: 'rnbqkbnr/8/8/pppppppp/PPPPPPPP/8/8/RNBQKBNR w KQkq - 0 1',
            PawnsPassed: 'rnbqkbnr/8/8/PPPPPPPP/pppppppp/8/8/RNBQKBNR w KQkq - 0 1',
            UpsideDown: 'RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr w - - 0 1',
            Theban: '1p6/2p3kn/3p2pp/4pppp/5ppp/8/PPPPPPPP/PPPPPPKN w - - 0 1',
            'No castle': {
                fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1',
                canRated: true,
            },
        },
    }),
    bughouse: variant({
        name: 'bughouse',
        tooltip: 'bughousebughousebughousebughouse.',
        displayName: 'bughouse',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1',
        chess960: true,
        icon: '¢',
        icon960: '⌀',
        twoBoards: true,
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        pocket: {
            roles: ['p', 'n', 'b', 'r', 'q'],
            pieceNames: {
                'p-piece': _('pawn'),
                'n-piece': _('knight'),
                'b-piece': _('bishop'),
                'r-piece': _('rook'),
                'q-piece': _('queen'),
            },
            captureToHand: true,
        },
        rules: { enPassant: true },
        ui: { showPromoted: true },
        alternateStart: {
            '': '',
            PawnsPushed:
                'rnbqkbnr/8/8/pppppppp/PPPPPPPP/8/8/RNBQKBNR[] w KQkq - 0 1 | rnbqkbnr/8/8/pppppppp/PPPPPPPP/8/8/RNBQKBNR[] w KQkq - 0 1',
            PawnsPassed:
                'rnbqkbnr/8/8/PPPPPPPP/pppppppp/8/8/RNBQKBNR[] w KQkq - 0 1 | rnbqkbnr/8/8/PPPPPPPP/pppppppp/8/8/RNBQKBNR[] w KQkq - 0 1',
            UpsideDown:
                'RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr[] w - - 0 1 | RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr[] w - - 0 1',
            Theban: '1p6/2p3kn/3p2pp/4pppp/5ppp/8/PPPPPPPP/PPPPPPKN[] w - - 0 1 | 1p6/2p3kn/3p2pp/4pppp/5ppp/8/PPPPPPPP/PPPPPPKN[] w - - 0 1',
            'No castle':
                'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w - - 0 1 | rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w - - 0 1',
        },
    }),
    crazyhouse: variant({
        name: 'crazyhouse',
        tooltip: 'Take captured pieces and drop them back on to the board as your own.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1',
        chess960: true,
        icon: '+',
        icon960: '%',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        pocket: {
            roles: ['p', 'n', 'b', 'r', 'q'],
            captureToHand: true,
        },
        rules: { enPassant: true },
        alternateStart: {
            '': '',
            PawnsPushed: 'rnbqkbnr/8/8/pppppppp/PPPPPPPP/8/8/RNBQKBNR[] w KQkq - 0 1',
            PawnsPassed: 'rnbqkbnr/8/8/PPPPPPPP/pppppppp/8/8/RNBQKBNR[] w KQkq - 0 1',
            UpsideDown: 'RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr[] w - - 0 1',
            Theban: '1p6/2p3kn/3p2pp/4pppp/5ppp/8/PPPPPPPP/PPPPPPKN[] w - - 0 1',
            'No castle': {
                fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w - - 0 1',
                canRated: true,
            },
        },
    }),

    placement: variant({
        name: 'placement',
        tooltip: 'Choose where your pieces start.',
        startFen: '8/pppppppp/8/8/8/8/PPPPPPPP/8[KQRRBBNNkqrrbbnn] w - - 0 1',
        icon: 'S',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['n', 'b', 'r', 'q', 'k'], captureToHand: false },
        rules: { enPassant: true },
    }),

    atomic: variant({
        name: 'atomic',
        tooltip: 'Pieces explode upon capture.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        chess960: true,
        icon: '~',
        icon960: '\\',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
        ui: { pieceSound: 'atomic' },
    }),

    kingofthehill: variant({
        name: 'kingofthehill',
        displayName: 'king of the hill',
        tooltip: 'Bring your King to the center to win the game.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        chess960: true,
        icon: '🏴',
        icon960: '🏁',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
        ui: { boardMark: 'kingofthehill' },
    }),

    '3check': variant({
        name: '3check',
        displayName: 'three-check',
        tooltip: 'Check your opponent 3 times to win the game.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 3+3 0 1',
        chess960: true,
        icon: '☰',
        icon960: '☷',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
        ui: { showCheckCounters: true },
        alternateStart: {
            '': '',
            '5check': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 5+5 0 1',
        },
    }),

    antichess: variant({
        name: 'antichess',
        tooltip: 'Lose all your pieces to win.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        chess960: true,
        icon: '🐥',
        icon960: '🐓',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    racingkings: variant({
        name: 'racingkings',
        displayName: 'racing kings',
        display960: '1440',
        tooltip: 'Race your King to the eighth rank to win.',
        startFen: '8/8/8/8/8/8/krbnNBRK/qrbnNBRQ w - - 0 1',
        chess960: true,
        icon: '🚗',
        icon960: '🚙',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        ui: { boardMark: 'racingkings' },
    }),

    horde: variant({
        name: 'horde',
        tooltip: 'Destroy the horde to win!',
        startFen: 'rnbqkbnr/pppppppp/8/1PP2PP1/PPPPPPPP/PPPPPPPP/PPPPPPPP/PPPPPPPP w kq - 0 1',
        chess960: true,
        icon: '🐖',
        icon960: '🐷',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: { white: ['p'], black: ['k', 'q', 'r', 'b', 'n', 'p'] },
        rules: { enPassant: true },
    }),

    duck: variant({
        name: 'duck',
        tooltip: 'The duck must be moved to a new square after every turn.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        icon: '🦆',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: { white: ['k', 'q', 'r', 'b', 'n', 'p', '*'], black: ['k', 'q', 'r', 'b', 'n', 'p'] },
        rules: { enPassant: true, duck: true },
    }),

    alice: variant({
        name: 'alice',
        tooltip: 'Through the Looking-Glass',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        icon: '👧',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: false },
        alternateStart: {
            '': '',
            'Looking glass': '|r|n|b|q|k|b|n|r/|p|p|p|p|p|p|p|p/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1',
        },
        // For Alice chess other board pieces we use promoted pieces to let them style differently,
        ui: { boardMark: 'alice' },
    }),

    fogofwar: variant({
        name: 'fogofwar',
        displayName: 'fog of war',
        tooltip: 'Players can only see the squares to which their pieces can legally move to.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        hiddenInfo: true,
        hiddenInfoMode: 'fog',
        icon: '🌫',
        boardFamily: 'standard8x8',
        pieceFamily: 'standard',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    makruk: variant({
        name: 'makruk',
        tooltip:
            'Thai Chess. A game closely resembling the original Chaturanga. Similar to Chess but with a different queen and bishop.',
        startFen: 'rnsmksnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR w - - 0 1',
        icon: 'Q',
        boardFamily: 'makruk8x8',
        pieceFamily: 'makruk',
        pieceRow: ['k', 's', 'm', 'n', 'r', 'p', 'm~' as cg.Letter],
        promotion: { type: 'regular', order: ['m'] },
        ui: { counting: 'makruk', showPromoted: true },
    }),

    makrukhouse: variant({
        name: 'makrukhouse',
        tooltip: 'Take captured pieces and drop them back on to the board as your own.',
        startFen: 'rnsmksnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR[] w - - 0 1',
        icon: 'Q',
        boardFamily: 'makruk8x8',
        pieceFamily: 'makruk',
        pieceRow: ['k', 's', 'm', 'n', 'r', 'p', 'm~' as cg.Letter],
        promotion: { type: 'regular', order: ['m'] },
        pocket: {
            roles: ['p', 'm', 's', 'n', 'r'],
            captureToHand: true,
        },
    }),

    makbug: variant({
        name: 'makbug',
        tooltip: 'Thai bughouse chess',
        displayName: 'makbug ᴮᴱᵀᴬ',
        startFen: 'rnsmksnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR[] w - - 0 1',
        icon: 'Q',
        twoBoards: true,
        boardFamily: 'makruk8x8',
        pieceFamily: 'makruk',
        pieceRow: ['k', 's', 'm', 'n', 'r', 'p', 'm~' as cg.Letter],
        promotion: { type: 'regular', order: ['m'] },
        pocket: {
            roles: ['p', 'm', 's', 'n', 'r'],
            pieceNames: {
                'p-piece': _('pawn'),
                'm-piece': _('queen'),
                's-piece': _('bishop'),
                'n-piece': _('knight'),
                'r-piece': _('rook'),
            },
            captureToHand: true,
        },
        ui: { showPromoted: true },
    }),

    makpong: variant({
        name: 'makpong',
        tooltip: 'Makruk variant where kings cannot move to escape out of check.',
        startFen: 'rnsmksnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR w - - 0 1',
        icon: 'O',
        boardFamily: 'makruk8x8',
        pieceFamily: 'makruk',
        pieceRow: ['k', 's', 'm', 'n', 'r', 'p', 'm~' as cg.Letter],
        promotion: { type: 'regular', order: ['m'] },
        ui: { counting: 'makruk', showPromoted: true },
    }),

    cambodian: variant({
        name: 'cambodian',
        displayName: 'ouk chaktrang',
        tooltip: 'Cambodian Chess. Makruk with a few additional opening abilities.',
        startFen: 'rnsmksnr/8/pppppppp/8/8/PPPPPPPP/8/RNSKMSNR w DEde - 0 1',
        icon: '!',
        boardFamily: 'makruk8x8',
        pieceFamily: 'makruk',
        pieceRow: ['k', 's', 'm', 'n', 'r', 'p', 'm~' as cg.Letter],
        promotion: { type: 'regular', order: ['m'] },
        ui: { counting: 'makruk', showPromoted: true },
    }),

    sittuyin: variant({
        name: 'sittuyin',
        tooltip: 'Burmese Chess. Similar to Makruk, but pieces are placed at the start of the match.',
        startFen: '8/8/4pppp/pppp4/4PPPP/PPPP4/8/8[KFRRSSNNkfrrssnn] w - - 0 1',
        icon: ':',
        boardFamily: 'sittuyin8x8',
        pieceFamily: 'sittuyin',
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'f', 's', 'n', 'r', 'p'],
        pocket: { roles: ['r', 'n', 's', 'f', 'k'], captureToHand: false },
        promotion: { type: 'regular', order: ['f'] },
    }),

    asean: variant({
        name: 'asean',
        tooltip: 'Makruk using the board/pieces from International Chess as well as pawn promotion rules.',
        startFen: 'rnbqkbnr/8/pppppppp/8/8/PPPPPPPP/8/RNBQKBNR w - - 0 1',
        icon: '♻',
        boardFamily: 'standard8x8',
        pieceFamily: 'asean',
        pieceRow: ['k', 'q', 'b', 'n', 'r', 'p'],
        promotion: { type: 'regular', order: ['r', 'n', 'b', 'q'] },
        ui: { counting: 'asean' },
    }),

    shogi: variant({
        name: 'shogi',
        tooltip: 'Japanese Chess, the standard 9x9 version played today with drops and promotions.',
        startFen: 'lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] w 0 1',
        icon: 'K',
        boardFamily: 'shogi9x9',
        pieceFamily: 'shogi',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 'r', 'b', 's', 'n', 'l', 'p'],
        pocket: { roles: ['p', 'l', 'n', 's', 'g', 'b', 'r'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'l', 'n', 's', 'r', 'b'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
        alternateStart: {
            '': '',
            'Lance HC': 'lnsgkgsn1/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            'Bishop HC': 'lnsgkgsnl/1r7/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            'Rook HC': 'lnsgkgsnl/7b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            'Rook+Lance HC': 'lnsgkgsn1/7b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '2-Piece HC': 'lnsgkgsnl/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '4-Piece HC': '1nsgkgsn1/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '6-Piece HC': '2sgkgs2/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '8-Piece HC': '3gkg3/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '9-Piece HC': '3gk4/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
            '10-Piece HC': '4k4/9/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] b 0 1',
        },
    }),

    shoshogi: variant({
        name: 'shoshogi',
        displayName: 'sho shogi',
        tooltip: 'Historical 9x9 Shogi with a drunken elephant piece and no drops.',
        startFen: 'lnsgkgsnl/1r2e2b1/ppppppppp/9/9/9/PPPPPPPPP/1B2E2R1/LNSGKGSNL w 0 1',
        icon: '🍹',
        boardFamily: 'shogi9x9',
        pieceFamily: 'shogi',
        pieceCSSExclude: ['shogi', 'shogip', 'shogim', 'shogikw3d', 'shogid', 'shogiim', 'portk'],
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 'r', 'b', 's', 'n', 'l', 'p', 'e'],
        kingRoles: ['k', '+e'],
        promotion: { type: 'shogi', roles: ['p', 'l', 'n', 's', 'r', 'b', 'e'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    yokai: variant({
        name: 'yokai',
        displayName: 'yokai shogi',
        tooltip: 'Modern Shogi variant',
        startFen: 'rgytkfygl/1c5a1/ppppppppp/9/9/9/PPPPPPPPP/1A5C1/LGYFKTYGR[Nn] w 0 1',
        icon: '👹',
        boardFamily: 'shogi9x9',
        pieceFamily: 'yokai',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 't', 'f', 'r', 'l', 'a', 'c', 'g', 'y', 'p', 'n'],
        pocket: { roles: ['n', 't', 'f', 'r', 'l', 'a', 'c', 'g', 'y', 'p'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'f', 'g', 'y', 't'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    cannonshogi: variant({
        name: 'cannonshogi',
        displayName: 'cannon shogi',
        tooltip: 'Shogi with Chinese and Korean cannons',
        startFen: 'lnsgkgsnl/1rci1uab1/p1p1p1p1p/9/9/9/P1P1P1P1P/1BAU1ICR1/LNSGKGSNL[-] w 0 1',
        icon: '💣',
        boardFamily: 'shogi9x9',
        pieceFamily: 'cannonshogi',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 'r', 'b', 's', 'n', 'l', 'p', 'u', 'a', 'c', 'i'],
        pocket: { roles: ['p', 'l', 'n', 's', 'g', 'b', 'r', 'u', 'a', 'c', 'i'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'l', 'n', 's', 'r', 'b', 'u', 'a', 'c', 'i'] },
        rules: { defaultTimeControl: 'byoyomi' },
        ui: { pieceSound: 'shogi' },
    }),

    minishogi: variant({
        name: 'minishogi',
        tooltip: '5x5 Shogi for more compact and faster games. There are no knights or lances.',
        startFen: 'rbsgk/4p/5/P4/KGSBR[-] w 0 1',
        icon: '6',
        boardFamily: 'shogi5x5',
        pieceFamily: 'shogi',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 'r', 'b', 's', 'p'],
        pocket: { roles: ['p', 's', 'g', 'b', 'r'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 's', 'r', 'b'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    kyotoshogi: variant({
        name: 'kyotoshogi',
        displayName: 'kyoto shogi',
        tooltip: 'A wild Shogi variant on a 5x5 board where pieces flip into a different piece after each move.',
        startFen: 'p+nks+l/5/5/5/+LSK+NP[-] w 0 1',
        icon: ')',
        boardFamily: 'shogi5x5',
        pieceFamily: 'kyoto',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'l', 's', 'n', 'p'],
        pocket: { roles: ['p', 'l', 'n', 's'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'l', 'n', 's'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    dobutsu: variant({
        name: 'dobutsu',
        tooltip: '3x4 game with cute animals, designed to teach children how to play Shogi.',
        startFen: 'gle/1c1/1C1/ELG[-] w 0 1',
        icon: '8',
        boardFamily: 'shogi3x4',
        pieceFamily: 'dobutsu',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['l', 'g', 'e', 'c'],
        kingRoles: ['l'],
        pocket: { roles: ['e', 'g', 'c'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['c'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    gorogoro: variant({
        name: 'gorogoro',
        tooltip: '5x6 Shogi designed to introduce tactics with the generals.',
        startFen: 'sgkgs/5/1ppp1/1PPP1/5/SGKGS[-] w 0 1',
        icon: '🐱',
        boardFamily: 'shogi5x6',
        pieceFamily: 'shogi',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 's', 'p'],
        pocket: { roles: ['p', 's', 'g'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 's'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
    }),

    gorogoroplus: variant({
        name: 'gorogoroplus',
        displayName: 'gorogoro+',
        tooltip: '5x6 Shogi designed to introduce tactics with the generals.',
        startFen: 'sgkgs/5/1ppp1/1PPP1/5/SGKGS[LNln] w 0 1',
        icon: '🐱',
        boardFamily: 'shogi5x6',
        pieceFamily: 'shogi',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'g', 's', 'n', 'l', 'p'],
        pocket: { roles: ['p', 'l', 'n', 's', 'g'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 's', 'n', 'l'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
        alternateStart: {
            'Gorogoro Plus N+L': '',
            'Original (No N+L)': 'sgkgs/5/1ppp1/1PPP1/5/SGKGS[-] w 0 1',
        },
    }),

    torishogi: variant({
        name: 'torishogi',
        displayName: 'tori shogi',
        tooltip: 'A confrontational 7x7 variant with unique pieces each named after different birds.',
        startFen: 'rpckcpl/3f3/sssssss/2s1S2/SSSSSSS/3F3/LPCKCPR[-] w 0 1',
        icon: '🐦',
        boardFamily: 'shogi7x7',
        pieceFamily: 'tori',
        notation: cg.Notation.SHOGI_ARBNUM,
        colors: { first: 'Black', second: 'White' },
        pieceRow: ['k', 'c', 'p', 'l', 'r', 'f', 's'],
        pocket: { roles: ['s', 'p', 'l', 'r', 'c', 'f'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['s', 'f'] },
        rules: { defaultTimeControl: 'byoyomi', noDrawOffer: true },
        ui: { pieceSound: 'shogi' },
        alternateStart: {
            '': '',
            'Left Quail HC': 'rpckcp1/3f3/sssssss/2s1S2/SSSSSSS/3F3/LPCKCPR[] b 0 1',
            'Falcon HC': 'rpckcpl/7/sssssss/2s1S2/SSSSSSS/3F3/LPCKCPR[] b 0 1',
            'Falcon + Left Quail HC': 'rpckcp1/7/sssssss/2s1S2/SSSSSSS/3F3/LPCKCPR[] b 0 1',
            'Falcon + Both Quails HC': '1pckcp1/7/sssssss/2s1S2/SSSSSSS/3F3/LPCKCPR[] b 0 1',
        },
    }),

    xiangqi: variant({
        name: 'xiangqi',
        tooltip: 'Chinese Chess, one of the oldest and most played board games in the world.',
        startFen: 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1',
        icon: '|',
        boardFamily: 'xiangqi9x10',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'a', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
    }),

    jieqi: variant({
        name: 'jieqi',
        tooltip: 'Players can see the identity of the pieces after their first move.',
        startFen: 'r~n~b~a~ka~b~n~r~/9/1c~5c~1/p~1p~1p~1p~1p~/9/9/P~1P~1P~1P~1P~/1C~5C~1/9/R~N~B~A~KA~B~N~R~ w - - 0 1',
        hiddenInfo: true,
        hiddenInfoMode: 'covered_pieces',
        icon: '⬤',
        boardFamily: 'xiangqi9x10',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'a', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
    }),

    xiangqihouse: variant({
        name: 'xiangqihouse',
        tooltip: 'Take captured pieces and drop them back on to the board as your own.',
        startFen: 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR[] w - - 0 1',
        icon: '+',
        boardFamily: 'xiangqi9x10',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'a', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
        pocket: {
            roles: ['p', 'n', 'b', 'r', 'c', 'a'],
            captureToHand: true,
        },
    }),

    supply: variant({
        name: 'supply',
        tooltip: 'Chinese bughouse chess',
        displayName: 'supply chess ᴮᴱᵀᴬ',
        startFen: 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR[] w - - 0 1',
        icon: '¢',
        twoBoards: true,
        boardFamily: 'xiangqi9x10',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'a', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
        pocket: {
            roles: ['p', 'n', 'b', 'r', 'c', 'a'],
            pieceNames: {
                'p-piece': _('pawn'),
                'n-piece': _('horse'),
                'b-piece': _('elephant'),
                'r-piece': _('chariot'),
                'c-piece': _('cannon'),
                'a-piece': _('advisor'),
            },
            captureToHand: true,
        },
        ui: { showPromoted: true },
    }),

    manchu: variant({
        name: 'manchu',
        displayName: 'manchu+',
        tooltip: 'Xiangqi variant where one side has a chariot that can also move as a cannon or horse.',
        // Manchu+R proved to be balanced
        startFen: 'm1bakab1r/9/9/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1',
        icon: '{',
        boardFamily: 'xiangqi9x10',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: { white: ['k', 'a', 'c', 'r', 'b', 'n', 'p'], black: ['k', 'a', 'm', 'r', 'b', 'p'] },
        promotion: { type: 'regular', roles: [] },
        alternateStart: {
            '': '',
            'Original Manchu': 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/9/9/M1BAKAB2 w - - 0 1',
        },
    }),

    janggi: variant({
        name: 'janggi',
        tooltip: 'Korean Chess, similar to Xiangqi but plays much differently. Tournament rules are used.',
        startFen: 'rnba1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ABNR w - - 0 1',
        icon: '=',
        boardFamily: 'janggi9x10',
        pieceFamily: 'janggi',
        notation: cg.Notation.JANGGI,
        colors: { first: 'Blue', second: 'Red' },
        pieceRow: ['k', 'a', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
        rules: { defaultTimeControl: 'byoyomi', pass: true, setup: true },
        ui: { materialPoint: 'janggi' },
        alternateStart: {
            '': '',
            'Central Chariot Setup': 'bnra1arnb/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/BNRA1ARNB w - - 0 1',
        },
    }),

    minixiangqi: variant({
        name: 'minixiangqi',
        tooltip: 'Compact version of Xiangqi played on a 7x7 board without a river.',
        startFen: 'rcnkncr/p1ppp1p/7/7/7/P1PPP1P/RCNKNCR w - - 0 1',
        icon: '7',
        boardFamily: 'xiangqi7x7',
        pieceFamily: 'xiangqi',
        notation: cg.Notation.XIANGQI_ARBNUM,
        colors: { first: 'Red', second: 'Black' },
        pieceRow: ['k', 'c', 'r', 'n', 'p'],
        promotion: { type: 'regular', roles: [] },
    }),

    shatranj: variant({
        name: 'shatranj',
        displayName: 'shatranj',
        tooltip: 'Ancient Arabian and Persian form of Chess.',
        startFen: 'rnbkqbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBKQBNR w - - 0 1',
        icon: '🐘',
        boardFamily: 'makruk8x8',
        pieceFamily: 'shatranj',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', order: ['q'] },
        alternateStart: {
            '': '',
            Chaturanga: 'rnbkqbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1',
        },
    }),

    capablanca: variant({
        name: 'capablanca',
        displayName960: 'caparandom',
        tooltip: 'Play with the hybrid pieces, archbishop (B+N) and chancellor (R+N), on a 10x8 board.',
        startFen: 'rnabqkbcnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNABQKBCNR w KQkq - 0 1',
        chess960: true,
        icon: 'P',
        icon960: ',',
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
        alternateStart: {
            '': '',
            Bird: {
                fen: 'rnbcqkabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBCQKABNR w KQkq - 0 1',
                canRated: true,
            },
            Carrera: {
                fen: 'ranbqkbncr/pppppppppp/10/10/10/10/PPPPPPPPPP/RANBQKBNCR w KQkq - 0 1',
                canRated: true,
            },
            Conservative: {
                fen: 'arnbqkbnrc/pppppppppp/10/10/10/10/PPPPPPPPPP/ARNBQKBNRC w KQkq - 0 1',
                canRated: true,
            },
            Embassy: {
                fen: 'rnbqkcabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQKCABNR w KQkq - 0 1',
                canRated: true,
            },
            Gothic: {
                fen: 'rnbqckabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQCKABNR w KQkq - 0 1',
                canRated: true,
            },
            Schoolbook: {
                fen: 'rqnbakbncr/pppppppppp/10/10/10/10/PPPPPPPPPP/RQNBAKBNCR w KQkq - 0 1',
                canRated: true,
            },
            Univers: {
                fen: 'rbncqkanbr/pppppppppp/10/10/10/10/PPPPPPPPPP/RBNCQKANBR w KQkq - 0 1',
                canRated: true,
            },
            Victorian: {
                fen: 'crnbakbnrq/pppppppppp/10/10/10/10/PPPPPPPPPP/CRNBAKBNRQ w KQkq - 0 1',
                canRated: true,
            },
        },
    }),

    capahouse: variant({
        name: 'capahouse',
        tooltip: 'Capablanca with Crazyhouse drop rules.',
        startFen: 'rnabqkbcnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNABQKBCNR[] w KQkq - 0 1',
        chess960: true,
        icon: '&',
        icon960: "'",
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'a', 'c', 'q'], captureToHand: true },
        rules: { enPassant: true },
        alternateStart: {
            '': '',
            Bird: {
                fen: 'rnbcqkabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBCQKABNR[] w KQkq - 0 1',
                canRated: true,
            },
            Carrera: {
                fen: 'ranbqkbncr/pppppppppp/10/10/10/10/PPPPPPPPPP/RANBQKBNCR[] w KQkq - 0 1',
                canRated: true,
            },
            Conservative: {
                fen: 'arnbqkbnrc/pppppppppp/10/10/10/10/PPPPPPPPPP/ARNBQKBNRC[] w KQkq - 0 1',
                canRated: true,
            },
            Embassy: {
                fen: 'rnbqkcabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQKCABNR[] w KQkq - 0 1',
                canRated: true,
            },
            Gothic: {
                fen: 'rnbqckabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQCKABNR[] w KQkq - 0 1',
                canRated: true,
            },
            Schoolbook: {
                fen: 'rqnbakbncr/pppppppppp/10/10/10/10/PPPPPPPPPP/RQNBAKBNCR[] w KQkq - 0 1',
                canRated: true,
            },
            Univers: {
                fen: 'rbncqkanbr/pppppppppp/10/10/10/10/PPPPPPPPPP/RBNCQKANBR[] w KQkq - 0 1',
                canRated: true,
            },
            Victorian: {
                fen: 'crnbakbnrq/pppppppppp/10/10/10/10/PPPPPPPPPP/CRNBAKBNRQ[] w KQkq - 0 1',
                canRated: true,
            },
        },
    }),

    dragon: variant({
        name: 'dragon',
        displayName: 'dragon chess',
        tooltip: 'The dragon can be dropped to the base rank.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[Dd] w KQkq - 0 1',
        icon: '🐉',
        boardFamily: 'standard8x8',
        pieceFamily: 'dragon',
        pieceRow: ['k', 'q', 'd', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['d'], captureToHand: false },
        promotion: { type: 'regular', order: ['q', 'd', 'n', 'r', 'b'] },
        rules: { enPassant: true },
    }),

    seirawan: variant({
        name: 'seirawan',
        displayName: 's-chess',
        tooltip:
            'Hybrid pieces, the hawk (B+N) and elephant (R+N), can enter the board after moving a back rank piece.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[HEhe] w KQBCDFGkqbcdfg - 0 1',
        icon: 'L',
        chess960: true,
        icon960: '}',
        boardFamily: 'standard8x8',
        pieceFamily: 'seirawan',
        pieceRow: ['k', 'q', 'e', 'h', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['h', 'e'], captureToHand: false },
        rules: { enPassant: true, gate: true },
    }),

    shouse: variant({
        name: 'shouse',
        displayName: 's-house',
        tooltip: 'S-Chess with Crazyhouse drop rules.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[HEhe] w KQBCDFGkqbcdfg - 0 1',
        icon: '$',
        boardFamily: 'standard8x8',
        pieceFamily: 'seirawan',
        pieceRow: ['k', 'q', 'e', 'h', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'h', 'e', 'q'], captureToHand: true },
        rules: { enPassant: true, gate: true },
    }),

    grand: variant({
        name: 'grand',
        tooltip: 'Play with the hybrid pieces, archbishop (B+N) and chancellor (R+N), on a grand 10x10 board.',
        startFen: 'r8r/1nbqkcabn1/pppppppppp/10/10/10/10/PPPPPPPPPP/1NBQKCABN1/R8R w - - 0 1',
        icon: '(',
        boardFamily: 'grand10x10',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    grandhouse: variant({
        name: 'grandhouse',
        tooltip: 'Grand Chess with Crazyhouse drop rules.',
        startFen: 'r8r/1nbqkcabn1/pppppppppp/10/10/10/10/PPPPPPPPPP/1NBQKCABN1/R8R[] w - - 0 1',
        icon: '*',
        boardFamily: 'grand10x10',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'a', 'c', 'q'], captureToHand: true },
        rules: { enPassant: true },
    }),

    shako: variant({
        name: 'shako',
        tooltip: 'Introduces the cannon and elephant from Xiangqi into a 10x10 chess board.',
        startFen: 'c8c/ernbqkbnre/pppppppppp/10/10/10/10/PPPPPPPPPP/ERNBQKBNRE/C8C w KQkq - 0 1',
        icon: '9',
        boardFamily: 'standard10x10',
        pieceFamily: 'shako',
        pieceRow: ['k', 'q', 'e', 'c', 'r', 'b', 'n', 'p'],
        promotion: { type: 'regular', order: ['q', 'n', 'c', 'r', 'e', 'b'] },
        rules: { enPassant: true },
        alternateStart: {
            '': '',
            'Setup similar to Xiangqi': 'rnbeqkebnr/10/1c6c1/p1p1pp1p1p/10/10/P1P1PP1P1P/1C6C1/10/RNBEQKEBNR w - - 0 1',
        },
    }),

    shogun: variant({
        name: 'shogun',
        tooltip: 'Pieces promote and can be dropped, similar to Shogi.',
        startFen: 'rnb+fkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB+FKBNR w KQkq - 0 1',
        icon: '-',
        boardFamily: 'shogun8x8',
        pieceFamily: 'shogun',
        pieceRow: ['k', 'f', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'f'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'f', 'r', 'b', 'n'] },
        rules: { defaultTimeControl: 'byoyomi', enPassant: true },
    }),

    hoppelpoppel: variant({
        name: 'hoppelpoppel',
        displayName: 'hoppel-poppel',
        tooltip: 'Knights capture as bishops; bishops  capture as knights.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        icon: '`',
        boardFamily: 'standard8x8',
        pieceFamily: 'hoppel',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    cwda: variant({
        name: 'cwda',
        displayName: 'cwda',
        tooltip: 'Choose one of four armies for each player.',
        startFen: CWDA_DEFAULT_FEN,
        ratingEnabled: false,
        icon: '⚔',
        boardFamily: 'standard8x8',
        pieceFamily: 'cwda',
        pieceRow: ['k', 'q', 'r', 'b', 'n', 'd', 'w', 'a', 'c', 'g', 'i', 'h', 'o', 's', 'm', 'f', 'e', 'p'],
        promotion: {
            type: 'regular',
            order: ['q', 'c', 'o', 'e', 'a', 'h', 'f', 'n', 'r', 'd', 'g', 's', 'b', 'w', 'i', 'm'],
        },
        rules: { enPassant: true },
        alternateStart: {
            'FIDE — Clobberers': { fen: CWDA_DEFAULT_FEN, canRated: true },
            'FIDE — Knights': {
                fen: 'gihokhig/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                canRated: true,
            },
            'FIDE — Rookies': {
                fen: 'smfekfms/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                canRated: true,
            },
            'Clobberers — FIDE': {
                fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/DWACKAWD w KQkq - 0 1',
                canRated: true,
            },
            'Clobberers — Clobberers': {
                fen: 'dwackawd/pppppppp/8/8/8/8/PPPPPPPP/DWACKAWD w KQkq - 0 1',
                canRated: true,
            },
            'Clobberers — Knights': {
                fen: 'gihokhig/pppppppp/8/8/8/8/PPPPPPPP/DWACKAWD w KQkq - 0 1',
                canRated: true,
            },
            'Clobberers — Rookies': {
                fen: 'smfekfms/pppppppp/8/8/8/8/PPPPPPPP/DWACKAWD w KQkq - 0 1',
                canRated: true,
            },
            'Knights — FIDE': {
                fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/GIHOKHIG w KQkq - 0 1',
                canRated: true,
            },
            'Knights — Clobberers': {
                fen: 'dwackawd/pppppppp/8/8/8/8/PPPPPPPP/GIHOKHIG w KQkq - 0 1',
                canRated: true,
            },
            'Knights — Knights': {
                fen: 'gihokhig/pppppppp/8/8/8/8/PPPPPPPP/GIHOKHIG w KQkq - 0 1',
                canRated: true,
            },
            'Knights — Rookies': {
                fen: 'smfekfms/pppppppp/8/8/8/8/PPPPPPPP/GIHOKHIG w KQkq - 0 1',
                canRated: true,
            },
            'Rookies — FIDE': {
                fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/SMFEKFMS w KQkq - 0 1',
                canRated: true,
            },
            'Rookies — Clobberers': {
                fen: 'dwackawd/pppppppp/8/8/8/8/PPPPPPPP/SMFEKFMS w KQkq - 0 1',
                canRated: true,
            },
            'Rookies — Knights': {
                fen: 'gihokhig/pppppppp/8/8/8/8/PPPPPPPP/SMFEKFMS w KQkq - 0 1',
                canRated: true,
            },
            'Rookies — Rookies': {
                fen: 'smfekfms/pppppppp/8/8/8/8/PPPPPPPP/SMFEKFMS w KQkq - 0 1',
                canRated: true,
            },
        },
    }),

    orda: variant({
        name: 'orda',
        tooltip: 'Asymmetric variant where one army has pieces that move like knights but capture differently.',
        startFen: 'lhaykahl/8/pppppppp/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1',
        icon: 'R',
        boardFamily: 'standard8x8',
        pieceFamily: 'orda',
        colors: { first: 'White', second: 'Gold' },
        pieceRow: { white: ['k', 'q', 'r', 'b', 'n', 'p', 'h'], black: ['k', 'y', 'l', 'a', 'h', 'p', 'q'] },
        promotion: { type: 'regular', order: ['q', 'h'] },
        rules: { enPassant: true },
        ui: { boardMark: 'campmate' },
    }),

    khans: variant({
        name: 'khans',
        tooltip: 'Orda Chess variant. The scout and khatun replaces the pawn and yurt.',
        startFen: 'lhatkahl/ssssssss/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1',
        icon: '🐎',
        boardFamily: 'standard8x8',
        pieceFamily: 'khans',
        colors: { first: 'White', second: 'Gold' },
        pieceRow: { black: ['k', 't', 'l', 'a', 'h', 's'], white: ['k', 'q', 'r', 'b', 'n', 'p'] },
        promotion: { type: 'regular' },
        rules: { enPassant: true },
        ui: { boardMark: 'campmate' },
    }),

    synochess: variant({
        name: 'synochess',
        tooltip:
            'Asymmetric East vs. West variant which pits the western Chess army against a Xiangqi and Janggi-styled army.',
        startFen: 'rneakenr/8/1c4c1/1ss2ss1/8/8/PPPPPPPP/RNBQKBNR[ss] w KQ - 0 1',
        icon: '_',
        boardFamily: 'standard8x8',
        pieceFamily: 'synochess',
        colors: { first: 'White', second: 'Red' },
        pieceRow: { white: ['k', 'q', 'r', 'b', 'n', 'p'], black: ['k', 'a', 'c', 'r', 'e', 'n', 's'] },
        pocket: { roles: { white: [], black: ['s'] }, captureToHand: false },
        ui: { boardMark: 'campmate' },
    }),

    shinobi: variant({
        name: 'shinobi',
        tooltip: 'Asymmetric variant which pits the western Chess army against a drop-based, Shogi-styled army.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/LH1CK1HL[LHMMDJ] w kq - 0 1',
        icon: '🐢',
        boardFamily: 'standard8x8',
        pieceFamily: 'shinobi',
        colors: { first: 'Pink', second: 'Black' },
        pieceRow: { white: ['k', 'd', 'j', 'c', 'l', 'h', 'm', 'p'], black: ['k', 'q', 'r', 'b', 'n', 'p'] },
        pocket: { roles: { white: ['l', 'h', 'm', 'd', 'j'], black: [] }, captureToHand: false },
        promotion: { type: 'shogi', roles: ['p', 'l', 'h', 'm'] },
        rules: { enPassant: true },
        ui: { boardMark: 'campmate' },
        material: {
            equivalences: {
                'pl-piece': 'r-piece',
                'ph-piece': 'n-piece',
                'pm-piece': 'b-piece',
                'pp-piece': 'c-piece',
            },
        },
    }),

    shinobiplus: variant({
        name: 'shinobiplus',
        displayName: 'shinobi+',
        tooltip: 'Asymmetric variant which pits the western Chess army against a drop-based, Shogi-styled army.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/4K3[JDFCLHM] w kq - 0 1',
        icon: '🐢',
        boardFamily: 'standard8x8',
        pieceFamily: 'shinobi',
        colors: { first: 'Pink', second: 'Black' },
        pieceRow: { white: ['k', 'f', 'd', 'j', 'l', 'h', 'm', 'p'], black: ['k', 'q', 'r', 'b', 'n', 'p'] },
        pocket: { roles: { white: ['l', 'h', 'm', 'd', 'j', 'f', 'c'], black: [] }, captureToHand: false },
        promotion: { type: 'shogi', roles: ['p', 'l', 'h', 'm'] },
        rules: { enPassant: true },
        ui: { boardMark: 'campmate' },
        material: {
            equivalences: {
                'pl-piece': 'r-piece',
                'ph-piece': 'n-piece',
                'pm-piece': 'b-piece',
                'pp-piece': 'c-piece',
            },
        },
        alternateStart: {
            '': '',
            'Original Shinobi': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/LH1CK1HL[LHMMDJ] w kq - 0 1',
        },
    }),

    empire: variant({
        name: 'empire',
        tooltip: 'Asymmetric variant where one army has pieces that move like queens but capture as usual.',
        startFen: 'rnbqkbnr/pppppppp/8/8/8/PPPSSPPP/8/TECDKCET w kq - 0 1',
        icon: '♚',
        boardFamily: 'standard8x8',
        pieceFamily: 'empire',
        colors: { first: 'Gold', second: 'Black' },
        pieceRow: { white: ['k', 'd', 't', 'c', 'e', 'p', 's', 'q'], black: ['k', 'q', 'r', 'b', 'n', 'p'] },
        rules: { enPassant: true },
        ui: { boardMark: 'campmate' },
    }),

    ordamirror: variant({
        name: 'ordamirror',
        displayName: 'orda mirror',
        tooltip: 'Orda Chess variant with two Horde armies. The Falcon replaces the Yurt.',
        startFen: 'lhafkahl/8/pppppppp/8/8/PPPPPPPP/8/LHAFKAHL w - - 0 1',
        icon: '◩',
        boardFamily: 'standard8x8',
        pieceFamily: 'ordamirror',
        colors: { first: 'White', second: 'Gold' },
        pieceRow: ['k', 'f', 'l', 'a', 'h', 'p'],
        promotion: { type: 'regular', order: ['h', 'l', 'f', 'a'] },
        ui: { boardMark: 'campmate' },
    }),

    chak: variant({
        name: 'chak',
        tooltip: 'Mayan chess. Inspired by cultural elements of Mesoamerica.',
        startFen: 'rvsqkjsvr/4o4/p1p1p1p1p/9/9/9/P1P1P1P1P/4O4/RVSJKQSVR w - - 0 1',
        icon: '🐬',
        boardFamily: 'chak9x9',
        pieceFamily: 'chak',
        colors: { first: 'White', second: 'Green' },
        pieceRow: ['k', 'j', 'q', 'r', 'v', 's', 'o', 'p'],
        kingRoles: ['k', '+k'],
        promotion: {
            type: 'shogi',
            roles: ['p', 'k'],
            strict: {
                isPromoted: (piece: cg.Piece, pos: cg.Pos) => {
                    switch (piece.role) {
                        case 'p-piece':
                        case 'pp-piece':
                        case 'k-piece':
                        case 'pk-piece':
                            return (piece.color === 'white' && pos[1] >= 4) || (piece.color === 'black' && pos[1] <= 4);
                        default:
                            return false;
                    }
                },
            },
        },
        material: {
            equivalences: {
                'pk-piece': 'k-piece',
            },
        },
    }),

    chennis: variant({
        name: 'chennis',
        tooltip: 'Pieces alternate between two forms with each move.',
        startFen: '1fkm3/1p1s3/7/7/7/3S1P1/3MKF1[] w - 0 1',
        icon: '🎾',
        boardFamily: 'chennis7x7',
        pieceFamily: 'chennis',
        pieceRow: ['k', 'p', 'm', 's', 'f'],
        pocket: { roles: ['p', 'm', 's', 'f'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['p', 'm', 's', 'f'] },
    }),

    spartan: variant({
        name: 'spartan',
        tooltip: 'Asymmetric Spartans vs. Persians variant.',
        startFen: 'lgkcckwl/hhhhhhhh/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1',
        icon: '⍺',
        boardFamily: 'standard8x8',
        pieceFamily: 'spartan',
        pieceRow: { white: ['k', 'q', 'r', 'b', 'n', 'p'], black: ['k', 'g', 'w', 'l', 'c', 'h'] },
    }),

    mansindam: variant({
        name: 'mansindam',
        tooltip: "A variant that combines the Shogi's drop rule with strong pieces.",
        startFen: 'rnbakqcnm/9/ppppppppp/9/9/9/PPPPPPPPP/9/MNCQKABNR[] w - - 0 1',
        icon: '⛵',
        boardFamily: 'standard9x9',
        pieceFamily: 'mansindam',
        pieceRow: ['k', 'r', 'n', 'b', 'a', 'q', 'c', 'm', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'a', 'q', 'c', 'm'], captureToHand: true },
        promotion: { type: 'shogi', roles: ['n', 'b', 'r', 'c', 'm', 'p'] },
    }),

    // We support the functionality to import/store/analyze some variants
    // but don't want to add them to leaderboard page
    embassy: variant({
        name: 'embassy',
        tooltip: 'Like Capablanca Chess but with Grand starting setup.',
        startFen: 'rnbqkcabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQKCABNR w KQkq - 0 1',
        icon: 'P',
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    embassyhouse: variant({
        name: 'embassyhouse',
        tooltip: 'Embassy with Crazyhouse drop rules.',
        startFen: 'rnbqkcabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQKCABNR[] w KQkq - 0 1',
        icon: '&',
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'a', 'c', 'q'], captureToHand: true },
        rules: { enPassant: true },
    }),

    gothic: variant({
        name: 'gothic',
        tooltip: 'Like Capablanca Chess but with a different starting setup.',
        startFen: 'rnbqckabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQCKABNR w KQkq - 0 1',
        icon: 'P',
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        rules: { enPassant: true },
    }),

    gothhouse: variant({
        name: 'gothhouse',
        tooltip: 'Gothic with Crazyhouse drop rules.',
        startFen: 'rnbqckabnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQCKABNR[] w KQkq - 0 1',
        icon: '&',
        boardFamily: 'standard10x8',
        pieceFamily: 'capa',
        pieceRow: ['k', 'q', 'c', 'a', 'r', 'b', 'n', 'p'],
        pocket: { roles: ['p', 'n', 'b', 'r', 'a', 'c', 'q'], captureToHand: true },
        rules: { enPassant: true },
    }),
};

export const variants = Object.keys(VARIANTS);
const BUILTIN_VARIANT_NAMES = new Set(Object.keys(VARIANTS));

export function isBuiltinVariantName(name: string | undefined | null): boolean {
    return !!name && BUILTIN_VARIANT_NAMES.has(name);
}
const disabledVariants = [
    'gothic',
    'gothhouse',
    'embassy',
    'embassyhouse',
    'gorogoro',
    'shinobi',
    'makrukhouse',
    'xiangqihouse',
];
export const enabledVariants = variants.filter(v => !disabledVariants.includes(v));

// variants having 0 puzzle so far
export const noPuzzleVariants = [
    'placement',
    'shoshogi',
    'gorogoroplus',
    'cannonshogi',
    'bughouse',
    'fogofwar',
    'antichess',
    'horde',
    'supply',
    'makbug',
    'jieqi',
    'xiangfu',
    'borderlands',
    'yokai',
];

export const twoBoarsVariants = variants.filter(v => VARIANTS[v].twoBoards);
export const unsupportedAiVariants = ['fogofwar', 'jieqi'];

export const devVariants = ['borderlands', 'cwda', 'makbug', 'supply', 'yokai'];
export const CATALOGUED_VARIANT_ICON = '☐';

export interface CataloguedVariantClientDocument {
    readonly name: string;
    readonly displayName: string;
    readonly tooltip?: string;
    readonly pieceNames?: Readonly<Record<string, string>>;
    readonly betzaPieces?: Readonly<Record<string, string>>;
    readonly ini: string;
    // Fairy-Stockfish rule inheritance. For FSF built-ins this names the
    // registered direct parent from variant.cpp and is empty for internal
    // helpers; it is not a pychess UI compatibility hint.
    readonly baseVariant?: string;
    // Optional pychess-only compatibility profile used for general client
    // defaults (promotion/pockets/rules UI and piece/board preference). It must
    // never be treated as Fairy-Stockfish rule inheritance.
    readonly clientVariant?: string;
    // Optional chessground-only premove fallback when movement geometry is
    // better represented by a different first-class variant.
    readonly premoveVariant?: string;
    readonly startFen: string;
    readonly randomStart?: boolean;
    readonly width: number;
    readonly height: number;
    readonly pieces: cg.Letter[];
    readonly kingRoles?: cg.Letter[];
    readonly pocketRoles?: cg.Letter[];
    readonly captureToHand?: boolean;
    readonly promotionType?: PromotionType;
    readonly promotionRoles?: cg.Letter[];
    readonly promotionOrder?: PromotionSuffix[];
    readonly showPromoted?: boolean;
    readonly rulesGate?: boolean;
    readonly rulesPass?: boolean;
    readonly rulesArrowing?: boolean;
    readonly showCheckCounters?: boolean;
    readonly category?: string;
    readonly author?: string;
    readonly source?: 'user' | 'fairy-stockfish-builtin';
    readonly system?: boolean;
    readonly nnueFingerprint?: string;
    readonly fsfBuiltinVariant?: string;
    readonly pieceFamilyOverride?: keyof typeof PIECE_FAMILIES;
    readonly boardFamilyOverride?: keyof typeof BOARD_FAMILIES;
    readonly archived?: boolean;
    readonly enabled?: boolean;
    readonly gameCount?: number;
    readonly favoriteCount?: number;
    readonly locked?: boolean;
    readonly visibility?: 'private' | 'unlisted' | 'public';
    readonly aiDisabled?: boolean;
    readonly aiDisabledReason?: string;
    readonly aiDisabledUntil?: string;
    readonly favorite?: boolean;
    readonly pieceSetDirectional?: boolean;
    readonly directionalPieceSet?: boolean;
    readonly hasPieceSet?: boolean;
    readonly pieceSetRevision?: string;
    readonly hasBoard?: boolean;
    readonly boardRevision?: string;
}

const cataloguedVariantInis: Record<string, string> = {};
const cataloguedVariantBaseNames: Record<string, string> = {};
const cataloguedVariantNames = new Set<string>();
const favoriteCataloguedVariantNames = new Set<string>();

export function allVariantsIni(baseIni: string): string {
    return [baseIni, ...Object.values(cataloguedVariantInis)].filter(Boolean).join('\n');
}

export function variantConfigIni(baseIni: string, variantName: string): string {
    const requiredInis: string[] = [];
    const seen = new Set<string>();
    let name = variantName;

    while (name) {
        if (seen.has(name)) {
            console.error(`Cyclic catalogued variant inheritance involving ${name}`);
            break;
        }
        seen.add(name);

        const ini = cataloguedVariantInis[name];
        if (!ini) break;

        requiredInis.push(ini);
        name = cataloguedVariantBaseNames[name] ?? '';
    }

    requiredInis.reverse();
    return [baseIni, ...requiredInis].filter(Boolean).join('\n');
}

export function isCataloguedVariant(name: string | undefined | null): boolean {
    return !!name && cataloguedVariantNames.has(name);
}

function ensureCataloguedBoardFamily(width: number, height: number): keyof typeof BOARD_FAMILIES {
    const safeWidth = Math.max(1, Math.min(16, Math.floor(width || 8)));
    const safeHeight = Math.max(1, Math.min(16, Math.floor(height || 8)));
    const key = `catalogued${safeWidth}x${safeHeight}`;
    if (!BOARD_FAMILIES[key]) {
        BOARD_FAMILIES[key] = {
            dimensions: { width: safeWidth, height: safeHeight },
            cg: `cg-catalogued-${safeWidth}x${safeHeight}`,
            // A concrete file is still needed by the board settings code. The
            // catalogued board CSS below overrides the image with a scalable
            // checkerboard matching the dynamic dimensions.
            boardCSS: ['8x8brown.svg'],
        };
    }
    return key;
}

function cataloguedKingRolesWithPromotions(
    kingRoles: cg.Letter[],
    promotionType: PromotionType,
    promotionRoles: cg.Letter[],
): cg.Letter[] {
    if (promotionType !== 'shogi') return kingRoles;

    const roles = [...kingRoles];
    const seen = new Set<cg.Letter>(roles);
    const promotable = new Set<cg.Letter>(promotionRoles);

    for (const role of kingRoles) {
        if (role.startsWith('+') || !promotable.has(role)) continue;
        const promotedRole = `+${role}` as cg.Letter;
        if (!seen.has(promotedRole)) {
            seen.add(promotedRole);
            roles.push(promotedRole);
        }
    }

    return roles;
}

function cataloguedIniOption(ini: string | undefined, key: string): string | undefined {
    if (!ini) return undefined;
    const wanted = key.toLowerCase();
    for (const line of ini.split(/\r?\n/)) {
        const stripped = line.trim();
        if (!stripped || stripped.startsWith('#') || !stripped.includes('=')) continue;
        const [left, ...right] = stripped.split('=');
        if (left.trim().toLowerCase() !== wanted) continue;
        return right.join('=').split('#', 1)[0].trim();
    }
    return undefined;
}

function cataloguedIniHasOption(ini: string | undefined, key: string): boolean {
    return cataloguedIniOption(ini, key) !== undefined;
}

export function cataloguedShowPromoted(ini: string, startFen: string): boolean {
    // Match server catalogued_show_promoted() for an immutable imported snapshot.
    if (cataloguedIniOption(ini, 'promotedPieceType')) return true;
    if (
        ['pieceDemotion', 'piecePromotionOnCapture', 'dropPromoted'].some(key =>
            /^(true|yes|1|on)$/i.test(cataloguedIniOption(ini, key) ?? ''),
        )
    )
        return true;
    for (const line of ini.split(/\r?\n/)) {
        const metadata = /^\s*[#;]\s*pychessPieces\s*=([^#;]*)/i.exec(line)?.[1];
        if (metadata?.split(/[\s,]+/).some(role => /^\+[a-z]$/i.test(role))) return true;
    }
    return startFen.split(/\s+/, 1)[0].includes('+');
}

function cataloguedDerivedPocketRoles(
    meta: CataloguedVariantClientDocument,
    pieces: cg.Letter[],
    kingRoles: cg.Letter[],
    clientVariant: Variant | undefined,
    hasPocketOverride: boolean,
): cg.Letter[] {
    if (meta.pocketRoles?.length || hasPocketOverride) {
        return (meta.pocketRoles ?? []) as cg.Letter[];
    }

    if (clientVariant?.pocket?.captureToHand) {
        const kingLetters = new Set(kingRoles);
        return pieces.filter(letter => !kingLetters.has(letter));
    }

    return (clientVariant?.pocket?.roles.white.map(role => util.letterOf(role)) ?? []) as cg.Letter[];
}

function cataloguedExplicitPocketRoles(startFen: string): Set<cg.Letter> {
    const pocket = /\[([^\]]*)\]/.exec(startFen)?.[1] ?? '';
    const roles = new Set<cg.Letter>();
    for (const letter of pocket.match(/[A-Za-z]/g) ?? []) addPieceLetter(roles, letter);
    return roles;
}

function cataloguedRenderablePocketRoles(
    meta: CataloguedVariantClientDocument,
    roles: cg.Letter[],
    kingRoles: cg.Letter[],
    captureToHand: boolean,
): cg.Letter[] {
    let renderableRoles = roles;
    if (captureToHand) {
        const explicitPocketRoles = cataloguedExplicitPocketRoles(meta.startFen);
        const royalBaseRoles = new Set(
            kingRoles.map(role => (role.startsWith('+') ? (role.slice(1) as cg.Letter) : role)),
        );
        renderableRoles = roles.filter(role => {
            const baseRole = role.startsWith('+') ? (role.slice(1) as cg.Letter) : role;
            return !royalBaseRoles.has(baseRole) || explicitPocketRoles.has(baseRole);
        });
    }

    const countValue = cataloguedIniOption(meta.ini, 'dropNoDoubledCount');
    const noDoubledRole = normalPieceLetter(cataloguedIniOption(meta.ini, 'dropNoDoubled'));
    if (countValue === undefined || !noDoubledRole) return renderableRoles;

    const noDoubledCount = Number(countValue);
    if (!Number.isFinite(noDoubledCount) || noDoubledCount > 0) return renderableRoles;

    // Fairy-Stockfish rejects this role when the number of pieces already on
    // the file is >= dropNoDoubledCount. A non-positive count therefore makes
    // the role permanently undroppable, even though capturesToHand may still
    // keep it in the engine's pocket FEN.
    renderableRoles = renderableRoles.filter(role => role !== noDoubledRole);
    return renderableRoles;
}

interface CataloguedPieceInfo {
    pieces: cg.Letter[];
    kingRoles: cg.Letter[];
    pocketRoles: cg.Letter[];
    promotionType: PromotionType;
    promotionRoles: cg.Letter[];
    promotionOrder?: PromotionSuffix[];
    clientVariant?: Variant;
}

function normalPieceLetter(letter: string | undefined): cg.Letter | undefined {
    const normalized = (letter ?? '').trim().toLowerCase();
    return /^\+?[a-z]$/.test(normalized) ? (normalized as cg.Letter) : undefined;
}

function addPieceLetter(target: Set<cg.Letter>, letter: string | undefined): void {
    const normalized = normalPieceLetter(letter);
    if (normalized) target.add(normalized);
}

function addPieceLetters(target: Set<cg.Letter>, letters: readonly string[] | undefined): void {
    for (const letter of letters ?? []) addPieceLetter(target, letter);
}

function promotedPieceLetter(letter: string): cg.Letter | undefined {
    const normalized = normalPieceLetter(letter);
    if (!normalized || normalized.startsWith('+')) return normalized;
    return `+${normalized}` as cg.Letter;
}

function cataloguedCustomPieceRoles(ini: string | undefined): Set<cg.Letter> {
    const roles = new Set<cg.Letter>();
    if (!ini) return roles;

    for (const line of ini.split(/\r?\n/)) {
        const stripped = line.trim();
        if (!stripped || stripped.startsWith('#') || !stripped.includes('=')) continue;
        const [left, ...right] = stripped.split('=');
        if (!/^customPiece\d+$/i.test(left.trim())) continue;
        const value = right.join('=').split('#', 1)[0].trim();
        const match = /^([A-Za-z])\s*:/.exec(value);
        addPieceLetter(roles, match?.[1]);
    }

    return roles;
}

const CATALOGUED_PROMOTED_PIECE_PAIR_RE = /([A-Za-z])\s*:\s*([A-Za-z-])/g;

function cataloguedPromotedPieceTypePairs(ini: string | undefined): [cg.Letter, cg.Letter | '-'][] {
    const value = cataloguedIniOption(ini, 'promotedPieceType') ?? '';
    const pairs: [cg.Letter, cg.Letter | '-'][] = [];
    const seen = new Set<cg.Letter>();
    for (const match of value.matchAll(CATALOGUED_PROMOTED_PIECE_PAIR_RE)) {
        const source = normalPieceLetter(match[1]);
        if (!source || source.startsWith('+') || seen.has(source)) continue;
        seen.add(source);
        const rawTarget = match[2].toLowerCase();
        const target = rawTarget === '-' ? '-' : normalPieceLetter(rawTarget);
        if (target) pairs.push([source, target]);
    }
    return pairs;
}

function cataloguedNeedsCustomPieceGlyphs(meta: CataloguedVariantClientDocument, needed: Set<cg.Letter>): boolean {
    const customRoles = cataloguedCustomPieceRoles(meta.ini);
    for (const role of customRoles) {
        if (needed.has(role)) return true;
    }

    if (cataloguedPieceInfo(meta).promotionType !== 'shogi') return false;

    for (const [source, target] of cataloguedPromotedPieceTypePairs(meta.ini)) {
        const promotedSource = promotedPieceLetter(source);
        if (promotedSource && target !== '-' && customRoles.has(target) && needed.has(promotedSource)) {
            return true;
        }
    }

    return false;
}

function cataloguedHasPocketOverride(meta: CataloguedVariantClientDocument): boolean {
    return (
        meta.startFen.includes('[') ||
        [
            'pieceDrops',
            'capturesToHand',
            'whiteDropRegion',
            'blackDropRegion',
            'dropRegionWhite',
            'dropRegionBlack',
        ].some(key => cataloguedIniHasOption(meta.ini, key))
    );
}

function cataloguedCaptureToHand(meta: CataloguedVariantClientDocument, clientVariant: Variant | undefined): boolean {
    return cataloguedIniHasOption(meta.ini, 'capturesToHand')
        ? !!meta.captureToHand
        : !!meta.captureToHand || !!clientVariant?.pocket?.captureToHand;
}

function cataloguedHasPromotionOverride(meta: CataloguedVariantClientDocument): boolean {
    return [
        'promotionPawnTypes',
        'promotionPawnTypesWhite',
        'promotionPawnTypesBlack',
        'promotionPieceTypes',
        'promotionPieceTypesWhite',
        'promotionPieceTypesBlack',
        'promotedPieceType',
        'mandatoryPawnPromotion',
        'mandatoryPiecePromotion',
        'pieceDemotion',
        'piecePromotionOnCapture',
        'dropPromoted',
    ].some(key => cataloguedIniHasOption(meta.ini, key));
}

function cataloguedClientVariantName(meta: CataloguedVariantClientDocument): string | undefined {
    // Ordinary uploaded variants normally have no clientVariant: their real
    // INI base is also the best client fallback. FSF built-ins can override
    // that approximation without corrupting baseVariant's engine semantics.
    return meta.clientVariant || meta.baseVariant || undefined;
}

function cataloguedClientVariant(meta: CataloguedVariantClientDocument): Variant | undefined {
    const name = cataloguedClientVariantName(meta);
    return name ? VARIANTS[name] : undefined;
}

function cataloguedPieceInfo(meta: CataloguedVariantClientDocument): CataloguedPieceInfo {
    const clientVariant = cataloguedClientVariant(meta);
    const pieces = (meta.pieces?.length ? meta.pieces : ['k']) as cg.Letter[];
    let kingRoles = (meta.kingRoles ?? clientVariant?.kingRoles.map(role => util.letterOf(role)) ?? []) as cg.Letter[];
    const hasPocketOverride = cataloguedHasPocketOverride(meta);
    const captureToHand = cataloguedCaptureToHand(meta, clientVariant);
    const pocketRoles = cataloguedRenderablePocketRoles(
        meta,
        cataloguedDerivedPocketRoles(meta, pieces, kingRoles, clientVariant, hasPocketOverride),
        kingRoles,
        captureToHand,
    );
    const hasPromotionOverride = cataloguedHasPromotionOverride(meta);
    const promotionType = hasPromotionOverride
        ? (meta.promotionType ?? 'regular')
        : (clientVariant?.promotion.type ?? meta.promotionType ?? 'regular');
    const promotionRoles = (
        hasPromotionOverride || meta.promotionRoles?.length
            ? (meta.promotionRoles ?? [])
            : (clientVariant?.promotion.roles.map(role => util.letterOf(role)) ?? [])
    ) as cg.Letter[];
    const promotionOrder = meta.promotionOrder?.length
        ? [...meta.promotionOrder]
        : hasPromotionOverride
          ? undefined
          : clientVariant
            ? [...clientVariant.promotion.order]
            : undefined;
    kingRoles = cataloguedKingRolesWithPromotions(kingRoles, promotionType, promotionRoles);

    return { pieces, kingRoles, pocketRoles, promotionType, promotionRoles, promotionOrder, clientVariant };
}

function variantPieceLetters(variant: Variant): Set<cg.Letter> {
    const letters = new Set<cg.Letter>();
    addPieceLetters(
        letters,
        variant.pieceRow.white.map(role => util.letterOf(role)),
    );
    addPieceLetters(
        letters,
        variant.pieceRow.black.map(role => util.letterOf(role)),
    );
    addPieceLetters(
        letters,
        variant.kingRoles.map(role => util.letterOf(role)),
    );
    addPieceLetters(
        letters,
        variant.pocket?.roles.white.map(role => util.letterOf(role)),
    );
    addPieceLetters(
        letters,
        variant.pocket?.roles.black.map(role => util.letterOf(role)),
    );
    if (variant.promotion.type === 'shogi') {
        for (const role of variant.promotion.roles) addPieceLetter(letters, promotedPieceLetter(util.letterOf(role)));
    }
    return letters;
}

type CataloguedPieceIdentityMap = Record<string, string>;

// Piece-set compatibility is stricter than role-letter compatibility: CSS files
// can only render the same letters, but those letters must also depict the
// same piece. Fairy-Stockfish built-ins reuse letters across variants (for
// example c can be Chancellor, Centaur or Champion; n can be Knight,
// Nightrider or Kniroo), so keep the known identities variant-scoped.
const CATALOGUED_PIECE_IDENTITIES_BY_CONTEXT: Record<string, CataloguedPieceIdentityMap> = {
    'pieceFamily:capa': { a: 'archbishop', c: 'chancellor' },
    'pieceFamily:centaur': { a: 'archbishop', c: 'chancellor', g: 'centaur' },
    'pieceFamily:shatranj': { b: 'alfil', q: 'fers' },
    almost: { c: 'chancellor' },
    amazon: { a: 'amazon' },
    berolina: { p: 'berolina-pawn' },
    capablanca: { a: 'archbishop', c: 'chancellor' },
    centaur: { c: 'centaur' },
    chancellor: { c: 'chancellor' },
    chaturanga: { b: 'alfil', q: 'fers' },
    chigorin: { c: 'chancellor' },
    courier: { e: 'alfil', f: 'fers', m: 'commoner', w: 'wazir' },
    extinction: { k: 'commoner' },
    georgian: { a: 'amazon' },
    giveaway: { k: 'commoner' },
    gothic: { a: 'archbishop', c: 'chancellor' },
    grand: { a: 'archbishop', c: 'chancellor' },
    grasshopper: { g: 'grasshopper' },
    gustav3: { a: 'amazon' },
    janus: { j: 'archbishop' },
    knightmate: { m: 'commoner' },
    legan: { p: 'legan-pawn' },
    modern: { m: 'archbishop' },
    newzealand: { n: 'kniroo', r: 'rookni' },
    nightrider: { n: 'nightrider' },
    nocheckatomic: { k: 'commoner' },
    omicron: { c: 'champion', w: 'wizard' },
    opulent: { a: 'archbishop', c: 'chancellor', n: 'marquis', w: 'wizard', l: 'lion' },
    pawnback: { p: 'backward-pawn' },
    pawnsideways: { p: 'sideways-pawn' },
    perfect: { c: 'chancellor', m: 'archbishop', g: 'amazon' },
    petrified: { k: 'commoner' },
    shatar: { j: 'bers' },
    shatranj: { b: 'alfil', q: 'fers' },
    tencubed: { a: 'archbishop', m: 'chancellor', c: 'champion', w: 'wizard' },
    threekings: { k: 'commoner' },
};

const CATALOGUED_FSF_PIECE_OPTION_IDENTITIES: Record<string, string> = {
    king: 'king',
    commoner: 'commoner',
    queen: 'queen',
    rook: 'rook',
    bishop: 'bishop',
    knight: 'knight',
    pawn: 'pawn',
    shogipawn: 'pawn',
    archbishop: 'archbishop',
    chancellor: 'chancellor',
    amazon: 'amazon',
    centaur: 'centaur',
    champion: 'champion',
    wizard: 'wizard',
    marquis: 'marquis',
    lion: 'lion',
    grasshopper: 'grasshopper',
    nightrider: 'nightrider',
    alfil: 'alfil',
    fers: 'fers',
    ferz: 'fers',
    wazir: 'wazir',
    bers: 'bers',
    rookni: 'rookni',
    kniroo: 'kniroo',
};

function cataloguedPieceIdentityDefault(letter: cg.Letter): string {
    const normalized = normalPieceLetter(letter) ?? letter;
    const promoted = normalized.startsWith('+');
    const base = (promoted ? normalized.slice(1) : normalized) as cg.Letter;
    const identity =
        (
            {
                k: 'king',
                q: 'queen',
                r: 'rook',
                b: 'bishop',
                n: 'knight',
                p: 'pawn',
            } as Record<string, string>
        )[base] ?? `letter:${base}`;
    return promoted ? `promoted:${identity}` : identity;
}

function cataloguedPieceIdentityFromMap(
    letter: cg.Letter,
    identities: CataloguedPieceIdentityMap | undefined,
): string | undefined {
    if (!identities) return undefined;
    const normalized = normalPieceLetter(letter) ?? letter;
    const promoted = normalized.startsWith('+');
    const base = promoted ? normalized.slice(1) : normalized;
    const identity = identities[base];
    if (!identity) return undefined;
    return promoted ? `promoted:${identity}` : identity;
}

function cataloguedContextPieceIdentity(
    letter: cg.Letter,
    contextKeys: readonly string[],
    explicitIdentities?: ReadonlyMap<cg.Letter, string>,
): string {
    const normalized = normalPieceLetter(letter) ?? letter;
    const promoted = normalized.startsWith('+');
    const base = (promoted ? normalized.slice(1) : normalized) as cg.Letter;
    const explicit = explicitIdentities?.get(base);
    if (explicit) return promoted ? `promoted:${explicit}` : explicit;

    for (const key of contextKeys) {
        const identity = cataloguedPieceIdentityFromMap(normalized, CATALOGUED_PIECE_IDENTITIES_BY_CONTEXT[key]);
        if (identity) return identity;
    }
    return cataloguedPieceIdentityDefault(normalized);
}

function cataloguedIniPieceIdentityOverrides(ini: string | undefined): Map<cg.Letter, string> {
    const identities = new Map<cg.Letter, string>();
    if (!ini) return identities;

    for (const line of ini.split(/\r?\n/)) {
        const stripped = line.trim();
        if (!stripped || stripped.startsWith('#') || !stripped.includes('=')) continue;
        const [left, ...right] = stripped.split('=');
        const key = left.trim().replace(/[_-]/g, '').toLowerCase();
        if (!key || /^custompiece\d+$/i.test(key)) continue;
        const identity = CATALOGUED_FSF_PIECE_OPTION_IDENTITIES[key];
        if (!identity) continue;

        const value = right.join('=').split('#', 1)[0].trim();
        const match = /^\+?([A-Za-z])(?:\s*:|\s*$)/.exec(value);
        const letter = normalPieceLetter(match?.[1]);
        if (letter) identities.set(letter, identity);
    }

    return identities;
}

function addCataloguedContextKey(keys: string[], seen: Set<string>, key: string | undefined | null): void {
    const normalized = (key ?? '').trim().toLowerCase();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    keys.push(normalized);
}

function cataloguedPieceIdentityContextKeys(meta: CataloguedVariantClientDocument): string[] {
    const keys: string[] = [];
    const seen = new Set<string>();
    addCataloguedContextKey(keys, seen, meta.fsfBuiltinVariant);
    if (meta.source === 'fairy-stockfish-builtin') addCataloguedContextKey(keys, seen, meta.name);
    // Piece identity follows the actual engine inheritance relationship, not
    // clientVariant. A compatibility profile may deliberately reuse a letter
    // for another piece (e.g. Shatar's normal bishop vs Shatranj's Alfil).
    addCataloguedContextKey(keys, seen, meta.baseVariant);

    const baseVariant = meta.baseVariant ? VARIANTS[meta.baseVariant] : undefined;
    addCataloguedContextKey(keys, seen, baseVariant?.name);
    addCataloguedContextKey(keys, seen, baseVariant ? `pieceFamily:${baseVariant.pieceFamily}` : undefined);
    return keys;
}

function variantPieceIdentityContextKeys(variant: Variant): string[] {
    const keys: string[] = [];
    const seen = new Set<string>();
    addCataloguedContextKey(keys, seen, variant.name);
    addCataloguedContextKey(keys, seen, `pieceFamily:${variant.pieceFamily}`);
    return keys;
}

function pieceIdentitiesForLetters(
    letters: Iterable<cg.Letter>,
    contextKeys: readonly string[],
    explicitIdentities?: ReadonlyMap<cg.Letter, string>,
): Set<string> {
    const identities = new Set<string>();
    for (const letter of letters) {
        identities.add(cataloguedContextPieceIdentity(letter, contextKeys, explicitIdentities));
    }
    return identities;
}

function variantPieceIdentities(variant: Variant, letters: Set<cg.Letter>): Set<string> {
    return pieceIdentitiesForLetters(letters, variantPieceIdentityContextKeys(variant));
}

function cataloguedNeededPieceLetters(meta: CataloguedVariantClientDocument): Set<cg.Letter> {
    const info = cataloguedPieceInfo(meta);
    const letters = new Set<cg.Letter>();
    addPieceLetters(letters, info.pieces);
    addPieceLetters(letters, info.kingRoles);
    addPieceLetters(letters, info.pocketRoles);
    if (info.promotionType === 'shogi') {
        for (const role of info.promotionRoles) addPieceLetter(letters, promotedPieceLetter(role));
    }
    return letters;
}

function cataloguedNeededPieceIdentities(meta: CataloguedVariantClientDocument, letters: Set<cg.Letter>): Set<string> {
    return pieceIdentitiesForLetters(
        letters,
        cataloguedPieceIdentityContextKeys(meta),
        cataloguedIniPieceIdentityOverrides(meta.ini),
    );
}

function isSubset<T>(needed: Set<T>, available: Set<T>): boolean {
    for (const value of needed) {
        if (!available.has(value)) return false;
    }
    return needed.size > 0;
}

interface CataloguedCompatiblePieceSource {
    pieceFamily: keyof typeof PIECE_FAMILIES;
    pieceCSSExclude: string[];
    variantName: string;
    roleCount: number;
}

function cataloguedCompatiblePieceSource(
    meta: CataloguedVariantClientDocument,
    options: { ignoreCustomPieceSet?: boolean } = {},
): CataloguedCompatiblePieceSource | undefined {
    if (meta.hasPieceSet && !options.ignoreCustomPieceSet) return undefined;

    if (meta.pieceFamilyOverride && PIECE_FAMILIES[meta.pieceFamilyOverride]) {
        return {
            pieceFamily: meta.pieceFamilyOverride,
            pieceCSSExclude: [],
            variantName: meta.name,
            roleCount: 0,
        };
    }

    const needed = cataloguedNeededPieceLetters(meta);
    // A Fairy-Stockfish customPiece role only tells pychess which FEN letter is
    // used, not that the matching built-in SVG depicts the same piece. Be
    // conservative and keep letter glyphs/custom uploads for variants that need
    // custom-piece roles; otherwise e.g. an unrelated custom "g" can be
    // mistaken for a Shogi gold general.
    if (cataloguedNeedsCustomPieceGlyphs(meta, needed)) return undefined;
    const neededIdentities = cataloguedNeededPieceIdentities(meta, needed);

    const clientVariantName = cataloguedClientVariantName(meta);
    return Object.values(VARIANTS)
        .filter(variant => !cataloguedVariantNames.has(variant.name))
        .map(variant => {
            const roles = variantPieceLetters(variant);
            return { variant, roles, identities: variantPieceIdentities(variant, roles) };
        })
        .filter(({ roles, identities }) => isSubset(needed, roles) && isSubset(neededIdentities, identities))
        .map(({ variant, roles }) => ({
            pieceFamily: variant.pieceFamily,
            pieceCSSExclude: [...variant.pieceCSSExclude],
            variantName: variant.name,
            roleCount: roles.size,
        }))
        .sort((left, right) => {
            if (left.variantName === clientVariantName && right.variantName !== clientVariantName) return -1;
            if (right.variantName === clientVariantName && left.variantName !== clientVariantName) return 1;
            return left.roleCount - right.roleCount || left.pieceCSSExclude.length - right.pieceCSSExclude.length;
        })[0];
}

export function cataloguedCompatiblePieceFamily(
    meta: CataloguedVariantClientDocument,
    options: { ignoreCustomPieceSet?: boolean } = {},
): keyof typeof PIECE_FAMILIES | undefined {
    return cataloguedCompatiblePieceSource(meta, options)?.pieceFamily;
}

function boardFamilyMatchesDimensions(
    boardFamily: keyof typeof BOARD_FAMILIES,
    width: number,
    height: number,
): boolean {
    const dimensions = BOARD_FAMILIES[boardFamily]?.dimensions;
    return !!dimensions && dimensions.width === width && dimensions.height === height;
}

export function cataloguedCompatibleBoardFamily(
    meta: CataloguedVariantClientDocument,
): keyof typeof BOARD_FAMILIES | undefined {
    if (
        meta.boardFamilyOverride &&
        BOARD_FAMILIES[meta.boardFamilyOverride] &&
        boardFamilyMatchesDimensions(meta.boardFamilyOverride, meta.width, meta.height)
    ) {
        return meta.boardFamilyOverride;
    }

    const clientVariant = cataloguedClientVariant(meta);
    if (clientVariant && boardFamilyMatchesDimensions(clientVariant.boardFamily, meta.width, meta.height)) {
        return clientVariant.boardFamily;
    }
    return undefined;
}

export function registerCataloguedVariant(meta: CataloguedVariantClientDocument): void {
    if (!meta?.name) return;
    if (VARIANTS[meta.name] && !cataloguedVariantNames.has(meta.name)) return;

    const info = cataloguedPieceInfo(meta);
    const { pieces, kingRoles, pocketRoles, promotionType, promotionRoles, promotionOrder, clientVariant } = info;
    const captureToHand = cataloguedCaptureToHand(meta, clientVariant);
    const boardFamily = cataloguedCompatibleBoardFamily(meta) ?? ensureCataloguedBoardFamily(meta.width, meta.height);
    const cataloguedPieceFamily = `catalogued-${meta.name}`;
    delete PIECE_FAMILIES[cataloguedPieceFamily];
    const compatiblePieceSource = meta.hasPieceSet
        ? undefined
        : cataloguedCompatiblePieceSource(meta, { ignoreCustomPieceSet: true });
    const pieceFamily = compatiblePieceSource?.pieceFamily ?? cataloguedPieceFamily;
    const customPieceCss = meta.pieceSetRevision ? `custom-${meta.pieceSetRevision}` : 'custom';
    if (pieceFamily === cataloguedPieceFamily) {
        PIECE_FAMILIES[cataloguedPieceFamily] = {
            pieceCSS: meta.hasPieceSet ? [customPieceCss, 'disguised'] : ['disguised'],
        };
    }
    VARIANTS[meta.name] = variant({
        name: meta.name,
        displayName: meta.displayName || meta.name,
        display960: '',
        randomStart: !!meta.randomStart,
        tooltip: meta.tooltip || 'Catalogued variant',
        aiDisabled: !!meta.aiDisabled,
        cataloguedSource: meta.source,
        nnueFingerprint: meta.nnueFingerprint,
        ratingEnabled: false,
        startFen: meta.startFen,
        icon: CATALOGUED_VARIANT_ICON,
        boardFamily,
        hasBoard: !!meta.hasBoard,
        boardRevision: meta.boardRevision,
        pieceFamily,
        pieceCSSExclude: compatiblePieceSource?.pieceCSSExclude,
        pieceRow: pieces,
        kingRoles,
        pocket: pocketRoles.length ? { roles: pocketRoles, captureToHand } : undefined,
        promotion: { type: promotionType, roles: promotionRoles, order: promotionOrder },
        rules: {
            defaultTimeControl: clientVariant?.rules.defaultTimeControl ?? 'incremental',
            enPassant: !!clientVariant?.rules.enPassant,
            gate: !!meta.rulesGate || !!clientVariant?.rules.gate,
            duck: !!clientVariant?.rules.duck,
            arrowing: !!meta.rulesArrowing || !!clientVariant?.rules.arrowing,
            pass: !!meta.rulesPass || !!clientVariant?.rules.pass,
            setup: !!clientVariant?.rules.setup,
            noDrawOffer: !!clientVariant?.rules.noDrawOffer,
        },
        ui: {
            showPromoted: !!meta.showPromoted || !!clientVariant?.ui.showPromoted,
            showCheckCounters: !!meta.showCheckCounters || !!clientVariant?.ui.showCheckCounters,
            counting: clientVariant?.ui.counting,
            materialPoint: clientVariant?.ui.materialPoint,
            pieceSound: clientVariant?.ui.pieceSound,
            boardMark: clientVariant?.ui.boardMark || undefined,
        },
    });
    cataloguedVariantNames.add(meta.name);
    if (meta.favorite) favoriteCataloguedVariantNames.add(meta.name);
    else favoriteCataloguedVariantNames.delete(meta.name);
    if (meta.ini) {
        cataloguedVariantInis[meta.name] = meta.ini;
        cataloguedVariantBaseNames[meta.name] = meta.baseVariant ?? '';
    }
    registerCataloguedPremove(meta);
}

export function unregisterCataloguedVariant(name: string | undefined | null): void {
    if (!name || !cataloguedVariantNames.has(name)) return;
    delete VARIANTS[name];
    delete PIECE_FAMILIES[`catalogued-${name}`];
    delete cataloguedVariantInis[name];
    delete cataloguedVariantBaseNames[name];
    unregisterCataloguedPremove(name);
    cataloguedVariantNames.delete(name);
    favoriteCataloguedVariantNames.delete(name);
}

export function loadCataloguedVariantsFromJson(raw: string | null): void {
    if (!raw) return;
    try {
        const variants = JSON.parse(raw) as CataloguedVariantClientDocument[];
        variants.forEach(registerCataloguedVariant);
    } catch (error) {
        console.error('Failed to load catalogued variants', error);
    }
}

export function disabledVariantsForCreateMode(
    createMode: 'createGame' | 'playFriend' | 'playAI' | 'playBOT' | 'createHost',
    profileid: string,
    anon: boolean,
    botSupportedVariants: ReadonlySet<string> | null = null,
): string[] {
    // Two-board variants are only supported by the dedicated multi-seat lobby flow.
    // Hide them whenever the dialog is being used for invites, profile challenges,
    // bot/AI games, or hosting, where the generic single-board flow is used.
    if (createMode === 'playAI') return [...new Set([...twoBoarsVariants, ...unsupportedAiVariants])];
    if (createMode === 'playBOT') {
        const disabled = new Set(twoBoarsVariants);
        if (botSupportedVariants !== null) {
            Object.values(VARIANTS).forEach(variant => {
                const supportsNormal = botSupportedVariants.has(variant.name);
                const supports960 = variant.chess960 && botSupportedVariants.has(`${variant.name}960`);
                if (!supportsNormal && !supports960) disabled.add(variant.name);
            });
        }
        return [...disabled];
    }
    if (createMode === 'createHost') return twoBoarsVariants;
    if (createMode !== 'createGame') return twoBoarsVariants;
    return anon || profileid !== '' ? twoBoarsVariants : [];
}

export const variantGroups: { [key: string]: { variants: string[] } } = {
    chess: {
        variants: [
            'chess',
            'bughouse',
            'crazyhouse',
            'atomic',
            'kingofthehill',
            '3check',
            'antichess',
            'racingkings',
            'horde',
            'placement',
            'duck',
            'alice',
            'fogofwar',
        ],
    },
    makruk: { variants: ['makruk', 'makbug', 'makpong', 'cambodian', 'sittuyin', 'asean'] },
    shogi: {
        variants: [
            'shogi',
            'shoshogi',
            'minishogi',
            'kyotoshogi',
            'dobutsu',
            'gorogoroplus',
            'torishogi',
            'cannonshogi',
            'yokai',
        ],
    },
    xiangqi: { variants: ['xiangqi', 'supply', 'manchu', 'janggi', 'minixiangqi', 'jieqi'] },
    fairy: {
        variants: [
            'shatranj',
            'capablanca',
            'capahouse',
            'dragon',
            'seirawan',
            'shouse',
            'grand',
            'grandhouse',
            'shako',
            'shogun',
            'hoppelpoppel',
            'mansindam',
        ],
    },
    army: {
        variants: [
            'orda',
            'khans',
            'synochess',
            'shinobiplus',
            'empire',
            'ordamirror',
            'chak',
            'chennis',
            'spartan',
            'xiangfu',
            'cwda',
        ],
    },
    other: { variants: ['borderlands', 'ataxx'] },
};

export function variantGroupLabel(group: string): string {
    return gameCategoryLabel(group);
}

function variantSelectOption(name: string, selected: string | null, disableds: string[]): VNode | null {
    const variant = VARIANTS[name];
    if (!variant) return null;
    return h(
        'option',
        {
            props: { value: name, title: variant.tooltip },
            attrs: { selected: name === selected, disabled: disableds.includes(variant.name) },
        },
        variant.displayName(false),
    );
}

function listedCataloguedVariantNames(): Set<string> {
    return new Set<string>([
        ...Object.values(variantGroups).flatMap(group => group.variants),
        ...favoriteCataloguedVariantNames,
    ]);
}

export function selectVariant(
    id: string,
    selected: string | null,
    onChange: EventListener,
    hookInsert: InsertHook,
    disableds: string[] = [],
    gameCategory: string = 'all',
    emptyLabel?: string,
): VNode {
    const groupedOptions: VNode[] = [];
    if (emptyLabel !== undefined) {
        groupedOptions.push(
            h(
                'option',
                {
                    props: { value: '' },
                    attrs: { selected: !selected },
                },
                emptyLabel,
            ),
        );
    }

    groupedOptions.push(
        ...Object.keys(variantGroups)
            .filter(g => gameCategory === 'all' || g === gameCategory)
            .map(g => {
                const group = variantGroups[g];
                return h(
                    'optgroup',
                    { props: { label: variantGroupLabel(g) } },
                    group.variants
                        .map(v => variantSelectOption(v, selected, disableds))
                        .filter((option): option is VNode => option !== null),
                );
            }),
    );

    const favoriteOptions = [...favoriteCataloguedVariantNames]
        .filter(v => !!VARIANTS[v])
        .sort((left, right) => VARIANTS[left].displayName(false).localeCompare(VARIANTS[right].displayName(false)))
        .map(v => variantSelectOption(v, selected, disableds))
        .filter((option): option is VNode => option !== null);
    if (favoriteOptions.length) {
        groupedOptions.push(h('optgroup', { props: { label: _('Favorite custom variants') } }, favoriteOptions));
    }

    if (
        selected &&
        isCataloguedVariant(selected) &&
        VARIANTS[selected] &&
        !listedCataloguedVariantNames().has(selected)
    ) {
        const option = variantSelectOption(selected, selected, disableds);
        if (option) {
            groupedOptions.push(h('optgroup', { props: { label: _('Selected custom variant') } }, [option]));
        }
    }

    return h(
        'select#' + id,
        {
            props: { name: id },
            on: { change: onChange },
            hook: { insert: hookInsert },
        },
        groupedOptions,
    );
}

// Some variants need to be treated differently according to the FEN.
// Refer to server/fairy.py for more information
export function moddedVariant(
    variantName: string,
    chess960: boolean,
    pieces: cg.Pieces,
    castling: string,
    initialFen: string = '',
): string {
    if (variantName === 'cwda') return cwdaEngineVariant(initialFen);
    if (!chess960 && ['capablanca', 'capahouse'].includes(variantName)) {
        const whiteKing = pieces.get('e1');
        const blackKing = pieces.get('e8');
        const whiteCanCastle =
            castling !== '-' &&
            (castling.includes('K') || castling.includes('Q')) &&
            whiteKing &&
            util.samePiece(whiteKing, { role: 'k-piece', color: 'white' });
        const blackCanCastle =
            castling !== '-' &&
            (castling.includes('k') || castling.includes('q')) &&
            blackKing &&
            util.samePiece(blackKing, { role: 'k-piece', color: 'black' });
        if (whiteCanCastle || blackCanCastle) return variantName.includes('house') ? 'embassyhouse' : 'embassy';
    }
    return variantName;
}

export function getLastMoveFen(variantName: string, lastMove: string, fen: string): [cg.Orig[] | undefined, string] {
    return [uci2LastMove(lastMove), variantName === 'fogofwar' ? fogFen(fen) : fen];
}

// Replace all brick ("*") pieces to be promoted ("*~") to let them CSS style as fog instead of duck
export function fogFen(currentFen: string): string {
    return currentFen.replace(/\*/g, '*~');
}

export function validVariant(variant: string): string {
    return Object.keys(VARIANTS).find(key => key === variant) ?? 'chess';
}

export function splitVariantKey(variantKey: string): { base: string; chess960: boolean } {
    if (isCataloguedVariant(variantKey)) {
        return { base: variantKey, chess960: VARIANTS[variantKey].randomStart };
    }
    if (variantKey.endsWith('960')) {
        return { base: variantKey.slice(0, -3), chess960: true };
    }
    return { base: variantKey, chess960: false };
}

export function variantKey(name: string, chess960: boolean): string {
    return name + (chess960 && !isCataloguedVariant(name) ? '960' : '');
}

export function getVariantByKey(variantKey: string): Variant {
    const { base } = splitVariantKey(variantKey);
    return VARIANTS[base] || VARIANTS['chess'];
}
