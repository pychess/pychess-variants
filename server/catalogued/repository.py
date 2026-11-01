"""Catalogue database operations, counters, and historical references."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from aiohttp import web
from const import T_STARTED
from pymongo.errors import DuplicateKeyError
from variants import CATALOGUED_VARIANTS, get_server_variant

from . import builtin_data, documents, models, validation

log = logging.getLogger(__name__)


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
    if validation._is_builtin_variant_name(name):
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

    existing = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one(
        {"_id": name}, projection={"_id": 1}
    )
    if existing is not None:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.")

    reserved = await app_state.db[models.CATALOGUED_VARIANT_NAME_COLLECTION].find_one(
        {"_id": name}, projection={"_id": 1}
    )
    if reserved is not None:
        raise web.HTTPConflict(
            text="This variant name was used previously and cannot be reused with different rules."
        )


async def find_catalogued_variant_doc(
    app_state: Any,
    name: str,
    username: str | None = None,
) -> Mapping[str, Any] | None:
    docs = getattr(app_state, "catalogued_variants", {})
    doc = docs.get(name)
    if doc is None and app_state.db is not None:
        doc = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        return None
    if documents._can_open_catalogued_doc(
        username, doc
    ) or documents._is_active_catalogued_game_participant(app_state, name, username):
        return doc
    return None


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
    disabled = failure_count >= models.CATALOGUED_AI_FAILURE_LIMIT
    if disabled:
        update_set.update(
            {
                "aiDisabledAt": now,
                "aiDisabledUntil": now + timedelta(seconds=models.CATALOGUED_AI_DISABLE_SECONDS),
                "aiDisabledReason": reason,
            }
        )

    if getattr(app_state, "db", None) is not None:
        try:
            await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
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
            await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
                {"_id": name}, {"$unset": {field: "" for field in fields}}
            )
        except Exception:
            log.exception("Failed to clear catalogued variant AI failure fields for %s", name)

    for field in fields:
        doc.pop(field, None)


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
            "source": models.CATALOGUED_SOURCE_FSF_BUILTIN,
            "description": builtin_data.FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        },
        {"$unset": {"description": ""}},
    )
    if result.modified_count:
        log.info(
            "Removed legacy default description from %d Fairy-Stockfish built-ins",
            result.modified_count,
        )


async def _game_count(app_state: Any, name: str) -> int:
    if app_state.db is None:
        return 0
    return await app_state.db.game.count_documents({"v": name})


async def _has_games(app_state: Any, name: str) -> bool:
    if app_state.db is None:
        return False
    return await app_state.db.game.find_one({"v": name}, projection={"_id": 1}) is not None


async def increment_catalogued_variant_game_count(app_state: Any, name: str) -> None:
    """Increment the stored played-game counter for a saved catalogued game."""

    if app_state.db is None or not validation._is_valid_variant_name(name):
        return

    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
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

    if app_state.db is None or not validation._is_valid_variant_name(name):
        return

    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
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
    return await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].count_documents(
        {"author": username, "archived": {"$ne": True}}
    )


async def _refresh_catalogued_variant_profile_count(app_state: Any, username: str) -> None:
    if not username or _catalogued_variant_user_collection(app_state) is None:
        return
    from profile_counts import refresh_user_counter

    await refresh_user_counter(app_state, username, "variantCount")


async def _ensure_catalogued_variant_quota(app_state: Any, username: str) -> None:
    if documents._is_admin_username(username):
        return
    count = await _catalogued_variant_slot_count_for_user(app_state, username)
    if count >= models.MAX_CATALOGUED_VARIANTS_PER_USER:
        raise web.HTTPConflict(
            text=(
                f"You can have at most {models.MAX_CATALOGUED_VARIANTS_PER_USER} user-defined variants. "
                "Archive or delete an active variant before uploading, cloning, or restoring "
                "another one."
            )
        )


async def ensure_fsf_catalogued_builtin_variants(app_state: Any) -> None:
    if app_state.db is None:
        return

    collection = app_state.db[models.CATALOGUED_VARIANT_COLLECTION]
    if builtin_data.FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS:
        await collection.update_many(
            {
                "_id": {"$in": sorted(builtin_data.FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS)},
                "source": models.CATALOGUED_SOURCE_FSF_BUILTIN,
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

    for name, metadata in builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS.items():
        if name not in builtin_data.BUILTIN_FSF_VARIANT_NAMES:
            log.warning(
                "Skipped FSF catalogued built-in %s: Fairy-Stockfish does not know it", name
            )
            continue

        existing = await collection.find_one({"_id": name})
        if existing is not None and not documents._is_fsf_builtin_catalogued_doc(existing):
            log.warning(
                "Skipped FSF catalogued built-in %s: a non-system catalogued variant already uses that key",
                name,
            )
            continue

        try:
            doc = documents._build_fsf_builtin_doc(name, metadata, existing=existing)
        except Exception:
            log.exception("Failed to prepare FSF catalogued built-in %s", name)
            continue

        if existing is None:
            try:
                await collection.insert_one(doc)
            except DuplicateKeyError:
                log.warning("Skipped FSF catalogued built-in %s: duplicate key", name)
            continue

        synced_fields = documents._fsf_builtin_synced_fields(doc)
        existing_description = str(existing.get("description") or "")
        references = documents._clean_catalogued_references(doc.get("references"))

        update: dict[str, Any] = {"$set": synced_fields}
        unset_fields = {
            field: ""
            for field in ("clientVariant", "premoveVariant")
            if field in existing and field not in doc
        }
        if documents._fsf_builtin_description_is_auto(existing_description, metadata, references):
            unset_fields["description"] = ""
        if unset_fields:
            update["$unset"] = unset_fields
        await collection.update_one(
            {"_id": name},
            update,
        )


def _catalogued_same_name_update(
    doc: Mapping[str, Any], existing: Mapping[str, Any]
) -> dict[str, Any]:
    """Build a non-destructive update for user-editable and derived fields."""
    set_fields = {
        key: value
        for key, value in doc.items()
        if key not in models.CATALOGUED_CONCURRENTLY_UPDATED_FIELDS
    }
    update: dict[str, Any] = {"$set": set_fields}
    unset_fields = {
        field: ""
        for field in models.CATALOGUED_METADATA_OPTIONAL_FIELDS
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
    doc: models.CataloguedVariantDocument,
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
    doc: models.CataloguedVariantDocument,
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
