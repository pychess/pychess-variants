"""Runtime catalogue registration and game/client integration."""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from typing import Any

from aiohttp import web
from const import STARTED
from fairy.fairy_board import sf
from json_utils import json_dumps
from variants import (
    CataloguedServerVariant,
    get_server_variant,
    is_catalogued_variant,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)

from . import documents, models, repository, validation
from .rules import catalogued_random_start

log = logging.getLogger(__name__)


def catalogued_variant_client_doc_for_name(
    app_state: Any,
    name: str,
    username: str | None = None,
) -> models.CataloguedVariantClientDocument | None:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None or not documents._can_open_catalogued_doc(username, doc):
        return None
    return documents._client_doc(doc)


async def catalogued_variant_client_doc_for_game(
    app_state: Any,
    game: Any,
    username: str,
) -> models.CataloguedVariantClientDocument | None:
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
        doc = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    return documents._client_doc(doc)


def can_create_catalogued_seek(app_state: Any, name: str, username: str | None) -> bool:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return False
    return documents._can_open_catalogued_doc(username, doc)


def is_public_catalogued_variant(app_state: Any, name: str) -> bool:
    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return False
    return (
        documents._is_active_catalogued_doc(doc)
        and documents._catalogued_visibility(doc) == models.CATALOGUED_VISIBILITY_PUBLIC
    )


def catalogued_variant_allows_fishnet(app_state: Any, name: str) -> bool:
    """Return whether Fairy-Stockfish/fishnet should currently handle this variant."""

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None:
        return not is_catalogued_variant(name)
    return not documents.catalogued_variant_ai_disabled(doc)


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


def catalogued_variants_for_client(
    app_state: Any,
    username: str | None = None,
    favorite_names: set[str] | None = None,
    *,
    names: Collection[str] | None = None,
) -> list[models.CataloguedVariantClientDocument]:
    docs = getattr(app_state, "catalogued_variants", {})
    # A selective caller must not construct client documents for every entry.
    selected_docs = (
        docs.values() if names is None else (docs[name] for name in set(names) if name in docs)
    )
    client_docs = [
        documents._client_doc(doc, favorite_names=favorite_names)
        for doc in sorted(
            selected_docs, key=lambda item: str(item.get("displayName", item["name"])).casefold()
        )
        if documents._can_preload_catalogued_doc(username, doc)
    ]
    return (
        catalogued_variant_client_docs_with_dependencies(app_state, client_docs, username)
        if names is not None
        else client_docs
    )


def catalogued_variant_client_docs_with_dependencies(
    app_state: Any,
    client_docs: list[models.CataloguedVariantClientDocument],
    username: str | None = None,
) -> list[models.CataloguedVariantClientDocument]:
    """Order authorized roots and accessible catalogue ancestors before their children.

    Callers authorize the roots (including historical game or Study snapshots).
    Dependencies still obey normal visibility checks; a public child must never
    disclose a private parent's definition to an unrelated viewer.
    """
    roots = {doc["name"]: doc for doc in client_docs}
    docs = getattr(app_state, "catalogued_variants", {})
    visited: set[str] = set()
    result: list[models.CataloguedVariantClientDocument] = []

    def visit(doc: models.CataloguedVariantClientDocument, depth: int = 0) -> None:
        name = doc["name"]
        if name in visited or depth >= 64:
            return
        visited.add(name)
        base = str(doc.get("baseVariant") or "")
        if base and base not in visited:
            parent = roots.get(base)
            if parent is None:
                stored_parent = docs.get(base)
                if stored_parent is not None and documents._can_open_catalogued_doc(
                    username, stored_parent
                ):
                    parent = documents._client_doc(stored_parent)
            if parent is not None:
                visit(parent, depth + 1)
        result.append(doc)

    for doc in roots.values():
        visit(doc)
    return result


def invalidate_public_catalogued_variants_json(app_state: Any) -> None:
    """Drop the anonymous HTML payload after a catalogue update."""
    app_state._public_catalogued_variants_json = None


def public_catalogued_variants_json(app_state: Any) -> str:
    """Reuse the identical public catalogue JSON across anonymous HTML views.

    The cache is scoped to one app process. Writers invalidate it; the cheap
    dictionary identity/size check also covers direct additions in tests.
    An AI-disabled deadline must not remain cached beyond its expiration.
    """
    docs = getattr(app_state, "catalogued_variants", {})
    cached = getattr(app_state, "_public_catalogued_variants_json", None)
    now = datetime.now(UTC)
    if cached is not None:
        docs_id, count, expires, value = cached
        if docs_id == id(docs) and count == len(docs) and (expires is None or now < expires):
            return value

    value = json_dumps(catalogued_variants_for_client(app_state))
    expires = min(
        (
            deadline
            for doc in docs.values()
            if documents._can_preload_catalogued_doc(None, doc)
            if (deadline := documents.catalogued_variant_ai_disabled_until(doc, now=now))
            is not None
        ),
        default=None,
    )
    app_state._public_catalogued_variants_json = (id(docs), len(docs), expires, value)
    return value


def register_catalogued_variant_doc(
    app_state: Any,
    doc: Mapping[str, Any],
    *,
    load_config: bool = True,
) -> None:
    name = str(doc["name"])
    invalidate_public_catalogued_variants_json(app_state)
    if not documents._is_active_catalogued_doc(doc):
        getattr(app_state, "catalogued_variants", {}).pop(name, None)
        unregister_catalogued_server_variant(name)
        return

    ini = str(doc.get("ini") or "")
    start_fen = str(doc.get("startFen") or "")
    validation._ensure_catalogued_start_fen_has_side_to_move(start_fen)
    is_fsf_builtin = documents._is_fsf_builtin_catalogued_doc(doc)
    if not is_fsf_builtin:
        validation._ensure_catalogued_rules_supported(ini)

    if load_config and not is_fsf_builtin:
        sf.load_variant_config(ini)

    width = int(doc.get("width") or 0)
    height = int(doc.get("height") or 0)
    if not width or not height:
        width, height = validation.board_dimensions_from_fen(start_fen)

    register_catalogued_server_variant(
        name,
        str(doc.get("displayName") or name),
        random_start=catalogued_random_start(ini, start_fen, width, height),
        grand=validation._catalogued_grand_from_dimensions(width, height),
        extended_move_codec=validation._catalogued_extended_move_codec_from_dimensions(
            width, height
        ),
        arrowing=bool(doc.get("rulesArrowing", False)),
        show_promoted=bool(
            doc.get("showPromoted", validation.catalogued_show_promoted(ini, start_fen))
        ),
        legal_moves_need_history=bool(
            doc.get("legalMovesNeedHistory", validation.catalogued_legal_moves_need_history(ini))
        ),
        n_fold_is_draw=bool(doc.get("nFoldIsDraw", validation.catalogued_n_fold_is_draw(ini))),
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

    validated = validation.validate_catalogued_ini(ini)
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
        grand=validation._catalogued_grand_from_dimensions(width, height),
        extended_move_codec=validation._catalogued_extended_move_codec_from_dimensions(
            width, height
        ),
        arrowing=bool(doc.get("rulesArrowing", False)),
        show_promoted=bool(
            doc.get("showPromoted", validation.catalogued_show_promoted(ini, start_fen))
        ),
        legal_moves_need_history=bool(
            doc.get("legalMovesNeedHistory", validation.catalogued_legal_moves_need_history(ini))
        ),
        n_fold_is_draw=bool(doc.get("nFoldIsDraw", validation.catalogued_n_fold_is_draw(ini))),
    )


async def catalogued_variant_client_doc_for_tournament(
    app_state: Any, name: str
) -> models.CataloguedVariantClientDocument | None:
    """Return metadata needed to render a historical tournament variant.

    Tournament variants are public at creation time.  Keep their historical pages
    renderable even if the catalogue entry is later archived or made non-public.
    """

    doc = getattr(app_state, "catalogued_variants", {}).get(name)
    if doc is None and getattr(app_state, "db", None) is not None:
        doc = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    return documents._client_doc(doc)


def ensure_catalogued_variant_from_game_doc(app_state: Any, doc: Mapping[str, Any]) -> None:
    """Load an inline variant definition saved with a historical game if needed."""
    code = str(doc.get("v") or "")
    if not code or is_catalogued_variant(code) or not doc.get("vini"):
        return

    validated = validation.validate_catalogued_ini(str(doc["vini"]))
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
            "category": models.CATALOGUED_CATEGORY,
            "visibility": models.CATALOGUED_VISIBILITY_PRIVATE,
            "createdAt": now,
            "updatedAt": now,
        },
        load_config=False,
    )


async def init_catalogued_variants(app_state: Any) -> None:
    invalidate_public_catalogued_variants_json(app_state)
    app_state.catalogued_variants = {}

    collection = app_state.db[models.CATALOGUED_VARIANT_COLLECTION]
    await repository._remove_legacy_catalogued_icon_fields(collection)
    await repository._remove_legacy_fsf_builtin_description_fields(collection)

    await repository.ensure_fsf_catalogued_builtin_variants(app_state)

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
    return documents._catalogued_visibility(doc) == models.CATALOGUED_VISIBILITY_PUBLIC


def _has_active_catalogued_games(app_state: Any, name: str) -> bool:
    for game in getattr(app_state, "games", {}).values():
        if getattr(game, "variant", None) == name and getattr(game, "status", STARTED) <= STARTED:
            return True
    return False
