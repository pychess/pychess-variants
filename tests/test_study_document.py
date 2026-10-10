from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import patch

from bson import BSON
from study.annotations import StudyAnnotations, StudyComment, StudyShape
from study.document import encode_chapter
from study.models import STUDY_CHAPTER_MODES, StudyChapter, StudyServerEval, StudySource
from study.mutations import StudyMutationService
from study.snapshot import chapter_snapshot_token
from study.storage import StudyStorageError, _ensure_chapter_size
from study.tree import StudyGamebook, StudyTree, StudyTreeNode


def make_chapter(count: int = 0) -> StudyChapter:
    nodes: dict[str, StudyTreeNode] = {}
    parent = None
    for index in range(count):
        node_id = f"N{index:09d}"
        nodes[node_id] = StudyTreeNode(
            id=node_id,
            parent_id=parent,
            order=0,
            move="e2e4",
            fen="after e4",
            turn_color="black",
            san="e4",
        )
        parent = node_id
    now = datetime(2026, 10, 8, tzinfo=UTC)
    return StudyChapter(
        id="chapter1",
        study_id="study001",
        name="Chapter",
        order=1,
        owner="owner",
        variant="chess",
        initial_fen="start",
        orientation="white",
        root=StudyTree(nodes),
        created_at=now,
        updated_at=now,
    )


class StudyDocumentTestCase(unittest.IsolatedAsyncioTestCase):
    async def assert_encoding_matches(self, chapter: StudyChapter) -> None:
        expected_document = chapter.to_document()
        expected_bson = BSON.encode(expected_document)
        expected_token = sha256(expected_bson).hexdigest()[:32]
        encoded = await encode_chapter(chapter, include_document=True, snapshot=True)
        self.assertEqual(encoded.size, len(expected_bson))
        self.assertEqual(encoded.document, expected_document)
        assert encoded.document is not None
        self.assertEqual(BSON.encode(encoded.document), expected_bson)
        self.assertEqual(encoded.snapshot_token, expected_token)
        self.assertEqual(await chapter_snapshot_token(chapter), expected_token)
        size_only = await encode_chapter(chapter)
        self.assertEqual(size_only.size, len(expected_bson))
        self.assertIsNone(size_only.document)
        self.assertIsNone(size_only.snapshot_token)

    async def test_empty_tree_and_batch_boundaries_match_complete_bson(self) -> None:
        for count in (0, 1, 31, 32, 33, 64, 65, 3000):
            with self.subTest(count=count):
                await self.assert_encoding_matches(make_chapter(count))

    async def test_all_optional_fields_unicode_and_field_order_match_complete_bson(self) -> None:
        chapter = make_chapter(65)
        annotations = StudyAnnotations(
            comments=(StudyComment("Comment001", "owner", "árvíztűrő 棋 ♟"),),
            shapes=(StudyShape("e4", "e5", "red"),),
            nags=(1, 3),
        )
        nodes = {
            node_id: replace(
                node,
                order=1,
                check=True,
                force_variation=node.id.endswith("3"),
                san_san="e4+",
                annotations=annotations,
                gamebook=StudyGamebook(hint="棋", deviation="Try ♟"),
                eval_score={"mate": -2},
                clocks=(300000, 299999.5),
            )
            for node_id, node in reversed(list(chapter.root.nodes.items()))
        }
        root = StudyTree(
            nodes,
            root_annotations=annotations,
            root_gamebook=StudyGamebook(hint="Root hint"),
            root_eval_score={"cp": 42},
            root_clocks=(300000, 300000),
        )
        chapter = replace(
            chapter,
            root=root,
            chess960=True,
            variant_ini="[custom:chess]\n",
            description="é 描述",
            tags={"Site": "PyChess", "Event": "棋"},
            source=StudySource("game", "Game0001"),
            revision=2**32,
            created_at=chapter.created_at.astimezone(timezone(timedelta(hours=2))),
            updated_at=chapter.updated_at.replace(tzinfo=None),
            server_eval=StudyServerEval(
                path="",
                done=True,
                requested_at=chapter.updated_at,
                analysis=(None, {"s": {"cp": 2**32}, "d": 20, "p": "e2e4 e7e5"}),
            ),
        )
        for mode in STUDY_CHAPTER_MODES:
            with self.subTest(mode=mode):
                await self.assert_encoding_matches(
                    replace(chapter, mode=mode, conceal_ply=2 if mode == "conceal" else None)
                )

    async def test_snapshot_detects_tree_and_analysis_changes_without_revision_change(self) -> None:
        chapter = make_chapter(33)
        original = await chapter_snapshot_token(chapter)
        last_id = next(reversed(dict(chapter.root.nodes)))
        changed_nodes = dict(chapter.root.nodes)
        changed_nodes[last_id] = replace(changed_nodes[last_id], eval_score={"cp": 42})
        tree_changed = replace(chapter, root=replace(chapter.root, nodes=changed_nodes))
        self.assertNotEqual(original, await chapter_snapshot_token(tree_changed))
        analysis_changed = replace(
            chapter,
            server_eval=StudyServerEval("", True, chapter.updated_at, ({"s": {"cp": 42}},)),
        )
        self.assertNotEqual(original, await chapter_snapshot_token(analysis_changed))
        self.assertEqual(chapter.revision, tree_changed.revision)
        self.assertEqual(chapter.revision, analysis_changed.revision)

    async def test_size_limit_accepts_exact_size_and_rejects_one_byte_less(self) -> None:
        chapter = make_chapter(33)
        expected = chapter.to_document()
        size = len(BSON.encode(expected))
        with (
            patch("study.storage.STUDY_CHAPTER_MAX_BSON_BYTES", size),
            patch("study.mutations.STUDY_CHAPTER_MAX_BSON_BYTES", size),
        ):
            self.assertEqual(await _ensure_chapter_size(chapter), expected)
            self.assertIsNone(await StudyMutationService._size_error(chapter))
        with (
            patch("study.storage.STUDY_CHAPTER_MAX_BSON_BYTES", size - 1),
            patch("study.mutations.STUDY_CHAPTER_MAX_BSON_BYTES", size - 1),
        ):
            with self.assertRaisesRegex(StudyStorageError, "too large"):
                await _ensure_chapter_size(chapter)
            error = await StudyMutationService._size_error(chapter)
            assert error is not None
            self.assertEqual(error.reason, "chapter_too_large")

    async def test_large_document_processing_allows_other_tasks_to_run(self) -> None:
        chapter = make_chapter(3000)
        progressed = asyncio.Event()

        async def other_task() -> None:
            progressed.set()

        for snapshot in (False, True):
            progressed.clear()
            task = asyncio.create_task(other_task())
            await encode_chapter(chapter, snapshot=snapshot)
            self.assertTrue(progressed.is_set())
            await task

    async def test_invalid_bson_is_still_rejected(self) -> None:
        chapter = make_chapter(1)
        node = next(iter(chapter.root.nodes.values()))
        chapter = replace(
            chapter, root=StudyTree({node.id: replace(node, eval_score={"cp": 2**80})})
        )
        with self.assertRaises(OverflowError):
            await encode_chapter(chapter)
        with self.assertRaisesRegex(StudyStorageError, "could not be encoded"):
            await _ensure_chapter_size(chapter)
