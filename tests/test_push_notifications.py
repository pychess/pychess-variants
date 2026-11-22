import asyncio
import json
import time
import unittest
from types import SimpleNamespace
from typing import cast

import push_notifications
import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp.web_ws import WebSocketResponse
from mongomock_motor import AsyncMongoMockClient
from notify import NOTIFICATION_CACHE_LIMIT, notify
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app

test_logger.init_test_logger()


class PushSubscribeTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_push_subscribe_stores_subscription(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True

        user = User(app_state, username="push_user")
        app_state.users[user.username] = user
        self.set_session_user(user.username)

        payload = {
            "endpoint": "https://example.com/sub/1",
            "keys": {
                "auth": "auth-key",
                "p256dh": "p256dh-key",
            },
        }

        response = await self.client.post("/push/subscribe", json=payload)
        self.assertEqual(response.status, 200)

        stored = await app_state.db.push_subscription.find_one({"user": user.username})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["endpoint"], payload["endpoint"])
        self.assertEqual(stored["auth"], payload["keys"]["auth"])
        self.assertEqual(stored["p256dh"], payload["keys"]["p256dh"])

    async def test_push_subscribe_rejects_anon_user(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True

        anon_user = User(app_state, username="Anon-push", anon=True)
        app_state.users[anon_user.username] = anon_user
        self.set_session_user(anon_user.username)

        payload = {
            "endpoint": "https://example.com/sub/2",
            "keys": {
                "auth": "auth-key",
                "p256dh": "p256dh-key",
            },
        }

        response = await self.client.post("/push/subscribe", json=payload)
        self.assertEqual(response.status, 403)

    async def test_push_unsubscribe_removes_only_requested_endpoint(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="unsub_user")
        app_state.users[user.username] = user
        self.set_session_user(user.username)

        await app_state.db.push_subscription.insert_many(
            [
                {
                    "user": user.username,
                    "endpoint": "https://example.com/sub/1",
                    "auth": "auth-key-1",
                    "p256dh": "p256dh-key-1",
                },
                {
                    "user": user.username,
                    "endpoint": "https://example.com/sub/2",
                    "auth": "auth-key-2",
                    "p256dh": "p256dh-key-2",
                },
            ]
        )

        response = await self.client.post(
            "/push/unsubscribe",
            json={"endpoint": "https://example.com/sub/1"},
        )
        self.assertEqual(response.status, 200)

        first = await app_state.db.push_subscription.find_one(
            {"user": user.username, "endpoint": "https://example.com/sub/1"}
        )
        second = await app_state.db.push_subscription.find_one(
            {"user": user.username, "endpoint": "https://example.com/sub/2"}
        )
        self.assertIsNone(first)
        self.assertIsNotNone(second)

    async def test_push_unsubscribe_without_endpoint_removes_all_user_subscriptions(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="unsub_all_user")
        app_state.users[user.username] = user
        self.set_session_user(user.username)

        await app_state.db.push_subscription.insert_many(
            [
                {
                    "user": user.username,
                    "endpoint": "https://example.com/sub/1",
                    "auth": "auth-key-1",
                    "p256dh": "p256dh-key-1",
                },
                {
                    "user": user.username,
                    "endpoint": "https://example.com/sub/2",
                    "auth": "auth-key-2",
                    "p256dh": "p256dh-key-2",
                },
            ]
        )

        response = await self.client.post("/push/unsubscribe", json={})
        self.assertEqual(response.status, 200)

        remaining = await app_state.db.push_subscription.count_documents({"user": user.username})
        self.assertEqual(remaining, 0)

    async def test_corr_browser_pref_persists_independently_of_push(self):
        app_state = get_app_state(self.app)
        username = "browser_pref_user"
        await app_state.db.user.insert_one({"_id": username, "cps": False})
        user = await app_state.users.get(username)
        self.assertTrue(user.corr_browser_enabled)
        self.set_session_user(username)

        for value in (False, True):
            response = await self.client.post(
                "/pref/corr-browser", data={"corr_browser": str(value).lower()}
            )
            self.assertEqual(response.status, 204)
            self.assertEqual(app_state.users[username].corr_browser_enabled, value)
            stored = await app_state.db.user.find_one({"_id": username})
            self.assertEqual(stored["cbs"], value)
            self.assertFalse(stored["cps"])

            app_state.users.data.pop(username, None)
            reloaded = await app_state.users.get(username)
            self.assertEqual(reloaded.corr_browser_enabled, value)
            self.assertFalse(reloaded.corr_push_enabled)

            response = await self.client.get("/")
            self.assertIn(f'data-corr-browser-enabled="{value}"', await response.text())

    async def test_corr_browser_pref_rejects_anon_user(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="Anon-browser-pref", anon=True)
        app_state.users[user.username] = user
        self.set_session_user(user.username)

        response = await self.client.post("/pref/corr-browser", data={"corr_browser": "false"})
        self.assertEqual(response.status, 403)
        self.assertTrue(user.corr_browser_enabled)

    async def test_corr_push_pref_updates_user_and_db(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="pref_user")
        app_state.users[user.username] = user
        await app_state.db.user.insert_one({"_id": user.username})
        self.set_session_user(user.username)

        response = await self.client.post(
            "/pref/corr-push",
            data={"corr_push": "false"},
        )
        self.assertEqual(response.status, 204)
        self.assertFalse(user.corr_push_enabled)

        stored = await app_state.db.user.find_one({"_id": user.username})
        self.assertIsNotNone(stored)
        self.assertFalse(stored["cps"])

    async def test_corr_push_pref_rejects_anon_user(self):
        app_state = get_app_state(self.app)
        anon_user = User(app_state, username="Anon-pref", anon=True)
        app_state.users[anon_user.username] = anon_user
        self.set_session_user(anon_user.username)

        response = await self.client.post(
            "/pref/corr-push",
            data={"corr_push": "false"},
        )
        self.assertEqual(response.status, 403)

    async def test_rr_push_pref_updates_user_and_db(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="rr_pref_user")
        app_state.users[user.username] = user
        await app_state.db.user.insert_one({"_id": user.username})
        self.set_session_user(user.username)

        response = await self.client.post(
            "/pref/rr-push",
            data={"rr_push": "true"},
        )
        self.assertEqual(response.status, 204)
        self.assertTrue(user.rr_push_enabled)

        stored = await app_state.db.user.find_one({"_id": user.username})
        self.assertIsNotNone(stored)
        self.assertTrue(stored["rps"])

        app_state.users.data.pop(user.username, None)
        reloaded = await app_state.users.get(user.username)
        self.assertTrue(reloaded.rr_push_enabled)

    async def test_rr_push_pref_rejects_anon_user(self):
        app_state = get_app_state(self.app)
        anon_user = User(app_state, username="Anon-rr-pref", anon=True)
        app_state.users[anon_user.username] = anon_user
        self.set_session_user(anon_user.username)

        response = await self.client.post(
            "/pref/rr-push",
            data={"rr_push": "true"},
        )
        self.assertEqual(response.status, 403)

    async def test_enqueue_skips_when_corr_push_pref_is_disabled(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        user = User(app_state, username="pref_disabled")
        user.corr_push_enabled = False

        app_state.push_notifier.enqueue_corr_move(
            user,
            game_id="abcd1234",
            opponent="opponent",
            san="e4",
        )
        self.assertEqual(app_state.push_notifier.queue.qsize(), 0)

    async def test_queued_corr_push_respects_later_opt_out(self):
        app_state = get_app_state(self.app)
        notifier = app_state.push_notifier
        notifier.enabled = True
        username = "corr_opt_out_after_enqueue"
        user = User(app_state, username=username)
        app_state.users[username] = user
        await app_state.db.user.insert_one({"_id": username, "cps": True})
        notifier.enqueue_corr_move(user, game_id="abcd1234", opponent="opp", san="e4")
        job = notifier.queue.get_nowait()
        notifier.queue.task_done()
        await app_state.db.user.update_one({"_id": username}, {"$set": {"cps": False}})

        from unittest.mock import AsyncMock

        notifier._deliver_payload = AsyncMock()
        await notifier._deliver_corr_move(job)
        notifier._deliver_payload.assert_not_awaited()

    async def test_rr_push_queues_for_offline_opted_in_user_without_materializing(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        username = "rr_offline_push"
        await app_state.db.user.insert_one({"_id": username, "rps": True})

        await app_state.push_notifier.enqueue_rr_arrangement(
            username,
            tournament_id="rrtour01",
            arrangement_id="arr-1",
            opponent="opponent",
            kind="reminder",
        )

        self.assertNotIn(username, app_state.users.data)
        job = app_state.push_notifier.queue.get_nowait()
        self.assertIsInstance(job, push_notifications.RRArrangementPushJob)
        assert isinstance(job, push_notifications.RRArrangementPushJob)
        self.assertEqual(job.kind, "reminder")
        self.assertEqual(job.arrangement_id, "arr-1")
        app_state.push_notifier.queue.task_done()

    async def test_rr_push_skips_disabled_or_live_user(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        user = User(app_state, username="rr_push_user")
        app_state.users[user.username] = user

        await app_state.push_notifier.enqueue_rr_arrangement(
            user.username,
            tournament_id="rrtour01",
            arrangement_id="arr-1",
            opponent="opponent",
            kind="confirmed",
        )
        self.assertEqual(app_state.push_notifier.queue.qsize(), 0)

        user.rr_push_enabled = True
        user.notify_channels.add(asyncio.Queue())
        await app_state.push_notifier.enqueue_rr_arrangement(
            user.username,
            tournament_id="rrtour01",
            arrangement_id="arr-1",
            opponent="opponent",
            kind="confirmed",
        )
        self.assertEqual(app_state.push_notifier.queue.qsize(), 0)

    async def test_enqueue_skips_while_user_is_playing_another_corr_game(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        user = User(app_state, username="corr_player")
        open_game = SimpleNamespace(id="open-corr-game")
        user.correspondence_games.append(open_game)
        user.add_ws_for_game(open_game.id, cast(WebSocketResponse, object()))

        app_state.push_notifier.enqueue_corr_move(
            user,
            game_id="updated-corr-game",
            opponent="opponent",
            san="e4",
        )

        self.assertEqual(app_state.push_notifier.queue.qsize(), 0)

    async def test_enqueue_continues_while_user_is_playing_a_live_game(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        user = User(app_state, username="live_player")
        user.add_ws_for_game("open-live-game", cast(WebSocketResponse, object()))

        app_state.push_notifier.enqueue_corr_move(
            user,
            game_id="updated-corr-game",
            opponent="opponent",
            san="e4",
        )

        job = app_state.push_notifier.queue.get_nowait()
        self.assertEqual(job.username, user.username)
        app_state.push_notifier.queue.task_done()

    async def test_corr_move_notification_hides_san_for_fogofwar(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="white")
        black = User(app_state, username="black")
        game = SimpleNamespace(id="foggame", wplayer=white, bplayer=black, fow=True)

        await white.notify_corr_move(game, "c3")

        self.assertIsNotNone(white.notifications)
        assert white.notifications is not None
        notification = white.notifications[-1]
        self.assertEqual(notification["type"], "corrMove")
        self.assertEqual(notification["content"]["opp"], "black")
        self.assertNotIn("san", notification["content"])

        stored = await app_state.db.notify.find_one({"notifies": "white", "type": "corrMove"})
        self.assertIsNotNone(stored)
        self.assertNotIn("san", stored["content"])

    async def test_in_memory_notification_history_is_bounded(self):
        app_state = get_app_state(self.app)
        user = User(app_state, username="bounded-notifications")
        user.notifications = []

        for index in range(NOTIFICATION_CACHE_LIMIT + 5):
            await notify(None, user, "corrMove", {"id": str(index)})

        self.assertEqual(len(user.notifications), NOTIFICATION_CACHE_LIMIT)
        self.assertEqual(user.notifications[0]["content"]["id"], "5")
        self.assertEqual(user.notifications[-1]["content"]["id"], str(NOTIFICATION_CACHE_LIMIT + 4))

    async def test_corr_push_body_hides_missing_san(self):
        self.assertEqual(
            push_notifications.PushNotifier._corr_move_body("opponent", None),
            "opponent played a move",
        )
        self.assertEqual(
            push_notifications.PushNotifier._corr_move_body("opponent", "e4"),
            "opponent played e4",
        )

    async def test_rr_push_payload_opens_arrangement(self):
        app_state = get_app_state(self.app)
        notifier = app_state.push_notifier
        notifier.enabled = True
        await app_state.db.push_subscription.insert_one(
            {
                "user": "rr_payload_user",
                "endpoint": "https://example.com/sub/rr",
                "auth": "auth-key",
                "p256dh": "p256dh-key",
                "seenAt": 1,
            }
        )

        original_webpush = push_notifications.webpush
        payloads: list[dict] = []
        try:

            def capture_webpush(*args, **kwargs):
                payloads.append(json.loads(kwargs["data"]))

            push_notifications.webpush = capture_webpush
            await notifier._deliver_rr_arrangement(
                push_notifications.RRArrangementPushJob(
                    username="rr_payload_user",
                    tournament_id="rrtour01",
                    arrangement_id="arr-1",
                    opponent="opponent",
                    kind="reminder",
                )
            )
        finally:
            push_notifications.webpush = original_webpush

        self.assertEqual(len(payloads), 1)
        self.assertIn("24 hours", payloads[0]["body"])
        self.assertEqual(payloads[0]["payload"]["url"], "/tournament/rrtour01#arr-1")

    async def test_deliver_retries_on_transient_failures_when_nothing_was_sent(self):
        app_state = get_app_state(self.app)
        notifier = app_state.push_notifier
        notifier.enabled = True
        notifier.retry_wait_initial_seconds = 0.0
        notifier.retry_wait_max_seconds = 0.0
        notifier.retry_wait_jitter_seconds = 0.0

        await app_state.db.push_subscription.insert_one(
            {
                "user": "retry_user",
                "endpoint": "https://example.com/sub/retry",
                "auth": "auth-key",
                "p256dh": "p256dh-key",
                "seenAt": 2,
            }
        )

        original_webpush = push_notifications.webpush
        calls = {"count": 0}
        try:

            def fail_webpush(*args, **kwargs):
                calls["count"] += 1
                raise RuntimeError("temporary failure")

            push_notifications.webpush = fail_webpush
            await notifier._deliver_corr_move(
                push_notifications.CorrMovePushJob(
                    username="retry_user",
                    game_id="abcd1234",
                    opponent="opp",
                    san="e4",
                )
            )
        finally:
            push_notifications.webpush = original_webpush

        self.assertEqual(calls["count"], notifier.retry_attempts)

    async def test_deliver_skips_retry_when_at_least_one_send_succeeds(self):
        app_state = get_app_state(self.app)
        notifier = app_state.push_notifier
        notifier.enabled = True
        notifier.retry_wait_initial_seconds = 0.0
        notifier.retry_wait_max_seconds = 0.0
        notifier.retry_wait_jitter_seconds = 0.0

        await app_state.db.push_subscription.insert_many(
            [
                {
                    "user": "mixed_user",
                    "endpoint": "https://example.com/sub/success",
                    "auth": "auth-key-1",
                    "p256dh": "p256dh-key-1",
                    "seenAt": 3,
                },
                {
                    "user": "mixed_user",
                    "endpoint": "https://example.com/sub/fail",
                    "auth": "auth-key-2",
                    "p256dh": "p256dh-key-2",
                    "seenAt": 2,
                },
            ]
        )

        original_webpush = push_notifications.webpush
        calls = {"count": 0}
        try:

            def mixed_webpush(*args, **kwargs):
                calls["count"] += 1
                endpoint = str(kwargs.get("subscription_info", {}).get("endpoint", ""))
                if endpoint.endswith("/fail"):
                    raise RuntimeError("temporary failure")

            push_notifications.webpush = mixed_webpush
            await notifier._deliver_corr_move(
                push_notifications.CorrMovePushJob(
                    username="mixed_user",
                    game_id="abcd1234",
                    opponent="opp",
                    san="e4",
                )
            )
        finally:
            push_notifications.webpush = original_webpush

        self.assertEqual(calls["count"], 1 + notifier.retry_attempts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
