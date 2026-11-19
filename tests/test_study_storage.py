from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from fairy import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from study.annotations import StudyAnnotations, StudyComment
from study.builder import StudyChapterDraft
from study.models import STUDY_CHAPTER_MODES, StudySource
from study.storage import (
    StudyStorageError,
    add_chapter,
    add_chapter_from_draft,
    add_study_member,
    autocomplete_study_topics,
    chapter_previews,
    clear_chapter_annotations,
    clear_chapter_variations,
    clone_study,
    contributed_studies_page,
    count_studies_for_owner_view,
    create_study_from_draft,
    create_study_from_drafts,
    create_study_with_chapter,
    delete_chapter,
    delete_study,
    edit_chapter_metadata,
    leave_study,
    load_owned_chapter,
    load_owned_study,
    member_study_topics,
    owner_studies_page,
    owner_view_studies_page,
    popular_study_topics,
    remove_study_member,
    rename_chapter,
    rename_study,
    select_chapter,
    set_study_member_role,
    set_study_topics,
    set_study_visibility,
    studies_for_owner,
    study_list_chapter_names,
    study_search_page,
    topic_studies_page,
)
from study.tree import StudyGamebook, StudyTree, StudyTreeNode


class StudyStorageTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.mode_gate = patch("study.models.STUDY_ENABLED_CHAPTER_MODES", STUDY_CHAPTER_MODES)
        self.mode_gate.start()
        self.addCleanup(self.mode_gate.stop)
        self.client = AsyncMongoMockClient(tz_aware=True)
        self.db = self.client["pychess-test"]
        self.app_state = SimpleNamespace(db=self.db)

    async def test_multi_draft_creation_rolls_back_when_later_batch_fails(self) -> None:
        drafts = [
            StudyChapterDraft(
                variant="chess", initial_fen=FairyBoard.start_fen("chess"), name="One"
            ),
            StudyChapterDraft(
                variant="chess", initial_fen=FairyBoard.start_fen("chess"), name="Two"
            ),
        ]
        with (
            patch(
                "study.storage.add_chapters_from_drafts",
                new=AsyncMock(side_effect=StudyStorageError("simulated import failure")),
            ),
            self.assertRaisesRegex(StudyStorageError, "simulated import failure"),
        ):
            await create_study_from_drafts(
                cast(Any, self.app_state), "owner", drafts, name="Atomic import"
            )

        self.assertEqual(await self.db.study.count_documents({"owner": "owner"}), 0)
        self.assertEqual(await self.db.study_chapter.count_documents({"owner": "owner"}), 0)

    async def test_create_list_and_owner_lookup(self) -> None:
        study, chapter = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Opening ideas"
        )

        self.assertEqual(study.current_chapter, chapter.id)
        self.assertEqual(chapter.variant, "chess")
        self.assertEqual(chapter.initial_fen, FairyBoard.start_fen("chess"))
        self.assertEqual(chapter.order, 1)

        loaded = await load_owned_study(cast(Any, self.app_state), study.id, "owner")
        assert loaded is not None
        self.assertEqual(
            (loaded.id, loaded.name, loaded.current_chapter), (study.id, study.name, chapter.id)
        )
        self.assertIsNone(await load_owned_study(cast(Any, self.app_state), study.id, "other"))
        listed = (await studies_for_owner(cast(Any, self.app_state), "owner"))[0]
        self.assertEqual((listed.id, listed.name), (study.id, study.name))

    async def test_owner_view_listing_keeps_unlisted_and_private_out_of_profiles(self) -> None:
        private, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Private ideas"
        )
        unlisted, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Link-only ideas"
        )
        public, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Public ideas"
        )
        await set_study_visibility(cast(Any, self.app_state), unlisted, "unlisted")
        await set_study_visibility(cast(Any, self.app_state), public, "public")

        for viewer, expected in (
            ("owner", {private.id, unlisted.id, public.id}),
            (None, {public.id}),
            ("other", {public.id}),
        ):
            result = await owner_view_studies_page(cast(Any, self.app_state), "owner", viewer)
            self.assertEqual({study.id for study in result["studies"]}, expected)
        self.assertEqual(
            await count_studies_for_owner_view(cast(Any, self.app_state), "owner", "owner"), 3
        )
        self.assertEqual(
            await count_studies_for_owner_view(cast(Any, self.app_state), "owner", "other"), 1
        )

    async def test_personal_list_pages_filter_contributions_and_order(self) -> None:
        private, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Zulu private"
        )
        unlisted, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Mike unlisted"
        )
        public, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Alpha public"
        )
        await set_study_visibility(cast(Any, self.app_state), unlisted, "unlisted")
        await set_study_visibility(cast(Any, self.app_state), public, "public")

        contributed, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "other", name="Contributor lab"
        )
        await add_study_member(cast(Any, self.app_state), contributed.id, "other", "owner", "write")
        read_only, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "reader_owner", name="Read-only lab"
        )
        await add_study_member(
            cast(Any, self.app_state), read_only.id, "reader_owner", "owner", "read"
        )

        mine = await owner_studies_page(cast(Any, self.app_state), "owner", order="alphabetical")
        self.assertEqual(
            [study.name for study in mine["studies"]],
            ["Alpha public", "Mike unlisted", "Zulu private"],
        )

        base = datetime(2026, 1, 1, tzinfo=UTC)
        await self.db.study.update_one(
            {"_id": private.id},
            {"$set": {"createdAt": base, "updatedAt": base + timedelta(days=3)}},
        )
        await self.db.study.update_one(
            {"_id": unlisted.id},
            {
                "$set": {
                    "createdAt": base + timedelta(days=1),
                    "updatedAt": base + timedelta(days=1),
                }
            },
        )
        await self.db.study.update_one(
            {"_id": public.id},
            {
                "$set": {
                    "createdAt": base + timedelta(days=2),
                    "updatedAt": base + timedelta(days=2),
                }
            },
        )
        newest = await owner_studies_page(cast(Any, self.app_state), "owner", order="newest")
        oldest = await owner_studies_page(cast(Any, self.app_state), "owner", order="oldest")
        updated = await owner_studies_page(cast(Any, self.app_state), "owner", order="updated")
        self.assertEqual(
            [study.id for study in newest["studies"]],
            [public.id, unlisted.id, private.id],
        )
        self.assertEqual(
            [study.id for study in oldest["studies"]],
            [private.id, unlisted.id, public.id],
        )
        self.assertEqual(
            [study.id for study in updated["studies"]],
            [private.id, public.id, unlisted.id],
        )

        public_only = await owner_studies_page(
            cast(Any, self.app_state), "owner", visibility="public"
        )
        self.assertEqual([study.id for study in public_only["studies"]], [public.id])

        private_like = await owner_studies_page(
            cast(Any, self.app_state), "owner", visibility="private-or-unlisted"
        )
        self.assertEqual(
            {study.id for study in private_like["studies"]},
            {private.id, unlisted.id},
        )

        contributed_page = await contributed_studies_page(cast(Any, self.app_state), "owner")
        self.assertEqual(
            {study.id for study in contributed_page["studies"]},
            {contributed.id, read_only.id},
        )

    async def test_member_lifecycle_preserves_owner_and_enforces_cap(self) -> None:
        study, _ = await create_study_with_chapter(cast(Any, self.app_state), "owner")

        study = await add_study_member(
            cast(Any, self.app_state), study.id, "owner", "writer", "write"
        )
        self.assertEqual(study.members, {"owner": "write", "writer": "write"})

        study = await set_study_member_role(
            cast(Any, self.app_state), study.id, "owner", "writer", "read"
        )
        self.assertEqual(study.members["writer"], "read")

        with (
            patch("study.storage.STUDY_MAX_MEMBERS", 2),
            self.assertRaisesRegex(StudyStorageError, "at most 2 members"),
        ):
            await add_study_member(cast(Any, self.app_state), study.id, "owner", "third")

        study = await remove_study_member(cast(Any, self.app_state), study.id, "owner", "writer")
        self.assertEqual(study.members, {"owner": "write"})

        study = await add_study_member(cast(Any, self.app_state), study.id, "owner", "reader")
        study = await leave_study(cast(Any, self.app_state), study.id, "reader")
        self.assertEqual(study.members, {"owner": "write"})

        with self.assertRaisesRegex(StudyStorageError, "owner cannot"):
            await leave_study(cast(Any, self.app_state), study.id, "owner")
        with self.assertRaisesRegex(StudyStorageError, "Only the Study owner"):
            await add_study_member(cast(Any, self.app_state), study.id, "reader", "other")

    async def test_topics_support_discovery_search_and_contributor_updates(self) -> None:
        public, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Public repertoire"
        )
        await set_study_visibility(cast(Any, self.app_state), public, "public")
        updated, changed = await set_study_topics(
            cast(Any, self.app_state), public.id, "owner", ["King pawn", "Endgame"]
        )
        self.assertTrue(changed)
        self.assertEqual(updated.topics, ("King pawn", "Endgame"))

        public_topic = await topic_studies_page(cast(Any, self.app_state), "King pawn", viewer=None)
        self.assertEqual([study.id for study in public_topic["studies"]], [public.id])
        self.assertEqual(
            await popular_study_topics(cast(Any, self.app_state)),
            ["Endgame", "King pawn"],
        )
        search = await study_search_page(cast(Any, self.app_state), q="king pawn", viewer=None)
        self.assertEqual([study.id for study in search["studies"]], [public.id])

        private, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "other", name="Private preparation"
        )
        private = await add_study_member(
            cast(Any, self.app_state), private.id, "other", "owner", "write"
        )
        private, changed = await set_study_topics(
            cast(Any, self.app_state), private.id, "owner", ["Secret prep"]
        )
        self.assertTrue(changed)
        self.assertEqual(
            (await topic_studies_page(cast(Any, self.app_state), "Secret prep", viewer=None))[
                "studies"
            ],
            [],
        )
        member_topic = await topic_studies_page(
            cast(Any, self.app_state), "Secret prep", viewer="owner"
        )
        self.assertEqual([study.id for study in member_topic["studies"]], [private.id])
        self.assertEqual(
            set(await member_study_topics(cast(Any, self.app_state), "owner")),
            {"King pawn", "Endgame", "Secret prep"},
        )
        self.assertEqual(
            await autocomplete_study_topics(cast(Any, self.app_state), "ki", viewer=None),
            ["King pawn"],
        )
        self.assertEqual(
            await autocomplete_study_topics(cast(Any, self.app_state), "se", viewer="owner"),
            ["Secret prep"],
        )
        self.assertEqual(
            await autocomplete_study_topics(cast(Any, self.app_state), "se", viewer=None),
            [],
        )
        self.assertEqual(
            await autocomplete_study_topics(cast(Any, self.app_state), "x" * 51, viewer="owner"),
            [],
        )

        private = await add_study_member(
            cast(Any, self.app_state), private.id, "other", "reader", "read"
        )
        with self.assertRaisesRegex(StudyStorageError, "cannot edit"):
            await set_study_topics(cast(Any, self.app_state), private.id, "reader", ["Should fail"])

    async def test_topic_aggregations_support_async_pymongo_aggregate(self) -> None:
        public, _ = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Public repertoire"
        )
        await set_study_visibility(cast(Any, self.app_state), public, "public")
        await set_study_topics(
            cast(Any, self.app_state), public.id, "owner", ["King pawn", "Endgame"]
        )

        aggregate = AsyncMock(side_effect=self.db.study.aggregate)
        app_state = SimpleNamespace(db=SimpleNamespace(study=SimpleNamespace(aggregate=aggregate)))
        self.assertEqual(
            await popular_study_topics(cast(Any, app_state)),
            ["Endgame", "King pawn"],
        )
        self.assertEqual(
            await autocomplete_study_topics(cast(Any, app_state), "ki", viewer=None),
            ["King pawn"],
        )

        self.assertEqual(aggregate.await_count, 2)

    async def test_create_from_draft_persists_source_tree_and_variant_snapshot(self) -> None:
        draft = StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            variant_ini="[snapshot:chess]",
            name="Imported",
            source=StudySource("game", "game0001"),
        )
        study, chapter = await create_study_from_draft(
            cast(Any, self.app_state), "owner", draft, name="Saved analysis"
        )
        self.assertEqual(study.source, StudySource("game", "game0001"))
        self.assertEqual(chapter.name, "Imported")
        self.assertEqual(chapter.variant_ini, "[snapshot:chess]")
        self.assertEqual(chapter.source, StudySource("game", "game0001"))
        loaded = await load_owned_chapter(cast(Any, self.app_state), study.id, chapter.id, "owner")
        assert loaded is not None
        self.assertEqual(loaded.id, chapter.id)
        self.assertEqual(loaded.name, chapter.name)
        self.assertEqual(loaded.variant_ini, chapter.variant_ini)
        self.assertEqual(loaded.source, StudySource("game", "game0001"))
        self.assertEqual(loaded.root, chapter.root)

    async def test_create_from_draft_enforces_chapter_bson_limit(self) -> None:
        draft = StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
        )
        with (
            patch("study.storage.STUDY_CHAPTER_MAX_BSON_BYTES", 1),
            self.assertRaisesRegex(StudyStorageError, "too large"),
        ):
            await create_study_from_draft(cast(Any, self.app_state), "owner", draft)
        self.assertEqual(await self.db.study.count_documents({}), 0)
        self.assertEqual(await self.db.study_chapter.count_documents({}), 0)

    async def test_clone_study_copies_content_with_fresh_private_ownership(self) -> None:
        first_draft = StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            variant_ini="[snapshot:chess]",
            name="Main line",
            description="Source description",
            tags={"Event": "Clone test"},
        )
        study, first = await create_study_from_draft(
            cast(Any, self.app_state), "owner", first_draft, name="Opening ideas"
        )
        second_draft = StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            name="Second line",
            orientation="black",
            mode="conceal",
            conceal_ply=1,
            root=StudyTree(
                {
                    "StudyNode1": StudyTreeNode(
                        id="StudyNode1",
                        parent_id=None,
                        order=0,
                        move="e2e4",
                        fen="after-e4",
                        turn_color="black",
                        gamebook=StudyGamebook(deviation="Node lesson"),
                    )
                },
                root_gamebook=StudyGamebook(hint="Root lesson"),
            ),
            tags={"Chapter": "Two"},
        )
        second = await add_chapter_from_draft(cast(Any, self.app_state), study, second_draft)
        source = replace(
            study,
            settings={"example": "preserved"},
            topics=("Opening", "King pawn"),
            flair="variant:chess960",
        )

        with patch.object(
            self.db.study_chapter,
            "insert_many",
            side_effect=AssertionError(
                "Study clone must stream chapters instead of bulk inserting"
            ),
        ):
            cloned, cloned_first = await clone_study(cast(Any, self.app_state), source, "cloner")

        self.assertNotEqual(cloned.id, study.id)
        self.assertEqual(cloned.name, study.name)
        self.assertEqual(cloned.owner, "cloner")
        self.assertEqual(cloned.members, {"cloner": "write"})
        self.assertEqual(cloned.visibility, "private")
        self.assertEqual(cloned.source, StudySource("study", study.id))
        self.assertEqual(cloned.settings, {"example": "preserved"})
        self.assertEqual(cloned.topics, ("Opening", "King pawn"))
        self.assertEqual(cloned.flair, "variant:chess960")
        self.assertEqual(cloned.revision, 0)
        self.assertEqual(cloned.current_chapter, cloned_first.id)
        self.assertNotEqual(cloned_first.id, first.id)

        source_chapters = [first, second]
        cloned_docs = (
            await self.db.study_chapter.find({"studyId": cloned.id})
            .sort("order", 1)
            .to_list(length=10)
        )
        self.assertEqual(len(cloned_docs), 2)
        self.assertTrue({doc["_id"] for doc in cloned_docs}.isdisjoint({first.id, second.id}))
        for original, doc in zip(source_chapters, cloned_docs, strict=True):
            self.assertEqual(doc["owner"], "cloner")
            self.assertEqual(doc["studyId"], cloned.id)
            self.assertEqual(doc["name"], original.name)
            self.assertEqual(doc["order"], original.order)
            self.assertEqual(doc["variant"], original.variant)
            self.assertEqual(doc["initialFen"], original.initial_fen)
            self.assertEqual(doc["orientation"], original.orientation)
            self.assertEqual(doc["mode"], original.mode)
            self.assertEqual(
                doc.get("concealPly"),
                0 if original.mode == "conceal" else original.conceal_ply,
            )
            self.assertEqual(doc.get("variantIni"), original.variant_ini)
            self.assertEqual(doc.get("description", ""), original.description)
            self.assertEqual(doc.get("tags", {}), dict(original.tags))
            self.assertEqual(doc.get("source", "scratch"), original.source.encode())
            self.assertEqual(doc["root"], original.root.to_document())
            self.assertEqual(doc["revision"], 0)

    async def test_disabled_mode_gate_blocks_clone_and_copy_without_touching_source(self) -> None:
        source, first = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        lesson_root = StudyTree(root_gamebook=StudyGamebook(hint="Preserve me"))
        lesson = replace(first, mode="gamebook", root=lesson_root)
        await self.db.study_chapter.update_one(
            {"_id": first.id},
            {"$set": {"mode": "gamebook", "root": lesson_root.to_document()}},
        )

        with patch("study.models.STUDY_ENABLED_CHAPTER_MODES", ("normal",)):
            with self.assertRaisesRegex(StudyStorageError, "not enabled"):
                await clone_study(cast(Any, self.app_state), source, "cloner")
            self.assertEqual(await self.db.study.count_documents({"owner": "cloner"}), 0)
            self.assertEqual(await self.db.study_chapter.count_documents({"owner": "cloner"}), 0)

            with self.assertRaisesRegex(StudyStorageError, "not enabled"):
                await add_chapter(cast(Any, self.app_state), source, lesson)

        stored = await self.db.study_chapter.find_one({"_id": first.id})
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["mode"], "gamebook")
        self.assertEqual(stored["root"]["_"]["g"], {"h": "Preserve me"})

    async def test_add_chapter_preserves_mode_and_resets_conceal_progress(self) -> None:
        study, first = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        main = StudyTreeNode(
            id="StudyNode1",
            parent_id=None,
            order=0,
            move="e2e4",
            fen="after-e4",
            turn_color="black",
        )
        concealed = replace(
            first,
            mode="conceal",
            conceal_ply=1,
            root=StudyTree({main.id: main}),
        )

        added = await add_chapter(cast(Any, self.app_state), study, concealed)

        self.assertEqual(added.mode, "conceal")
        self.assertEqual(added.conceal_ply, 0)
        stored = await self.db.study_chapter.find_one({"_id": added.id})
        assert stored is not None
        self.assertEqual(stored["mode"], "conceal")
        self.assertEqual(stored["concealPly"], 0)

    async def test_study_list_chapter_names_previews_first_four_in_order(self) -> None:
        study, first = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        for name in ("Second line", "Third line", "Fourth line", "Fifth line"):
            await add_chapter(cast(Any, self.app_state), study, first, name=name)

        previews = await study_list_chapter_names(cast(Any, self.app_state), [study])

        self.assertEqual(
            previews,
            {study.id: ("Chapter 1", "Second line", "Third line", "Fourth line")},
        )

    async def test_chapter_previews_include_pgn_result_status(self) -> None:
        draft = StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            name="Alice - Bob",
            tags={"result": "1/2-1/2"},
        )
        study, chapter = await create_study_from_draft(cast(Any, self.app_state), "owner", draft)

        previews = await chapter_previews(cast(Any, self.app_state), study.id)

        self.assertEqual(previews[0]["id"], chapter.id)
        self.assertEqual(previews[0]["status"], "½-½")

    async def test_chapter_crud_keeps_lightweight_ordered_previews(self) -> None:
        study, first = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        second = await add_chapter(cast(Any, self.app_state), study, first)
        third = await add_chapter(cast(Any, self.app_state), study, second, name="Third line")

        self.assertEqual(second.order, 2)
        self.assertEqual(third.order, 3)
        await rename_chapter(cast(Any, self.app_state), second, "  Sicilian  ")
        await edit_chapter_metadata(
            cast(Any, self.app_state),
            third,
            name="Third line",
            orientation="black",
            pinned_description="1",
        )
        previews = await chapter_previews(cast(Any, self.app_state), study.id)
        self.assertEqual(
            previews,
            [
                {
                    "id": first.id,
                    "name": "Chapter 1",
                    "order": 1,
                    "orientation": "white",
                    "mode": "normal",
                    "descriptionPinned": False,
                },
                {
                    "id": second.id,
                    "name": "Sicilian",
                    "order": 2,
                    "orientation": "white",
                    "mode": "normal",
                    "descriptionPinned": False,
                },
                {
                    "id": third.id,
                    "name": "Third line",
                    "order": 3,
                    "orientation": "black",
                    "mode": "normal",
                    "descriptionPinned": True,
                },
            ],
        )

        # Delete a middle chapter and compact the display order.
        next_id = await delete_chapter(cast(Any, self.app_state), study, second)
        self.assertEqual(next_id, first.id)
        previews = await chapter_previews(cast(Any, self.app_state), study.id)
        self.assertEqual([item["order"] for item in previews], [1, 2])
        self.assertEqual([item["id"] for item in previews], [first.id, third.id])

    async def test_clear_chapter_annotations_clears_every_position(self) -> None:
        study, chapter = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        main = StudyTreeNode(
            id="MainNode01",
            parent_id=None,
            order=0,
            move="e2e4",
            fen="fen-1",
            turn_color="black",
            annotations=StudyAnnotations(nags=(1,)),
            gamebook=StudyGamebook(deviation="Remove node lesson"),
            clocks=(298000, 300000),
        )
        tree = StudyTree(
            {main.id: main},
            root_annotations=StudyAnnotations(
                comments=(StudyComment("Comment001", "owner", "Root note"),)
            ),
            root_gamebook=StudyGamebook(hint="Remove root lesson"),
            root_eval_score={"cp": 25},
            root_clocks=(300000, 300000),
        )
        chapter = replace(chapter, root=tree)
        await self.db.study_chapter.update_one(
            {"_id": chapter.id}, {"$set": {"root": tree.to_document()}}
        )

        changed = await clear_chapter_annotations(cast(Any, self.app_state), study, chapter)

        self.assertTrue(changed)
        loaded = await load_owned_chapter(cast(Any, self.app_state), study.id, chapter.id, "owner")
        assert loaded is not None
        self.assertTrue(loaded.root.root_annotations.empty)
        self.assertTrue(all(node.annotations.empty for node in loaded.root.nodes.values()))
        self.assertTrue(loaded.root.root_gamebook.empty)
        self.assertTrue(loaded.root.nodes[main.id].gamebook.empty)
        self.assertEqual(loaded.root.root_eval_score, {"cp": 25})
        self.assertEqual(loaded.root.root_clocks, (300000, 300000))
        self.assertEqual(loaded.root.nodes[main.id].clocks, (298000, 300000))

    async def test_clear_chapter_variations_keeps_first_child_recursively(self) -> None:
        study, chapter = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        main = StudyTreeNode(
            id="MainNode01",
            parent_id=None,
            order=0,
            move="e2e4",
            fen="fen-1",
            turn_color="black",
            gamebook=StudyGamebook(hint="Mainline hint"),
        )
        root_variation = StudyTreeNode(
            id="RootVar001", parent_id=None, order=1, move="d2d4", fen="fen-2", turn_color="black"
        )
        continuation = StudyTreeNode(
            id="MainNode02",
            parent_id=main.id,
            order=0,
            move="e7e5",
            fen="fen-3",
            turn_color="white",
            gamebook=StudyGamebook(deviation="Mainline fallback"),
        )
        side = StudyTreeNode(
            id="SideNode01",
            parent_id=main.id,
            order=1,
            move="c7c5",
            fen="fen-4",
            turn_color="white",
        )
        tree = StudyTree(
            {node.id: node for node in (main, root_variation, continuation, side)},
            root_gamebook=StudyGamebook(hint="Root hint"),
            root_clocks=(300000, 300000),
        )
        chapter = replace(chapter, root=tree, mode="conceal", conceal_ply=2)
        variation_path = f"{main.id}.{side.id}"
        study = replace(study, current_path=variation_path)
        await self.db.study_chapter.update_one(
            {"_id": chapter.id},
            {"$set": {"root": tree.to_document(), "mode": "conceal", "concealPly": 2}},
        )
        await self.db.study.update_one({"_id": study.id}, {"$set": {"currentPath": variation_path}})

        changed = await clear_chapter_variations(cast(Any, self.app_state), study, chapter)

        self.assertTrue(changed)
        loaded = await load_owned_chapter(cast(Any, self.app_state), study.id, chapter.id, "owner")
        assert loaded is not None
        self.assertEqual(set(loaded.root.nodes), {main.id, continuation.id})
        self.assertEqual(loaded.root.root_gamebook, StudyGamebook(hint="Root hint"))
        self.assertEqual(loaded.root.nodes[main.id].gamebook, StudyGamebook(hint="Mainline hint"))
        self.assertEqual(
            loaded.root.nodes[continuation.id].gamebook,
            StudyGamebook(deviation="Mainline fallback"),
        )
        self.assertEqual(loaded.root.root_clocks, (300000, 300000))
        self.assertEqual(loaded.conceal_ply, 2)
        study_doc = await self.db.study.find_one({"_id": study.id})
        assert study_doc is not None
        self.assertEqual(study_doc.get("currentPath"), main.id)

    async def test_select_and_delete_current_chapter_prefers_adjacent(self) -> None:
        study, first = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        second = await add_chapter(cast(Any, self.app_state), study, first)
        third = await add_chapter(cast(Any, self.app_state), study, second)

        await select_chapter(cast(Any, self.app_state), study, second)
        selected = await load_owned_study(cast(Any, self.app_state), study.id, "owner")
        assert selected is not None
        self.assertEqual(selected.current_chapter, second.id)

        next_id = await delete_chapter(cast(Any, self.app_state), selected, second)
        self.assertEqual(next_id, third.id)
        loaded = await load_owned_study(cast(Any, self.app_state), study.id, "owner")
        assert loaded is not None
        self.assertEqual(loaded.current_chapter, third.id)

        previews = await chapter_previews(cast(Any, self.app_state), study.id)
        self.assertEqual([item["id"] for item in previews], [first.id, third.id])
        self.assertEqual([item["order"] for item in previews], [1, 2])

    async def test_cannot_delete_last_chapter(self) -> None:
        study, chapter = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        with self.assertRaisesRegex(StudyStorageError, "at least one chapter"):
            await delete_chapter(cast(Any, self.app_state), study, chapter)

    async def test_rename_and_delete_study(self) -> None:
        study, chapter = await create_study_with_chapter(cast(Any, self.app_state), "owner")
        name = await rename_study(cast(Any, self.app_state), study, "  My repertoire  ")
        self.assertEqual(name, "My repertoire")
        loaded = await load_owned_study(cast(Any, self.app_state), study.id, "owner")
        assert loaded is not None
        self.assertEqual(loaded.name, "My repertoire")

        loaded_chapter = await load_owned_chapter(
            cast(Any, self.app_state), study.id, chapter.id, "owner"
        )
        self.assertIsNotNone(loaded_chapter)
        await delete_study(cast(Any, self.app_state), loaded)
        self.assertIsNone(await self.db.study.find_one({"_id": study.id}))
        self.assertEqual(await self.db.study_chapter.count_documents({"studyId": study.id}), 0)


if __name__ == "__main__":
    unittest.main()
