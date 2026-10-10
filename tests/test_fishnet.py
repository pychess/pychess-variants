import asyncio
import json
import unittest
from collections import defaultdict
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import fishnet
import pytest
import wsr
from aiohttp import web
from fishnet import _read_fishnet_json, _winning_chances
from game import Game
from typedefs import pychess_global_app_state_key


class FishnetTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_read_fishnet_json_returns_payload(self):
        request = cast(web.Request, AsyncMock())
        request.json = AsyncMock(return_value={"fishnet": {"apikey": "abc"}})
        request.rel_url = SimpleNamespace(path="/fishnet/acquire")
        request.remote = "10.1.1.1"

        data, status = await _read_fishnet_json(request)

        self.assertEqual(data, {"fishnet": {"apikey": "abc"}})
        self.assertIsNone(status)

    async def test_read_fishnet_json_connection_reset_returns_204(self):
        request = cast(web.Request, AsyncMock())
        request.json = AsyncMock(side_effect=ConnectionResetError)
        request.rel_url = SimpleNamespace(path="/fishnet/acquire")
        request.remote = "10.1.1.1"

        data, status = await _read_fishnet_json(request)

        self.assertIsNone(data)
        self.assertEqual(status, 204)

    async def test_read_fishnet_json_invalid_json_returns_400(self):
        request = cast(web.Request, AsyncMock())
        request.json = AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))
        request.rel_url = SimpleNamespace(path="/fishnet/acquire")
        request.remote = "10.1.1.1"

        data, status = await _read_fishnet_json(request)

        self.assertIsNone(data)
        self.assertEqual(status, 400)

    async def test_fishnet_acquire_old_version_returns_update_required_json(self):
        app_state = SimpleNamespace()
        request = cast(web.Request, AsyncMock())
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/acquire")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {"apikey": "k", "version": "1.16.62"},
                "stockfish": {"name": "Fairy-Stockfish"},
            }
        )

        with patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True):
            response = await fishnet.fishnet_acquire(request)

        self.assertEqual(response.status, 426)
        self.assertIn("Please restart fishnet to upgrade", response.text)

    async def test_get_work_reissues_stale_analysis_job(self):
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={
                "work123": {
                    "work": {"type": "analysis", "id": "work123"},
                    "game_id": "g1",
                    "position": "startpos",
                    "variant": "chess",
                    "chess960": False,
                    "moves": "",
                    "nnue": True,
                    "time": 0.0,
                }
            },
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
        )
        payload = {"fishnet": {"apikey": "k"}}

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.monotonic", return_value=fishnet.ANALYSIS_WORK_TIME_OUT + 100.0),
        ):
            response = await fishnet.get_work(app_state, payload)

        self.assertEqual(response.status, 202)
        self.assertIn("work123", response.text)
        self.assertEqual(app_state.fishnet_works["work123"]["stale_reissue_count"], 1)

    async def test_get_work_drops_stale_analysis_after_reissue_limit(self):
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={
                "work123": {
                    "work": {"type": "analysis", "id": "work123"},
                    "game_id": "g1",
                    "position": "startpos",
                    "variant": "chess",
                    "chess960": False,
                    "moves": "",
                    "nnue": True,
                    "time": 0.0,
                    "stale_reissue_count": fishnet.ANALYSIS_STALE_REISSUE_LIMIT - 1,
                }
            },
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
        )
        payload = {"fishnet": {"apikey": "k"}}

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.monotonic", return_value=fishnet.ANALYSIS_WORK_TIME_OUT + 100.0),
        ):
            response = await fishnet.get_work(app_state, payload)

        self.assertEqual(response.status, 204)
        self.assertNotIn("work123", app_state.fishnet_works)

    async def test_get_work_drops_analysis_when_game_no_longer_exists(self):
        work = {
            "work": {"type": "analysis", "id": "work123"},
            "game_id": "missing-game",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "",
            "nnue": True,
            "time": 0.0,
        }
        queue = asyncio.PriorityQueue()
        queue.put_nowait((fishnet.ANALYSIS, "work123"))
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=queue,
            fishnet_works={"work123": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock(return_value=None)),
        ):
            response = await fishnet.get_work(app_state, {"fishnet": {"apikey": "k"}})

        self.assertEqual(response.status, 204)
        self.assertNotIn("work123", app_state.fishnet_works)
        self.assertEqual(app_state.fishnet_queue.qsize(), 0)

    async def test_get_work_serves_study_analysis_without_loading_game(self):
        work = {
            "work": {"type": "analysis", "id": "studywork"},
            "study_id": "study001",
            "chapter_id": "chapter1",
            "study_path": "Node000001",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "e2e4",
            "nnue": True,
        }
        queue = asyncio.PriorityQueue()
        queue.put_nowait((fishnet.ANALYSIS, "studywork"))
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=queue,
            fishnet_works={"studywork": work},
            fishnet_variant_payloads={},
            catalogued_variants={},
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch(
                "study.analysis.study_analysis_work_is_current",
                AsyncMock(return_value=True),
            ),
            patch("fishnet.load_game", AsyncMock()) as load_game,
        ):
            response = await fishnet.get_work(app_state, {"fishnet": {"apikey": "k"}})

        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.text)["study_id"], "study001")
        load_game.assert_not_awaited()

    async def test_fishnet_analysis_routes_study_progress_to_study_merger(self):
        work = {
            "work": {"type": "analysis", "id": "studywork"},
            "study_id": "study001",
            "chapter_id": "chapter1",
            "study_path": "Node000001",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "e2e4",
            "nnue": True,
        }
        app_state = SimpleNamespace(
            fishnet_works={"studywork": work},
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_worker_last_seen={},
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "studywork"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/analysis/studywork")
        request.remote = "10.1.1.1"
        rows = [{"score": {"cp": 12}, "depth": 15}]
        request.json = AsyncMock(return_value={"fishnet": {"apikey": "k"}, "analysis": rows})

        merger = AsyncMock()
        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("study.analysis.merge_study_server_analysis", merger),
        ):
            response = await fishnet.fishnet_analysis(request)

        self.assertEqual(response.status, 204)
        merger.assert_awaited_once_with(app_state, "studywork", work, rows)

    async def test_fishnet_move_play_move_exception_requeues_without_deleting_work(self):
        work = {
            "work": {"type": "move", "id": "work123", "level": 1},
            "game_id": "g1",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "",
            "nnue": True,
            "time": 100.0,
        }
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={"work123": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )
        game = SimpleNamespace(
            id="g1",
            status=fishnet.STARTED,
            board=SimpleNamespace(fen="fen", move_stack=[]),
            move_lock=asyncio.Lock(),
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "work123"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/move/work123")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {"apikey": "k"},
                "move": {"bestmove": "e2e4", "fen": "fen"},
            }
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock(return_value=game)),
            patch("fishnet.play_move", AsyncMock(side_effect=RuntimeError("boom"))),
            patch("fishnet.monotonic", return_value=101.0),
        ):
            response = await fishnet.fishnet_move(request)

        self.assertEqual(response.status, 204)
        self.assertIn("work123", app_state.fishnet_works)
        self.assertEqual(app_state.fishnet_works["work123"]["move_failure_count"], 1)
        self.assertEqual(app_state.fishnet_queue.qsize(), 1)

    async def test_fishnet_move_applies_when_worker_fen_mismatches_but_move_stack_matches(self):
        work = {
            "work": {"type": "move", "id": "work123", "level": 1},
            "game_id": "g1",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "e2e4",
            "nnue": True,
            "time": 100.0,
        }
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={"work123": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )
        game = SimpleNamespace(
            id="g1",
            status=fishnet.STARTED,
            board=SimpleNamespace(fen="server-fen", move_stack=["e2e4"]),
            move_lock=asyncio.Lock(),
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "work123"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/move/work123")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {"apikey": "k"},
                "move": {"bestmove": "e7e5", "fen": "wrong-worker-fen"},
            }
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock(return_value=game)),
            patch("fishnet.play_move", AsyncMock()) as play_move,
            patch("fishnet.clear_catalogued_variant_ai_failures", AsyncMock()),
            patch("fishnet.monotonic", return_value=101.0),
        ):
            response = await fishnet.fishnet_move(request)

        self.assertEqual(response.status, 204)
        play_move.assert_awaited_once()
        self.assertNotIn("work123", app_state.fishnet_works)

    async def test_fishnet_move_uses_alice_stockfish_game_player(self):
        work = {
            "work": {"type": "move", "id": "work-alice", "level": 1},
            "game_id": "g-alice",
            "position": "startpos",
            "variant": "alice",
            "chess960": False,
            "moves": "",
            "nnue": True,
            "time": 100.0,
        }
        fairy = SimpleNamespace(online=True)
        alice = SimpleNamespace(username="Alice-Stockfish", bot=True, online=True)
        human = SimpleNamespace(username="human", bot=False)
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={"work-alice": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": fairy, "Alice-Stockfish": alice},
            catalogued_variants={},
        )
        game = SimpleNamespace(
            id="g-alice",
            status=fishnet.STARTED,
            wplayer=human,
            bplayer=alice,
            board=SimpleNamespace(fen="fen", move_stack=[], color=1),
            move_lock=asyncio.Lock(),
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "work-alice"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/move/work-alice")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {
                    "apikey": "k",
                    "capabilities": {"variants": ["alice"]},
                },
                "move": {"bestmove": "e7e5", "fen": "fen"},
            }
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock(return_value=game)),
            patch("fishnet.play_move", AsyncMock()) as play_move,
            patch("fishnet.clear_catalogued_variant_ai_failures", AsyncMock()),
            patch("fishnet.monotonic", return_value=101.0),
        ):
            response = await fishnet.fishnet_move(request)

        self.assertEqual(response.status, 204)
        play_move.assert_awaited_once_with(app_state, alice, game, "e7e5")
        self.assertNotIn("work-alice", app_state.fishnet_works)

    async def test_fishnet_move_discards_when_server_move_stack_changed(self):
        work = {
            "work": {"type": "move", "id": "work123", "level": 1},
            "game_id": "g1",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "e2e4",
            "nnue": True,
            "time": 100.0,
        }
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={"work123": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )
        game = SimpleNamespace(
            id="g1",
            status=fishnet.STARTED,
            board=SimpleNamespace(fen="server-fen", move_stack=["d2d4"]),
            move_lock=asyncio.Lock(),
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "work123"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/move/work123")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {"apikey": "k"},
                "move": {"bestmove": "e7e5", "fen": "server-fen"},
            }
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock(return_value=game)),
            patch("fishnet.play_move", AsyncMock()) as play_move,
            patch("fishnet.monotonic", return_value=101.0),
        ):
            response = await fishnet.fishnet_move(request)

        self.assertEqual(response.status, 204)
        play_move.assert_not_awaited()
        self.assertNotIn("work123", app_state.fishnet_works)

    async def test_fishnet_move_malformed_bestmove_requeues_without_loading_game(self):
        work = {
            "work": {"type": "move", "id": "work123", "level": 1},
            "game_id": "g1",
            "position": "startpos",
            "variant": "chess",
            "chess960": False,
            "moves": "",
            "nnue": True,
            "time": 100.0,
        }
        app_state = SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=asyncio.PriorityQueue(),
            fishnet_works={"work123": work},
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )
        request = cast(web.Request, AsyncMock())
        request.match_info = {"workId": "work123"}
        request.app = {pychess_global_app_state_key: app_state}
        request.rel_url = SimpleNamespace(path="/fishnet/move/work123")
        request.remote = "10.1.1.1"
        request.json = AsyncMock(
            return_value={
                "fishnet": {"apikey": "k"},
                "move": {"bestmove": None, "fen": "fen"},
            }
        )

        with (
            patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True),
            patch("fishnet.load_game", AsyncMock()) as load_game,
            patch("fishnet.monotonic", return_value=101.0),
        ):
            response = await fishnet.fishnet_move(request)

        self.assertEqual(response.status, 204)
        load_game.assert_not_awaited()
        self.assertIn("work123", app_state.fishnet_works)
        self.assertEqual(app_state.fishnet_works["work123"]["move_failure_count"], 1)
        self.assertEqual(app_state.fishnet_queue.qsize(), 1)

    def test_drop_stale_analysis_work_removes_only_old_analysis(self):
        queue = asyncio.PriorityQueue()
        queue.put_nowait((fishnet.ANALYSIS, "analysis1"))
        queue.put_nowait((fishnet.ANALYSIS, "analysis2"))
        queue.put_nowait((fishnet.ANALYSIS, "analysis2"))
        queue.put_nowait((fishnet.MOVE, "move1"))
        queue.put_nowait((fishnet.MOVE, "missing"))
        app_state = SimpleNamespace(
            fishnet_works={
                "analysis1": {
                    "work": {"type": "analysis", "id": "analysis1"},
                    "time": 0.0,
                },
                "analysis2": {
                    "work": {"type": "analysis", "id": "analysis2"},
                    "time": 100.0,
                },
                "move1": {"work": {"type": "move", "id": "move1"}, "time": 0.0},
            },
            fishnet_queue=queue,
        )

        dropped = fishnet.drop_stale_analysis_work(
            app_state, now=fishnet.ANALYSIS_WORK_TIME_OUT + 1.0
        )

        self.assertEqual(dropped, 1)
        self.assertEqual(set(app_state.fishnet_works), {"analysis2", "move1"})
        self.assertEqual(app_state.fishnet_queue.qsize(), 2)
        retained_ids = {
            app_state.fishnet_queue.get_nowait()[1],
            app_state.fishnet_queue.get_nowait()[1],
        }
        self.assertEqual(retained_ids, {"analysis2", "move1"})

    def test_drop_fishnet_work_for_game_compacts_queue(self):
        queue = asyncio.PriorityQueue()
        queue.put_nowait((fishnet.MOVE, "drop"))
        queue.put_nowait((fishnet.ANALYSIS, "keep"))
        queue.put_nowait((fishnet.MOVE, "already-missing"))
        app_state = SimpleNamespace(
            fishnet_works={
                "drop": {"game_id": "done"},
                "keep": {"game_id": "active"},
            },
            fishnet_queue=queue,
        )

        dropped = fishnet.drop_fishnet_work_for_game(app_state, "done")

        self.assertEqual(dropped, 1)
        self.assertEqual(set(app_state.fishnet_works), {"keep"})
        self.assertEqual(app_state.fishnet_queue.qsize(), 1)
        self.assertEqual(app_state.fishnet_queue.get_nowait()[1], "keep")

    def test_has_recent_fishnet_activity_requires_recent_worker_heartbeat(self):
        app_state = SimpleNamespace(
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
        )

        self.assertTrue(
            fishnet.has_recent_fishnet_activity(
                app_state, now=100.0 + fishnet.FISHNET_ACTIVITY_TIMEOUT - 1.0
            )
        )
        self.assertFalse(
            fishnet.has_recent_fishnet_activity(
                app_state, now=100.0 + fishnet.FISHNET_ACTIVITY_TIMEOUT + 1.0
            )
        )

    def test_prune_stale_fishnet_workers_removes_stale_and_marks_offline(self):
        engine = SimpleNamespace(online=True)
        app_state = SimpleNamespace(
            workers={"stale", "fresh"},
            fishnet_worker_last_seen={"stale": 0.0, "fresh": 100.0},
            fishnet_monitor=defaultdict(list),
            users={"Fairy-Stockfish": engine},
        )

        with patch.dict(
            fishnet.FISHNET_KEYS, {"stale": "stale-worker", "fresh": "fresh-worker"}, clear=True
        ):
            pruned = fishnet.prune_stale_fishnet_workers(
                app_state, now=100.0 + fishnet.FISHNET_ACTIVITY_TIMEOUT - 1.0
            )

        self.assertEqual(pruned, 1)
        self.assertEqual(app_state.workers, {"fresh"})
        self.assertNotIn("stale", app_state.fishnet_worker_last_seen)
        self.assertTrue(engine.online)
        self.assertTrue(app_state.fishnet_monitor["stale-worker"])

        pruned = fishnet.prune_stale_fishnet_workers(
            app_state, now=100.0 + fishnet.FISHNET_ACTIVITY_TIMEOUT + 1.0
        )

        self.assertEqual(pruned, 1)
        self.assertEqual(app_state.workers, set())
        self.assertFalse(engine.online)

    def test_has_available_fishnet_worker_prunes_before_answering(self):
        engine = SimpleNamespace(online=True)
        app_state = SimpleNamespace(
            workers={"k"},
            fishnet_worker_last_seen={"k": 0.0},
            fishnet_monitor=defaultdict(list),
            users={"Fairy-Stockfish": engine},
        )

        self.assertFalse(
            fishnet.has_available_fishnet_worker(
                app_state, now=fishnet.FISHNET_ACTIVITY_TIMEOUT + 1.0
            )
        )
        self.assertEqual(app_state.workers, set())
        self.assertFalse(engine.online)

    async def test_handle_analysis_with_stale_worker_prunes_worker(self):
        game = SimpleNamespace(
            id="g1",
            steps=[],
            board=SimpleNamespace(initial_fen="startpos", move_stack=[], nnue=True),
            variant="chess",
            chess960=False,
        )
        engine = SimpleNamespace(online=True, game_queues={}, event_queue=asyncio.Queue())
        app_state = SimpleNamespace(
            games={"g1": game},
            users={"Fairy-Stockfish": engine},
            workers={"k"},
            fishnet_worker_last_seen={"k": 0.0},
            fishnet_monitor=defaultdict(list),
            fishnet_works={},
            fishnet_queue=asyncio.PriorityQueue(),
        )
        data = {"gameId": "g1", "username": "u"}
        ws = SimpleNamespace()
        ws_send_json = AsyncMock()

        with (
            patch("wsr.ws_send_json", new=ws_send_json),
            patch("fishnet.monotonic", return_value=fishnet.FISHNET_ACTIVITY_TIMEOUT + 1.0),
            patch("wsr.log"),
        ):
            await wsr.handle_analysis(app_state, ws, data, game)

        self.assertFalse(engine.online)
        self.assertEqual(app_state.workers, set())
        self.assertEqual(app_state.fishnet_works, {})
        self.assertEqual(engine.event_queue.qsize(), 0)
        self.assertEqual(ws_send_json.await_count, 1)
        self.assertEqual(
            ws_send_json.await_args.args[1]["message"],
            "Analysis unavailable right now.",
        )

    async def test_handle_analysis_deduplicates_pending_work_for_game(self):
        game = SimpleNamespace(
            id="g1",
            steps=[],
            board=SimpleNamespace(initial_fen="startpos", move_stack=[], nnue=True),
            variant="chess",
            chess960=False,
        )
        queue = asyncio.PriorityQueue()
        queue.put_nowait((fishnet.ANALYSIS, "pending"))
        app_state = SimpleNamespace(
            games={"g1": game},
            users={},
            workers={"k"},
            fishnet_worker_last_seen={"k": fishnet.monotonic()},
            fishnet_monitor=defaultdict(list),
            fishnet_works={
                "pending": {
                    "work": {"type": "analysis", "id": "pending"},
                    "game_id": "g1",
                    "time": fishnet.monotonic(),
                    "variant": "chess",
                }
            },
            fishnet_queue=queue,
        )
        ws_send_json = AsyncMock()

        with (
            patch("wsr.ws_send_json", new=ws_send_json),
            patch(
                "wsr.has_available_fishnet_worker",
                side_effect=AssertionError("duplicate must return before worker lookup"),
            ),
        ):
            await wsr.handle_analysis(
                app_state,
                SimpleNamespace(),
                {"gameId": "g1", "username": "u"},
                game,
            )

        self.assertEqual(set(app_state.fishnet_works), {"pending"})
        self.assertEqual(app_state.fishnet_queue.qsize(), 1)
        self.assertEqual(
            ws_send_json.await_args.args[1]["message"],
            "Analysis already requested...",
        )

    async def test_handle_analysis_does_not_replace_internal_engine_queue(self):
        game = SimpleNamespace(
            id="g1",
            steps=[],
            board=SimpleNamespace(initial_fen="startpos", move_stack=[], nnue=True),
            variant="chess",
            chess960=False,
        )
        existing_queue = asyncio.Queue()
        engine = SimpleNamespace(
            online=True,
            game_queues={"g1": existing_queue},
            event_queue=asyncio.Queue(),
        )
        app_state = SimpleNamespace(
            games={"g1": game},
            users={"Fairy-Stockfish": engine},
            workers=set(),
            fishnet_worker_last_seen={},
            fishnet_monitor=defaultdict(list),
            fishnet_works={},
            fishnet_queue=asyncio.PriorityQueue(),
        )
        ws_send_json = AsyncMock()

        with patch("wsr.ws_send_json", new=ws_send_json):
            await wsr.handle_analysis(
                app_state,
                SimpleNamespace(),
                {"gameId": "g1", "username": "u"},
                game,
            )

        self.assertIs(engine.game_queues["g1"], existing_queue)
        self.assertEqual(engine.event_queue.qsize(), 0)
        self.assertEqual(
            ws_send_json.await_args.args[1]["message"],
            "Analysis already requested...",
        )


class TestWinningChances(unittest.TestCase):
    def test_cp_zero_is_neutral(self) -> None:
        assert _winning_chances({"cp": 0}) == pytest.approx(0.0, abs=1e-9)

    def test_positive_cp_is_positive(self) -> None:
        wc = _winning_chances({"cp": 500})
        assert 0.0 < wc < 1.0

    def test_negative_cp_is_negative(self) -> None:
        wc = _winning_chances({"cp": -500})
        assert -1.0 < wc < 0.0

    def test_cp_clipped_at_1000(self) -> None:
        assert _winning_chances({"cp": 1001}) == pytest.approx(
            _winning_chances({"cp": 1000}), abs=1e-9
        )

    def test_positive_mate_approaches_one(self) -> None:
        assert _winning_chances({"mate": 1}) > 0.9

    def test_negative_mate_approaches_minus_one(self) -> None:
        assert _winning_chances({"mate": -1}) < -0.9

    def test_mate_beats_cp(self) -> None:
        assert _winning_chances({"mate": 3}) > _winning_chances({"cp": 1000})

    def test_no_cp_no_mate_defaults_to_zero(self) -> None:
        assert _winning_chances({}) == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]

    def test_antisymmetric(self) -> None:
        for cp in (50, 200, 800):
            assert _winning_chances({"cp": cp}) == pytest.approx(
                -_winning_chances({"cp": -cp}), abs=1e-9
            )


class TestSavePvDirection(unittest.TestCase):
    """Exercises fishnet._should_save_analysis_pv() directly (the real production
    function), so these tests fail if the save/drop logic later regresses."""

    @staticmethod
    def _analysis(cp: int) -> dict:
        # "pv" must be present, otherwise _should_save_analysis_pv short-circuits to False.
        return {"score": {"cp": cp}, "pv": "e2e4"}

    def test_white_move_improves_white_no_pv(self) -> None:
        """White plays well: winning chances increase -> no PV saved."""
        self.assertFalse(
            fishnet._should_save_analysis_pv(self._analysis(200), self._analysis(0), "black", 1)
        )

    def test_white_move_worsens_white_saves_pv(self) -> None:
        """White blunders: winning chances drop >= 10% -> PV saved."""
        self.assertTrue(
            fishnet._should_save_analysis_pv(self._analysis(-400), self._analysis(400), "black", 1)
        )

    def test_black_move_improves_black_no_pv(self) -> None:
        """Black plays well: White's winning chances decrease -> no PV saved."""
        self.assertFalse(
            fishnet._should_save_analysis_pv(self._analysis(0), self._analysis(200), "white", 2)
        )

    def test_black_move_worsens_black_saves_pv(self) -> None:
        """Black blunders: White's winning chances rise >= 10% -> PV saved."""
        self.assertTrue(
            fishnet._should_save_analysis_pv(self._analysis(400), self._analysis(0), "white", 2)
        )

    def test_boundary_white_move_cp_minus_50_does_not_save(self) -> None:
        """White move cp 0 -> -50: drop ~0.0997, just under the 0.1 threshold -> no save."""
        self.assertFalse(
            fishnet._should_save_analysis_pv(self._analysis(-50), self._analysis(0), "black", 1)
        )

    def test_boundary_white_move_cp_minus_51_saves(self) -> None:
        """White move cp 0 -> -51: drop ~0.1016, crosses the 0.1 threshold -> save."""
        self.assertTrue(
            fishnet._should_save_analysis_pv(self._analysis(-51), self._analysis(0), "black", 1)
        )

    def test_small_drop_below_threshold_no_save(self) -> None:
        """Drop well below 0.1 (minor fluctuation) -> do not save PV."""
        self.assertFalse(
            fishnet._should_save_analysis_pv(self._analysis(-20), self._analysis(0), "black", 1)
        )


class FishnetAnalysisPvRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    """Exercises the real fishnet.fishnet_analysis() endpoint across multiple
    calls, reproducing fairyfishnet's partial-progress-report behaviour.

    Regression coverage for the gbtami Tur #2 finding: the old
    `if "analysis" not in game.steps[i]:` gate permanently blocked a step from
    ever receiving its PV once *any* progress report had touched it, even if
    the neighbouring ply needed for the PV decision only became available in a
    later report. See HANDOFF.md section 6.
    """

    @staticmethod
    def _score(cp: int) -> dict:
        return {"cp": cp}

    @staticmethod
    def _make_app_state(game: SimpleNamespace | Game) -> SimpleNamespace:
        if isinstance(game, SimpleNamespace):
            game.server_variant = SimpleNamespace(two_boards=True)
            game.ply = len(game.steps) - 1
        return SimpleNamespace(
            fishnet_works={"work1": {"game_id": "g1", "username": "botuser"}},
            fishnet_monitor=defaultdict(list),
            fishnet_worker_last_seen={},
            games={"g1": game},
            users={"botuser": SimpleNamespace(send_game_message=AsyncMock())},
            db=SimpleNamespace(game=SimpleNamespace(find_one_and_update=AsyncMock())),
        )

    @staticmethod
    async def _call(app_state: SimpleNamespace, game: SimpleNamespace, analysis_payload: list):
        """Invoke the real, unmodified fishnet.fishnet_analysis() once."""
        data = {"fishnet": {"apikey": "testkey"}, "analysis": analysis_payload}
        request = cast(web.Request, SimpleNamespace(match_info={"workId": "work1"}, app=None))
        with (
            patch.dict(fishnet.FISHNET_KEYS, {"testkey": "worker1"}, clear=True),
            patch("fishnet.get_app_state", return_value=app_state),
            patch("fishnet._read_fishnet_json", new=AsyncMock(return_value=(data, None))),
            patch("fishnet.load_game", new=AsyncMock(return_value=game)),
        ):
            return await fishnet.fishnet_analysis(request)

    async def test_partial_report_then_full_report_adds_missing_pv(self) -> None:
        # ply 0: White's move (neutral eval). ply 1: Black's move that blunders,
        # swinging White's winning chances from ~0 to strongly positive.
        game = SimpleNamespace(id="g1", steps=[{"turnColor": "black"}, {"turnColor": "white"}])
        app_state = self._make_app_state(game)
        analysis_ply0 = {"score": self._score(0), "pv": "e2e4", "depth": 20}
        analysis_ply1 = {"score": self._score(400), "pv": "Qxf7+", "depth": 18}

        # Call 1: fairyfishnet has only finished ply 1 so far; ply 0 is still
        # None, so prev for ply 1 is unavailable and the PV cannot be decided.
        await self._call(app_state, game, [None, analysis_ply1])

        self.assertNotIn("p", game.steps[1]["analysis"])
        self.assertNotIn("analysis", game.steps[0])
        self.assertEqual(app_state.users["botuser"].send_game_message.await_count, 1)
        self.assertIn("work1", app_state.fishnet_works)  # not complete yet

        # Call 2: ply 0 has now also arrived. Under the old gate, ply 1 already
        # having an "analysis" dict meant it was skipped forever and "p" could
        # never be added even though prev is now known - that must not happen.
        await self._call(app_state, game, [analysis_ply0, analysis_ply1])

        self.assertEqual(game.steps[1]["analysis"]["p"], "Qxf7+")
        self.assertNotIn("p", game.steps[0]["analysis"])  # ply 0 never has a prev
        # 1 message from call 1 (ply1, no PV yet) + 2 from call 2 (ply1 gains
        # PV, ply0 is created for the first time).
        self.assertEqual(app_state.users["botuser"].send_game_message.await_count, 3)
        self.assertNotIn("work1", app_state.fishnet_works)  # all analysed -> cleaned up
        app_state.db.game.find_one_and_update.assert_awaited_once()

    async def test_unchanged_step_does_not_resend_message(self) -> None:
        """A step that already has its final analysis (PV included, where
        applicable) must not trigger another websocket message when the same
        report is redelivered - only newly created or newly-PV'd steps notify.
        """
        game = SimpleNamespace(
            id="g1",
            steps=[
                {"turnColor": "black", "analysis": {"s": {"cp": 0}, "d": 20}},
                {"turnColor": "white", "analysis": {"s": {"cp": 400}, "p": "Qxf7+", "d": 18}},
            ],
        )
        app_state = self._make_app_state(game)
        analysis_ply0 = {"score": self._score(0), "pv": "e2e4", "depth": 20}
        analysis_ply1 = {"score": self._score(400), "pv": "Qxf7+", "depth": 18}

        await self._call(app_state, game, [analysis_ply0, analysis_ply1])

        app_state.users["botuser"].send_game_message.assert_not_awaited()
        self.assertNotIn("work1", app_state.fishnet_works)
        app_state.db.game.find_one_and_update.assert_awaited_once()

    async def test_extra_worker_row_is_ignored_for_zero_ply_game(self) -> None:
        """fairyfishnet 1.16.69 splits an empty moves string into one empty
        item, returning two rows for a game whose only step is its start
        position. The extra row must not index past game.steps.
        """
        game = SimpleNamespace(id="g1", steps=[{"turnColor": "white"}])
        app_state = self._make_app_state(game)
        initial_position = {"score": self._score(15), "pv": "e2e4", "depth": 20}
        duplicate_extra_row = {"score": self._score(15), "pv": "e2e4", "depth": 20}

        response = await self._call(
            app_state,
            game,
            [initial_position, duplicate_extra_row],
        )

        self.assertEqual(response.status, 204)
        self.assertEqual(game.steps[0]["analysis"], {"s": {"cp": 15}, "d": 20})
        self.assertEqual(app_state.users["botuser"].send_game_message.await_count, 1)
        self.assertNotIn("work1", app_state.fishnet_works)
        app_state.db.game.find_one_and_update.assert_awaited_once_with(
            {"_id": "g1"},
            {"$set": {"a": [{"s": {"cp": 15}, "d": 20}]}},
        )

    async def test_short_worker_response_remains_pending(self) -> None:
        game = SimpleNamespace(
            id="g1",
            steps=[{"turnColor": "white"}, {"turnColor": "black"}],
        )
        app_state = self._make_app_state(game)
        initial_position = {"score": self._score(15), "pv": "e2e4", "depth": 20}

        response = await self._call(app_state, game, [initial_position])

        self.assertEqual(response.status, 204)
        self.assertIn("work1", app_state.fishnet_works)
        app_state.db.game.find_one_and_update.assert_not_awaited()


class FishnetVariantsEndpointTestCase(unittest.IsolatedAsyncioTestCase):
    def test_variants_payload_cache_keeps_rules_pinned_by_pending_study_work(self):
        first = {
            "variantsIni": "a" * 10,
            "variantsSha256": "a" * 64,
            "variantsScope": "studysnap_aaaaaaaaaaaa",
        }
        second = {
            "variantsIni": "b" * 10,
            "variantsSha256": "b" * 64,
            "variantsScope": "studysnap_bbbbbbbbbbbb",
        }
        app_state = SimpleNamespace(
            fishnet_variant_payloads={},
            fishnet_works={
                "studywork": {
                    "work": {"type": "analysis", "id": "studywork"},
                    "variantsSha256": first["variantsSha256"],
                }
            },
        )

        with patch.object(fishnet, "FISHNET_VARIANTS_PAYLOAD_CACHE_MAX_BYTES", 15):
            fishnet._cache_fishnet_variants_payload(app_state, first)
            fishnet._cache_fishnet_variants_payload(app_state, second)

        self.assertEqual(
            set(app_state.fishnet_variant_payloads),
            {first["variantsSha256"], second["variantsSha256"]},
        )
        self.assertGreater(fishnet.fishnet_variants_payload_cache_bytes(app_state), 15)

    def test_exact_study_snapshot_payload_survives_attach(self):
        app_state = SimpleNamespace(
            fishnet_variant_payloads={}, fishnet_works={}, catalogued_variants={}
        )
        alias = "studysnap_0123456789ab"
        payload = fishnet.fishnet_variants_payload_from_ini(
            app_state,
            alias,
            f"[{alias}:chess]\ncustomPiece1 = a:KN\n",
        )
        work = {
            "work": {"type": "analysis", "id": "studywork"},
            "study_id": "study001",
            "chapter_id": "chapter1",
            "study_path": "StudyNode1",
            "position": "startpos",
            "variant": alias,
            "chess960": False,
            "moves": "e2e4",
            "nnue": True,
            "variantsSha256": payload["variantsSha256"],
            "variantsScope": alias,
        }
        app_state.fishnet_works["studywork"] = work

        fishnet._attach_variants_hash(app_state, work)

        self.assertEqual(work["variantsSha256"], payload["variantsSha256"])
        self.assertEqual(work["variantsScope"], alias)
        self.assertEqual(
            app_state.fishnet_variant_payloads[payload["variantsSha256"]]["variantsIni"],
            f"[{alias}:chess]\ncustomPiece1 = a:KN\n",
        )

    def test_variants_payload_cache_has_byte_budget(self):
        app_state = SimpleNamespace(fishnet_variant_payloads={})
        first = {
            "variantsIni": "a" * 10,
            "variantsSha256": "a" * 64,
        }
        second = {
            "variantsIni": "b" * 10,
            "variantsSha256": "b" * 64,
        }

        with patch.object(fishnet, "FISHNET_VARIANTS_PAYLOAD_CACHE_MAX_BYTES", 15):
            fishnet._cache_fishnet_variants_payload(app_state, first)
            fishnet._cache_fishnet_variants_payload(app_state, second)

        self.assertEqual(set(app_state.fishnet_variant_payloads), {second["variantsSha256"]})
        self.assertLessEqual(fishnet.fishnet_variants_payload_cache_bytes(app_state), 15)

    async def test_variants_endpoint_rejects_unavailable_exact_hash(self):
        app_state = SimpleNamespace(catalogued_variants={})
        request = cast(web.Request, AsyncMock())
        request.app = {pychess_global_app_state_key: app_state}
        request.match_info = {"key": "k"}
        request.query = {"sha256": "a" * 64, "variant": "grandhouse"}

        with patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True):
            response = await fishnet.fishnet_variants(request)

        self.assertEqual(response.status, 409)
        payload = json.loads(response.text)
        self.assertIn("no longer available", payload["error"])
        self.assertRegex(payload["variantsSha256"], r"^[0-9a-f]{64}$")

    async def test_variants_endpoint_returns_cached_exact_payload(self):
        cached = {
            "variantsIni": "[old]\n",
            "variantsSha256": "b" * 64,
            "variantsScope": "grandhouse",
        }
        app_state = SimpleNamespace(
            catalogued_variants={},
            fishnet_variant_payloads={cached["variantsSha256"]: cached},
        )
        request = cast(web.Request, AsyncMock())
        request.app = {pychess_global_app_state_key: app_state}
        request.match_info = {"key": "k"}
        request.query = {"sha256": cached["variantsSha256"], "variant": "grandhouse"}

        with patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True):
            response = await fishnet.fishnet_variants(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text), cached)


class FishnetCapabilityTestCase(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _move_work(work_id: str, variant: str):
        return {
            "work": {"type": "move", "id": work_id, "level": 1},
            "game_id": "g1",
            "position": "startpos",
            "variant": variant,
            "chess960": False,
            "moves": "",
            "nnue": True,
            "time": 100.0,
        }

    @staticmethod
    def _app_state(works):
        queue = asyncio.PriorityQueue()
        for work_id in works:
            queue.put_nowait((fishnet.MOVE, work_id))
        return SimpleNamespace(
            fishnet_monitor=defaultdict(list, {"worker1": []}),
            fishnet_queue=queue,
            fishnet_works=works,
            workers={"k"},
            fishnet_worker_last_seen={"k": 100.0},
            fishnet_worker_capability_last_seen={},
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
            catalogued_variants={},
        )

    async def test_worker_without_alice_capability_skips_alice_queue_item(self):
        works = {
            "a-alice": self._move_work("a-alice", "alice"),
            "z-chess": self._move_work("z-chess", "chess"),
        }
        app_state = self._app_state(works)
        payload = {"fishnet": {"apikey": "k"}}

        with patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True):
            response = await fishnet.get_work(app_state, payload)

        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.text)["work"]["id"], "z-chess")
        self.assertEqual(app_state.fishnet_queue.qsize(), 1)
        self.assertEqual(app_state.fishnet_queue.get_nowait()[1], "a-alice")

    async def test_alice_capable_worker_receives_alice_job(self):
        works = {"a-alice": self._move_work("a-alice", "alice")}
        app_state = self._app_state(works)
        payload = {
            "fishnet": {
                "apikey": "k",
                "capabilities": {"variants": ["alice"]},
            }
        }

        with patch.dict(fishnet.FISHNET_KEYS, {"k": "worker1"}, clear=True):
            response = await fishnet.get_work(app_state, payload)

        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.text)["work"]["id"], "a-alice")

    def test_alice_stockfish_online_tracks_capable_worker(self):
        now = 1000.0
        alice = SimpleNamespace(online=False)
        app_state = SimpleNamespace(
            workers={"k"},
            fishnet_worker_last_seen={"k": now},
            fishnet_worker_capability_last_seen={("k", "alice"): now},
            users={
                "Fairy-Stockfish": SimpleNamespace(online=True),
                "Alice-Stockfish": alice,
            },
        )

        fishnet._sync_alice_stockfish_online(app_state, now=now)
        self.assertTrue(alice.online)

        app_state.fishnet_worker_capability_last_seen[("k", "alice")] = (
            now - fishnet.FISHNET_ACTIVITY_TIMEOUT - 1.0
        )
        fishnet._sync_alice_stockfish_online(app_state, now=now)
        self.assertFalse(alice.online)

    def test_variant_specific_availability_uses_capability_heartbeat(self):
        now = 1000.0
        app_state = SimpleNamespace(
            workers={"k"},
            fishnet_worker_last_seen={"k": now},
            fishnet_worker_capability_last_seen={
                ("k", "alice"): now - fishnet.FISHNET_ACTIVITY_TIMEOUT - 1.0
            },
            fishnet_monitor=defaultdict(list),
            users={"Fairy-Stockfish": SimpleNamespace(online=True)},
        )

        self.assertTrue(fishnet.has_available_fishnet_worker(app_state, variant="chess", now=now))
        self.assertFalse(fishnet.has_available_fishnet_worker(app_state, variant="alice", now=now))

        app_state.fishnet_worker_capability_last_seen.clear()
        self.assertFalse(
            fishnet.has_available_fishnet_worker(app_state, variant="alice", now=100.0)
        )

        fishnet._record_fishnet_capabilities(
            app_state,
            {
                "fishnet": {
                    "apikey": "k",
                    "capabilities": {"variants": ["alice"]},
                }
            },
            now=now,
        )
        self.assertTrue(fishnet.has_available_fishnet_worker(app_state, variant="alice", now=now))

    async def test_alice_analysis_without_capable_worker_does_not_use_legacy_bot(self):
        now = fishnet.monotonic()
        game = SimpleNamespace(
            id="g-alice",
            steps=[],
            board=SimpleNamespace(
                initial_fen="startpos", move_stack=[], nnue=True, variant="alice"
            ),
            variant="alice",
            chess960=False,
        )
        engine = SimpleNamespace(online=True, game_queues={}, event_queue=asyncio.Queue())
        app_state = SimpleNamespace(
            games={"g-alice": game},
            users={"Fairy-Stockfish": engine},
            workers={"k"},
            fishnet_worker_last_seen={"k": now},
            fishnet_worker_capability_last_seen={},
            fishnet_monitor=defaultdict(list),
            fishnet_works={},
            fishnet_queue=asyncio.PriorityQueue(),
            catalogued_variants={},
        )
        ws_send_json = AsyncMock()

        with patch("wsr.ws_send_json", new=ws_send_json):
            await wsr.handle_analysis(
                app_state,
                SimpleNamespace(),
                {"gameId": "g-alice", "username": "u"},
                game,
            )

        self.assertEqual(app_state.fishnet_works, {})
        self.assertEqual(engine.event_queue.qsize(), 0)
        self.assertEqual(
            ws_send_json.await_args.args[1]["message"],
            "Analysis unavailable right now.",
        )

    async def test_alice_analysis_without_any_fishnet_worker_does_not_use_legacy_bot(self):
        game = SimpleNamespace(
            id="g-alice",
            steps=[],
            board=SimpleNamespace(
                initial_fen="startpos", move_stack=[], nnue=True, variant="alice"
            ),
            variant="alice",
            chess960=False,
        )
        engine = SimpleNamespace(online=True, game_queues={}, event_queue=asyncio.Queue())
        app_state = SimpleNamespace(
            games={"g-alice": game},
            users={"Fairy-Stockfish": engine},
            workers=set(),
            fishnet_worker_last_seen={},
            fishnet_worker_capability_last_seen={},
            fishnet_monitor=defaultdict(list),
            fishnet_works={},
            fishnet_queue=asyncio.PriorityQueue(),
            catalogued_variants={},
        )
        ws_send_json = AsyncMock()

        with patch("wsr.ws_send_json", new=ws_send_json):
            await wsr.handle_analysis(
                app_state,
                SimpleNamespace(),
                {"gameId": "g-alice", "username": "u"},
                game,
            )

        self.assertEqual(app_state.fishnet_works, {})
        self.assertEqual(engine.event_queue.qsize(), 0)
        self.assertEqual(
            ws_send_json.await_args.args[1]["message"],
            "Analysis unavailable right now.",
        )
