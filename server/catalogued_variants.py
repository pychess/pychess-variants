from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple, NotRequired, TypedDict, cast
from urllib.parse import unquote, urlparse

import aiohttp_session
from aiohttp import web
from catalogued_betza import catalogued_betza_diagrams, catalogued_betza_pieces
from catalogued_rules import catalogued_random_start, catalogued_rule_summary
from compress import MAX_COMPRESSED_BOARD_HEIGHT, MAX_COMPRESSED_BOARD_WIDTH
from const import ANON_PREFIX, STARTED, T_STARTED
from fairy.fairy_board import sf
from json_utils import json_response
from nnue_identity import fsf_ini_v1_fingerprint
from pychess_global_app_state_utils import get_app_state
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from request_utils import read_json_data, read_post_data, read_text_data
from settings import ADMINS
from variants import (
    CATALOGUED_VARIANTS,
    CataloguedServerVariant,
    ServerVariants,
    get_server_variant,
    is_catalogued_variant,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)

log = logging.getLogger(__name__)

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
        "janggi",
        "khans",
        "kyoto",
        "letter",
        "makruk",
        "mansindam",
        "orda",
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
        "spartan",
        "standard",
        "synochess",
        "tori",
        "xiangfu",
        "xiangqi",
        "yokai",
        "perfect",
        "decimalshogi",
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
        "dobutsu",
        "kyoto",
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
    "shogi9x9": (9, 9),
    "shogi7x7": (7, 7),
    "shogi7x9": (7, 9),
    "shogi6x6": (6, 6),
    "shogi5x5": (5, 5),
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
FSF_CATALOGUED_BUILTIN_DESCRIPTION = (
    "Fairy-Stockfish built-in variant exposed as a casual community variant."
)


def _reference_label_for_url(url: str) -> str:
    host = urlparse(url).netloc.casefold().removeprefix("www.")
    if not host:
        return "Reference"
    if host.endswith("wikipedia.org"):
        return "Wikipedia"
    if host == "chessvariants.com":
        return "Chess Variant Pages"
    if host == "chessclub.com":
        return "ICC help"
    if host == "freechess.org":
        return "FICS help"
    if host == "arxiv.org":
        return "arXiv"
    if host == "github.com":
        return "GitHub"
    if host == "web.archive.org":
        return "Archived rules"
    if host == "binnewirtz.com":
        return "Binnewirtz"
    if host == "kotesovec.cz":
        return "Kotesovec"
    return host


def _fsf_builtin_references(*urls: str) -> tuple[dict[str, str], ...]:
    return tuple({"label": _reference_label_for_url(url), "url": url} for url in urls)


# Curated subset of Fairy-Stockfish built-ins that pychess exposes through the
# community/user-defined variant UI. Keep this list intentionally conservative
# and add entries only after the board, pieces, move input, analysis and
# saved-game paths have been tested on pychess. The catalogue entry name must
# remain the real Fairy-Stockfish UCI_Variant key so matching NNUE files can
# still be used.
#
# Avoid aliases/internal helpers, variants that need custom move encoding
# (duck/walling/flipping), setup/drop/gating flows, two-board flows, covered
# information, side-specific promotion UI, or regional adjudication that needs
# first-class client support. Admins can still fill in display metadata and
# upload piece/board SVGs for entries in this allowlist.
#
# Metadata relationship fields have deliberately separate responsibilities:
#
# * ``baseVariant`` describes Fairy-Stockfish rule inheritance. It names the
#   registered Fairy-Stockfish variant whose constructor is the direct parent in
#   variant.cpp. If the C++ constructor starts from an unregistered internal
#   helper such as ``chess_variant_base()``, ``minishogi_variant_base()`` or
#   ``variant_base()``, leave it empty rather than inventing a related variant.
#   Server-side rule/Betza inheritance may rely on this field.
# * ``clientVariant`` is an optional pychess-only compatibility profile. It is
#   the closest existing first-class site variant for general client defaults
#   such as promotion/pocket/rules UI and board/piece-family preference. It MUST
#   NOT be used as Fairy-Stockfish inheritance or authoritative rule docs. When
#   omitted, the client may fall back to ``baseVariant``.
# * ``premoveVariant`` is an even narrower optional chessground fallback. Set it
#   only when premove geometry is better represented by another first-class
#   variant than ``clientVariant`` (for example Grand-style pawn start ranks on
#   a variant whose other client defaults are Chess-like).
#
# More specific visual choices still belong in ``pieceFamilyOverride`` /
# ``boardFamilyOverride``; Betza movement exceptions belong in catalogued_betza.
FSF_CATALOGUED_BUILTIN_VARIANTS: Mapping[str, Mapping[str, Any]] = {
    "5check": {
        "displayName": "Five-Check Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "3check",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
        "showCheckCounters": True,
    },
    "almost": {
        "displayName": "Almost Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Almost_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("c", "r", "b", "n"),
    },
    "amazon": {
        "displayName": "Amazon Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/diffmove.dir/amazone.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("a", "r", "b", "n"),
    },
    "amazons": {
        "displayName": "Game of the Amazons",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Game_of_the_Amazons",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "pieceFamilyOverride": "amazons",
        "rulesArrowing": True,
    },
    "atomar": {
        "displayName": "Atomar",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://web.archive.org/web/20230519082613/"
            "https://chronatog.com/wp-content/uploads/2021/09/"
            "atomar-chess-rules.pdf",
        ),
        "baseVariant": "nocheckatomic",
        "clientVariant": "atomic",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "berolina": {
        "displayName": "Berolina Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/dpieces.dir/berlin.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "centaur": {
        "displayName": "Centaur Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/large.dir/contest/royalcourt.html",
        ),
        "baseVariant": "",
        "clientVariant": "capablanca",
        "promotionRoles": ("p",),
        "promotionOrder": ("c", "q", "r", "b", "n"),
    },
    "chancellor": {
        "displayName": "Chancellor Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Chancellor_chess"),
        "baseVariant": "",
        "clientVariant": "capablanca",
        "promotionRoles": ("p",),
        "promotionOrder": ("c", "q", "r", "b", "n"),
    },
    "chaturanga": {
        "displayName": "Chaturanga",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Chaturanga"),
        "baseVariant": "shatranj",
    },
    "codrus": {
        "displayName": "Codrus",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("http://www.binnewirtz.com/Schlagschach1.htm"),
        "baseVariant": "giveaway",
        "clientVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "coregal": {
        "displayName": "Coregal Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/winning.dir/coregal.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "kingRoles": ("k", "q"),
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "courier": {
        "displayName": "Courier Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Courier_chess"),
        "baseVariant": "",
        "clientVariant": "shatranj",
        "promotionRoles": ("p",),
        "promotionOrder": ("f",),
    },
    "extinction": {
        "displayName": "Extinction Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Extinction_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("k", "q", "r", "b", "n"),
    },
    "gardner": {
        "displayName": "Gardner Minichess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Minichess#5%C3%975_chess",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "georgian": {
        "displayName": "Georgian Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "amazon",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("a", "r", "b", "n"),
    },
    "giveaway": {
        "displayName": "Giveaway Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/diffobjective.dir/giveaway.old.html",
        ),
        "baseVariant": "",
        "clientVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": ("k", "q", "r", "b", "n"),
    },
    "grasshopper": {
        "displayName": "Grasshopper Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Grasshopper_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("q", "r", "b", "n", "g"),
    },
    "janus": {
        "displayName": "Janus Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Janus_Chess"),
        "baseVariant": "",
        "clientVariant": "capablanca",
        "promotionRoles": ("p",),
        "promotionOrder": ("j", "q", "r", "b", "n"),
    },
    "joust": {
        "displayName": "Joust",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/programs.dir/joust.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "rulesArrowing": True,
    },
    "judkins": {
        "displayName": "Judkins Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Judkins_shogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "boardFamilyOverride": "shogi6x6",
        "captureToHand": True,
        "promotionType": "shogi",
        "promotionRoles": ("p", "n", "s", "b", "r"),
        "promotionOrder": ("+", ""),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
    },
    "kinglet": {
        "displayName": "Kinglet",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/V._R._Parton#Kinglet_chess",
        ),
        "baseVariant": "extinction",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("k",),
    },
    "knightmate": {
        "displayName": "Knightmate",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/diffobjective.dir/knightmate.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("m", "q", "r", "b"),
    },
    "legan": {
        "displayName": "Legan Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Legan_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "losalamos": {
        "displayName": "Los Alamos Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Los_Alamos_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("q", "r", "n"),
    },
    "losers": {
        "displayName": "Losers Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessclub.com/help/Wild17"),
        "baseVariant": "",
        "clientVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "misere": {
        "displayName": "Misère Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("http://www.kotesovec.cz/gustav/gustav_alybadix.htm"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "modern": {
        "displayName": "Modern Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Modern_chess"),
        "baseVariant": "",
        "clientVariant": "capablanca",
        "promotionRoles": ("p",),
        "promotionOrder": ("m", "q", "r", "b", "n"),
    },
    "newzealand": {
        "displayName": "New Zealand Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nightrider": {
        "displayName": "Nightrider Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Nightrider_(chess)"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nocastle": {
        "displayName": "No-Castle Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nocheckatomic": {
        "displayName": "No-Check Atomic",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessclub.com/help/atomic"),
        "baseVariant": "",
        "clientVariant": "atomic",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "opulent": {
        "displayName": "Opulent Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessvariants.com/rules/opulent-chess"),
        "baseVariant": "grand",
        "promotionRoles": ("p",),
        "promotionOrder": ("q", "r", "b", "a", "c", "n", "w", "l"),
    },
    "pawnback": {
        "displayName": "Pawnback Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://arxiv.org/abs/2009.04374"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "pawnsideways": {
        "displayName": "Pawnsideways Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://arxiv.org/abs/2009.04374"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "paradigm": {
        "displayName": "Paradigm Chess30",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/rules/paradigm-chess30",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "pieceNames": {"b": "Dragon Bishop"},
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "perfect": {
        "displayName": "Perfect Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/diffmove.dir/perfectchess.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("g", "c", "m", "q", "r", "b", "n"),
    },
    "shatar": {
        "displayName": "Shatar",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Shatar"),
        "baseVariant": "",
        "clientVariant": "shatranj",
        "promotionRoles": ("p",),
        "promotionOrder": ("j",),
    },
    "suicide": {
        "displayName": "Suicide Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.freechess.org/Help/HelpFiles/suicide_chess.html",
        ),
        "baseVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": ("k", "q", "r", "b", "n"),
    },
    "tencubed": {
        "displayName": "Ten Cubed Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/contests/10/tencubedchess.html",
        ),
        "baseVariant": "",
        "clientVariant": "grand",
        "promotionRoles": ("p",),
        "promotionOrder": ("a", "m", "q"),
    },
    "threekings": {
        "displayName": "Three Kings",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://github.com/cutechess/cutechess/blob/master/"
            "projects/lib/src/board/threekingsboard.h",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "torpedo": {
        "displayName": "Torpedo Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://arxiv.org/abs/2009.04374"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "raazuvaa": {
        "displayName": "Raazuvaa",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "",
        "clientVariant": "chess",
    },
    "gustav3": {
        "displayName": "Gustav III Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/play/gustav-iiis-chess",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": ("a", "q", "r", "b", "n"),
    },
    "troitzky": {
        "displayName": "Troitzky Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/play/troitzky-chess",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "premoveVariant": "grand",
    },
    "omicron": {
        "displayName": "Omicron Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "http://www.eglebbk.dds.nl/program/chess-omicron.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "premoveVariant": "grand",
        "promotionRoles": ("p",),
        "promotionOrder": ("w", "c", "q", "r", "b", "n"),
    },
    "petrified": {
        "displayName": "Petrified",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chess.com/variants/petrified"),
        "baseVariant": "pawnsideways",
        "clientVariant": "chess",
    },
    "pocketknight": {
        "displayName": "Pocket Knight Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/other.dir/pocket.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
    },
    "yarishogi": {
        "displayName": "Yari Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Yari_shogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "captureToHand": True,
        "promotionType": "shogi",
        "promotionRoles": ("p", "n", "b", "r"),
        "promotionOrder": ("+", ""),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation-only transcription of the built-in C++ definition.
        # Runtime engine/client paths must continue to use the canonical
        # Fairy-Stockfish built-in name and the empty ``ini`` field.
        "rulesIni": """\
[yarishogi]
maxRank = 9
maxFile = 7
startFen = rnnkbbr/7/ppppppp/7/7/7/PPPPPPP/7/RBBKNNR[-] w 0 1
shogiPawn = p
rook = l
customPiece1 = n:fRffN  # Yari knight
customPiece2 = b:fFfR   # Yari bishop
customPiece3 = r:frlR   # Yari rook
customPiece4 = g:WfFbR  # Yari gold
customPiece5 = s:fKbR   # Yari silver
promotionRegionWhite = *7 *8 *9
promotionRegionBlack = *1 *2 *3
promotedPieceType = p:s n:g b:g r:l
pieceDrops = true
capturesToHand = true
doubleStep = false
castling = false
dropNoDoubled = p
immobilityIllegal = true
shogiPawnDropMateIllegal = false
stalemateValue = loss
nFoldRule = 3
nMoveRule = 0
perpetualCheckIllegal = true
""",
    },
}


# Structured backlog of Fairy-Stockfish built-ins that are not currently
# first-class pychess variants and are not seeded through
# FSF_CATALOGUED_BUILTIN_VARIANTS above. This constant is deliberately unused by
# the runtime seeding path: entries here are candidates for future review only.
#
# To enable one, move/copy its metadata to FSF_CATALOGUED_BUILTIN_VARIANTS and
# test the complete pychess flow first: game creation, move input, replay,
# analysis, fishnet/AI, piece-set compatibility, rules text, board preview,
# clocks/byo where relevant, and saved-game export/import. Some entries are
# aliases, internal helpers, drop/setup variants, pass/wall/flipping games, or
# regionally adjudicated rule sets, so presence here does not imply that the
# variant is safe or useful to expose.
FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES: Mapping[str, Mapping[str, Any]] = {
    "ai-wok": {
        "displayName": "Ai-Wok",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "makruk",
        "reviewNotes": "Makruk-family fairy-piece variant; review pieces and promotion UI.",
    },
    "armageddon": {
        "displayName": "Armageddon Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Fast_chess#Armageddon",
        ),
        "baseVariant": "chess",
        "reviewNotes": "Likely needs time-odds/draw-odds UI before exposing.",
    },
    "breakthrough": {
        "displayName": "Breakthrough",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Breakthrough_(board_game)",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Non-checkmate objective; verify result handling and notation.",
    },
    "caparandom": {
        "displayName": "Capablanca Random Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Capablanca_random_chess",
        ),
        "baseVariant": "capablanca",
        "reviewNotes": "Shuffle variant; pychess already has first-class Caparandom support.",
    },
    "checkshogi": {
        "displayName": "Check-Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "shogi",
        "reviewNotes": "Shogi-family check-counting variant; review byo/check-counter UI.",
    },
    "chigorin": {
        "displayName": "Chigorin Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://www.chessvariants.com/diffsetup.dir/chigorin.html",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": (
            "Fairy-Stockfish has side-specific promotion targets (White: c/r/n; "
            "Black: q/r/b). Keep out of the allowlist until catalogued promotion "
            "UI can model that explicitly."
        ),
    },
    "chessgi": {
        "displayName": "Chessgi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Crazyhouse#Variations",
        ),
        "baseVariant": "loop",
        "clientVariant": "crazyhouse",
        "reviewNotes": "Drop variant with changed pawn-drop rules; review pocket/drop UI.",
    },
    "clobber": {
        "displayName": "Clobber",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Clobber"),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Non-chess game; verify pass/stalemate/objective handling.",
    },
    "clobber10": {
        "displayName": "Clobber 10x10",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Clobber"),
        "baseVariant": "clobber",
        "reviewNotes": "Large-board non-chess game; verify board sizing and objective handling.",
    },
    "euroshogi": {
        "displayName": "EuroShogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/EuroShogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "reviewNotes": "Shogi-family drops/promotions; review piece assets and byo UI.",
    },
    "fairy": {
        "displayName": "Fairy",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Internal helper used by Fairy-Stockfish endgame initialization; do not expose.",
    },
    "fischerandom": {
        "displayName": "Fischer Random Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Fischer_random_chess",
        ),
        "baseVariant": "chess",
        "reviewNotes": "Alias of Chess960; pychess already exposes this as Chess960.",
    },
    "flipello": {
        "displayName": "Flipello",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Reversi#Othello",
        ),
        "baseVariant": "flipersi",
        "reviewNotes": "Reversi-like placement game; verify pass/drop-like move flow.",
    },
    "flipello10": {
        "displayName": "Flipello 10x10",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Reversi"),
        "baseVariant": "flipello",
        "reviewNotes": "Large-board Reversi-like placement game; verify pass/drop-like move flow.",
    },
    "flipersi": {
        "displayName": "Flipersi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Reversi"),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Reversi-like placement game; verify pass/drop-like move flow.",
    },
    "fox-and-hounds": {
        "displayName": "Fox and Hounds",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/148180/fox-and-hounds",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Asymmetric non-capturing game; verify result handling and pieces.",
    },
    "gorogoro": {
        "displayName": "Gorogoro Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/D%C5%8Dbutsu_sh%C5%8Dgi#Variation",
        ),
        "baseVariant": "",
        "clientVariant": "shogi",
        "reviewNotes": "Pychess exposes Gorogoro+ separately; compare rule differences first.",
    },
    "isolation": {
        "displayName": "Isolation",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/1875/isolation",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Non-chess blocking game; verify move encoding and result handling.",
    },
    "isolation7x7": {
        "displayName": "Isolation 7x7",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/1875/isolation",
        ),
        "baseVariant": "isolation",
        "reviewNotes": "Non-chess blocking game; verify move encoding and result handling.",
    },
    "janggicasual": {
        "displayName": "Janggi Casual",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "reviewNotes": "Janggi rule-set alias/variant; compare with existing pychess Janggi support.",
    },
    "janggimodern": {
        "displayName": "Janggi Modern",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "reviewNotes": "Janggi rule-set alias/variant; compare with existing pychess Janggi support.",
    },
    "janggitraditional": {
        "displayName": "Janggi Traditional",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "reviewNotes": "Janggi rule-set alias/variant; compare with existing pychess Janggi support.",
    },
    "jesonmor": {
        "displayName": "Jeson Mor",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Jeson_Mor"),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Asymmetric goal variant; review result handling and piece identities.",
    },
    "karouk": {
        "displayName": "Kar Ouk",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Makruk#Ka_Ouk",
        ),
        "baseVariant": "cambodian",
        "reviewNotes": "Cambodian/Makruk-family first-check-wins variant; review adjudication/UI.",
    },
    "koedem": {
        "displayName": "Koedem",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "http://schachclub-oetigheim.de/wp-content/uploads/2016/04/Koedem-rules.pdf",
        ),
        "baseVariant": "bughouse",
        "reviewNotes": "Bughouse-family/two-board variant; not suitable for catalogued flow yet.",
    },
    "loop": {
        "displayName": "Loop Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Crazyhouse#Variations",
        ),
        "baseVariant": "crazyhouse",
        "reviewNotes": "Drop variant; review pocket/drop UI and promoted-piece capture behavior.",
    },
    "micro": {
        "displayName": "Micro Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Micro_shogi"),
        "baseVariant": "kyotoshogi",
        "reviewNotes": "Kyoto-style flipping/demotion mechanics; review move encoding/UI.",
    },
    "mini": {
        "displayName": "Mini Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "",
        "clientVariant": "minishogi",
        "reviewNotes": "Alias of Minishogi; pychess already exposes Minishogi.",
    },
    "normal": {
        "displayName": "Normal Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Alias of standard chess; pychess already exposes Chess.",
    },
    "okisakishogi": {
        "displayName": "Okisaki Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Okisaki_shogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "reviewNotes": "Shogi-family drops/promotions; review piece assets and byo UI.",
    },
    "snailtrail": {
        "displayName": "Snail Trail",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/37135/snailtrail",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "Non-chess blocking game; verify move encoding and result handling.",
    },
    "sortofalmost": {
        "displayName": "Sort-of-Almost Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Almost_chess#Sort_of_almost_chess",
        ),
        "baseVariant": "chess",
        "reviewNotes": "Asymmetric Almost Chess variant; verify pieces and castling assumptions.",
    },
    "wolf": {
        "displayName": "Wolf Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Wolf_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "reviewNotes": "10x8 fairy-piece variant; review piece identities and promotion UI.",
    },
}

# Built-ins that were seeded in production before a later audit found that the
# generic catalogued client cannot represent their rules safely. Keep this
# explicit instead of silently leaving an old MongoDB document enabled after
# moving the metadata back to the candidate list.
FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS = frozenset({"chigorin"})


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FSF_CHECK_TIMEOUT_SECONDS = 8.0
BUILTIN_VARIANT_NAMES = frozenset(variant.server_name for variant in ServerVariants)
BUILTIN_FSF_VARIANT_NAMES = frozenset(sf.variants())


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
    aiDisabledReason: NotRequired[str]
    aiDisabledUntil: NotRequired[datetime]
    favorite: NotRequired[bool]
    pieceSetDirectional: NotRequired[bool]
    directionalPieceSet: NotRequired[bool]
    hasPieceSet: NotRequired[bool]
    pieceSetRevision: NotRequired[str]
    hasBoard: NotRequired[bool]
    boardRevision: NotRequired[str]


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def _is_active_catalogued_doc(doc: Mapping[str, Any]) -> bool:
    return bool(doc.get("enabled", True)) and not bool(doc.get("archived", False))


def _catalogued_visibility(doc: Mapping[str, Any]) -> str:
    visibility = str(doc.get("visibility") or CATALOGUED_VISIBILITY_PRIVATE).strip().lower()
    return visibility if visibility in CATALOGUED_VISIBILITIES else CATALOGUED_VISIBILITY_PRIVATE


def _catalogued_source(doc: Mapping[str, Any]) -> str:
    source = str(doc.get("source") or CATALOGUED_SOURCE_USER).strip().lower()
    if source == CATALOGUED_SOURCE_FSF_BUILTIN:
        return CATALOGUED_SOURCE_FSF_BUILTIN
    return CATALOGUED_SOURCE_USER


def _clean_piece_family_override(piece_family: str | None) -> str:
    cleaned = str(piece_family or "").strip().lower()
    if cleaned in {"", "auto", "auto-detect", "autodetect"}:
        return ""
    if cleaned not in CATALOGUED_PIECE_FAMILY_OVERRIDES:
        raise web.HTTPBadRequest(text="Unknown catalogued piece-set override.")
    return cleaned


def _read_piece_family_override(data: Mapping[str, Any]) -> str:
    # Treat an explicit empty modern field as a request to clear the override.
    # Do not let a stale legacy snake_case value revive an old override when the
    # admin selects "Auto-detect" in the current UI.
    if "pieceFamilyOverride" in data:
        value = data.get("pieceFamilyOverride")
    else:
        value = data.get("piece_family_override")
    return _clean_piece_family_override(str(value or ""))


def _read_bool_metadata(data: Mapping[str, Any], key: str, legacy_key: str) -> bool | None:
    if key in data:
        value = data.get(key)
    elif legacy_key in data:
        value = data.get(legacy_key)
    else:
        return None
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    raise web.HTTPBadRequest(text=f"Invalid {key} metadata. Use true or false.")


def _catalogued_piece_family_override(doc: Mapping[str, Any]) -> str:
    try:
        return _clean_piece_family_override(str(doc.get("pieceFamilyOverride") or ""))
    except web.HTTPBadRequest:
        return ""


def _catalogued_client_variant_name(doc: Mapping[str, Any]) -> str:
    """Return the pychess client fallback profile for a catalogued variant.

    ``baseVariant`` is rule inheritance and must stay faithful to
    Fairy-Stockfish. ``clientVariant`` is deliberately separate: it is only a
    pychess compatibility hint for client-side defaults. Ordinary uploaded
    variants normally omit it, in which case their real INI base is also the
    natural client fallback.
    """

    return str(doc.get("clientVariant") or doc.get("baseVariant") or "").strip().lower()


def _catalogued_piece_set_is_directional(doc: Mapping[str, Any]) -> bool:
    """Whether custom pieces must keep pointing toward the opponent."""
    if bool(doc.get("pieceSetDirectional", False)):
        return True
    client_variant = _catalogued_client_variant_name(doc)
    if client_variant in CATALOGUED_DIRECTIONAL_PIECE_BASE_VARIANTS:
        return True
    return _catalogued_piece_family_override(doc) in CATALOGUED_DIRECTIONAL_PIECE_FAMILIES


def _clean_board_family_override(board_family: str | None) -> str:
    cleaned = str(board_family or "").strip().lower()
    if cleaned in {"", "auto", "auto-detect", "autodetect"}:
        return ""
    if cleaned not in CATALOGUED_BOARD_FAMILY_OVERRIDES:
        raise web.HTTPBadRequest(text="Unknown catalogued board-style override.")
    return cleaned


def _read_board_family_override(data: Mapping[str, Any]) -> str:
    if "boardFamilyOverride" in data:
        value = data.get("boardFamilyOverride")
    else:
        value = data.get("board_family_override")
    return _clean_board_family_override(str(value or ""))


def _catalogued_board_family_override(doc: Mapping[str, Any]) -> str:
    try:
        return _clean_board_family_override(str(doc.get("boardFamilyOverride") or ""))
    except web.HTTPBadRequest:
        return ""


def _ensure_board_family_dimensions(board_family: str, width: int, height: int) -> None:
    if not board_family:
        return
    expected_width, expected_height = CATALOGUED_BOARD_FAMILY_DIMENSIONS[board_family]
    if (width, height) != (expected_width, expected_height):
        raise web.HTTPBadRequest(
            text=(
                f'Board style "{board_family}" requires a '
                f"{expected_width}x{expected_height} board, not {width}x{height}."
            )
        )


def _is_fsf_builtin_catalogued_doc(doc: Mapping[str, Any]) -> bool:
    return _catalogued_source(doc) == CATALOGUED_SOURCE_FSF_BUILTIN


def _catalogued_description(doc: Mapping[str, Any]) -> str:
    description = str(doc.get("description") or "")
    if description or not _is_fsf_builtin_catalogued_doc(doc):
        return description
    name = str(doc.get("fsfBuiltinVariant") or doc.get("name") or doc.get("_id") or "")
    metadata = FSF_CATALOGUED_BUILTIN_VARIANTS.get(name, {})
    return str(metadata.get("description") or FSF_CATALOGUED_BUILTIN_DESCRIPTION)


def _fsf_builtin_variant_name(doc: Mapping[str, Any]) -> str:
    return str(doc.get("fsfBuiltinVariant") or doc.get("name") or doc.get("_id") or "")


def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def catalogued_variant_ai_disabled_until(
    doc: Mapping[str, Any], *, now: datetime | None = None
) -> datetime | None:
    """Return an active fishnet AI-disable deadline for this catalogued variant."""

    disabled_until = _utc_datetime(doc.get("aiDisabledUntil"))
    if disabled_until is None:
        return None
    now = now or datetime.now(UTC)
    return disabled_until if disabled_until > now else None


def catalogued_variant_ai_disabled(doc: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    return catalogued_variant_ai_disabled_until(doc, now=now) is not None


def _clean_visibility(visibility: str | None) -> str:
    cleaned = str(visibility or CATALOGUED_VISIBILITY_PRIVATE).strip().lower()
    if cleaned not in CATALOGUED_VISIBILITIES:
        raise web.HTTPBadRequest(text="Variant visibility must be private, unlisted, or public.")
    return cleaned


def _can_preload_catalogued_doc(username: str | None, doc: Mapping[str, Any]) -> bool:
    if not _is_active_catalogued_doc(doc):
        return False
    if _catalogued_visibility(doc) == CATALOGUED_VISIBILITY_PUBLIC:
        return True
    if not username:
        return False
    return doc.get("author") == username or _is_admin_username(username)


def _can_open_catalogued_doc(username: str | None, doc: Mapping[str, Any]) -> bool:
    if not _is_active_catalogued_doc(doc):
        return False
    if _catalogued_visibility(doc) in {
        CATALOGUED_VISIBILITY_PUBLIC,
        CATALOGUED_VISIBILITY_UNLISTED,
    }:
        return True
    if not username:
        return False
    return doc.get("author") == username or _is_admin_username(username)


def _catalogued_public_query() -> dict[str, Any]:
    return {
        "enabled": {"$ne": False},
        "archived": {"$ne": True},
        "visibility": CATALOGUED_VISIBILITY_PUBLIC,
    }


def _ensure_catalogued_dimensions_supported(width: int, height: int) -> None:
    if width > MAX_COMPRESSED_BOARD_WIDTH:
        raise web.HTTPBadRequest(
            text=(
                "This board is too wide for the current saved-game move codec. "
                f"User-defined variants can have at most {MAX_COMPRESSED_BOARD_WIDTH} files."
            )
        )
    if height > MAX_COMPRESSED_BOARD_HEIGHT:
        raise web.HTTPBadRequest(
            text=(
                "This board is too tall for the current saved-game move codec. "
                f"User-defined variants can have at most {MAX_COMPRESSED_BOARD_HEIGHT} ranks."
            )
        )


def _catalogued_grand_from_dimensions(width: int, height: int) -> bool:
    """Return whether moves can use the old fast 10-rank Grand codec."""

    _ensure_catalogued_dimensions_supported(width, height)
    return height == 10


def _catalogued_extended_move_codec_from_dimensions(width: int, height: int) -> bool:
    """Return whether moves need the slower variable-rank codec.

    Variants up to 10 ranks keep the old standard codec plus optional
    grand2zero()/zero2grand() normalization. Only 11..16-rank user-defined
    variants use the extended parser/codec.
    """

    _ensure_catalogued_dimensions_supported(width, height)
    return height > 10


def _is_valid_variant_name(name: str) -> bool:
    if not 3 <= len(name) <= 32:
        return False
    if not "a" <= name[0] <= "z":
        return False
    return all(("a" <= ch <= "z") or ch.isdigit() or ch in {"-", "_"} for ch in name)


def _clean_favorite_names(value: object) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(name) for name in value if isinstance(name, str) and _is_valid_variant_name(name)}


def _ensure_catalogued_ini_size(ini: str) -> None:
    if len(ini.encode("utf-8")) > MAX_CATALOGUED_INI_BYTES:
        raise web.HTTPBadRequest(text="The INI file is too large.")


def _catalogued_variant_section_matches(ini: str) -> list[VariantSectionMatch]:
    """Return simple top-level INI section headers without using regex.

    The uploaded text is user controlled, so parsing line-by-line avoids the
    CodeQL ReDoS warning around multiline regex scanning. The caller still
    validates the extracted section name with the stricter site rule.
    """
    _ensure_catalogued_ini_size(ini)

    matches: list[VariantSectionMatch] = []
    offset = 0

    for line in ini.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            left = line.index("[")
            right = line.rindex("]")
            body = line[left + 1 : right]
            name_part, separator, suffix_part = body.partition(":")
            name = name_part.strip()

            if name:
                suffix = f":{suffix_part.strip()}" if separator else ""
                matches.append(
                    VariantSectionMatch(
                        start=offset + left,
                        end=offset + right + 1,
                        name=name,
                        suffix=suffix,
                    )
                )

        offset += len(line)

    return matches


def extract_variant_name(ini: str) -> str:
    sections = [match.name for match in _catalogued_variant_section_matches(ini)]
    if len(sections) != 1:
        raise web.HTTPBadRequest(text="The INI must contain exactly one variant section.")

    name = sections[0]
    if not _is_valid_variant_name(name):
        raise web.HTTPBadRequest(text=VARIANT_NAME_ERROR)

    return name


def extract_variant_base_name(ini: str) -> str:
    matches = _catalogued_variant_section_matches(ini)
    if len(matches) != 1:
        raise web.HTTPBadRequest(text="The INI must contain exactly one variant section.")

    suffix = matches[0].suffix.strip()
    return suffix[1:].strip() if suffix.startswith(":") else ""


def _ensure_catalogued_rule_changes(ini: str) -> None:
    """Reject cosmetic aliases of playable site variants before loading or saving them.

    This checks for gameplay overrides, not semantic equivalence of arbitrary
    rules. Engine variants not yet offered on the site may still be introduced
    through an inherited definition.
    """
    base = extract_variant_base_name(ini)
    playable_names = {
        variant.uci_variant: variant.translated_name
        for variant in ServerVariants
        if not variant.chess960
    }
    playable_names.update(
        {
            name: str(metadata["displayName"])
            for name, metadata in FSF_CATALOGUED_BUILTIN_VARIANTS.items()
        }
    )
    display_name = playable_names.get(base)
    if display_name is None:
        return

    for line in ini.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "[")):
            continue
        key, separator, _value = stripped.partition("=")
        if separator and key.strip().casefold() not in CATALOGUED_NON_RULE_OPTIONS:
            return

    raise web.HTTPBadRequest(text=f"This variant is already playable on PyChess as {display_name}.")


def replace_variant_section_name(ini: str, new_name: str) -> str:
    if not _is_valid_variant_name(new_name):
        raise web.HTTPBadRequest(text=VARIANT_NAME_ERROR)

    matches = _catalogued_variant_section_matches(ini)
    if len(matches) != 1:
        raise web.HTTPBadRequest(text="The INI must contain exactly one variant section.")

    match = matches[0]
    return ini[: match.start] + f"[{new_name}{match.suffix}]" + ini[match.end :]


def _one_line_log_text(text: str, limit: int = 500) -> str:
    collapsed = " ".join(text.replace("\x00", "\ufffd").split())
    if len(collapsed) > limit:
        return collapsed[:limit] + "…"
    return collapsed


def _board_part_from_fen(fen: str) -> str:
    return fen.split(maxsplit=1)[0]


def _iter_fen_piece_letters(board_part: str):
    for ch in board_part:
        if ch == "[":
            continue
        if ch == "]":
            continue
        if ch in "/~":
            continue
        if ch == "+":
            continue
        if ch.isalpha():
            # In FSF FEN a promoted piece is written as +P. The piece role used
            # by the UI is still the base letter; the promotion marker is not a square.
            yield ch.lower()
            continue
        if ch.isdigit():
            continue


def board_dimensions_from_fen(fen: str) -> tuple[int, int]:
    board_part = _board_part_from_fen(fen).split("[", 1)[0]
    ranks = board_part.split("/")
    widths: list[int] = []

    for rank in ranks:
        width = 0
        i = 0
        while i < len(rank):
            ch = rank[i]
            if ch.isdigit():
                j = i
                while j < len(rank) and rank[j].isdigit():
                    j += 1
                width += int(rank[i:j])
                i = j
                continue
            if ch == "+":
                i += 1
                continue
            if ch in "~":
                i += 1
                continue
            width += 1
            i += 1
        widths.append(width)

    if not widths or any(width != widths[0] for width in widths):
        raise web.HTTPBadRequest(text="The variant start FEN has inconsistent board rank widths.")

    return widths[0], len(ranks)


def piece_letters_from_fen(fen: str) -> list[str]:
    seen: set[str] = set()
    pieces: list[str] = []

    for letter in _iter_fen_piece_letters(_board_part_from_fen(fen)):
        if letter not in seen:
            seen.add(letter)
            pieces.append(letter)

    if not pieces:
        pieces = ["k"]

    # Keep common king/pawn/power pieces early in the editor row when present,
    # then append any fantasy letters in their first-seen order.
    preferred = [letter for letter in "kqrbnpacefwhm" if letter in seen]
    return preferred + [letter for letter in pieces if letter not in preferred]


def _ini_option(ini: str, key: str) -> str | None:
    wanted = key.casefold()

    for line in ini.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        left, right = stripped.split("=", 1)
        if left.strip().casefold() == wanted:
            return right.split("#", 1)[0].strip()

    return None


def _ini_bool(ini: str, key: str, default: bool = False) -> bool:
    value = _ini_option(ini, key)
    if value is None:
        return default
    return value.casefold() in {"true", "yes", "1", "on"}


def _ini_option_is_enabled(ini: str, key: str) -> bool:
    value = _ini_option(ini, key)
    if value is None:
        return False
    return value.strip().casefold() in {"true", "yes", "1", "on"}


def _ini_option_has_non_neutral_value(ini: str, key: str) -> bool:
    value = _ini_option(ini, key)
    if value is None:
        return False
    return value.strip().casefold() not in {"", "-", "0", "false", "no", "off", "none"}


def _ensure_catalogued_rules_supported(ini: str) -> None:
    unsupported: list[str] = []

    for key, reason in UNSUPPORTED_CATALOGUED_BOOL_RULES.items():
        if _ini_option_is_enabled(ini, key):
            unsupported.append(f"{key}: {reason}")

    if _ini_option_is_enabled(ini, "gating") and not _ini_option_is_enabled(ini, "seirawanGating"):
        unsupported.append(
            "gating: only Seirawan-style gating is supported for user-defined variants so far."
        )

    if _ini_option_has_non_neutral_value(ini, "wallingRule"):
        unsupported.append(
            "wallingRule: walling/duck-style moves need dedicated client input and move encoding support."
        )

    for key, reason in UNSUPPORTED_CATALOGUED_VALUE_RULES.items():
        if _ini_option_has_non_neutral_value(ini, key):
            unsupported.append(f"{key}: {reason}")

    if unsupported:
        raise web.HTTPBadRequest(
            text=(
                "This Fairy-Stockfish rule is not supported for user-defined variants yet: "
                + "; ".join(unsupported)
            )
        )


def _ini_piece_letters(ini: str, key: str) -> list[str]:
    value = _ini_option(ini, key) or ""
    seen: set[str] = set()
    letters: list[str] = []
    for ch in value:
        if ch.isalpha() and ch.lower() not in seen:
            seen.add(ch.lower())
            letters.append(ch.lower())
    return letters


def _pychess_pieces_metadata_value(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped[0] not in {"#", ";"}:
        return None

    body = stripped[1:].lstrip()
    key, separator, value = body.partition("=")
    if not separator or key.strip().casefold() != PYCHESS_PIECES_METADATA_KEY:
        return None

    # After the leading Fairy-Stockfish comment marker has made the line safe
    # for FSF, let users add ordinary inline notes after the pychess metadata.
    return value.split("#", 1)[0].split(";", 1)[0].strip()


def _pychess_pieces_metadata_lines(ini: str) -> list[str]:
    values: list[str] = []
    for line in ini.splitlines():
        value = _pychess_pieces_metadata_value(line)
        if value is not None:
            values.append(value)
    return values


def _strip_pychess_pieces_metadata(ini: str) -> str:
    return "\n".join(
        line for line in ini.splitlines() if _pychess_pieces_metadata_value(line) is None
    ).strip()


def _parse_pychess_piece_token(token: str) -> tuple[str, str] | None:
    token = token.strip()
    if not token:
        return None
    promoted = token.startswith("+")
    role = token[1:] if promoted else token
    if len(role) != 1 or not role.isascii() or not role.isalpha():
        raise web.HTTPBadRequest(
            text=(
                "Invalid pychessPieces metadata. Use one-letter piece roles like "
                "k,q,r,p and promoted roles like +p."
            )
        )
    return ("promoted" if promoted else "base"), role.lower()


def catalogued_pychess_piece_roles(ini: str) -> tuple[list[str], list[str]]:
    base_roles: list[str] = []
    promoted_roles: list[str] = []
    seen_base: set[str] = set()
    seen_promoted: set[str] = set()

    for value in _pychess_pieces_metadata_lines(ini):
        for raw_token in value.replace(",", " ").split():
            parsed = _parse_pychess_piece_token(raw_token)
            if parsed is None:
                continue
            kind, role = parsed
            if kind == "promoted":
                if role not in seen_promoted:
                    seen_promoted.add(role)
                    promoted_roles.append(role)
            elif role not in seen_base:
                seen_base.add(role)
                base_roles.append(role)

    return base_roles, promoted_roles


def _merge_piece_letters(first: list[str], second: list[str]) -> list[str]:
    merged = list(first)
    seen = set(merged)
    for letter in second:
        if letter not in seen:
            seen.add(letter)
            merged.append(letter)
    return merged


def _catalogued_piece_roles_from_ini(ini: str, start_fen: str) -> list[str]:
    pychess_base_roles, _pychess_promoted_roles = catalogued_pychess_piece_roles(ini)
    pieces = _merge_piece_letters(
        piece_letters_from_fen(start_fen), _ini_piece_letters(ini, "promotionPieceTypes")
    )
    return _merge_piece_letters(pieces, pychess_base_roles)


def pocket_letters_from_fen(fen: str) -> list[str]:
    board_part = _board_part_from_fen(fen)
    if "[" not in board_part or "]" not in board_part:
        return []

    pocket = board_part.split("[", 1)[1].split("]", 1)[0]
    seen: set[str] = set()
    letters: list[str] = []

    for ch in pocket:
        if ch.isalpha() and ch.lower() not in seen:
            seen.add(ch.lower())
            letters.append(ch.lower())

    return letters


def _non_royal_hand_roles(pieces: list[str], king_roles: list[str] | None) -> list[str]:
    royal_base_roles = {role.removeprefix("+") for role in (king_roles or []) if role}
    return [piece for piece in pieces if (piece.removeprefix("+")) not in royal_base_roles]


def catalogued_pocket_roles(
    ini: str,
    start_fen: str,
    pieces: list[str],
    king_roles: list[str] | None = None,
    *,
    capture_to_hand: bool | None = None,
) -> list[str]:
    has_pocket = _ini_bool(ini, "pieceDrops") or "[" in _board_part_from_fen(start_fen)
    if not has_pocket:
        return []

    if capture_to_hand is None:
        capture_to_hand = _ini_bool(ini, "capturesToHand", default=False)
    if capture_to_hand:
        return _merge_piece_letters(
            pocket_letters_from_fen(start_fen),
            _non_royal_hand_roles(pieces, king_roles),
        )

    return pocket_letters_from_fen(start_fen) or pieces


def _catalogued_pocket_roles_from_doc(
    doc: Mapping[str, Any],
    ini: str,
    start_fen: str,
    pieces: list[str],
    king_roles: list[str],
) -> list[str]:
    capture_to_hand = bool(
        doc.get("captureToHand", _ini_bool(ini, "capturesToHand", default=False))
    )
    stored_pocket_roles = list(doc.get("pocketRoles") or [])
    if stored_pocket_roles and capture_to_hand:
        explicit_pocket_roles = pocket_letters_from_fen(start_fen)
        stored_non_royal_roles = _non_royal_hand_roles(stored_pocket_roles, king_roles)
        return _merge_piece_letters(
            explicit_pocket_roles,
            _merge_piece_letters(
                stored_non_royal_roles,
                _non_royal_hand_roles(pieces, king_roles),
            ),
        )
    return stored_pocket_roles or catalogued_pocket_roles(
        ini, start_fen, pieces, king_roles, capture_to_hand=capture_to_hand
    )


def _catalogued_promotion_piece_letters(ini: str) -> list[str]:
    letters: list[str] = []
    seen: set[str] = set()
    for key in ("promotionPieceTypes", "promotionPieceTypesWhite", "promotionPieceTypesBlack"):
        for letter in _ini_piece_letters(ini, key):
            if letter not in seen:
                seen.add(letter)
                letters.append(letter)
    return letters


def _catalogued_promotion_pawn_letters(ini: str, pieces: list[str]) -> list[str]:
    letters: list[str] = []
    seen: set[str] = set()
    for key in ("promotionPawnTypes", "promotionPawnTypesWhite", "promotionPawnTypesBlack"):
        for letter in _ini_piece_letters(ini, key):
            if letter not in seen:
                seen.add(letter)
                letters.append(letter)

    if letters:
        return letters

    if "p" in pieces:
        return ["p"]
    return []


def catalogued_promotion_type(ini: str) -> str:
    promoted_piece_type = (_ini_option(ini, "promotedPieceType") or "").strip()
    _pychess_base_roles, pychess_promoted_roles = catalogued_pychess_piece_roles(ini)
    if promoted_piece_type or pychess_promoted_roles:
        return "shogi"
    return "regular"


PROMOTED_PIECE_TYPE_RE = re.compile(r"([A-Za-z])\s*:\s*([A-Za-z-])")


def _catalogued_promoted_piece_type_pairs(ini: str) -> list[tuple[str, str]]:
    promoted_piece_type = _ini_option(ini, "promotedPieceType") or ""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    for match in PROMOTED_PIECE_TYPE_RE.finditer(promoted_piece_type):
        source = match.group(1).lower()
        target = match.group(2).lower()
        if source in seen:
            continue
        seen.add(source)
        pairs.append((source, target))

    return pairs


def catalogued_promotion_roles(ini: str, pieces: list[str]) -> list[str]:
    roles: list[str] = []
    seen: set[str] = set()

    def add_role(role: str) -> None:
        if role not in seen:
            seen.add(role)
            roles.append(role)

    for source, _target in _catalogued_promoted_piece_type_pairs(ini):
        add_role(source)

    if not roles:
        if _catalogued_promotion_piece_letters(ini):
            for role in _catalogued_promotion_pawn_letters(ini, pieces):
                add_role(role)
        elif (
            _ini_bool(ini, "mandatoryPawnPromotion") or _ini_bool(ini, "mandatoryPiecePromotion")
        ) and "p" in pieces:
            add_role("p")

    _pychess_base_roles, pychess_promoted_roles = catalogued_pychess_piece_roles(ini)
    for role in pychess_promoted_roles:
        add_role(role)

    return roles


def catalogued_promotion_order(ini: str, promotion_type: str) -> list[str]:
    if promotion_type == "shogi":
        return ["+", ""]
    return _catalogued_promotion_piece_letters(ini)


def catalogued_show_promoted(ini: str, start_fen: str) -> bool:
    _pychess_base_roles, pychess_promoted_roles = catalogued_pychess_piece_roles(ini)
    if (_ini_option(ini, "promotedPieceType") or "").strip() or pychess_promoted_roles:
        return True
    if any(
        _ini_bool(ini, key) for key in ("pieceDemotion", "piecePromotionOnCapture", "dropPromoted")
    ):
        return True
    return "+" in _board_part_from_fen(start_fen)


def catalogued_rules_gate(ini: str) -> bool:
    return _ini_bool(ini, "seirawanGating")


def catalogued_rules_pass(ini: str) -> bool:
    return any(
        _ini_bool(ini, key)
        for key in (
            "pass",
            "passWhite",
            "passBlack",
            "passOnStalemate",
            "passOnStalemateWhite",
            "passOnStalemateBlack",
        )
    )


def catalogued_legal_moves_need_history(ini: str) -> bool:
    return catalogued_rules_pass(ini) or any(
        _ini_bool(ini, key)
        for key in (
            "perpetualCheckIllegal",
            "moveRepetitionIllegal",
            "bikjangRule",
        )
    )


def catalogued_n_fold_is_draw(ini: str) -> bool:
    if not _ini_option_has_non_neutral_value(ini, "nFoldRule"):
        return False
    return (_ini_option(ini, "nFoldValue") or "draw").strip().casefold() == "draw"


def catalogued_show_check_counters(ini: str) -> bool:
    return _ini_bool(ini, "checkCounting") or _ini_bool(ini, "dupleCheck")


PIECE_SET_FILENAME_RE = re.compile(r"^([wb])(\+?)([A-Za-z])\.svg$")
XML_DECL_RE = re.compile(r"^\ufeff?\s*<\?xml\s+[^?]*\?>", re.IGNORECASE)
SVG_DOCTYPE_RE = re.compile(
    r"^\s*<!DOCTYPE\s+svg\s+"
    r'(?:PUBLIC\s+"[^"]*"\s+"[^"]*"|SYSTEM\s+"[^"]*")\s*>',
    re.IGNORECASE,
)
XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SAFE_SVG_TAGS = frozenset(
    {
        "svg",
        "defs",
        "g",
        "pattern",
        "linearGradient",
        "radialGradient",
        "stop",
        "filter",
        "feGaussianBlur",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "title",
        "desc",
    }
)
SAFE_SVG_ATTRS = frozenset(
    {
        "xmlns",
        "version",
        "id",
        "viewBox",
        "width",
        "height",
        "patternUnits",
        "patternContentUnits",
        "patternTransform",
        "gradientUnits",
        "gradientTransform",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "fx",
        "fy",
        "r",
        "rx",
        "ry",
        "offset",
        "d",
        "points",
        "fill",
        "stroke",
        "stop-color",
        "stop-opacity",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "fill-rule",
        "clip-rule",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "filter",
        "stdDeviation",
        "transform",
        "transform-origin",
        "href",
        "aria-label",
        "role",
    }
)
SAFE_SVG_STYLE_ATTRS = frozenset(
    {
        "fill",
        "stroke",
        "stop-color",
        "stop-opacity",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "fill-rule",
        "clip-rule",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "filter",
        "transform",
        "transform-origin",
    }
)
SAFE_SVG_VALUE_RE = re.compile(r"^[#%,.0-9A-Za-z_() +\-/:]*$")
# Several bundled piece sets use editor-generated numeric IDs such as ``id="0"``.
# They are safe here because references are still restricted to same-document
# fragments containing only this narrow character set.
SAFE_SVG_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:-]*$")
SAFE_SVG_LOCAL_REF_RE = re.compile(r"^url\(#[A-Za-z0-9_][A-Za-z0-9_.:-]*\)$")
SAFE_SVG_FRAGMENT_REF_RE = re.compile(r"^#[A-Za-z0-9_][A-Za-z0-9_.:-]*$")


def _local_xml_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[1]
    return name


def _svg_value_is_unsafe(value: str, *, allow_local_ref: bool = False) -> bool:
    lowered = value.casefold()
    if "javascript:" in lowered or "data:" in lowered:
        return True
    if "url(" not in lowered:
        return False
    return not (allow_local_ref and SAFE_SVG_LOCAL_REF_RE.fullmatch(value) is not None)


def _svg_value_is_supported(attribute: str, value: str) -> bool:
    # Accessible names commonly contain non-ASCII text (for example, the kanji
    # printed on shogi pieces). ElementTree escapes the value when serializing,
    # so it is safe to preserve after the unsafe-reference check above.
    return attribute == "aria-label" or SAFE_SVG_VALUE_RE.fullmatch(value) is not None


def _parse_safe_svg_style(style: str, filename: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for chunk in style.split(";"):
        declaration = chunk.strip()
        if not declaration:
            continue
        name, separator, value = declaration.partition(":")
        if not separator:
            raise web.HTTPBadRequest(text=f"{filename} contains malformed SVG style declarations.")
        prop = name.strip().casefold()
        if prop not in SAFE_SVG_STYLE_ATTRS:
            continue
        cleaned_value = value.strip()
        allow_local_ref_value = prop in {"fill", "stroke", "filter"}
        if _svg_value_is_unsafe(cleaned_value, allow_local_ref=allow_local_ref_value):
            raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG attribute values.")
        if not SAFE_SVG_VALUE_RE.fullmatch(cleaned_value):
            raise web.HTTPBadRequest(text=f"{filename} contains unsupported SVG attribute values.")
        parsed[prop] = cleaned_value
    return parsed


def _prune_unsupported_svg_children(element: ET.Element) -> None:
    for child in list(element):
        if not isinstance(child.tag, str):
            element.remove(child)
            continue
        tag = _local_xml_name(child.tag)
        if tag not in SAFE_SVG_TAGS:
            element.remove(child)
            continue
        child.tag = tag
        _prune_unsupported_svg_children(child)


def _canonical_piece_set_filename(filename: str) -> str | None:
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    filename = unquote(filename)
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    match = PIECE_SET_FILENAME_RE.fullmatch(filename)
    if match is None:
        return None
    color, promoted, letter = match.groups()
    return f"{color}{promoted}{letter.upper()}.svg"


def _catalogued_piece_set_filenames(doc: Mapping[str, Any], colors: tuple[str, ...]) -> list[str]:
    roles = {str(role).lower() for role in doc.get("pieces", []) if str(role).isalpha()}
    promotion_type = str(
        doc.get("promotionType") or catalogued_promotion_type(str(doc.get("ini") or ""))
    ).casefold()
    promoted_roles = (
        {str(role).lower() for role in doc.get("promotionRoles", []) if str(role).isalpha()}
        if promotion_type == "shogi"
        else set()
    )
    filenames: list[str] = []
    for color in colors:
        for role in sorted(roles):
            filenames.append(f"{color}{role.upper()}.svg")
        for role in sorted(promoted_roles):
            filenames.append(f"{color}+{role.upper()}.svg")
    return filenames


def _catalogued_piece_set_required_filenames(doc: Mapping[str, Any]) -> list[str]:
    return _catalogued_piece_set_filenames(doc, ("w", "b"))


def _catalogued_piece_set_single_color_filenames(doc: Mapping[str, Any], color: str) -> list[str]:
    return _catalogued_piece_set_filenames(doc, (color,))


def _catalogued_piece_set_required_filenames_text(doc: Mapping[str, Any]) -> str:
    return ", ".join(_catalogued_piece_set_required_filenames(doc))


def _catalogued_piece_set_storage_key(filename_or_key: str) -> str:
    # MongoDB field names with dots are awkward and can fail on older server /
    # driver combinations. Store wP.svg as wP and w+P.svg as w+P, but accept
    # the old dotted keys when reading in case any test data was already saved.
    key = filename_or_key
    key = key.removesuffix(".svg")
    return key


def _catalogued_piece_set_required_keys(doc: Mapping[str, Any]) -> set[str]:
    return {
        _catalogued_piece_set_storage_key(filename)
        for filename in _catalogued_piece_set_required_filenames(doc)
    }


def _catalogued_piece_set_single_color_keys(doc: Mapping[str, Any], color: str) -> set[str]:
    return {
        _catalogued_piece_set_storage_key(filename)
        for filename in _catalogued_piece_set_single_color_filenames(doc, color)
    }


def _catalogued_piece_set_mode_for_keys(doc: Mapping[str, Any], keys: set[str]) -> str | None:
    if keys == _catalogued_piece_set_required_keys(doc):
        return "paired"
    if not _catalogued_piece_set_is_directional(doc):
        return None
    for color in ("w", "b"):
        if keys == _catalogued_piece_set_single_color_keys(doc, color):
            return f"canonical-{color}"
    return None


def _catalogued_piece_set_public_filename(key: str) -> str:
    return key if key.endswith(".svg") else f"{key}.svg"


def _piece_set_revision(doc: Mapping[str, Any]) -> str:
    updated_at = doc.get("pieceSetUpdatedAt")
    if isinstance(updated_at, datetime):
        return str(int(updated_at.timestamp()))
    return re.sub(r"\W+", "", str(updated_at or "0")) or "0"


def _board_svg_revision(doc: Mapping[str, Any]) -> str:
    updated_at = doc.get("boardSvgUpdatedAt")
    if isinstance(updated_at, datetime):
        return str(int(updated_at.timestamp()))
    return re.sub(r"\W+", "", str(updated_at or "0")) or "0"


def _sanitize_catalogued_svg(
    raw: bytes,
    filename: str,
    max_bytes: int,
) -> str:
    if not raw:
        raise web.HTTPBadRequest(text=f"{filename} is empty.")
    if len(raw) > max_bytes:
        raise web.HTTPBadRequest(
            text=(f"{filename} is too large. The SVG must be at most {max_bytes // 1024} KiB.")
        )

    try:
        text = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid UTF-8 SVG file.") from exc
    xml_decl = XML_DECL_RE.match(text)
    if xml_decl is not None:
        text = text[xml_decl.end() :].lstrip()

    # Many editor-exported SVG files include the legacy SVG 1.1 external DTD.
    # It does not carry image data, and keeping it only makes otherwise safe
    # piece sets fail. Strip only the simple external SVG doctype form; any
    # internal subset / entity declaration is still rejected by the check below.
    svg_doctype = SVG_DOCTYPE_RE.match(text)
    if svg_doctype is not None:
        text = text[svg_doctype.end() :].lstrip()

    text = XML_COMMENT_RE.sub("", text)
    lowered = text.casefold()
    if "<!" in text or "<?" in text:
        raise web.HTTPBadRequest(
            text=(
                f"{filename} contains unsupported doctypes, entity declarations, "
                "or processing instructions."
            )
        )
    if any(token in lowered for token in ("<script", "foreignobject", "javascript:", "data:")):
        raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG content.")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid UTF-8 SVG file.") from exc

    if _local_xml_name(root.tag) != "svg":
        raise web.HTTPBadRequest(text=f"{filename} must contain one <svg> root element.")

    root.tag = "svg"
    _prune_unsupported_svg_children(root)

    for element in root.iter():
        if not isinstance(element.tag, str):
            raise web.HTTPBadRequest(text=f"{filename} contains unsupported SVG nodes.")
        if element.tag not in SAFE_SVG_TAGS:
            raise web.HTTPBadRequest(
                text=f"{filename} contains unsupported <{element.tag}> SVG elements."
            )

        clean_attrs: dict[str, str] = {}
        for attr, raw_value in list(element.attrib.items()):
            local_attr = _local_xml_name(attr)
            value = raw_value.strip()
            if local_attr == "style":
                clean_attrs.update(_parse_safe_svg_style(value, filename))
                continue
            if local_attr.startswith("on"):
                continue
            if local_attr in {"src", "class"}:
                continue
            if local_attr not in SAFE_SVG_ATTRS:
                continue
            if local_attr == "id" and not SAFE_SVG_ID_RE.fullmatch(value):
                continue
            if local_attr == "href":
                if not SAFE_SVG_FRAGMENT_REF_RE.fullmatch(value):
                    continue
                clean_attrs[local_attr] = value
                continue
            allow_local_ref_value = local_attr in {"fill", "stroke", "filter"}
            if _svg_value_is_unsafe(value, allow_local_ref=allow_local_ref_value):
                raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG attribute values.")
            if not _svg_value_is_supported(local_attr, value):
                raise web.HTTPBadRequest(
                    text=f"{filename} contains unsupported SVG attribute values."
                )
            clean_attrs[local_attr] = value

        element.attrib.clear()
        element.attrib.update(clean_attrs)

    root.attrib["xmlns"] = "http://www.w3.org/2000/svg"
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _sanitize_catalogued_piece_svg(raw: bytes, filename: str) -> str:
    return _sanitize_catalogued_svg(raw, filename, MAX_CATALOGUED_PIECE_SVG_BYTES)


def _parse_svg_view_box_size(svg: str, filename: str) -> tuple[float, float]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid SVG file.") from exc

    raw_view_box = str(root.attrib.get("viewBox") or "").strip()
    if not raw_view_box:
        raise web.HTTPBadRequest(text=f"{filename} must define a viewBox.")

    parts = [part for part in re.split(r"[\s,]+", raw_view_box) if part]
    if len(parts) != 4:
        raise web.HTTPBadRequest(text=f"{filename} has an invalid viewBox.")

    try:
        _min_x, _min_y, width, height = (float(part) for part in parts)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=f"{filename} has an invalid viewBox.") from exc

    if width <= 0 or height <= 0:
        raise web.HTTPBadRequest(text=f"{filename} viewBox must have positive width and height.")
    return width, height


def _sanitize_catalogued_board_svg(raw: bytes, filename: str, width: int, height: int) -> str:
    # Files and ranks describe the logical grid. The SVG viewBox describes the
    # intended physical board shape, including rectangular cells on regional
    # boards such as shogi. The generated board CSS applies that shape at render time.
    del width, height
    sanitized = _sanitize_catalogued_svg(raw, filename, MAX_CATALOGUED_BOARD_SVG_BYTES)
    _parse_svg_view_box_size(sanitized, filename)
    return sanitized


def _catalogued_piece_css_selector(
    variant_name: str, key: str, *, image_layer: bool = False
) -> str:
    # key format is wP, bP, w+P, b+P. Accept *.svg legacy keys too.
    key = _catalogued_piece_set_storage_key(key)
    color = "white" if key[0] == "w" else "black"
    promoted = key[1] == "+"
    letter = key[2 if promoted else 1].lower()
    role_class = f"p{letter}-piece" if promoted else f"{letter}-piece"
    style_class = f".piece-style-catalogued-{variant_name}-custom"
    piece_suffix = "::before" if image_layer else ""
    return (
        f"{style_class} piece.{role_class}.{color}{piece_suffix}, "
        f"label.piece.catalogued-custom-preview{style_class}.{role_class}.{color}"
    )


def _catalogued_piece_set_css(
    variant_name: str,
    piece_set: Mapping[str, Any],
    *,
    directional: bool = False,
) -> str:
    lines: list[str] = []
    stored_keys = {_catalogued_piece_set_storage_key(str(key)) for key in piece_set}
    stored_colors = {key[0] for key in stored_keys if key and key[0] in {"w", "b"}}
    canonical_color = next(iter(stored_colors)) if directional and len(stored_colors) == 1 else None
    if directional:
        style_class = f".piece-style-catalogued-{variant_name}-custom"
        lines.append(
            f"{style_class} piece::before "
            '{content:"";display:block;width:100%;height:100%;pointer-events:none;}'
        )
    for key in sorted(piece_set):
        item = piece_set[key]
        svg = str(item.get("svg") if isinstance(item, Mapping) else "")
        if not svg:
            continue
        data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        selectors = [_catalogued_piece_css_selector(variant_name, key, image_layer=directional)]
        if canonical_color is not None:
            stored_key = _catalogued_piece_set_storage_key(str(key))
            other_color = "b" if canonical_color == "w" else "w"
            selectors.append(
                _catalogued_piece_css_selector(
                    variant_name,
                    other_color + stored_key[1:],
                    image_layer=True,
                )
            )
        lines.append(
            f"{', '.join(selectors)} "
            "{background-position:center;background-size:contain;background-repeat:no-repeat;background-image:"
            f'url("data:image/svg+xml;base64,{data}");}}'
        )
    if directional:
        # chessgroundx owns the piece element's transform for positioning and
        # animation. Rotate only its image layer so that translation is left
        # untouched.
        if canonical_color == "w":
            lines.append(f"{style_class} piece.enemy::before {{transform:rotate(180deg);}}")
        elif canonical_color == "b":
            lines.append(f"{style_class} piece.ally::before {{transform:rotate(180deg);}}")
        else:
            lines.append(
                f"{style_class} piece.white.enemy::before, "
                f"{style_class} piece.black.ally::before "
                "{transform:rotate(180deg);}"
            )
    return "\n".join(lines) + "\n"


def _catalogued_disguised_piece_css(variant_name: str) -> str:
    style_class = f".piece-style-catalogued-{variant_name}-disguised"
    preview_class = f"label.piece.catalogued-disguised-preview{style_class}.white"
    white_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<circle cx="256" cy="256" r="170" fill="#fff" stroke="#000" stroke-width="20"/>'
        "</svg>"
    )
    black_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<circle cx="256" cy="256" r="170" fill="#000" stroke="#000" stroke-width="20"/>'
        "</svg>"
    )
    white_data = base64.b64encode(white_svg.encode("utf-8")).decode("ascii")
    black_data = base64.b64encode(black_svg.encode("utf-8")).decode("ascii")
    return (
        "\n".join(
            (
                f'{style_class} piece.white, {preview_class} {{background-image:url("data:image/svg+xml;base64,{white_data}");background-position:center;background-size:contain;background-repeat:no-repeat;}}',
                f'{style_class} piece.black {{background-image:url("data:image/svg+xml;base64,{black_data}");background-position:center;background-size:contain;background-repeat:no-repeat;}}',
            )
        )
        + "\n"
    )


def _catalogued_board_svg_css(variant_name: str, board_svg: Mapping[str, Any]) -> str:
    svg = str(board_svg.get("svg") or "")
    view_box_width, view_box_height = _parse_svg_view_box_size(svg, "board.svg")
    padding_bottom = view_box_height * 100 / view_box_width

    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    image = f'url("data:image/svg+xml;base64,{encoded}")'
    scope = f'[data-board-variant="{variant_name}"]'
    wrapper_selector = f"{scope}.cg-wrap, {scope} .cg-wrap"
    selector = f"{scope} cg-board"
    preview_selector = f"{scope}.catalogued-board-preview-surface"
    settings_preview_selector = (
        f'label.board.catalogued-custom-board-preview[data-board-variant="{variant_name}"]'
    )
    return (
        f"{wrapper_selector} {{\n"
        f"  padding-bottom: {padding_bottom:.8f}% !important;\n"
        "}\n"
        f"{selector}, {preview_selector}, {settings_preview_selector} {{\n"
        f"  background-image: {image} !important;\n"
        "  background-size: 100% 100% !important;\n"
        "  background-repeat: no-repeat !important;\n"
        "  background-position: center center !important;\n"
        "}\n"
        f"{preview_selector}, {settings_preview_selector} {{\n"
        f"  aspect-ratio: {view_box_width:g} / {view_box_height:g} !important;\n"
        "}\n"
    )


def _has_complete_piece_set(doc: Mapping[str, Any]) -> bool:
    piece_set = doc.get("pieceSet")
    if not isinstance(piece_set, Mapping):
        return False
    keys = {_catalogued_piece_set_storage_key(str(key)) for key in piece_set}
    return _catalogued_piece_set_mode_for_keys(doc, keys) is not None


def _copy_catalogued_uploaded_assets(
    target_doc: CataloguedVariantDocument, source_doc: Mapping[str, Any]
) -> None:
    """Keep user uploads even when changed metadata makes them temporarily unusable."""
    piece_set = source_doc.get("pieceSet")
    if isinstance(piece_set, Mapping):
        target_doc["pieceSet"] = cast(dict[str, CataloguedVariantPieceSetSvg], dict(piece_set))
        updated_at = source_doc.get("pieceSetUpdatedAt")
        if isinstance(updated_at, datetime):
            target_doc["pieceSetUpdatedAt"] = updated_at

    board_svg = source_doc.get("boardSvg")
    if isinstance(board_svg, Mapping) and board_svg.get("svg"):
        target_doc["boardSvg"] = cast(CataloguedVariantBoardSvg, dict(board_svg))
        updated_at = source_doc.get("boardSvgUpdatedAt")
        if isinstance(updated_at, datetime):
            target_doc["boardSvgUpdatedAt"] = updated_at


def _has_board_svg(doc: Mapping[str, Any]) -> bool:
    board_svg = doc.get("boardSvg")
    return isinstance(board_svg, Mapping) and bool(board_svg.get("svg"))


def catalogued_king_roles(ini: str, pieces: list[str]) -> list[str]:
    extinction_value = _ini_option(ini, "extinctionValue")
    if extinction_value is not None:
        # Extinction/custom-goal variants often have no royal/check concept.
        # Do not invent a king role just because one of the piece letters is "k".
        pseudo_royal = _ini_bool(ini, "extinctionPseudoRoyal", default=False)
        if not pseudo_royal:
            return []

    roles: list[str] = []
    seen: set[str] = set()

    def add(role: str) -> None:
        if role not in seen:
            seen.add(role)
            roles.append(role)

    if "k" in pieces:
        add("k")

    if extinction_value is None:
        royal_targets = {"k"}
    else:
        extinction_piece_types = (_ini_option(ini, "extinctionPieceTypes") or "").strip()
        if "*" in extinction_piece_types:
            royal_targets = set(pieces)
            royal_targets.update(
                target
                for _source, target in _catalogued_promoted_piece_type_pairs(ini)
                if target != "-"
            )
        else:
            royal_targets = set(_ini_piece_letters(ini, "extinctionPieceTypes"))

        for piece in pieces:
            if piece in royal_targets:
                add(piece)

    for source, target in _catalogued_promoted_piece_type_pairs(ini):
        if source in pieces and target in royal_targets:
            add(f"+{source}")

    return roles


async def _run_process(args: list[str], *, stdin: str | None = None) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )
    except FileNotFoundError as exc:
        raise web.HTTPServiceUnavailable(
            text=f"Fairy-Stockfish checker executable was not found: {args[0]}"
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin.encode("utf-8") if stdin is not None else None),
            timeout=FSF_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise web.HTTPBadRequest(text="Fairy-Stockfish check timed out.") from exc

    return proc.returncode or 0, (stdout + stderr).decode("utf-8", errors="replace")


def _ensure_catalogued_start_fen_has_side_to_move(start_fen: str) -> None:
    parts = start_fen.split()
    if len(parts) < 2 or parts[1] not in ("w", "b"):
        raise web.HTTPBadRequest(
            text="startFen must explicitly include the side to move ('w' or 'b')."
        )


async def _check_ini_with_pyffish_child(ini: str, name: str) -> str:
    """Validate in a child process so trial checks do not mutate server pyffish state."""
    _ensure_catalogued_ini_size(ini)
    _ensure_catalogued_rules_supported(ini)

    code = """
import json
import sys

import pyffish as sf

name = sys.argv[1]
ini = sys.stdin.read()
try:
    sf.set_option("VariantPath", "variants.ini")
    sf.load_variant_config(ini)
    start_fen = sf.start_fen(name)
    if not start_fen:
        raise RuntimeError("Fairy-Stockfish did not return a start FEN.")
    status = sf.validate_fen(start_fen, name, False)
    if status != sf.FEN_OK:
        raise RuntimeError(f"The start FEN is invalid for {name} (status {status}).")
    print(json.dumps({"ok": True, "startFen": start_fen}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    raise
"""
    returncode, output = await _run_process([sys.executable, "-c", code, name], stdin=ini)

    if returncode != 0:
        log.info(
            "Fairy-Stockfish validation failed for catalogued variant %s: %s",
            name,
            _one_line_log_text(output),
        )
        raise web.HTTPBadRequest(text="Fairy-Stockfish rejected this variant definition.")

    try:
        payload = json.loads(output.splitlines()[-1])
        start_fen = str(payload.get("startFen") or "")
        _ensure_catalogued_start_fen_has_side_to_move(start_fen)
        return start_fen
    except web.HTTPException:
        raise
    except Exception:
        log.info(
            "Fairy-Stockfish validation returned invalid output for catalogued variant %s: %s",
            name,
            _one_line_log_text(output),
            exc_info=True,
        )
        raise web.HTTPBadRequest(
            text="Fairy-Stockfish validation returned invalid output."
        ) from None


async def check_catalogued_ini_without_mutating_server(ini: str, name: str) -> str:
    """Validate with pyffish in a child process.

    pychess.org does not ship a native Fairy-Stockfish executable on the web
    server, and upstream bindings do not expose the UCI `check` command. Import
    the already-installed pyffish package in a short-lived child process instead:
    this catches parser/start-FEN/FEN-validation failures without registering
    trial variants in the long-running server process.
    """
    return await _check_ini_with_pyffish_child(ini, name)


async def check_catalogued_ini_tree_without_mutating_server(
    ini: str,
    name: str,
    initial_fen: str,
    move_tree: Iterable[tuple[str, str | None, str]],
) -> None:
    """Validate an imported custom position/tree in an isolated pyffish process.

    A successful Study import may later admit its immutable rules snapshot into the
    serving process. Untrusted imports must first prove that their INI, initial FEN,
    and every submitted move can be replayed without mutating the main process's
    irreversible Fairy-Stockfish variant registry.
    """
    _ensure_catalogued_ini_size(ini)
    _ensure_catalogued_rules_supported(ini)

    payload = json.dumps(
        {
            "ini": ini,
            "initialFen": initial_fen,
            "moveTree": [list(node) for node in move_tree],
        },
        separators=(",", ":"),
    )
    code = r"""
import json
import sys

import pyffish as sf

name = sys.argv[1]
payload = json.loads(sys.stdin.read())
ini = payload["ini"]
initial_fen = payload["initialFen"]
move_tree = payload["moveTree"]

try:
    sf.set_option("VariantPath", "variants.ini")
    sf.load_variant_config(ini)
    start_fen = sf.start_fen(name)
    if not start_fen:
        raise RuntimeError("Fairy-Stockfish did not return a start FEN.")
    if sf.validate_fen(start_fen, name, False) != sf.FEN_OK:
        raise RuntimeError("The variant start FEN is invalid.")
    if sf.validate_fen(initial_fen, name, False) != sf.FEN_OK:
        raise RuntimeError("The imported initial FEN is invalid.")

    nodes = {node_id: (parent_id, move) for node_id, parent_id, move in move_tree}
    parent_ids = {parent_id for parent_id, _move in nodes.values() if parent_id is not None}
    for leaf_id in nodes:
        if leaf_id in parent_ids:
            continue
        path = []
        current_id = leaf_id
        while current_id is not None:
            parent_id, move = nodes[current_id]
            path.append(move)
            current_id = parent_id
        path.reverse()

        history = []
        for move in path:
            if move not in sf.legal_moves(name, initial_fen, history, False):
                raise RuntimeError("The imported tree contains an illegal move.")
            history.append(move)
        if history:
            sf.get_fen(name, initial_fen, history, False)

    print(json.dumps({"ok": True, "startFen": start_fen}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    raise
"""
    returncode, output = await _run_process([sys.executable, "-c", code, name], stdin=payload)

    if returncode != 0:
        log.info(
            "Fairy-Stockfish isolated Study import validation failed for %s: %s",
            name,
            _one_line_log_text(output),
        )
        raise web.HTTPBadRequest(text="Fairy-Stockfish rejected this Study variant import.")

    try:
        result = json.loads(output.splitlines()[-1])
        start_fen = str(result.get("startFen") or "")
        _ensure_catalogued_start_fen_has_side_to_move(start_fen)
    except web.HTTPException:
        raise
    except Exception:
        log.info(
            "Fairy-Stockfish Study import validation returned invalid output for %s: %s",
            name,
            _one_line_log_text(output),
            exc_info=True,
        )
        raise web.HTTPBadRequest(
            text="Fairy-Stockfish Study import validation returned invalid output."
        ) from None


def _is_builtin_variant_name(name: str) -> bool:
    # Do not use the mutable ALL_VARIANTS map here. A previously-buggy upload
    # could have registered a catalogued variant with a built-in key and hidden
    # the original entry in ALL_VARIANTS. ServerVariants is the stable source
    # for built-in site names, while sf.variants() at import time covers
    # Fairy-Stockfish-only built-ins such as tencubed.
    return name in BUILTIN_VARIANT_NAMES or name in BUILTIN_FSF_VARIANT_NAMES


async def ensure_catalogued_variant_name_available(
    app_state: Any,
    name: str,
    *,
    current_name: str | None = None,
) -> None:
    """Ensure a user-uploaded variant key is globally unique.

    Names are game document variant codes, FSF UCI_Variant keys, URL slugs, and
    catalog keys, so they must not collide with built-ins or any active/archived
    catalogued variant owned by any user.
    """
    if _is_builtin_variant_name(name):
        raise web.HTTPConflict(
            text="This variant name conflicts with an existing built-in variant."
        )

    if current_name is not None and name == current_name:
        return

    if name in CATALOGUED_VARIANTS:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.")

    if name in getattr(app_state, "catalogued_variants", {}):
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.")

    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    existing = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one(
        {"_id": name}, projection={"_id": 1}
    )
    if existing is not None:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.")

    reserved = await app_state.db[CATALOGUED_VARIANT_NAME_COLLECTION].find_one(
        {"_id": name}, projection={"_id": 1}
    )
    if reserved is not None:
        raise web.HTTPConflict(
            text="This variant name was used previously and cannot be reused with different rules."
        )


def validate_catalogued_ini(ini: str) -> CataloguedVariantValidation:
    _ensure_catalogued_ini_size(ini)
    _ensure_catalogued_rules_supported(ini)
    name = extract_variant_name(ini)
    base_variant = extract_variant_base_name(ini)

    try:
        sf.load_variant_config(ini)
        start_fen = sf.start_fen(name)
    except Exception:
        log.info("Fairy-Stockfish rejected catalogued variant %s", name, exc_info=True)
        raise web.HTTPBadRequest(text="Fairy-Stockfish rejected this variant definition.") from None

    if not start_fen:
        raise web.HTTPBadRequest(
            text="Fairy-Stockfish did not provide a start FEN for this variant."
        )
    _ensure_catalogued_start_fen_has_side_to_move(start_fen)

    width, height = board_dimensions_from_fen(start_fen)
    _catalogued_grand_from_dimensions(width, height)
    pieces = _catalogued_piece_roles_from_ini(ini, start_fen)
    king_roles = catalogued_king_roles(ini, pieces)
    capture_to_hand = _ini_bool(ini, "capturesToHand", default=False)
    pocket_roles = catalogued_pocket_roles(
        ini, start_fen, pieces, king_roles, capture_to_hand=capture_to_hand
    )
    promotion_type = catalogued_promotion_type(ini)
    promotion_roles = catalogued_promotion_roles(ini, pieces)
    promotion_order = catalogued_promotion_order(ini, promotion_type)
    show_promoted = catalogued_show_promoted(ini, start_fen)
    rules_gate = catalogued_rules_gate(ini)
    rules_pass = catalogued_rules_pass(ini)
    legal_moves_need_history = catalogued_legal_moves_need_history(ini)
    n_fold_is_draw = catalogued_n_fold_is_draw(ini)
    show_check_counters = catalogued_show_check_counters(ini)

    return CataloguedVariantValidation(
        name,
        start_fen,
        width,
        height,
        pieces,
        king_roles,
        pocket_roles,
        capture_to_hand,
        promotion_type,
        promotion_roles,
        promotion_order,
        show_promoted,
        rules_gate,
        rules_pass,
        legal_moves_need_history,
        n_fold_is_draw,
        show_check_counters,
        base_variant,
    )


def _client_doc(
    doc: Mapping[str, Any],
    *,
    game_count: int | None = None,
    favorite_names: set[str] | None = None,
) -> CataloguedVariantClientDocument:
    description = _catalogued_description(doc)
    tooltip = description or "Catalogued variant"
    ini = str(doc.get("ini") or "")
    start_fen = str(doc["startFen"])
    base_variant = str(doc.get("baseVariant") or "")
    pieces = list(doc.get("pieces") or ["k"])
    king_roles = (
        catalogued_king_roles(ini, pieces)
        if _ini_option(ini, "extinctionValue") is not None
        else list(doc.get("kingRoles") or catalogued_king_roles(ini, pieces))
    )
    pocket_roles = _catalogued_pocket_roles_from_doc(doc, ini, start_fen, pieces, king_roles)
    capture_to_hand = bool(
        doc.get("captureToHand", _ini_bool(ini, "capturesToHand", default=False))
    )
    promotion_type = str(doc.get("promotionType") or catalogued_promotion_type(ini))
    promotion_roles = list(doc.get("promotionRoles") or catalogued_promotion_roles(ini, pieces))
    promotion_order = list(
        doc.get("promotionOrder") or catalogued_promotion_order(ini, promotion_type)
    )
    show_promoted = bool(doc.get("showPromoted", catalogued_show_promoted(ini, start_fen)))
    rules_gate = bool(doc.get("rulesGate", catalogued_rules_gate(ini)))
    rules_pass = bool(doc.get("rulesPass", catalogued_rules_pass(ini)))
    rules_arrowing = bool(doc.get("rulesArrowing", False))
    show_check_counters = bool(doc.get("showCheckCounters", catalogued_show_check_counters(ini)))

    client_doc: CataloguedVariantClientDocument = {
        "name": str(doc["name"]),
        "displayName": str(doc.get("displayName") or doc["name"]),
        "tooltip": tooltip,
        "ini": ini,
        "baseVariant": base_variant or (extract_variant_base_name(ini) if ini else ""),
        "startFen": start_fen,
        "randomStart": catalogued_random_start(
            ini, start_fen, int(doc["width"]), int(doc["height"])
        ),
        "width": int(doc["width"]),
        "height": int(doc["height"]),
        "pieces": pieces,
        "kingRoles": king_roles,
        "pocketRoles": pocket_roles,
        "captureToHand": capture_to_hand,
        "promotionType": promotion_type,
        "promotionRoles": promotion_roles,
        "promotionOrder": promotion_order,
        "showPromoted": show_promoted,
        "rulesGate": rules_gate,
        "rulesPass": rules_pass,
        "rulesArrowing": rules_arrowing,
        "showCheckCounters": show_check_counters,
        "category": CATALOGUED_CATEGORY,
        "author": str(doc.get("author") or ""),
        "source": _catalogued_source(doc),
        "system": _is_fsf_builtin_catalogued_doc(doc),
        "visibility": _catalogued_visibility(doc),
        "pieceSetDirectional": bool(doc.get("pieceSetDirectional", False)),
        "directionalPieceSet": _catalogued_piece_set_is_directional(doc),
        "hasPieceSet": _has_complete_piece_set(doc),
        "hasBoard": _has_board_svg(doc),
        "archived": bool(doc.get("archived", False)),
        "enabled": bool(doc.get("enabled", True)),
    }
    if client_doc["source"] == CATALOGUED_SOURCE_USER and ini:
        nnue_base_variant = extract_variant_base_name(ini)
        # A section-only fingerprint is sufficient only when the inherited base
        # is an engine/site built-in whose meaning a different UDV cannot
        # replace. Custom-on-custom inheritance would need a full chain identity,
        # so keep those variants on the manual NNUE path for now.
        if not nnue_base_variant or _is_builtin_variant_name(nnue_base_variant):
            try:
                client_doc["nnueFingerprint"] = fsf_ini_v1_fingerprint(ini)
            except ValueError:
                # Existing/historical catalogued variants should remain renderable
                # even if their stored INI cannot be fingerprinted conservatively.
                pass
    client_variant = str(doc.get("clientVariant") or "").strip()
    if client_variant:
        client_doc["clientVariant"] = client_variant
    premove_variant = str(doc.get("premoveVariant") or "").strip()
    if premove_variant:
        client_doc["premoveVariant"] = premove_variant
    piece_names = parse_catalogued_piece_names(doc.get("pieceNames"))
    if piece_names:
        client_doc["pieceNames"] = piece_names
    betza_pieces = catalogued_betza_pieces(doc)
    if betza_pieces:
        client_doc["betzaPieces"] = betza_pieces
    if _is_fsf_builtin_catalogued_doc(doc):
        client_doc["fsfBuiltinVariant"] = _fsf_builtin_variant_name(doc)
        references = _catalogued_references_for_display(doc)
        if references:
            client_doc["references"] = references
    piece_family_override = _catalogued_piece_family_override(doc)
    if piece_family_override:
        client_doc["pieceFamilyOverride"] = piece_family_override
    board_family_override = _catalogued_board_family_override(doc)
    if board_family_override:
        client_doc["boardFamilyOverride"] = board_family_override
    if client_doc["hasPieceSet"]:
        client_doc["pieceSetRevision"] = _piece_set_revision(doc)
    if client_doc["hasBoard"]:
        client_doc["boardRevision"] = _board_svg_revision(doc)
    ai_disabled_until = catalogued_variant_ai_disabled_until(doc)
    if ai_disabled_until is not None:
        client_doc["aiDisabled"] = True
        client_doc["aiDisabledUntil"] = ai_disabled_until
        if doc.get("aiDisabledReason"):
            client_doc["aiDisabledReason"] = str(doc["aiDisabledReason"])
    if favorite_names is not None and str(client_doc["name"]) in favorite_names:
        client_doc["favorite"] = True
    if game_count is not None:
        client_doc["gameCount"] = game_count
        client_doc["locked"] = game_count > 0
    elif "gameCount" in doc:
        client_doc["gameCount"] = int(doc.get("gameCount") or 0)
    client_doc["favoriteCount"] = max(0, int(doc.get("favoriteCount") or 0))
    return client_doc


def _is_active_catalogued_game_participant(
    app_state: Any,
    name: str,
    username: str | None,
) -> bool:
    if not username:
        return False
    for game in getattr(app_state, "games", {}).values():
        if getattr(game, "variant", None) != name or getattr(game, "status", STARTED) > STARTED:
            continue
        if username in {
            str(getattr(getattr(game, "wplayer", None), "username", "")),
            str(getattr(getattr(game, "bplayer", None), "username", "")),
        }:
            return True
    return False


async def find_catalogued_variant_doc(
    app_state: Any,
    name: str,
    username: str | None = None,
) -> Mapping[str, Any] | None:
    docs = getattr(app_state, "catalogued_variants", {})
    doc = docs.get(name)
    if doc is None and app_state.db is not None:
        doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    if _can_open_catalogued_doc(username, doc) or _is_active_catalogued_game_participant(
        app_state, name, username
    ):
        return doc
    return None


def catalogued_variant_client_doc_for_name(
    app_state: Any,
    name: str,
    username: str | None = None,
) -> CataloguedVariantClientDocument | None:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None or not _can_open_catalogued_doc(username, doc):
        return None
    return _client_doc(doc)


async def catalogued_variant_client_doc_for_game(
    app_state: Any,
    game: Any,
    username: str,
) -> CataloguedVariantClientDocument | None:
    """Return variant metadata needed by a participant's existing game.

    Existing games must remain renderable after their catalogued variant becomes
    private, unlisted, or archived.  This deliberately bypasses normal catalogue
    visibility checks, but only after verifying that ``username`` is one of the
    game's players.
    """

    if not username or username not in {
        str(getattr(getattr(game, "wplayer", None), "username", "")),
        str(getattr(getattr(game, "bplayer", None), "username", "")),
    }:
        return None

    if not isinstance(getattr(game, "server_variant", None), CataloguedServerVariant):
        return None

    name = str(getattr(game, "variant", ""))
    if not name:
        return None

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None and getattr(app_state, "db", None) is not None:
        doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    return _client_doc(doc)


def can_create_catalogued_seek(app_state: Any, name: str, username: str | None) -> bool:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return False
    return _can_open_catalogued_doc(username, doc)


def is_public_catalogued_variant(app_state: Any, name: str) -> bool:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return False
    return (
        _is_active_catalogued_doc(doc)
        and _catalogued_visibility(doc) == CATALOGUED_VISIBILITY_PUBLIC
    )


def catalogued_variant_allows_fishnet(app_state: Any, name: str) -> bool:
    """Return whether Fairy-Stockfish/fishnet should currently handle this variant."""

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return not is_catalogued_variant(name)
    return not catalogued_variant_ai_disabled(doc)


async def record_catalogued_variant_ai_failure(
    app_state: Any,
    name: str,
    reason: str,
) -> bool:
    """Record a fishnet engine failure and quarantine the variant after repeated failures.

    Returns True when this call put the variant into the temporary AI-disabled state.
    """

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return False

    now = datetime.now(UTC)
    failure_count = int(doc.get("aiFailureCount") or 0) + 1
    update_set: dict[str, Any] = {
        "aiFailureCount": failure_count,
        "aiLastFailureAt": now,
        "aiLastFailureReason": reason,
    }
    disabled = failure_count >= CATALOGUED_AI_FAILURE_LIMIT
    if disabled:
        update_set.update(
            {
                "aiDisabledAt": now,
                "aiDisabledUntil": now + timedelta(seconds=CATALOGUED_AI_DISABLE_SECONDS),
                "aiDisabledReason": reason,
            }
        )

    if getattr(app_state, "db", None) is not None:
        try:
            await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
                {"_id": name}, {"$set": update_set}
            )
        except Exception:
            log.exception("Failed to persist catalogued variant AI failure for %s", name)

    doc.update(update_set)
    if disabled:
        log.warning(
            "Temporarily disabled Fairy-Stockfish AI for catalogued variant %s after %s failures "
            "(latest reason=%s)",
            name,
            failure_count,
            reason,
        )
    return disabled


async def clear_catalogued_variant_ai_failures(app_state: Any, name: str) -> None:
    """Clear transient fishnet AI failure/quarantine fields after successful engine work."""

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return

    fields = {
        "aiFailureCount",
        "aiLastFailureAt",
        "aiLastFailureReason",
        "aiDisabledAt",
        "aiDisabledUntil",
        "aiDisabledReason",
    }
    if not any(field in doc for field in fields):
        return

    if getattr(app_state, "db", None) is not None:
        try:
            await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
                {"_id": name}, {"$unset": {field: "" for field in fields}}
            )
        except Exception:
            log.exception("Failed to clear catalogued variant AI failure fields for %s", name)

    for field in fields:
        doc.pop(field, None)


def public_catalogued_variants_for_forms(app_state: Any) -> dict[str, Any]:
    """Return public uploaded variants that are safe in durable site events."""

    docs = getattr(app_state, "catalogued_variants", {})
    return {
        name: get_server_variant(name, False)
        for name, doc in sorted(
            docs.items(),
            key=lambda item: str(item[1].get("displayName", item[0])).casefold(),
        )
        if is_public_catalogued_variant(app_state, name)
    }


def catalogued_variant_rule_context(doc: Mapping[str, Any]) -> dict[str, Any]:
    ini = str(doc.get("rulesIni") or doc.get("ini") or "")
    start_fen = str(doc.get("startFen") or "")
    pieces = list(doc.get("pieces") or piece_letters_from_fen(start_fen or "8/8/8/8/8/8/8/8"))
    width = int(doc.get("width") or 0)
    height = int(doc.get("height") or 0)
    if not width or not height:
        width, height = board_dimensions_from_fen(start_fen) if start_fen else (8, 8)
    king_roles = list(doc.get("kingRoles") or catalogued_king_roles(ini, pieces))

    return {
        "name": str(doc.get("name") or doc.get("_id") or ""),
        "system": _is_fsf_builtin_catalogued_doc(doc),
        "displayName": str(
            doc.get("displayName") or doc.get("name") or doc.get("_id") or "Catalogued variant"
        ),
        "description": _catalogued_description(doc),
        "author": str(doc.get("author") or ""),
        "references": _catalogued_references_for_display(doc),
        "ini": ini,
        "startFen": start_fen,
        "width": width,
        "height": height,
        "pieces": ", ".join(pieces),
        "pocketRoles": ", ".join(
            _catalogued_pocket_roles_from_doc(doc, ini, start_fen, pieces, king_roles)
        ),
        "promotionRoles": ", ".join(
            list(doc.get("promotionRoles") or catalogued_promotion_roles(ini, pieces))
        ),
        "captureToHand": bool(
            doc.get("captureToHand", _ini_bool(ini, "capturesToHand", default=False))
        ),
        "enabled": bool(doc.get("enabled", True)),
        "archived": bool(doc.get("archived", False)),
        "visibility": _catalogued_visibility(doc),
        "ruleSummary": catalogued_rule_summary(doc),
        "customPieceDiagrams": catalogued_betza_diagrams(doc),
    }


def catalogued_variants_for_client(
    app_state: Any,
    username: str | None = None,
    favorite_names: set[str] | None = None,
) -> list[CataloguedVariantClientDocument]:
    docs = getattr(app_state, "catalogued_variants", {})
    return [
        _client_doc(doc, favorite_names=favorite_names)
        for doc in sorted(
            docs.values(), key=lambda item: str(item.get("displayName", item["name"])).casefold()
        )
        if _can_preload_catalogued_doc(username, doc)
    ]


def register_catalogued_variant_doc(
    app_state: Any,
    doc: Mapping[str, Any],
    *,
    load_config: bool = True,
) -> None:
    name = str(doc["name"])
    if not _is_active_catalogued_doc(doc):
        getattr(app_state, "catalogued_variants", {}).pop(name, None)
        unregister_catalogued_server_variant(name)
        return

    ini = str(doc.get("ini") or "")
    start_fen = str(doc.get("startFen") or "")
    _ensure_catalogued_start_fen_has_side_to_move(start_fen)
    is_fsf_builtin = _is_fsf_builtin_catalogued_doc(doc)
    if not is_fsf_builtin:
        _ensure_catalogued_rules_supported(ini)

    if load_config and not is_fsf_builtin:
        sf.load_variant_config(ini)

    width = int(doc.get("width") or 0)
    height = int(doc.get("height") or 0)
    if not width or not height:
        width, height = board_dimensions_from_fen(start_fen)

    register_catalogued_server_variant(
        name,
        str(doc.get("displayName") or name),
        random_start=catalogued_random_start(ini, start_fen, width, height),
        grand=_catalogued_grand_from_dimensions(width, height),
        extended_move_codec=_catalogued_extended_move_codec_from_dimensions(width, height),
        arrowing=bool(doc.get("rulesArrowing", False)),
        show_promoted=bool(doc.get("showPromoted", catalogued_show_promoted(ini, start_fen))),
        legal_moves_need_history=bool(
            doc.get("legalMovesNeedHistory", catalogued_legal_moves_need_history(ini))
        ),
        n_fold_is_draw=bool(doc.get("nFoldIsDraw", catalogued_n_fold_is_draw(ini))),
    )
    app_state.catalogued_variants[name] = dict(doc)


def register_historical_catalogued_variant_doc(doc: Mapping[str, Any]) -> None:
    """Register server metadata for a saved/archived catalogued variant.

    Historical games and tournaments must remain readable after the catalogue entry
    is archived.  Unlike ``register_catalogued_variant_doc()``, this helper does not
    add the document back to ``app_state.catalogued_variants`` and therefore does not
    make it eligible for new seeks or tournament creation.
    """

    name = str(doc.get("v") or doc.get("name") or "")
    ini = str(doc.get("ini") or doc.get("vini") or "")
    if not name or not ini or is_catalogued_variant(name):
        return

    validated = validate_catalogued_ini(ini)
    if validated.name != name:
        raise ValueError(
            f"Historical catalogued variant INI defines {validated.name!r}, but record uses {name!r}"
        )

    width = int(doc.get("width") or validated.width)
    height = int(doc.get("height") or validated.height)
    start_fen = str(doc.get("startFen") or validated.start_fen)
    register_catalogued_server_variant(
        name,
        str(doc.get("displayName") or doc.get("vd") or name),
        random_start=catalogued_random_start(ini, start_fen, width, height),
        grand=_catalogued_grand_from_dimensions(width, height),
        extended_move_codec=_catalogued_extended_move_codec_from_dimensions(width, height),
        arrowing=bool(doc.get("rulesArrowing", False)),
        show_promoted=bool(doc.get("showPromoted", catalogued_show_promoted(ini, start_fen))),
        legal_moves_need_history=bool(
            doc.get("legalMovesNeedHistory", catalogued_legal_moves_need_history(ini))
        ),
        n_fold_is_draw=bool(doc.get("nFoldIsDraw", catalogued_n_fold_is_draw(ini))),
    )


async def catalogued_variant_client_doc_for_tournament(
    app_state: Any, name: str
) -> CataloguedVariantClientDocument | None:
    """Return metadata needed to render a historical tournament variant.

    Tournament variants are public at creation time.  Keep their historical pages
    renderable even if the catalogue entry is later archived or made non-public.
    """

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None and getattr(app_state, "db", None) is not None:
        doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    return _client_doc(doc)


async def _remove_catalogued_variant_seeks(app_state: Any, name: str) -> int:
    """Remove live/persisted seeks that can no longer use a catalogued variant."""

    removed = 0
    seeks = getattr(app_state, "seeks", {})
    invites = getattr(app_state, "invites", {})
    for seek_id, seek in tuple(seeks.items()):
        if seek.variant != name:
            continue
        seeks.pop(seek_id, None)
        seek.creator.seeks.pop(seek_id, None)
        if seek.game_id is not None:
            invites.pop(seek.game_id, None)
        removed += 1

    db = getattr(app_state, "db", None)
    seek_collection = getattr(db, "seek", None) if db is not None else None
    if seek_collection is not None:
        await seek_collection.delete_many({"variant": name})

    if removed:
        log.info("Removed %s seek(s) for unavailable catalogued variant %s", removed, name)
        lobby = getattr(app_state, "lobby", None)
        if lobby is not None:
            await lobby.lobby_broadcast_seeks()
    return removed


def _catalogued_tournament_snapshot(doc: Mapping[str, Any]) -> dict[str, str]:
    ini = str(doc.get("ini") or "")
    if not ini:
        return {}
    return {
        "vini": ini,
        "vd": str(doc.get("displayName") or doc.get("name") or ""),
        "vby": str(doc.get("author") or ""),
    }


async def _snapshot_catalogued_variant_tournaments(
    app_state: Any, name: str, doc: Mapping[str, Any]
) -> None:
    """Backfill the variant rules onto tournament records before archival."""

    db = getattr(app_state, "db", None)
    if db is None:
        return
    tournament_collection = getattr(db, "tournament", None)
    if tournament_collection is None:
        return
    snapshot = _catalogued_tournament_snapshot(doc)
    if snapshot:
        await tournament_collection.update_many({"v": name}, {"$set": snapshot})


async def _migrate_catalogued_variant_tournaments(
    app_state: Any, old_name: str, new_name: str, doc: Mapping[str, Any]
) -> None:
    """Move no-game tournament references along with a renamed variant."""

    db = getattr(app_state, "db", None)
    tournament_collection = getattr(db, "tournament", None) if db is not None else None
    if tournament_collection is not None:
        update = {"v": new_name, **_catalogued_tournament_snapshot(doc)}
        await tournament_collection.update_many({"v": old_name}, {"$set": update})

    server_variant = get_server_variant(new_name, False)
    for tournament in getattr(app_state, "tournaments", {}).values():
        if getattr(tournament, "variant", None) != old_name:
            continue
        tournament.variant = new_name
        tournament.server_variant = server_variant
        tournament.browser_title = "%s Tournament • %s" % (
            server_variant.display_name,
            tournament.name,
        )


async def _remove_catalogued_variant_tournaments(app_state: Any, name: str) -> int:
    """Cancel and remove tournaments whose variant is being deleted.

    Variant deletion is already forbidden once a saved game exists, so these
    tournaments have no game history to preserve.
    """

    db = getattr(app_state, "db", None)
    if db is None:
        return 0
    tournament_collection = getattr(db, "tournament", None)
    if tournament_collection is None:
        return 0

    tournament_docs = [
        doc
        async for doc in tournament_collection.find(
            {"v": name}, projection={"_id": 1, "nbPlayers": 1, "nbGames": 1}
        )
    ]
    if not tournament_docs:
        return 0
    if any(
        int(doc.get("nbPlayers") or 0) > 0 or int(doc.get("nbGames") or 0) > 0
        for doc in tournament_docs
    ):
        raise web.HTTPConflict(
            text=(
                "This variant is already used by a tournament with participants or games. "
                "Archive it instead of deleting it."
            )
        )

    tournament_ids = [str(doc["_id"]) for doc in tournament_docs]
    for tournament_id in tournament_ids:
        tournament = getattr(app_state, "tournaments", {}).get(tournament_id)
        if tournament is not None and getattr(tournament, "status", 0) <= T_STARTED:
            await tournament.abort()

    query = {"tid": {"$in": tournament_ids}}
    await db.tournament_player.delete_many(query)
    await db.tournament_pairing.delete_many(query)
    await db.tournament_arrangement.delete_many(query)
    await db.tournament_chat.delete_many(query)
    await tournament_collection.delete_many({"_id": {"$in": tournament_ids}})
    log.info(
        "Removed %s tournament(s) for deleted catalogued variant %s",
        len(tournament_ids),
        name,
    )
    return len(tournament_ids)


def ensure_catalogued_variant_from_game_doc(app_state: Any, doc: Mapping[str, Any]) -> None:
    """Load an inline variant definition saved with a historical game if needed."""
    code = str(doc.get("v") or "")
    if not code or is_catalogued_variant(code) or not doc.get("vini"):
        return

    validated = validate_catalogued_ini(str(doc["vini"]))
    name = validated.name
    if name != code:
        raise ValueError(f"Inline game variant INI defines {name!r}, but game uses {code!r}")

    now = datetime.now(UTC)
    register_catalogued_variant_doc(
        app_state,
        {
            "_id": name,
            "name": name,
            "displayName": str(doc.get("vd") or name),
            "description": "Loaded from saved game",
            "author": str(doc.get("vby") or ""),
            "ini": str(doc["vini"]),
            "baseVariant": validated.base_variant,
            "enabled": True,
            "archived": False,
            "startFen": validated.start_fen,
            "width": validated.width,
            "height": validated.height,
            "pieces": validated.pieces,
            "kingRoles": validated.king_roles,
            "pocketRoles": validated.pocket_roles,
            "captureToHand": validated.capture_to_hand,
            "promotionType": validated.promotion_type,
            "promotionRoles": validated.promotion_roles,
            "promotionOrder": validated.promotion_order,
            "showPromoted": validated.show_promoted,
            "rulesGate": validated.rules_gate,
            "rulesPass": validated.rules_pass,
            "rulesArrowing": False,
            "legalMovesNeedHistory": validated.legal_moves_need_history,
            "nFoldIsDraw": validated.n_fold_is_draw,
            "showCheckCounters": validated.show_check_counters,
            "category": CATALOGUED_CATEGORY,
            "visibility": CATALOGUED_VISIBILITY_PRIVATE,
            "createdAt": now,
            "updatedAt": now,
        },
        load_config=False,
    )


async def _remove_legacy_catalogued_icon_fields(collection: Any) -> None:
    """Drop the old persisted copy of the code-defined catalogue icon."""
    result = await collection.update_many(
        {"icon": {"$exists": True}},
        {"$unset": {"icon": ""}},
    )
    if result.modified_count:
        log.info("Removed legacy icon field from %d catalogued variants", result.modified_count)


async def _remove_legacy_fsf_builtin_description_fields(collection: Any) -> None:
    """Drop the persisted copy of the code-defined built-in description."""
    result = await collection.update_many(
        {
            "source": CATALOGUED_SOURCE_FSF_BUILTIN,
            "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        },
        {"$unset": {"description": ""}},
    )
    if result.modified_count:
        log.info(
            "Removed legacy default description from %d Fairy-Stockfish built-ins",
            result.modified_count,
        )


async def init_catalogued_variants(app_state: Any) -> None:
    app_state.catalogued_variants = {}

    collection = app_state.db[CATALOGUED_VARIANT_COLLECTION]
    await _remove_legacy_catalogued_icon_fields(collection)
    await _remove_legacy_fsf_builtin_description_fields(collection)

    await ensure_fsf_catalogued_builtin_variants(app_state)

    cursor = collection.find({"enabled": {"$ne": False}, "archived": {"$ne": True}})
    async for doc in cursor:
        try:
            register_catalogued_variant_doc(app_state, doc)
        except web.HTTPException as exc:
            log.warning(
                "Skipped catalogued variant %s: %s",
                doc.get("name"),
                exc.text or exc.reason,
            )
        except Exception:
            log.exception("Failed to load catalogued variant %s", doc.get("name"))


async def get_catalogued_variants(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    favorite_names: set[str] | None = None
    if username is not None:
        user = await app_state.users.get(username)
        favorite_names = _clean_favorite_names(getattr(user, "catalogued_variant_favorites", set()))
    return json_response(
        {
            "variants": catalogued_variants_for_client(
                app_state, username, favorite_names=favorite_names
            )
        }
    )


async def _optional_human_username(request: web.Request) -> str | None:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    username = session.get("user_name")
    if not username or str(username).startswith(ANON_PREFIX):
        return None

    user = await app_state.users.get(username)
    if user.anon or user.bot:
        return None

    return str(username)


async def _current_human_username(request: web.Request) -> str:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    username = session.get("user_name")
    if not username or str(username).startswith(ANON_PREFIX):
        raise web.HTTPForbidden(text="Only logged-in users can manage catalogued variants.")

    user = await app_state.users.get(username)
    if user.anon or user.bot:
        raise web.HTTPForbidden(text="Only logged-in human users can manage catalogued variants.")

    return str(username)


def _can_modify(username: str, doc: Mapping[str, Any]) -> bool:
    return doc.get("author") == username or _is_admin_username(username)


async def _game_count(app_state: Any, name: str) -> int:
    if app_state.db is None:
        return 0
    return await app_state.db.game.count_documents({"v": name})


async def _has_games(app_state: Any, name: str) -> bool:
    if app_state.db is None:
        return False
    return await app_state.db.game.find_one({"v": name}, projection={"_id": 1}) is not None


def catalogued_variant_games_are_persisted(app_state: Any, name: str) -> bool:
    """Return whether newly created games for this catalogued variant are saved.

    The decision is intentionally made at game creation time. Public variants
    create durable games; private and unlisted variants are test/sandbox
    variants whose games remain in memory only.
    """

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        # Preserve the old behaviour for unexpected/migrating runtime state.
        return True
    return _catalogued_visibility(doc) == CATALOGUED_VISIBILITY_PUBLIC


def _has_active_catalogued_games(app_state: Any, name: str) -> bool:
    for game in getattr(app_state, "games", {}).values():
        if getattr(game, "variant", None) == name and getattr(game, "status", STARTED) <= STARTED:
            return True
    return False


async def increment_catalogued_variant_game_count(app_state: Any, name: str) -> None:
    """Increment the stored played-game counter for a saved catalogued game."""

    if app_state.db is None or not _is_valid_variant_name(name):
        return

    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name}, {"$inc": {"gameCount": 1}}
    )
    if not result.matched_count:
        return

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is not None:
        doc["gameCount"] = int(doc.get("gameCount") or 0) + 1


async def increment_catalogued_variant_game_count_once(
    app_state: Any, name: str, game_id: str
) -> None:
    """Count a tournament game exactly once across restart recovery."""

    if app_state.db is None or not _is_valid_variant_name(name):
        return

    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {
            "_id": name,
            "gameCountEffectIds": {"$ne": game_id},
        },
        {
            "$inc": {"gameCount": 1},
            "$push": {
                "gameCountEffectIds": {
                    "$each": [game_id],
                    "$slice": -64,
                }
            },
        },
    )
    if not result.modified_count:
        return

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is not None:
        doc["gameCount"] = int(doc.get("gameCount") or 0) + 1


async def _catalogued_variant_slot_count_for_user(app_state: Any, username: str) -> int:
    if app_state.db is None:
        return 0
    # Archived variants are historical records, not active variant slots. In
    # particular, variants with saved public games may need to be archived
    # instead of deleted, so counting them here could permanently exhaust a
    # user's quota.
    return await app_state.db[CATALOGUED_VARIANT_COLLECTION].count_documents(
        {"author": username, "archived": {"$ne": True}}
    )


async def _refresh_catalogued_variant_profile_count(app_state: Any, username: str) -> None:
    if not username or _catalogued_variant_user_collection(app_state) is None:
        return
    from profile_counts import refresh_user_counter

    await refresh_user_counter(app_state, username, "variantCount")


async def _ensure_catalogued_variant_quota(app_state: Any, username: str) -> None:
    if _is_admin_username(username):
        return
    count = await _catalogued_variant_slot_count_for_user(app_state, username)
    if count >= MAX_CATALOGUED_VARIANTS_PER_USER:
        raise web.HTTPConflict(
            text=(
                f"You can have at most {MAX_CATALOGUED_VARIANTS_PER_USER} user-defined variants. "
                "Archive or delete an active variant before uploading, cloning, or restoring "
                "another one."
            )
        )


def _search_regex(text: str) -> re.Pattern[str]:
    # Escape user text before handing it to MongoDB as a regex. This keeps the
    # catalogued-variant searches simple while avoiding user-controlled regex execution.
    return re.compile(re.escape(text), re.IGNORECASE)


async def community_catalogued_variants_page(
    app_state: Any,
    *,
    q: str = "",
    author: str = "",
    sort: str = "updated",
    page: int = 1,
    favorite_names: set[str] | None = None,
    favorites_only: bool = False,
) -> dict[str, Any]:
    q = q.strip()[:80]
    author = author.strip()[:40]
    page = max(1, page)
    can_favorite = favorite_names is not None
    favorite_names = _clean_favorite_names(favorite_names or set())
    favorites_only = favorites_only and can_favorite

    if app_state.db is None:
        return {
            "variants": [],
            "q": q,
            "author": author,
            "sort": sort,
            "favoritesOnly": favorites_only,
            "canFavorite": can_favorite,
            "page": 1,
            "pages": 1,
            "total": 0,
            "prev_page": None,
            "next_page": None,
        }

    query = _catalogued_public_query()
    if q:
        regex = _search_regex(q)
        query["$or"] = [
            {"name": {"$regex": regex}},
            {"displayName": {"$regex": regex}},
            {"description": {"$regex": regex}},
            {"author": {"$regex": regex}},
        ]
    if author:
        query["author"] = author
    if favorites_only:
        if favorite_names:
            query["name"] = {"$in": sorted(favorite_names)}
        else:
            return {
                "variants": [],
                "q": q,
                "author": author,
                "sort": sort,
                "favoritesOnly": favorites_only,
                "canFavorite": can_favorite,
                "page": 1,
                "pages": 1,
                "total": 0,
                "prev_page": None,
                "next_page": None,
            }

    use_favorite_sort = sort == "favorites" and can_favorite
    if sort == "name":
        sort_spec = [("displayName", 1), ("name", 1)]
    elif sort == "newest":
        sort_spec = [("createdAt", -1), ("name", 1)]
    elif sort == "played":
        sort_spec = [("gameCount", -1), ("updatedAt", -1), ("name", 1)]
    elif sort == "favorited":
        sort_spec = [("favoriteCount", -1), ("updatedAt", -1), ("name", 1)]
    elif use_favorite_sort:
        sort_spec = [("updatedAt", -1), ("name", 1)]
    else:
        sort = "updated"
        sort_spec = [("updatedAt", -1), ("name", 1)]

    total = await app_state.db[CATALOGUED_VARIANT_COLLECTION].count_documents(query)
    pages = max(1, (total + CATALOGUED_COMMUNITY_PAGE_SIZE - 1) // CATALOGUED_COMMUNITY_PAGE_SIZE)
    page = min(page, pages)
    skip = (page - 1) * CATALOGUED_COMMUNITY_PAGE_SIZE

    variants: list[dict[str, Any]] = []
    if use_favorite_sort:
        cursor = await app_state.db[CATALOGUED_VARIANT_COLLECTION].aggregate(
            [
                {"$match": query},
                {
                    "$addFields": {
                        "favoriteSort": {
                            "$cond": [{"$in": ["$name", sorted(favorite_names)]}, 0, 1]
                        }
                    }
                },
                {"$sort": {"favoriteSort": 1, "updatedAt": -1, "name": 1}},
                {"$skip": skip},
                {"$limit": CATALOGUED_COMMUNITY_PAGE_SIZE},
            ]
        )
    else:
        cursor = (
            app_state.db[CATALOGUED_VARIANT_COLLECTION]
            .find(query)
            .sort(sort_spec)
            .skip(skip)
            .limit(CATALOGUED_COMMUNITY_PAGE_SIZE)
        )
    async for doc in cursor:
        name = str(doc.get("name") or doc.get("_id") or "")
        count = int(doc.get("gameCount") or 0)
        variants.append(
            {
                "name": name,
                "displayName": str(doc.get("displayName") or name),
                "description": _catalogued_description(doc),
                "author": str(doc.get("author") or ""),
                "system": _is_fsf_builtin_catalogued_doc(doc),
                "references": _catalogued_references_for_display(doc),
                "width": int(doc.get("width") or 0),
                "height": int(doc.get("height") or 0),
                "gameCount": count,
                "favoriteCount": max(0, int(doc.get("favoriteCount") or 0)),
                "updatedAt": doc.get("updatedAt"),
                "favorite": name in favorite_names,
                "hasStartBoard": bool(doc.get("startFen")),
            }
        )

    return {
        "variants": variants,
        "q": q,
        "author": author,
        "sort": sort,
        "favoritesOnly": favorites_only,
        "canFavorite": can_favorite,
        "page": page,
        "pages": pages,
        "total": total,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < pages else None,
    }


async def set_catalogued_variant_favorite(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _current_human_username(request)
    name = request.match_info["name"]
    if not _is_valid_variant_name(name):
        raise web.HTTPBadRequest(text=VARIANT_NAME_ERROR)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one(
        {"_id": name, **_catalogued_public_query()},
        projection={"_id": 1, "favoriteCount": 1},
    )
    if doc is None:
        raise web.HTTPNotFound(text="Public catalogued variant not found.")

    data = await read_json_data(request)
    if not isinstance(data, Mapping):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    favorite = bool(data.get("favorite"))

    user = await app_state.users.get(username)
    favorites = _clean_favorite_names(getattr(user, "catalogued_variant_favorites", set()))
    if favorite:
        if name not in favorites and len(favorites) >= MAX_CATALOGUED_FAVORITES_PER_USER:
            raise web.HTTPConflict(
                text=f"You can favorite at most {MAX_CATALOGUED_FAVORITES_PER_USER} variants."
            )
        user_result = await app_state.db.user.update_one(
            {"_id": username}, {"$addToSet": {"cvf": name}}
        )
        favorites.add(name)
        delta = 1
    else:
        user_result = await app_state.db.user.update_one(
            {"_id": username}, {"$pull": {"cvf": name}}
        )
        favorites.discard(name)
        delta = -1

    favorite_count = max(0, int(doc.get("favoriteCount") or 0))
    if user_result.modified_count:
        updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one_and_update(
            {"_id": name},
            [
                {
                    "$set": {
                        "favoriteCount": {
                            "$max": [
                                0,
                                {
                                    "$add": [
                                        {"$ifNull": ["$favoriteCount", 0]},
                                        delta,
                                    ]
                                },
                            ]
                        }
                    }
                }
            ],
            projection={"favoriteCount": 1},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            if favorite:
                await app_state.db.user.update_one({"_id": username}, {"$pull": {"cvf": name}})
                favorites.discard(name)
            user.catalogued_variant_favorites = favorites
            raise web.HTTPNotFound(text="Public catalogued variant not found.")
        favorite_count = max(0, int(updated.get("favoriteCount") or 0))
        cached_doc = getattr(app_state, "catalogued_variants", {}).get(name)
        if cached_doc is not None:
            cached_doc["favoriteCount"] = favorite_count
    else:
        current = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one(
            {"_id": name}, projection={"favoriteCount": 1}
        )
        if current is None:
            raise web.HTTPNotFound(text="Public catalogued variant not found.")
        favorite_count = max(0, int(current.get("favoriteCount") or 0))

    user.catalogued_variant_favorites = favorites
    return json_response(
        {
            "ok": True,
            "name": name,
            "favorite": favorite,
            "favoriteCount": favorite_count,
        }
    )


async def _read_upload_payload(
    request: web.Request,
) -> tuple[str, str, str, dict[str, str], bool | None, str, str, str]:
    content_type = request.content_type or ""

    if content_type == "application/json":
        data = await read_json_data(request)
        if not isinstance(data, Mapping):
            raise web.HTTPBadRequest(text="Expected JSON object.")
        ini = str(data.get("ini") or "")
        display_name = normalize_catalogued_display_name(
            str(data.get("displayName") or data.get("display_name") or "")
        )
        description = str(data.get("description") or "")
        piece_names = parse_catalogued_piece_names(
            data.get("pieceNames", data.get("piece_names", ""))
        )
        piece_set_directional = _read_bool_metadata(
            data, "pieceSetDirectional", "piece_set_directional"
        )
        piece_family_override = _read_piece_family_override(data)
        board_family_override = _read_board_family_override(data)
        visibility = _clean_visibility(str(data.get("visibility") or CATALOGUED_VISIBILITY_PRIVATE))
        return (
            ini,
            display_name,
            description,
            piece_names,
            piece_set_directional,
            piece_family_override,
            board_family_override,
            visibility,
        )

    if content_type.startswith("text/"):
        ini = await read_text_data(request)
        return ini or "", "", "", {}, None, "", "", CATALOGUED_VISIBILITY_PRIVATE

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Missing form data.")

    upload = data.get("file") or data.get("ini_file")
    if hasattr(upload, "file"):
        raw = upload.file.read(MAX_CATALOGUED_INI_BYTES + 1)
        ini = raw.decode("utf-8", errors="replace")
    else:
        ini = str(data.get("ini") or "")

    display_name = normalize_catalogued_display_name(
        str(data.get("displayName") or data.get("display_name") or "")
    )
    description = str(data.get("description") or "")
    piece_names = parse_catalogued_piece_names(data.get("pieceNames", data.get("piece_names", "")))
    piece_set_directional = _read_bool_metadata(
        data, "pieceSetDirectional", "piece_set_directional"
    )
    piece_family_override = _read_piece_family_override(data)
    board_family_override = _read_board_family_override(data)
    visibility = _clean_visibility(str(data.get("visibility") or CATALOGUED_VISIBILITY_PRIVATE))
    return (
        ini,
        display_name,
        description,
        piece_names,
        piece_set_directional,
        piece_family_override,
        board_family_override,
        visibility,
    )


async def check_catalogued_variant_rules(request: web.Request) -> web.Response:
    await _current_human_username(request)
    app_state = get_app_state(request.app)
    data = await read_json_data(request)
    if not isinstance(data, Mapping):
        raise web.HTTPBadRequest(text="Expected JSON object.")

    ini = str(data.get("ini") or "").strip()
    current_name = data.get("currentName")
    current_name = str(current_name) if current_name else None
    if not ini:
        raise web.HTTPBadRequest(text="Missing INI content.")

    name = extract_variant_name(ini)
    catalogued_pychess_piece_roles(ini)
    existing = app_state.catalogued_variants.get(current_name) if current_name else None
    if existing is None or _strip_pychess_pieces_metadata(ini) != _strip_pychess_pieces_metadata(
        str(existing.get("ini") or "")
    ):
        _ensure_catalogued_rule_changes(ini)
    await ensure_catalogued_variant_name_available(app_state, name, current_name=current_name)
    start_fen = await check_catalogued_ini_without_mutating_server(ini, name)
    return json_response({"ok": True, "name": name, "startFen": start_fen})


def _catalogued_display_name_key(display_name: str) -> str:
    """Return a locale-independent key for exact canonical-name comparisons.

    User-entered display names are normalized separately by
    ``normalize_catalogued_display_name``.  This helper intentionally accepts
    canonical site names too, including punctuation that community display
    names may not permit (for example ``Khan's Chess``).
    """

    return unicodedata.normalize("NFKC", display_name).strip().casefold()


def _reserved_catalogued_display_names() -> dict[str, str]:
    """Canonical display names that community variants may not impersonate.

    First-class site variants and the active curated Fairy-Stockfish catalogue
    entries own their public names.  Candidates are deliberately excluded until
    they are actually exposed by pychess.  Ordinary community variants do not
    reserve names against one another.
    """

    reserved = {
        _catalogued_display_name_key(variant.translated_name): variant.translated_name
        for variant in ServerVariants
    }
    reserved.update(
        {
            _catalogued_display_name_key(str(metadata["displayName"])): str(metadata["displayName"])
            for metadata in FSF_CATALOGUED_BUILTIN_VARIANTS.values()
            if metadata.get("displayName")
        }
    )
    return reserved


def ensure_catalogued_display_name_available(
    display_name: str,
    *,
    variant_name: str,
    current_display_name: str | None = None,
    current_variant_name: str | None = None,
) -> None:
    """Reject community display names owned by canonical pychess variants.

    ``variant_name`` is used when the user leaves the optional display name
    blank, matching ``_build_doc``.  Existing legacy collisions are grandfathered
    only while both their display name and internal variant key remain unchanged;
    this lets authors edit descriptions/visibility without perpetuating the
    collision through a rename.
    """

    effective_name = _clean_display_name(display_name, variant_name)
    if current_display_name is not None and current_variant_name == variant_name:
        current_effective_name = _clean_display_name(current_display_name, variant_name)
        if effective_name == current_effective_name:
            return

    canonical_name = _reserved_catalogued_display_names().get(
        _catalogued_display_name_key(effective_name)
    )
    if canonical_name is None:
        return

    raise web.HTTPConflict(
        text=(
            f'"{effective_name}" is reserved for the official PyChess variant '
            f'"{canonical_name}". Please choose a distinct display name, such as '
            f'"{canonical_name} Custom" or "{canonical_name} Modified".'
        )
    )


def normalize_catalogued_display_name(display_name: str) -> str:
    """Validate and normalize a user-editable catalogue display name."""
    cleaned = unicodedata.normalize("NFKC", display_name).strip()
    if not cleaned:
        return ""
    if any(
        char not in DISPLAY_NAME_PUNCTUATION
        and not (unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd")
        for char in cleaned
    ):
        raise web.HTTPBadRequest(text=DISPLAY_NAME_ERROR)

    cleaned = DISPLAY_NAME_REPEATED_SEPARATOR_RE.sub(r"\1", cleaned)
    has_letter_or_number = any(
        unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd"
        for char in cleaned
    )
    if (
        len(cleaned) > MAX_DISPLAY_NAME_LEN
        or not has_letter_or_number
        or cleaned[0] in DISPLAY_NAME_DISALLOWED_EDGE_SEPARATORS
        or cleaned[-1] in DISPLAY_NAME_DISALLOWED_EDGE_SEPARATORS
    ):
        raise web.HTTPBadRequest(text=DISPLAY_NAME_ERROR)
    return cleaned


def _clean_display_name(display_name: str, fallback: str) -> str:
    return (display_name or fallback).strip()[:MAX_DISPLAY_NAME_LEN] or fallback


def _clean_description(description: str) -> str:
    return description.strip()[:MAX_DESCRIPTION_LEN]


def _clean_piece_name(piece: str, name: str) -> tuple[str, str]:
    letter = piece.strip().lower()
    if len(letter) != 1 or not letter.isascii() or not letter.isalpha():
        raise web.HTTPBadRequest(
            text="Invalid piece names. Use one ASCII letter before each colon, such as z:Zebra."
        )

    cleaned = " ".join(unicodedata.normalize("NFKC", name).split())
    if (
        not cleaned
        or len(cleaned) > MAX_PIECE_NAME_LEN
        or "," in cleaned
        or ":" in cleaned
        or any(unicodedata.category(char).startswith("C") for char in cleaned)
        or not any(
            unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd"
            for char in cleaned
        )
    ):
        raise web.HTTPBadRequest(
            text=(
                f"Piece names must be 1-{MAX_PIECE_NAME_LEN} characters, contain a letter "
                "or number, and cannot contain commas or colons."
            )
        )
    return letter, cleaned


def parse_catalogued_piece_names(value: object) -> dict[str, str]:
    """Parse user-facing ``letter:name`` metadata into a normalized mapping."""

    if value is None or value == "":
        return {}

    raw_entries: list[tuple[object, object]]
    if isinstance(value, Mapping):
        raw_entries = list(value.items())
    elif isinstance(value, str):
        if len(value) > MAX_PIECE_NAMES_TEXT_LEN:
            raise web.HTTPBadRequest(text="Piece names are too long.")
        raw_entries = []
        for entry in value.split(","):
            entry = entry.strip()
            if not entry:
                continue
            piece, separator, name = entry.partition(":")
            if not separator:
                raise web.HTTPBadRequest(
                    text=(
                        "Invalid piece names. Use comma-separated letter:name pairs, "
                        "such as p:Soldier, z:Zebra."
                    )
                )
            raw_entries.append((piece, name))
    else:
        raise web.HTTPBadRequest(
            text="Invalid piece names. Expected comma-separated letter:name pairs."
        )

    names: dict[str, str] = {}
    for raw_piece, raw_name in raw_entries:
        if not isinstance(raw_piece, str) or not isinstance(raw_name, str):
            raise web.HTTPBadRequest(text="Piece name letters and names must be text.")
        piece, name = _clean_piece_name(raw_piece, raw_name)
        if piece in names:
            raise web.HTTPBadRequest(text=f"Piece name {piece!r} is listed more than once.")
        names[piece] = name
    return names


def _build_doc(
    *,
    name: str,
    base_variant: str,
    display_name: str,
    description: str,
    piece_names: Mapping[str, str] | None,
    username: str,
    ini: str,
    start_fen: str,
    width: int,
    height: int,
    pieces: list[str],
    king_roles: list[str],
    pocket_roles: list[str],
    capture_to_hand: bool,
    promotion_type: str,
    promotion_roles: list[str],
    promotion_order: list[str],
    show_promoted: bool,
    rules_gate: bool,
    rules_pass: bool,
    legal_moves_need_history: bool,
    n_fold_is_draw: bool,
    show_check_counters: bool,
    created_at: datetime,
    rules_arrowing: bool = False,
    piece_set_directional: bool = False,
    visibility: str = CATALOGUED_VISIBILITY_PRIVATE,
    piece_family_override: str = "",
    board_family_override: str = "",
    archived: bool = False,
    game_count: int = 0,
    favorite_count: int = 0,
    source: str = CATALOGUED_SOURCE_USER,
    fsf_builtin_variant: str | None = None,
    client_variant: str = "",
    premove_variant: str = "",
) -> CataloguedVariantDocument:
    doc: CataloguedVariantDocument = {
        "_id": name,
        "name": name,
        "displayName": _clean_display_name(display_name, name),
        "description": _clean_description(description),
        "author": username,
        "ini": ini,
        "baseVariant": base_variant,
        "enabled": not archived,
        "archived": archived,
        "startFen": start_fen,
        "width": width,
        "height": height,
        "pieces": pieces,
        "kingRoles": king_roles,
        "pocketRoles": pocket_roles,
        "captureToHand": capture_to_hand,
        "promotionType": promotion_type,
        "promotionRoles": promotion_roles,
        "promotionOrder": promotion_order,
        "showPromoted": show_promoted,
        "rulesGate": rules_gate,
        "rulesPass": rules_pass,
        "rulesArrowing": rules_arrowing,
        "legalMovesNeedHistory": legal_moves_need_history,
        "nFoldIsDraw": n_fold_is_draw,
        "showCheckCounters": show_check_counters,
        "category": CATALOGUED_CATEGORY,
        "visibility": _clean_visibility(visibility),
        "pieceSetDirectional": piece_set_directional,
        "source": source,
        "gameCount": max(0, int(game_count)),
        "favoriteCount": max(0, int(favorite_count)),
        "createdAt": created_at,
        "updatedAt": datetime.now(UTC),
    }
    cleaned_piece_names = parse_catalogued_piece_names(piece_names)
    if cleaned_piece_names:
        doc["pieceNames"] = cleaned_piece_names
    if piece_family_override:
        doc["pieceFamilyOverride"] = _clean_piece_family_override(piece_family_override)
    if board_family_override:
        cleaned_board_family = _clean_board_family_override(board_family_override)
        _ensure_board_family_dimensions(cleaned_board_family, width, height)
        doc["boardFamilyOverride"] = cleaned_board_family
    if fsf_builtin_variant:
        doc["fsfBuiltinVariant"] = fsf_builtin_variant
    if client_variant:
        doc["clientVariant"] = client_variant
    if premove_variant:
        doc["premoveVariant"] = premove_variant
    return doc


def _fsf_metadata_string_list(metadata: Mapping[str, Any], key: str) -> list[str]:
    value = metadata.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        items = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = item.strip().lower()
        # An empty promotion suffix is the explicit "do not promote" choice.
        if (not item and key != "promotionOrder") or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _fsf_metadata_bool(metadata: Mapping[str, Any], key: str, default: bool) -> bool:
    value = metadata.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "yes", "1", "on"}
    return bool(value)


def _clean_catalogued_reference(value: Any) -> CataloguedVariantReference | None:
    if not isinstance(value, Mapping):
        return None

    url = str(value.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    label = str(value.get("label") or "").strip()[:80] or _reference_label_for_url(url)
    return {"label": label, "url": url}


def _clean_catalogued_references(value: Any) -> list[CataloguedVariantReference]:
    if not isinstance(value, (list, tuple)):
        return []

    seen: set[str] = set()
    references: list[CataloguedVariantReference] = []
    for item in value:
        reference = _clean_catalogued_reference(item)
        if reference is None or reference["url"] in seen:
            continue
        seen.add(reference["url"])
        references.append(reference)
    return references


def _fsf_legacy_reference_description(references: list[CataloguedVariantReference]) -> str:
    if not references:
        return FSF_CATALOGUED_BUILTIN_DESCRIPTION
    urls = ", ".join(reference["url"] for reference in references)
    return f"{FSF_CATALOGUED_BUILTIN_DESCRIPTION} Reference: {urls}"


def _fsf_builtin_description_is_auto(
    description: str, metadata: Mapping[str, Any], references: list[CataloguedVariantReference]
) -> bool:
    metadata_description = str(metadata.get("description") or FSF_CATALOGUED_BUILTIN_DESCRIPTION)
    return not description or description in {
        FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        metadata_description,
        _fsf_legacy_reference_description(references),
    }


def _catalogued_references_for_display(doc: Mapping[str, Any]) -> list[CataloguedVariantReference]:
    if not _is_fsf_builtin_catalogued_doc(doc):
        return []
    return _clean_catalogued_references(doc.get("references"))


def _fsf_builtin_description_for_doc(
    metadata: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
    references: list[CataloguedVariantReference],
) -> str:
    existing_description = str((existing or {}).get("description") or "")
    if _fsf_builtin_description_is_auto(existing_description, metadata, references):
        return ""
    return existing_description


def _build_fsf_builtin_doc(
    name: str,
    metadata: Mapping[str, Any],
    *,
    existing: Mapping[str, Any] | None = None,
) -> CataloguedVariantDocument:
    start_fen = sf.start_fen(name)
    if not start_fen:
        raise ValueError(f"Fairy-Stockfish did not provide a start FEN for {name!r}.")

    width, height = board_dimensions_from_fen(start_fen)
    _catalogued_grand_from_dimensions(width, height)
    pieces = _merge_piece_letters(
        _catalogued_piece_roles_from_ini("", start_fen),
        _fsf_metadata_string_list(metadata, "pieces"),
    )
    king_roles = _fsf_metadata_string_list(metadata, "kingRoles") or catalogued_king_roles(
        "", pieces
    )
    pocket_roles = _fsf_metadata_string_list(metadata, "pocketRoles") or catalogued_pocket_roles(
        "",
        start_fen,
        pieces,
        king_roles,
        capture_to_hand=_fsf_metadata_bool(metadata, "captureToHand", False),
    )
    promotion_type = str(metadata.get("promotionType") or catalogued_promotion_type(""))
    promotion_roles = _fsf_metadata_string_list(
        metadata, "promotionRoles"
    ) or catalogued_promotion_roles("", pieces)
    promotion_order = _fsf_metadata_string_list(
        metadata, "promotionOrder"
    ) or catalogued_promotion_order("", promotion_type)
    references = _clean_catalogued_references(metadata.get("references"))

    description = _fsf_builtin_description_for_doc(metadata, existing, references)
    doc = _build_doc(
        name=name,
        base_variant=str(metadata.get("baseVariant") or ""),
        display_name=str(
            (existing or {}).get("displayName") or metadata.get("displayName") or name
        ),
        description=description,
        piece_names=(existing or {}).get("pieceNames") or metadata.get("pieceNames"),
        username=CATALOGUED_FSF_BUILTIN_AUTHOR,
        ini="",
        start_fen=start_fen,
        width=width,
        height=height,
        pieces=pieces,
        king_roles=king_roles,
        pocket_roles=pocket_roles,
        capture_to_hand=_fsf_metadata_bool(metadata, "captureToHand", False),
        promotion_type=promotion_type,
        promotion_roles=promotion_roles,
        promotion_order=promotion_order,
        show_promoted=_fsf_metadata_bool(
            metadata, "showPromoted", catalogued_show_promoted("", start_fen)
        ),
        rules_gate=_fsf_metadata_bool(metadata, "rulesGate", False),
        rules_pass=_fsf_metadata_bool(metadata, "rulesPass", False),
        rules_arrowing=_fsf_metadata_bool(metadata, "rulesArrowing", False),
        legal_moves_need_history=_fsf_metadata_bool(metadata, "legalMovesNeedHistory", False),
        n_fold_is_draw=_fsf_metadata_bool(metadata, "nFoldIsDraw", False),
        show_check_counters=_fsf_metadata_bool(metadata, "showCheckCounters", False),
        created_at=cast(datetime, (existing or {}).get("createdAt") or datetime.now(UTC)),
        visibility=str((existing or {}).get("visibility") or CATALOGUED_VISIBILITY_PUBLIC),
        archived=bool((existing or {}).get("archived", False)),
        game_count=int((existing or {}).get("gameCount") or 0),
        favorite_count=int((existing or {}).get("favoriteCount") or 0),
        source=CATALOGUED_SOURCE_FSF_BUILTIN,
        fsf_builtin_variant=name,
        client_variant=str(metadata.get("clientVariant") or ""),
        premove_variant=str(metadata.get("premoveVariant") or ""),
        piece_family_override=str(metadata.get("pieceFamilyOverride") or ""),
        board_family_override=str(metadata.get("boardFamilyOverride") or ""),
    )
    doc["references"] = references
    doc["rulesIni"] = str(metadata.get("rulesIni") or "").strip()
    if not description:
        doc.pop("description", None)
    return doc


def _fsf_builtin_synced_fields(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Fields controlled by the server-side curated FSF built-in list.

    Admin-editable metadata (displayName, description, visibility), assets,
    counters and AI-disable state are intentionally not overwritten at startup.
    Startup seeding may separately replace only the old generic description.
    """

    keys = (
        "name",
        "author",
        "ini",
        "rulesIni",
        "baseVariant",
        "clientVariant",
        "premoveVariant",
        "pieceFamilyOverride",
        "boardFamilyOverride",
        "enabled",
        "startFen",
        "width",
        "height",
        "pieces",
        "kingRoles",
        "pocketRoles",
        "captureToHand",
        "promotionType",
        "promotionRoles",
        "promotionOrder",
        "showPromoted",
        "rulesGate",
        "rulesPass",
        "rulesArrowing",
        "legalMovesNeedHistory",
        "nFoldIsDraw",
        "showCheckCounters",
        "category",
        "source",
        "fsfBuiltinVariant",
        "references",
    )
    return {key: doc[key] for key in keys if key in doc}


async def ensure_fsf_catalogued_builtin_variants(app_state: Any) -> None:
    if app_state.db is None:
        return

    collection = app_state.db[CATALOGUED_VARIANT_COLLECTION]
    if FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS:
        await collection.update_many(
            {
                "_id": {"$in": sorted(FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS)},
                "source": CATALOGUED_SOURCE_FSF_BUILTIN,
                "$or": [
                    {"enabled": {"$ne": False}},
                    {"archived": {"$ne": True}},
                ],
            },
            {
                "$set": {
                    "enabled": False,
                    "archived": True,
                    "updatedAt": datetime.now(UTC),
                }
            },
        )

    for name, metadata in FSF_CATALOGUED_BUILTIN_VARIANTS.items():
        if name not in BUILTIN_FSF_VARIANT_NAMES:
            log.warning(
                "Skipped FSF catalogued built-in %s: Fairy-Stockfish does not know it", name
            )
            continue

        existing = await collection.find_one({"_id": name})
        if existing is not None and not _is_fsf_builtin_catalogued_doc(existing):
            log.warning(
                "Skipped FSF catalogued built-in %s: a non-system catalogued variant already uses that key",
                name,
            )
            continue

        try:
            doc = _build_fsf_builtin_doc(name, metadata, existing=existing)
        except Exception:
            log.exception("Failed to prepare FSF catalogued built-in %s", name)
            continue

        if existing is None:
            try:
                await collection.insert_one(doc)
            except DuplicateKeyError:
                log.warning("Skipped FSF catalogued built-in %s: duplicate key", name)
            continue

        synced_fields = _fsf_builtin_synced_fields(doc)
        existing_description = str(existing.get("description") or "")
        references = _clean_catalogued_references(doc.get("references"))

        update: dict[str, Any] = {"$set": synced_fields}
        unset_fields = {
            field: ""
            for field in ("clientVariant", "premoveVariant")
            if field in existing and field not in doc
        }
        if _fsf_builtin_description_is_auto(existing_description, metadata, references):
            unset_fields["description"] = ""
        if unset_fields:
            update["$unset"] = unset_fields
        await collection.update_one(
            {"_id": name},
            update,
        )


async def upload_catalogued_variant(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _current_human_username(request)
    (
        ini,
        display_name,
        description,
        piece_names,
        piece_set_directional,
        piece_family_override,
        board_family_override,
        visibility,
    ) = await _read_upload_payload(request)
    ini = ini.strip()
    await _ensure_catalogued_variant_quota(app_state, username)
    if not ini:
        raise web.HTTPBadRequest(text="Missing INI content.")

    # Check uniqueness before asking FSF to load the config. load_variant_config()
    # is intentionally global and should not be called for a duplicate upload.
    name = extract_variant_name(ini)
    _ensure_catalogued_rule_changes(ini)
    await ensure_catalogued_variant_name_available(app_state, name)
    ensure_catalogued_display_name_available(display_name, variant_name=name)
    await check_catalogued_ini_without_mutating_server(ini, name)

    validated = validate_catalogued_ini(ini)
    name = validated.name

    now = datetime.now(UTC)
    doc = _build_doc(
        name=name,
        base_variant=validated.base_variant,
        display_name=display_name,
        description=description,
        piece_names=piece_names,
        username=username,
        ini=ini,
        start_fen=validated.start_fen,
        width=validated.width,
        height=validated.height,
        pieces=validated.pieces,
        king_roles=validated.king_roles,
        pocket_roles=validated.pocket_roles,
        capture_to_hand=validated.capture_to_hand,
        promotion_type=validated.promotion_type,
        promotion_roles=validated.promotion_roles,
        promotion_order=validated.promotion_order,
        show_promoted=validated.show_promoted,
        rules_gate=validated.rules_gate,
        rules_pass=validated.rules_pass,
        rules_arrowing=False,
        legal_moves_need_history=validated.legal_moves_need_history,
        n_fold_is_draw=validated.n_fold_is_draw,
        show_check_counters=validated.show_check_counters,
        created_at=now,
        piece_set_directional=bool(piece_set_directional),
        visibility=visibility,
        piece_family_override=piece_family_override,
        board_family_override=board_family_override,
    )

    try:
        await app_state.db[CATALOGUED_VARIANT_COLLECTION].insert_one(doc)
    except DuplicateKeyError as exc:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.") from exc

    register_catalogued_variant_doc(app_state, doc, load_config=False)
    await _refresh_catalogued_variant_profile_count(app_state, username)
    return json_response({"ok": True, "variant": _client_doc(doc, game_count=0)})


async def upload_catalogued_piece_set(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if not _is_active_catalogued_doc(doc):
        raise web.HTTPConflict(text="Archived variants cannot have custom piece sets.")

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Missing form data.")

    uploads = []
    if hasattr(data, "getall"):
        uploads.extend(data.getall("pieces", []))
        uploads.extend(data.getall("files", []))
        uploads.extend(data.getall("file", []))
    if not uploads:
        raise web.HTTPBadRequest(text="Upload one SVG file for every required piece.")

    paired_keys = _catalogued_piece_set_required_keys(doc)
    if not paired_keys:
        raise web.HTTPBadRequest(text="This variant has no renderable piece roles.")

    piece_set: dict[str, CataloguedVariantPieceSetSvg] = {}
    total_size = 0
    for upload in uploads:
        filename = str(getattr(upload, "filename", "") or "").strip()
        if not filename:
            raise web.HTTPBadRequest(text="Every uploaded file must have a filename.")
        canonical = _canonical_piece_set_filename(filename)
        if canonical is None:
            raise web.HTTPBadRequest(
                text="Piece SVG filenames must look like wP.svg, bP.svg, w+P.svg, or b+P.svg."
            )
        key = _catalogued_piece_set_storage_key(canonical)
        if key in piece_set:
            raise web.HTTPBadRequest(text=f"Duplicate piece SVG: {canonical}.")
        if key not in paired_keys:
            raise web.HTTPBadRequest(text=f"Unexpected piece SVG: {canonical}.")
        if not hasattr(upload, "file"):
            raise web.HTTPBadRequest(text=f"{canonical} is not a file upload.")

        raw = upload.file.read(MAX_CATALOGUED_PIECE_SVG_BYTES + 1)
        total_size += len(raw)
        if total_size > MAX_CATALOGUED_PIECE_SET_TOTAL_BYTES:
            raise web.HTTPBadRequest(
                text=(
                    "The piece set is too large. "
                    f"All SVGs together must be at most "
                    f"{MAX_CATALOGUED_PIECE_SET_TOTAL_BYTES // 1024} KiB."
                )
            )
        svg = _sanitize_catalogued_piece_svg(raw, canonical)
        piece_set[key] = {"svg": svg, "size": len(svg.encode("utf-8"))}

    uploaded = set(piece_set)
    if _catalogued_piece_set_mode_for_keys(doc, uploaded) is None:
        if _catalogued_piece_set_is_directional(doc):
            raise web.HTTPBadRequest(
                text=(
                    "Directional custom piece sets must be either one complete color "
                    "(all white or all black SVGs) or a complete white/black pair."
                )
            )
        missing = ", ".join(
            _catalogued_piece_set_public_filename(key) for key in sorted(paired_keys - uploaded)
        )
        extra = ", ".join(
            _catalogued_piece_set_public_filename(key) for key in sorted(uploaded - paired_keys)
        )
        details = []
        if missing:
            details.append(f"missing: {missing}")
        if extra:
            details.append(f"extra: {extra}")
        raise web.HTTPBadRequest(
            text="Custom piece sets must be complete and exact (" + "; ".join(details) + ")."
        )

    now = datetime.now(UTC)
    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"pieceSet": piece_set, "pieceSetUpdatedAt": now, "updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    count = await _game_count(app_state, name)
    return json_response({"ok": True, "variant": _client_doc(updated, game_count=count)})


async def delete_catalogued_piece_set(request: web.Request) -> web.Response:
    app_state, _username, name, _doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    now = datetime.now(UTC)
    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$unset": {"pieceSet": "", "pieceSetUpdatedAt": ""}, "$set": {"updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    count = await _game_count(app_state, name)
    return json_response({"ok": True, "variant": _client_doc(updated, game_count=count)})


async def upload_catalogued_board(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if not _is_active_catalogued_doc(doc):
        raise web.HTTPConflict(text="Archived variants cannot have custom boards.")

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Missing form data.")

    upload = None
    if hasattr(data, "getall"):
        uploads = []
        uploads.extend(data.getall("board", []))
        uploads.extend(data.getall("file", []))
        uploads.extend(data.getall("files", []))
        if len(uploads) > 1:
            raise web.HTTPBadRequest(text="Upload exactly one board SVG file.")
        upload = uploads[0] if uploads else None
    if upload is None:
        upload = data.get("board") or data.get("file")
    if not hasattr(upload, "file"):
        raise web.HTTPBadRequest(text="Upload exactly one board SVG file.")

    filename = str(getattr(upload, "filename", "") or "board.svg").strip() or "board.svg"
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    filename = unquote(filename).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not filename.casefold().endswith(".svg"):
        raise web.HTTPBadRequest(text="Board upload must be an SVG file.")

    raw = upload.file.read(MAX_CATALOGUED_BOARD_SVG_BYTES + 1)
    svg = _sanitize_catalogued_board_svg(raw, filename, int(doc["width"]), int(doc["height"]))
    board_svg: CataloguedVariantBoardSvg = {"svg": svg, "size": len(svg.encode("utf-8"))}

    now = datetime.now(UTC)
    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"boardSvg": board_svg, "boardSvgUpdatedAt": now, "updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    count = await _game_count(app_state, name)
    return json_response({"ok": True, "variant": _client_doc(updated, game_count=count)})


async def delete_catalogued_board(request: web.Request) -> web.Response:
    app_state, _username, name, _doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    now = datetime.now(UTC)
    result = await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$unset": {"boardSvg": "", "boardSvgUpdatedAt": ""}, "$set": {"updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    count = await _game_count(app_state, name)
    return json_response({"ok": True, "variant": _client_doc(updated, game_count=count)})


async def get_catalogued_board_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    board_svg = doc.get("boardSvg")
    if not isinstance(board_svg, Mapping) or not _has_board_svg(doc):
        raise web.HTTPNotFound(text="This variant has no custom board.")

    return web.Response(
        text=_catalogued_board_svg_css(str(doc["name"]), board_svg),
        content_type="text/css",
        headers={"Cache-Control": "private, max-age=300"},
    )


async def get_catalogued_piece_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    piece_set = doc.get("pieceSet")
    if not isinstance(piece_set, Mapping) or not _has_complete_piece_set(doc):
        raise web.HTTPNotFound(text="This variant has no complete custom piece set.")

    return web.Response(
        text=_catalogued_piece_set_css(
            str(doc["name"]),
            piece_set,
            directional=_catalogued_piece_set_is_directional(doc),
        ),
        content_type="text/css",
        headers={"Cache-Control": "private, max-age=300"},
    )


async def get_catalogued_disguised_piece_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    return web.Response(
        text=_catalogued_disguised_piece_css(str(doc["name"])),
        content_type="text/css",
        headers={"Cache-Control": "private, max-age=300"},
    )


def _positive_management_page(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _management_sort_spec(value: str) -> tuple[str, list[tuple[str, int]]]:
    if value == "name":
        return value, [("displayName", 1), ("name", 1)]
    if value == "newest":
        return value, [("createdAt", -1), ("name", 1)]
    if value == "played":
        return value, [("gameCount", -1), ("updatedAt", -1), ("name", 1)]
    if value == "favorited":
        return value, [("favoriteCount", -1), ("updatedAt", -1), ("name", 1)]
    return "updated", [("updatedAt", -1), ("name", 1)]


async def get_my_catalogued_variants(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _current_human_username(request)
    admin = _is_admin_username(username)
    params = request.rel_url.query

    q = params.get("q", "").strip()[:80] if admin else ""
    if admin and "author" in params:
        author = params.get("author", "").strip()[:40]
    elif admin and params.get("scope") == "fsf":
        author = CATALOGUED_FSF_BUILTIN_AUTHOR
    elif admin and (params.get("scope") == "all" or params.get("all") == "1"):
        author = ""
    else:
        author = username
    sort, sort_spec = _management_sort_spec(params.get("sort", "updated") if admin else "updated")

    query: dict[str, Any] = {}
    if q:
        regex = _search_regex(q)
        query["$or"] = [
            {"name": {"$regex": regex}},
            {"displayName": {"$regex": regex}},
            {"description": {"$regex": regex}},
            {"author": {"$regex": regex}},
        ]
    if author:
        query["author"] = author

    page = _positive_management_page(params.get("page"))
    total = 0
    pages = 1
    variants: list[CataloguedVariantClientDocument] = []
    if app_state.db is not None:
        collection = app_state.db[CATALOGUED_VARIANT_COLLECTION]
        total = await collection.count_documents(query)
        pages = max(
            1,
            (total + CATALOGUED_MANAGEMENT_PAGE_SIZE - 1) // CATALOGUED_MANAGEMENT_PAGE_SIZE,
        )
        page = min(page, pages)
        skip = (page - 1) * CATALOGUED_MANAGEMENT_PAGE_SIZE
        cursor = (
            collection.find(query).sort(sort_spec).skip(skip).limit(CATALOGUED_MANAGEMENT_PAGE_SIZE)
        )
        async for doc in cursor:
            count = await _game_count(app_state, str(doc["name"]))
            variants.append(_client_doc(doc, game_count=count))

    max_variants = None if admin else MAX_CATALOGUED_VARIANTS_PER_USER
    variant_slots_used = None
    if not admin:
        variant_slots_used = await _catalogued_variant_slot_count_for_user(app_state, username)
    return json_response(
        {
            "variants": variants,
            "maxVariants": max_variants,
            "variantSlotsUsed": variant_slots_used,
            "q": q,
            "author": author,
            "sort": sort,
            "total": total,
            "page": page,
            "pages": pages,
            "prevPage": page - 1 if page > 1 else None,
            "nextPage": page + 1 if page < pages else None,
        }
    )


async def _load_owned_doc(request: web.Request) -> tuple[Any, str, str, Mapping[str, Any]]:
    app_state = get_app_state(request.app)
    username = await _current_human_username(request)
    name = request.match_info["name"]

    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")
    if not _can_modify(username, doc):
        raise web.HTTPForbidden(text="You can only manage your own catalogued variants.")

    return app_state, username, name, doc


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


def _catalogued_same_name_update(
    doc: Mapping[str, Any], existing: Mapping[str, Any]
) -> dict[str, Any]:
    """Build a non-destructive update for user-editable and derived fields."""
    set_fields = {
        key: value
        for key, value in doc.items()
        if key not in CATALOGUED_CONCURRENTLY_UPDATED_FIELDS
    }
    update: dict[str, Any] = {"$set": set_fields}
    unset_fields = {
        field: ""
        for field in CATALOGUED_METADATA_OPTIONAL_FIELDS
        if field in existing and field not in doc
    }
    if unset_fields:
        update["$unset"] = unset_fields
    return update


async def _update_catalogued_variant_document(
    collection: Any,
    *,
    name: str,
    existing: Mapping[str, Any],
    doc: CataloguedVariantDocument,
) -> Mapping[str, Any]:
    result = await collection.update_one(
        {"_id": name},
        _catalogued_same_name_update(doc, existing),
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")
    updated = await collection.find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    return cast(Mapping[str, Any], updated)


async def _reserve_catalogued_variant_name(
    collection: Any, name: str, existing: Mapping[str, Any]
) -> None:
    """Permanently reserve an internal Fairy-Stockfish name before removing its document."""

    reservation: dict[str, Any] = {
        "_id": name,
        "reservedAt": datetime.now(UTC),
    }
    author = existing.get("author")
    if isinstance(author, str) and author:
        reservation["author"] = author
    try:
        await collection.insert_one(reservation)
    except DuplicateKeyError:
        # Retrying deletion or rename is safe; a reservation is permanent.
        pass


def _catalogued_rename_source_query(old_name: str, existing: Mapping[str, Any]) -> dict[str, Any]:
    """Match the source revision so a concurrent upload cannot be discarded."""
    query: dict[str, Any] = {"_id": old_name}
    for field in ("updatedAt", "gameCount", "favoriteCount"):
        if field in existing:
            query[field] = existing[field]
        else:
            query[field] = {"$exists": False}
    return query


def _catalogued_variant_user_collection(app_state: Any) -> Any | None:
    """Return the user collection when the app state exposes one."""

    db = getattr(app_state, "db", None)
    if db is None:
        return None
    user_collection = getattr(db, "user", None)
    if user_collection is None and isinstance(db, Mapping):
        user_collection = db.get("user")
    return user_collection


def _cached_catalogued_variant_users(app_state: Any) -> Iterable[Any]:
    """Return cached users when the app state has an initialized user cache."""

    users = getattr(app_state, "users", None)
    values = getattr(users, "values", None)
    return values() if callable(values) else ()


async def _rename_catalogued_variant_favorites(
    app_state: Any, old_name: str, new_name: str
) -> None:
    """Move stored user favorites to a renamed catalogued variant."""

    if old_name == new_name:
        return

    user_collection = _catalogued_variant_user_collection(app_state)
    if user_collection is not None:
        await user_collection.update_many(
            {"cvf": old_name},
            [
                {
                    "$set": {
                        "cvf": {
                            "$setUnion": [
                                {
                                    "$map": {
                                        "input": {"$ifNull": ["$cvf", []]},
                                        "as": "favorite",
                                        "in": {
                                            "$cond": [
                                                {"$eq": ["$$favorite", old_name]},
                                                new_name,
                                                "$$favorite",
                                            ]
                                        },
                                    }
                                },
                                [],
                            ]
                        }
                    }
                }
            ],
        )

    for cached_user in _cached_catalogued_variant_users(app_state):
        favorites = getattr(cached_user, "catalogued_variant_favorites", None)
        if isinstance(favorites, set) and old_name in favorites:
            favorites.discard(old_name)
            favorites.add(new_name)


async def _remove_catalogued_variant_favorites(app_state: Any, name: str) -> None:
    """Remove a deleted catalogued variant from stored and cached favorites."""

    user_collection = _catalogued_variant_user_collection(app_state)
    if user_collection is not None:
        await user_collection.update_many({"cvf": name}, {"$pull": {"cvf": name}})

    for cached_user in _cached_catalogued_variant_users(app_state):
        favorites = getattr(cached_user, "catalogued_variant_favorites", None)
        if isinstance(favorites, set):
            favorites.discard(name)


async def _rename_catalogued_variant_document(
    collection: Any,
    name_collection: Any,
    *,
    old_name: str,
    new_name: str,
    existing: Mapping[str, Any],
    doc: CataloguedVariantDocument,
) -> None:
    await _reserve_catalogued_variant_name(name_collection, old_name, existing)
    try:
        await collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.") from exc

    deleted = await collection.delete_one(_catalogued_rename_source_query(old_name, existing))
    if deleted.deleted_count == 1:
        return

    rollback = await collection.delete_one({"_id": new_name})
    if rollback.deleted_count != 1:
        log.error(
            "Failed to roll back stale catalogued variant rename from %s to %s",
            old_name,
            new_name,
        )
    raise web.HTTPConflict(
        text="This variant changed while it was being saved. Please review it and try again."
    )


async def update_catalogued_variant(request: web.Request) -> web.Response:
    app_state, username, old_name, existing = await _load_owned_doc(request)

    (
        ini,
        display_name,
        description,
        piece_names,
        piece_set_directional,
        piece_family_override,
        board_family_override,
        visibility,
    ) = await _read_upload_payload(request)
    ini = ini.strip()
    if piece_set_directional is None:
        piece_set_directional = bool(existing.get("pieceSetDirectional", False))
    if _is_fsf_builtin_catalogued_doc(existing):
        now = datetime.now(UTC)
        cleaned_description = _clean_description(description)
        update: dict[str, Any] = {
            "$set": {
                "displayName": _clean_display_name(display_name, old_name),
                "visibility": visibility,
                "pieceSetDirectional": piece_set_directional,
                "updatedAt": now,
            }
        }
        unset_fields: dict[str, str] = {}
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS.get(_fsf_builtin_variant_name(existing), {})
        references = _clean_catalogued_references(existing.get("references"))
        if _fsf_builtin_description_is_auto(cleaned_description, metadata, references):
            unset_fields["description"] = ""
        else:
            update["$set"]["description"] = cleaned_description
        if piece_names:
            update["$set"]["pieceNames"] = piece_names
        else:
            unset_fields["pieceNames"] = ""
        if piece_family_override:
            update["$set"]["pieceFamilyOverride"] = piece_family_override
        else:
            unset_fields["pieceFamilyOverride"] = ""
        if board_family_override:
            _ensure_board_family_dimensions(
                board_family_override,
                int(existing.get("width") or 8),
                int(existing.get("height") or 8),
            )
            update["$set"]["boardFamilyOverride"] = board_family_override
        else:
            unset_fields["boardFamilyOverride"] = ""
        if unset_fields:
            update["$unset"] = unset_fields
        await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one({"_id": old_name}, update)
        updated = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": old_name})
        if updated is None:
            raise web.HTTPNotFound(text="Catalogued variant not found after update.")
        register_catalogued_variant_doc(app_state, updated, load_config=False)
        await _refresh_catalogued_variant_profile_count(
            app_state, str(updated.get("author") or existing.get("author") or "")
        )
        count = await _game_count(app_state, old_name)
        return json_response(
            {"ok": True, "oldName": old_name, "variant": _client_doc(updated, game_count=count)}
        )

    if not ini:
        raise web.HTTPBadRequest(text="Missing INI content.")

    new_name = extract_variant_name(ini)
    ensure_catalogued_display_name_available(
        display_name,
        variant_name=new_name,
        current_display_name=str(existing.get("displayName") or ""),
        current_variant_name=old_name,
    )
    existing_ini = str(existing.get("ini") or "")
    fsf_rules_changed = _strip_pychess_pieces_metadata(ini) != _strip_pychess_pieces_metadata(
        existing_ini
    )
    if fsf_rules_changed or new_name != old_name:
        _ensure_catalogued_rule_changes(ini)
    if (fsf_rules_changed or new_name != old_name) and await _has_games(app_state, old_name):
        raise web.HTTPConflict(
            text="This variant already has games. Its rules are locked; clone it to make a changed version."
        )

    if fsf_rules_changed and new_name == old_name:
        raise web.HTTPConflict(
            text=(
                "Changing rules requires a new variant section name because Fairy-Stockfish "
                "cannot replace an already loaded runtime variant. Rename the [section] or clone this variant."
            )
        )

    if new_name != old_name:
        await ensure_catalogued_variant_name_available(app_state, new_name, current_name=old_name)

    if fsf_rules_changed or new_name != old_name:
        await check_catalogued_ini_without_mutating_server(ini, new_name)
        validated = validate_catalogued_ini(ini)
        new_name = validated.name
        base_variant = validated.base_variant
        start_fen = validated.start_fen
        width = validated.width
        height = validated.height
        pieces = validated.pieces
        king_roles = validated.king_roles
        pocket_roles = validated.pocket_roles
        capture_to_hand = validated.capture_to_hand
        promotion_type = validated.promotion_type
        promotion_roles = validated.promotion_roles
        promotion_order = validated.promotion_order
        show_promoted = validated.show_promoted
        rules_gate = validated.rules_gate
        rules_pass = validated.rules_pass
        legal_moves_need_history = validated.legal_moves_need_history
        n_fold_is_draw = validated.n_fold_is_draw
        show_check_counters = validated.show_check_counters
    else:
        base_variant = str(existing.get("baseVariant") or extract_variant_base_name(ini))
        start_fen = str(existing["startFen"])
        width = int(existing["width"])
        height = int(existing["height"])
        pieces = _catalogued_piece_roles_from_ini(ini, start_fen)
        king_roles = catalogued_king_roles(ini, pieces)
        capture_to_hand = _ini_bool(ini, "capturesToHand", default=False)
        pocket_roles = catalogued_pocket_roles(
            ini, start_fen, pieces, king_roles, capture_to_hand=capture_to_hand
        )
        promotion_type = catalogued_promotion_type(ini)
        promotion_roles = catalogued_promotion_roles(ini, pieces)
        promotion_order = catalogued_promotion_order(ini, promotion_type)
        show_promoted = catalogued_show_promoted(ini, start_fen)
        rules_gate = catalogued_rules_gate(ini)
        rules_pass = catalogued_rules_pass(ini)
        legal_moves_need_history = catalogued_legal_moves_need_history(ini)
        n_fold_is_draw = catalogued_n_fold_is_draw(ini)
        show_check_counters = catalogued_show_check_counters(ini)

    doc = _build_doc(
        name=new_name,
        base_variant=base_variant,
        display_name=display_name,
        description=description,
        piece_names=piece_names,
        username=str(existing.get("author") or username),
        ini=ini,
        start_fen=start_fen,
        width=width,
        height=height,
        pieces=pieces,
        king_roles=king_roles,
        pocket_roles=pocket_roles,
        capture_to_hand=capture_to_hand,
        promotion_type=promotion_type,
        promotion_roles=promotion_roles,
        promotion_order=promotion_order,
        show_promoted=show_promoted,
        rules_gate=rules_gate,
        rules_pass=rules_pass,
        rules_arrowing=False,
        legal_moves_need_history=legal_moves_need_history,
        n_fold_is_draw=n_fold_is_draw,
        show_check_counters=show_check_counters,
        created_at=existing.get("createdAt", datetime.now(UTC)),
        piece_set_directional=piece_set_directional,
        visibility=visibility,
        piece_family_override=piece_family_override,
        board_family_override=board_family_override,
        archived=bool(existing.get("archived", False)),
        game_count=int(existing.get("gameCount") or 0),
        favorite_count=int(existing.get("favoriteCount") or 0),
    )

    _copy_catalogued_uploaded_assets(doc, existing)

    if new_name != old_name:
        await _rename_catalogued_variant_document(
            app_state.db[CATALOGUED_VARIANT_COLLECTION],
            app_state.db[CATALOGUED_VARIANT_NAME_COLLECTION],
            old_name=old_name,
            new_name=new_name,
            existing=existing,
            doc=doc,
        )
        await _rename_catalogued_variant_favorites(app_state, old_name, new_name)
        await _remove_catalogued_variant_seeks(app_state, old_name)
        unregister_catalogued_server_variant(old_name)
        app_state.catalogued_variants.pop(old_name, None)
        updated = doc
    else:
        updated = await _update_catalogued_variant_document(
            app_state.db[CATALOGUED_VARIANT_COLLECTION],
            name=new_name,
            existing=existing,
            doc=doc,
        )

    register_catalogued_variant_doc(app_state, updated, load_config=False)
    if new_name != old_name:
        await _migrate_catalogued_variant_tournaments(app_state, old_name, new_name, updated)
    await _refresh_catalogued_variant_profile_count(
        app_state, str(updated.get("author") or existing.get("author") or "")
    )
    count = await _game_count(app_state, new_name)
    return json_response(
        {"ok": True, "oldName": old_name, "variant": _client_doc(updated, game_count=count)}
    )


async def delete_catalogued_variant(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if _is_fsf_builtin_catalogued_doc(doc):
        raise web.HTTPConflict(text="Fairy-Stockfish built-in catalogue entries cannot be deleted.")
    if _has_active_catalogued_games(app_state, name):
        raise web.HTTPConflict(
            text=(
                "This variant still has an active game. "
                "Finish or abort it before deleting the variant."
            )
        )
    if await _has_games(app_state, name):
        raise web.HTTPConflict(
            text="This variant already has saved public games. Archive it instead of deleting it."
        )

    await _remove_catalogued_variant_tournaments(app_state, name)
    await _reserve_catalogued_variant_name(
        app_state.db[CATALOGUED_VARIANT_NAME_COLLECTION], name, doc
    )
    await app_state.db[CATALOGUED_VARIANT_COLLECTION].delete_one({"_id": name})
    await _remove_catalogued_variant_favorites(app_state, name)
    await _remove_catalogued_variant_seeks(app_state, name)
    app_state.catalogued_variants.pop(name, None)
    unregister_catalogued_server_variant(name)
    await _refresh_catalogued_variant_profile_count(app_state, str(doc.get("author") or ""))
    return json_response({"ok": True, "deleted": name})


async def archive_catalogued_variant(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    await _snapshot_catalogued_variant_tournaments(app_state, name, doc)
    now = datetime.now(UTC)
    await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"archived": True, "enabled": False, "updatedAt": now}},
    )
    await _remove_catalogued_variant_seeks(app_state, name)
    app_state.catalogued_variants.pop(name, None)
    unregister_catalogued_server_variant(name)
    await _refresh_catalogued_variant_profile_count(app_state, str(doc.get("author") or ""))
    return json_response({"ok": True, "archived": name})


async def restore_catalogued_variant(request: web.Request) -> web.Response:
    app_state, username, name, doc = await _load_owned_doc(request)
    if bool(doc.get("archived", False)):
        await _ensure_catalogued_variant_quota(app_state, username)
    now = datetime.now(UTC)
    restored = dict(doc)
    restored["archived"] = False
    restored["enabled"] = True
    restored["updatedAt"] = now

    await app_state.db[CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"archived": False, "enabled": True, "updatedAt": now}},
    )
    register_catalogued_variant_doc(app_state, restored, load_config=True)
    await _refresh_catalogued_variant_profile_count(app_state, str(doc.get("author") or ""))
    count = await _game_count(app_state, name)
    return json_response({"ok": True, "variant": _client_doc(restored, game_count=count)})


async def clone_catalogued_variant(request: web.Request) -> web.Response:
    app_state, username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if _is_fsf_builtin_catalogued_doc(doc):
        raise web.HTTPConflict(text="Fairy-Stockfish built-in catalogue entries cannot be cloned.")

    _ensure_catalogued_rule_changes(str(doc["ini"]))
    await _ensure_catalogued_variant_quota(app_state, username)

    for n in range(2, 100):
        suffix = f"_v{n}"
        candidate = f"{name[: 32 - len(suffix)]}{suffix}"
        try:
            await ensure_catalogued_variant_name_available(app_state, candidate)
        except web.HTTPConflict:
            continue
        new_name = candidate
        break
    else:
        raise web.HTTPConflict(text="Could not find a free variant name for the clone.")

    ini = replace_variant_section_name(str(doc["ini"]), new_name)
    await check_catalogued_ini_without_mutating_server(ini, new_name)
    validated = validate_catalogued_ini(ini)
    new_name = validated.name

    now = datetime.now(UTC)
    display_name = f"{doc.get('displayName') or name} v{new_name.rsplit('_v', 1)[-1]}"
    cloned = _build_doc(
        name=new_name,
        base_variant=validated.base_variant,
        display_name=display_name,
        description=str(doc.get("description") or ""),
        piece_names=parse_catalogued_piece_names(doc.get("pieceNames")),
        username=username,
        ini=ini,
        start_fen=validated.start_fen,
        width=validated.width,
        height=validated.height,
        pieces=validated.pieces,
        king_roles=validated.king_roles,
        pocket_roles=validated.pocket_roles,
        capture_to_hand=validated.capture_to_hand,
        promotion_type=validated.promotion_type,
        promotion_roles=validated.promotion_roles,
        promotion_order=validated.promotion_order,
        show_promoted=validated.show_promoted,
        rules_gate=validated.rules_gate,
        rules_pass=validated.rules_pass,
        rules_arrowing=False,
        legal_moves_need_history=validated.legal_moves_need_history,
        n_fold_is_draw=validated.n_fold_is_draw,
        show_check_counters=validated.show_check_counters,
        created_at=now,
        piece_set_directional=bool(doc.get("pieceSetDirectional", False)),
        piece_family_override=_catalogued_piece_family_override(doc),
        board_family_override=_catalogued_board_family_override(doc),
    )

    try:
        await app_state.db[CATALOGUED_VARIANT_COLLECTION].insert_one(cloned)
    except DuplicateKeyError as exc:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.") from exc

    register_catalogued_variant_doc(app_state, cloned, load_config=False)
    await _refresh_catalogued_variant_profile_count(app_state, username)
    return json_response({"ok": True, "variant": _client_doc(cloned, game_count=0)})
