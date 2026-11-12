"""Curated Fairy-Stockfish built-in catalogue metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from fairy.fairy_board import sf
from variants import ServerVariants

from . import models

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
# ``boardFamilyOverride``; Betza movement exceptions belong in catalogued.betza.
FSF_CATALOGUED_BUILTIN_VARIANTS: Mapping[str, Mapping[str, Any]] = {
    "5check": {
        "displayName": "Five-Check Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "3check",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "breakthrough": {
        "displayName": "Breakthrough",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Breakthrough_(board_game)"
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard8x8",
        "pieceFamilyOverride": "standard",
        # Documentation only, transcribed from breakthrough_variant() in
        # Fairy-Stockfish's src/variant.cpp. The goal rank ends play, without promotion.
        "rulesIni": """
[breakthrough]
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
breakthrough = p
doubleStep = false
castling = false
stalemateValue = loss
flagPiece = p
flagRegionWhite = *8
flagRegionBlack = *1
""",
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
    "checkshogi": {
        "displayName": "Check-Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "shogi",
        "clientVariant": "shogi",
        "boardFamilyOverride": "shogi9x9",
        "pieceFamilyOverride": "shogi",
        "captureToHand": True,
        "promotionType": "shogi",
        "promotionRoles": ("p", "l", "n", "s", "b", "r"),
        "promotionOrder": ("+",),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        "showCheckCounters": True,
        # Documentation only, from checkshogi_variant() in src/variant.cpp.
        # The inherited Shogi FEN omits the counter: Position::set defaults
        # checkCounting positions without one to 1+1 (the next check wins).
        "rulesIni": """
[checkshogi:shogi]
checkCounting = true
""",
    },
    "chessgi": {
        "displayName": "Chessgi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Crazyhouse#Variations",
        ),
        "baseVariant": "loop",
        "clientVariant": "crazyhouse",
        "captureToHand": True,
        "dropLoop": True,
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
        "showPromoted": True,
        "nFoldIsDraw": True,
        # Documentation only; runtime paths use the canonical built-in key.
        "rulesIni": """
[chessgi:loop]
dropLoop = true
firstRankPawnDrops = true
""",
    },
    "clobber": {
        "displayName": "Clobber",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Clobber"),
        "baseVariant": "",
        "clientVariant": "chess",
        "pieceFamilyOverride": "ataxx",
        "pieceNames": {"p": "Disc"},
        # Documentation only, transcribed from clobber_variant() in
        # Fairy-Stockfish's src/variant.cpp. A player with no legal capture loses.
        "rulesIni": """
[clobber]
maxRank = 6
maxFile = 5
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
clobber = p
doubleStep = false
castling = false
stalemateValue = loss
immobilityIllegal = false
""",
    },
    "clobber10": {
        "displayName": "Clobber 10x10",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Clobber"),
        "baseVariant": "clobber",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard10x10",
        "pieceFamilyOverride": "ataxx",
        "pieceNames": {"p": "Disc"},
        # Documentation only; use the native 10x10 starting position at runtime.
        "rulesIni": """
[clobber10:clobber]
maxRank = 10
maxFile = 10
""",
    },
    "codrus": {
        "displayName": "Codrus",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("http://www.binnewirtz.com/Schlagschach1.htm"),
        "baseVariant": "giveaway",
        "clientVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
    "euroshogi": {
        "displayName": "EuroShogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/EuroShogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "boardFamilyOverride": "standard8x8",
        # Standard chess sets lack generals and the four promoted forms.
        "pieceFamilyOverride": "shogi",
        "pieceNames": {"g": "General"},
        "captureToHand": True,
        "promotionType": "shogi",
        "promotionRoles": ("p", "n", "b", "r"),
        "promotionOrder": ("+",),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only, transcribed from minishogi_variant_base() and
        # euroshogi_variant() in Fairy-Stockfish's src/variant.cpp. The built-in
        # uses fourfold repetition, losing stalemate and no pawn-drop mate.
        "rulesIni": """
[euroshogi]
variantTemplate = shogi
maxRank = 8
maxFile = 8
king = k
shogiPawn = p
silver = s
gold = g
bishop = b
dragonHorse = h
rook = r
bers = d
customPiece1 = n:fNsW
promotionRegionWhite = *6 *7 *8
promotionRegionBlack = *1 *2 *3
promotedPieceType = p:g s:g b:h r:d n:g
mandatoryPiecePromotion = true
pieceDrops = true
capturesToHand = true
doubleStep = false
castling = false
dropNoDoubled = p
immobilityIllegal = true
shogiPawnDropMateIllegal = true
stalemateValue = loss
nFoldRule = 4
nMoveRule = 0
perpetualCheckIllegal = true
""",
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "flipello": {
        "displayName": "Flipello",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Reversi#Othello"),
        "baseVariant": "flipersi",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard8x8",
        "pieceFamilyOverride": "ataxx",
        "pieceNames": {"p": "Disc"},
        "pocketRoles": ("p",),
        "captureToHand": False,
        "rulesPass": True,
        "legalMovesNeedHistory": True,
        # Documentation only; the native built-in supplies the initial reserves.
        "rulesIni": """
[flipello:flipersi]
passOnStalemate = true
""",
    },
    "flipello10": {
        "displayName": "Flipello 10x10",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Reversi"),
        "baseVariant": "flipello",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard10x10",
        "pieceFamilyOverride": "ataxx",
        "pieceNames": {"p": "Disc"},
        "pocketRoles": ("p",),
        "captureToHand": False,
        "rulesPass": True,
        "legalMovesNeedHistory": True,
        # Documentation only; the native built-in supplies the initial reserves.
        "rulesIni": """
[flipello10:flipello]
maxRank = 10
maxFile = 10
enclosingDropStart = e5 f5 e6 f6
""",
    },
    "flipersi": {
        "displayName": "Flipersi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Reversi"),
        "baseVariant": "",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard8x8",
        "pieceFamilyOverride": "ataxx",
        "pieceNames": {"p": "Disc"},
        "pocketRoles": ("p",),
        "captureToHand": False,
        "rulesPass": False,
        "legalMovesNeedHistory": True,
        # Documentation only; the native built-in supplies the initial reserves.
        "rulesIni": """
[flipersi]
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
immobile = p
pieceDrops = true
doubleStep = false
castling = false
immobilityIllegal = false
stalemateValue = loss
stalematePieceCount = true
enclosingDrop = reversi
enclosingDropStart = d4 e4 d5 e5
flipEnclosedPieces = reversi
materialCounting = unweighted
adjudicateFullBoard = true
passOnStalemate = false
""",
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
    "isolation": {
        "displayName": "Isolation",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/1875/isolation",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "pieceFamilyOverride": "snailtrail",
        "pieceNames": {"p": "Token"},
        "rulesArrowing": True,
        # Documentation only, transcribed from isolation_variant() in
        # Fairy-Stockfish's src/variant.cpp. Starting squares cannot be walled.
        "rulesIni": """
[isolation]
maxRank = 8
maxFile = 6
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
customPiece1 = p:mK
stalemateValue = loss
wallingRule = static
wallingRegion = a1 b1 d1 e1 f1 *2 *3 *4 *5 *6 *7 a8 b8 c8 e8 f8
""",
    },
    "isolation7x7": {
        "displayName": "Isolation 7x7",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/1875/isolation",
        ),
        "baseVariant": "isolation",
        "clientVariant": "chess",
        "boardFamilyOverride": "ataxx7x7",
        "pieceFamilyOverride": "snailtrail",
        "pieceNames": {"p": "Token"},
        "rulesArrowing": True,
        # Documentation only, transcribed from isolation7x7_variant().
        "rulesIni": """
[isolation7x7:isolation]
maxRank = 7
maxFile = 7
# Inherited token and wall rules are repeated for the rules page and premoves.
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
customPiece1 = p:mK
stalemateValue = loss
wallingRule = static
wallingRegion = a1 b1 c1 e1 f1 g1 *2 *3 *4 *5 *6 a7 b7 c7 e7 f7 g7
""",
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
    "janggicasual": {
        "displayName": "Janggi Casual",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "clientVariant": "janggi",
        "boardFamilyOverride": "janggi9x10",
        "pieceFamilyOverride": "janggi",
        "rulesPass": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only: retain the native engine key and its history rules.
        "rulesIni": """
[janggicasual:janggi]
bikjangRule = false
materialCounting = none
pass = true
perpetualCheckIllegal = true
""",
    },
    "janggimodern": {
        "displayName": "Janggi Modern",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "clientVariant": "janggi",
        "boardFamilyOverride": "janggi9x10",
        "pieceFamilyOverride": "janggi",
        "rulesPass": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only: retain the native engine key and its history rules.
        "rulesIni": """
[janggimodern:janggi]
bikjangRule = false
materialCounting = janggi
pass = true
perpetualCheckIllegal = true
moveRepetitionIllegal = true
nFoldRule = 4
nMoveRule = 100
""",
    },
    "janggitraditional": {
        "displayName": "Janggi Traditional",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "janggi",
        "clientVariant": "janggi",
        "boardFamilyOverride": "janggi9x10",
        "pieceFamilyOverride": "janggi",
        "rulesPass": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only: retain the native engine key and its history rules.
        "rulesIni": """
[janggitraditional:janggi]
bikjangRule = true
materialCounting = none
pass = true
perpetualCheckIllegal = true
""",
    },
    "jesonmor": {
        "displayName": "Jeson Mor",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Jeson_Mor"),
        "baseVariant": "",
        "clientVariant": "chess",
        "boardFamilyOverride": "standard9x9",
        "pieceFamilyOverride": "standard",
        "nFoldIsDraw": True,
        # Documentation only, transcribed from jesonmor_variant() and the
        # inherited defaults in Fairy-Stockfish's src/variant.cpp / variant.h.
        "rulesIni": """
[jesonmor]
maxRank = 9
maxFile = 9
pawn = -
knight = n
bishop = -
rook = -
queen = -
king = -
doubleStep = false
castling = false
stalemateValue = loss
flagPiece = n
flagRegionWhite = e5
flagRegionBlack = e5
# A knight on e5 wins after surviving the opponent's reply.
flagMove = true
nFoldRule = 3
nMoveRule = 50
""",
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
    "karouk": {
        "displayName": "Kar Ouk",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Makruk#Ka_Ouk"),
        "baseVariant": "cambodian",
        "clientVariant": "cambodian",
        "boardFamilyOverride": "makruk8x8",
        "pieceFamilyOverride": "makruk",
        "promotionRoles": ("p",),
        "promotionOrder": ("m",),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        "showCheckCounters": True,
        # Documentation only, from karouk_variant() in src/variant.cpp.
        # The inherited Cambodian FEN omits the check counter, implying 1+1.
        "rulesIni": """
[karouk:cambodian]
checkCounting = true
""",
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
    "loop": {
        "displayName": "Loop Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Crazyhouse#Variations",
        ),
        "baseVariant": "crazyhouse",
        "captureToHand": True,
        "dropLoop": True,
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
        "showPromoted": True,
        "nFoldIsDraw": True,
        # Documentation only; runtime paths use the canonical built-in key.
        "rulesIni": """
[loop:crazyhouse]
dropLoop = true
""",
    },
    "losers": {
        "displayName": "Losers Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessclub.com/help/Wild17"),
        "baseVariant": "",
        "clientVariant": "antichess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "micro": {
        "displayName": "Micro Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Micro_shogi"),
        "baseVariant": "kyotoshogi",
        "clientVariant": "kyotoshogi",
        "boardFamilyOverride": "shogi4x5",
        "pieceFamilyOverride": "microshogi",
        "captureToHand": True,
        "pocketRoles": ("p", "l", "b", "r"),
        "promotionType": "shogi",
        "promotionRoles": ("p", "l", "b", "r"),
        "promotionOrder": ("+", ""),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only, transcribed from microshogi_variant() and its
        # Kyoto/minishogi helpers in Fairy-Stockfish's src/variant.cpp.
        "rulesIni": """
[micro:kyotoshogi]
maxRank = 5
maxFile = 4
promotionRegionWhite = *
promotionRegionBlack = *
promotedPieceType = p:n l:s b:g r:g
mandatoryPiecePromotion = true
pieceDemotion = true
piecePromotionOnCapture = true
pieceDrops = true
capturesToHand = true
dropPromoted = true
doubleStep = false
castling = false
dropNoDoubled = -
immobilityIllegal = false
shogiPawnDropMateIllegal = false
stalemateValue = loss
nFoldRule = 4
nMoveRule = 0
perpetualCheckIllegal = true
""",
    },
    "misere": {
        "displayName": "Misère Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("http://www.kotesovec.cz/gustav/gustav_alybadix.htm"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nightrider": {
        "displayName": "Nightrider Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Nightrider_(chess)"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nocastle": {
        "displayName": "No-Castle Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "baseVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "nocheckatomic": {
        "displayName": "No-Check Atomic",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessclub.com/help/atomic"),
        "baseVariant": "",
        "clientVariant": "atomic",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "okisakishogi": {
        "displayName": "Okisaki Shogi",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Okisaki_shogi"),
        "baseVariant": "",
        "clientVariant": "shogi",
        "boardFamilyOverride": "shogi10x10",
        "pieceFamilyOverride": "okisakishogi",
        "pieceNames": {"n": "Jumping horse", "l": "Two-way lance", "q": "Queen"},
        "captureToHand": True,
        "promotionType": "shogi",
        "promotionRoles": ("p", "l", "n", "s", "b", "r"),
        "promotionOrder": ("+", ""),
        "showPromoted": True,
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only, transcribed from minishogi_variant_base() and
        # okisakishogi_variant() in Fairy-Stockfish's src/variant.cpp.
        "rulesIni": """
[okisakishogi]
variantTemplate = shogi
maxRank = 10
maxFile = 10
king = k
shogiPawn = p
silver = s
gold = g
bishop = b
dragonHorse = h
rook = r
bers = d
customPiece1 = l:vR
knight = n
queen = q
promotionRegionWhite = *8 *9 *10
promotionRegionBlack = *1 *2 *3
promotedPieceType = p:g l:g n:g s:g b:h r:d
pieceDrops = true
capturesToHand = true
doubleStep = false
castling = false
dropNoDoubled = p
immobilityIllegal = true
shogiPawnDropMateIllegal = true
stalemateValue = loss
nFoldRule = 4
nMoveRule = 0
perpetualCheckIllegal = true
""",
    },
    "opulent": {
        "displayName": "Opulent Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://www.chessvariants.com/rules/opulent-chess"),
        "baseVariant": "grand",
        "pieceFamilyOverride": "opulent",
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "pawnsideways": {
        "displayName": "Pawnsideways Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://arxiv.org/abs/2009.04374"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
    "snailtrail": {
        "displayName": "Snail Trail",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://boardgamegeek.com/boardgame/37135/snailtrail",
        ),
        "baseVariant": "",
        "clientVariant": "chess",
        "boardFamilyOverride": "ataxx7x7",
        "pieceFamilyOverride": "snailtrail",
        "pieceNames": {"p": "Snail"},
        "rulesArrowing": True,
        # Documentation only, transcribed from snailtrail_variant() in
        # Fairy-Stockfish's src/variant.cpp. Tokens are non-royal and cannot capture.
        "rulesIni": """
[snailtrail]
maxRank = 7
maxFile = 7
pawn = -
knight = -
bishop = -
rook = -
queen = -
king = -
customPiece1 = p:mK
stalemateValue = loss
wallingRule = past
""",
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
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
    },
    "torpedo": {
        "displayName": "Torpedo Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://arxiv.org/abs/2009.04374"),
        "baseVariant": "",
        "clientVariant": "chess",
        "promotionRoles": ("p",),
        "promotionOrder": models.CATALOGUED_CHESS_PROMOTION_ORDER,
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
    "wolf": {
        "displayName": "Wolf Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references("https://en.wikipedia.org/wiki/Wolf_chess"),
        "baseVariant": "",
        "clientVariant": "chess",
        "pieceFamilyOverride": "wolf",
        "pieces": ("+p",),
        "pieceNames": {
            "w": "Wolf",
            "f": "Fox",
            "s": "Sergeant",
            "n": "Nightrider",
            "e": "Elephant",
        },
        "promotionRoles": ("p", "s"),
        "promotionOrder": ("q", "w", "f", "r", "b", "+"),
        "legalMovesNeedHistory": True,
        "nFoldIsDraw": True,
        # Documentation only, from wolf_variant() in src/variant.cpp.
        # '+' promotes a pawn to the elephant; sergeants only use letter choices.
        "rulesIni": """
[wolf]
maxRank = 10
knight = -
chancellor = w
archbishop = f
customPiece1 = s:fKifmnD
customPiece2 = n:NN
customPiece3 = e:NNQ
mainPromotionPawnType = p
promotionPawnTypes = p s
promotionPieceTypes = q w f r b
promotedPieceType = p:e
promotionRegionWhite = *10
promotionRegionBlack = *1
doubleStepRegionWhite = *2 b3 c3 f3 g3
doubleStepRegionBlack = *9 b8 c8 f8 g8
enPassantTypes = p
nMoveRuleTypes = p s
castling = false
""",
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
    "caparandom": {
        "displayName": "Capablanca Random Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Capablanca_random_chess",
        ),
        "baseVariant": "capablanca",
        "reviewNotes": "Shuffle variant; pychess already has first-class Caparandom support.",
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
    "koedem": {
        "displayName": "Koedem",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "http://schachclub-oetigheim.de/wp-content/uploads/2016/04/Koedem-rules.pdf",
        ),
        "baseVariant": "bughouse",
        "reviewNotes": "Bughouse-family/two-board variant; not suitable for catalogued flow yet.",
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
    "sortofalmost": {
        "displayName": "Sort-of-Almost Chess",
        "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        "references": _fsf_builtin_references(
            "https://en.wikipedia.org/wiki/Almost_chess#Sort_of_almost_chess",
        ),
        "baseVariant": "chess",
        "reviewNotes": "Asymmetric Almost Chess variant; verify pieces and castling assumptions.",
    },
}


# Built-ins that were seeded in production before a later audit found that the
# generic catalogued client cannot represent their rules safely. Keep this
# explicit instead of silently leaving an old MongoDB document enabled after
# moving the metadata back to the candidate list.
FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS = frozenset({"chigorin"})


BUILTIN_VARIANT_NAMES = frozenset(variant.server_name for variant in ServerVariants)


BUILTIN_FSF_VARIANT_NAMES = frozenset(sf.variants())
