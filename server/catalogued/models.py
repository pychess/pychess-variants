"""Shared catalogue types, limits, and configuration constants."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, NotRequired, TypedDict

CATALOGUED_VARIANT_COLLECTION = "catalogued_variant"
CATALOGUED_VARIANT_NAME_COLLECTION = "catalogued_variant_name"
CATALOGUED_CATEGORY = "other"
CATALOGUED_VISIBILITY_PRIVATE = "private"
CATALOGUED_VISIBILITY_UNLISTED = "unlisted"
CATALOGUED_VISIBILITY_PUBLIC = "public"
CATALOGUED_VISIBILITIES = frozenset(
    {CATALOGUED_VISIBILITY_PRIVATE, CATALOGUED_VISIBILITY_UNLISTED, CATALOGUED_VISIBILITY_PUBLIC}
)
CATALOGUED_SOURCE_USER = "user"
CATALOGUED_SOURCE_FSF_BUILTIN = "fairy-stockfish-builtin"
CATALOGUED_FSF_BUILTIN_AUTHOR = "Fairy-Stockfish"
CATALOGUED_COMMUNITY_PAGE_SIZE = 20
CATALOGUED_MANAGEMENT_PAGE_SIZE = 20
MAX_CATALOGUED_VARIANTS_PER_USER = 20
MAX_CATALOGUED_FAVORITES_PER_USER = 500
CATALOGUED_AI_FAILURE_LIMIT = 3
CATALOGUED_AI_DISABLE_SECONDS = 24 * 60 * 60
MAX_CATALOGUED_PIECE_SET_TOTAL_BYTES = 256 * 1024
MAX_CATALOGUED_PIECE_SVG_BYTES = 32 * 1024
MAX_CATALOGUED_BOARD_SVG_BYTES = 128 * 1024
MAX_CATALOGUED_INI_BYTES = 64 * 1024
MAX_DESCRIPTION_LEN = 1000
MAX_DISPLAY_NAME_LEN = 50
MAX_PIECE_NAME_LEN = 50
MAX_PIECE_NAMES_TEXT_LEN = 2048
DISPLAY_NAME_ERROR = (
    f"Display names must be at most {MAX_DISPLAY_NAME_LEN} characters, contain a letter or "
    "number, and use only letters, numbers, spaces, hyphens, underscores, periods, plus signs, "
    "slashes, and parentheses."
)
DISPLAY_NAME_PUNCTUATION = frozenset(" _-.+/()")
DISPLAY_NAME_DISALLOWED_EDGE_SEPARATORS = frozenset(" _-")
DISPLAY_NAME_REPEATED_SEPARATOR_RE = re.compile(r"([ _-])[ _-]+")
UNSUPPORTED_CATALOGUED_BOOL_RULES: dict[str, str] = {
    "twoBoards": "two-board variants need the dedicated bughouse/supply lobby and game flow.",
    "cambodianMoves": "Cambodian/Ouk opening moves need dedicated client-side move input support.",
    "materialCounting": "material counting needs variant-specific adjudication and UI support.",
    "freeDrops": "free drops need dedicated pocket/setup-flow tests.",
}
UNSUPPORTED_CATALOGUED_VALUE_RULES: dict[str, str] = {
    "countingRule": "regional counting needs dedicated adjudication and UI support.",
    "chasingRule": "chasing/perpetual adjudication needs history-aware regional-rule tests.",
}
VARIANT_NAME_ERROR = (
    "Variant names must be 3-32 chars, start with a lowercase letter, "
    "and contain only lowercase letters, digits, hyphens, and underscores."
)
PYCHESS_PIECES_METADATA_KEY = "pychesspieces"


# XBoard/WinBoard presentation and protocol settings do not change gameplay.
CATALOGUED_NON_RULE_OPTIONS = frozenset({"varianttemplate", "piecetochartable", "pocketsize"})
CATALOGUED_PIECE_FAMILY_OVERRIDES = frozenset(
    {
        "aiwok",
        "amazons",
        "asean",
        "ataxx",
        "borderlands",
        "cannonshogi",
        "capa",
        "centaur",
        "chak",
        "chennis",
        "courier",
        "dobutsu",
        "dragon",
        "empire",
        "hoppel",
        "isolation",
        "janggi",
        "khans",
        "kyoto",
        "letter",
        "makruk",
        "mansindam",
        "microshogi",
        "orda",
        "opulent",
        "ordamirror",
        "paradigm",
        "pemba",
        "seirawan",
        "shako",
        "shatranj",
        "shinobi",
        "shogi",
        "shogun",
        "sittuyin",
        "snailtrail",
        "spartan",
        "standard",
        "synochess",
        "tori",
        "xiangfu",
        "xiangqi",
        "yokai",
        "wolf",
        "perfect",
        "decimalshogi",
        "okisakishogi",
    }
)


# Custom piece sets for these Shogi-derived variants use the pointed end of a
# piece to show ownership. A set may upload one canonical player orientation or
# distinct white/black SVGs. Generated CSS derives the missing orientation when
# needed and keeps both players facing correctly after a board flip.
CATALOGUED_DIRECTIONAL_PIECE_BASE_VARIANTS = frozenset(
    {
        "cannonshogi",
        "dobutsu",
        "gorogoro",
        "gorogoroplus",
        "kyotoshogi",
        "minishogi",
        "shogi",
        "shoshogi",
        "torishogi",
        "yokai",
    }
)
CATALOGUED_DIRECTIONAL_PIECE_FAMILIES = frozenset(
    {
        "cannonshogi",
        "decimalshogi",
        "okisakishogi",
        "dobutsu",
        "kyoto",
        "microshogi",
        "mansindam",
        "shogi",
        "tori",
        "yokai",
    }
)


# Keep these static board families in sync with client/variants.ts. Dynamic
# catalogued* checkerboard families are deliberately not valid admin overrides.
CATALOGUED_BOARD_FAMILY_DIMENSIONS: dict[str, tuple[int, int]] = {
    "ataxx7x7": (7, 7),
    "standard8x8": (8, 8),
    "standard9x9": (9, 9),
    "standard10x8": (10, 8),
    "standard10x10": (10, 10),
    "grand10x10": (10, 10),
    "makruk8x8": (8, 8),
    "sittuyin8x8": (8, 8),
    "shogi10x10": (10, 10),
    "shogi9x9": (9, 9),
    "shogi7x7": (7, 7),
    "shogi7x9": (7, 9),
    "shogi6x6": (6, 6),
    "shogi5x5": (5, 5),
    "shogi4x5": (4, 5),
    "shogi5x6": (5, 6),
    "shogi3x4": (3, 4),
    "xiangqi9x10": (9, 10),
    "xiangqi7x7": (7, 7),
    "janggi9x10": (9, 10),
    "shogun8x8": (8, 8),
    "chak9x9": (9, 9),
    "chennis7x7": (7, 7),
    "xiangfu9x9": (9, 9),
    "borderlands9x10": (9, 10),
}
CATALOGUED_BOARD_FAMILY_OVERRIDES = frozenset(CATALOGUED_BOARD_FAMILY_DIMENSIONS)
CATALOGUED_CHESS_PROMOTION_ORDER = ("q", "r", "b", "n")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FSF_CHECK_TIMEOUT_SECONDS = 8.0


class VariantSectionMatch(NamedTuple):
    start: int
    end: int
    name: str
    suffix: str


class CataloguedVariantValidation(NamedTuple):
    name: str
    start_fen: str
    width: int
    height: int
    pieces: list[str]
    king_roles: list[str]
    pocket_roles: list[str]
    capture_to_hand: bool
    promotion_type: str
    promotion_roles: list[str]
    promotion_order: list[str]
    show_promoted: bool
    rules_gate: bool
    rules_pass: bool
    legal_moves_need_history: bool
    n_fold_is_draw: bool
    show_check_counters: bool
    base_variant: str


class CataloguedVariantPieceSetSvg(TypedDict):
    svg: str
    size: int


class CataloguedVariantBoardSvg(TypedDict):
    svg: str
    size: int


class CataloguedVariantReference(TypedDict):
    label: str
    url: str


class CataloguedVariantDocument(TypedDict):
    _id: str
    name: str
    displayName: str
    description: NotRequired[str]
    pieceNames: NotRequired[dict[str, str]]
    author: str
    ini: str
    rulesIni: NotRequired[str]
    dropLoop: NotRequired[bool]
    baseVariant: str
    clientVariant: NotRequired[str]
    premoveVariant: NotRequired[str]
    enabled: bool
    archived: bool
    startFen: str
    width: int
    height: int
    pieces: list[str]
    kingRoles: list[str]
    pocketRoles: list[str]
    captureToHand: bool
    promotionType: str
    promotionRoles: list[str]
    promotionOrder: list[str]
    promotionOrderByColor: NotRequired[dict[str, list[str]]]
    showPromoted: bool
    rulesGate: bool
    rulesPass: bool
    rulesArrowing: bool
    legalMovesNeedHistory: bool
    nFoldIsDraw: bool
    showCheckCounters: bool
    category: str
    visibility: str
    source: NotRequired[str]
    fsfBuiltinVariant: NotRequired[str]
    pieceFamilyOverride: NotRequired[str]
    boardFamilyOverride: NotRequired[str]
    pieceSetDirectional: bool
    references: NotRequired[list[CataloguedVariantReference]]
    pieceSet: NotRequired[dict[str, CataloguedVariantPieceSetSvg]]
    pieceSetUpdatedAt: NotRequired[datetime]
    boardSvg: NotRequired[CataloguedVariantBoardSvg]
    boardSvgUpdatedAt: NotRequired[datetime]
    aiFailureCount: NotRequired[int]
    aiLastFailureAt: NotRequired[datetime]
    aiLastFailureReason: NotRequired[str]
    aiDisabledAt: NotRequired[datetime]
    aiDisabledUntil: NotRequired[datetime]
    aiDisabledReason: NotRequired[str]
    gameCount: int
    favoriteCount: int
    gameCountEffectIds: NotRequired[list[str]]
    createdAt: datetime
    updatedAt: datetime


class CataloguedVariantClientDocument(TypedDict):
    name: str
    dropLoop: NotRequired[bool]
    displayName: str
    tooltip: str
    pieceNames: NotRequired[dict[str, str]]
    betzaPieces: NotRequired[dict[str, str]]
    ini: str
    baseVariant: str
    clientVariant: NotRequired[str]
    premoveVariant: NotRequired[str]
    startFen: str
    randomStart: NotRequired[bool]
    width: int
    height: int
    pieces: list[str]
    kingRoles: list[str]
    pocketRoles: list[str]
    captureToHand: bool
    promotionType: str
    promotionRoles: list[str]
    promotionOrder: list[str]
    promotionOrderByColor: NotRequired[dict[str, list[str]]]
    showPromoted: bool
    rulesGate: bool
    rulesPass: bool
    rulesArrowing: bool
    showCheckCounters: bool
    category: str
    author: NotRequired[str]
    source: NotRequired[str]
    system: NotRequired[bool]
    nnueFingerprint: NotRequired[str]
    fsfBuiltinVariant: NotRequired[str]
    pieceFamilyOverride: NotRequired[str]
    boardFamilyOverride: NotRequired[str]
    references: NotRequired[list[CataloguedVariantReference]]
    archived: NotRequired[bool]
    enabled: NotRequired[bool]
    gameCount: NotRequired[int]
    favoriteCount: NotRequired[int]
    locked: NotRequired[bool]
    visibility: NotRequired[str]
    aiDisabled: NotRequired[bool]
    replayOnly: NotRequired[bool]
    aiDisabledReason: NotRequired[str]
    aiDisabledUntil: NotRequired[datetime]
    favorite: NotRequired[bool]
    pieceSetDirectional: NotRequired[bool]
    directionalPieceSet: NotRequired[bool]
    hasPieceSet: NotRequired[bool]
    pieceSetRevision: NotRequired[str]
    hasBoard: NotRequired[bool]
    boardRevision: NotRequired[str]


CATALOGUED_METADATA_OPTIONAL_FIELDS = (
    "pieceNames",
    "pieceFamilyOverride",
    "boardFamilyOverride",
    "icon",
)
CATALOGUED_CONCURRENTLY_UPDATED_FIELDS = frozenset(
    {
        "_id",
        "createdAt",
        "gameCount",
        "favoriteCount",
        "pieceSet",
        "pieceSetUpdatedAt",
        "boardSvg",
        "boardSvgUpdatedAt",
        "aiFailureCount",
        "aiLastFailureAt",
        "aiLastFailureReason",
        "aiDisabledAt",
        "aiDisabledUntil",
        "aiDisabledReason",
    }
)
