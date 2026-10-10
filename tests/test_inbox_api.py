import json
import time
from datetime import UTC, datetime
from unittest.mock import patch

from aiohttp.test_utils import AioHTTPTestCase
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class InboxApiTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        self.client.session.cookie_jar.clear()
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_send_and_read_inbox_message_flow(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice", patron=True)
        bob = User(app_state, username="bob", patron=True)
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(resp.status, 200)
        payload = await resp.json()
        self.assertTrue(payload.get("ok"))

        threads_resp = await self.client.get("/api/inbox/threads")
        self.assertEqual(threads_resp.status, 200)
        threads_payload = await threads_resp.json()
        self.assertEqual(1, len(threads_payload["threads"]))
        self.assertEqual("bob", threads_payload["threads"][0]["user"])
        self.assertTrue(threads_payload["threads"][0]["patron"])
        self.assertFalse(threads_payload["threads"][0]["unread"])

        self.set_session_user("bob")
        unread_before = await (await self.client.get("/api/inbox/unread")).json()
        self.assertEqual(1, unread_before["unread"])

        thread_resp = await self.client.get(
            "/api/inbox/thread/alice",
            headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"},
        )
        self.assertEqual(thread_resp.status, 200)
        thread_payload = await thread_resp.json()
        self.assertEqual("alice", thread_payload["contact"]["name"])
        self.assertTrue(thread_payload["contact"]["patron"])
        self.assertEqual(1, len(thread_payload["messages"]))
        self.assertEqual("hello bob", thread_payload["messages"][0]["text"])
        self.assertEqual("alice", thread_payload["messages"][0]["from"])

        unread_after_get = await (await self.client.get("/api/inbox/unread")).json()
        self.assertEqual(1, unread_after_get["unread"])

        rejected = await self.client.post(
            "/api/inbox/thread/alice/read", headers={"Origin": "https://attacker.test"}
        )
        self.assertEqual(403, rejected.status)
        unread_after_rejected_post = await (await self.client.get("/api/inbox/unread")).json()
        self.assertEqual(1, unread_after_rejected_post["unread"])

        origin = str(self.client.make_url("/")).rstrip("/")
        read_response = await self.client.post(
            "/api/inbox/thread/alice/read", headers={"Origin": origin}
        )
        self.assertEqual(200, read_response.status)
        self.assertTrue((await read_response.json())["ok"])

        unread_after = await (await self.client.get("/api/inbox/unread")).json()
        self.assertEqual(0, unread_after["unread"])

    async def test_sending_to_offline_recipient_does_not_cache_full_user(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        app_state.users[alice.username] = alice
        await app_state.db.user.insert_one({"_id": "bob", "title": ""})

        self.assertNotIn("bob", app_state.users.data)
        self.set_session_user("alice")
        response = await self.client.post(
            "/api/inbox/thread/bob", data={"text": "hello offline bob"}
        )

        self.assertEqual(response.status, 200)
        self.assertNotIn("bob", app_state.users.data)
        self.assertIsNotNone(await app_state.db.inbox_msg.find_one({"to": "bob"}))

    async def test_cannot_send_message_to_blocked_user(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        alice.blocked.add("bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post("/api/inbox/thread/bob", data={"text": "blocked"})
        self.assertEqual(resp.status, 403)
        payload = await resp.json()
        self.assertEqual("error", payload.get("type"))

    async def test_blocked_conversation_remains_readable_but_not_postable(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(resp.status, 200)

        alice.blocked.add("bob")

        thread_resp = await self.client.get("/api/inbox/thread/bob")
        self.assertEqual(thread_resp.status, 200)
        thread_payload = await thread_resp.json()
        self.assertEqual(1, len(thread_payload["messages"]))
        self.assertFalse(thread_payload["contact"]["canMessage"])
        self.assertTrue(thread_payload["contact"]["blockedByMe"])
        self.assertFalse(thread_payload["contact"]["blockedByThem"])

    async def test_delete_conversation_hides_only_for_deleting_user(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(resp.status, 200)

        delete_resp = await self.client.post("/api/inbox/thread/bob/delete")
        self.assertEqual(delete_resp.status, 200)
        delete_payload = await delete_resp.json()
        self.assertTrue(delete_payload.get("ok"))

        alice_threads = await (await self.client.get("/api/inbox/threads")).json()
        self.assertEqual([], alice_threads["threads"])

        alice_convo = await (await self.client.get("/api/inbox/thread/bob")).json()
        self.assertEqual([], alice_convo["messages"])

        self.set_session_user("bob")
        bob_threads = await (await self.client.get("/api/inbox/threads")).json()
        self.assertEqual(1, len(bob_threads["threads"]))
        self.assertEqual("alice", bob_threads["threads"][0]["user"])

        bob_convo = await (await self.client.get("/api/inbox/thread/alice")).json()
        self.assertEqual(1, len(bob_convo["messages"]))
        self.assertEqual("hello bob", bob_convo["messages"][0]["text"])

    async def test_thread_pagination_returns_latest_tail_and_loads_older_with_before(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob
        app_state.chat_flood.allow_message = lambda source, text: True

        with patch("inbox_api.THREAD_MSG_PAGE_SIZE", 5):
            self.set_session_user("alice")
            for idx in range(7):
                resp = await self.client.post("/api/inbox/thread/bob", data={"text": f"m{idx}"})
                self.assertEqual(resp.status, 200)

            self.set_session_user("bob")
            page1_resp = await self.client.get("/api/inbox/thread/alice")
            self.assertEqual(page1_resp.status, 200)
            page1 = await page1_resp.json()
            self.assertEqual(5, len(page1["messages"]))
            self.assertTrue(page1["hasMore"])

            oldest_page1 = page1["messages"][0]["createdAt"]
            oldest_dt = datetime.fromisoformat(oldest_page1)
            if oldest_dt.tzinfo is None:
                oldest_dt = oldest_dt.replace(tzinfo=UTC)
            before_ms = int(oldest_dt.timestamp() * 1000)

            page2_resp = await self.client.get(f"/api/inbox/thread/alice?before={before_ms}")
            self.assertEqual(page2_resp.status, 200)
            page2 = await page2_resp.json()
            self.assertEqual(2, len(page2["messages"]))
            self.assertFalse(page2["hasMore"])

    async def test_inbox_post_sanitizes_blacklisted_links(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post(
            "/api/inbox/thread/bob", data={"text": "visit https://tinyurl.com/abc"}
        )
        self.assertEqual(resp.status, 200)

        self.set_session_user("bob")
        thread_resp = await self.client.get("/api/inbox/thread/alice")
        self.assertEqual(thread_resp.status, 200)
        thread_payload = await thread_resp.json()
        self.assertEqual("visit [redacted]", thread_payload["messages"][0]["text"])

    async def test_inbox_post_rejects_repeated_similar_messages(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        first = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(first.status, 200)

        repeated = await self.client.post("/api/inbox/thread/bob", data={"text": "  Hello   bob  "})
        self.assertEqual(repeated.status, 429)
        repeated_payload = await repeated.json()
        self.assertEqual("error", repeated_payload.get("type"))

    async def test_shadowbanned_user_cannot_send_inbox_message(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice", shadowban=True)
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        resp = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(resp.status, 403)
        payload = await resp.json()
        self.assertEqual("error", payload.get("type"))

    async def test_follow_and_unfollow_endpoint_updates_relation_and_cache(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob")
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        follow_resp = await self.client.post("/api/bob/follow", data={"follow": "true"})
        self.assertEqual(follow_resp.status, 200)
        self.assertIn("bob", alice.following)

        relation_doc = await app_state.db.relation.find_one({"_id": "alice/bob"})
        self.assertIsNotNone(relation_doc)
        self.assertEqual(True, relation_doc.get("r"))

        unfollow_resp = await self.client.post("/api/bob/follow", data={"follow": "false"})
        self.assertEqual(unfollow_resp.status, 200)
        self.assertNotIn("bob", alice.following)

        relation_doc = await app_state.db.relation.find_one({"_id": "alice/bob"})
        self.assertIsNone(relation_doc)

    async def test_friends_only_pm_requires_follow_for_new_conversation(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob", pm_friends_only=True)
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("alice")
        blocked_resp = await self.client.post("/api/inbox/thread/bob", data={"text": "hello bob"})
        self.assertEqual(blocked_resp.status, 403)
        blocked_payload = await blocked_resp.json()
        self.assertEqual("Only friends can message this user", blocked_payload.get("message"))

        await self.client.post("/api/bob/follow", data={"follow": "true"})
        allowed_resp = await self.client.post(
            "/api/inbox/thread/bob", data={"text": "hello after follow"}
        )
        self.assertEqual(allowed_resp.status, 200)
        allowed_payload = await allowed_resp.json()
        self.assertTrue(allowed_payload.get("ok"))

    async def test_friends_only_pm_allows_reply_in_existing_conversation(self):
        app_state = get_app_state(self.app)
        alice = User(app_state, username="alice")
        bob = User(app_state, username="bob", pm_friends_only=True)
        app_state.users[alice.username] = alice
        app_state.users[bob.username] = bob

        self.set_session_user("bob")
        first = await self.client.post("/api/inbox/thread/alice", data={"text": "hello alice"})
        self.assertEqual(first.status, 200)

        self.set_session_user("alice")
        reply = await self.client.post(
            "/api/inbox/thread/bob", data={"text": "reply without follow"}
        )
        self.assertEqual(reply.status, 200)


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
