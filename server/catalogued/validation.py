"""INI, FEN, and metadata validation for catalogue entries."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from aiohttp import web
from compress import MAX_COMPRESSED_BOARD_HEIGHT, MAX_COMPRESSED_BOARD_WIDTH
from fairy.fairy_board import sf
from variants import ServerVariants

from . import builtin_data, models
from .promotions import ensure_no_promotion_chaining

log = logging.getLogger(__name__)


def _clean_piece_family_override(piece_family: str | None) -> str:
    cleaned = str(piece_family or "").strip().lower()
    if cleaned in {"", "auto", "auto-detect", "autodetect"}:
        return ""
    if cleaned not in models.CATALOGUED_PIECE_FAMILY_OVERRIDES:
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


def _clean_board_family_override(board_family: str | None) -> str:
    cleaned = str(board_family or "").strip().lower()
    if cleaned in {"", "auto", "auto-detect", "autodetect"}:
        return ""
    if cleaned not in models.CATALOGUED_BOARD_FAMILY_OVERRIDES:
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
    expected_width, expected_height = models.CATALOGUED_BOARD_FAMILY_DIMENSIONS[board_family]
    if (width, height) != (expected_width, expected_height):
        raise web.HTTPBadRequest(
            text=(
                f'Board style "{board_family}" requires a '
                f"{expected_width}x{expected_height} board, not {width}x{height}."
            )
        )


def _clean_visibility(visibility: str | None) -> str:
    cleaned = str(visibility or models.CATALOGUED_VISIBILITY_PRIVATE).strip().lower()
    if cleaned not in models.CATALOGUED_VISIBILITIES:
        raise web.HTTPBadRequest(text="Variant visibility must be private, unlisted, or public.")
    return cleaned


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
    if len(ini.encode("utf-8")) > models.MAX_CATALOGUED_INI_BYTES:
        raise web.HTTPBadRequest(text="The INI file is too large.")


def _catalogued_variant_section_matches(ini: str) -> list[models.VariantSectionMatch]:
    """Return simple top-level INI section headers without using regex.

    The uploaded text is user controlled, so parsing line-by-line avoids the
    CodeQL ReDoS warning around multiline regex scanning. The caller still
    validates the extracted section name with the stricter site rule.
    """
    _ensure_catalogued_ini_size(ini)

    matches: list[models.VariantSectionMatch] = []
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
                    models.VariantSectionMatch(
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
        raise web.HTTPBadRequest(text=models.VARIANT_NAME_ERROR)

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
            for name, metadata in builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS.items()
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
        if separator and key.strip().casefold() not in models.CATALOGUED_NON_RULE_OPTIONS:
            return

    raise web.HTTPBadRequest(text=f"This variant is already playable on PyChess as {display_name}.")


def replace_variant_section_name(ini: str, new_name: str) -> str:
    if not _is_valid_variant_name(new_name):
        raise web.HTTPBadRequest(text=models.VARIANT_NAME_ERROR)

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


def _ensure_catalogued_rules_supported(ini: str, *, for_replay: bool = False) -> None:
    if not for_replay:
        ensure_no_promotion_chaining(ini)
    unsupported: list[str] = []

    for key, reason in models.UNSUPPORTED_CATALOGUED_BOOL_RULES.items():
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

    for key, reason in models.UNSUPPORTED_CATALOGUED_VALUE_RULES.items():
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
    if not separator or key.strip().casefold() != models.PYCHESS_PIECES_METADATA_KEY:
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
            cwd=models.PROJECT_ROOT,
        )
    except FileNotFoundError as exc:
        raise web.HTTPServiceUnavailable(
            text=f"Fairy-Stockfish checker executable was not found: {args[0]}"
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin.encode("utf-8") if stdin is not None else None),
            timeout=models.FSF_CHECK_TIMEOUT_SECONDS,
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
    return (
        name in builtin_data.BUILTIN_VARIANT_NAMES or name in builtin_data.BUILTIN_FSF_VARIANT_NAMES
    )


def validate_catalogued_ini(
    ini: str, *, for_replay: bool = False
) -> models.CataloguedVariantValidation:
    _ensure_catalogued_ini_size(ini)
    _ensure_catalogued_rules_supported(ini, for_replay=for_replay)
    name = extract_variant_name(ini)
    base_variant = extract_variant_base_name(ini)

    try:
        if not for_replay or name not in sf.variants():
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

    return models.CataloguedVariantValidation(
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
            for metadata in builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS.values()
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
        char not in models.DISPLAY_NAME_PUNCTUATION
        and not (unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd")
        for char in cleaned
    ):
        raise web.HTTPBadRequest(text=models.DISPLAY_NAME_ERROR)

    cleaned = models.DISPLAY_NAME_REPEATED_SEPARATOR_RE.sub(r"\1", cleaned)
    has_letter_or_number = any(
        unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd"
        for char in cleaned
    )
    if (
        len(cleaned) > models.MAX_DISPLAY_NAME_LEN
        or not has_letter_or_number
        or cleaned[0] in models.DISPLAY_NAME_DISALLOWED_EDGE_SEPARATORS
        or cleaned[-1] in models.DISPLAY_NAME_DISALLOWED_EDGE_SEPARATORS
    ):
        raise web.HTTPBadRequest(text=models.DISPLAY_NAME_ERROR)
    return cleaned


def _clean_display_name(display_name: str, fallback: str) -> str:
    return (display_name or fallback).strip()[: models.MAX_DISPLAY_NAME_LEN] or fallback


def _clean_description(description: str) -> str:
    return description.strip()[: models.MAX_DESCRIPTION_LEN]


def _clean_piece_name(piece: str, name: str) -> tuple[str, str]:
    letter = piece.strip().lower()
    if len(letter) != 1 or not letter.isascii() or not letter.isalpha():
        raise web.HTTPBadRequest(
            text="Invalid piece names. Use one ASCII letter before each colon, such as z:Zebra."
        )

    cleaned = " ".join(unicodedata.normalize("NFKC", name).split())
    if (
        not cleaned
        or len(cleaned) > models.MAX_PIECE_NAME_LEN
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
                f"Piece names must be 1-{models.MAX_PIECE_NAME_LEN} characters, contain a letter "
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
        if len(value) > models.MAX_PIECE_NAMES_TEXT_LEN:
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
