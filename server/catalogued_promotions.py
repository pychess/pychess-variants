from __future__ import annotations

import re
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

from aiohttp import web
from catalogued_rules import PIECE_OPTION_NAMES, parse_catalogued_ini

# pyffish does not expose inherited promotion mappings. These are the built-in
# shogi-style mappings from Fairy-Stockfish's src/variant.cpp; site definitions
# below are read from our authoritative variants.ini instead of duplicated.
_MINISHOGI_PIECES = "shogiPawn=p silver=s gold=g bishop=b dragonHorse=h rook=r bers=d king=k"
_MINISHOGI_PROMOTIONS = "p:g s:g b:h r:d"
_BUILTIN_PROMOTIONS: dict[str, tuple[str, str]] = {
    "minishogi": (_MINISHOGI_PIECES, _MINISHOGI_PROMOTIONS),
    "mini": (_MINISHOGI_PIECES, _MINISHOGI_PROMOTIONS),
    "gorogoro": (_MINISHOGI_PIECES, _MINISHOGI_PROMOTIONS),
    "judkins": (_MINISHOGI_PIECES + " shogiKnight=n", _MINISHOGI_PROMOTIONS + " n:g"),
    "euroshogi": (_MINISHOGI_PIECES + " customPiece1=n", _MINISHOGI_PROMOTIONS + " n:g"),
    "shogi": (_MINISHOGI_PIECES + " lance=l shogiKnight=n", _MINISHOGI_PROMOTIONS + " l:g n:g"),
    "checkshogi": (
        _MINISHOGI_PIECES + " lance=l shogiKnight=n",
        _MINISHOGI_PROMOTIONS + " l:g n:g",
    ),
    "shoshogi": (
        _MINISHOGI_PIECES + " king=- commoner=k lance=l shogiKnight=n customPiece1=e",
        _MINISHOGI_PROMOTIONS + " l:g n:g e:k",
    ),
    "okisakishogi": (
        _MINISHOGI_PIECES + " customPiece1=l knight=n queen=q",
        _MINISHOGI_PROMOTIONS + " l:g n:g",
    ),
    "kyotoshogi": (_MINISHOGI_PIECES + " lance=l shogiKnight=n", "p:r s:b l:g n:g"),
    "micro": (_MINISHOGI_PIECES + " lance=l shogiKnight=n", "p:n l:s b:g r:g"),
    "dobutsu": ("shogiPawn=c gold=h fers=e wazir=g commoner=l", "c:h"),
    "torishogi": (
        (
            "shogiPawn=s king=k customPiece1=f customPiece2=c customPiece3=l "
            "customPiece4=r customPiece5=p customPiece6=g customPiece7=e"
        ),
        "s:g f:e",
    ),
    "yarishogi": (
        (
            "shogiPawn=p king=k rook=l customPiece1=n customPiece2=b customPiece3=r "
            "customPiece4=g customPiece5=s"
        ),
        "p:s n:g b:g r:l",
    ),
    "wolf": ("pawn=p customPiece3=e", "p:e"),
}
_PROMOTION_PAIR = re.compile(r"([A-Za-z])\s*:\s*([A-Za-z-])")


@lru_cache(maxsize=1)
def _site_definitions() -> dict[str, str]:
    parser = ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=("#",))
    parser.read(Path(__file__).resolve().parents[1] / "variants.ini", encoding="utf-8")
    return {
        section.split(":", 1)[0].strip(): (
            f"[{section}]\n" + "\n".join(f"{key}={value}" for key, value in parser[section].items())
        )
        for section in parser.sections()
    }


@lru_cache(maxsize=256)
def _base_promotions(name: str) -> tuple[dict[str, str], dict[str, str]]:
    if name in _BUILTIN_PROMOTIONS:
        pieces, promotions = _BUILTIN_PROMOTIONS[name]
        ini = "[builtin]\n" + pieces.replace(" ", "\n") + "\npromotedPieceType=" + promotions
        return _promotion_rules(ini)
    ini = _site_definitions().get(name)
    if ini is not None:
        return _promotion_rules(ini)
    # Other built-ins have no shogi-style promotions. Unknown parents are
    # rejected by the existing isolated engine validation.
    return {"pawn": "p", "knight": "n", "bishop": "b", "rook": "r", "queen": "q", "king": "k"}, {}


def _promotion_rules(ini: str) -> tuple[dict[str, str], dict[str, str]]:
    parsed = parse_catalogued_ini(ini)
    inherited_pieces, inherited_promotions = (
        _base_promotions(parsed.parent) if parsed.parent else ({}, {})
    )
    pieces = inherited_pieces.copy()
    promotions = inherited_promotions.copy()
    # Store edges by piece identity, so renaming an inherited gold or rook does
    # not hide a chain. Only promotion rules and piece letters matter here.
    for key, value in parsed.items():
        key = key.casefold()
        if key in PIECE_OPTION_NAMES or key.startswith("custompiece"):
            pieces[key] = value.split(":", 1)[0].strip().lower()
    identities = {letter: key for key, letter in pieces.items() if letter != "-"}
    for match in _PROMOTION_PAIR.finditer(parsed.option("promotedPieceType") or ""):
        source, target = (letter.lower() for letter in match.groups())
        promotions[identities.get(source, source)] = identities.get(target, target)
    return pieces, promotions


def ensure_no_promotion_chaining(ini: str) -> None:
    pieces, promotions = _promotion_rules(ini)
    enabled_promotions = {
        source: target
        for source, target in promotions.items()
        if target != "-" and pieces.get(source) != "-" and pieces.get(target) != "-"
    }
    if any(target in enabled_promotions for target in enabled_promotions.values()):
        raise web.HTTPBadRequest(text="Promotion chaining is not supported by FSF.")
