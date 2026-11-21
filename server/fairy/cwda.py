from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from catalogued.betza import CataloguedBetzaDiagram, betza_diagram


@dataclass(frozen=True)
class Army:
    name: str
    back_rank: str
    pieces: str
    castling_rook: str


class CwdaDiagramGroup(TypedDict):
    name: str
    diagrams: list[CataloguedBetzaDiagram]


FIDE = Army("FIDE", "rnbqkbnr", "rnbq", "r")
COLORBOUND_CLOBBERERS = Army("Colorbound Clobberers", "dwackawd", "dwac", "d")
NUTTY_KNIGHTS = Army("Nutty Knights", "gihokhig", "giho", "g")
REMARKABLE_ROOKIES = Army("Remarkable Rookies", "smfekfms", "smfe", "s")

CWDA_ARMIES = (FIDE, COLORBOUND_CLOBBERERS, NUTTY_KNIGHTS, REMARKABLE_ROOKIES)
CWDA_DEFAULT_FEN = "dwackawd/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

CWDA_FAIRY_PIECES = (
    (
        COLORBOUND_CLOBBERERS.name,
        (
            ("Bede", "d", "BD"),
            ("Waffle", "w", "WA"),
            ("FAD", "a", "FAD"),
            ("Cardinal", "c", "BN"),
        ),
    ),
    (
        NUTTY_KNIGHTS.name,
        (
            ("Charging rook", "g", "fsRbK"),
            ("Fibnif", "i", "FvN"),
            ("Charging knight", "h", "fhNbKsW"),
            ("Colonel", "o", "KfsRfhN"),
        ),
    ),
    (
        REMARKABLE_ROOKIES.name,
        (
            ("Short rook", "s", "R4"),
            ("Woody rook", "m", "WD"),
            ("Half duck", "f", "FDH"),
            ("Chancellor", "e", "RN"),
        ),
    ),
)


def cwda_betza_diagram_groups() -> list[CwdaDiagramGroup]:
    """Return movement diagrams for the three non-FIDE CWDA armies."""

    return [
        {
            "name": army_name,
            "diagrams": [
                betza_diagram(piece, betza, f"{piece_name} ({piece.upper()})")
                for piece_name, piece, betza in pieces
            ],
        }
        for army_name, pieces in CWDA_FAIRY_PIECES
    ]


def cwda_start_fen(white: Army, black: Army) -> str:
    return f"{black.back_rank}/pppppppp/8/8/8/8/PPPPPPPP/{white.back_rank.upper()} w KQkq - 0 1"


# FIDE vs. FIDE is ordinary Chess, so it is intentionally not offered here.
CWDA_START_FENS = tuple(
    cwda_start_fen(white, black)
    for white in CWDA_ARMIES
    for black in CWDA_ARMIES
    if white is not FIDE or black is not FIDE
)

_PROFILE_BY_ARMIES = {
    frozenset((FIDE.back_rank, COLORBOUND_CLOBBERERS.back_rank)): "cwda-fide-clobberers",
    frozenset((FIDE.back_rank, NUTTY_KNIGHTS.back_rank)): "cwda-fide-knights",
    frozenset((FIDE.back_rank, REMARKABLE_ROOKIES.back_rank)): "cwda-fide-rookies",
    frozenset((COLORBOUND_CLOBBERERS.back_rank,)): "cwda-clobberers",
    frozenset(
        (COLORBOUND_CLOBBERERS.back_rank, NUTTY_KNIGHTS.back_rank)
    ): "cwda-clobberers-knights",
    frozenset(
        (COLORBOUND_CLOBBERERS.back_rank, REMARKABLE_ROOKIES.back_rank)
    ): "cwda-clobberers-rookies",
    frozenset((NUTTY_KNIGHTS.back_rank,)): "cwda-knights",
    frozenset((NUTTY_KNIGHTS.back_rank, REMARKABLE_ROOKIES.back_rank)): "cwda-knights-rookies",
    frozenset((REMARKABLE_ROOKIES.back_rank,)): "cwda-rookies",
}


def cwda_engine_variant(initial_fen: str | None) -> str:
    """Return the hidden Fairy-Stockfish profile matching a CwDA start position."""

    if not initial_fen:
        return "cwda-fide-clobberers"

    try:
        ranks = initial_fen.split()[0].split("/")
        black_back_rank = ranks[0].lower()
        white_back_rank = ranks[-1].lower()
    except (IndexError, AttributeError):
        return "cwda"

    return _PROFILE_BY_ARMIES.get(frozenset((white_back_rank, black_back_rank)), "cwda")
