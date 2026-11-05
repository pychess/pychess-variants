"""Catalogue document construction, access policy, and client presentation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse

from const import STARTED
from fairy.fairy_board import sf
from nnue_identity import fsf_ini_v1_fingerprint
from settings import ADMINS

from . import assets, builtin_data, models, validation
from .betza import catalogued_betza_diagrams, catalogued_betza_pieces
from .promotions import promotion_chaining_requires_replay_only
from .rules import catalogued_random_start, catalogued_rule_summary


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def _is_active_catalogued_doc(doc: Mapping[str, Any]) -> bool:
    return (
        bool(doc.get("enabled", True))
        and not bool(doc.get("archived", False))
        and not promotion_chaining_requires_replay_only(str(doc.get("ini") or ""))
    )


def _catalogued_visibility(doc: Mapping[str, Any]) -> str:
    visibility = str(doc.get("visibility") or models.CATALOGUED_VISIBILITY_PRIVATE).strip().lower()
    return (
        visibility
        if visibility in models.CATALOGUED_VISIBILITIES
        else models.CATALOGUED_VISIBILITY_PRIVATE
    )


def _catalogued_source(doc: Mapping[str, Any]) -> str:
    source = str(doc.get("source") or models.CATALOGUED_SOURCE_USER).strip().lower()
    if source == models.CATALOGUED_SOURCE_FSF_BUILTIN:
        return models.CATALOGUED_SOURCE_FSF_BUILTIN
    return models.CATALOGUED_SOURCE_USER


def _is_fsf_builtin_catalogued_doc(doc: Mapping[str, Any]) -> bool:
    return _catalogued_source(doc) == models.CATALOGUED_SOURCE_FSF_BUILTIN


def _catalogued_description(doc: Mapping[str, Any]) -> str:
    description = str(doc.get("description") or "")
    if description or not _is_fsf_builtin_catalogued_doc(doc):
        return description
    name = str(doc.get("fsfBuiltinVariant") or doc.get("name") or doc.get("_id") or "")
    metadata = builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS.get(name, {})
    return str(metadata.get("description") or builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION)


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


def _can_preload_catalogued_doc(username: str | None, doc: Mapping[str, Any]) -> bool:
    if not _is_active_catalogued_doc(doc):
        return False
    if _catalogued_visibility(doc) == models.CATALOGUED_VISIBILITY_PUBLIC:
        return True
    if not username:
        return False
    return doc.get("author") == username or _is_admin_username(username)


def _can_open_catalogued_doc(username: str | None, doc: Mapping[str, Any]) -> bool:
    if not _is_active_catalogued_doc(doc):
        return False
    if _catalogued_visibility(doc) in {
        models.CATALOGUED_VISIBILITY_PUBLIC,
        models.CATALOGUED_VISIBILITY_UNLISTED,
    }:
        return True
    if not username:
        return False
    return doc.get("author") == username or _is_admin_username(username)


def _catalogued_public_query() -> dict[str, Any]:
    return {
        "enabled": {"$ne": False},
        "archived": {"$ne": True},
        "visibility": models.CATALOGUED_VISIBILITY_PUBLIC,
    }


def _client_doc(
    doc: Mapping[str, Any],
    *,
    game_count: int | None = None,
    favorite_names: set[str] | None = None,
) -> models.CataloguedVariantClientDocument:
    description = _catalogued_description(doc)
    tooltip = description or "Catalogued variant"
    ini = str(doc.get("ini") or "")
    start_fen = str(doc["startFen"])
    base_variant = str(doc.get("baseVariant") or "")
    pieces = list(doc.get("pieces") or ["k"])
    king_roles = (
        validation.catalogued_king_roles(ini, pieces)
        if validation._ini_option(ini, "extinctionValue") is not None
        else list(doc.get("kingRoles") or validation.catalogued_king_roles(ini, pieces))
    )
    pocket_roles = validation._catalogued_pocket_roles_from_doc(
        doc, ini, start_fen, pieces, king_roles
    )
    capture_to_hand = bool(
        doc.get("captureToHand", validation._ini_bool(ini, "capturesToHand", default=False))
    )
    promotion_type = str(doc.get("promotionType") or validation.catalogued_promotion_type(ini))
    promotion_roles = list(
        doc.get("promotionRoles") or validation.catalogued_promotion_roles(ini, pieces)
    )
    promotion_order = list(
        doc.get("promotionOrder") or validation.catalogued_promotion_order(ini, promotion_type)
    )
    show_promoted = bool(
        doc.get("showPromoted", validation.catalogued_show_promoted(ini, start_fen))
    )
    rules_gate = bool(doc.get("rulesGate", validation.catalogued_rules_gate(ini)))
    rules_pass = bool(doc.get("rulesPass", validation.catalogued_rules_pass(ini)))
    rules_arrowing = bool(doc.get("rulesArrowing", False))
    show_check_counters = bool(
        doc.get("showCheckCounters", validation.catalogued_show_check_counters(ini))
    )

    client_doc: models.CataloguedVariantClientDocument = {
        "name": str(doc["name"]),
        "displayName": str(doc.get("displayName") or doc["name"]),
        "tooltip": tooltip,
        "ini": ini,
        "baseVariant": base_variant or (validation.extract_variant_base_name(ini) if ini else ""),
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
        "category": models.CATALOGUED_CATEGORY,
        "author": str(doc.get("author") or ""),
        "source": _catalogued_source(doc),
        "system": _is_fsf_builtin_catalogued_doc(doc),
        "visibility": _catalogued_visibility(doc),
        "pieceSetDirectional": bool(doc.get("pieceSetDirectional", False)),
        "directionalPieceSet": assets._catalogued_piece_set_is_directional(doc),
        "hasPieceSet": assets._has_complete_piece_set(doc),
        "hasBoard": assets._has_board_svg(doc),
        "archived": bool(doc.get("archived", False)),
        "enabled": bool(doc.get("enabled", True)),
        "replayOnly": promotion_chaining_requires_replay_only(ini),
    }
    if client_doc["source"] == models.CATALOGUED_SOURCE_USER and ini:
        nnue_base_variant = validation.extract_variant_base_name(ini)
        # A section-only fingerprint is sufficient only when the inherited base
        # is an engine/site built-in whose meaning a different UDV cannot
        # replace. Custom-on-custom inheritance would need a full chain identity,
        # so keep those variants on the manual NNUE path for now.
        if not nnue_base_variant or validation._is_builtin_variant_name(nnue_base_variant):
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
    piece_names = validation.parse_catalogued_piece_names(doc.get("pieceNames"))
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
    piece_family_override = validation._catalogued_piece_family_override(doc)
    if piece_family_override:
        client_doc["pieceFamilyOverride"] = piece_family_override
    board_family_override = validation._catalogued_board_family_override(doc)
    if board_family_override:
        client_doc["boardFamilyOverride"] = board_family_override
    if client_doc["hasPieceSet"]:
        client_doc["pieceSetRevision"] = assets._piece_set_revision(doc)
    if client_doc["hasBoard"]:
        client_doc["boardRevision"] = assets._board_svg_revision(doc)
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


def catalogued_variant_rule_context(doc: Mapping[str, Any]) -> dict[str, Any]:
    ini = str(doc.get("rulesIni") or doc.get("ini") or "")
    start_fen = str(doc.get("startFen") or "")
    pieces = list(
        doc.get("pieces") or validation.piece_letters_from_fen(start_fen or "8/8/8/8/8/8/8/8")
    )
    width = int(doc.get("width") or 0)
    height = int(doc.get("height") or 0)
    if not width or not height:
        width, height = validation.board_dimensions_from_fen(start_fen) if start_fen else (8, 8)
    king_roles = list(doc.get("kingRoles") or validation.catalogued_king_roles(ini, pieces))

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
            validation._catalogued_pocket_roles_from_doc(doc, ini, start_fen, pieces, king_roles)
        ),
        "promotionRoles": ", ".join(
            list(doc.get("promotionRoles") or validation.catalogued_promotion_roles(ini, pieces))
        ),
        "captureToHand": bool(
            doc.get("captureToHand", validation._ini_bool(ini, "capturesToHand", default=False))
        ),
        "enabled": bool(doc.get("enabled", True)),
        "archived": bool(doc.get("archived", False)),
        "visibility": _catalogued_visibility(doc),
        "ruleSummary": catalogued_rule_summary(doc),
        "customPieceDiagrams": catalogued_betza_diagrams(doc),
    }


def _can_modify(username: str, doc: Mapping[str, Any]) -> bool:
    return doc.get("author") == username or _is_admin_username(username)


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
    visibility: str = models.CATALOGUED_VISIBILITY_PRIVATE,
    piece_family_override: str = "",
    board_family_override: str = "",
    archived: bool = False,
    game_count: int = 0,
    favorite_count: int = 0,
    source: str = models.CATALOGUED_SOURCE_USER,
    fsf_builtin_variant: str | None = None,
    client_variant: str = "",
    premove_variant: str = "",
) -> models.CataloguedVariantDocument:
    doc: models.CataloguedVariantDocument = {
        "_id": name,
        "name": name,
        "displayName": validation._clean_display_name(display_name, name),
        "description": validation._clean_description(description),
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
        "category": models.CATALOGUED_CATEGORY,
        "visibility": validation._clean_visibility(visibility),
        "pieceSetDirectional": piece_set_directional,
        "source": source,
        "gameCount": max(0, int(game_count)),
        "favoriteCount": max(0, int(favorite_count)),
        "createdAt": created_at,
        "updatedAt": datetime.now(UTC),
    }
    cleaned_piece_names = validation.parse_catalogued_piece_names(piece_names)
    if cleaned_piece_names:
        doc["pieceNames"] = cleaned_piece_names
    if piece_family_override:
        doc["pieceFamilyOverride"] = validation._clean_piece_family_override(piece_family_override)
    if board_family_override:
        cleaned_board_family = validation._clean_board_family_override(board_family_override)
        validation._ensure_board_family_dimensions(cleaned_board_family, width, height)
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


def _clean_catalogued_reference(value: Any) -> models.CataloguedVariantReference | None:
    if not isinstance(value, Mapping):
        return None

    url = str(value.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    label = str(value.get("label") or "").strip()[:80] or builtin_data._reference_label_for_url(url)
    return {"label": label, "url": url}


def _clean_catalogued_references(value: Any) -> list[models.CataloguedVariantReference]:
    if not isinstance(value, (list, tuple)):
        return []

    seen: set[str] = set()
    references: list[models.CataloguedVariantReference] = []
    for item in value:
        reference = _clean_catalogued_reference(item)
        if reference is None or reference["url"] in seen:
            continue
        seen.add(reference["url"])
        references.append(reference)
    return references


def _fsf_legacy_reference_description(references: list[models.CataloguedVariantReference]) -> str:
    if not references:
        return builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION
    urls = ", ".join(reference["url"] for reference in references)
    return f"{builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION} Reference: {urls}"


def _fsf_builtin_description_is_auto(
    description: str,
    metadata: Mapping[str, Any],
    references: list[models.CataloguedVariantReference],
) -> bool:
    metadata_description = str(
        metadata.get("description") or builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION
    )
    return not description or description in {
        builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        metadata_description,
        _fsf_legacy_reference_description(references),
    }


def _catalogued_references_for_display(
    doc: Mapping[str, Any],
) -> list[models.CataloguedVariantReference]:
    if not _is_fsf_builtin_catalogued_doc(doc):
        return []
    return _clean_catalogued_references(doc.get("references"))


def _fsf_builtin_description_for_doc(
    metadata: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
    references: list[models.CataloguedVariantReference],
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
) -> models.CataloguedVariantDocument:
    start_fen = sf.start_fen(name)
    if not start_fen:
        raise ValueError(f"Fairy-Stockfish did not provide a start FEN for {name!r}.")

    width, height = validation.board_dimensions_from_fen(start_fen)
    validation._catalogued_grand_from_dimensions(width, height)
    pieces = validation._merge_piece_letters(
        validation._catalogued_piece_roles_from_ini("", start_fen),
        _fsf_metadata_string_list(metadata, "pieces"),
    )
    king_roles = _fsf_metadata_string_list(
        metadata, "kingRoles"
    ) or validation.catalogued_king_roles("", pieces)
    pocket_roles = _fsf_metadata_string_list(
        metadata, "pocketRoles"
    ) or validation.catalogued_pocket_roles(
        "",
        start_fen,
        pieces,
        king_roles,
        capture_to_hand=_fsf_metadata_bool(metadata, "captureToHand", False),
    )
    promotion_type = str(metadata.get("promotionType") or validation.catalogued_promotion_type(""))
    promotion_roles = _fsf_metadata_string_list(
        metadata, "promotionRoles"
    ) or validation.catalogued_promotion_roles("", pieces)
    promotion_order = _fsf_metadata_string_list(
        metadata, "promotionOrder"
    ) or validation.catalogued_promotion_order("", promotion_type)
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
        username=models.CATALOGUED_FSF_BUILTIN_AUTHOR,
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
            metadata, "showPromoted", validation.catalogued_show_promoted("", start_fen)
        ),
        rules_gate=_fsf_metadata_bool(metadata, "rulesGate", False),
        rules_pass=_fsf_metadata_bool(metadata, "rulesPass", False),
        rules_arrowing=_fsf_metadata_bool(metadata, "rulesArrowing", False),
        legal_moves_need_history=_fsf_metadata_bool(metadata, "legalMovesNeedHistory", False),
        n_fold_is_draw=_fsf_metadata_bool(metadata, "nFoldIsDraw", False),
        show_check_counters=_fsf_metadata_bool(metadata, "showCheckCounters", False),
        created_at=cast(datetime, (existing or {}).get("createdAt") or datetime.now(UTC)),
        visibility=str((existing or {}).get("visibility") or models.CATALOGUED_VISIBILITY_PUBLIC),
        archived=bool((existing or {}).get("archived", False)),
        game_count=int((existing or {}).get("gameCount") or 0),
        favorite_count=int((existing or {}).get("favoriteCount") or 0),
        source=models.CATALOGUED_SOURCE_FSF_BUILTIN,
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
