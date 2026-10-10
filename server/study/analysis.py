from __future__ import annotations

import asyncio
import logging
import random
import string
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast

from analysis_advice import (
    ANALYSIS_COMMENT_AUTHOR,
    MoveAdvice,
    advice_for_move,
    analysis_pv,
    analysis_score,
    prepare_analysis_line,
)
from catalogued_variants import catalogued_variant_allows_fishnet, replace_variant_section_name
from const import ANALYSIS
from fairy.fairy_board import FairyBoard
from typing_defs import AnalysisStep, FishnetAnalysisItem, FishnetWork
from websocket_utils import ws_send_json_many

from study.annotations import StudyAnnotations, StudyComment
from study.constants import (
    STUDY_CHAPTER_MAX_BSON_BYTES,
    STUDY_MAX_COMMENTS_PER_POSITION,
    STUDY_MAX_NAGS_PER_POSITION,
    STUDY_MAX_NODES_PER_CHAPTER,
)
from study.document import encode_chapter
from study.engine import validated_study_position
from study.models import Study, StudyChapter, StudyServerEval
from study.permissions import can_write_study
from study.quota import (
    StudyQuotaExceeded,
    claim_study_analysis_slot,
    release_study_analysis_slot,
)
from study.sequencer import sequence_study
from study.tree import StudyTree, StudyTreeNode, new_study_node_id
from study.variant import study_variant_context

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState

STUDY_ANALYSIS_MIN_MOVES = 5
STUDY_ANALYSIS_COOLDOWN = timedelta(minutes=5)
STUDY_ANALYSIS_NODES = 500_000

StudyAnalysisRequestStatus = Literal[
    "started",
    "already_requested",
    "already_done",
    "too_short",
    "forbidden",
    "not_found",
    "fishnet_unavailable",
    "variant_unavailable",
    "concurrent_analysis",
    "daily_limit",
    "weekly_limit",
]


@dataclass(frozen=True, slots=True)
class StudyAnalysisRequestResult:
    status: StudyAnalysisRequestStatus
    server_eval: StudyServerEval | None = None
    pending: bool = False


def _new_work_id(app_state: PychessGlobalAppState) -> str:
    while True:
        work_id = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(6))
        if work_id not in app_state.fishnet_works:
            return work_id


def _study_work_matches(work: FishnetWork, study_id: str, chapter_id: str) -> bool:
    return (
        work["work"]["type"] == "analysis"
        and work.get("study_id") == study_id
        and work.get("chapter_id") == chapter_id
    )


def has_pending_study_analysis(
    app_state: PychessGlobalAppState, study_id: str, chapter_id: str
) -> bool:
    return any(
        _study_work_matches(work, study_id, chapter_id) for work in app_state.fishnet_works.values()
    )


def has_pending_study_analysis_for_user(app_state: PychessGlobalAppState, username: str) -> bool:
    return any(
        work["work"]["type"] == "analysis"
        and bool(work.get("study_id"))
        and work.get("username") == username
        for work in app_state.fishnet_works.values()
    )


def _analysis_request_lock(app_state: PychessGlobalAppState) -> asyncio.Lock:
    lock = getattr(app_state, "study_analysis_request_lock", None)
    if lock is None:
        # Tests and small helper app states do not necessarily construct the full
        # PychessGlobalAppState. There is no await between this lookup and set, so
        # lazy initialization is still atomic within the single aiohttp process.
        lock = asyncio.Lock()
        app_state.study_analysis_request_lock = lock
    return lock


def _drop_study_analysis_works(
    app_state: PychessGlobalAppState, study_id: str, chapter_id: str | None = None
) -> int:
    works = getattr(app_state, "fishnet_works", None)
    if not works:
        return 0

    from fishnet import _compact_fishnet_queue

    ids = {
        work_id
        for work_id, work in tuple(works.items())
        if work["work"]["type"] == "analysis"
        and work.get("study_id") == study_id
        and (chapter_id is None or work.get("chapter_id") == chapter_id)
    }
    for work_id in ids:
        works.pop(work_id, None)
    if ids and hasattr(app_state, "fishnet_queue"):
        _compact_fishnet_queue(app_state)
    return len(ids)


def drop_study_analysis_work(
    app_state: PychessGlobalAppState, study_id: str, chapter_id: str
) -> int:
    return _drop_study_analysis_works(app_state, study_id, chapter_id)


def drop_study_analysis_works_for_study(app_state: PychessGlobalAppState, study_id: str) -> int:
    return _drop_study_analysis_works(app_state, study_id)


async def _load_study_and_chapter(
    app_state: PychessGlobalAppState, study_id: str, chapter_id: str
) -> tuple[Study, StudyChapter] | None:
    study_doc = await app_state.db.study.find_one({"_id": study_id})
    chapter_doc = await app_state.db.study_chapter.find_one(
        {"_id": chapter_id, "studyId": study_id}
    )
    if study_doc is None or chapter_doc is None:
        return None
    try:
        return Study.from_document(study_doc), StudyChapter.from_document(chapter_doc)
    except (TypeError, ValueError):
        return None


async def _broadcast_server_eval(
    app_state: PychessGlobalAppState,
    chapter: StudyChapter,
    server_eval: StudyServerEval,
    *,
    pending: bool,
) -> None:
    room = app_state.study_sockets.get(chapter.study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_analysis_progress",
            "studyId": chapter.study_id,
            "chapterId": chapter.id,
            "tree": chapter.root.to_payload(),
            "serverEval": server_eval.to_payload(pending=pending),
        },
    )


async def _broadcast_unavailable(
    app_state: PychessGlobalAppState, study_id: str, chapter_id: str, reason: str
) -> None:
    room = app_state.study_sockets.get(study_id)
    if not room:
        return
    await ws_send_json_many(
        tuple(room),
        {
            "type": "study_analysis_unavailable",
            "studyId": study_id,
            "chapterId": chapter_id,
            "reason": reason,
        },
    )


async def request_study_server_analysis(
    app_state: PychessGlobalAppState,
    *,
    study_id: str,
    chapter_id: str,
    username: str,
    now: datetime | None = None,
) -> StudyAnalysisRequestResult:
    """Queue a Lichess-style server analysis for the preferred chapter mainline."""

    loaded = await _load_study_and_chapter(app_state, study_id, chapter_id)
    if loaded is None:
        return StudyAnalysisRequestResult("not_found")
    study, chapter = loaded
    if not can_write_study(study, username):
        return StudyAnalysisRequestResult("forbidden")

    mainline = chapter.root.preferred_mainline()
    if len(mainline) < STUDY_ANALYSIS_MIN_MOVES:
        return StudyAnalysisRequestResult("too_short", chapter.server_eval)
    path = chapter.root.preferred_mainline_path()
    current = chapter.server_eval
    if current is not None and current.path == path:
        if current.done:
            return StudyAnalysisRequestResult("already_done", current)
        if has_pending_study_analysis(app_state, study_id, chapter_id):
            return StudyAnalysisRequestResult("already_requested", current, pending=True)
        requested_at = now or datetime.now(UTC)
        if requested_at - current.requested_at < STUDY_ANALYSIS_COOLDOWN:
            return StudyAnalysisRequestResult("already_requested", current)

    if has_pending_study_analysis_for_user(app_state, username):
        return StudyAnalysisRequestResult("concurrent_analysis", current)

    from fishnet import (
        fishnet_variants_payload_from_ini,
        has_available_fishnet_worker,
    )

    try:
        with study_variant_context(app_state, chapter.variant, chapter.variant_ini) as options:
            board = FairyBoard(
                options.runtime_variant,
                initial_fen=chapter.initial_fen,
                chess960=chapter.chess960,
                show_promoted=options.show_promoted,
                legal_moves_need_history=options.legal_moves_need_history,
            )
            work_variant = board.variant
            pinned_payload: dict[str, str] | None = None
            if chapter.variant_ini and options.runtime_variant != chapter.variant:
                aliased_ini = replace_variant_section_name(
                    chapter.variant_ini, options.runtime_variant
                )
                pinned_payload = fishnet_variants_payload_from_ini(
                    app_state, work_variant, aliased_ini
                )
    except Exception:
        log.info(
            "Study Fishnet analysis variant setup failed for %s/%s (%s)",
            study_id,
            chapter_id,
            chapter.variant,
            exc_info=True,
        )
        return StudyAnalysisRequestResult("variant_unavailable", current)

    if not has_available_fishnet_worker(app_state, variant=work_variant):
        return StudyAnalysisRequestResult("fishnet_unavailable", current)

    if not catalogued_variant_allows_fishnet(app_state, work_variant):
        return StudyAnalysisRequestResult("variant_unavailable", current)

    requested_at = now or datetime.now(UTC)
    async with _analysis_request_lock(app_state):
        # Different Studies have different mutation locks, so two tabs could reach
        # this point concurrently for the same account. Recheck under one short
        # process-wide admission lock before charging quota and queueing work.
        if has_pending_study_analysis_for_user(app_state, username):
            return StudyAnalysisRequestResult("concurrent_analysis", current)
        try:
            quota_claim = await claim_study_analysis_slot(
                app_state,
                username,
                now=requested_at,
            )
        except StudyQuotaExceeded as exc:
            if exc.code in {"daily_limit", "weekly_limit"}:
                return StudyAnalysisRequestResult(
                    cast(StudyAnalysisRequestStatus, exc.code), current
                )
            return StudyAnalysisRequestResult("forbidden", current)

        server_eval = StudyServerEval(path=path, done=False, requested_at=requested_at)
        result = await app_state.db.study_chapter.update_one(
            {"_id": chapter.id, "studyId": study.id},
            {"$set": {"serverEval": server_eval.to_document()}},
        )
        if result.matched_count != 1:
            await release_study_analysis_slot(app_state, username, quota_claim)
            return StudyAnalysisRequestResult("not_found")

        work_id = _new_work_id(app_state)
        work: FishnetWork = {
            "work": {"type": "analysis", "id": work_id},
            "study_id": study.id,
            "chapter_id": chapter.id,
            "study_path": path,
            "username": username,
            "position": chapter.initial_fen,
            "variant": work_variant,
            "chess960": chapter.chess960,
            "moves": " ".join(node.move for node in mainline),
            "nnue": board.nnue,
            "nodes": STUDY_ANALYSIS_NODES,
        }
        if pinned_payload is not None:
            work["variantsSha256"] = pinned_payload["variantsSha256"]
            work["variantsScope"] = pinned_payload["variantsScope"]
        app_state.fishnet_works[work_id] = work
        try:
            app_state.fishnet_queue.put_nowait((ANALYSIS, work_id))
        except Exception:
            app_state.fishnet_works.pop(work_id, None)
            await release_study_analysis_slot(app_state, username, quota_claim)
            if current is None:
                await app_state.db.study_chapter.update_one(
                    {"_id": chapter.id, "studyId": study.id},
                    {"$unset": {"serverEval": ""}},
                )
            else:
                await app_state.db.study_chapter.update_one(
                    {"_id": chapter.id, "studyId": study.id},
                    {"$set": {"serverEval": current.to_document()}},
                )
            raise

    chapter = replace(chapter, server_eval=server_eval)
    await _broadcast_server_eval(app_state, chapter, server_eval, pending=True)
    return StudyAnalysisRequestResult("started", server_eval, pending=True)


async def study_analysis_work_is_current(
    app_state: PychessGlobalAppState, work: FishnetWork
) -> bool:
    study_id = work.get("study_id")
    chapter_id = work.get("chapter_id")
    path = work.get("study_path")
    if not study_id or not chapter_id or path is None:
        return False
    loaded = await _load_study_and_chapter(app_state, study_id, chapter_id)
    if loaded is None:
        return False
    _, chapter = loaded
    server_eval = chapter.server_eval
    return (
        server_eval is not None
        and not server_eval.done
        and server_eval.path == path
        and chapter.root.preferred_mainline_path() == path
    )


def _merge_analysis_rows(
    chapter: StudyChapter,
    rows: list[FishnetAnalysisItem | None],
) -> tuple[tuple[AnalysisStep | None, ...], bool]:
    """Persist Study analysis in the same move-oriented shape lila exposes.

    Fairyfishnet evaluates positions, so row ``i`` is the position after move ``i``
    (row 0 is the initial position).  Lila attaches the score from the *after*
    position to the played move, but its explanatory variation comes from the
    engine PV in the *before* position.  Keep that distinction here instead of
    reusing the ordinary-game PV helper, whose stored PV has different semantics.
    """

    mainline = chapter.root.preferred_mainline()
    step_count = len(mainline) + 1
    bounded = rows[:step_count]
    merged = list(chapter.server_eval.analysis if chapter.server_eval is not None else ())
    if len(merged) < step_count:
        merged.extend([None] * (step_count - len(merged)))
    elif len(merged) > step_count:
        merged = merged[:step_count]

    for i, analysis in enumerate(bounded):
        if analysis is None or "score" not in analysis:
            continue
        existing = merged[i]
        step: AnalysisStep = dict(existing) if existing is not None else {}
        step["s"] = analysis["score"]
        if "depth" in analysis:
            step["d"] = analysis["depth"]

        # Lila has no advice for the first move because its synthetic starting
        # Info has no evaluation.  For later moves, save the best alternative
        # from the position *before* the played move only when that move is an
        # inaccuracy/mistake/blunder.
        if i >= 2:
            node = mainline[i - 1]
            previous_node = mainline[i - 2]
            previous_row = bounded[i - 1]
            pv = analysis_pv(previous_row, node.move)
            advice = (
                advice_for_move(
                    analysis_score(previous_row),
                    analysis_score(analysis),
                    previous_side_to_move=previous_node.turn_color,
                    current_side_to_move=node.turn_color,
                )
                if pv
                else None
            )
            if advice is not None:
                step["p"] = " ".join(pv)
        merged[i] = step

    complete = len(bounded) == step_count and all(row is not None for row in bounded)
    return tuple(merged), complete


def _has_generated_analysis_comment(node: StudyTreeNode) -> bool:
    return any(comment.author == ANALYSIS_COMMENT_AUTHOR for comment in node.annotations.comments)


def _merge_advice_annotations(
    node: StudyTreeNode,
    advice: MoveAdvice,
    best_san: str | None,
) -> StudyTreeNode:
    annotations = node.annotations
    comments = list(annotations.comments)
    nags = list(annotations.nags)

    if (
        not _has_generated_analysis_comment(node)
        and len(comments) < STUDY_MAX_COMMENTS_PER_POSITION
    ):
        comments.append(
            StudyComment(
                id=new_study_node_id(comment.id for comment in comments),
                author=ANALYSIS_COMMENT_AUTHOR,
                text=advice.comment(best_san),
            )
        )

    if advice.nag not in nags and len(nags) < STUDY_MAX_NAGS_PER_POSITION:
        nags.append(advice.nag)

    merged = StudyAnnotations(
        shapes=annotations.shapes,
        comments=tuple(comments),
        nags=tuple(nags),
    )
    return replace(node, annotations=merged)


def _new_analysis_board(
    chapter: StudyChapter,
    mainline: tuple[StudyTreeNode, ...],
    *,
    parent_ply: int,
    runtime_variant: str,
    show_promoted: bool,
    legal_moves_need_history: bool,
) -> FairyBoard:
    parent = mainline[parent_ply - 1] if parent_ply else None
    parent_fen = parent.fen if parent is not None else chapter.initial_fen
    if parent is not None and not legal_moves_need_history:
        return validated_study_position(
            runtime_variant,
            parent_fen,
            chess960=chapter.chess960,
            show_promoted=show_promoted,
        )

    board = FairyBoard(
        runtime_variant,
        initial_fen=chapter.initial_fen,
        chess960=chapter.chess960,
        show_promoted=show_promoted,
        legal_moves_need_history=legal_moves_need_history,
    )
    for node in mainline[:parent_ply]:
        board.push(node.move)
    if parent is not None and board.fen != parent_fen:
        raise ValueError("Study analysis parent reconstruction does not match stored FEN")
    return board


def _merge_analysis_line(
    chapter: StudyChapter,
    mainline: tuple[StudyTreeNode, ...],
    nodes: dict[str, StudyTreeNode],
    children: dict[str | None, list[str]],
    *,
    parent_ply: int,
    pv: list[str],
    runtime_variant: str,
    show_promoted: bool,
    legal_moves_need_history: bool,
) -> str | None:
    """Merge one validated Fishnet best line, reusing matching Study moves.

    Lila's tree ids are move-derived, so ``addChild`` naturally merges an engine
    line with an existing human variation. PyChess Study ids are random, therefore
    matching is by UCI move below the same parent. Validate the complete PV before
    mutating the tree so a malformed later move cannot leave a half-inserted engine
    line; lila similarly drops a variation when UCI-to-SAN conversion fails.
    """

    if not pv:
        return None
    board = _new_analysis_board(
        chapter,
        mainline,
        parent_ply=parent_ply,
        runtime_variant=runtime_variant,
        show_promoted=show_promoted,
        legal_moves_need_history=legal_moves_need_history,
    )

    prepared = prepare_analysis_line(board, pv)

    # Verify the already-existing prefix first. Once a move is missing, every
    # descendant below the new random id will necessarily be new as well.
    parent_id = mainline[parent_ply - 1].id if parent_ply else None
    for step in prepared:
        move, fen = step["move"], step["fen"]
        sibling_ids = children.get(parent_id, [])
        existing = next(
            (nodes[node_id] for node_id in sibling_ids if nodes[node_id].move == move),
            None,
        )
        if existing is None:
            break
        if existing.fen != fen:
            log.info(
                "Ignoring Study Fishnet PV with mismatched existing node %s for %s/%s",
                existing.id,
                chapter.study_id,
                chapter.id,
            )
            return None
        parent_id = existing.id

    parent_id = mainline[parent_ply - 1].id if parent_ply else None
    for step in prepared:
        move, fen = step["move"], step["fen"]
        sibling_ids = children.setdefault(parent_id, [])
        existing = next(
            (nodes[node_id] for node_id in sibling_ids if nodes[node_id].move == move),
            None,
        )
        if existing is not None:
            parent_id = existing.id
            continue

        if len(nodes) >= STUDY_MAX_NODES_PER_CHAPTER:
            break
        node_id = new_study_node_id(nodes)
        node = StudyTreeNode(
            id=node_id,
            parent_id=parent_id,
            order=len(sibling_ids),
            move=move,
            fen=fen,
            turn_color=step["turnColor"],
            check=step["check"],
            san=step["san"],
            san_san=step["sanSAN"],
        )
        nodes[node_id] = node
        sibling_ids.append(node_id)
        children.setdefault(node_id, [])
        parent_id = node_id

    return prepared[0]["san"] if prepared else None


def _merge_analysis_into_tree(
    app_state: PychessGlobalAppState,
    chapter: StudyChapter,
    rows: list[FishnetAnalysisItem | None],
) -> StudyTree:
    """Apply lila-style server evaluation, advice and PV branches to a Study tree."""

    mainline = chapter.root.preferred_mainline()
    if not mainline:
        return chapter.root

    nodes = dict(chapter.root.nodes)
    children: dict[str | None, list[str]] = {None: []}
    for node in nodes.values():
        children.setdefault(node.parent_id, []).append(node.id)
        children.setdefault(node.id, [])
    for sibling_ids in children.values():
        sibling_ids.sort(key=lambda node_id: nodes[node_id].order)

    try:
        with study_variant_context(app_state, chapter.variant, chapter.variant_ini) as options:
            for ply, mainline_node in enumerate(mainline, start=1):
                current_score = analysis_score(rows[ply] if ply < len(rows) else None)
                previous_row = rows[ply - 1] if ply - 1 < len(rows) else None
                current = nodes[mainline_node.id]
                previous_side_to_move = mainline[ply - 2].turn_color if ply >= 2 else None

                # Lila keeps a best-line variation only when the played move receives
                # advice. Its first move has no advice because Info.start has no eval,
                # and UciToSan drops all other non-meaningful variations before the
                # Study merger sees them.
                pv = analysis_pv(previous_row, mainline_node.move)
                advice: MoveAdvice | None = None
                if pv and previous_side_to_move is not None:
                    advice = advice_for_move(
                        analysis_score(previous_row),
                        current_score,
                        previous_side_to_move=previous_side_to_move,
                        current_side_to_move=current.turn_color,
                    )

                best_san: str | None = None
                if advice is not None:
                    try:
                        best_san = _merge_analysis_line(
                            chapter,
                            mainline,
                            nodes,
                            children,
                            parent_ply=ply - 1,
                            pv=pv,
                            runtime_variant=options.runtime_variant,
                            show_promoted=options.show_promoted,
                            legal_moves_need_history=options.legal_moves_need_history,
                        )
                    except Exception:
                        log.info(
                            "Study Fishnet PV conversion failed for %s/%s at ply %s",
                            chapter.study_id,
                            chapter.id,
                            ply,
                            exc_info=True,
                        )
                        advice = None
                    if best_san is None:
                        advice = None

                had_generated_comment = _has_generated_analysis_comment(current)
                if current_score is not None and (
                    current.eval_score is None or (advice is not None and not had_generated_comment)
                ):
                    current = replace(current, eval_score=current_score)
                if advice is not None:
                    current = _merge_advice_annotations(current, advice, best_san)
                nodes[current.id] = current
    except Exception:
        log.info(
            "Study Fishnet tree merge setup failed for %s/%s (%s)",
            chapter.study_id,
            chapter.id,
            chapter.variant,
            exc_info=True,
        )
        return chapter.root

    return StudyTree(
        nodes,
        root_annotations=chapter.root.root_annotations,
        root_gamebook=chapter.root.root_gamebook,
        root_eval_score=chapter.root.root_eval_score,
        root_clocks=chapter.root.root_clocks,
    )


async def _sized_tree_document(
    chapter: StudyChapter,
    root: StudyTree,
    server_eval: StudyServerEval,
) -> dict[str, object] | None:
    try:
        candidate = replace(chapter, root=root, server_eval=server_eval)
        encoded = await encode_chapter(candidate, include_document=True)
        if encoded.size <= STUDY_CHAPTER_MAX_BSON_BYTES:
            assert encoded.document is not None
            return cast(dict[str, object], encoded.document["root"])
    except Exception:
        log.exception(
            "Failed to size Study Fishnet tree merge for %s/%s",
            chapter.study_id,
            chapter.id,
        )
    return None


async def merge_study_server_analysis(
    app_state: PychessGlobalAppState,
    work_id: str,
    work: FishnetWork,
    rows: list[FishnetAnalysisItem | None],
) -> None:
    study_id = work.get("study_id")
    chapter_id = work.get("chapter_id")
    work_path = work.get("study_path")
    if not study_id or not chapter_id or work_path is None:
        app_state.fishnet_works.pop(work_id, None)
        return

    async with sequence_study(app_state, study_id):
        loaded = await _load_study_and_chapter(app_state, study_id, chapter_id)
        if loaded is None:
            app_state.fishnet_works.pop(work_id, None)
            return
        _, chapter = loaded
        current = chapter.server_eval
        if (
            current is None
            or current.done
            or current.path != work_path
            or chapter.root.preferred_mainline_path() != work_path
        ):
            app_state.fishnet_works.pop(work_id, None)
            return

        analysis, complete = _merge_analysis_rows(chapter, rows)
        server_eval = replace(current, done=complete, analysis=analysis)
        merged_root = _merge_analysis_into_tree(app_state, chapter, rows)
        set_fields: dict[str, object] = {"serverEval": server_eval.to_document()}
        if merged_root != chapter.root:
            root_document = await _sized_tree_document(chapter, merged_root, server_eval)
            if root_document is None:
                log.warning(
                    "Skipping Study Fishnet tree merge for %s/%s because the chapter size limit would be exceeded",
                    chapter.study_id,
                    chapter.id,
                )
                merged_root = chapter.root
            else:
                set_fields["root"] = root_document
        result = await app_state.db.study_chapter.update_one(
            {
                "_id": chapter.id,
                "studyId": chapter.study_id,
                "serverEval.path": work_path,
                "serverEval.done": False,
            },
            {"$set": set_fields},
        )
        if result.matched_count != 1:
            app_state.fishnet_works.pop(work_id, None)
            return

        chapter = replace(chapter, root=merged_root, server_eval=server_eval)
        await _broadcast_server_eval(app_state, chapter, server_eval, pending=not complete)
        if complete:
            app_state.fishnet_works.pop(work_id, None)
            from catalogued_variants import clear_catalogued_variant_ai_failures

            await clear_catalogued_variant_ai_failures(app_state, str(work.get("variant") or ""))


async def fail_study_server_analysis(
    app_state: PychessGlobalAppState,
    work: FishnetWork,
    *,
    reason: str,
) -> None:
    study_id = work.get("study_id")
    chapter_id = work.get("chapter_id")
    work_path = work.get("study_path")
    if not study_id or not chapter_id or work_path is None:
        return

    async with sequence_study(app_state, study_id):
        result = await app_state.db.study_chapter.update_one(
            {
                "_id": chapter_id,
                "studyId": study_id,
                "serverEval.path": work_path,
                "serverEval.done": False,
            },
            {"$unset": {"serverEval": ""}},
        )
        if result.matched_count == 1:
            log.info(
                "Study Fishnet analysis failed for %s/%s: %s",
                study_id,
                chapter_id,
                reason,
            )
            await _broadcast_unavailable(app_state, study_id, chapter_id, "fishnet_failed")
