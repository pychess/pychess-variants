import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from admin_ops_api import fishnet_key_id
from aiohttp.test_utils import AioHTTPTestCase
from event_loop_lag import loop_lag_monitor_key
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from settings import FISHNET_KEYS
from user import User

from server import make_app


class AdminOperationsTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    def add_live_user(self, username: str) -> None:
        app_state = get_app_state(self.app)
        app_state.users[username] = User(app_state, username=username)

    async def test_operations_require_admin(self):
        app_state = get_app_state(self.app)
        self.add_live_user("alice")
        self.set_session_user("alice")

        with patch("admin_ops_api.ADMINS", ["mod"]), patch("views.admin.ADMINS", ["mod"]):
            page = await self.client.get("/admin/operations")
            response = await self.client.post("/api/admin/operations/disable-anons")

        self.assertEqual(page.status, 403)
        self.assertEqual(response.status, 403)
        self.assertFalse(app_state.disable_new_anons)
        self.assertEqual(0, await app_state.db.mod_log.count_documents({}))

    async def test_operations_page_renders_status_without_fishnet_secrets(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")
        app_state.youtube.add("UCtestChannel123", "Streamer", "Variant night")
        app_state.workers.add("private-fishnet-key")
        app_state.fishnet_versions["worker-one"] = "1.16.69 Fairy-Stockfish"
        await app_state.db.fishnet.insert_one({"_id": "private-fishnet-key", "name": "worker-one"})
        await app_state.db.mod_log.insert_one(
            {
                "_id": "operation-log",
                "mod": "mod",
                "user": "site",
                "action": "stream_added",
                "details": "UCtestChannel123 (Streamer)",
                "createdAt": datetime(2026, 8, 16, tzinfo=UTC),
            }
        )

        with (
            patch.dict(FISHNET_KEYS, {"private-fishnet-key": "worker-one"}, clear=True),
            patch("views.admin.ADMINS", ["mod"]),
        ):
            response = await self.client.get("/admin/operations?done=stream_added")

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn("Site operations", body)
        self.assertIn("Variant night", body)
        self.assertIn("worker-one", body)
        self.assertIn("Active", body)
        self.assertIn(fishnet_key_id("private-fishnet-key"), body)
        self.assertNotIn("private-fishnet-key", body)
        self.assertIn("Add YouTube stream completed.", body)
        self.assertIn("Recent site operations", body)

    async def test_event_loop_lag_toggle_is_admin_only_immediate_and_audited(self):
        monitor = self.app[loop_lag_monitor_key]
        self.assertFalse(monitor.enabled)
        self.add_live_user("alice")
        self.add_live_user("mod")
        self.set_session_user("alice")
        with patch("admin_ops_api.ADMINS", ["mod"]):
            forbidden = await self.client.post("/api/admin/operations/loop-lag-enable")
        self.assertEqual(forbidden.status, 403)
        self.assertFalse(monitor.enabled)

        self.client.session.cookie_jar.clear()
        self.set_session_user("mod")
        with (
            patch("admin_ops_api.ADMINS", ["mod"]),
            patch("views.admin.ADMINS", ["mod"]),
        ):
            enabled = await self.client.post("/api/admin/operations/loop-lag-enable")
            duplicate = await self.client.post("/api/admin/operations/loop-lag-enable")
            self.assertTrue(monitor.enabled)
            self.assertIsNotNone(monitor._handle)
            page = await self.client.get("/admin/operations")
            body = await page.text()
            self.assertIn("Disable monitoring", body)
            self.assertIn("Peak scheduling delay", body)
            disabled = await self.client.post("/api/admin/operations/loop-lag-disable")
            self.assertFalse(monitor.enabled)
            self.assertIsNone(monitor._handle)
            disabled_again = await self.client.post("/api/admin/operations/loop-lag-disable")
            page_after = await self.client.get("/admin/operations")
            self.assertIn("Enable monitoring", await page_after.text())

        self.assertEqual(enabled.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(page.status, 200)
        self.assertEqual(disabled.status, 200)
        self.assertEqual(disabled_again.status, 409)
        logs = await get_app_state(self.app).db.mod_log.find({"user": "site"}).to_list(None)
        self.assertEqual(
            ["event_loop_lag_enabled", "event_loop_lag_disabled"],
            [entry["action"] for entry in logs],
        )
        self.assertTrue(all(entry["mod"] == "mod" for entry in logs))

    async def test_logging_level_update_is_admin_only_validated_and_audited(self):
        app_state = get_app_state(self.app)
        await app_state.db.config.insert_one(
            {
                "name": "logging.config",
                "value": {
                    "handlers": {"default": {"level": "DEBUG", "formatter": "standard"}},
                    "loggers": {"wsr": {"level": "DEBUG"}},
                },
            }
        )
        self.add_live_user("alice")
        self.add_live_user("mod")
        self.set_session_user("alice")
        with patch("admin_ops_api.ADMINS", ["mod"]):
            forbidden = await self.client.post(
                "/api/admin/operations/logging-level", data={"level": "INFO"}
            )
        self.assertEqual(forbidden.status, 403)

        self.client.session.cookie_jar.clear()
        self.set_session_user("mod")
        with patch("admin_ops_api.ADMINS", ["mod"]):
            invalid = await self.client.post(
                "/api/admin/operations/logging-level", data={"level": "OFF"}
            )
            updated = await self.client.post(
                "/api/admin/operations/logging-level", data={"level": "INFO"}
            )
        self.assertEqual(invalid.status, 400)
        self.assertEqual(updated.status, 200)
        config = await app_state.db.config.find_one({"name": "logging.config"})
        self.assertEqual(config["value"]["handlers"]["default"]["level"], "INFO")
        self.assertEqual(config["value"]["handlers"]["default"]["formatter"], "standard")
        self.assertEqual(config["value"]["loggers"]["wsr"]["level"], "DEBUG")
        logs = await app_state.db.mod_log.find({"action": "logging_level_changed"}).to_list(None)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["mod"], "mod")
        self.assertEqual(logs[0]["details"], "INFO")

    async def test_anonymous_session_toggle_is_idempotent_and_audited(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")

        with patch("admin_ops_api.ADMINS", ["mod"]):
            disable = await self.client.post("/api/admin/operations/disable-anons")
            duplicate = await self.client.post("/api/admin/operations/disable-anons")
            enable = await self.client.post("/api/admin/operations/enable-anons")

        self.assertEqual(disable.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(enable.status, 200)
        self.assertFalse(app_state.disable_new_anons)
        logs = await app_state.db.mod_log.find({"user": "site"}).to_list(None)
        self.assertEqual(
            ["anonymous_sessions_disabled", "anonymous_sessions_enabled"],
            [entry["action"] for entry in logs],
        )

    async def test_stream_add_and_remove_broadcast_and_audit(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")

        with (
            patch("admin_ops_api.ADMINS", ["mod"]),
            patch("admin_ops_api.broadcast_streams", new=AsyncMock()) as broadcast,
        ):
            add = await self.client.post(
                "/api/admin/operations/stream-add",
                data={
                    "channel": "UCtestChannel123",
                    "username": "Streamer",
                    "title": "Variant night live",
                },
            )
            duplicate = await self.client.post(
                "/api/admin/operations/stream-add",
                data={"channel": "UCtestChannel123", "username": "Other", "title": "Other"},
            )
            remove = await self.client.post(
                "/api/admin/operations/stream-remove",
                data={"channel": "UCtestChannel123"},
            )

        self.assertEqual(add.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(remove.status, 200)
        self.assertNotIn("UCtestChannel123", app_state.youtube.streams)
        self.assertEqual(2, broadcast.await_count)
        logs = await app_state.db.mod_log.find({"user": "site"}).to_list(None)
        self.assertEqual(["stream_added", "stream_removed"], [entry["action"] for entry in logs])

    async def test_maintenance_actions_validate_targets_and_audit(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")
        await app_state.db.user.insert_one(
            {"_id": "MixedCase", "username_lower": "mixedcase", "enabled": True}
        )
        await app_state.db.puzzle.insert_one({"_id": "Ab123", "v": "chess"})

        with (
            patch("admin_ops_api.ADMINS", ["mod"]),
            patch("admin_ops_api.generate_highscore", new=AsyncMock()) as highscore,
            patch("admin_ops_api.generate_crosstable", new=AsyncMock()) as crosstable,
        ):
            highscore_response = await self.client.post(
                "/api/admin/operations/highscore", data={"variant": "chess"}
            )
            crosstable_response = await self.client.post(
                "/api/admin/operations/crosstable", data={"username": "mixedcase"}
            )
            puzzle_response = await self.client.post(
                "/api/admin/operations/puzzle-delete", data={"puzzle_id": "Ab123"}
            )
            missing_puzzle = await self.client.post(
                "/api/admin/operations/puzzle-delete", data={"puzzle_id": "Ab123"}
            )

        self.assertEqual(highscore_response.status, 200)
        self.assertEqual(crosstable_response.status, 200)
        self.assertEqual(puzzle_response.status, 200)
        self.assertEqual(missing_puzzle.status, 404)
        highscore.assert_awaited_once_with(app_state, "chess")
        crosstable.assert_awaited_once_with(app_state, "MixedCase")
        self.assertIsNone(await app_state.db.puzzle.find_one({"_id": "Ab123"}))
        logs = await app_state.db.mod_log.find({"user": "site"}).to_list(None)
        self.assertEqual(
            ["highscore_regenerated", "crosstable_regenerated", "puzzle_deleted"],
            [entry["action"] for entry in logs],
        )

    async def test_puzzle_delete_clears_daily_puzzle_references(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")
        await app_state.db.puzzle.insert_one({"_id": "Ab123", "v": "chess"})
        await app_state.db.puzzle.insert_one({"_id": "Cd456", "v": "chess"})
        today = datetime.now(UTC).date().isoformat()
        app_state.daily_puzzle_ids = {
            f"{today}:all": "Ab123",
            "2020-01-01:all": "Ab123",
            f"{today}:shogi": "Cd456",
        }
        await app_state.db.dailypuzzle.insert_many(
            [
                {"_id": f"{today}:all", "puzzleId": "Ab123"},
                {"_id": "2020-01-01:all", "puzzleId": "Ab123"},
                {"_id": f"{today}:shogi", "puzzleId": "Cd456"},
            ]
        )

        with patch("admin_ops_api.ADMINS", ["mod"]):
            response = await self.client.post(
                "/api/admin/operations/puzzle-delete", data={"puzzle_id": "Ab123"}
            )

        self.assertEqual(response.status, 200)
        self.assertNotIn("Ab123", app_state.daily_puzzle_ids.values())
        self.assertEqual(app_state.daily_puzzle_ids[f"{today}:shogi"], "Cd456")
        remaining = await app_state.db.dailypuzzle.find({"puzzleId": "Ab123"}).to_list(None)
        self.assertEqual(remaining, [])
        self.assertIsNotNone(await app_state.db.dailypuzzle.find_one({"_id": f"{today}:shogi"}))

    async def test_fishnet_key_is_revealed_once_then_revoked_by_public_id(self):
        app_state = get_app_state(self.app)
        self.add_live_user("mod")
        self.set_session_user("mod")

        with patch.dict(FISHNET_KEYS, {}, clear=True), patch("admin_ops_api.ADMINS", ["mod"]):
            create = await self.client.post(
                "/api/admin/operations/fishnet-create", data={"name": "worker-one"}
            )
            payload = await create.json()
            secret = payload["secret"]
            public_id = fishnet_key_id(secret)

            self.assertEqual(create.status, 200)
            self.assertEqual("worker-one", FISHNET_KEYS[secret])
            self.assertIsNotNone(await app_state.db.fishnet.find_one({"_id": secret}))

            app_state.workers.add(secret)
            app_state.fishnet_worker_last_seen[secret] = 1.0
            app_state.fishnet_versions["worker-one"] = "1.16.69"
            remove = await self.client.post(
                "/api/admin/operations/fishnet-remove", data={"key_id": public_id}
            )

            self.assertEqual(remove.status, 200)
            self.assertNotIn(secret, FISHNET_KEYS)

            FISHNET_KEYS["configured-key"] = "configured-worker"
            configured_remove = await self.client.post(
                "/api/admin/operations/fishnet-remove",
                data={"key_id": fishnet_key_id("configured-key")},
            )
            self.assertEqual(configured_remove.status, 409)
            self.assertIn("configured-key", FISHNET_KEYS)

        self.assertIsNone(await app_state.db.fishnet.find_one({"_id": secret}))
        self.assertNotIn(secret, app_state.workers)
        self.assertNotIn(secret, app_state.fishnet_worker_last_seen)
        self.assertNotIn("worker-one", app_state.fishnet_versions)
        logs = await app_state.db.mod_log.find({"user": "site"}).to_list(None)
        self.assertEqual(
            ["fishnet_key_created", "fishnet_key_removed"],
            [entry["action"] for entry in logs],
        )
        self.assertNotIn(secret, " ".join(str(entry.get("details", "")) for entry in logs))


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
