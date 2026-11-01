from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from functools import lru_cache
from typing import Any, NamedTuple, TypedDict

from betza_visualizer import BetzaSvgOptions, render_betza_svg

log = logging.getLogger(__name__)


class CataloguedBetzaDiagram(TypedDict):
    piece: str
    betza: str
    title: str
    svg: str


class _PieceDiagramDefinition(NamedTuple):
    key: str
    piece: str
    betza: str
    title: str


class _FsfBuiltinPieceDefinition(NamedTuple):
    piece: str
    title: str
    betza: str


MAX_CATALOGUED_BETZA_DIAGRAMS = 32  # 25 customPiece slots + known FSF built-in pieces.
BETZA_DIAGRAM_CACHE_SIZE = 512
BETZA_DIAGRAM_RENDERER_VERSION = 3

# Fairy-Stockfish built-in pieces that can appear in catalogued/user-defined
# variants through inherited built-in variants rather than customPieceN INI
# lines. Keep this variant-scoped instead of global-by-letter: several FSF
# variants intentionally reuse familiar letters for different pieces (for
# example New Zealand's rook/knight, Nightrider's knight, and Shatranj's
# bishop/queen letters), so the same letter must not be interpreted outside
# the variant where Fairy-Stockfish assigns that built-in piece name.
FSF_BUILTIN_PIECE_DIAGRAMS_BY_VARIANT: Mapping[str, tuple[_FsfBuiltinPieceDefinition, ...]] = {
    "almost": (_FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),),
    "amazon": (_FsfBuiltinPieceDefinition("a", "Amazon", "QN"),),
    "berolina": (_FsfBuiltinPieceDefinition("p", "Berolina pawn", "mfFcfeWimfnA"),),
    "capablanca": (
        _FsfBuiltinPieceDefinition("a", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),
    ),
    "centaur": (_FsfBuiltinPieceDefinition("c", "Centaur", "KN"),),
    "chancellor": (_FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),),
    "chaturanga": (
        _FsfBuiltinPieceDefinition("b", "Alfil", "A"),
        _FsfBuiltinPieceDefinition("q", "Fers", "F"),
    ),
    "courier": (
        _FsfBuiltinPieceDefinition("e", "Alfil", "A"),
        _FsfBuiltinPieceDefinition("f", "Fers", "F"),
        _FsfBuiltinPieceDefinition("m", "Commoner", "K"),
        _FsfBuiltinPieceDefinition("w", "Wazir", "W"),
    ),
    "extinction": (_FsfBuiltinPieceDefinition("k", "Commoner", "K"),),
    "georgian": (_FsfBuiltinPieceDefinition("a", "Amazon", "QN"),),
    "giveaway": (_FsfBuiltinPieceDefinition("k", "Commoner", "K"),),
    "gothic": (
        _FsfBuiltinPieceDefinition("a", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),
    ),
    "grand": (
        _FsfBuiltinPieceDefinition("a", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),
    ),
    "grasshopper": (_FsfBuiltinPieceDefinition("g", "Grasshopper", "gQ"),),
    "gustav3": (_FsfBuiltinPieceDefinition("a", "Amazon", "QN"),),
    "janus": (_FsfBuiltinPieceDefinition("j", "Archbishop", "BN"),),
    "knightmate": (_FsfBuiltinPieceDefinition("m", "Commoner", "K"),),
    "legan": (_FsfBuiltinPieceDefinition("p", "Legan pawn", "mflFcflW"),),
    "modern": (_FsfBuiltinPieceDefinition("m", "Archbishop", "BN"),),
    "newzealand": (
        _FsfBuiltinPieceDefinition("r", "Rookni", "mRcN"),
        _FsfBuiltinPieceDefinition("n", "Kniroo", "mNcR"),
    ),
    "nightrider": (_FsfBuiltinPieceDefinition("n", "Nightrider", "NN"),),
    "nocheckatomic": (_FsfBuiltinPieceDefinition("k", "Commoner", "K"),),
    "omicron": (
        _FsfBuiltinPieceDefinition("c", "Champion", "DAW"),
        _FsfBuiltinPieceDefinition("w", "Wizard", "CF"),
    ),
    "opulent": (
        _FsfBuiltinPieceDefinition("a", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),
        _FsfBuiltinPieceDefinition("n", "Marquis", "NW"),
        _FsfBuiltinPieceDefinition("w", "Wizard", "CF"),
        _FsfBuiltinPieceDefinition("l", "Lion", "FDH"),
    ),
    "pawnback": (_FsfBuiltinPieceDefinition("p", "Backward pawn", "fbmWfceFifmnD"),),
    "pawnsideways": (_FsfBuiltinPieceDefinition("p", "Sideways pawn", "fsmWfceFifmnD"),),
    "paradigm": (_FsfBuiltinPieceDefinition("b", "Dragon Bishop", "BnN"),),
    "perfect": (
        _FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),
        _FsfBuiltinPieceDefinition("m", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("g", "Amazon", "QN"),
    ),
    "petrified": (_FsfBuiltinPieceDefinition("k", "Commoner", "K"),),
    "shatar": (_FsfBuiltinPieceDefinition("j", "Bers", "RF"),),
    "shatranj": (
        _FsfBuiltinPieceDefinition("b", "Alfil", "A"),
        _FsfBuiltinPieceDefinition("q", "Fers", "F"),
    ),
    "tencubed": (
        _FsfBuiltinPieceDefinition("a", "Archbishop", "BN"),
        _FsfBuiltinPieceDefinition("m", "Chancellor", "RN"),
        _FsfBuiltinPieceDefinition("c", "Champion", "DAW"),
        _FsfBuiltinPieceDefinition("w", "Wizard", "CF"),
    ),
    "threekings": (_FsfBuiltinPieceDefinition("k", "Commoner", "K"),),
    "chigorin": (_FsfBuiltinPieceDefinition("c", "Chancellor", "RN"),),
}

# Betza definitions sent to the client for premove calculation but intentionally
# not rendered as rule-page diagrams. These are standard-looking pieces whose
# role letter differs from the chosen ``clientVariant`` compatibility profile.
# Keeping them separate avoids misleading diagrams (the Shatar/Courier bishop
# regression) while still overriding chessground's approximate fallback where
# required.
FSF_BUILTIN_PREMOVE_BETZA_OVERRIDES_BY_VARIANT: Mapping[str, Mapping[str, str]] = {
    "courier": {"b": "B"},
    # Raazuvaa disables the normal chess pawn double-step.
    "raazuvaa": {"p": "fmWfceF"},
    "shatar": {"b": "B"},
    # Torpedo pawns may make the forward double-step from every rank.
    "torpedo": {"p": "fmWfceFfmnD"},
    # Yari Shogi reuses the Shogi lance letter for a normal rook.
    "yarishogi": {"l": "R"},
}


def _strip_inline_comment(line: str) -> str:
    # Fairy-Stockfish examples use # for comments and not inside option values.
    return line.split("#", 1)[0].strip()


def _iter_ini_options(ini: str) -> Iterator[tuple[str, str]]:
    """Yield option/value pairs from the first parsed Fairy-Stockfish variant section."""

    inside_section = False
    for raw_line in ini.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and "]" in line:
            if inside_section:
                break
            inside_section = True
            continue
        if not inside_section or "=" not in line:
            continue

        key, value = _strip_inline_comment(line).split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            yield key, value


def _custom_piece_sort_key(option: str) -> tuple[int, int]:
    lowered = option.casefold()
    if lowered == "king":
        return (1, 0)
    suffix = lowered.removeprefix("custompiece")
    return (0, int(suffix) if suffix.isdigit() else 0)


def _custom_piece_definitions(ini: str) -> list[_PieceDiagramDefinition]:
    definitions: list[_PieceDiagramDefinition] = []

    for key, value in _iter_ini_options(ini):
        lowered = key.casefold()
        if lowered != "king" and not lowered.startswith("custompiece"):
            continue
        if value == "-":
            continue

        piece, separator, betza = value.partition(":")
        piece = piece.strip()
        betza = betza.strip()

        # A bare king definition, e.g. "king = k", means the normal king move.
        # It does not need a custom Betza diagram.
        if lowered == "king" and not separator:
            continue
        if not separator or not betza:
            continue
        if len(piece) != 1 or not piece.isalpha():
            continue

        piece = piece.lower()
        definitions.append(
            _PieceDiagramDefinition(
                key=key,
                piece=piece,
                betza=betza,
                title=f"{_custom_piece_title(key, piece)} movement",
            )
        )

    definitions.sort(key=lambda item: _custom_piece_sort_key(item.key))
    return definitions[:MAX_CATALOGUED_BETZA_DIAGRAMS]


def _preview_dimension(value: object, *, fallback: int = 11) -> int:
    if value is None or value == "":
        dimension = fallback
    elif isinstance(value, int):
        dimension = value
    elif isinstance(value, (float, str)):
        try:
            dimension = int(value)
        except ValueError:
            dimension = fallback
    else:
        dimension = fallback
    return min(11, max(5, dimension))


def _custom_piece_title(option: str, piece: str) -> str:
    if option.casefold() == "king":
        return f"Custom king ({piece.upper()})"
    suffix = option.casefold().removeprefix("custompiece")
    if suffix.isdigit():
        return f"Custom piece {suffix} ({piece.upper()})"
    return f"Custom piece {piece.upper()}"


def _section_base_variant(ini: str) -> str:
    for raw_line in ini.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and "]" in line:
            section = line[1 : line.index("]")].strip()
            _name, separator, base = section.partition(":")
            return base.strip().lower() if separator else ""
    return ""


def _doc_piece_letters(doc: Mapping[str, Any]) -> set[str]:
    pieces = doc.get("pieces")
    if isinstance(pieces, str):
        return {piece.lower() for piece in pieces.replace(",", " ").split() if piece}
    if isinstance(pieces, (list, tuple, set)):
        return {str(piece).lower() for piece in pieces if str(piece)}
    return set()


def _doc_piece_letters_key(doc: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(_doc_piece_letters(doc)))


def _doc_piece_names_key(doc: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    value = doc.get("pieceNames")
    if not isinstance(value, Mapping):
        return ()
    return tuple(
        sorted(
            (str(piece).strip().lower(), str(name).strip())
            for piece, name in value.items()
            if len(str(piece).strip()) == 1 and str(name).strip()
        )
    )


def _doc_variant_name(value: object) -> str:
    return str(value or "").strip().lower()


def _fsf_builtin_variant_names(doc: Mapping[str, Any], ini: str) -> list[str]:
    candidates = [
        doc.get("fsfBuiltinVariant"),
        doc.get("name"),
        doc.get("baseVariant"),
        _section_base_variant(ini),
    ]
    names: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        name = str(candidate or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _fsf_builtin_piece_definitions(
    doc: Mapping[str, Any],
    ini: str,
    occupied_pieces: set[str],
) -> list[_PieceDiagramDefinition]:
    pieces = _doc_piece_letters(doc)
    if not pieces:
        return []

    definitions: list[_PieceDiagramDefinition] = []
    for variant_name in _fsf_builtin_variant_names(doc, ini):
        for known in FSF_BUILTIN_PIECE_DIAGRAMS_BY_VARIANT.get(variant_name, ()):
            if known.piece not in pieces or known.piece in occupied_pieces:
                continue
            occupied_pieces.add(known.piece)
            definitions.append(
                _PieceDiagramDefinition(
                    key=f"fsf:{variant_name}:{known.piece}",
                    piece=known.piece,
                    betza=known.betza,
                    title=f"{known.title} movement",
                )
            )
    return definitions


def _fsf_builtin_premove_overrides(
    doc: Mapping[str, Any],
    ini: str,
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for variant_name in _fsf_builtin_variant_names(doc, ini):
        for piece, betza in FSF_BUILTIN_PREMOVE_BETZA_OVERRIDES_BY_VARIANT.get(
            variant_name, {}
        ).items():
            # A role may only appear after promotion and therefore be absent
            # from the starting-FEN-derived ``pieces`` list (Yari's l rook is
            # the concrete example). Sending an unused variant-scoped override
            # is harmless, while filtering it out would produce wrong premoves
            # after promotion.
            overrides.setdefault(piece, betza)
    return overrides


@lru_cache(maxsize=1024)
def _cached_betza_svg(
    betza: str,
    piece_label: str,
    title: str,
    board_width: int,
    board_height: int,
    renderer_version: int,
) -> str:
    del renderer_version  # Cache-busting key for future renderer changes.
    options = BetzaSvgOptions(
        board_width=board_width,
        board_height=board_height,
        cell_size=22,
        piece_label=piece_label,
        css_class="catalogued-betza-svg",
        title=title,
    )
    return render_betza_svg(betza, options)


def betza_diagram(
    piece: str,
    betza: str,
    title: str,
    *,
    board_width: int = 8,
    board_height: int = 8,
    svg_title: str | None = None,
) -> CataloguedBetzaDiagram:
    """Return one diagram using the renderer shared by variant rule pages."""

    width = _preview_dimension(board_width, fallback=8)
    height = _preview_dimension(board_height, fallback=8)
    return {
        "piece": piece.lower(),
        "betza": betza,
        "title": title,
        "svg": _cached_betza_svg(
            betza,
            piece.upper(),
            svg_title or f"{title} movement",
            width,
            height,
            BETZA_DIAGRAM_RENDERER_VERSION,
        ),
    }


@lru_cache(maxsize=BETZA_DIAGRAM_CACHE_SIZE)
def _cached_piece_diagram_definitions(
    ini: str,
    pieces: tuple[str, ...],
    piece_names: tuple[tuple[str, str], ...],
    fsf_builtin_variant: str,
    name: str,
    base_variant: str,
    renderer_version: int,
) -> tuple[_PieceDiagramDefinition, ...]:
    del renderer_version  # Cache-busting key for future built-in definition changes.
    custom_definitions = _custom_piece_definitions(ini)
    occupied_pieces = {definition.piece for definition in custom_definitions}
    fsf_doc = {
        "pieces": pieces,
        "fsfBuiltinVariant": fsf_builtin_variant,
        "name": name,
        "baseVariant": base_variant,
    }
    definitions = custom_definitions + _fsf_builtin_piece_definitions(fsf_doc, ini, occupied_pieces)
    names = dict(piece_names)
    definitions = [
        definition._replace(
            title=f"{names[definition.piece]} ({definition.piece.upper()}) movement"
        )
        if definition.piece in names
        else definition
        for definition in definitions
    ]
    return tuple(definitions[:MAX_CATALOGUED_BETZA_DIAGRAMS])


@lru_cache(maxsize=BETZA_DIAGRAM_CACHE_SIZE)
def _cached_catalogued_betza_diagrams(
    definitions: tuple[_PieceDiagramDefinition, ...],
    board_width: int,
    board_height: int,
    renderer_version: int,
) -> tuple[CataloguedBetzaDiagram, ...]:
    del renderer_version  # Cache-busting key for future diagram wording/layout changes.
    diagrams: list[CataloguedBetzaDiagram] = []

    for definition in definitions:
        try:
            diagram = betza_diagram(
                definition.piece,
                definition.betza,
                definition.title,
                board_width=board_width,
                board_height=board_height,
                svg_title=definition.title,
            )
        except Exception:
            log.warning(
                "Failed to render Betza diagram for %s (%s)",
                definition.key,
                definition.betza,
                exc_info=True,
            )
            continue
        if not diagram["svg"]:
            continue
        diagrams.append(diagram)

    return tuple(diagrams)


def _piece_definitions_for_doc(doc: Mapping[str, Any]) -> tuple[_PieceDiagramDefinition, ...]:
    ini = str(doc.get("rulesIni") or doc.get("ini") or "")
    return _cached_piece_diagram_definitions(
        ini,
        _doc_piece_letters_key(doc),
        _doc_piece_names_key(doc),
        _doc_variant_name(doc.get("fsfBuiltinVariant")),
        _doc_variant_name(doc.get("name")),
        _doc_variant_name(doc.get("baseVariant")),
        BETZA_DIAGRAM_RENDERER_VERSION,
    )


def catalogued_betza_pieces(doc: Mapping[str, Any]) -> dict[str, str]:
    """Return resolved Betza movement definitions needed by catalogued clients."""

    ini = str(doc.get("rulesIni") or doc.get("ini") or "")
    pieces = _fsf_builtin_premove_overrides(doc, ini)
    # Explicit/custom and diagram-worthy definitions are authoritative over
    # premove-only compatibility corrections for the same role.
    pieces.update(
        {definition.piece: definition.betza for definition in _piece_definitions_for_doc(doc)}
    )
    return pieces


def catalogued_betza_diagrams(doc: Mapping[str, Any]) -> list[CataloguedBetzaDiagram]:
    """Return inline SVG movement diagrams for custom and known FSF built-in pieces."""

    definitions = _piece_definitions_for_doc(doc)
    board_width = _preview_dimension(doc.get("width"))
    board_height = _preview_dimension(doc.get("height"))
    return list(
        _cached_catalogued_betza_diagrams(
            definitions,
            board_width,
            board_height,
            BETZA_DIAGRAM_RENDERER_VERSION,
        )
    )
