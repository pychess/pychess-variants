import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from catalogued.variants import (
    CATALOGUED_FSF_BUILTIN_AUTHOR,
    MAX_CATALOGUED_VARIANTS_PER_USER,
    _management_sort_spec,
    _positive_management_page,
    get_my_catalogued_variants,
)
from yarl import URL


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.skip_count = 0
        self.limit_count = len(self.docs)
        self.sort_spec = []

    def sort(self, spec):
        self.sort_spec = list(spec)
        for field, direction in reversed(self.sort_spec):
            self.docs.sort(key=lambda doc: doc.get(field), reverse=direction < 0)
        return self

    def skip(self, count):
        self.skip_count = count
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def __aiter__(self):
        selected = self.docs[self.skip_count : self.skip_count + self.limit_count]

        async def iterate():
            for doc in selected:
                yield doc

        return iterate()


class FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.count_queries = []
        self.find_queries = []
        self.cursor = None

    @classmethod
    def _matches(cls, doc, query):
        for field, value in query.items():
            if field == "$or":
                if not any(cls._matches(doc, item) for item in value):
                    return False
            elif isinstance(value, dict) and "$regex" in value:
                if value["$regex"].search(str(doc.get(field) or "")) is None:
                    return False
            elif isinstance(value, dict) and "$ne" in value:
                if doc.get(field) == value["$ne"]:
                    return False
            elif doc.get(field) != value:
                return False
        return True

    async def count_documents(self, query):
        self.count_queries.append(query)
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def find(self, query):
        self.find_queries.append(query)
        self.cursor = FakeCursor(doc for doc in self.docs if self._matches(doc, query))
        return self.cursor


class FakeDatabase:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, _name):
        return self.collection


class CataloguedVariantManagementPaginationTestCase(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_docs(count, *, author="owner", prefix="variant"):
        return [
            {
                "name": f"{prefix}{i:02d}",
                "displayName": f"Variant {i:02d}",
                "description": f"Description {i:02d}",
                "author": author,
                "source": "user",
                "gameCount": i % 7,
                "favoriteCount": i % 5,
                "createdAt": i,
                "updatedAt": i,
            }
            for i in range(count)
        ]

    async def call_handler(self, url, docs, *, username="admin", admin=True):
        collection = FakeCollection(docs)
        app_state = SimpleNamespace(db=FakeDatabase(collection))
        request = SimpleNamespace(app=object(), rel_url=URL(url))

        with (
            patch("catalogued.variants.get_app_state", return_value=app_state),
            patch(
                "catalogued.variants._current_human_username",
                new=AsyncMock(return_value=username),
            ),
            patch("catalogued.variants._is_admin_username", return_value=admin),
            patch("catalogued.variants._game_count", new=AsyncMock(return_value=7)),
            patch(
                "catalogued.variants._client_doc",
                side_effect=lambda doc, game_count: {
                    "name": doc["name"],
                    "gameCount": game_count,
                },
            ),
        ):
            response = await get_my_catalogued_variants(request)

        return json.loads(response.text), collection

    def test_positive_page_normalizes_invalid_values(self):
        self.assertEqual(_positive_management_page(None), 1)
        self.assertEqual(_positive_management_page("invalid"), 1)
        self.assertEqual(_positive_management_page("-5"), 1)
        self.assertEqual(_positive_management_page("3"), 3)

    def test_management_sort_options_match_community_sorting(self):
        self.assertEqual(
            _management_sort_spec("played"),
            ("played", [("gameCount", -1), ("updatedAt", -1), ("name", 1)]),
        )
        self.assertEqual(
            _management_sort_spec("favorited"),
            ("favorited", [("favoriteCount", -1), ("updatedAt", -1), ("name", 1)]),
        )
        self.assertEqual(
            _management_sort_spec("invalid"),
            ("updated", [("updatedAt", -1), ("name", 1)]),
        )

    async def test_admin_defaults_to_own_username(self):
        docs = [
            *self.make_docs(3, author="admin", prefix="mine"),
            *self.make_docs(4, author="other", prefix="other"),
        ]
        payload, collection = await self.call_handler("/api/catalogued-variants/mine", docs)

        expected_query = {"author": "admin"}
        self.assertEqual(collection.count_queries, [expected_query])
        self.assertEqual(collection.find_queries, [expected_query])
        self.assertEqual(payload["author"], "admin")
        self.assertEqual(payload["total"], 3)
        self.assertIsNone(payload["maxVariants"])

    async def test_cleared_author_returns_all_variants_on_requested_page(self):
        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine?author=&page=2",
            self.make_docs(45),
        )

        self.assertEqual(payload["author"], "")
        self.assertEqual(payload["total"], 45)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["pages"], 3)
        self.assertEqual(payload["prevPage"], 1)
        self.assertEqual(payload["nextPage"], 3)
        self.assertEqual(
            [variant["name"] for variant in payload["variants"]],
            [f"variant{i:02d}" for i in range(24, 4, -1)],
        )
        self.assertEqual(collection.count_queries, [{}])
        self.assertEqual(collection.find_queries, [{}])
        self.assertEqual(collection.cursor.sort_spec, [("updatedAt", -1), ("name", 1)])
        self.assertEqual(collection.cursor.skip_count, 20)
        self.assertEqual(collection.cursor.limit_count, 20)

    async def test_page_beyond_end_is_clamped_to_last_page(self):
        payload, _collection = await self.call_handler(
            "/api/catalogued-variants/mine?author=&page=99",
            self.make_docs(45),
        )

        self.assertEqual(payload["page"], 3)
        self.assertEqual(payload["prevPage"], 2)
        self.assertIsNone(payload["nextPage"])
        self.assertEqual(
            [variant["name"] for variant in payload["variants"]],
            [f"variant{i:02d}" for i in range(4, -1, -1)],
        )

    async def test_fairy_stockfish_author_filter_is_applied_before_pagination(self):
        fsf_docs = self.make_docs(21, author=CATALOGUED_FSF_BUILTIN_AUTHOR, prefix="fsf")
        payload, collection = await self.call_handler(
            f"/api/catalogued-variants/mine?author={CATALOGUED_FSF_BUILTIN_AUTHOR}&page=2",
            [*self.make_docs(10), *fsf_docs],
        )

        expected_query = {"author": CATALOGUED_FSF_BUILTIN_AUTHOR}
        self.assertEqual(collection.count_queries, [expected_query])
        self.assertEqual(collection.find_queries, [expected_query])
        self.assertEqual(payload["total"], 21)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["pages"], 2)
        self.assertEqual(len(payload["variants"]), 1)

    async def test_search_and_author_filters_are_combined(self):
        docs = [
            {
                **self.make_docs(1, author="alice", prefix="makruk")[0],
                "description": "Royal Thai chess",
            },
            {
                **self.make_docs(1, author="bob", prefix="makruk")[0],
                "description": "Royal Thai chess",
            },
            *self.make_docs(1, author="alice", prefix="shogi"),
        ]
        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine?author=alice&q=THAI",
            docs,
        )

        query = collection.count_queries[0]
        self.assertEqual(query["author"], "alice")
        self.assertEqual(query["$or"][0]["name"]["$regex"].pattern, "THAI")
        self.assertEqual(payload["q"], "THAI")
        self.assertEqual(payload["total"], 1)
        self.assertEqual([item["name"] for item in payload["variants"]], ["makruk00"])

    async def test_played_sort_matches_community_page_order(self):
        docs = self.make_docs(3, author="admin")
        docs[0]["gameCount"] = 20
        docs[0]["updatedAt"] = 1
        docs[1]["gameCount"] = 20
        docs[1]["updatedAt"] = 3
        docs[2]["gameCount"] = 5
        docs[2]["updatedAt"] = 9

        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine?sort=played",
            docs,
        )

        self.assertEqual(payload["sort"], "played")
        self.assertEqual(
            collection.cursor.sort_spec,
            [("gameCount", -1), ("updatedAt", -1), ("name", 1)],
        )
        self.assertEqual(
            [item["name"] for item in payload["variants"]],
            ["variant01", "variant00", "variant02"],
        )

    async def test_favorited_sort_matches_global_favorite_count_order(self):
        docs = self.make_docs(3, author="admin")
        docs[0]["favoriteCount"] = 12
        docs[0]["updatedAt"] = 1
        docs[1]["favoriteCount"] = 12
        docs[1]["updatedAt"] = 3
        docs[2]["favoriteCount"] = 4
        docs[2]["updatedAt"] = 9

        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine?sort=favorited",
            docs,
        )

        self.assertEqual(payload["sort"], "favorited")
        self.assertEqual(
            collection.cursor.sort_spec,
            [("favoriteCount", -1), ("updatedAt", -1), ("name", 1)],
        )
        self.assertEqual(
            [item["name"] for item in payload["variants"]],
            ["variant01", "variant00", "variant02"],
        )

    async def test_non_admin_filters_are_ignored_and_total_drives_quota_counter(self):
        docs = [
            *self.make_docs(3, author="alice", prefix="mine"),
            *self.make_docs(4, author="other", prefix="other"),
        ]
        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine?author=&q=other&sort=played",
            docs,
            username="alice",
            admin=False,
        )

        expected_query = {"author": "alice"}
        active_query = {"author": "alice", "archived": {"$ne": True}}
        self.assertEqual(collection.count_queries, [expected_query, active_query])
        self.assertEqual(collection.find_queries, [expected_query])
        self.assertEqual(payload["q"], "")
        self.assertEqual(payload["author"], "alice")
        self.assertEqual(payload["sort"], "updated")
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["maxVariants"], MAX_CATALOGUED_VARIANTS_PER_USER)
        self.assertEqual(payload["variantSlotsUsed"], 3)
        self.assertEqual(len(payload["variants"]), 3)

    async def test_archived_variants_remain_listed_but_do_not_use_quota_slots(self):
        docs = self.make_docs(3, author="alice", prefix="mine")
        docs[1]["archived"] = True
        docs[1]["enabled"] = False

        payload, collection = await self.call_handler(
            "/api/catalogued-variants/mine",
            docs,
            username="alice",
            admin=False,
        )

        expected_query = {"author": "alice"}
        active_query = {"author": "alice", "archived": {"$ne": True}}
        self.assertEqual(collection.count_queries, [expected_query, active_query])
        self.assertEqual(collection.find_queries, [expected_query])
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["variantSlotsUsed"], 2)
        self.assertEqual(len(payload["variants"]), 3)
