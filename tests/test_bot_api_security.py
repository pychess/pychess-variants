import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import bot_api
from aiohttp.test_utils import AioHTTPTestCase
from bot_accounts import create_bot_token
from const import INVALIDMOVE, STARTED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from seek import BOT_CHALLENGE_DECLINED, Seek
from user import User
from utils import play_move
from variants import VARIANTS

from server import make_app

PERFS = new_default_perf_map(VARIANTS)


class BotApiSecurityTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=cast(Any, AsyncMongoMockClient(tz_aware=True)))

    async def tearDownAsync(self):
        await self.client.close()

    async def create_bot(self, username: str) -> tuple[User, str]:
        app_state = get_app_state(self.app)
        user = User(app_state, bot=True, username=username, title="BOT", perfs=PERFS)
        app_state.users[user.username] = user
        await app_state.db.user.insert_one(
            {
                "_id": username,
                "username_lower": username.lower(),
                "enabled": True,
                "title": "BOT",
                "count": {"game": 0, "win": 0, "loss": 0, "draw": 0, "rated": 0},
            }
        )
        _, raw_token = await create_bot_token(app_state, username, f"{username} token")
        return user, raw_token

    @staticmethod
    def auth_headers(raw_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {raw_token}"}

    @classmethod
    def event_stream_headers(cls, raw_token: str, variants: list[str]) -> dict[str, str]:
        return cls.auth_headers(raw_token) | {
            bot_api.BOT_CAPABILITIES_HEADER: json.dumps(
                {"version": bot_api.BOT_CAPABILITIES_VERSION, "variants": variants}
            )
        }

    async def test_challenge_accept_and_decline_require_invited_bot(self):
        app_state = get_app_state(self.app)
        challenger = User(app_state, username="human", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        owner_bot, _ = await self.create_bot("owner-bot")
        _, other_token = await self.create_bot("other-bot")

        seek = Seek(
            "seek1234",
            challenger,
            "chess",
            target="BOT_challenge",
            player1=challenger,
            player2=owner_bot,
            game_id="abcd1234",
            rated=False,
        )
        app_state.invites["abcd1234"] = seek

        for path in ("/api/challenge/abcd1234/accept", "/api/challenge/abcd1234/decline"):
            response = await self.client.post(path, headers=self.auth_headers(other_token))
            self.assertEqual(response.status, 403, path)

    async def test_challenge_decline_preserves_reason_for_invited_bot_challenge(self):
        app_state = get_app_state(self.app)
        challenger = User(app_state, username="human", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        owner_bot, owner_token = await self.create_bot("owner-bot")

        seek = Seek(
            "seek1234",
            challenger,
            "atomic",
            target="BOT_challenge",
            player1=challenger,
            player2=owner_bot,
            game_id="abcd1234",
            rated=False,
        )
        app_state.seeks[seek.id] = seek
        challenger.seeks[seek.id] = seek
        app_state.invites["abcd1234"] = seek
        queue: asyncio.Queue[str] = asyncio.Queue()
        app_state.invite_channels["abcd1234"] = {queue}

        response = await self.client.post(
            "/api/challenge/abcd1234/decline",
            headers=self.auth_headers(owner_token),
            data={"reason": "variant"},
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(BOT_CHALLENGE_DECLINED, seek.bot_challenge_status)
        self.assertEqual(
            "I'm not willing to play this variant right now.",
            seek.bot_challenge_decline_reason,
        )

        payload = await queue.get()
        self.assertIn('"accept":false', payload)
        self.assertIn('"declineReason":"I\'m not willing to play this variant right now."', payload)

    async def test_challenge_accept_does_not_wait_for_browser_subscriber(self):
        app_state = get_app_state(self.app)
        challenger = User(app_state, username="human", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        owner_bot, owner_token = await self.create_bot("owner-bot")

        seek = Seek(
            "seek1234",
            challenger,
            "chess",
            target="BOT_challenge",
            player1=challenger,
            player2=owner_bot,
            game_id="abcd1234",
            rated=False,
        )
        app_state.seeks[seek.id] = seek
        challenger.seeks[seek.id] = seek
        app_state.invites["abcd1234"] = seek

        with patch(
            "bot_api.asyncio.wait_for",
            side_effect=AssertionError("challenge_accept must not wait for SSE"),
        ):
            response = await self.client.post(
                "/api/challenge/abcd1234/accept",
                headers=self.auth_headers(owner_token),
            )

        self.assertEqual(response.status, 200)
        self.assertIn("abcd1234", app_state.games)

    async def test_challenge_decline_does_not_wait_for_browser_subscriber(self):
        app_state = get_app_state(self.app)
        challenger = User(app_state, username="human", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        owner_bot, owner_token = await self.create_bot("owner-bot")

        seek = Seek(
            "seek1234",
            challenger,
            "atomic",
            target="BOT_challenge",
            player1=challenger,
            player2=owner_bot,
            game_id="abcd1234",
            rated=False,
        )
        app_state.seeks[seek.id] = seek
        challenger.seeks[seek.id] = seek
        app_state.invites["abcd1234"] = seek

        with patch(
            "bot_api.asyncio.wait_for",
            side_effect=AssertionError("challenge_decline must not wait for SSE"),
        ):
            response = await self.client.post(
                "/api/challenge/abcd1234/decline",
                headers=self.auth_headers(owner_token),
                data={"reason": "variant"},
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(BOT_CHALLENGE_DECLINED, seek.bot_challenge_status)

    async def test_user_status_is_lichess_bot_compatible(self):
        bot, _ = await self.create_bot("status-bot")
        bot.online = True

        response = await self.client.get("/api/users/status?ids=status-bot")

        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), [{"id": "status-bot", "online": True}])

        bot.patron = True
        response = await self.client.get("/api/users/status?ids=status-bot")
        self.assertEqual(
            await response.json(), [{"id": "status-bot", "online": True, "patron": True}]
        )

    async def test_event_stream_disconnect_marks_bot_offline(self):
        bot, token = await self.create_bot("owner-bot")

        with (
            patch("bot_api.BOT_API_ONLINE_TTL_SECONDS", 0.01),
            patch(
                "bot_api.web.StreamResponse.write",
                side_effect=ConnectionResetError("disconnect"),
            ),
        ):
            response = await self.client.get(
                "/api/stream/event",
                headers=self.event_stream_headers(
                    token, ["standard", "chess960", "crazyhouse960", "not-on-pychess"]
                ),
            )

            self.assertEqual(response.status, 200)
            self.assertTrue(bot.online)

            for _ in range(40):
                if not bot.online:
                    break
                await asyncio.sleep(0.01)

        self.assertFalse(bot.online)
        self.assertEqual({"chess", "chess960", "crazyhouse960"}, bot.bot_supported_variants)
        response.close()

    async def test_event_stream_requires_capabilities(self):
        _, token = await self.create_bot("missing-capabilities-bot")

        response = await self.client.get(
            "/api/stream/event",
            headers=self.auth_headers(token),
        )

        self.assertEqual(response.status, 400)
        self.assertIn(bot_api.BOT_CAPABILITIES_HEADER, await response.text())

    async def test_bot_stream_write_times_out(self):
        async def blocked_write(_payload):
            await asyncio.Event().wait()

        response = SimpleNamespace(write=blocked_write)
        with (
            patch("bot_api.BOT_STREAM_WRITE_TIMEOUT_SECONDS", 0.01),
            self.assertRaises(TimeoutError),
        ):
            await bot_api._write_bot_stream_payload(response, "payload")

    async def test_bot_ping_is_coalesced_behind_pending_payload(self):
        queue = asyncio.Queue[str]()
        queue.put_nowait("semantic-event")

        self.assertFalse(bot_api._enqueue_bot_ping_if_idle(queue))
        self.assertEqual(queue.qsize(), 1)

        self.assertEqual(queue.get_nowait(), "semantic-event")
        queue.task_done()
        self.assertTrue(bot_api._enqueue_bot_ping_if_idle(queue))
        self.assertFalse(bot_api._enqueue_bot_ping_if_idle(queue))
        self.assertEqual(queue.qsize(), 1)

    async def create_external_bot_game(self) -> tuple[Game, str, User]:
        app_state = get_app_state(self.app)
        bot, token = await self.create_bot("retry-bot")
        human = User(app_state, username="retry-human", perfs=PERFS)
        app_state.users[human.username] = human
        game = Game(app_state, "retry123", "chess", "", bot, human, rated=False)
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()
        return game, token, human

    async def test_external_bot_move_retry_after_opponent_reply_does_not_forfeit(self):
        game, token, human = await self.create_external_bot_game()
        url = f"/api/bot/game/{game.id}/move/"
        headers = self.auth_headers(token)

        response = await self.client.post(url + "e2e4", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"ok": True})
        self.assertEqual(game.board.move_stack, ["e2e4"])

        # The original POST succeeded, but the BOT timed out before reading its
        # response. The human replies while pychess-bot retries that same POST.
        async with game.move_lock:
            await play_move(get_app_state(self.app), human, game, "e7e5")
        self.assertEqual(game.board.move_stack, ["e2e4", "e7e5"])

        response = await self.client.post(url + "e2e4", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"ok": True})
        self.assertEqual(game.board.move_stack, ["e2e4", "e7e5"])
        self.assertEqual(game.status, STARTED)
        self.assertEqual(game.result, "*")

        # Normal play still works after the harmless retry.
        response = await self.client.post(url + "g1f3", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(game.board.move_stack, ["e2e4", "e7e5", "g1f3"])
        self.assertEqual(game.status, STARTED)

    async def test_legal_repeated_external_bot_move_is_not_suppressed(self):
        game, token, human = await self.create_external_bot_game()
        headers = self.auth_headers(token)
        await self.client.post(f"/api/bot/game/{game.id}/move/e2e4", headers=headers)
        async with game.move_lock:
            await play_move(get_app_state(self.app), human, game, "e7e5")

        # A second move with identical notation can be legal in a drop variant.
        # Simulate that legal-move result to ensure the retry heuristic does not
        # swallow moves merely because their notation repeats.
        async def check_locked(*_args):
            self.assertTrue(game.move_lock.locked())

        with (
            patch.object(game.board, "legal_moves", return_value=["e2e4"]),
            patch("bot_api.play_move", side_effect=check_locked) as mock_play,
        ):
            response = await self.client.post(f"/api/bot/game/{game.id}/move/e2e4", headers=headers)
        self.assertEqual(response.status, 200)
        mock_play.assert_awaited_once_with(get_app_state(self.app), game.wplayer, game, "e2e4")

    async def test_unrelated_invalid_external_bot_move_still_forfeits(self):
        game, token, human = await self.create_external_bot_game()
        response = await self.client.post(
            f"/api/bot/game/{game.id}/move/e2e4",
            headers=self.auth_headers(token),
        )
        self.assertEqual(response.status, 200)
        async with game.move_lock:
            await play_move(get_app_state(self.app), human, game, "e7e5")

        response = await self.client.post(
            f"/api/bot/game/{game.id}/move/e2e5",
            headers=self.auth_headers(token),
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(game.status, INVALIDMOVE)
        self.assertEqual(game.result, "0-1")

    async def test_bot_game_endpoints_require_authenticated_bot_to_be_player(self):
        app_state = get_app_state(self.app)
        owner_bot, _ = await self.create_bot("owner-bot")
        _, other_token = await self.create_bot("other-bot")
        human = User(app_state, username="human", perfs=PERFS)
        app_state.users[human.username] = human

        game = Game(app_state, "game1234", "chess", "", owner_bot, human, rated=False)
        app_state.games[game.id] = game

        requests = (
            ("get", f"/api/bot/game/stream/{game.id}", {}),
            ("post", f"/api/bot/game/{game.id}/move/e2e4", {}),
            ("post", f"/api/bot/game/{game.id}/abort", {}),
            ("post", f"/api/bot/game/{game.id}/resign", {}),
            ("post", f"/api/bot/game/{game.id}/chat", {"data": {"room": "player", "text": "hi"}}),
        )

        for method, path, kwargs in requests:
            response = await getattr(self.client, method)(
                path,
                headers=self.auth_headers(other_token),
                **kwargs,
            )
            self.assertEqual(response.status, 403, path)
