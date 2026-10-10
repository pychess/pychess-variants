from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from catalogued_variants import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    _build_fsf_builtin_doc,
    register_catalogued_variant_doc,
)
from fairy import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from study import variant as study_variant
from study.builder import StudyChapterBuilder, StudyChapterBuildError
from study.variant import (
    StudyVariantCapacityError,
    study_variant_client_doc,
    study_variant_context,
)
from variants import unregister_catalogued_server_variant


class StudyChapterBuilderTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncMongoMockClient(tz_aware=True)
        self.db = self.client["pychess-test"]
        self.app_state = SimpleNamespace(db=self.db, catalogued_variants={})
        self.builder = StudyChapterBuilder(cast(Any, self.app_state), "owner")

    async def test_blank_and_validated_fen(self) -> None:
        blank = await self.builder.blank_or_fen(variant="chess")
        self.assertEqual(blank.initial_fen, FairyBoard.start_fen("chess"))
        self.assertEqual(blank.root.count(), 0)

        fen = "8/8/8/8/8/8/4K3/7k w - - 0 1"
        custom = await self.builder.blank_or_fen(variant="chess", fen=fen)
        self.assertEqual(custom.initial_fen, fen)

        with self.assertRaisesRegex(StudyChapterBuildError, "Invalid FEN"):
            await self.builder.blank_or_fen(variant="chess", fen="not a fen")

    async def test_seirawan_import_accepts_engine_generated_gating_rights_after_castling(
        self,
    ) -> None:
        # This is the position before 19.Bf4/H in Kingwalker2-ubdip from the
        # first PyChess S-Chess tournament. Fairy-Stockfish generated this FEN
        # after White castled; the remaining A/C/D flags are piece-virginity
        # rights, not castling rights. The non-960 validator historically
        # rejected them merely because the king is no longer on e1.
        fen = "rh3rk1/pp4pp/2n3q1/2pp1pP1/8/2PP1N2/PP3P2/R1BQ1RK1[H] w ACD - 1 19"
        board = FairyBoard("seirawan", initial_fen=fen)
        board.push("c1f4h")
        draft = await self.builder.from_import(
            variant="seirawan",
            initial_fen=fen,
            tree_payload={
                "nodes": [
                    {
                        "id": "GateMove01",
                        "parentId": None,
                        "order": 0,
                        "move": "c1f4h",
                        "fen": board.fen,
                        "turnColor": "black",
                        "check": False,
                        "san": "Bf4/H",
                    }
                ]
            },
            mode="gamebook",
        )

        self.assertEqual(draft.initial_fen, fen)
        self.assertEqual(draft.root.children_of(None)[0].san, "Bf4/H")

    async def test_randomized_community_game_position_can_be_imported_with_snapshot(self) -> None:
        name = "studysideways960"
        ini = f"[{name}:pawnsideways]\nchess960 = true"
        default = FairyBoard.start_fen("chess")
        metadata = {
            "name": name,
            "ini": ini,
            "startFen": default,
            "width": 8,
            "height": 8,
            "visibility": "public",
        }
        register_catalogued_variant_doc(self.app_state, metadata)
        self.addCleanup(unregister_catalogued_server_variant, name)
        fen = "rnkrqbbn/pppppppp/8/8/8/8/PPPPPPPP/RNKRQBBN w DAda - 0 1"
        draft = await self.builder.from_import(
            variant=name,
            initial_fen=fen,
            chess960=True,
            variant_ini=ini,
            tree_payload={"nodes": []},
        )
        self.assertEqual(draft.variant, name)
        self.assertEqual(draft.initial_fen, fen)
        self.assertTrue(draft.chess960)
        self.assertEqual(draft.variant_ini, ini)
        with patch("study.builder.find_catalogued_variant_doc", AsyncMock(return_value=metadata)):
            custom = await self.builder.blank_or_fen(variant=name, fen=fen, chess960=True)
        self.assertEqual(custom.initial_fen, fen)
        self.assertTrue(custom.chess960)

    async def test_disabled_mode_gate_rejects_new_mode_and_hidden_lesson_import(self) -> None:
        root_fen = FairyBoard.start_fen("chess")
        with patch("study.models.STUDY_ENABLED_CHAPTER_MODES", ("normal",)):
            with self.assertRaisesRegex(StudyChapterBuildError, "mode is not enabled"):
                await self.builder.blank_or_fen(variant="chess", mode="practice")

            with self.assertRaisesRegex(StudyChapterBuildError, "lesson data is not enabled"):
                await self.builder.from_import(
                    variant="chess",
                    initial_fen=root_fen,
                    tree_payload={"nodes": [], "rootGamebook": {"hint": "Hidden draft"}},
                    mode="normal",
                )

    async def test_bulk_analysis_does_not_engine_validate_node_positions(self) -> None:
        root_fen = FairyBoard.start_fen("chess")
        with (
            patch.object(self.builder, "_validated_initial_fen", return_value=(True, root_fen)),
            patch("study.builder.FairyBoard") as board,
            patch("study.builder.validate_fen") as validate,
        ):
            draft = await self.builder.from_analysis(
                variant="chess",
                initial_fen=root_fen,
                tree_payload={
                    "nodes": [
                        {
                            "id": "Client0001",
                            "parentId": None,
                            "order": 0,
                            "move": "e2e4",
                            "fen": "client-derived b",
                            "turnColor": "black",
                            "check": False,
                        }
                    ]
                },
            )
        self.assertEqual(draft.root.count(), 1)
        board.assert_not_called()
        validate.assert_not_called()

    async def test_analysis_tree_trusts_client_chess_data_and_canonicalizes_authors(self) -> None:
        root_fen = FairyBoard.start_fen("chess")
        submitted = {
            "rootGamebook": {"hint": "Root lesson"},
            "rootEval": {"cp": 18},
            "rootAnnotations": {
                "shapes": [{"orig": "e4", "brush": "blue"}],
                "comments": [{"id": "Comment001", "author": "spoofed", "text": "Root note"}],
                "nags": [1],
            },
            "nodes": [
                {
                    "id": "Client0001",
                    "parentId": None,
                    "order": 0,
                    "move": "e2e4",
                    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    "turnColor": "black",
                    "check": True,
                    "san": "client-e4",
                    "gamebook": {"deviation": "Node lesson"},
                    "eval": {"cp": 35},
                    "annotations": {
                        "shapes": [{"orig": "e4", "dest": "e5", "brush": "red"}],
                        "comments": [
                            {"id": "Comment002", "author": "spoofed", "text": "Node note"}
                        ],
                        "nags": [3],
                    },
                },
                {
                    "id": "Client0002",
                    "parentId": "Client0001",
                    "order": 0,
                    "move": "e7e5",
                    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    "turnColor": "white",
                    "check": True,
                    "san": "client-e5",
                    "eval": {"mate": 3},
                },
                {
                    "id": "Client0003",
                    "parentId": None,
                    "order": 1,
                    "move": "d2d4",
                    "fen": "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
                    "turnColor": "black",
                    "check": False,
                    "forceVariation": True,
                },
            ],
        }
        draft = await self.builder.from_analysis(
            variant="chess",
            initial_fen=root_fen,
            tree_payload=submitted,
        )

        first = draft.root.nodes["Client0001"]
        self.assertEqual(first.san, "client-e4")
        self.assertEqual(first.turn_color, "black")
        self.assertTrue(first.check)
        self.assertEqual(
            first.fen,
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        )
        self.assertEqual(first.eval_score, {"cp": 35})
        self.assertEqual(draft.root.nodes["Client0002"].san, "client-e5")
        self.assertEqual(draft.root.nodes["Client0002"].eval_score, {"mate": 3})
        self.assertTrue(draft.root.nodes["Client0003"].force_variation)
        self.assertEqual([n.id for n in draft.root.children_of(None)], ["Client0001", "Client0003"])
        self.assertEqual(draft.root.root_annotations.comments[0].text, "Root note")
        self.assertEqual(draft.root.root_annotations.comments[0].author, "owner")
        self.assertEqual(draft.root.root_gamebook.hint, "Root lesson")
        self.assertEqual(draft.root.root_eval_score, {"cp": 18})
        self.assertEqual(first.gamebook.deviation, "Node lesson")
        self.assertEqual(first.annotations.comments[0].text, "Node note")
        self.assertEqual(first.annotations.comments[0].author, "owner")
        self.assertEqual(first.annotations.nags, (3,))

    async def test_analysis_preserves_orientation_and_pgn_tags(self) -> None:
        draft = await self.builder.from_analysis(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            tree_payload={"nodes": []},
            orientation="black",
            tags={"White": "Alice", "Black": "Bob", "Event": "PyChess casual game"},
        )

        self.assertEqual(draft.orientation, "black")
        self.assertEqual(
            dict(draft.tags),
            {"Black": "Bob", "Event": "PyChess casual game", "White": "Alice"},
        )

    async def test_analysis_rejects_invalid_pgn_tags(self) -> None:
        with self.assertRaisesRegex(StudyChapterBuildError, "PGN tags"):
            await self.builder.from_analysis(
                variant="chess",
                initial_fen=FairyBoard.start_fen("chess"),
                tree_payload={"nodes": []},
                tags={"not valid tag": "value"},
            )

    async def test_analysis_from_saved_game_uses_historical_variant_snapshot(self) -> None:
        variant = "studysource"
        root_fen = FairyBoard.start_fen("chess")
        saved_ini = f"[{variant}:chess]\nstartFen = {root_fen}\n"
        await self.db.game.insert_one({"_id": "gameOld1", "v": variant, "vini": saved_ini, "z": 0})

        draft = await self.builder.from_analysis(
            variant=variant,
            chess960=False,
            initial_fen=root_fen,
            game_id="gameOld1",
            tree_payload={
                "nodes": [
                    {
                        "id": "ClientOld1",
                        "parentId": None,
                        "order": 0,
                        "move": "e2e4",
                        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                        "turnColor": "black",
                        "check": False,
                        "san": "e4",
                    }
                ]
            },
        )

        self.assertEqual(draft.variant_ini, saved_ini)
        self.assertEqual(draft.source.kind, "game")
        self.assertEqual(draft.source.source_id, "gameOld1")
        self.assertEqual(draft.root.children_of(None)[0].san, "e4")

    async def test_analysis_from_fsf_catalogued_builtin_does_not_require_ini_snapshot(self) -> None:
        doc = _build_fsf_builtin_doc("joust", FSF_CATALOGUED_BUILTIN_VARIANTS["joust"])
        register_catalogued_variant_doc(cast(Any, self.app_state), doc, load_config=False)
        initial_fen = FairyBoard.start_fen("joust")
        board = FairyBoard("joust", initial_fen=initial_fen)
        move = next(iter(board.legal_moves()))
        board.push(move)
        await self.db.game.insert_one({"_id": "gameFsf1", "v": "joust", "z": 0})
        try:
            draft = await self.builder.from_analysis(
                variant="joust",
                initial_fen=initial_fen,
                game_id="gameFsf1",
                tree_payload={
                    "nodes": [
                        {
                            "id": "Client0001",
                            "parentId": None,
                            "order": 0,
                            "move": move,
                            "fen": board.fen,
                            "turnColor": "white" if board.fen.split()[1] == "w" else "black",
                            "check": False,
                        }
                    ]
                },
            )
        finally:
            unregister_catalogued_server_variant("joust")

        self.assertIsNone(draft.variant_ini)
        self.assertEqual(draft.source.kind, "game")
        self.assertEqual(draft.source.source_id, "gameFsf1")
        self.assertEqual(draft.root.children_of(None)[0].move, move)

    async def test_analysis_rejects_catalogued_variant_without_rules_snapshot(self) -> None:
        with (
            patch("study.builder.is_catalogued_variant", return_value=True),
            patch(
                "study.builder.find_catalogued_variant_doc",
                new=AsyncMock(return_value={"name": "chess", "source": "user", "ini": ""}),
            ),
            self.assertRaisesRegex(StudyChapterBuildError, "rules snapshot"),
        ):
            await self.builder.from_analysis(
                variant="chess",
                initial_fen=FairyBoard.start_fen("chess"),
                tree_payload={"nodes": []},
            )

    async def test_analysis_tree_rejects_fen_turn_mismatch(self) -> None:
        with self.assertRaisesRegex(StudyChapterBuildError, "FEN/turn mismatch"):
            await self.builder.from_analysis(
                variant="chess",
                initial_fen=FairyBoard.start_fen("chess"),
                tree_payload={
                    "nodes": [
                        {
                            "id": "Client0001",
                            "parentId": None,
                            "order": 0,
                            "move": "e2e4",
                            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                            "turnColor": "white",
                            "check": False,
                        }
                    ]
                },
            )

    async def test_saved_game_builds_mainline_and_source(self) -> None:
        await self.db.game.insert_one({"_id": "game0001", "vini": ""})
        fake_game = SimpleNamespace(
            server_variant=SimpleNamespace(two_boards=False),
            variant="chess",
            chess960=False,
            initial_fen=FairyBoard.start_fen("chess"),
            date=datetime(2026, 9, 7, tzinfo=UTC),
            result="1-0",
            wrating=2107,
            brating=2224,
            wplayer=SimpleNamespace(username="White", title="FM"),
            bplayer=SimpleNamespace(username="Black", title=""),
            get_board=lambda full=True: {
                "steps": [
                    {
                        "fen": FairyBoard.start_fen("chess"),
                        "turnColor": "white",
                        "clocks": [300000, 300000],
                    },
                    {
                        "move": "e2e4",
                        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                        "turnColor": "black",
                        "check": False,
                        "san": "e4",
                        "clocks": [298000, 300000],
                    },
                ]
            },
        )
        with patch("study.builder.load_game", new=AsyncMock(return_value=fake_game)):
            draft = await self.builder.from_game("game0001")
        self.assertEqual(draft.name, "White - Black")
        self.assertEqual(draft.source.kind, "game")
        self.assertEqual(draft.source.source_id, "game0001")
        self.assertEqual(draft.root.count(), 1)
        self.assertEqual(draft.root.root_clocks, (300000, 300000))
        self.assertEqual(draft.root.children_of(None)[0].move, "e2e4")
        self.assertEqual(draft.root.children_of(None)[0].clocks, (298000, 300000))
        self.assertEqual(draft.tags["WhiteElo"], "2107")
        self.assertEqual(draft.tags["BlackElo"], "2224")
        self.assertEqual(draft.tags["WhiteTitle"], "FM")

    def test_rejects_nonfinite_saved_game_clock(self) -> None:
        with self.assertRaisesRegex(StudyChapterBuildError, "invalid clock data"):
            self.builder._step_clocks({"clocks": [float("nan"), 300000]})

    async def test_rejected_embedded_snapshot_never_reaches_main_pyffish_registry(self) -> None:
        snapshot = (
            "[isolatedstudy:chess]\n"
            "startFen = rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\n"
        )
        from fairy.fairy_board import sf

        before_variants = set(sf.variants())
        with patch("study.variant.validate_catalogued_ini") as main_process_validate:
            for index in range(3):
                with self.assertRaisesRegex(StudyChapterBuildError, "snapshot is invalid"):
                    await self.builder.from_import(
                        variant="isolatedstudy",
                        initial_fen="not a fen",
                        tree_payload={"nodes": []},
                        variant_ini=f"{snapshot}# rejected import {index}\n",
                    )

        main_process_validate.assert_not_called()
        self.assertEqual(set(sf.variants()), before_variants)

    async def test_embedded_snapshot_isolated_check_does_not_replay_move_tree(self) -> None:
        initial_fen = FairyBoard.start_fen("chess")
        snapshot = f"[isolatedtree:chess]\nstartFen = {initial_fen}\n"
        with patch(
            "study.variant.check_catalogued_ini_tree_without_mutating_server",
            new=AsyncMock(),
        ) as isolated_check:
            await study_variant.validate_study_variant_import_without_mutating_server(
                "isolatedtree", snapshot, initial_fen
            )

        args = isolated_check.await_args.args
        self.assertEqual(args[2], initial_fen)
        self.assertEqual(args[3], ())

    async def test_rejects_two_board_game(self) -> None:
        await self.db.game.insert_one({"_id": "game0002"})
        fake_game = SimpleNamespace(server_variant=SimpleNamespace(two_boards=True))
        with (
            patch("study.builder.load_game", new=AsyncMock(return_value=fake_game)),
            self.assertRaisesRegex(StudyChapterBuildError, "Two-board"),
        ):
            await self.builder.from_game("game0002")


class StudyVariantSnapshotTestCase(unittest.TestCase):
    def test_semantic_alias_ignores_comments_and_native_registry_has_hard_cap(self) -> None:
        first = "[studybudget:chess]\ncustomPiece1 = a:KN\n"
        commented = f"{first}# formatting-only historical note\n"
        second = "[studybudget:chess]\ncustomPiece1 = a:BN\n"
        self.assertEqual(
            study_variant._snapshot_alias(first), study_variant._snapshot_alias(commented)
        )

        def validation(ini: str):
            return SimpleNamespace(
                name=study_variant.extract_variant_name(ini),
                start_fen=FairyBoard.start_fen("chess"),
                show_promoted=False,
            )

        with (
            patch("study.variant._SNAPSHOT_NATIVE_ALIASES", set()),
            patch("study.variant._SNAPSHOT_VALIDATION", {}),
            patch("study.variant.STUDY_MAX_NATIVE_SNAPSHOT_VARIANTS", 1),
            patch("study.variant.validate_catalogued_ini", side_effect=validation) as validate_ini,
        ):
            first_validation = study_variant._snapshot_validation(first)
            same_validation = study_variant._snapshot_validation(commented)
            self.assertIs(same_validation, first_validation)
            with self.assertRaisesRegex(StudyVariantCapacityError, "capacity"):
                study_variant._snapshot_validation(second)

        self.assertEqual(validate_ini.call_count, 1)

    def test_current_snapshot_client_doc_reuses_live_metadata_without_alias(self) -> None:
        name = "studycurrent"
        ini = f"[{name}:chess]\nstartFen = 8/8/8/8/8/8/4K3/7k w - - 0 1\n"
        metadata = {
            "ini": ini,
            "displayName": "Current",
            "baseVariant": "chess",
            "startFen": "8/8/8/8/8/8/4K3/7k w - - 0 1",
            "width": 8,
            "height": 8,
            "pieces": ["k"],
            "kingRoles": ["k"],
            "pocketRoles": [],
            "captureToHand": False,
            "promotionType": "normal",
            "promotionRoles": [],
            "promotionOrder": [],
            "showPromoted": False,
            "rulesGate": False,
            "rulesPass": False,
            "showCheckCounters": False,
        }

        app_state = SimpleNamespace(catalogued_variants={name: metadata})
        with patch("study.variant._snapshot_validation") as validate_snapshot:
            with study_variant_context(cast(Any, app_state), name, ini) as options:
                self.assertEqual(options.runtime_variant, name)
            doc = study_variant_client_doc(name, ini, metadata=metadata)

        validate_snapshot.assert_not_called()
        self.assertEqual(doc["displayName"], "Current")
        self.assertEqual(doc["startFen"], metadata["startFen"])

    def test_snapshot_client_doc_and_live_definition_restore(self) -> None:
        name = "studysnapshot"
        live_ini = f"[{name}:chess]\nstartFen = 8/8/8/8/8/8/4K3/7k w - - 0 1\n"
        saved_ini = f"[{name}:chess]\nstartFen = 8/8/8/8/8/8/7k/4K3 w - - 0 1\n"
        app_state = SimpleNamespace(
            catalogued_variants={name: {"ini": live_ini, "displayName": "Live"}}
        )

        from fairy.fairy_board import sf

        sf.load_variant_config(live_ini)
        self.assertEqual(sf.start_fen(name), "8/8/8/8/8/8/4K3/7k w - - 0 1")
        with study_variant_context(cast(Any, app_state), name, saved_ini) as options:
            doc = study_variant_client_doc(name, saved_ini)
            self.assertEqual(doc["ini"], saved_ini)
            self.assertEqual(doc["startFen"], "8/8/8/8/8/8/7k/4K3 w - - 0 1")
            self.assertNotEqual(options.runtime_variant, name)
            self.assertEqual(sf.start_fen(options.runtime_variant), "8/8/8/8/8/8/7k/4K3 w - - 0 1")
            self.assertEqual(sf.start_fen(name), "8/8/8/8/8/8/4K3/7k w - - 0 1")
        self.assertEqual(sf.start_fen(name), "8/8/8/8/8/8/4K3/7k w - - 0 1")


if __name__ == "__main__":
    unittest.main()
