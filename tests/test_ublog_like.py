import json
import time

from aiohttp.test_utils import AioHTTPTestCase
from const import FOLLOW
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class UblogEngagementTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.clear()
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def add_user(self, username: str, *, enabled: bool = True) -> None:
        app_state = get_app_state(self.app)
        app_state.users[username] = User(app_state, username=username, enabled=enabled)
        await app_state.db.user.insert_one(
            {
                "_id": username,
                "username_lower": username.casefold(),
                "enabled": enabled,
            }
        )

    async def add_post(
        self,
        likes: list[str] | None = None,
        views: int = 0,
        *,
        post_id: str = "post0001",
        author: str = "author",
        title: str = "Post",
    ) -> None:
        app_state = get_app_state(self.app)
        if await app_state.db.user.find_one({"_id": author}) is None:
            await self.add_user(author)
        await app_state.db.ublog_post2.insert_one(
            {
                "_id": post_id,
                "author": author,
                "title": title,
                "slug": "post",
                "intro": "Intro",
                "markdown": "Body",
                "language": "en",
                "live": True,
                "views": views,
                "likes": likes or [],
            }
        )

    async def like(self):
        return await self.client.post(
            "/blogs/@/author/post0001/like",
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    async def view(self):
        return await self.client.get("/blogs/@/author/post/post0001")

    async def test_one_user_cannot_add_more_than_one_like(self):
        await self.add_user("alice")
        await self.add_post()
        self.set_session_user("alice")

        first = await self.like()
        self.assertEqual(first.status, 200)
        self.assertEqual(await first.json(), {"ok": True, "liked": True, "likes": 1})

        second = await self.like()
        self.assertEqual(second.status, 200)
        self.assertEqual(await second.json(), {"ok": True, "liked": False, "likes": 0})

        third = await self.like()
        self.assertEqual(third.status, 200)
        self.assertEqual(await third.json(), {"ok": True, "liked": True, "likes": 1})

        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["likes"], ["alice"])

    async def test_new_like_is_published_to_followers_but_unlike_is_not(self):
        app_state = get_app_state(self.app)
        await self.add_user("alice")
        await self.add_user("bob")
        await self.add_post(title="Timeline post")
        await app_state.db.relation.insert_one(
            {"_id": "bob/alice", "u1": "bob", "u2": "alice", "r": FOLLOW}
        )
        self.set_session_user("alice")

        like_response = await self.like()
        self.assertEqual(like_response.status, 200)
        entries = await app_state.timeline.entries_for("bob")
        self.assertEqual(1, len(entries))
        self.assertEqual("ublog-post-like", entries[0]["type"])
        self.assertEqual(
            {
                "actor": "alice",
                "profile": "author",
                "slug": "post",
                "postId": "post0001",
                "title": "Timeline post",
            },
            entries[0]["data"],
        )

        unlike_response = await self.like()
        self.assertEqual(unlike_response.status, 200)
        self.assertEqual(1, len(await app_state.timeline.entries_for("bob")))

    async def test_anonymous_user_cannot_like(self):
        await self.add_post()

        response = await self.like()

        self.assertEqual(response.status, 403)
        self.assertEqual(await response.json(), {"ok": False, "error": "forbidden"})
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["likes"], [])

    async def test_legacy_duplicate_usernames_count_as_one_like(self):
        await self.add_user("alice")
        await self.add_post(["alice", "alice"])
        self.set_session_user("alice")

        response = await self.like()
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"ok": True, "liked": False, "likes": 0})

        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["likes"], [])

    async def test_likes_are_counted_per_user(self):
        await self.add_user("alice")
        await self.add_user("bob")
        await self.add_post()

        self.set_session_user("alice")
        alice_response = await self.like()
        self.assertEqual((await alice_response.json())["likes"], 1)

        self.set_session_user("bob")
        bob_response = await self.like()
        self.assertEqual((await bob_response.json())["likes"], 2)

        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(set(post["likes"]), {"alice", "bob"})

    async def test_anonymous_views_are_not_counted(self):
        await self.add_user("author")
        await self.add_post()

        response = await self.view()

        self.assertEqual(response.status, 200)
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["views"], 0)
        self.assertNotIn("viewers", post)

    async def test_authenticated_view_is_counted_only_once(self):
        await self.add_user("author")
        await self.add_user("alice")
        await self.add_post()
        self.set_session_user("alice")

        first = await self.view()
        second = await self.view()

        self.assertEqual(first.status, 200)
        self.assertEqual(second.status, 200)
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["views"], 1)
        self.assertEqual(post["viewers"], ["alice"])

    async def test_views_are_counted_per_authenticated_user(self):
        await self.add_user("author")
        await self.add_user("alice")
        await self.add_user("bob")
        await self.add_post()

        self.set_session_user("alice")
        alice_response = await self.view()
        self.set_session_user("bob")
        bob_response = await self.view()

        self.assertEqual(alice_response.status, 200)
        self.assertEqual(bob_response.status, 200)
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["views"], 2)
        self.assertEqual(set(post["viewers"]), {"alice", "bob"})

    async def test_disabled_author_post_returns_404(self):
        await self.add_user("author", enabled=False)
        await self.add_post()

        response = await self.view()

        self.assertEqual(response.status, 404)
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["views"], 0)
        self.assertNotIn("viewers", post)

    async def test_disabled_author_post_cannot_be_liked(self):
        await self.add_user("author", enabled=False)
        await self.add_user("alice")
        await self.add_post()
        self.set_session_user("alice")

        response = await self.like()

        self.assertEqual(response.status, 404)
        self.assertEqual(await response.json(), {"ok": False, "error": "not_found"})
        app_state = get_app_state(self.app)
        post = await app_state.db.ublog_post2.find_one({"_id": "post0001"})
        self.assertEqual(post["likes"], [])

    async def test_disabled_author_posts_are_hidden_from_community_list(self):
        await self.add_user("disabled-author", enabled=False)
        await self.add_user("enabled-author")
        await self.add_post(
            post_id="hidden01",
            author="disabled-author",
            title="Hidden post",
        )
        await self.add_post(
            post_id="visible1",
            author="enabled-author",
            title="Visible post",
        )

        response = await self.client.get("/blogs/community")
        body = await response.text()

        self.assertEqual(response.status, 200)
        self.assertNotIn("Hidden post", body)
        self.assertIn("Visible post", body)
