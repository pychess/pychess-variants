from __future__ import annotations

import json
from typing import Any

import aiohttp_jinja2
import practice as practice_data
import settings
from aiohttp import web
from practice_progress import (
    EMPTY_PRACTICE_PROGRESS,
    PracticeProgress,
    load_practice_progress,
    practice_progress_key,
    record_practice_completion,
    reset_practice_chapters,
)
from pychess_global_app_state_utils import get_app_state
from study.permissions import can_view_study, can_write_study
from study.storage import load_chapter, load_study
from typing_defs import ViewContext

from views import get_user_context
from views.study import _populate_study_chapter_context, _study_context


def _progress_username(user: Any) -> str | None:
    if user.anon or user.bot:
        return None
    return user.username


async def _user_practice_progress(app_state: Any, user: Any) -> PracticeProgress:
    username = _progress_username(user)
    if username is None:
        return EMPTY_PRACTICE_PROGRESS
    return await load_practice_progress(app_state, username)


def _practice_progress_context(
    curriculum: tuple[practice_data.PracticeSectionValidation, ...],
    progress: PracticeProgress,
) -> tuple[dict[str, object], dict[str, int]]:
    by_study: dict[str, object] = {}
    done = 0
    total = 0
    seen: set[str] = set()
    for section in curriculum:
        for resolved in section.valid_studies:
            if resolved.study is None:
                continue
            chapter_ids = tuple(chapter.id for chapter in resolved.chapters)
            summary = progress.for_study(resolved.study.id, chapter_ids)
            by_study[resolved.study.id] = summary
            if resolved.study.id in seen:
                continue
            seen.add(resolved.study.id)
            done += summary.done
            total += summary.total
    return by_study, {"done": done, "total": total}


@aiohttp_jinja2.template("practice.html")
async def practice(request: web.Request) -> ViewContext:
    if not settings.DEV:
        raise web.HTTPNotFound()

    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    curriculum = await practice_data.build_practice_curriculum(
        app_state,
        sections=practice_data.PRACTICE_SECTIONS,
    )
    available_variants = practice_data.practice_variant_keys(curriculum)
    requested_variant = request.match_info.get("variant")

    if requested_variant is None and available_variants:
        menu_variant = context["menu_variant"]
        selected_variant = (
            menu_variant if menu_variant in available_variants else available_variants[0]
        )
        raise web.HTTPFound(f"/practice/{selected_variant}")

    selected_variant = requested_variant
    if selected_variant is None:
        # With no valid curated Study there is no selector target. Keep invalid DEV
        # entries visible so maintainers can see why the registry is unusable.
        visible_curriculum = curriculum
    else:
        visible_curriculum = practice_data.filter_practice_curriculum(curriculum, selected_variant)

    progress = await _user_practice_progress(app_state, user)
    progress_by_study, variant_progress = _practice_progress_context(visible_curriculum, progress)

    context["title"] = "Practice • PyChess"
    context["view_css"] = "practice.css"
    context["practice_sections"] = visible_curriculum
    context["practice_variant"] = selected_variant
    context["practice_variants"] = available_variants
    context["practice_has_content"] = selected_variant in available_variants
    context["practice_progress_authenticated"] = _progress_username(user) is not None
    context["practice_progress_by_study"] = progress_by_study
    context["practice_variant_progress"] = variant_progress
    return context


@aiohttp_jinja2.template("analysis.html")
async def practice_study(request: web.Request) -> ViewContext | web.Response:
    """Render one curated Study in the learner-only Practice shell."""

    if not settings.DEV:
        raise web.HTTPNotFound()

    variant_key = request.match_info["variant"]
    study_id = request.match_info["studyId"]
    location = practice_data.find_practice_study(variant_key, study_id)
    if location is None:
        raise web.HTTPNotFound()

    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Practice requires database access.")

    resolved = await practice_data.validate_practice_study(app_state, location.ref)
    if not resolved.valid or resolved.study is None:
        reason = "; ".join(issue.message for issue in resolved.issues) or "Invalid Practice Study"
        raise web.HTTPNotFound(text=reason)

    user, context = await get_user_context(request, include_catalogued_variants=True)
    progress = await _user_practice_progress(app_state, user)
    chapter_ids = tuple(chapter.id for chapter in resolved.chapters)
    requested_chapter_id = request.match_info.get("chapterId")
    if requested_chapter_id is None:
        resume_chapter_id = progress.first_unfinished(resolved.study.id, chapter_ids)
        if resume_chapter_id is None:
            resume_chapter_id = resolved.chapters[0].id
        raise web.HTTPFound(f"/practice/{variant_key}/{resolved.study.id}/{resume_chapter_id}")

    chapter_metadata = next(
        (item for item in resolved.chapters if item.id == requested_chapter_id), None
    )
    if chapter_metadata is None:
        raise web.HTTPNotFound()

    try:
        chapter = await load_chapter(app_state, resolved.study.id, requested_chapter_id)
    except (TypeError, ValueError) as exc:
        raise web.HTTPNotFound(text="Practice chapter is unavailable") from exc
    if chapter is None or chapter.mode not in practice_data.PRACTICE_ELIGIBLE_CHAPTER_MODES:
        raise web.HTTPNotFound()

    study_progress = progress.for_study(resolved.study.id, chapter_ids)
    _study_context(context)
    context["view"] = "study"
    context["title"] = f"{resolved.study.name} • Practice • PyChess"
    await _populate_study_chapter_context(
        app_state,
        user,
        context,
        resolved.study,
        chapter,
        writable=False,
        practice_context={
            "variant": variant_key,
            "sectionId": location.section.id,
            "sectionName": location.section.name,
            "studyTitle": location.ref.title or resolved.study.name,
            "studyDescription": location.ref.description,
            "studyIcon": location.ref.icon,
            "menu": practice_data.practice_menu_payload(),
            "indexUrl": f"/practice/{variant_key}",
            "studyUrl": f"/practice/{variant_key}/{resolved.study.id}",
            "completedChapterIds": list(study_progress.completed_chapter_ids),
            "persistProgress": _progress_username(user) is not None,
            **(
                {"goal": chapter_metadata.goal.to_payload()}
                if chapter_metadata.goal is not None
                else {}
            ),
        },
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


async def practice_preview(request: web.Request) -> web.StreamResponse:
    """Preview one writable Study through the learner-only Practice runtime.

    This DEV authoring aid intentionally bypasses the curated registry while keeping
    the same chapter/content validation. Preview never hydrates or persists curriculum
    progress and never joins the Study websocket room.
    """

    if not settings.DEV:
        raise web.HTTPNotFound()

    user, context = await get_user_context(request, include_catalogued_variants=True)
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Practice requires database access.")

    study_id = request.match_info["studyId"]
    study = await load_study(app_state, study_id)
    viewer = None if user.anon else user.username
    if study is None or not can_view_study(study, viewer):
        raise web.HTTPNotFound()
    if not can_write_study(study, viewer):
        raise web.HTTPForbidden(text="You cannot preview this Study as Practice.")

    resolved = await practice_data.validate_practice_preview_study(app_state, study)
    requested_chapter_id = request.match_info.get("chapterId")
    editor_chapter_id = requested_chapter_id or study.current_chapter
    if editor_chapter_id is None and resolved.chapters:
        editor_chapter_id = resolved.chapters[0].id
    editor_url = f"/study/{study.id}" + (
        f"/{editor_chapter_id}" if editor_chapter_id is not None else ""
    )

    if not resolved.valid:
        if request.headers.get("Accept") == "application/json":
            return web.json_response(
                {
                    "studyId": study.id,
                    "valid": False,
                    "issues": [
                        {"code": issue.code, "message": issue.message} for issue in resolved.issues
                    ],
                },
                status=422,
            )
        context["title"] = f"{study.name} • Practice Preview • PyChess"
        context["practice_preview_study"] = study
        context["practice_preview_issues"] = resolved.issues
        context["practice_preview_back_url"] = editor_url
        return await aiohttp_jinja2.render_template_async("practice-preview.html", request, context)

    if requested_chapter_id is None:
        chapter_ids = {chapter.id for chapter in resolved.chapters}
        chapter_id = study.current_chapter if study.current_chapter in chapter_ids else None
        if chapter_id is None:
            chapter_id = resolved.chapters[0].id
        raise web.HTTPFound(f"/practice/preview/{study.id}/{chapter_id}")

    chapter_metadata = next(
        (item for item in resolved.chapters if item.id == requested_chapter_id), None
    )
    if chapter_metadata is None:
        raise web.HTTPNotFound()

    try:
        chapter = await load_chapter(app_state, study.id, requested_chapter_id)
    except (TypeError, ValueError) as exc:
        raise web.HTTPNotFound(text="Practice preview chapter is unavailable") from exc
    if chapter is None or chapter.mode not in practice_data.PRACTICE_ELIGIBLE_CHAPTER_MODES:
        raise web.HTTPNotFound()

    _study_context(context)
    context["view"] = "study"
    context["title"] = f"{study.name} • Practice Preview • PyChess"
    await _populate_study_chapter_context(
        app_state,
        user,
        context,
        study,
        chapter,
        writable=False,
        practice_context={
            "variant": practice_data.practice_variant_key(resolved.ref),
            "sectionId": "preview",
            "sectionName": "Practice Preview",
            "studyTitle": study.name,
            "studyDescription": "Practice Preview",
            "studyIcon": "help",
            "menu": [],
            "indexUrl": f"/study/{study.id}/{chapter.id}",
            "studyUrl": f"/practice/preview/{study.id}",
            "completedChapterIds": [],
            "persistProgress": False,
            "preview": True,
            **(
                {"goal": chapter_metadata.goal.to_payload()}
                if chapter_metadata.goal is not None
                else {}
            ),
        },
    )

    if request.headers.get("Accept") == "application/json":
        return web.json_response(
            {
                "study": json.loads(str(context["study_data"])),
                "board": json.loads(str(context["board"])),
                "cataloguedVariants": json.loads(str(context.get("catalogued_variants") or "[]")),
            }
        )
    return await aiohttp_jinja2.render_template_async("analysis.html", request, context)


async def practice_complete(request: web.Request) -> web.Response:
    """Persist completion of a curated Practice chapter for a signed-in learner."""

    if not settings.DEV:
        raise web.HTTPNotFound()

    user, _context = await get_user_context(request)
    username = _progress_username(user)
    if username is None:
        raise web.HTTPUnauthorized(text="Sign in to save Practice progress.")

    variant_key = request.match_info["variant"]
    study_id = request.match_info["studyId"]
    chapter_id = request.match_info["chapterId"]
    location = practice_data.find_practice_study(variant_key, study_id)
    if location is None:
        raise web.HTTPNotFound()

    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Practice requires database access.")
    resolved = await practice_data.validate_practice_study(app_state, location.ref)
    if not resolved.valid or resolved.study is None:
        raise web.HTTPNotFound()

    chapter = next((item for item in resolved.chapters if item.id == chapter_id), None)
    if chapter is None:
        raise web.HTTPNotFound()
    best_moves: int | None = None
    if chapter.mode == "practice":
        # The browser owns the bounded Fairy-Stockfish evaluator. Persist only the
        # successful attempt summary it sends after P8 has reached a real success state.
        try:
            payload = await request.json()
        except (json.JSONDecodeError, TypeError):
            raise web.HTTPBadRequest(text="Computer Practice completion needs a move count.")
        raw_best_moves = payload.get("bestMoves") if isinstance(payload, dict) else None
        if (
            isinstance(raw_best_moves, bool)
            or not isinstance(raw_best_moves, int)
            or raw_best_moves < 0
        ):
            raise web.HTTPBadRequest(text="Computer Practice completion needs a valid move count.")
        best_moves = raw_best_moves
    elif chapter.mode != "gamebook":
        raise web.HTTPBadRequest(text="This Practice chapter has no completion evaluator.")

    await record_practice_completion(
        app_state,
        username,
        resolved.study.id,
        chapter.id,
        best_moves=best_moves,
    )
    return web.json_response(
        {"completed": True, **({"bestMoves": best_moves} if best_moves is not None else {})}
    )


async def practice_reset(request: web.Request) -> web.StreamResponse:
    """Reset the signed-in learner's progress for the selected Practice variant."""

    if not settings.DEV:
        raise web.HTTPNotFound()

    user, _context = await get_user_context(request)
    username = _progress_username(user)
    if username is None:
        raise web.HTTPUnauthorized(text="Sign in to reset Practice progress.")

    variant_key = request.match_info["variant"]
    app_state = get_app_state(request.app)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Practice requires database access.")

    curriculum = await practice_data.build_practice_curriculum(
        app_state,
        sections=practice_data.PRACTICE_SECTIONS,
    )
    visible = practice_data.filter_practice_curriculum(curriculum, variant_key)
    keys = tuple(
        sorted(
            {
                practice_progress_key(resolved.study.id, chapter.id)
                for section in visible
                for resolved in section.valid_studies
                if resolved.study is not None
                for chapter in resolved.chapters
            }
        )
    )
    await reset_practice_chapters(app_state, username, keys)
    raise web.HTTPFound(f"/practice/{variant_key}")
