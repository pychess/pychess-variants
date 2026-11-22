from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from fairy.fairy_board import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from study.analysis import merge_study_server_analysis, request_study_server_analysis
from study.models import Study, StudyChapter
from study.mutations import StudyMutationService
from study.tree import StudyGamebook, StudyTree

STUDY_ID = "study001"
CHAPTER_ID = "chapter1"
OWNER = "owner"


class StudyServerAnalysisTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncMongoMockClient(tz_aware=True)
        self.db = self.client["pychess-test"]
        self.app_state = SimpleNamespace(
            db=self.db,
            catalogued_variants={},
            fishnet_works={},
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_variant_payloads={},
            study_sockets={},
            study_mutation_locks={},
            study_mutation_lock_refs={},
        )
        self.service = StudyMutationService(cast(Any, self.app_state))
        now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
        study = Study(
            id=STUDY_ID,
            name="Server analysis",
            owner=OWNER,
            members={OWNER: "write", "writer": "write", "reader": "read"},
            created_at=now,
            updated_at=now,
        )
        chapter = StudyChapter(
            id=CHAPTER_ID,
            study_id=STUDY_ID,
            name="Chapter 1",
            order=1,
            owner=OWNER,
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            orientation="white",
            root=StudyTree(),
            created_at=now,
            updated_at=now,
        )
        await self.db.study.insert_one(study.to_document())
        await self.db.study_chapter.insert_one(chapter.to_document())
        await self.db.user.insert_many(
            [
                {"_id": OWNER},
                {"_id": "writer"},
                {"_id": "reader"},
            ]
        )

    async def _add_line(
        self, moves: list[str], *, start_revision: int = 0, parent_path: str = ""
    ) -> tuple[str, int]:
        path = parent_path
        revision = start_revision
        for move in moves:
            result = await self.service.add_node(
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                parent_path=path,
                move=move,
                expected_revision=revision,
            )
            self.assertEqual(result.status, "ok")
            self.assertTrue(result.changed)
            assert result.path is not None
            assert result.revision is not None
            path = result.path
            revision = result.revision
        return path, revision

    async def _request(self, username: str = OWNER):
        with patch("fishnet.has_available_fishnet_worker", return_value=True):
            return await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=username,
            )

    async def test_request_requires_contributor_and_five_move_mainline(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6"])

        too_short = await self._request()
        self.assertEqual(too_short.status, "too_short")
        self.assertEqual(self.app_state.fishnet_works, {})

        path, revision = await self._add_line(
            ["f1b5"],
            start_revision=4,
            parent_path=(await self._chapter()).root.preferred_mainline_path(),
        )
        self.assertEqual(revision, 5)

        forbidden = await self._request("reader")
        self.assertEqual(forbidden.status, "forbidden")
        self.assertEqual(self.app_state.fishnet_works, {})

        started = await self._request("writer")
        self.assertEqual(started.status, "started")
        self.assertIsNotNone(started.server_eval)
        work = next(iter(self.app_state.fishnet_works.values()))
        self.assertEqual(work["study_id"], STUDY_ID)
        self.assertEqual(work["chapter_id"], CHAPTER_ID)
        self.assertEqual(work["study_path"], path)
        self.assertEqual(work["username"], "writer")
        self.assertEqual(work["variant"], "chess")
        self.assertEqual(work["position"], FairyBoard.start_fen("chess"))
        self.assertEqual(work["moves"], "e2e4 e7e5 g1f3 b8c6 f1b5")
        self.assertEqual(self.app_state.fishnet_queue.qsize(), 1)

        repeated = await self._request("writer")
        self.assertEqual(repeated.status, "already_requested")
        self.assertEqual(len(self.app_state.fishnet_works), 1)

    async def test_user_cannot_queue_two_study_analyses_at_once(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        self.app_state.fishnet_works["other1"] = {
            "work": {"type": "analysis", "id": "other1"},
            "study_id": "another1",
            "chapter_id": "another2",
            "username": OWNER,
        }

        result = await self._request()

        self.assertEqual(result.status, "concurrent_analysis")
        self.assertEqual(set(self.app_state.fishnet_works), {"other1"})
        account = await self.db.user.find_one({"_id": OWNER})
        assert account is not None
        self.assertNotIn("studyAnalysisHistory", account)

    async def test_analysis_request_honors_persisted_daily_and_weekly_budgets(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        requested_at = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        await self.db.user.update_one(
            {"_id": OWNER},
            {
                "$set": {
                    "studyAnalysisHistory": [
                        {"at": requested_at, "id": "today", "cost": 1},
                    ]
                }
            },
        )
        with (
            patch("study.quota.STUDY_ANALYSIS_MAX_PER_DAY", 1),
            patch("study.quota.STUDY_ANALYSIS_MAX_PER_WEEK", 10),
            patch("fishnet.has_available_fishnet_worker", return_value=True),
        ):
            daily = await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                now=requested_at,
            )
        self.assertEqual(daily.status, "daily_limit")
        self.assertEqual(self.app_state.fishnet_works, {})

        await self.db.user.update_one(
            {"_id": OWNER},
            {
                "$set": {
                    "studyAnalysisHistory": [
                        {
                            "at": requested_at - timedelta(days=2),
                            "id": "week",
                            "cost": 1,
                        },
                    ]
                }
            },
        )
        with (
            patch("study.quota.STUDY_ANALYSIS_MAX_PER_DAY", 10),
            patch("study.quota.STUDY_ANALYSIS_MAX_PER_WEEK", 1),
            patch("fishnet.has_available_fishnet_worker", return_value=True),
        ):
            weekly = await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                now=requested_at,
            )
        self.assertEqual(weekly.status, "weekly_limit")
        self.assertEqual(self.app_state.fishnet_works, {})

    async def test_partial_progress_persists_then_completion_finishes_work(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        started = await self._request()
        self.assertEqual(started.status, "started")
        work_id, work = next(iter(self.app_state.fishnet_works.items()))

        # Fairyfishnet analyses from the final position backwards. Progress is
        # cumulative: completed rows form a stable suffix and pending rows stay null.
        partial = [
            None,
            None,
            None,
            None,
            {"score": {"cp": 35}, "depth": 18},
            {"score": {"cp": 15}, "depth": 18},
        ]
        await merge_study_server_analysis(cast(Any, self.app_state), work_id, work, partial)

        chapter = await self._chapter()
        self.assertIsNotNone(chapter.server_eval)
        assert chapter.server_eval is not None
        self.assertFalse(chapter.server_eval.done)
        self.assertIsNone(chapter.server_eval.analysis[0])
        self.assertIsNone(chapter.server_eval.analysis[3])
        self.assertEqual(chapter.server_eval.analysis[4], {"s": {"cp": 35}, "d": 18})
        self.assertEqual(chapter.server_eval.analysis[5], {"s": {"cp": 15}, "d": 18})
        self.assertIn(work_id, self.app_state.fishnet_works)

        complete = [
            {"score": {"cp": 20}, "depth": 18},
            {"score": {"cp": -10}, "depth": 18},
            {"score": {"cp": 24}, "depth": 18},
            {"score": {"cp": 5}, "depth": 18},
            {"score": {"cp": 35}, "depth": 18},
            {"score": {"cp": 15}, "depth": 18},
        ]
        await merge_study_server_analysis(cast(Any, self.app_state), work_id, work, complete)

        chapter = await self._chapter()
        self.assertIsNotNone(chapter.server_eval)
        assert chapter.server_eval is not None
        self.assertTrue(chapter.server_eval.done)
        self.assertEqual(len(chapter.server_eval.analysis), 6)
        self.assertNotIn(work_id, self.app_state.fishnet_works)

        repeated = await self._request()
        self.assertEqual(repeated.status, "already_done")

    async def test_oversized_analysis_tree_merge_keeps_original_tree(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        original = await self._chapter()
        started = await self._request()
        self.assertEqual(started.status, "started")
        work_id, work = next(iter(self.app_state.fishnet_works.items()))
        rows = [{"score": {"cp": 25}, "depth": 18} for _ in range(6)]
        with (
            patch("study.analysis.STUDY_CHAPTER_MAX_BSON_BYTES", 1),
            self.assertLogs("study.analysis", level="WARNING"),
        ):
            await merge_study_server_analysis(cast(Any, self.app_state), work_id, work, rows)
        chapter = await self._chapter()
        self.assertEqual(chapter.root, original.root)
        self.assertEqual(chapter.revision, original.revision)
        assert chapter.server_eval is not None
        self.assertTrue(chapter.server_eval.done)
        self.assertEqual(len(chapter.server_eval.analysis), 6)
        self.assertNotIn(work_id, self.app_state.fishnet_works)

    async def test_analysis_merges_lila_style_evals_advice_and_best_lines(self) -> None:
        _, revision = await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        chapter = await self._chapter()
        mainline = chapter.root.preferred_mainline()
        e4_path = mainline[0].id
        e5_path = f"{mainline[0].id}.{mainline[1].id}"

        # Pre-existing human variations are reused rather than duplicated when the
        # Fishnet best line starts with the same move, just like lila's addChild.
        c5 = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path=e4_path,
            move="c7c5",
            expected_revision=revision,
        )
        self.assertEqual(c5.status, "ok")
        assert c5.node is not None
        assert c5.revision is not None
        existing_c5_id = c5.node.id

        human_comment = await self.service.set_comment(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e5_path,
            comment_id="HumanNote1",
            text="Human note",
            expected_revision=c5.revision,
        )
        self.assertEqual(human_comment.status, "ok")
        assert human_comment.revision is not None

        root_hint = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            field_name="hint",
            value="Keep the root hint",
            expected_revision=human_comment.revision,
        )
        self.assertEqual(root_hint.status, "ok")
        assert root_hint.revision is not None
        node_deviation = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e5_path,
            field_name="deviation",
            value="Keep the node fallback",
            expected_revision=root_hint.revision,
        )
        self.assertEqual(node_deviation.status, "ok")

        started = await self._request()
        self.assertEqual(started.status, "started")
        work_id, work = next(iter(self.app_state.fishnet_works.items()))

        # Fairyfishnet rows evaluate positions, not moves. Scores here are raw UCI
        # side-to-move scores. After 1.e4, -0.40 therefore means White +0.40;
        # after 1...e5, +4.00 means White +4.00, making ...e5 a blunder for Black.
        partial = [
            {"score": {"cp": 50}, "depth": 18, "pv": "d2d4 d7d5 c2c4"},
            {"score": {"cp": -40}, "depth": 18, "pv": "c7c5 g1f3 d7d6"},
            {"score": {"cp": 400}, "depth": 18, "pv": "f1c4 b8c6"},
            {"score": {"cp": -380}, "depth": 18, "pv": "b8c6 f1b5"},
            {"score": {"cp": 390}, "depth": 18, "pv": "f1b5 a7a6"},
            None,
        ]
        await merge_study_server_analysis(cast(Any, self.app_state), work_id, work, partial)

        chapter = await self._chapter()
        mainline = chapter.root.preferred_mainline()
        self.assertEqual(mainline[0].eval_score, {"cp": -40})
        self.assertEqual(mainline[1].eval_score, {"cp": 400})
        self.assertEqual(mainline[2].eval_score, {"cp": -380})

        e5 = mainline[1]
        self.assertEqual(chapter.root.root_gamebook, StudyGamebook(hint="Keep the root hint"))
        self.assertEqual(e5.gamebook, StudyGamebook(deviation="Keep the node fallback"))
        self.assertIn(4, e5.annotations.nags)
        self.assertTrue(any(comment.text == "Human note" for comment in e5.annotations.comments))
        generated = [comment for comment in e5.annotations.comments if comment.author == "PyChess"]
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].text, "Blunder. c5 was best.")
        self.assertNotIn(4, mainline[0].annotations.nags)

        # Lila drops best-line variations that do not carry advice. The root PV
        # therefore does not become a first-move alternative, and the small eval
        # loss after 2.Nf3 does not add the differing 2.Bc4 engine line either.
        root_moves = chapter.root.children_of(None)
        self.assertEqual([node.move for node in root_moves], ["e2e4"])
        e5_children = chapter.root.children_of(mainline[1].id)
        self.assertNotIn("f1c4", [node.move for node in e5_children])

        e4_children = chapter.root.children_of(mainline[0].id)
        self.assertEqual([node.move for node in e4_children], ["e7e5", "c7c5"])
        self.assertEqual(e4_children[1].id, existing_c5_id)
        c5_children = chapter.root.children_of(existing_c5_id)
        self.assertEqual([node.move for node in c5_children], ["g1f3"])
        self.assertEqual(c5_children[0].san, "Nf3")

        assert chapter.server_eval is not None
        self.assertNotIn("p", chapter.server_eval.analysis[1] or {})
        self.assertEqual((chapter.server_eval.analysis[2] or {}).get("p"), "c7c5 g1f3 d7d6")
        self.assertNotIn("p", chapter.server_eval.analysis[3] or {})

        # Partial reports can overlap. Re-merging the same Fishnet rows must not
        # duplicate engine comments, NAGs, or PV branches.
        node_count = chapter.root.count()
        await merge_study_server_analysis(cast(Any, self.app_state), work_id, work, partial)
        chapter = await self._chapter()
        self.assertEqual(chapter.root.count(), node_count)
        e5 = chapter.root.preferred_mainline()[1]
        self.assertEqual(
            sum(comment.author == "PyChess" for comment in e5.annotations.comments),
            1,
        )
        self.assertEqual(e5.annotations.nags.count(4), 1)
        self.assertEqual(
            sum(node.move == "c7c5" for node in chapter.root.children_of(mainline[0].id)),
            1,
        )

    async def test_interrupted_request_can_be_retried_after_cooldown(self) -> None:
        await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        requested_at = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
        with patch("fishnet.has_available_fishnet_worker", return_value=True):
            started = await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                now=requested_at,
            )
        self.assertEqual(started.status, "started")
        self.assertTrue(started.pending)

        # Simulate a server restart: persisted serverEval survives but the in-memory
        # Fishnet work queue does not. During the five-minute request window we
        # report the cooldown without pretending work is still running.
        self.app_state.fishnet_works.clear()
        while not self.app_state.fishnet_queue.empty():
            self.app_state.fishnet_queue.get_nowait()
            self.app_state.fishnet_queue.task_done()
        with patch("fishnet.has_available_fishnet_worker", return_value=True):
            cooling_down = await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                now=requested_at + timedelta(minutes=4),
            )
        self.assertEqual(cooling_down.status, "already_requested")
        self.assertFalse(cooling_down.pending)
        self.assertEqual(self.app_state.fishnet_works, {})

        with patch("fishnet.has_available_fishnet_worker", return_value=True):
            retried = await request_study_server_analysis(
                cast(Any, self.app_state),
                study_id=STUDY_ID,
                chapter_id=CHAPTER_ID,
                username=OWNER,
                now=requested_at + timedelta(minutes=5),
            )
        self.assertEqual(retried.status, "started")
        self.assertTrue(retried.pending)
        self.assertEqual(len(self.app_state.fishnet_works), 1)

    async def test_server_eval_parser_rejects_malformed_scores(self) -> None:
        chapter = await self._chapter()
        doc = chapter.to_document()
        doc["serverEval"] = {
            "path": "StudyNode1",
            "done": False,
            "requestedAt": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            "analysis": [{"s": {"cp": "not-a-number"}}],
        }
        with self.assertRaises(TypeError):
            StudyChapter.from_document(doc)

    async def test_mainline_change_invalidates_analysis_and_drops_queued_work(self) -> None:
        path, revision = await self._add_line(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"])
        started = await self._request()
        self.assertEqual(started.status, "started")
        self.assertEqual(len(self.app_state.fishnet_works), 1)

        extended = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path=path,
            move="a7a6",
            expected_revision=revision,
        )
        self.assertEqual(extended.status, "ok")
        self.assertTrue(extended.changed)
        self.assertEqual(self.app_state.fishnet_works, {})

        chapter_doc = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        assert chapter_doc is not None
        self.assertNotIn("serverEval", chapter_doc)

    async def _chapter(self) -> StudyChapter:
        doc = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        assert doc is not None
        return StudyChapter.from_document(doc)


if __name__ == "__main__":
    unittest.main()
