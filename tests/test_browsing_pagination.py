from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from aiohttp.test_utils import AioHTTPTestCase
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from videos import VIDEO_CATEGORIES

from server import make_app


class Listing(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.keys: list[str] = []
        self.next_href: str | None = None
        self.hrefs: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if key := attrs.get("data-infinite-scroll-key"):
            self.keys.append(key)
        if tag == "a" and (href := attrs.get("href")):
            self.hrefs.append(href)
            if attrs.get("rel") == "next":
                self.next_href = href


class BrowsingPaginationTest(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def setUpAsync(self):
        await super().setUpAsync()
        self.state = get_app_state(self.app)
        await self.state.db.user.insert_one({"_id": "alice", "enabled": True, "title": "FM"})
        self.state.users["alice"] = User(self.state, username="alice", title="FM")
        self.session_user("alice")

    def session_user(self, username: str):
        self.client.session.cookie_jar.clear()
        self.client.session.cookie_jar.update_cookies(
            {
                "AIOHTTP_SESSION": json.dumps(
                    {"session": {"user_name": username}, "created": int(time.time())}
                )
            },
            response_url=self.client.make_url("/"),
        )

    async def listing(self, href: str) -> tuple[Listing, str]:
        response = await self.client.get(href)
        self.assertEqual(response.status, 200)
        html = await response.text()
        return Listing(html), html

    async def blog(self, key: str, **overrides):
        await self.state.db.ublog_post2.insert_one(
            {
                "_id": key,
                "author": "alice",
                "title": key,
                "slug": key,
                "blogType": "site",
                "live": True,
                "sticky": False,
                "publishedAt": datetime(2026, 1, 1, tzinfo=UTC),
                "topics": ["announcement"],
                "category": "all",
                **overrides,
            }
        )

    async def video(self, key: str, **overrides):
        await self.state.db.video.insert_one(
            {
                "_id": key,
                "title": key,
                "author": "alice",
                "duration": "1:00",
                "target": "beginner",
                "tags": ["Introduction"],
                "category": "all",
                **overrides,
            }
        )

    async def test_blog_pages_filter_before_limit_and_keep_tags_from_later_pages(self):
        await self.state.db.user.insert_one({"_id": "closed", "enabled": False})
        await self.blog("zzzclosed", author="closed", sticky=True)
        await self.blog("zzzmissing", author="missing", sticky=True)
        await self.blog("zzzdraft", live=False, sticky=True)
        await self.blog("zzzcommunity", blogType="community", sticky=True)
        for key in ["blog01", "blog02", "blog03", "blog04", "blog05"]:
            await self.blog(key)
        await self.blog("blog00", topics=["announcement", "engine"])
        with patch("views.blogs.BLOG_PAGE_SIZE", 2):
            first, html = await self.listing("/blogs?tags=ANNOUNCEMENT")
            self.assertEqual(first.keys, ["blog05", "blog04"])
            self.assertIn("FM", html)
            self.assertTrue(any("tags=engine" in href for href in first.hrefs))
            self.assertEqual(
                parse_qs(urlsplit(first.next_href).query), {"tags": ["ANNOUNCEMENT"], "page": ["2"]}
            )
            seen = first.keys[:]
            href = first.next_href
            while href:
                page, _ = await self.listing(href)
                seen.extend(page.keys)
                href = page.next_href
            self.assertEqual(seen, [f"blog{i:02}" for i in reversed(range(6))])
            self.assertEqual(len(seen), len(set(seen)))

    async def test_blog_category_and_literal_tag_filters_are_applied_before_paging(self):
        self.state.users["alice"].game_category = "shogi"
        await self.blog("zzzother", category="fairy")
        await self.blog("zzzwrongtag", topics=["engine"])
        await self.blog("specific", category=["shogi", "fairy"], topics=["A+B"])
        await self.blog("general", topics=["A+B"])
        await self.blog("legacy", tags=["A+B"], topics=None)
        with patch("views.blogs.BLOG_PAGE_SIZE", 2):
            first, _ = await self.listing("/blogs?tags=a%2Bb")
            self.assertEqual(first.keys, ["specific", "legacy"])
            final, _ = await self.listing(first.next_href)
            self.assertEqual(final.keys, ["general"])
            self.assertIsNone(final.next_href)

    async def test_video_pages_keep_tag_filter_and_use_stable_order(self):
        for i in reversed(range(5)):
            await self.video(f"video{i}")
        await self.video("other", tags=["Opening"])
        with patch("views.videos.VIDEO_PAGE_SIZE", 2):
            seen = []
            href = "/video?tags=Introduction"
            while href:
                page, _ = await self.listing(href)
                seen.extend(page.keys)
                href = page.next_href
                if href:
                    self.assertEqual(parse_qs(urlsplit(href).query)["tags"], ["Introduction"])
            self.assertEqual(seen, [f"video{i}" for i in range(5)])

    async def test_video_category_filter_preserves_legacy_fallbacks_and_complete_tag_menu(self):
        self.state.users["alice"].game_category = "shogi"
        for i in range(3):
            await self.video(f"a{i}", category="fairy")
        await self.video("b0", category=["shogi", "fairy"])
        await self.video("b1", category=None)
        await self.video("b2", tags=["Opening"])
        await self.state.db.video.insert_one(
            {
                "_id": "legacy-match",
                "title": "legacy",
                "target": "beginner",
                "tags": ["Opening"],
            }
        )
        await self.state.db.video.insert_one(
            {
                "_id": "legacy-other",
                "title": "legacy",
                "target": "beginner",
                "tags": ["Opening"],
            }
        )
        with (
            patch.dict(VIDEO_CATEGORIES, {"legacy-match": "shogi", "legacy-other": "fairy"}),
            patch("views.videos.VIDEO_PAGE_SIZE", 2),
        ):
            first, _ = await self.listing("/video")
            self.assertEqual(first.keys, ["b0", "b1"])
            self.assertTrue(any("tags=Opening" in href for href in first.hrefs))
            final, _ = await self.listing(first.next_href)
            self.assertEqual(final.keys, ["b2", "legacy-match"])
            self.assertIsNone(final.next_href)

    async def test_pending_requests_are_bounded_to_managed_teams_and_actions_still_work(self):
        created = await self.client.post(
            "/team/new",
            data={
                "name": "Variant Fans",
                "intro": "Play variants together",
                "description": "A friendly team for people who enjoy chess variants together.",
                "requestRequired": "1",
            },
            allow_redirects=False,
        )
        self.assertEqual(created.status, 302, await created.text())
        for i in range(5):
            username = f"queued{i}"
            self.state.users[username] = User(self.state, username=username)
            await self.state.db.team_request.insert_one(
                {
                    "_id": f"{username}@variant-fans",
                    "team": "variant-fans",
                    "user": username,
                    "declined": False,
                    "message": "Let me join",
                    "createdAt": datetime(2026, 1, 1, tzinfo=UTC),
                }
            )
        await self.state.db.team_request.insert_one(
            {"_id": "foreign", "team": "not-managed", "user": "outsider", "declined": False}
        )
        await self.state.db.team_request.insert_one(
            {"_id": "declined", "team": "variant-fans", "user": "declined", "declined": True}
        )
        with patch("views.team.TEAM_REQUESTS_PAGE_SIZE", 2):
            first, html = await self.listing("/team/requests")
            self.assertEqual(first.keys, ["queued0@variant-fans", "queued1@variant-fans"])
            self.assertIn("5 join requests", html)
            second, _ = await self.listing(first.next_href)
            self.assertEqual(second.keys, ["queued2@variant-fans", "queued3@variant-fans"])
            final, _ = await self.listing(second.next_href)
            self.assertEqual(final.keys, ["queued4@variant-fans"])
            self.assertIsNone(final.next_href)
            accepted = await self.client.post(
                "/team/variant-fans/request/queued4/accept",
                data={"redirect": "/team/requests"},
                allow_redirects=False,
            )
            self.assertEqual(accepted.status, 302)
            self.assertEqual(accepted.headers["Location"], "/team/requests")
            self.assertIsNotNone(
                await self.state.db.team_member.find_one({"_id": "queued4@variant-fans"})
            )
            clamped, _ = await self.listing("/team/requests?page=3")
            self.assertEqual(clamped.keys, second.keys)

    async def test_invalid_page_values_and_empty_lists(self):
        for path in ["/blogs", "/video", "/team/requests"]:
            for value in ["0", "-1", "invalid"]:
                with self.subTest(path=path, page=value):
                    page, _ = await self.listing(f"{path}?page={value}")
                    self.assertEqual(page.keys, [])
                    self.assertIsNone(page.next_href)
