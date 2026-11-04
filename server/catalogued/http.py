"""HTTP handlers for community catalogue browsing and management."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import aiohttp_session
from aiohttp import web
from const import ANON_PREFIX
from json_utils import json_response
from pychess_global_app_state_utils import get_app_state
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from request_utils import read_json_data, read_post_data, read_text_data
from variants import unregister_catalogued_server_variant

from . import assets, builtin_data, documents, models, repository, validation, variants


async def get_catalogued_variants(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    # Repeated ?name=... parameters let widgets request exactly the variants
    # they encounter. Bound the list to avoid rebuilding the entire catalogue
    # through a large query supplied by an anonymous caller.
    names = request.rel_url.query.getall("name", [])
    if names and (len(names) > 32 or any(not name or len(name) > 100 for name in names)):
        raise web.HTTPBadRequest(text="Invalid catalogued variant names")
    username = await _optional_human_username(request)
    if names:
        user = await app_state.users.get(username) if username is not None else None
        favorite_names = (
            validation._clean_favorite_names(user.catalogued_variant_favorites)
            if user is not None
            else set()
        )
        docs = getattr(app_state, "catalogued_variants", {})
        return json_response(
            {
                "variants": [
                    documents._client_doc(docs[name], favorite_names=favorite_names)
                    for name in dict.fromkeys(names)
                    if name in docs and documents._can_open_catalogued_doc(username, docs[name])
                ]
            }
        )

    # Compatibility for clients running an older JS bundle during deployment.
    # New code never requests this full-catalogue fallback.
    if username is None:
        return web.Response(
            text='{"variants":' + variants.public_catalogued_variants_json(app_state) + "}",
            content_type="application/json",
        )
    user = await app_state.users.get(username)
    return json_response(
        {
            "variants": variants.catalogued_variants_for_client(
                app_state,
                username,
                favorite_names=validation._clean_favorite_names(user.catalogued_variant_favorites),
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
    favorite_names = validation._clean_favorite_names(favorite_names or set())
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

    query = documents._catalogued_public_query()
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

    total = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].count_documents(query)
    pages = max(
        1,
        (total + models.CATALOGUED_COMMUNITY_PAGE_SIZE - 1)
        // models.CATALOGUED_COMMUNITY_PAGE_SIZE,
    )
    page = min(page, pages)
    skip = (page - 1) * models.CATALOGUED_COMMUNITY_PAGE_SIZE

    variants: list[dict[str, Any]] = []
    if use_favorite_sort:
        cursor = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].aggregate(
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
                {"$limit": models.CATALOGUED_COMMUNITY_PAGE_SIZE},
            ]
        )
    else:
        cursor = (
            app_state.db[models.CATALOGUED_VARIANT_COLLECTION]
            .find(query)
            .sort(sort_spec)
            .skip(skip)
            .limit(models.CATALOGUED_COMMUNITY_PAGE_SIZE)
        )
    async for doc in cursor:
        name = str(doc.get("name") or doc.get("_id") or "")
        count = int(doc.get("gameCount") or 0)
        variants.append(
            {
                "name": name,
                "displayName": str(doc.get("displayName") or name),
                "description": documents._catalogued_description(doc),
                "author": str(doc.get("author") or ""),
                "system": documents._is_fsf_builtin_catalogued_doc(doc),
                "references": documents._catalogued_references_for_display(doc),
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
    if not validation._is_valid_variant_name(name):
        raise web.HTTPBadRequest(text=models.VARIANT_NAME_ERROR)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    doc = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one(
        {"_id": name, **documents._catalogued_public_query()},
        projection={"_id": 1, "favoriteCount": 1},
    )
    if doc is None:
        raise web.HTTPNotFound(text="Public catalogued variant not found.")

    data = await read_json_data(request)
    if not isinstance(data, Mapping):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    favorite = bool(data.get("favorite"))

    user = await app_state.users.get(username)
    favorites = validation._clean_favorite_names(
        getattr(user, "catalogued_variant_favorites", set())
    )
    if favorite:
        if name not in favorites and len(favorites) >= models.MAX_CATALOGUED_FAVORITES_PER_USER:
            raise web.HTTPConflict(
                text=f"You can favorite at most {models.MAX_CATALOGUED_FAVORITES_PER_USER} variants."
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
        updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one_and_update(
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
            variants.invalidate_public_catalogued_variants_json(app_state)
    else:
        current = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one(
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
        display_name = validation.normalize_catalogued_display_name(
            str(data.get("displayName") or data.get("display_name") or "")
        )
        description = str(data.get("description") or "")
        piece_names = validation.parse_catalogued_piece_names(
            data.get("pieceNames", data.get("piece_names", ""))
        )
        piece_set_directional = validation._read_bool_metadata(
            data, "pieceSetDirectional", "piece_set_directional"
        )
        piece_family_override = validation._read_piece_family_override(data)
        board_family_override = validation._read_board_family_override(data)
        visibility = validation._clean_visibility(
            str(data.get("visibility") or models.CATALOGUED_VISIBILITY_PRIVATE)
        )
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
        return ini or "", "", "", {}, None, "", "", models.CATALOGUED_VISIBILITY_PRIVATE

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Missing form data.")

    upload = data.get("file") or data.get("ini_file")
    if hasattr(upload, "file"):
        raw = upload.file.read(models.MAX_CATALOGUED_INI_BYTES + 1)
        ini = raw.decode("utf-8", errors="replace")
    else:
        ini = str(data.get("ini") or "")

    display_name = validation.normalize_catalogued_display_name(
        str(data.get("displayName") or data.get("display_name") or "")
    )
    description = str(data.get("description") or "")
    piece_names = validation.parse_catalogued_piece_names(
        data.get("pieceNames", data.get("piece_names", ""))
    )
    piece_set_directional = validation._read_bool_metadata(
        data, "pieceSetDirectional", "piece_set_directional"
    )
    piece_family_override = validation._read_piece_family_override(data)
    board_family_override = validation._read_board_family_override(data)
    visibility = validation._clean_visibility(
        str(data.get("visibility") or models.CATALOGUED_VISIBILITY_PRIVATE)
    )
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

    name = validation.extract_variant_name(ini)
    validation.catalogued_pychess_piece_roles(ini)
    existing = app_state.catalogued_variants.get(current_name) if current_name else None
    if existing is None or validation._strip_pychess_pieces_metadata(
        ini
    ) != validation._strip_pychess_pieces_metadata(str(existing.get("ini") or "")):
        validation._ensure_catalogued_rule_changes(ini)
    await repository.ensure_catalogued_variant_name_available(
        app_state, name, current_name=current_name
    )
    start_fen = await validation.check_catalogued_ini_without_mutating_server(ini, name)
    return json_response({"ok": True, "name": name, "startFen": start_fen})


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
    await repository._ensure_catalogued_variant_quota(app_state, username)
    if not ini:
        raise web.HTTPBadRequest(text="Missing INI content.")

    # Check uniqueness before asking FSF to load the config. load_variant_config()
    # is intentionally global and should not be called for a duplicate upload.
    name = validation.extract_variant_name(ini)
    validation._ensure_catalogued_rule_changes(ini)
    await repository.ensure_catalogued_variant_name_available(app_state, name)
    validation.ensure_catalogued_display_name_available(display_name, variant_name=name)
    await validation.check_catalogued_ini_without_mutating_server(ini, name)

    validated = validation.validate_catalogued_ini(ini)
    name = validated.name

    now = datetime.now(UTC)
    doc = documents._build_doc(
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
        await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].insert_one(doc)
    except DuplicateKeyError as exc:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.") from exc

    variants.register_catalogued_variant_doc(app_state, doc, load_config=False)
    await repository._refresh_catalogued_variant_profile_count(app_state, username)
    return json_response({"ok": True, "variant": documents._client_doc(doc, game_count=0)})


async def upload_catalogued_piece_set(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if not documents._is_active_catalogued_doc(doc):
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

    paired_keys = assets._catalogued_piece_set_required_keys(doc)
    if not paired_keys:
        raise web.HTTPBadRequest(text="This variant has no renderable piece roles.")

    piece_set: dict[str, models.CataloguedVariantPieceSetSvg] = {}
    total_size = 0
    for upload in uploads:
        filename = str(getattr(upload, "filename", "") or "").strip()
        if not filename:
            raise web.HTTPBadRequest(text="Every uploaded file must have a filename.")
        canonical = assets._canonical_piece_set_filename(filename)
        if canonical is None:
            raise web.HTTPBadRequest(
                text="Piece SVG filenames must look like wP.svg, bP.svg, w+P.svg, or b+P.svg."
            )
        key = assets._catalogued_piece_set_storage_key(canonical)
        if key in piece_set:
            raise web.HTTPBadRequest(text=f"Duplicate piece SVG: {canonical}.")
        if key not in paired_keys:
            raise web.HTTPBadRequest(text=f"Unexpected piece SVG: {canonical}.")
        if not hasattr(upload, "file"):
            raise web.HTTPBadRequest(text=f"{canonical} is not a file upload.")

        raw = upload.file.read(models.MAX_CATALOGUED_PIECE_SVG_BYTES + 1)
        total_size += len(raw)
        if total_size > models.MAX_CATALOGUED_PIECE_SET_TOTAL_BYTES:
            raise web.HTTPBadRequest(
                text=(
                    "The piece set is too large. "
                    f"All SVGs together must be at most "
                    f"{models.MAX_CATALOGUED_PIECE_SET_TOTAL_BYTES // 1024} KiB."
                )
            )
        svg = assets._sanitize_catalogued_piece_svg(raw, canonical)
        piece_set[key] = {"svg": svg, "size": len(svg.encode("utf-8"))}

    uploaded = set(piece_set)
    if assets._catalogued_piece_set_mode_for_keys(doc, uploaded) is None:
        if assets._catalogued_piece_set_is_directional(doc):
            raise web.HTTPBadRequest(
                text=(
                    "Directional custom piece sets must be either one complete color "
                    "(all white or all black SVGs) or a complete white/black pair."
                )
            )
        missing = ", ".join(
            assets._catalogued_piece_set_public_filename(key)
            for key in sorted(paired_keys - uploaded)
        )
        extra = ", ".join(
            assets._catalogued_piece_set_public_filename(key)
            for key in sorted(uploaded - paired_keys)
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
    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"pieceSet": piece_set, "pieceSetUpdatedAt": now, "updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    variants.invalidate_public_catalogued_variants_json(app_state)
    count = await repository._game_count(app_state, name)
    return json_response({"ok": True, "variant": documents._client_doc(updated, game_count=count)})


async def delete_catalogued_piece_set(request: web.Request) -> web.Response:
    app_state, _username, name, _doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    now = datetime.now(UTC)
    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$unset": {"pieceSet": "", "pieceSetUpdatedAt": ""}, "$set": {"updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    variants.invalidate_public_catalogued_variants_json(app_state)
    count = await repository._game_count(app_state, name)
    return json_response({"ok": True, "variant": documents._client_doc(updated, game_count=count)})


async def upload_catalogued_board(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if not documents._is_active_catalogued_doc(doc):
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

    raw = upload.file.read(models.MAX_CATALOGUED_BOARD_SVG_BYTES + 1)
    svg = assets._sanitize_catalogued_board_svg(
        raw, filename, int(doc["width"]), int(doc["height"])
    )
    board_svg: models.CataloguedVariantBoardSvg = {"svg": svg, "size": len(svg.encode("utf-8"))}

    now = datetime.now(UTC)
    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"boardSvg": board_svg, "boardSvgUpdatedAt": now, "updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    variants.invalidate_public_catalogued_variants_json(app_state)
    count = await repository._game_count(app_state, name)
    return json_response({"ok": True, "variant": documents._client_doc(updated, game_count=count)})


async def delete_catalogued_board(request: web.Request) -> web.Response:
    app_state, _username, name, _doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")

    now = datetime.now(UTC)
    result = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$unset": {"boardSvg": "", "boardSvgUpdatedAt": ""}, "$set": {"updatedAt": now}},
    )
    if result.matched_count != 1:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if updated is None:
        raise web.HTTPNotFound(text="Catalogued variant not found after update.")
    app_state.catalogued_variants[name] = updated
    variants.invalidate_public_catalogued_variants_json(app_state)
    count = await repository._game_count(app_state, name)
    return json_response({"ok": True, "variant": documents._client_doc(updated, game_count=count)})


async def get_catalogued_board_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await repository.find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    board_svg = doc.get("boardSvg")
    if not isinstance(board_svg, Mapping) or not assets._has_board_svg(doc):
        raise web.HTTPNotFound(text="This variant has no custom board.")

    return web.Response(
        text=assets._catalogued_board_svg_css(str(doc["name"]), board_svg),
        content_type="text/css",
        headers={"Cache-Control": "private, max-age=300"},
    )


async def get_catalogued_piece_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await repository.find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    piece_set = doc.get("pieceSet")
    if not isinstance(piece_set, Mapping) or not assets._has_complete_piece_set(doc):
        raise web.HTTPNotFound(text="This variant has no complete custom piece set.")

    return web.Response(
        text=assets._catalogued_piece_set_css(
            str(doc["name"]),
            piece_set,
            directional=assets._catalogued_piece_set_is_directional(doc),
        ),
        content_type="text/css",
        headers={"Cache-Control": "private, max-age=300"},
    )


async def get_catalogued_disguised_piece_css(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _optional_human_username(request)
    name = request.match_info["name"]
    doc = await repository.find_catalogued_variant_doc(app_state, name, username)
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")

    return web.Response(
        text=assets._catalogued_disguised_piece_css(str(doc["name"])),
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
    admin = documents._is_admin_username(username)
    params = request.rel_url.query

    q = params.get("q", "").strip()[:80] if admin else ""
    if admin and "author" in params:
        author = params.get("author", "").strip()[:40]
    elif admin and params.get("scope") == "fsf":
        author = models.CATALOGUED_FSF_BUILTIN_AUTHOR
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
    variants: list[models.CataloguedVariantClientDocument] = []
    if app_state.db is not None:
        collection = app_state.db[models.CATALOGUED_VARIANT_COLLECTION]
        total = await collection.count_documents(query)
        pages = max(
            1,
            (total + models.CATALOGUED_MANAGEMENT_PAGE_SIZE - 1)
            // models.CATALOGUED_MANAGEMENT_PAGE_SIZE,
        )
        page = min(page, pages)
        skip = (page - 1) * models.CATALOGUED_MANAGEMENT_PAGE_SIZE
        cursor = (
            collection.find(query)
            .sort(sort_spec)
            .skip(skip)
            .limit(models.CATALOGUED_MANAGEMENT_PAGE_SIZE)
        )
        async for doc in cursor:
            count = await repository._game_count(app_state, str(doc["name"]))
            variants.append(documents._client_doc(doc, game_count=count))

    max_variants = None if admin else models.MAX_CATALOGUED_VARIANTS_PER_USER
    variant_slots_used = None
    if not admin:
        variant_slots_used = await repository._catalogued_variant_slot_count_for_user(
            app_state, username
        )
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

    doc = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one({"_id": name})
    if doc is None:
        raise web.HTTPNotFound(text="Catalogued variant not found.")
    if not documents._can_modify(username, doc):
        raise web.HTTPForbidden(text="You can only manage your own catalogued variants.")

    return app_state, username, name, doc


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
    if documents._is_fsf_builtin_catalogued_doc(existing):
        now = datetime.now(UTC)
        cleaned_description = validation._clean_description(description)
        update: dict[str, Any] = {
            "$set": {
                "displayName": validation._clean_display_name(display_name, old_name),
                "visibility": visibility,
                "pieceSetDirectional": piece_set_directional,
                "updatedAt": now,
            }
        }
        unset_fields: dict[str, str] = {}
        metadata = builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS.get(
            documents._fsf_builtin_variant_name(existing), {}
        )
        references = documents._clean_catalogued_references(existing.get("references"))
        if documents._fsf_builtin_description_is_auto(cleaned_description, metadata, references):
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
            validation._ensure_board_family_dimensions(
                board_family_override,
                int(existing.get("width") or 8),
                int(existing.get("height") or 8),
            )
            update["$set"]["boardFamilyOverride"] = board_family_override
        else:
            unset_fields["boardFamilyOverride"] = ""
        if unset_fields:
            update["$unset"] = unset_fields
        await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
            {"_id": old_name}, update
        )
        updated = await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].find_one(
            {"_id": old_name}
        )
        if updated is None:
            raise web.HTTPNotFound(text="Catalogued variant not found after update.")
        variants.register_catalogued_variant_doc(app_state, updated, load_config=False)
        await repository._refresh_catalogued_variant_profile_count(
            app_state, str(updated.get("author") or existing.get("author") or "")
        )
        count = await repository._game_count(app_state, old_name)
        return json_response(
            {
                "ok": True,
                "oldName": old_name,
                "variant": documents._client_doc(updated, game_count=count),
            }
        )

    if not ini:
        raise web.HTTPBadRequest(text="Missing INI content.")

    new_name = validation.extract_variant_name(ini)
    validation.ensure_catalogued_display_name_available(
        display_name,
        variant_name=new_name,
        current_display_name=str(existing.get("displayName") or ""),
        current_variant_name=old_name,
    )
    existing_ini = str(existing.get("ini") or "")
    fsf_rules_changed = validation._strip_pychess_pieces_metadata(
        ini
    ) != validation._strip_pychess_pieces_metadata(existing_ini)
    if fsf_rules_changed or new_name != old_name:
        validation._ensure_catalogued_rule_changes(ini)
    if (fsf_rules_changed or new_name != old_name) and await repository._has_games(
        app_state, old_name
    ):
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
        await repository.ensure_catalogued_variant_name_available(
            app_state, new_name, current_name=old_name
        )

    if fsf_rules_changed or new_name != old_name:
        await validation.check_catalogued_ini_without_mutating_server(ini, new_name)
        validated = validation.validate_catalogued_ini(ini)
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
        base_variant = str(existing.get("baseVariant") or validation.extract_variant_base_name(ini))
        start_fen = str(existing["startFen"])
        width = int(existing["width"])
        height = int(existing["height"])
        pieces = validation._catalogued_piece_roles_from_ini(ini, start_fen)
        king_roles = validation.catalogued_king_roles(ini, pieces)
        capture_to_hand = validation._ini_bool(ini, "capturesToHand", default=False)
        pocket_roles = validation.catalogued_pocket_roles(
            ini, start_fen, pieces, king_roles, capture_to_hand=capture_to_hand
        )
        promotion_type = validation.catalogued_promotion_type(ini)
        promotion_roles = validation.catalogued_promotion_roles(ini, pieces)
        promotion_order = validation.catalogued_promotion_order(ini, promotion_type)
        show_promoted = validation.catalogued_show_promoted(ini, start_fen)
        rules_gate = validation.catalogued_rules_gate(ini)
        rules_pass = validation.catalogued_rules_pass(ini)
        legal_moves_need_history = validation.catalogued_legal_moves_need_history(ini)
        n_fold_is_draw = validation.catalogued_n_fold_is_draw(ini)
        show_check_counters = validation.catalogued_show_check_counters(ini)

    doc = documents._build_doc(
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

    assets._copy_catalogued_uploaded_assets(doc, existing)

    if new_name != old_name:
        await repository._rename_catalogued_variant_document(
            app_state.db[models.CATALOGUED_VARIANT_COLLECTION],
            app_state.db[models.CATALOGUED_VARIANT_NAME_COLLECTION],
            old_name=old_name,
            new_name=new_name,
            existing=existing,
            doc=doc,
        )
        await repository._rename_catalogued_variant_favorites(app_state, old_name, new_name)
        await repository._remove_catalogued_variant_seeks(app_state, old_name)
        unregister_catalogued_server_variant(old_name)
        app_state.catalogued_variants.pop(old_name, None)
        variants.invalidate_public_catalogued_variants_json(app_state)
        updated = doc
    else:
        updated = await repository._update_catalogued_variant_document(
            app_state.db[models.CATALOGUED_VARIANT_COLLECTION],
            name=new_name,
            existing=existing,
            doc=doc,
        )

    variants.register_catalogued_variant_doc(app_state, updated, load_config=False)
    if new_name != old_name:
        await repository._migrate_catalogued_variant_tournaments(
            app_state, old_name, new_name, updated
        )
    await repository._refresh_catalogued_variant_profile_count(
        app_state, str(updated.get("author") or existing.get("author") or "")
    )
    count = await repository._game_count(app_state, new_name)
    return json_response(
        {
            "ok": True,
            "oldName": old_name,
            "variant": documents._client_doc(updated, game_count=count),
        }
    )


async def delete_catalogued_variant(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    if documents._is_fsf_builtin_catalogued_doc(doc):
        raise web.HTTPConflict(text="Fairy-Stockfish built-in catalogue entries cannot be deleted.")
    if variants._has_active_catalogued_games(app_state, name):
        raise web.HTTPConflict(
            text=(
                "This variant still has an active game. "
                "Finish or abort it before deleting the variant."
            )
        )
    if await repository._has_games(app_state, name):
        raise web.HTTPConflict(
            text="This variant already has saved public games. Archive it instead of deleting it."
        )

    await repository._remove_catalogued_variant_tournaments(app_state, name)
    await repository._reserve_catalogued_variant_name(
        app_state.db[models.CATALOGUED_VARIANT_NAME_COLLECTION], name, doc
    )
    await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].delete_one({"_id": name})
    await repository._remove_catalogued_variant_favorites(app_state, name)
    await repository._remove_catalogued_variant_seeks(app_state, name)
    app_state.catalogued_variants.pop(name, None)
    variants.invalidate_public_catalogued_variants_json(app_state)
    unregister_catalogued_server_variant(name)
    await repository._refresh_catalogued_variant_profile_count(
        app_state, str(doc.get("author") or "")
    )
    return json_response({"ok": True, "deleted": name})


async def archive_catalogued_variant(request: web.Request) -> web.Response:
    app_state, _username, name, doc = await _load_owned_doc(request)
    await repository._snapshot_catalogued_variant_tournaments(app_state, name, doc)
    now = datetime.now(UTC)
    await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"archived": True, "enabled": False, "updatedAt": now}},
    )
    await repository._remove_catalogued_variant_seeks(app_state, name)
    app_state.catalogued_variants.pop(name, None)
    variants.invalidate_public_catalogued_variants_json(app_state)
    unregister_catalogued_server_variant(name)
    await repository._refresh_catalogued_variant_profile_count(
        app_state, str(doc.get("author") or "")
    )
    return json_response({"ok": True, "archived": name})


async def restore_catalogued_variant(request: web.Request) -> web.Response:
    app_state, username, name, doc = await _load_owned_doc(request)
    if bool(doc.get("archived", False)):
        await repository._ensure_catalogued_variant_quota(app_state, username)
    now = datetime.now(UTC)
    restored = dict(doc)
    restored["archived"] = False
    restored["enabled"] = True
    restored["updatedAt"] = now

    await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].update_one(
        {"_id": name},
        {"$set": {"archived": False, "enabled": True, "updatedAt": now}},
    )
    variants.register_catalogued_variant_doc(app_state, restored, load_config=True)
    await repository._refresh_catalogued_variant_profile_count(
        app_state, str(doc.get("author") or "")
    )
    count = await repository._game_count(app_state, name)
    return json_response({"ok": True, "variant": documents._client_doc(restored, game_count=count)})


async def clone_catalogued_variant(request: web.Request) -> web.Response:
    app_state, username, name, doc = await _load_owned_doc(request)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database is unavailable.")
    if documents._is_fsf_builtin_catalogued_doc(doc):
        raise web.HTTPConflict(text="Fairy-Stockfish built-in catalogue entries cannot be cloned.")

    validation._ensure_catalogued_rule_changes(str(doc["ini"]))
    await repository._ensure_catalogued_variant_quota(app_state, username)

    for n in range(2, 100):
        suffix = f"_v{n}"
        candidate = f"{name[: 32 - len(suffix)]}{suffix}"
        try:
            await repository.ensure_catalogued_variant_name_available(app_state, candidate)
        except web.HTTPConflict:
            continue
        new_name = candidate
        break
    else:
        raise web.HTTPConflict(text="Could not find a free variant name for the clone.")

    ini = validation.replace_variant_section_name(str(doc["ini"]), new_name)
    await validation.check_catalogued_ini_without_mutating_server(ini, new_name)
    validated = validation.validate_catalogued_ini(ini)
    new_name = validated.name

    now = datetime.now(UTC)
    display_name = f"{doc.get('displayName') or name} v{new_name.rsplit('_v', 1)[-1]}"
    cloned = documents._build_doc(
        name=new_name,
        base_variant=validated.base_variant,
        display_name=display_name,
        description=str(doc.get("description") or ""),
        piece_names=validation.parse_catalogued_piece_names(doc.get("pieceNames")),
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
        piece_family_override=validation._catalogued_piece_family_override(doc),
        board_family_override=validation._catalogued_board_family_override(doc),
    )

    try:
        await app_state.db[models.CATALOGUED_VARIANT_COLLECTION].insert_one(cloned)
    except DuplicateKeyError as exc:
        raise web.HTTPConflict(text="A catalogued variant with this name already exists.") from exc

    variants.register_catalogued_variant_doc(app_state, cloned, load_config=False)
    await repository._refresh_catalogued_variant_profile_count(app_state, username)
    return json_response({"ok": True, "variant": documents._client_doc(cloned, game_count=0)})
