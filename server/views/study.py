from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, cast

import aiohttp_jinja2
import aiohttp_session
import settings
from aiohttp import web
from catalogued_variants import catalogued_variant_client_doc_for_name
from fairy import BLACK, FairyBoard
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from request_utils import read_json_data, read_post_data
from study.analysis import has_pending_study_analysis
from study.builder import (
    StudyChapterBuilder,
    StudyChapterBuildError,
    StudyChapterDraft,
    StudyOrientation,
)
from study.constants import (
    STUDY_CLONE_CREATION_COST,
    STUDY_MAX_MEMBERS,
    STUDY_MAX_TOPICS,
    STUDY_PREVIEW_NB_MEMBERS,
    STUDY_TOPIC_MAX_LENGTH,
    STUDY_TOPIC_MIN_LENGTH,
)
from study.models import (
    Study,
    StudyChapter,
    StudyChapterMode,
    StudyVisibility,
    study_chapter_mode,
    study_chapter_mode_enabled,
    study_enabled_chapter_modes,
    study_topic,
    study_user_selection,
    study_visibility,
)
from study.permissions import (
    can_clone_study,
    can_embed_study,
    can_share_study,
    can_use_study_computer,
    can_use_study_explorer,
    can_view_study,
    can_write_study,
    is_study_owner,
    study_feature_selection,
)
from study.quota import (
    StudyQuotaExceeded,
    claim_study_creation_slot,
    release_study_creation_slot,
)
from study.sequencer import sequence_study
from study.snapshot import chapter_snapshot_token, study_snapshot_token
from study.storage import (
    StudyStorageError,
    add_chapter_from_draft,
    add_chapters_from_drafts,
    add_study_member,
    autocomplete_study_topics,
    chapter_previews,
    clear_chapter_annotations,
    clear_chapter_variations,
    clone_study,
    contributed_studies_page,
    create_study_from_draft,
    create_study_from_drafts,
    delete_chapter,
    delete_study,
    edit_chapter_metadata,
    favorite_studies_page,
    leave_study,
    load_chapter,
    load_owned_chapter,
    load_owned_study,
    load_study,
    member_study_topics,
    owner_studies_page,
    popular_study_topics,
    public_studies_page,
    remove_study_member,
    rename_study,
    set_study_feature_settings,
    set_study_like,
    set_study_member_role,
    set_study_topics,
    set_study_visibility,
    studies_for_owner_view,
    studies_writable_by,
    study_list_chapter_names,
    study_list_order,
    study_search_page,
    topic_studies_page,
)
from study.variant import (
    StudyVariantCapacityError,
    study_variant_client_doc,
    study_variant_context,
    study_variant_metadata,
)
from study.ws import (
    broadcast_study_chapter_content,
    broadcast_study_chapters,
    broadcast_study_likes,
    broadcast_study_members,
    broadcast_study_position,
    broadcast_study_reload,
    broadcast_study_topics,
    close_study_sockets,
)
from typing_defs import ViewContext
from utils import USERNAME_PREFIX_RE
from variants import ALL_VARIANTS, is_catalogued_variant

from views import get_user_context


def _require_owner_user(user: Any) -> None:
    if user.anon:
        raise web.HTTPFound("/login")
    if user.bot:
        raise web.HTTPForbidden(text="BOT accounts cannot use Studies.")


def _study_quota_http_error(exc: StudyQuotaExceeded) -> web.HTTPException:
    if exc.code == "account_missing":
        return web.HTTPForbidden(text=str(exc))
    return web.HTTPTooManyRequests(
        text=str(exc),
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


def _study_sync_enabled(value: object, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
    raise StudyStorageError("Invalid Study SYNC mode")


def _study_creation_metadata(
    data: Mapping[str, object],
) -> tuple[str, StudyVisibility, dict[str, object]]:
    try:
        visibility = study_visibility(data.get("visibility", "private"))
        settings = {
            feature: study_user_selection(data.get(feature, "everyone"))
            for feature in ("computer", "explorer", "cloneable", "shareable")
        }
    except ValueError as exc:
        raise StudyStorageError("Invalid Study settings") from exc
    name = str(data.get("name") or "").strip()
    return name, visibility, settings


def _study_context(context: ViewContext) -> None:
    context["view_css"] = "study.css"
    context["title"] = "Studies • PyChess"
    context["study_preview_nb_members"] = STUDY_PREVIEW_NB_MEMBERS
    context["study_enabled_modes"] = json_dumps(list(study_enabled_chapter_modes()))


def _positive_page(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


_STUDY_ORDER_LABELS = {
    "updated": "Recently updated",
    "newest": "Date added (newest)",
    "oldest": "Date added (oldest)",
    "alphabetical": "Alphabetical",
}


def _study_list_query_href(
    request: web.Request, *, order: str | None = None, page: object = None
) -> str:
    query = dict(request.rel_url.query)
    if order is not None:
        query["order"] = order
        query.pop("page", None)
    if isinstance(page, int):
        query["page"] = str(page)
    elif page is not None:
        query.pop("page", None)
    return str(request.rel_url.with_query(query))


def _populate_study_list_navigation(context: ViewContext, *, active: str) -> None:
    context["study_list_navigation"] = True
    context["study_list_active"] = active


async def _populate_study_navigation_topics(
    context: ViewContext,
    app_state: Any,
    username: str | None,
) -> None:
    context["study_nav_topics"] = await member_study_topics(app_state, username) if username else []


def _populate_study_search_form(
    context: ViewContext,
    value: str = "",
    *,
    clear_href: str = "",
) -> None:
    context["study_search_value"] = value
    context["study_search_clear_href"] = clear_href


def _populate_study_page(
    context: ViewContext,
    request: web.Request,
    result: Mapping[str, object],
    *,
    active: str,
) -> None:
    order = study_list_order(result.get("order"))
    context["studies"] = result["studies"]
    context["study_card_chapters"] = result.get("chapter_names", {})
    context["study_page"] = result
    context["study_list_order"] = order
    context["study_list_order_label"] = _STUDY_ORDER_LABELS[order]
    context["study_order_hrefs"] = {
        key: _study_list_query_href(request, order=key) for key in _STUDY_ORDER_LABELS
    }
    context["study_prev_href"] = (
        _study_list_query_href(request, page=result.get("prev_page"))
        if isinstance(result.get("prev_page"), int)
        else ""
    )
    context["study_next_href"] = (
        _study_list_query_href(request, page=result.get("next_page"))
        if isinstance(result.get("next_page"), int)
        else ""
    )
    _populate_study_list_navigation(context, active=active)


async def _owned_study_and_chapter(
    request: web.Request,
) -> tuple[Any, ViewContext, Study, StudyChapter]:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    study_id = request.match_info["studyId"]
    study = await load_owned_study(app_state, study_id, user.username)
    if study is None:
        raise web.HTTPNotFound()

    requested_chapter_id = request.match_info.get("chapterId")
    chapter_id = requested_chapter_id or study.current_chapter
    chapter = None
    if chapter_id:
        chapter = await load_owned_chapter(app_state, study.id, chapter_id, user.username)
    if requested_chapter_id and chapter is None:
        raise web.HTTPNotFound()
    if chapter is None:
        doc = await app_state.db.study_chapter.find_one(
            {"studyId": study.id, "owner": user.username}, sort=[("order", 1)]
        )
        if doc is None:
            raise web.HTTPNotFound(text="Study has no chapters")
        chapter = StudyChapter.from_document(doc)
    return user, context, study, chapter


async def _writable_study_and_chapter(
    request: web.Request,
) -> tuple[Any, ViewContext, Study, StudyChapter]:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    study = await load_study(app_state, request.match_info["studyId"])
    if study is None or not can_view_study(study, user.username):
        raise web.HTTPNotFound()
    if not can_write_study(study, user.username):
        raise web.HTTPForbidden(text="You cannot edit this Study.")

    requested_chapter_id = request.match_info.get("chapterId")
    chapter_id = requested_chapter_id or study.current_chapter
    chapter = await load_chapter(app_state, study.id, chapter_id) if chapter_id else None
    if requested_chapter_id and chapter is None:
        raise web.HTTPNotFound()
    if chapter is None:
        doc = await app_state.db.study_chapter.find_one({"studyId": study.id}, sort=[("order", 1)])
        if doc is None:
            raise web.HTTPNotFound(text="Study has no chapters")
        chapter = StudyChapter.from_document(doc)
    return user, context, study, chapter


@asynccontextmanager
async def _sequenced_writable_study_and_chapter(
    request: web.Request,
) -> AsyncIterator[tuple[Any, ViewContext, Study, StudyChapter]]:
    """Load authoritative writable Study/chapter state under its mutation sequencer."""

    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    study_id = request.match_info["studyId"]
    async with sequence_study(app_state, study_id):
        study = await load_study(app_state, study_id)
        if study is None or not can_view_study(study, user.username):
            raise web.HTTPNotFound()
        if not can_write_study(study, user.username):
            raise web.HTTPForbidden(text="You cannot edit this Study.")

        requested_chapter_id = request.match_info.get("chapterId")
        chapter_id = requested_chapter_id or study.current_chapter
        chapter = await load_chapter(app_state, study.id, chapter_id) if chapter_id else None
        if requested_chapter_id and chapter is None:
            raise web.HTTPNotFound()
        if chapter is None:
            doc = await app_state.db.study_chapter.find_one(
                {"studyId": study.id}, sort=[("order", 1)]
            )
            if doc is None:
                raise web.HTTPNotFound(text="Study has no chapters")
            chapter = StudyChapter.from_document(doc)
        yield user, context, study, chapter


async def _viewable_study_and_chapter(
    request: web.Request,
) -> tuple[Any, ViewContext, Study, StudyChapter]:
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    study_id = request.match_info["studyId"]
    study = await load_study(app_state, study_id)
    if study is None:
        raise web.HTTPNotFound()

    # Authorize from the session before materializing an anonymous user. This keeps
    # private Study probes as cheap as the websocket authorization path.
    session = await aiohttp_session.get_session(request)
    session_username = session.get("user_name")
    viewer = session_username if isinstance(session_username, str) else None
    if not can_view_study(study, viewer):
        raise web.HTTPNotFound()

    user, context = await get_user_context(request)
    requested_chapter_id = request.match_info.get("chapterId")
    chapter_id = requested_chapter_id or study.current_chapter
    chapter = await load_chapter(app_state, study.id, chapter_id) if chapter_id else None
    if requested_chapter_id and chapter is None:
        raise web.HTTPNotFound()
    if chapter is None:
        doc = await app_state.db.study_chapter.find_one({"studyId": study.id}, sort=[("order", 1)])
        if doc is None:
            raise web.HTTPNotFound(text="Study has no chapters")
        chapter = StudyChapter.from_document(doc)
    return user, context, study, chapter


def _form_bool(value: object) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _chapter_teaching_from_input(
    data: Mapping[str, object],
    *,
    default_mode: StudyChapterMode = "normal",
) -> tuple[StudyChapterMode, int | None]:
    try:
        mode = study_chapter_mode(data.get("mode", default_mode))
    except ValueError as exc:
        raise StudyChapterBuildError("Invalid Study chapter mode") from exc
    if not study_chapter_mode_enabled(mode):
        raise StudyChapterBuildError("Study chapter mode is not enabled")
    raw_conceal_ply = data.get("concealPly")
    if raw_conceal_ply is None or raw_conceal_ply == "":
        return mode, None
    if isinstance(raw_conceal_ply, bool):
        raise StudyChapterBuildError("Invalid Study conceal boundary")
    try:
        conceal_ply = int(raw_conceal_ply)
    except (TypeError, ValueError) as exc:
        raise StudyChapterBuildError("Invalid Study conceal boundary") from exc
    if str(conceal_ply) != str(raw_conceal_ply).strip():
        raise StudyChapterBuildError("Invalid Study conceal boundary")
    return mode, conceal_ply


async def _draft_from_form(
    builder: StudyChapterBuilder,
    data: Any,
    *,
    fallback_variant: str = "chess",
    fallback_chess960: bool = False,
) -> StudyChapterDraft:
    mode, conceal_ply = _chapter_teaching_from_input(data)
    game_id = str(data.get("gameId") or "").strip()
    chapter_name = str(data.get("chapterName") or "").strip() or None
    if game_id:
        return await builder.from_game(
            game_id,
            name=chapter_name,
            mode=mode,
            conceal_ply=conceal_ply,
        )

    raw_variant = data.get("variant")
    variant = str(raw_variant or fallback_variant).strip() or fallback_variant
    fen = str(data.get("fen") or "").strip() or None
    raw_chess960 = data.get("chess960")
    if raw_chess960 is not None:
        chess960 = _form_bool(raw_chess960)
    elif raw_variant is None:
        chess960 = fallback_chess960
    else:
        chess960 = False
    orientation = "black" if str(data.get("orientation") or "").lower() == "black" else "white"
    return await builder.blank_or_fen(
        variant=variant,
        fen=fen,
        chess960=chess960,
        name=chapter_name,
        orientation=orientation,
        mode=mode,
        conceal_ply=conceal_ply,
    )


def _study_board(chapter: StudyChapter, *, runtime_variant: str | None = None) -> dict[str, object]:
    board = FairyBoard(runtime_variant or chapter.variant, chapter.initial_fen, chapter.chess960)
    turn_color = "black" if board.color == BLACK else "white"
    return {
        "gameId": "",
        "fen": chapter.initial_fen,
        "ply": 0,
        "lastMove": "",
        "bikjang": False,
        "check": False,
        "by": "",
        "status": 0,
        "pgn": "",
        "tp": "",
        "uci_usi": "",
        "result": "*",
        "steps": [
            {
                "fen": chapter.initial_fen,
                "check": False,
                "turnColor": turn_color,
            }
        ],
        "berserk": {"w": False, "b": False},
    }


def _chapter_export_payload(chapter: StudyChapter) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": chapter.id,
        "name": chapter.name,
        "order": chapter.order,
        "variant": chapter.variant,
        "chess960": chapter.chess960,
        "initialFen": chapter.initial_fen,
        "orientation": chapter.orientation,
        "mode": chapter.mode,
        "description": "" if chapter.description == "-" else chapter.description,
        "tags": dict(chapter.tags),
        "createdAt": chapter.created_at.isoformat(),
        "tree": chapter.root.to_payload(),
    }
    if chapter.variant_ini is not None:
        payload["variantIni"] = chapter.variant_ini
    if chapter.conceal_ply is not None:
        payload["concealPly"] = chapter.conceal_ply
    return payload


@aiohttp_jinja2.template("studies.html")
async def studies(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    order = study_list_order(request.rel_url.query.get("order"))
    result = await owner_studies_page(
        app_state,
        user.username,
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = user.username
    context["study_list_is_self"] = True
    context["study_list_can_create"] = True
    context["study_list_show_visibility"] = True
    context["study_list_show_owner"] = False
    _populate_study_search_form(context, f"owner:{user.username} ")
    _populate_study_page(context, request, result, active="mine")
    await _populate_study_navigation_topics(context, app_state, user.username)
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_contributed(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "Studies I contribute to • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    result = await contributed_studies_page(
        app_state,
        user.username,
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = user.username
    context["study_list_is_self"] = False
    context["study_list_can_create"] = True
    context["study_list_show_visibility"] = True
    context["study_list_show_owner"] = True
    _populate_study_search_form(context, f"member:{user.username} ")
    _populate_study_page(context, request, result, active="member")
    await _populate_study_navigation_topics(context, app_state, user.username)
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_liked(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "My favorite studies • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    result = await favorite_studies_page(
        app_state,
        user.username,
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = user.username
    context["study_list_is_self"] = False
    context["study_list_can_create"] = True
    context["study_list_show_visibility"] = True
    context["study_list_show_owner"] = True
    _populate_study_search_form(context)
    _populate_study_page(context, request, result, active="likes")
    await _populate_study_navigation_topics(context, app_state, user.username)
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_mine_public(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "My public studies • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    result = await owner_studies_page(
        app_state,
        user.username,
        visibility="public",
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = user.username
    context["study_list_is_self"] = True
    context["study_list_can_create"] = True
    context["study_list_show_visibility"] = False
    context["study_list_show_owner"] = False
    _populate_study_search_form(context, f"owner:{user.username} ")
    _populate_study_page(context, request, result, active="mine-public")
    await _populate_study_navigation_topics(context, app_state, user.username)
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_mine_private(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "My private studies • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    result = await owner_studies_page(
        app_state,
        user.username,
        visibility="private-or-unlisted",
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = user.username
    context["study_list_is_self"] = True
    context["study_list_can_create"] = True
    context["study_list_show_visibility"] = True
    context["study_list_show_owner"] = False
    _populate_study_search_form(context, f"owner:{user.username} ")
    _populate_study_page(context, request, result, active="mine-private")
    await _populate_study_navigation_topics(context, app_state, user.username)
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_public(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "All studies • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    result = await public_studies_page(
        app_state,
        q=request.rel_url.query.get("q", ""),
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = ""
    context["study_list_is_self"] = False
    context["study_list_can_create"] = not user.anon and not user.bot
    context["study_list_show_visibility"] = False
    context["study_list_show_owner"] = True
    context["study_public"] = result
    _populate_study_search_form(
        context,
        str(result.get("q") or ""),
        clear_href=f"/study/all?order={order}",
    )
    _populate_study_page(context, request, result, active="all")
    await _populate_study_navigation_topics(
        context, app_state, None if user.anon else user.username
    )
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_by_owner(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    requested_owner = request.match_info["username"]
    profile_user = await app_state.public_users.get_profile(requested_owner)
    if profile_user is None or not profile_user.enabled:
        raise web.HTTPNotFound()

    owner = profile_user.username
    viewer = None if user.anon else user.username
    is_self = viewer == owner
    _study_context(context)
    context["title"] = f"Studies by {owner} • PyChess"
    owner_studies = await studies_for_owner_view(app_state, owner, viewer)
    context["studies"] = owner_studies
    context["study_card_chapters"] = await study_list_chapter_names(app_state, owner_studies)
    context["study_list_owner"] = owner
    context["study_list_is_self"] = is_self
    context["study_list_can_create"] = is_self and not user.bot
    context["study_list_show_visibility"] = is_self
    context["study_list_show_owner"] = False
    context["study_list_navigation"] = False
    _populate_study_search_form(context, f"owner:{owner} ")
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_search(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "Search studies • PyChess"
    order = study_list_order(request.rel_url.query.get("order"))
    viewer = None if user.anon else user.username
    result = await study_search_page(
        app_state,
        q=request.rel_url.query.get("q", ""),
        viewer=viewer,
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    context["study_list_owner"] = ""
    context["study_list_is_self"] = False
    context["study_list_can_create"] = not user.anon and not user.bot
    context["study_list_show_visibility"] = not user.anon
    context["study_list_show_owner"] = True
    context["study_search"] = result
    _populate_study_search_form(
        context,
        str(result.get("q") or ""),
        clear_href=f"/study/all?order={order}",
    )
    _populate_study_page(context, request, result, active="search")
    await _populate_study_navigation_topics(
        context, app_state, None if user.anon else user.username
    )
    return context


async def study_topic_autocomplete(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response([])
    term = request.rel_url.query.get("term", "")
    suggestions = await autocomplete_study_topics(
        app_state,
        term,
        viewer=None if user.anon else user.username,
    )
    return web.json_response(suggestions)


@aiohttp_jinja2.template("studies.html")
async def studies_topics(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    _study_context(context)
    context["title"] = "Study topics • PyChess"
    context["study_list_can_create"] = not user.anon and not user.bot
    context["study_topics_index"] = True
    context["study_popular_topics"] = await popular_study_topics(app_state)
    _populate_study_list_navigation(context, active="topics")
    await _populate_study_navigation_topics(
        context, app_state, None if user.anon else user.username
    )
    return context


@aiohttp_jinja2.template("studies.html")
async def studies_by_topic(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    try:
        topic = study_topic(request.match_info["topic"])
    except ValueError as exc:
        raise web.HTTPNotFound() from exc
    viewer = None if user.anon else user.username
    order = study_list_order(request.rel_url.query.get("order"))
    result = await topic_studies_page(
        app_state,
        topic,
        viewer=viewer,
        order=order,
        page=_positive_page(request.rel_url.query.get("page")),
    )
    _study_context(context)
    context["title"] = f"{topic} • Study topics • PyChess"
    context["study_list_owner"] = ""
    context["study_list_is_self"] = False
    context["study_list_can_create"] = not user.anon and not user.bot
    context["study_list_show_visibility"] = not user.anon
    context["study_list_show_owner"] = True
    context["study_topic"] = topic
    _populate_study_page(context, request, result, active="topic")
    await _populate_study_navigation_topics(context, app_state, viewer)
    return context


async def study_create(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    try:
        name, visibility, settings = _study_creation_metadata(data)
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc

    try:
        draft = await _draft_from_form(StudyChapterBuilder(app_state, user.username), data)
    except (StudyStorageError, StudyChapterBuildError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc

    try:
        quota_claim = await claim_study_creation_slot(app_state, user.username)
    except StudyQuotaExceeded as exc:
        raise _study_quota_http_error(exc) from exc
    try:
        study, chapter = await create_study_from_draft(
            app_state,
            user.username,
            draft,
            name=name or None,
            visibility=visibility,
            settings=settings,
        )
    except (StudyStorageError, StudyChapterBuildError) as exc:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        raise web.HTTPBadRequest(text=str(exc)) from exc
    except Exception:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        raise
    raise web.HTTPFound(f"/study/{study.id}/{chapter.id}")


async def study_choices(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response({"studies": [], "error": "db_unavailable"}, status=503)
    studies = await studies_writable_by(app_state, user.username)
    return web.json_response(
        {"studies": [{"id": study.id, "name": study.name} for study in studies]}
    )


async def _populate_study_chapter_context(
    app_state: Any,
    user: Any,
    context: ViewContext,
    study: Study,
    chapter: StudyChapter,
    *,
    writable: bool,
    practice_context: Mapping[str, object] | None = None,
) -> None:
    context["variant"] = chapter.variant
    context["chess960"] = chapter.chess960
    context["fen"] = chapter.initial_fen
    context["initialFen"] = chapter.initial_fen
    context["status"] = 0
    context["ply"] = 0

    snapshot_client_doc = None
    if chapter.variant_ini:
        metadata = await study_variant_metadata(app_state, chapter.variant)
        try:
            with study_variant_context(app_state, chapter.variant, chapter.variant_ini) as options:
                context["board"] = json_dumps(
                    _study_board(chapter, runtime_variant=options.runtime_variant)
                )
                snapshot_client_doc = study_variant_client_doc(
                    chapter.variant, chapter.variant_ini, metadata=metadata
                )
        except (ValueError, web.HTTPException) as exc:
            raise web.HTTPNotFound(text="Study variant snapshot is unavailable") from exc
    else:
        context["board"] = json_dumps(_study_board(chapter))

    # The current full tree is paired with lightweight chapter previews. Both the
    # normal Study page and the compact chapter embed consume this same snapshot.
    viewer = None if user.anon else user.username
    chapters = await chapter_previews(app_state, study.id)
    context["study_data"] = json_dumps(
        {
            "id": study.id,
            "name": study.name,
            "owner": study.owner,
            "visibility": study.visibility,
            "isOwner": (
                False
                if practice_context is not None
                else is_study_owner(study, None if user.anon else user.username)
            ),
            "canWrite": writable and practice_context is None,
            "canPreviewPractice": settings.DEV and writable and practice_context is None,
            "canClone": (
                practice_context is None
                and not user.anon
                and not user.bot
                and can_clone_study(study, user.username)
            ),
            "canShare": practice_context is None and can_share_study(study, viewer),
            "canEmbed": practice_context is None and can_embed_study(study),
            "enabledModes": list(study_enabled_chapter_modes()),
            "features": {
                # Practice is a learner runtime. Curated computer-practice chapters may
                # use the bounded local engine regardless of the Study authoring setting.
                "computer": (
                    True if practice_context is not None else can_use_study_computer(study, viewer)
                ),
                "explorer": can_use_study_explorer(study, viewer),
            },
            "settings": {
                "computer": study_feature_selection(study, "computer"),
                "explorer": study_feature_selection(study, "explorer"),
                "cloneable": study_feature_selection(study, "cloneable"),
                "shareable": study_feature_selection(study, "shareable"),
            },
            "canLike": practice_context is None and not user.anon and not user.bot,
            "liked": study.is_liked_by(None if user.anon else user.username),
            "likes": study.likes,
            "topics": list(study.topics),
            "maxTopics": STUDY_MAX_TOPICS,
            "topicMinLength": STUDY_TOPIC_MIN_LENGTH,
            "topicMaxLength": STUDY_TOPIC_MAX_LENGTH,
            "members": dict(study.members),
            "maxMembers": STUDY_MAX_MEMBERS,
            "sharedChapter": study.current_chapter or chapter.id,
            "sharedPath": study.current_path or "",
            "roomSnapshotToken": study_snapshot_token(study, chapters),
            "chapter": {
                "id": chapter.id,
                "name": chapter.name,
                "revision": chapter.revision,
                "snapshotToken": await chapter_snapshot_token(chapter),
                "order": chapter.order,
                "orientation": chapter.orientation,
                "mode": chapter.mode,
                **({"concealPly": chapter.conceal_ply} if chapter.conceal_ply is not None else {}),
                "variant": chapter.variant,
                "chess960": chapter.chess960,
                "initialFen": chapter.initial_fen,
                "variantIni": chapter.variant_ini,
                "createdAt": chapter.created_at.isoformat(),
                "source": {
                    "kind": (
                        study.source.kind
                        if chapter.source.kind == "scratch"
                        and chapter.order == 1
                        and study.source.kind != "scratch"
                        else chapter.source.kind
                    ),
                    **(
                        {
                            "id": (
                                study.source.source_id
                                if chapter.source.kind == "scratch"
                                and chapter.order == 1
                                and study.source.kind != "scratch"
                                else chapter.source.source_id
                            )
                        }
                        if (
                            (chapter.source.kind != "scratch" and chapter.source.source_id)
                            or (
                                chapter.source.kind == "scratch"
                                and chapter.order == 1
                                and study.source.kind != "scratch"
                                and study.source.source_id
                            )
                        )
                        else {}
                    ),
                },
                "description": chapter.description,
                "tags": dict(chapter.tags),
                "serverEval": (
                    chapter.server_eval.to_payload(
                        pending=has_pending_study_analysis(app_state, study.id, chapter.id)
                    )
                    if chapter.server_eval is not None
                    else None
                ),
                "tree": chapter.root.to_payload(),
            },
            "chapters": chapters,
            **({"practice": dict(practice_context)} if practice_context is not None else {}),
        }
    )

    if snapshot_client_doc is not None:
        variants = json.loads(str(context.get("catalogued_variants") or "[]"))
        variants = [item for item in variants if item.get("name") != chapter.variant]
        variants.append(snapshot_client_doc)
        context["catalogued_variants"] = json_dumps(variants)
    elif is_catalogued_variant(chapter.variant):
        catalogued_doc = catalogued_variant_client_doc_for_name(
            app_state, chapter.variant, user.username
        )
        if catalogued_doc is not None:
            variants = json.loads(str(context.get("catalogued_variants") or "[]"))
            if not any(item.get("name") == chapter.variant for item in variants):
                variants.append(catalogued_doc)
                context["catalogued_variants"] = json_dumps(variants)
    elif chapter.variant not in ALL_VARIANTS:
        raise web.HTTPNotFound(text="Study variant is unavailable")


@aiohttp_jinja2.template("analysis.html")
async def study_show(request: web.Request) -> ViewContext | web.Response:
    user, context, study, chapter = await _viewable_study_and_chapter(request)
    if request.match_info.get("chapterId") is None:
        raise web.HTTPFound(f"/study/{study.id}/{chapter.id}")
    app_state = get_app_state(request.app)
    viewer = None if user.anon else user.username
    writable = can_write_study(study, viewer)
    _study_context(context)
    context["view"] = "study"
    context["title"] = f"{study.name} • PyChess"
    await _populate_study_chapter_context(
        app_state,
        user,
        context,
        study,
        chapter,
        writable=writable,
    )

    if request.headers.get("Accept") == "application/json":
        return web.json_response(
            {
                "study": json.loads(str(context["study_data"])),
                "board": json.loads(str(context["board"])),
                "cataloguedVariants": json.loads(str(context.get("catalogued_variants") or "[]")),
            }
        )
    return context


@aiohttp_jinja2.template("embed.html")
async def study_embed(request: web.Request) -> ViewContext:
    user, context, study, chapter = await _viewable_study_and_chapter(request)

    # Embeds are deliberately a link-share surface. Like Lichess, private Studies
    # remain non-embeddable even for their owner, so a third-party iframe never
    # depends on authenticated cookies to reveal private Study content.
    if not can_embed_study(study):
        raise web.HTTPNotFound()

    app_state = get_app_state(request.app)
    context["view"] = "embed"
    context["view_css"] = "embed.css"
    context["title"] = f"{study.name}: {chapter.name} • PyChess"
    await _populate_study_chapter_context(
        app_state,
        user,
        context,
        study,
        chapter,
        writable=False,
    )
    return context


async def study_chapter_export_data(request: web.Request) -> web.StreamResponse:
    user, _, study, chapter = await _viewable_study_and_chapter(request)
    viewer = None if user.anon else user.username
    if not can_share_study(study, viewer):
        raise web.HTTPNotFound()
    return web.json_response(_chapter_export_payload(chapter))


async def study_from_analysis(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    if user.anon:
        return web.json_response({"ok": False, "error": "login_required"}, status=401)
    if user.bot:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response({"ok": False, "error": "db_unavailable"}, status=503)
    data = await read_json_data(request)
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="invalid analysis data")
    tree_payload = data.get("tree")
    if not isinstance(tree_payload, dict):
        raise web.HTTPBadRequest(text="invalid analysis tree")
    try:
        raw_tags = data.get("tags")
        if raw_tags is not None and not isinstance(raw_tags, Mapping):
            raise StudyChapterBuildError("Analysis PGN tags are invalid")
        mode, conceal_ply = _chapter_teaching_from_input(data)
        draft = await StudyChapterBuilder(app_state, user.username).from_analysis(
            variant=str(data.get("variant") or "chess"),
            initial_fen=str(data.get("initialFen") or ""),
            tree_payload=tree_payload,
            chess960=bool(data.get("chess960", False)),
            game_id=str(data.get("gameId") or "").strip() or None,
            name=str(data.get("chapterName") or "").strip() or None,
            orientation="black"
            if str(data.get("orientation") or "").lower() == "black"
            else "white",
            mode=mode,
            conceal_ply=conceal_ply,
            tags=cast(Mapping[str, str], raw_tags) if raw_tags is not None else None,
        )
        destination_id = str(data.get("studyId") or "").strip()
        if destination_id:
            activate_shared = _study_sync_enabled(data.get("sync"))
            async with sequence_study(app_state, destination_id):
                study = await load_study(app_state, destination_id)
                if study is None or not can_view_study(study, user.username):
                    return web.json_response({"ok": False, "error": "study_not_found"}, status=404)
                if not can_write_study(study, user.username):
                    return web.json_response({"ok": False, "error": "forbidden"}, status=403)
                chapter = await add_chapter_from_draft(
                    app_state, study, draft, activate_shared=activate_shared
                )
                await broadcast_study_chapters(app_state, study.id)
                if activate_shared:
                    await broadcast_study_position(app_state, study.id, chapter.id, "")
        else:
            try:
                quota_claim = await claim_study_creation_slot(app_state, user.username)
            except StudyQuotaExceeded as exc:
                if exc.code == "account_missing":
                    return web.json_response({"ok": False, "error": str(exc)}, status=403)
                return web.json_response(
                    {"ok": False, "error": str(exc)},
                    status=429,
                    headers={"Retry-After": str(exc.retry_after_seconds)},
                )
            try:
                study, chapter = await create_study_from_draft(
                    app_state,
                    user.username,
                    draft,
                    name=str(data.get("studyName") or "").strip() or None,
                )
            except Exception:
                await release_study_creation_slot(app_state, user.username, quota_claim)
                raise
    except (StudyChapterBuildError, StudyStorageError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)
    return web.json_response(
        {
            "ok": True,
            "studyId": study.id,
            "chapterId": chapter.id,
            "url": f"/study/{study.id}/{chapter.id}",
        }
    )


async def _pgn_import_drafts(
    app_state: Any, owner: str, data: Mapping[str, object]
) -> list[StudyChapterDraft]:
    raw_chapters = data.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters:
        raise StudyStorageError("PGN import contains no chapters")

    builder = StudyChapterBuilder(app_state, owner)
    drafts: list[StudyChapterDraft] = []
    for index, raw in enumerate(raw_chapters, start=1):
        if not isinstance(raw, Mapping):
            raise StudyChapterBuildError(f"Imported chapter {index} is invalid")
        raw_tree = raw.get("tree")
        if not isinstance(raw_tree, Mapping):
            raise StudyChapterBuildError(f"Imported chapter {index} has no valid tree")
        raw_chess960 = raw.get("chess960", False)
        if not isinstance(raw_chess960, bool):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid Chess960 mode")
        raw_orientation = raw.get("orientation", "white")
        if raw_orientation not in ("white", "black"):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid orientation")
        raw_tags = raw.get("tags", {})
        if not isinstance(raw_tags, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_tags.items()
        ):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid PGN tags")
        raw_snapshot = raw.get("variantIni")
        if raw_snapshot is not None and not isinstance(raw_snapshot, str):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid variant snapshot")
        raw_variant = raw.get("variant")
        raw_initial_fen = raw.get("initialFen")
        raw_name = raw.get("name")
        raw_description = raw.get("description", "")
        if not isinstance(raw_variant, str) or not isinstance(raw_initial_fen, str):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid variant/FEN data")
        if raw_name is not None and not isinstance(raw_name, str):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid name")
        if not isinstance(raw_description, str):
            raise StudyChapterBuildError(f"Imported chapter {index} has invalid description")

        try:
            mode, conceal_ply = _chapter_teaching_from_input(raw)
            drafts.append(
                await builder.from_import(
                    variant=raw_variant,
                    initial_fen=raw_initial_fen,
                    tree_payload=cast(Mapping[str, object], raw_tree),
                    chess960=raw_chess960,
                    variant_ini=cast(str | None, raw_snapshot),
                    name=raw_name.strip() or None if raw_name is not None else None,
                    orientation=cast(StudyOrientation, raw_orientation),
                    mode=mode,
                    conceal_ply=conceal_ply,
                    description=raw_description,
                    tags=cast(Mapping[str, str], raw_tags),
                )
            )
        except StudyVariantCapacityError:
            raise
        except StudyChapterBuildError as exc:
            raise StudyChapterBuildError(f"Imported chapter {index}: {exc}") from exc
    return drafts


async def study_create_pgn(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response(
            {"ok": False, "error": "Studies require database access."}, status=503
        )

    data = await read_json_data(request)
    if not isinstance(data, Mapping):
        return web.json_response({"ok": False, "error": "invalid import payload"}, status=400)
    try:
        name, visibility, settings = _study_creation_metadata(data)
        drafts = await _pgn_import_drafts(app_state, user.username, data)
    except StudyVariantCapacityError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=503)
    except (StudyStorageError, StudyChapterBuildError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    try:
        quota_claim = await claim_study_creation_slot(app_state, user.username)
    except StudyQuotaExceeded as exc:
        status = 403 if exc.code == "account_missing" else 429
        headers = {} if status == 403 else {"Retry-After": str(exc.retry_after_seconds)}
        return web.json_response({"ok": False, "error": str(exc)}, status=status, headers=headers)

    try:
        study, chapters = await create_study_from_drafts(
            app_state,
            user.username,
            drafts,
            name=name or None,
            visibility=visibility,
            settings=settings,
        )
    except (StudyStorageError, StudyChapterBuildError) as exc:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        return web.json_response({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        raise

    last = chapters[-1]
    return web.json_response(
        {
            "ok": True,
            "imported": len(chapters),
            "studyId": study.id,
            "chapterId": last.id,
            "url": f"/study/{study.id}/{last.id}",
        }
    )


async def study_import_pgn(request: web.Request) -> web.StreamResponse:
    user, _, study, _ = await _writable_study_and_chapter(request)
    app_state = get_app_state(request.app)
    data = await read_json_data(request)
    if not isinstance(data, Mapping):
        return web.json_response({"ok": False, "error": "invalid import payload"}, status=400)
    try:
        drafts = await _pgn_import_drafts(app_state, user.username, data)
    except StudyVariantCapacityError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=503)
    except (StudyStorageError, StudyChapterBuildError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    try:
        activate_shared = _study_sync_enabled(data.get("sync"))
        async with _sequenced_writable_study_and_chapter(request) as (_, _, study, _):
            chapters = await add_chapters_from_drafts(
                app_state, study, drafts, activate_shared=activate_shared
            )
            await broadcast_study_chapters(app_state, study.id)
            if activate_shared:
                await broadcast_study_position(app_state, study.id, chapters[-1].id, "")
    except StudyStorageError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    last = chapters[-1]
    return web.json_response(
        {
            "ok": True,
            "imported": len(chapters),
            "studyId": study.id,
            "chapterId": last.id,
            "url": f"/study/{study.id}/{last.id}",
        }
    )


async def study_clone(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    source = await load_study(app_state, request.match_info["studyId"])
    if source is None or not can_clone_study(source, user.username):
        raise web.HTTPNotFound()

    try:
        quota_claim = await claim_study_creation_slot(
            app_state,
            user.username,
            cost=STUDY_CLONE_CREATION_COST,
        )
    except StudyQuotaExceeded as exc:
        raise _study_quota_http_error(exc) from exc

    try:
        async with sequence_study(app_state, source.id):
            source = await load_study(app_state, source.id)
            if source is None or not can_clone_study(source, user.username):
                raise web.HTTPNotFound()
            cloned, chapter = await clone_study(app_state, source, user.username)
    except StudyStorageError as exc:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        raise web.HTTPBadRequest(text=str(exc)) from exc
    except Exception:
        await release_study_creation_slot(app_state, user.username, quota_claim)
        raise
    raise web.HTTPFound(f"/study/{cloned.id}/{chapter.id}")


async def study_like(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    if user.anon or user.bot:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)

    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response({"ok": False, "error": "db_unavailable"}, status=503)
    data = await read_json_data(request)
    if data is None:
        raise web.HTTPNoContent()
    if not isinstance(data, Mapping) or not isinstance(data.get("liked"), bool):
        return web.json_response({"ok": False, "error": "invalid_like"}, status=400)

    study_id = request.match_info["studyId"]
    async with sequence_study(app_state, study_id):
        study = await load_study(app_state, study_id)
        if study is None or not can_view_study(study, user.username):
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        liked, likes, changed = await set_study_like(app_state, study, user.username, data["liked"])
        await broadcast_study_likes(app_state, study.id, likes)
    if changed and liked and study.visibility == "public":
        await app_state.timeline.publish(
            "study-like",
            user,
            {"studyId": study.id, "name": study.name},
        )
    return web.json_response({"ok": True, "liked": liked, "likes": likes})


async def study_topics_update(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    if user.anon or user.bot:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)

    app_state = get_app_state(request.app)
    if app_state.db is None:
        return web.json_response({"ok": False, "error": "db_unavailable"}, status=503)
    data = await read_json_data(request)
    if not isinstance(data, Mapping) or not isinstance(data.get("topics"), list):
        return web.json_response({"ok": False, "error": "invalid_topics"}, status=400)
    study_id = request.match_info["studyId"]
    try:
        async with sequence_study(app_state, study_id):
            study = await load_study(app_state, study_id)
            if study is None or not can_view_study(study, user.username):
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            if not can_write_study(study, user.username):
                return web.json_response({"ok": False, "error": "forbidden"}, status=403)
            updated, changed = await set_study_topics(
                app_state,
                study.id,
                user.username,
                data["topics"],
            )
            if changed:
                await broadcast_study_topics(app_state, updated.id, updated.topics)
    except StudyStorageError as exc:
        return web.json_response(
            {"ok": False, "error": "invalid_topics", "message": str(exc)},
            status=400,
        )
    return web.json_response({"ok": True, "topics": list(updated.topics)})


async def study_edit(request: web.Request) -> web.StreamResponse:
    user, _, study, _ = await _owned_study_and_chapter(request)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    app_state = get_app_state(request.app)
    async with sequence_study(app_state, study.id):
        current = await load_owned_study(app_state, study.id, user.username)
        if current is None:
            raise web.HTTPNotFound()
        try:
            visibility = study_visibility(data.get("visibility", current.visibility))
        except ValueError as exc:
            raise web.HTTPBadRequest(text="Invalid Study visibility") from exc
        try:
            settings = await set_study_feature_settings(app_state, current, data)
        except StudyStorageError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        settings_changed = settings != dict(current.settings)
        await rename_study(app_state, current, data.get("name"))
        await set_study_visibility(app_state, current, visibility)
        if settings_changed:
            await broadcast_study_reload(
                app_state, current.id, reason="feature_permissions_changed"
            )
        if visibility == "private" and current.visibility != "private":
            await close_study_sockets(app_state, current.id)
    raise web.HTTPFound(f"/study/{study.id}")


async def study_delete(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")

    study_id = request.match_info["studyId"]
    async with sequence_study(app_state, study_id):
        study = await load_owned_study(app_state, study_id, user.username)
        if study is None:
            raise web.HTTPNotFound()
        await delete_study(app_state, study)
        await broadcast_study_reload(app_state, study.id, reason="study_deleted")
        await close_study_sockets(app_state, study.id)
    raise web.HTTPFound("/study")


async def _study_member_target(request: web.Request, data: Mapping[str, object]) -> str:
    raw = str(data.get("username") or "").strip().lstrip("@")
    if not USERNAME_PREFIX_RE.fullmatch(raw):
        raise web.HTTPBadRequest(text="Invalid username")
    app_state = get_app_state(request.app)
    profile = await app_state.public_users.get_profile(raw)
    if profile is None or not profile.enabled:
        raise web.HTTPBadRequest(text="User not found")
    if profile.bot:
        raise web.HTTPBadRequest(text="BOT accounts cannot be Study members")
    return profile.username


async def study_member_add(request: web.Request) -> web.StreamResponse:
    user, _, study, _ = await _owned_study_and_chapter(request)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    target = await _study_member_target(request, data)
    app_state = get_app_state(request.app)
    try:
        async with sequence_study(app_state, study.id):
            updated = await add_study_member(
                app_state, study.id, user.username, target, data.get("role", "read")
            )
            await broadcast_study_members(app_state, updated)
    except (StudyStorageError, ValueError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}")


async def study_member_role(request: web.Request) -> web.StreamResponse:
    user, _, study, _ = await _owned_study_and_chapter(request)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    target = str(data.get("username") or "").strip()
    app_state = get_app_state(request.app)
    try:
        async with sequence_study(app_state, study.id):
            updated = await set_study_member_role(
                app_state, study.id, user.username, target, data.get("role")
            )
            await broadcast_study_members(app_state, updated)
    except (StudyStorageError, ValueError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}")


async def study_member_remove(request: web.Request) -> web.StreamResponse:
    user, _, study, _ = await _owned_study_and_chapter(request)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    target = str(data.get("username") or "").strip()
    app_state = get_app_state(request.app)
    try:
        async with sequence_study(app_state, study.id):
            updated = await remove_study_member(app_state, study.id, user.username, target)
            await broadcast_study_members(app_state, updated)
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}")


async def study_leave(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_owner_user(user)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Studies require database access.")
    study = await load_study(app_state, request.match_info["studyId"])
    if study is None or not can_view_study(study, user.username):
        raise web.HTTPNotFound()
    try:
        async with sequence_study(app_state, study.id):
            updated = await leave_study(app_state, study.id, user.username)
            await broadcast_study_members(app_state, updated)
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound("/study")


async def study_chapter_create(request: web.Request) -> web.StreamResponse:
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    app_state = get_app_state(request.app)
    try:
        async with _sequenced_writable_study_and_chapter(request) as (
            user,
            _,
            study,
            chapter,
        ):
            # A source-aware form creates a fresh chapter. The old one-button request still
            # creates a blank chapter using the current chapter's variant as its default.
            draft = await _draft_from_form(
                StudyChapterBuilder(app_state, user.username),
                data,
                fallback_variant=chapter.variant,
                fallback_chess960=chapter.chess960,
            )
            activate_shared = _study_sync_enabled(data.get("sync"))
            created = await add_chapter_from_draft(
                app_state, study, draft, activate_shared=activate_shared
            )
            await broadcast_study_chapters(app_state, study.id)
            if activate_shared:
                await broadcast_study_position(app_state, study.id, created.id, "")
    except (StudyStorageError, StudyChapterBuildError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}/{created.id}")


async def study_chapter_edit(request: web.Request) -> web.StreamResponse:
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    app_state = get_app_state(request.app)
    try:
        async with _sequenced_writable_study_and_chapter(request) as (_, _, study, chapter):
            await edit_chapter_metadata(
                app_state,
                chapter,
                name=data.get("name"),
                orientation=data.get("orientation", chapter.orientation),
                pinned_description=data.get("description") if "description" in data else None,
                mode=data.get("mode") if "mode" in data else None,
                conceal_ply=data.get("concealPly") if "concealPly" in data else None,
            )
            updated_chapter = await load_chapter(app_state, study.id, chapter.id)
            if updated_chapter is None:
                raise StudyStorageError("Study chapter disappeared while editing metadata")
            teaching_changed = (
                updated_chapter.mode != chapter.mode
                or updated_chapter.conceal_ply != chapter.conceal_ply
            )
            orientation_changed = updated_chapter.orientation != chapter.orientation
            reload_required = teaching_changed or orientation_changed
            metadata_changed = (
                updated_chapter.name != chapter.name
                or orientation_changed
                or updated_chapter.description != chapter.description
                or teaching_changed
            )
            if teaching_changed:
                await broadcast_study_reload(app_state, study.id, reason="chapter_mode_changed")
            elif orientation_changed:
                await broadcast_study_reload(
                    app_state, study.id, reason="chapter_orientation_changed"
                )
            elif updated_chapter.revision != chapter.revision:
                await broadcast_study_chapter_content(
                    app_state,
                    study.id,
                    updated_chapter.id,
                    updated_chapter.revision,
                    updated_chapter.description,
                )
            if metadata_changed and not reload_required:
                await broadcast_study_chapters(app_state, study.id)
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}/{chapter.id}")


async def study_chapter_clear_annotations(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    try:
        async with _sequenced_writable_study_and_chapter(request) as (_, _, study, chapter):
            changed = await clear_chapter_annotations(app_state, study, chapter)
            if changed:
                await broadcast_study_reload(
                    app_state, study.id, reason="chapter_annotations_cleared"
                )
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}/{chapter.id}")


async def study_chapter_clear_variations(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    try:
        async with _sequenced_writable_study_and_chapter(request) as (_, _, study, chapter):
            changed = await clear_chapter_variations(app_state, study, chapter)
            if changed:
                await broadcast_study_reload(
                    app_state, study.id, reason="chapter_variations_cleared"
                )
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}/{chapter.id}")


async def study_chapter_delete(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    try:
        async with _sequenced_writable_study_and_chapter(request) as (_, _, study, chapter):
            shared_chapter_deleted = (
                not study.current_chapter or study.current_chapter == chapter.id
            )
            next_chapter = await delete_chapter(app_state, study, chapter)
            await broadcast_study_chapters(app_state, study.id)
            if shared_chapter_deleted:
                await broadcast_study_position(app_state, study.id, next_chapter, "")
    except StudyStorageError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    raise web.HTTPFound(f"/study/{study.id}/{next_chapter}")
