from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from fairy.fairy_board import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from study.annotations import StudyShape
from study.document import encode_chapter
from study.models import Study, StudyChapter
from study.mutations import StudyMutationService
from study.tree import StudyTree

STUDY_ID = "study001"
CHAPTER_ID = "chapter1"
OWNER = "owner"


class StudyMutationServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncMongoMockClient(tz_aware=True)
        self.db = self.client["pychess-test"]
        self.app_state = SimpleNamespace(db=self.db, catalogued_variants={})
        self.service = StudyMutationService(cast(Any, self.app_state))
        now = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
        study = Study(
            id=STUDY_ID,
            name="Study",
            owner=OWNER,
            members={OWNER: "write"},
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

    async def _chapter(self) -> StudyChapter:
        doc = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        assert doc is not None
        return StudyChapter.from_document(doc)

    async def _add(self, move: str, revision: int, parent_path: str = ""):
        return await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path=parent_path,
            move=move,
            expected_revision=revision,
        )

    async def test_cancelled_large_chapter_size_check_does_not_commit_mutation(self) -> None:
        added = await self._add("e2e4", 0)
        assert added.node is not None
        nodes = {}
        parent = None
        for index in range(65):
            node_id = f"N{index:09d}"
            nodes[node_id] = replace(added.node, id=node_id, parent_id=parent)
            parent = node_id
        await self.db.study_chapter.update_one(
            {"_id": CHAPTER_ID}, {"$set": {"root": StudyTree(nodes).to_document()}}
        )
        before = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        encoding_started = asyncio.Event()

        async def encode(chapter: StudyChapter):
            encoding_started.set()
            return await encode_chapter(chapter)

        with patch("study.mutations.encode_chapter", side_effect=encode):
            task = asyncio.create_task(
                self.service.set_comment(
                    study_id=STUDY_ID,
                    chapter_id=CHAPTER_ID,
                    username=OWNER,
                    path="",
                    comment_id="Comment001",
                    text="Interrupted annotation",
                    expected_revision=1,
                )
            )
            await encoding_started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(await self.db.study_chapter.find_one({"_id": CHAPTER_ID}), before)

    async def test_write_contributor_can_mutate_but_reader_cannot(self) -> None:
        await self.db.study.update_one(
            {"_id": STUDY_ID},
            {"$set": {"members": {OWNER: "write", "writer": "write", "reader": "read"}}},
        )

        writer = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username="writer",
            parent_path="",
            move="e2e4",
            expected_revision=0,
        )
        self.assertEqual(writer.status, "ok")
        self.assertTrue(writer.changed)

        reader = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username="reader",
            parent_path="",
            move="d2d4",
            expected_revision=1,
        )
        self.assertEqual(reader.status, "error")
        self.assertEqual(reader.reason, "forbidden")

    async def test_add_node_is_authoritative_and_deduplicates(self) -> None:
        added = await self._add("e2e4", 0)
        self.assertEqual(added.status, "ok")
        self.assertTrue(added.changed)
        self.assertEqual(added.revision, 1)
        self.assertIsNotNone(added.node)
        assert added.node is not None
        self.assertEqual(added.node.san, "e4")
        self.assertEqual(added.node.san_san, "e4")
        self.assertEqual(added.node.turn_color, "black")
        self.assertEqual(added.path, added.node.id)

        chapter = await self._chapter()
        self.assertEqual(chapter.revision, 1)
        self.assertEqual(chapter.root.nodes[added.node.id], added.node)

        duplicate = await self._add("e2e4", 1)
        self.assertEqual(duplicate.status, "ok")
        self.assertFalse(duplicate.changed)
        self.assertEqual(duplicate.revision, 1)
        self.assertEqual(duplicate.node, added.node)
        self.assertEqual((await self._chapter()).revision, 1)

    async def test_add_accepts_client_stable_node_id(self) -> None:
        added = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path="",
            move="e2e4",
            expected_revision=0,
            node_id="Client0001",
        )
        self.assertEqual(added.status, "ok")
        self.assertTrue(added.changed)
        self.assertEqual(added.path, "Client0001")
        self.assertIsNotNone(added.node)
        assert added.node is not None
        self.assertEqual(added.node.id, "Client0001")

        invalid = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path="",
            move="d2d4",
            expected_revision=1,
            node_id="bad",
        )
        self.assertEqual(invalid.status, "error")
        self.assertEqual(invalid.reason, "invalid_node_id")
        self.assertEqual((await self._chapter()).revision, 1)

    async def test_add_rejects_untrusted_parent_fen_before_native_move_generation(self) -> None:
        added = await self._add("e2e4", 0)
        assert added.node is not None
        for variant, fen in (
            ("chess", "not-a-fen b"),
            (
                "crazyhouse",
                FairyBoard.start_fen("crazyhouse").replace("[]", "[" + "P" * 1000 + "]"),
            ),
        ):
            with self.subTest(variant=variant):
                await self.db.study_chapter.update_one(
                    {"_id": CHAPTER_ID},
                    {"$set": {"variant": variant, f"root.{added.node.id}.f": fen}},
                )
                with patch("fairy.fairy_board.sf.legal_moves") as legal:
                    result = await self._add("e7e5", 1, added.node.id)
                self.assertEqual(result.reason, "invalid_chapter_tree")
                self.assertEqual((await self._chapter()).revision, 1)
                legal.assert_not_called()

    async def test_add_rejects_illegal_move_and_stale_revision(self) -> None:
        illegal = await self._add("e2e5", 0)
        self.assertEqual(illegal.status, "error")
        self.assertEqual(illegal.reason, "illegal_move")
        self.assertEqual((await self._chapter()).revision, 0)

        added = await self._add("e2e4", 0)
        self.assertEqual(added.status, "ok")
        stale = await self._add("d2d4", 0)
        self.assertEqual(stale.status, "reload")
        self.assertEqual(stale.reason, "revision_mismatch")
        self.assertEqual(stale.revision, 1)

    async def test_atomic_revision_guard_catches_race_after_initial_load(self) -> None:
        collection = self.db.study_chapter
        injected = False

        class RacingCollection:
            async def find_one(inner_self, *args, **kwargs):
                return await collection.find_one(*args, **kwargs)

            async def update_one(inner_self, query, update, *args, **kwargs):
                nonlocal injected
                if not injected and query.get("revision") == 0:
                    injected = True
                    await collection.update_one({"_id": CHAPTER_ID}, {"$set": {"revision": 1}})
                return await collection.update_one(query, update, *args, **kwargs)

        self.service.db = SimpleNamespace(
            study=self.db.study,
            study_chapter=RacingCollection(),
        )
        result = await self._add("e2e4", 0)

        self.assertEqual(result.status, "reload")
        self.assertEqual(result.reason, "revision_mismatch")
        self.assertEqual(result.revision, 1)
        chapter = await self._chapter()
        self.assertEqual(chapter.revision, 1)
        self.assertEqual(chapter.root.count(), 0)

    async def test_owner_only_and_invalid_path_are_structured_results(self) -> None:
        forbidden = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username="other",
            parent_path="",
            move="e2e4",
            expected_revision=0,
        )
        self.assertEqual(forbidden.status, "error")
        self.assertEqual(forbidden.reason, "forbidden")

        invalid_path = await self.service.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path="NotANode01",
            move="e2e4",
            expected_revision=0,
        )
        self.assertEqual(invalid_path.status, "reload")
        self.assertEqual(invalid_path.reason, "invalid_path")

    async def test_delete_branch_removes_descendants_and_renumbers_siblings(self) -> None:
        e4 = await self._add("e2e4", 0)
        d4 = await self._add("d2d4", 1)
        assert e4.path is not None and d4.node is not None
        e5 = await self._add("e7e5", 2, e4.path)
        assert e5.path is not None
        nf3 = await self._add("g1f3", 3, e5.path)
        assert nf3.path is not None

        deleted = await self.service.delete_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e4.path,
            expected_revision=4,
        )
        self.assertEqual(deleted.status, "ok")
        self.assertTrue(deleted.changed)
        self.assertEqual(deleted.revision, 5)

        chapter = await self._chapter()
        self.assertEqual(chapter.root.count(), 1)
        remaining = chapter.root.children_of(None)
        self.assertEqual([node.id for node in remaining], [d4.node.id])
        self.assertEqual(remaining[0].order, 0)

    async def test_promote_matches_client_one_level_and_to_mainline_semantics(self) -> None:
        e4 = await self._add("e2e4", 0)
        d4 = await self._add("d2d4", 1)
        assert e4.path is not None and d4.path is not None
        e5 = await self._add("e7e5", 2, e4.path)
        c5 = await self._add("c7c5", 3, e4.path)
        assert e5.node is not None and c5.path is not None and c5.node is not None

        promoted = await self.service.promote_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=c5.path,
            to_mainline=False,
            expected_revision=4,
        )
        self.assertEqual(promoted.status, "ok")
        chapter = await self._chapter()
        self.assertEqual(
            [node.id for node in chapter.root.children_of(e4.node.id)],
            [c5.node.id, e5.node.id],
        )
        self.assertEqual(
            [node.id for node in chapter.root.children_of(None)], [e4.node.id, d4.node.id]
        )

        to_mainline = await self.service.promote_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=d4.path,
            to_mainline=True,
            expected_revision=5,
        )
        self.assertEqual(to_mainline.status, "ok")
        chapter = await self._chapter()
        self.assertEqual(
            [node.id for node in chapter.root.children_of(None)], [d4.node.id, e4.node.id]
        )

    async def test_conceal_boundary_clamps_when_mainline_is_promoted_or_deleted(self) -> None:
        e4 = await self._add("e2e4", 0)
        assert e4.path is not None
        e5 = await self._add("e7e5", 1, e4.path)
        c5 = await self._add("c7c5", 2, e4.path)
        assert e5.path is not None and c5.path is not None
        await self.db.study_chapter.update_one(
            {"_id": CHAPTER_ID},
            {"$set": {"mode": "conceal", "concealPly": 2}},
        )

        promoted = await self.service.promote_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=c5.path,
            to_mainline=False,
            expected_revision=3,
        )
        self.assertEqual(promoted.status, "ok")
        self.assertTrue(promoted.conceal_changed)
        self.assertEqual(promoted.conceal_ply, 1)
        self.assertEqual((await self._chapter()).conceal_ply, 1)

        # Reveal the new second ply, then remove it. Deletion keeps only the still
        # unchanged first mainline move revealed.
        await self.db.study_chapter.update_one(
            {"_id": CHAPTER_ID},
            {"$set": {"concealPly": 2}},
        )
        deleted = await self.service.delete_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=c5.path,
            expected_revision=4,
        )
        self.assertEqual(deleted.status, "ok")
        self.assertTrue(deleted.conceal_changed)
        self.assertEqual(deleted.conceal_ply, 1)
        self.assertEqual((await self._chapter()).conceal_ply, 1)

    async def test_force_variation_keeps_only_one_marker(self) -> None:
        e4 = await self._add("e2e4", 0)
        d4 = await self._add("d2d4", 1)
        assert (
            e4.path is not None
            and d4.path is not None
            and e4.node is not None
            and d4.node is not None
        )

        first = await self.service.force_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e4.path,
            force=True,
            expected_revision=2,
        )
        self.assertEqual(first.revision, 3)

        second = await self.service.force_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=d4.path,
            force=True,
            expected_revision=3,
        )
        self.assertEqual(second.revision, 4)
        chapter = await self._chapter()
        self.assertFalse(chapter.root.nodes[e4.node.id].force_variation)
        self.assertTrue(chapter.root.nodes[d4.node.id].force_variation)

        noop = await self.service.force_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=d4.path,
            force=True,
            expected_revision=4,
        )
        self.assertEqual(noop.status, "ok")
        self.assertFalse(noop.changed)
        self.assertEqual(noop.revision, 4)

    async def test_root_and_node_annotations_are_incremental_and_survive_tree_edits(self) -> None:
        root_shapes = await self.service.set_shapes(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            shapes=[{"orig": "e4", "dest": "e5", "brush": "red", "ignored": True}],
            expected_revision=0,
        )
        self.assertEqual(root_shapes.status, "ok")
        self.assertEqual(root_shapes.revision, 1)
        self.assertEqual(root_shapes.annotations.shapes, (StudyShape("e4", "e5", "red"),))  # type: ignore[union-attr]

        e4 = await self._add("e2e4", 1)
        assert e4.path is not None and e4.node is not None
        comment = await self.service.set_comment(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e4.path,
            comment_id="Comment001",
            text="  useful https://tinyurl.com/bad  ",
            expected_revision=2,
        )
        self.assertEqual(comment.status, "ok")
        self.assertEqual(comment.revision, 3)
        assert comment.annotations is not None
        self.assertEqual(comment.annotations.comments[0].author, OWNER)
        self.assertEqual(comment.annotations.comments[0].text, "useful [redacted]")

        nags = await self.service.set_nags(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=e4.path,
            nags=[1, 3, 1],
            expected_revision=3,
        )
        self.assertEqual(nags.revision, 4)
        assert nags.annotations is not None
        self.assertEqual(nags.annotations.nags, (1, 3))

        d4 = await self._add("d2d4", 4)
        assert d4.path is not None
        promoted = await self.service.promote_variation(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=d4.path,
            to_mainline=True,
            expected_revision=5,
        )
        self.assertEqual(promoted.revision, 6)

        chapter = await self._chapter()
        self.assertEqual(chapter.root.root_annotations.shapes, (StudyShape("e4", "e5", "red"),))
        self.assertEqual(chapter.root.nodes[e4.node.id].annotations.nags, (1, 3))
        self.assertEqual(chapter.root.nodes[e4.node.id].annotations.comments[0].id, "Comment001")

        raw = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        assert raw is not None
        self.assertIn("a", raw["root"]["_"])
        self.assertIn("a", raw["root"][e4.node.id])

    async def test_clear_annotations_and_chapter_metadata_canonicalization(self) -> None:
        shaped = await self.service.set_shapes(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            shapes=[{"orig": "a1", "brush": "blue"}],
            expected_revision=0,
        )
        self.assertEqual(shaped.revision, 1)
        lesson = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            field_name="hint",
            value="Lesson hint",
            expected_revision=1,
        )
        self.assertEqual(lesson.revision, 2)

        cleared = await self.service.clear_annotations(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            expected_revision=2,
        )
        self.assertTrue(cleared.changed)
        self.assertEqual(cleared.revision, 3)
        assert cleared.annotations is not None
        assert cleared.gamebook is not None
        self.assertTrue(cleared.annotations.empty)
        self.assertTrue(cleared.gamebook.empty)

        description = await self.service.set_description(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            description="  Line one\r\nLine two  ",
            expected_revision=3,
        )
        self.assertEqual(description.description, "Line one\nLine two")
        self.assertEqual(description.revision, 4)

        tags = await self.service.set_tags(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            tags={"Site": " PyChess ", "Event": " Study test ", "Empty": "  "},
            expected_revision=4,
        )
        self.assertEqual(tags.tags, {"Event": "Study test", "Site": "PyChess"})
        self.assertEqual(tags.revision, 5)

        chapter = await self._chapter()
        self.assertTrue(chapter.root.root_annotations.empty)
        self.assertTrue(chapter.root.root_gamebook.empty)
        self.assertEqual(chapter.description, "Line one\nLine two")
        self.assertEqual(chapter.tags, {"Event": "Study test", "Site": "PyChess"})
        raw = await self.db.study_chapter.find_one({"_id": CHAPTER_ID})
        assert raw is not None
        self.assertNotIn("a", raw["root"]["_"])
        self.assertNotIn("g", raw["root"]["_"])
        raw_study = await self.db.study.find_one({"_id": STUDY_ID})
        assert raw_study is not None
        self.assertIn("line", raw_study["searchTokens"])
        self.assertIn("pychess", raw_study["searchTokens"])

    async def test_annotation_validation_rejects_without_revision_change(self) -> None:
        invalid_shape = await self.service.set_shapes(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            shapes=[{"orig": "z99", "brush": "green"}],
            expected_revision=0,
        )
        self.assertEqual(invalid_shape.status, "error")
        self.assertEqual(invalid_shape.reason, "invalid_shapes")

        invalid_comment = await self.service.set_comment(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            comment_id="bad",
            text="comment",
            expected_revision=0,
        )
        self.assertEqual(invalid_comment.reason, "invalid_comment_id")

        invalid_tags = await self.service.set_tags(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            tags={"Bad Tag": "value"},
            expected_revision=0,
        )
        self.assertEqual(invalid_tags.reason, "invalid_tags")
        self.assertEqual((await self._chapter()).revision, 0)

    async def test_node_and_bson_limits_reject_without_partial_write(self) -> None:
        first = await self._add("e2e4", 0)
        self.assertEqual(first.revision, 1)

        with patch("study.mutations.STUDY_MAX_NODES_PER_CHAPTER", 1):
            limited = await self._add("d2d4", 1)
        self.assertEqual(limited.status, "error")
        self.assertEqual(limited.reason, "node_limit")
        self.assertEqual((await self._chapter()).revision, 1)

        with patch("study.mutations.STUDY_CHAPTER_MAX_BSON_BYTES", 1):
            overweight = await self._add("d2d4", 1)
        self.assertEqual(overweight.status, "error")
        self.assertEqual(overweight.reason, "chapter_too_large")
        chapter = await self._chapter()
        self.assertEqual(chapter.revision, 1)
        self.assertEqual(chapter.root.count(), 1)

    async def test_gamebook_field_mutations_merge_without_overwriting_other_metadata(self) -> None:
        added = await self._add("e2e4", 0)
        assert added.path is not None

        hint = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            field_name="hint",
            value="  Look at the center  ",
            expected_revision=1,
        )
        self.assertEqual(hint.status, "ok")
        self.assertTrue(hint.changed)
        self.assertEqual(hint.gamebook.to_payload(), {"hint": "Look at the center"})  # type: ignore[union-attr]

        # Room sequencing may accept a contributor operation created against the
        # previous revision. Field-specific writes must merge instead of replacing
        # the whole gamebook object.
        rebasing = StudyMutationService(cast(Any, self.app_state), allow_stale_revision=True)
        deviation = await rebasing.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path="",
            field_name="deviation",
            value="Try the mainline move",
            expected_revision=1,
        )
        self.assertEqual(deviation.status, "ok")
        chapter = await self._chapter()
        self.assertEqual(
            chapter.root.root_gamebook.to_payload(),
            {"hint": "Look at the center", "deviation": "Try the mainline move"},
        )

        node_hint = await rebasing.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=added.path,
            field_name="hint",
            value="Develop quickly",
            expected_revision=chapter.revision,
        )
        self.assertEqual(node_hint.status, "ok")
        chapter = await self._chapter()
        self.assertEqual(chapter.root.node_at_path(added.path).gamebook.hint, "Develop quickly")  # type: ignore[union-attr]

        # An unrelated tree edit must retain root and node lesson metadata.
        unrelated = await rebasing.add_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            parent_path="",
            move="d2d4",
            expected_revision=chapter.revision,
        )
        self.assertEqual(unrelated.status, "ok")
        chapter = await self._chapter()
        self.assertEqual(chapter.root.root_gamebook.hint, "Look at the center")
        self.assertEqual(chapter.root.node_at_path(added.path).gamebook.hint, "Develop quickly")  # type: ignore[union-attr]

    async def test_gamebook_deleted_target_requests_reload_and_empty_text_removes_field(
        self,
    ) -> None:
        added = await self._add("e2e4", 0)
        assert added.path is not None
        set_hint = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=added.path,
            field_name="hint",
            value="Hint",
            expected_revision=1,
        )
        self.assertEqual(set_hint.revision, 2)
        cleared = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=added.path,
            field_name="hint",
            value="   ",
            expected_revision=2,
        )
        self.assertEqual(cleared.gamebook.to_payload(), {})  # type: ignore[union-attr]
        chapter = await self._chapter()
        self.assertTrue(chapter.root.node_at_path(added.path).gamebook.empty)  # type: ignore[union-attr]

        deleted = await self.service.delete_node(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=added.path,
            expected_revision=3,
        )
        self.assertEqual(deleted.revision, 4)
        missing = await self.service.set_gamebook(
            study_id=STUDY_ID,
            chapter_id=CHAPTER_ID,
            username=OWNER,
            path=added.path,
            field_name="deviation",
            value="Too late",
            expected_revision=4,
        )
        self.assertEqual(missing.status, "reload")
        self.assertEqual(missing.reason, "invalid_path")

    def test_catalogued_snapshot_restores_current_active_definition(self) -> None:
        snapshot = "[studycustom:chess]\ncustomPiece1 = a:KN\n"
        current = "[studycustom:chess]\ncustomPiece1 = a:BN\n"
        self.app_state.catalogued_variants["studycustom"] = {"ini": current}
        now = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
        chapter = StudyChapter(
            id=CHAPTER_ID,
            study_id=STUDY_ID,
            name="Custom",
            order=1,
            owner=OWNER,
            variant="studycustom",
            initial_fen=FairyBoard.start_fen("chess"),
            orientation="white",
            root=StudyTree(),
            created_at=now,
            updated_at=now,
            variant_ini=snapshot,
        )

        with patch("study.variant.validate_catalogued_ini") as validate_ini:
            validate_ini.return_value = SimpleNamespace(
                name="studysnap_test",
                start_fen=FairyBoard.start_fen("chess"),
                show_promoted=False,
            )
            with self.service._chapter_variant(chapter) as options:
                self.assertEqual(options.runtime_variant, "studysnap_test")

        self.assertEqual(validate_ini.call_count, 1)


if __name__ == "__main__":
    unittest.main()
