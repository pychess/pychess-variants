from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

import aiohttp_session
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from pychess_global_app_state_utils import get_app_state
from websocket_utils import get_user, process_ws, ws_send_json, ws_send_json_many
from ws_structs import STUDY_TYPED_DECODERS, WsInboundStruct

from study.models import Study
from study.mutations import StudyMutationResult, StudyMutationService
from study.permissions import can_view_study
from study.sequencer import cleanup_study_sequence, sequence_study
from study.snapshot import chapter_snapshot_token, study_snapshot_token
from study.storage import (
    StudyStorageError,
    chapter_previews,
    load_chapter,
    load_study,
    reset_concealment,
    set_shared_position,
)

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User

log = logging.getLogger(__name__)

_CLIENT_OP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_PATH_LENGTH = 40_000
_MAX_MOVE_LENGTH = 256
_MAX_ANNOTATION_PATH_LENGTH = _MAX_PATH_LENGTH


def _as_mapping(data: object) -> Mapping[str, object] | None:
    # msgspec.Struct deliberately exposes the mapping methods used by the shared
    # websocket decoder, but it is not registered as collections.abc.Mapping.
    if isinstance(data, Mapping):
        return data
    if isinstance(data, WsInboundStruct):
        keys = data.keys()
        return {key: cast(object, data[key]) for key in keys}
    return None


def _valid_common_message(data: Mapping[str, object], study_id: str) -> bool:
    if data.get("studyId") != study_id:
        return False
    chapter_id = data.get("chapterId")
    client_op_id = data.get("clientOpId")
    expected_revision = data.get("expectedRevision")
    return (
        isinstance(chapter_id, str)
        and bool(chapter_id)
        and isinstance(client_op_id, str)
        and _CLIENT_OP_ID_RE.fullmatch(client_op_id) is not None
        and isinstance(expected_revision, int)
        and not isinstance(expected_revision, bool)
        and expected_revision >= 0
    )


def _response_base(data: Mapping[str, object]) -> dict[str, object]:
    return {
        "type": data["type"],
        "studyId": data["studyId"],
        "chapterId": data["chapterId"],
        "clientOpId": data["clientOpId"],
    }


async def _send_invalid_message(ws: WebSocketResponse, data: Mapping[str, object]) -> None:
    payload: dict[str, object] = {
        "type": "study_error",
        "reason": "invalid_message",
    }
    for key in ("studyId", "chapterId", "clientOpId"):
        value = data.get(key)
        if isinstance(value, str):
            payload[key] = value
    await ws_send_json(ws, payload)


async def _finish_mutation(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    study_id: str,
    data: Mapping[str, object],
    result: StudyMutationResult,
    extra: Mapping[str, object] | None = None,
) -> None:
    if result.status == "reload":
        await ws_send_json(
            ws,
            {
                "type": "study_reload",
                "studyId": study_id,
                "chapterId": data["chapterId"],
                "clientOpId": data["clientOpId"],
                "revision": result.revision,
                "reason": result.reason,
            },
        )
        return
    if result.status == "error":
        await ws_send_json(
            ws,
            {
                "type": "study_error",
                "studyId": study_id,
                "chapterId": data["chapterId"],
                "clientOpId": data["clientOpId"],
                "revision": result.revision,
                "reason": result.reason,
            },
        )
        return

    payload = _response_base(data)
    payload["revision"] = result.revision
    payload["changed"] = result.changed
    if result.path is not None:
        payload["path"] = result.path
    if result.node is not None:
        payload["node"] = result.node.to_payload()
    if result.annotations is not None:
        payload["annotations"] = result.annotations.to_payload()
    if result.gamebook is not None:
        payload["gamebook"] = result.gamebook.to_payload()
    if result.description is not None:
        payload["description"] = result.description
    if result.tags is not None:
        payload["tags"] = dict(result.tags)
    if result.conceal_changed:
        payload["concealPly"] = result.conceal_ply
    if extra:
        payload.update(extra)

    # Idempotent/no-op mutations are acknowledgements, not shared changes.
    if not result.changed:
        await ws_send_json(ws, payload)
        return

    room = app_state.study_sockets.get(study_id)
    if room:
        await ws_send_json_many(tuple(room), payload)
    else:
        await ws_send_json(ws, payload)


async def broadcast_study_chapters(
    app_state: PychessGlobalAppState,
    study_id: str,
) -> None:
    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    study_doc = await app_state.db.study.find_one(
        {"_id": study_id}, projection={"currentChapter": 1, "currentPath": 1}
    )
    if study_doc is None:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_chapters",
            "studyId": study_id,
            "chapters": await chapter_previews(app_state, study_id),
            "sharedChapter": str(study_doc.get("currentChapter") or ""),
            "sharedPath": str(study_doc.get("currentPath") or ""),
        },
    )


async def broadcast_study_chapter_content(
    app_state: PychessGlobalAppState,
    study_id: str,
    chapter_id: str,
    revision: int,
    description: str,
) -> None:
    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_chapter_content",
            "studyId": study_id,
            "chapterId": chapter_id,
            "revision": revision,
            "description": description,
        },
    )


async def broadcast_study_position(
    app_state: PychessGlobalAppState,
    study_id: str,
    chapter_id: str,
    path: str,
) -> None:
    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_position",
            "studyId": study_id,
            "chapterId": chapter_id,
            "path": path,
        },
    )


async def _broadcast_conceal_state(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    study_id: str,
    chapter_id: str,
    path: str,
    conceal_ply: int,
    revision: int,
) -> None:
    payload = {
        "type": "study_conceal",
        "studyId": study_id,
        "chapterId": chapter_id,
        "path": path,
        "concealPly": conceal_ply,
        "revision": revision,
    }
    room = app_state.study_sockets.get(study_id)
    if room:
        await ws_send_json_many(tuple(room), payload)
    else:
        await ws_send_json(ws, payload)


async def _broadcast_shared_position(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    study_id: str,
    chapter_id: str,
    path: str,
) -> None:
    room = app_state.study_sockets.get(study_id)
    if room:
        await broadcast_study_position(app_state, study_id, chapter_id, path)
    else:
        await ws_send_json(
            ws,
            {
                "type": "study_position",
                "studyId": study_id,
                "chapterId": chapter_id,
                "path": path,
            },
        )


async def _set_shared_position_message(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    data: Mapping[str, object],
    *,
    study_id: str,
) -> None:
    chapter_id = data.get("chapterId")
    path = data.get("path")
    expected_revision = data.get("expectedRevision")
    if (
        data.get("studyId") != study_id
        or not isinstance(chapter_id, str)
        or not chapter_id
        or not isinstance(path, str)
        or len(path) > _MAX_PATH_LENGTH
        or (
            expected_revision is not None
            and (
                isinstance(expected_revision, bool)
                or not isinstance(expected_revision, int)
                or expected_revision < 0
            )
        )
    ):
        await _send_invalid_message(ws, data)
        return
    try:
        result = await set_shared_position(
            app_state,
            study_id,
            user.username,
            chapter_id,
            path,
            expected_revision=cast(int | None, expected_revision),
        )
    except StudyStorageError:
        await ws_send_json(
            ws,
            {
                "type": "study_reload",
                "studyId": study_id,
                "chapterId": chapter_id,
                "reason": "invalid_shared_position",
            },
        )
        return
    if not result.changed:
        return
    if result.conceal_changed and result.conceal_ply is not None:
        await _broadcast_conceal_state(
            app_state,
            ws,
            study_id,
            chapter_id,
            path,
            result.conceal_ply,
            result.chapter_revision,
        )
        return
    await _broadcast_shared_position(app_state, ws, study_id, chapter_id, path)


async def _reset_conceal_message(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    data: Mapping[str, object],
    *,
    study_id: str,
) -> None:
    chapter_id = data.get("chapterId")
    expected_revision = data.get("expectedRevision")
    if (
        data.get("studyId") != study_id
        or not isinstance(chapter_id, str)
        or not chapter_id
        or isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        await _send_invalid_message(ws, data)
        return
    try:
        result = await reset_concealment(
            app_state,
            study_id,
            user.username,
            chapter_id,
            expected_revision,
        )
    except StudyStorageError:
        await ws_send_json(
            ws,
            {
                "type": "study_reload",
                "studyId": study_id,
                "chapterId": chapter_id,
                "reason": "invalid_conceal_reset",
            },
        )
        return
    if not result.changed:
        return
    path = result.study.current_path or ""
    if result.conceal_changed and result.conceal_ply is not None:
        await _broadcast_conceal_state(
            app_state,
            ws,
            study_id,
            chapter_id,
            path,
            result.conceal_ply,
            result.chapter_revision,
        )
        return
    await _broadcast_shared_position(app_state, ws, study_id, chapter_id, path)


async def _repair_shared_position_after_delete(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    study_id: str,
    chapter_id: str,
    deleted_path: str,
) -> None:
    raw = await app_state.db.study.find_one({"_id": study_id})
    if raw is None:
        return
    try:
        study = Study.from_document(raw)
    except (TypeError, ValueError):
        return
    shared_path = study.current_path or ""
    if study.current_chapter != chapter_id or not shared_path:
        return
    if shared_path != deleted_path and not shared_path.startswith(f"{deleted_path}."):
        return
    repaired = deleted_path.rpartition(".")[0]
    update: dict[str, object]
    if repaired:
        update = {"$set": {"currentPath": repaired}}
    else:
        update = {"$unset": {"currentPath": ""}}
    await app_state.db.study.update_one({"_id": study_id}, update)
    await _broadcast_shared_position(app_state, ws, study_id, chapter_id, repaired)


async def _sync_chapter_message(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    data: Mapping[str, object],
    *,
    study_id: str,
) -> None:
    chapter_id = data.get("chapterId")
    request_id = data.get("requestId")
    if (
        data.get("studyId") != study_id
        or not isinstance(chapter_id, str)
        or not chapter_id
        or not isinstance(request_id, str)
        or _CLIENT_OP_ID_RE.fullmatch(request_id) is None
    ):
        await _send_invalid_message(ws, data)
        return

    study = await load_study(app_state, study_id)
    chapters = await chapter_previews(app_state, study_id) if study is not None else []
    chapter = await load_chapter(app_state, study_id, chapter_id)
    await ws_send_json(
        ws,
        {
            "type": "study_chapter_sync",
            "studyId": study_id,
            "chapterId": chapter_id,
            "requestId": request_id,
            "revision": chapter.revision if chapter is not None else None,
            "snapshotToken": await chapter_snapshot_token(chapter) if chapter is not None else None,
            "roomSnapshotToken": (
                study_snapshot_token(study, chapters) if study is not None else None
            ),
        },
    )


async def process_message(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    raw_data: object,
    *,
    study_id: str,
    service: StudyMutationService,
) -> None:
    # One Study-wide sequencer is enough for PyChess: all chapter mutations in a
    # room are processed and broadcast in one total order. Holding the lock through
    # broadcast guarantees every connected client observes monotonically ordered
    # revisions before the next queued mutation starts.
    async with sequence_study(app_state, study_id):
        await _process_message_unlocked(
            app_state, user, ws, raw_data, study_id=study_id, service=service
        )


async def _process_message_unlocked(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    raw_data: object,
    *,
    study_id: str,
    service: StudyMutationService,
) -> None:
    # Existing Study websockets can outlive the HTTP account-deletion request.
    # Once that request disables the shared User object, reject messages that were
    # queued before socket shutdown but have not yet entered the Study sequencer.
    if not getattr(user, "enabled", True):
        await ws.close()
        return

    data = _as_mapping(raw_data)
    if data is None:
        await _send_invalid_message(ws, {})
        return

    message_type = data.get("type")
    if message_type == "study_sync_chapter":
        await _sync_chapter_message(app_state, ws, data, study_id=study_id)
        return

    if message_type == "study_set_position":
        await _set_shared_position_message(app_state, user, ws, data, study_id=study_id)
        return

    if message_type == "study_reset_conceal":
        await _reset_conceal_message(app_state, user, ws, data, study_id=study_id)
        return

    if message_type == "study_request_analysis":
        chapter_id = data.get("chapterId")
        if data.get("studyId") != study_id or not isinstance(chapter_id, str) or not chapter_id:
            await _send_invalid_message(ws, data)
            return
        from study.analysis import request_study_server_analysis

        result = await request_study_server_analysis(
            app_state,
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
        )
        if result.status == "started":
            return
        if result.status == "already_requested" and not result.pending:
            await ws_send_json(
                ws,
                {
                    "type": "study_analysis_unavailable",
                    "studyId": study_id,
                    "chapterId": chapter_id,
                    "reason": result.status,
                },
            )
            return
        if result.server_eval is not None and result.status in {
            "already_requested",
            "already_done",
        }:
            await ws_send_json(
                ws,
                {
                    "type": "study_analysis_progress",
                    "studyId": study_id,
                    "chapterId": chapter_id,
                    "serverEval": result.server_eval.to_payload(pending=result.pending),
                },
            )
            return
        await ws_send_json(
            ws,
            {
                "type": "study_analysis_unavailable",
                "studyId": study_id,
                "chapterId": chapter_id,
                "reason": result.status,
            },
        )
        return

    if not _valid_common_message(data, study_id):
        await _send_invalid_message(ws, data)
        return

    chapter_id = cast(str, data["chapterId"])
    expected_revision = cast(int, data["expectedRevision"])

    if message_type == "study_add_node":
        parent_path = data.get("parentPath")
        move = data.get("move")
        node_id = data.get("nodeId")
        if (
            not isinstance(parent_path, str)
            or len(parent_path) > _MAX_PATH_LENGTH
            or not isinstance(move, str)
            or not move
            or len(move) > _MAX_MOVE_LENGTH
            or not isinstance(node_id, str)
        ):
            await _send_invalid_message(ws, data)
            return
        result = await service.add_node(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            parent_path=parent_path,
            move=move,
            expected_revision=expected_revision,
            node_id=node_id,
        )
        await _finish_mutation(
            app_state,
            ws,
            study_id,
            data,
            result,
            {"parentPath": parent_path, "move": move},
        )
        return

    if message_type in {
        "study_set_shapes",
        "study_set_comment",
        "study_set_nags",
        "study_clear_annotations",
        "study_set_gamebook",
    }:
        path = data.get("path")
        if not isinstance(path, str) or len(path) > _MAX_ANNOTATION_PATH_LENGTH:
            await _send_invalid_message(ws, data)
            return
        if message_type == "study_set_shapes":
            result = await service.set_shapes(
                study_id=study_id,
                chapter_id=chapter_id,
                username=user.username,
                path=path,
                shapes=data.get("shapes"),
                expected_revision=expected_revision,
            )
        elif message_type == "study_set_comment":
            comment_id = data.get("commentId")
            text = data.get("text")
            if not isinstance(comment_id, str) or not isinstance(text, str):
                await _send_invalid_message(ws, data)
                return
            result = await service.set_comment(
                study_id=study_id,
                chapter_id=chapter_id,
                username=user.username,
                path=path,
                comment_id=comment_id,
                text=text,
                expected_revision=expected_revision,
            )
        elif message_type == "study_set_nags":
            result = await service.set_nags(
                study_id=study_id,
                chapter_id=chapter_id,
                username=user.username,
                path=path,
                nags=data.get("nags"),
                expected_revision=expected_revision,
            )
        elif message_type == "study_clear_annotations":
            result = await service.clear_annotations(
                study_id=study_id,
                chapter_id=chapter_id,
                username=user.username,
                path=path,
                expected_revision=expected_revision,
            )
        else:
            field_name = data.get("field")
            value = data.get("value")
            if field_name not in {"hint", "deviation"} or not isinstance(value, str):
                await _send_invalid_message(ws, data)
                return
            result = await service.set_gamebook(
                study_id=study_id,
                chapter_id=chapter_id,
                username=user.username,
                path=path,
                field_name=cast(str, field_name),
                value=value,
                expected_revision=expected_revision,
            )
        await _finish_mutation(app_state, ws, study_id, data, result, {"path": path})
        return

    if message_type == "study_set_description":
        description = data.get("description")
        if not isinstance(description, str):
            await _send_invalid_message(ws, data)
            return
        result = await service.set_description(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            description=description,
            expected_revision=expected_revision,
        )
        await _finish_mutation(app_state, ws, study_id, data, result)
        return

    if message_type == "study_set_tags":
        tags = data.get("tags")
        if not isinstance(tags, Mapping):
            await _send_invalid_message(ws, data)
            return
        result = await service.set_tags(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            tags=tags,
            expected_revision=expected_revision,
        )
        await _finish_mutation(app_state, ws, study_id, data, result)
        return

    path = data.get("path")
    if not isinstance(path, str) or not path or len(path) > _MAX_PATH_LENGTH:
        await _send_invalid_message(ws, data)
        return

    if message_type == "study_delete_node":
        result = await service.delete_node(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            path=path,
            expected_revision=expected_revision,
        )
        await _finish_mutation(app_state, ws, study_id, data, result, {"path": path})
        if result.status == "ok" and result.changed:
            await _repair_shared_position_after_delete(app_state, ws, study_id, chapter_id, path)
    elif message_type == "study_promote_variation":
        to_mainline = data.get("toMainline")
        if not isinstance(to_mainline, bool):
            await _send_invalid_message(ws, data)
            return
        result = await service.promote_variation(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            path=path,
            to_mainline=to_mainline,
            expected_revision=expected_revision,
        )
        await _finish_mutation(
            app_state,
            ws,
            study_id,
            data,
            result,
            {"path": path, "toMainline": to_mainline},
        )
    elif message_type == "study_force_variation":
        force = data.get("force")
        if not isinstance(force, bool):
            await _send_invalid_message(ws, data)
            return
        result = await service.force_variation(
            study_id=study_id,
            chapter_id=chapter_id,
            username=user.username,
            path=path,
            force=force,
            expected_revision=expected_revision,
        )
        await _finish_mutation(
            app_state,
            ws,
            study_id,
            data,
            result,
            {"path": path, "force": force},
        )
    else:
        await _send_invalid_message(ws, data)


async def init_ws(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    study_id: str,
) -> None:
    # The HTTP handshake may have authorized an older Study snapshot. Re-read the
    # document under the same sequencer used by visibility/member revocations, then
    # insert the socket before releasing it. No private room event can pass between
    # the authoritative authorization check and room membership.
    async with sequence_study(app_state, study_id):
        # Account deletion disables the shared in-memory User before GDPR cleanup.
        # Recheck here as well as in process_ws so a handshake that passed its first
        # enabled check cannot enter a Study room after erasure has begun.
        if not getattr(user, "enabled", True):
            await ws.close()
            return

        raw_study = await app_state.db.study.find_one({"_id": study_id})
        if raw_study is None:
            await ws.close()
            return
        try:
            study = Study.from_document(raw_study)
        except (TypeError, ValueError):
            log.warning("Invalid stored Study document %s", study_id, exc_info=True)
            await ws.close()
            return
        if not can_view_study(study, user.username):
            await ws.close()
            return

        chapters = await chapter_previews(app_state, study_id)
        room = app_state.study_sockets.setdefault(study_id, set())
        room.add(ws)
        app_state.study_socket_users.setdefault(study_id, {})[ws] = user.username
        user.study_sockets.setdefault(study_id, set()).add(ws)
        user.update_online()
        await ws_send_json(
            ws,
            {
                "type": "study_user_connected",
                "studyId": study_id,
                "roomSnapshotToken": study_snapshot_token(study, chapters),
            },
        )


async def finally_logic(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    study_id: str,
) -> None:
    room = app_state.study_sockets.get(study_id)
    if room is not None:
        room.discard(ws)
        users = app_state.study_socket_users.get(study_id)
        if users is not None:
            users.pop(ws, None)
        if not room:
            app_state.study_sockets.pop(study_id, None)
            app_state.study_socket_users.pop(study_id, None)

    user_room = user.study_sockets.get(study_id)
    if user_room is not None:
        user_room.discard(ws)
        if not user_room:
            user.study_sockets.pop(study_id, None)
    user.update_online()
    cleanup_study_sequence(app_state, study_id)


async def broadcast_study_likes(
    app_state: PychessGlobalAppState, study_id: str, likes: int
) -> None:
    """Broadcast the current Study like count to connected viewers."""

    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_likes",
            "studyId": study_id,
            "likes": max(0, likes),
        },
    )


async def broadcast_study_topics(
    app_state: PychessGlobalAppState, study_id: str, topics: tuple[str, ...]
) -> None:
    """Broadcast Study-level discovery topics to connected viewers."""

    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_topics",
            "studyId": study_id,
            "topics": list(topics),
        },
    )


async def broadcast_study_reload(
    app_state: PychessGlobalAppState, study_id: str, *, reason: str
) -> None:
    """Ask every connected Study client to refresh capability-sensitive page data."""

    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_reload",
            "studyId": study_id,
            "reason": reason,
        },
    )


async def broadcast_study_members(app_state: PychessGlobalAppState, study: Study) -> None:
    """Broadcast membership/capability changes without tearing down the whole room.

    Clients whose access was actually revoked from a private Study are closed after
    receiving the update; public/unlisted former members may remain as read-only
    viewers.
    """

    room = app_state.study_sockets.get(study.id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_members",
            "studyId": study.id,
            "members": dict(study.members),
            "revision": study.revision,
        },
    )
    users = app_state.study_socket_users.get(study.id, {})
    for ws, username in tuple(users.items()):
        if not can_view_study(study, username):
            await ws.close()


async def close_study_sockets(app_state: PychessGlobalAppState, study_id: str) -> None:
    """Close live Study sockets so a stricter visibility applies immediately."""

    for ws in tuple(app_state.study_sockets.get(study_id, ())):
        await ws.close()


async def close_study_user_sockets(
    app_state: PychessGlobalAppState, study_id: str, username: str
) -> None:
    """Close one user's live sockets in a Study room without evicting other viewers."""

    users = app_state.study_socket_users.get(study_id, {})
    for ws, socket_username in tuple(users.items()):
        if socket_username == username:
            await ws.close()


async def study_socket_handler(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    study_id = request.match_info["studyId"]
    raw_study = await app_state.db.study.find_one({"_id": study_id})
    if raw_study is None:
        raise web.HTTPNotFound()
    try:
        study = Study.from_document(raw_study)
    except (TypeError, ValueError):
        log.warning("Invalid stored Study document %s", study_id, exc_info=True)
        raise web.HTTPNotFound() from None

    session = await aiohttp_session.get_session(request)
    session_username = session.get("user_name")
    viewer = session_username if isinstance(session_username, str) else None
    if not can_view_study(study, viewer):
        raise web.HTTPNotFound()
    user = await get_user(session, request)

    service = StudyMutationService(app_state, allow_stale_revision=True)

    async def on_init(
        inner_app_state: PychessGlobalAppState,
        ws: WebSocketResponse,
        inner_user: User,
    ) -> None:
        await init_ws(inner_app_state, ws, inner_user, study_id)

    async def on_message(
        inner_app_state: PychessGlobalAppState,
        inner_user: User,
        ws: WebSocketResponse,
        data: object,
    ) -> None:
        await process_message(
            inner_app_state,
            inner_user,
            ws,
            data,
            study_id=study_id,
            service=service,
        )

    ws = await process_ws(
        session,
        request,
        user,
        on_init,
        on_message,
        typed_decoders=STUDY_TYPED_DECODERS,
    )
    if ws is None:
        return web.HTTPFound("/")
    await finally_logic(app_state, ws, user, study_id)
    return ws
