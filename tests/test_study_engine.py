from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from fairy.fairy_board import FairyBoard
from study.analysis import _new_analysis_board
from study.engine import validated_study_position
from study.models import StudyChapter
from study.tree import StudyTree, StudyTreeNode


class StudyEnginePositionTestCase(unittest.TestCase):
    def test_oversized_rank_is_rejected_before_native_validation(self) -> None:
        fen = "99P/8/8/8/8/8/8/K6k b - - 0 1"
        with (
            patch("fairy.fairy_board.sf.validate_fen") as validate,
            self.assertRaisesRegex(ValueError, "FEN geometry"),
        ):
            validated_study_position("chess", fen, chess960=False, show_promoted=False)
        validate.assert_not_called()

    def test_excessive_pocket_material_is_rejected_before_native_validation(self) -> None:
        fen = FairyBoard.start_fen("crazyhouse").replace("[]", "[" + "P" * 1000 + "]")
        with (
            patch("fairy.fairy_board.sf.validate_fen") as validate,
            self.assertRaisesRegex(ValueError, "material limits"),
        ):
            validated_study_position("crazyhouse", fen, chess960=False, show_promoted=False)
        validate.assert_not_called()

    def test_position_local_analysis_rejects_malformed_imported_fen(self) -> None:
        now = datetime.now(UTC)
        node = StudyTreeNode(
            id="Client0001",
            parent_id=None,
            order=0,
            move="e2e4",
            fen="not-a-fen b",
            turn_color="black",
        )
        chapter = StudyChapter(
            id="chapter1",
            study_id="study001",
            owner="owner",
            name="Import",
            order=1,
            orientation="white",
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
            created_at=now,
            updated_at=now,
            root=StudyTree({node.id: node}),
        )
        for fen in ("not-a-fen b", "8/8/8/8/8/8/8/8 b - - 0 1"):
            with self.subTest(fen=fen), patch("fairy.fairy_board.sf.legal_moves") as legal:
                with self.assertRaisesRegex(ValueError, "Invalid stored Study FEN"):
                    _new_analysis_board(
                        chapter,
                        (replace(node, fen=fen),),
                        parent_ply=1,
                        runtime_variant="chess",
                        show_promoted=False,
                        legal_moves_need_history=False,
                    )
                legal.assert_not_called()

    def test_engine_generated_positions_remain_usable(self) -> None:
        for variant in (
            "chess",
            "crazyhouse",
            "shogi",
            "xiangqi",
            "seirawan",
            "duck",
            "alice",
            "capablanca",
            "makruk",
        ):
            with self.subTest(variant=variant):
                board = FairyBoard(variant)
                move = board.legal_moves()[0]
                board.push(move)
                checked = validated_study_position(
                    variant, board.fen, chess960=False, show_promoted=False
                )
                self.assertEqual(checked.legal_moves(), board.legal_moves())

    def test_seirawan_gating_rights_after_castling_remain_usable(self) -> None:
        fen = "rh3rk1/pp4pp/2n3q1/2pp1pP1/8/2PP1N2/PP3P2/R1BQ1RK1[H] w ACD - 1 19"
        board = validated_study_position("seirawan", fen, chess960=False, show_promoted=False)
        self.assertIn("c1f4h", board.legal_moves())
