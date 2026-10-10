import json
import time
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from const import ARENA, RR, SWISS, T_ABORTED, T_ARCHIVED, T_FINISHED, T_STARTED
from mongomock_motor import AsyncMongoMockClient
from profile_counts import (
    HISTORY_PAGE_SIZE,
    calculate_counter,
    refresh_counter,
    refresh_tournament_points,
    refresh_user_counter,
)
from pychess_global_app_state_utils import get_app_state

from scripts.backfill_profile_counts import main as backfill_main
from server import make_app


class ProfileCountsTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def setUpAsync(self):
        await super().setUpAsync()
        self.state = get_app_state(self.app)
        self.db = self.state.db
        for username in ("alice", "bob"):
            await self.db.user.insert_one({"_id": username, "title": "FM", "perfs": {}})
        self.alice = await self.state.users.get("alice")
        self.client.session.cookie_jar.update_cookies(
            {
                "AIOHTTP_SESSION": json.dumps(
                    {"session": {"user_name": "alice"}, "created": int(time.time())}
                )
            },
            response_url=self.client.make_url("/"),
        )

    async def tearDownAsync(self):
        await self.client.close()

    async def add_result(
        self, tid, score, *, status=T_FINISHED, system=ARENA, variant="n", date=None
    ):
        await self.db.tournament.insert_one(
            {
                "_id": tid,
                "name": f"Event {tid}",
                "status": status,
                "system": system,
                "v": variant,
                "startsAt": date or datetime.now(UTC),
                "profilePointsPending": True,
            }
        )
        await self.db.tournament_player.insert_one({"tid": tid, "uid": "alice", "s": score})

    async def test_stored_points_use_display_scores_and_refresh_is_repeatable(self):
        await self.add_result("arena001", 8)
        await self.add_result("swiss001", 5, system=SWISS)
        await self.add_result("janggi01", 7, system=RR, variant="j")
        await self.add_result("archive1", 4, status=T_ARCHIVED, system=RR)
        await self.add_result("aborted1", 100, status=T_ABORTED)
        await self.add_result("started1", 100, status=T_STARTED)
        await self.db.tournament_player.insert_one({"tid": "missing1", "uid": "alice", "s": 100})
        await self.db.tournament_player.insert_one({"tid": "arena001", "uid": "bob", "s": 100})
        for _ in range(2):
            await refresh_tournament_points(self.state, "arena001")
        self.assertEqual(19.5, self.alice.tournament_points)
        self.assertEqual(19.5, (await self.db.user.find_one({"_id": "alice"}))["tournamentPoints"])
        self.assertNotIn(
            "profilePointsPending", await self.db.tournament.find_one({"_id": "arena001"})
        )
        offline = self.state.public_users._profile_from_doc(
            "alice", await self.db.user.find_one({"_id": "alice"}), frozenset()
        )
        self.assertEqual(19.5, offline.tournament_points)

    async def test_profile_reads_stored_counters_without_count_queries(self):
        await self.db.user.update_one(
            {"_id": "alice"},
            {"$set": {"forumPosts": 12, "tournamentPoints": 17.5, "variantCount": 3}},
        )
        self.alice.forum_posts = 12
        self.alice.tournament_points = 17.5
        self.alice.variant_count = 3
        self.client.session.cookie_jar.clear()
        with (
            patch.object(
                self.db.forum_post,
                "count_documents",
                side_effect=AssertionError("profile counted posts"),
            ),
            patch.object(
                self.db.tournament_player,
                "aggregate",
                side_effect=AssertionError("profile aggregated points"),
            ),
            patch.object(
                self.db.catalogued_variant,
                "count_documents",
                side_effect=AssertionError("profile counted variants"),
            ),
        ):
            response = await self.client.get("/@/alice")
            self.assertEqual(200, response.status)
            html = await response.text()
        self.assertIn("<strong>12</strong> Forum posts</a>", html)
        self.assertIn("<strong>17.5</strong> Tournament points</a>", html)
        self.assertIn("<strong>3</strong> Variants</a>", html)
        self.assertIn("/forum/search?text=user%3Aalice", html)
        self.assertIn("/variants/community?author=alice", html)

    async def test_forum_post_creation_erasure_and_thread_deletion_refresh_counts(self):
        with patch("forum.mutations.forum_captcha_is_valid", return_value=True):
            response = await self.client.post(
                "/api/forum/general-chess-discussion/topic",
                data={"name": "Counter discussion", "text": "Opening message"},
            )
            topic = (await response.json())["topic"]
            response = await self.client.post(
                f"/api/forum/general-chess-discussion/{topic['slug']}/post",
                data={"text": "A second message"},
            )
            post = (await response.json())["post"]
        self.assertEqual(2, self.alice.forum_posts)
        response = await self.client.get("/api/forum/search?text=user:alice")
        self.assertEqual(2, (await response.json())["total"])
        response = await self.client.post(f"/api/forum/post/{post['_id']}/delete")
        self.assertEqual(200, response.status)
        self.assertTrue((await response.json())["erased"])
        self.assertEqual(1, self.alice.forum_posts)
        first = await self.db.forum_post.find_one({"topicId": topic["_id"], "user": "alice"})
        await self.db.forum_post.insert_one(
            {
                "_id": "bobpost",
                "topicId": topic["_id"],
                "categId": "general-chess-discussion",
                "user": "bob",
                "text": "Bob's reply",
                "createdAt": datetime.now(UTC),
            }
        )
        await refresh_user_counter(self.state, "bob", "forumPosts")
        with patch("forum.mutations.can_moderate_forum_categ", new=AsyncMock(return_value=True)):
            self.client.session.cookie_jar.update_cookies(
                {
                    "AIOHTTP_SESSION": json.dumps(
                        {"session": {"user_name": "bob"}, "created": int(time.time())}
                    )
                },
                response_url=self.client.make_url("/"),
            )
            response = await self.client.post(f"/api/forum/post/{first['_id']}/delete")
            self.assertEqual(200, response.status)
            self.assertTrue((await response.json())["deletedTopic"])
        self.assertEqual(0, (await self.db.user.find_one({"_id": "alice"}))["forumPosts"])
        self.assertEqual(0, (await self.db.user.find_one({"_id": "bob"}))["forumPosts"])

    async def test_forum_search_and_counter_exclude_team_and_erased_posts(self):
        await self.db.forum_post.insert_many(
            [
                {
                    "_id": "visible",
                    "user": "alice",
                    "categId": "general-chess-discussion",
                    "text": "Visible",
                },
                {"_id": "private", "user": "alice", "categId": "team-secret", "text": "Private"},
                {
                    "_id": "erased",
                    "user": "alice",
                    "categId": "general-chess-discussion",
                    "text": "Erased",
                    "erasedAt": datetime.now(UTC),
                },
                {
                    "_id": "other",
                    "user": "bob",
                    "categId": "general-chess-discussion",
                    "text": "Mentions alice",
                },
            ]
        )
        await refresh_user_counter(self.state, "alice", "forumPosts")
        self.assertEqual(1, self.alice.forum_posts)
        response = await self.client.get("/api/forum/search?text=user:alice")
        data = await response.json()
        self.assertEqual(1, data["total"])
        self.assertEqual("Visible", data["posts"][0]["post"]["text"])
        response = await self.client.get("/api/forum/search?text=user:alice+missing")
        self.assertEqual(0, (await response.json())["total"])

    async def test_concurrent_refresh_retries_instead_of_overwriting_newer_count(self):
        calls = 0

        async def racing_count(db, username, counter):
            nonlocal calls
            calls += 1
            result = await calculate_counter(db, username, counter)
            if calls == 1:
                await db.forum_post.insert_one(
                    {"user": "alice", "categId": "general", "text": "New"}
                )
                await refresh_counter(db, username, counter)
            return result

        with patch("profile_counts.calculate_counter", side_effect=racing_count):
            await refresh_user_counter(self.state, "alice", "forumPosts")
        self.assertEqual(3, calls)
        self.assertEqual(1, self.alice.forum_posts)

    async def test_history_paginates_and_handles_empty_unknown_profiles(self):
        for index in range(HISTORY_PAGE_SIZE + 1):
            await self.add_result(
                f"hist{index:04}",
                3,
                system=SWISS,
                date=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index),
            )
        response = await self.client.get("/@/alice/tournaments")
        self.assertEqual(200, response.status)
        html = await response.text()
        self.assertIn("Event hist0025", html)
        self.assertNotIn("Event hist0000", html)
        self.assertIn("/tournaments?page=2", html)
        self.assertIn("<td>1.5</td>", html)
        response = await self.client.get("/@/alice/tournaments?page=2")
        html = await response.text()
        self.assertIn("Event hist0000", html)
        self.assertNotIn("Event hist0025", html)
        response = await self.client.get("/@/bob/tournaments?page=bad")
        self.assertIn("No tournaments yet.", await response.text())
        response = await self.client.get("/@/missing/tournaments")
        self.assertEqual(404, response.status)

    async def test_backfill_dry_run_and_apply_only_selected_user(self):
        await self.add_result("backfill", 5)
        await self.db.forum_post.insert_one(
            {"user": "alice", "categId": "general", "text": "Hello"}
        )
        await self.db.catalogued_variant.insert_many(
            [
                {
                    "_id": "alice-public",
                    "author": "alice",
                    "visibility": "public",
                    "enabled": True,
                    "archived": False,
                },
                {
                    "_id": "alice-private",
                    "author": "alice",
                    "visibility": "private",
                    "enabled": True,
                    "archived": False,
                },
                {
                    "_id": "alice-unlisted",
                    "author": "alice",
                    "visibility": "unlisted",
                    "enabled": True,
                    "archived": False,
                },
                {
                    "_id": "alice-disabled",
                    "author": "alice",
                    "visibility": "public",
                    "enabled": False,
                    "archived": False,
                },
                {
                    "_id": "alice-archived",
                    "author": "alice",
                    "visibility": "public",
                    "enabled": True,
                    "archived": True,
                },
                {
                    "_id": "bob-public",
                    "author": "bob",
                    "visibility": "public",
                    "enabled": True,
                    "archived": False,
                },
            ]
        )
        client = MagicMock()
        client.__getitem__.return_value = self.db
        client.close = AsyncMock()
        with patch("scripts.backfill_profile_counts.AsyncMongoClient", return_value=client):
            with (
                patch("sys.argv", ["backfill_profile_counts.py", "--user", "alice"]),
                redirect_stdout(StringIO()),
            ):
                await backfill_main()
            self.assertNotIn("forumPosts", await self.db.user.find_one({"_id": "alice"}))
            for _ in range(2):
                with (
                    patch("sys.argv", ["backfill_profile_counts.py", "--user", "alice", "--apply"]),
                    redirect_stdout(StringIO()),
                ):
                    await backfill_main()
            user = await self.db.user.find_one({"_id": "alice"})
            self.assertEqual(1, user["forumPosts"])
            self.assertEqual(5, user["tournamentPoints"])
            self.assertEqual(1, user["variantCount"])
            self.assertNotIn("forumPosts", await self.db.user.find_one({"_id": "bob"}))
            self.assertNotIn("variantCount", await self.db.user.find_one({"_id": "bob"}))
