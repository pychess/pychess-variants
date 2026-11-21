"""Behavioral checks for the native forum CAPTCHA fast path."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import pyffish as sf
from fairy.fairy_board import FairyBoard
from forum.captcha import _captcha_from_fen, _captcha_from_game_doc
from forum.constants import FORUM_CAPTCHA_FALLBACK_BY_VARIANT
from variants import VARIANTS


class ForumCaptchaOptimizationTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_mate_in_one_parity_across_all_configured_variants(self):
        for variant, fallback in FORUM_CAPTCHA_FALLBACK_BY_VARIANT.items():
            with self.subTest(variant=variant):
                # Building candidate FENs and undoing moves is no longer needed.
                with (
                    patch.object(FairyBoard, "push", side_effect=AssertionError("push")),
                    patch.object(FairyBoard, "pop", side_effect=AssertionError("pop")),
                ):
                    puzzle = await _captcha_from_fen(
                        game_id=str(fallback["gameId"]),
                        fen=str(fallback["fen"]),
                        variant=variant,
                    )
                self.assertIsNotNone(puzzle)
                assert puzzle is not None
                self.assertEqual(fallback["moves"], puzzle["moves"])
                self.assertEqual(fallback["solutions"], puzzle["solutions"])
                self.assertEqual(fallback["color"], puzzle["color"])

    async def test_evaluation_yields_to_other_tasks(self):
        loop = asyncio.get_running_loop()
        callbacks_run: list[bool] = []
        loop.call_soon(callbacks_run.append, True)

        fallback = FORUM_CAPTCHA_FALLBACK_BY_VARIANT["chess"]
        puzzle = await _captcha_from_fen(
            game_id="example", fen=str(fallback["fen"]), variant="chess"
        )

        self.assertIsNotNone(puzzle)
        self.assertEqual([True], callbacks_run)

    async def test_game_replay_uses_one_native_call_and_preserves_solution(self):
        # Scholar's mate: the last move in the document is the solution.
        moves = ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"]
        chess = VARIANTS["chess"]
        doc = {
            "_id": "game-id",
            "v": chess.code,
            "m": [chess.move_encoding(move) for move in moves],
        }

        with (
            patch.object(FairyBoard, "push", side_effect=AssertionError("push")),
            patch.object(sf, "get_fen", wraps=sf.get_fen) as get_fen,
        ):
            puzzle = await _captcha_from_game_doc(doc)

        self.assertIsNotNone(puzzle)
        assert puzzle is not None
        self.assertEqual(("h5 f7",), puzzle["solutions"])
        self.assertEqual("/game-id", puzzle["helpUrl"])
        get_fen.assert_called_once()
        self.assertEqual(moves[:-1], get_fen.call_args.args[2])

    async def test_invalid_game_history_is_rejected(self):
        chess = VARIANTS["chess"]
        doc = {
            "_id": "invalid-game",
            "v": chess.code,
            "m": [chess.move_encoding("e2e4"), chess.move_encoding("e2e4"), "not-a-move"],
        }
        self.assertIsNone(await _captcha_from_game_doc(doc))
