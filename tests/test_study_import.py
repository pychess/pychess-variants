from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from aiohttp import web
from fairy import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from study.storage import create_study_with_chapter
from views.study import study_import_pgn


class StudyImportTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncMongoMockClient(tz_aware=True)
        self.db = self.client["pychess-test"]
        self.app_state = SimpleNamespace(
            db=self.db,
            catalogued_variants={},
            study_sockets={},
            study_mutation_locks={},
            study_mutation_lock_refs={},
        )
        self.study, self.initial_chapter = await create_study_with_chapter(
            cast(Any, self.app_state), "owner", name="Import target"
        )

    @staticmethod
    def _node(
        node_id: str,
        move: str,
        *,
        parent_id: str | None = None,
        order: int = 0,
        variant: str = "chess",
        initial_fen: str | None = None,
    ):
        # Bulk import trusts the browser-normalized chess data. Mirror the client
        # importer here instead of relying on the server to replay and repair it.
        board = FairyBoard(variant, initial_fen=initial_fen)
        san = board.get_san(move)
        board.push(move)
        fields = board.fen.split()
        return {
            "id": node_id,
            "parentId": parent_id,
            "order": order,
            "move": move,
            "fen": board.fen,
            "turnColor": "white" if fields[1] == "w" else "black",
            "check": board.is_checked(),
            "san": san,
        }

    def _chapter(self, move: str, *, name: str, node_id: str) -> dict[str, object]:
        return {
            "name": name,
            "variant": "chess",
            "chess960": False,
            "initialFen": FairyBoard.start_fen("chess"),
            "orientation": "black",
            "description": f"Description for {name}",
            "tags": {"Event": "Imported event"},
            "tree": {
                "rootAnnotations": {
                    "shapes": [],
                    "comments": [
                        {
                            "id": "Comment001",
                            "author": "spoofed",
                            "text": "Root import note",
                            "sourceAuthor": "Mary",
                            "sourceAuthorId": "mary",
                        }
                    ],
                    "nags": [3],
                },
                "nodes": [self._node(node_id, move)],
            },
        }

    async def _request(self, payload: dict[str, object], username: str = "owner"):
        request = SimpleNamespace(app=object(), match_info={"studyId": self.study.id})
        user = SimpleNamespace(username=username, anon=False, bot=False)
        with (
            patch("views.study.get_user_context", return_value=(user, {})),
            patch("views.study.get_app_state", return_value=self.app_state),
            patch("views.study.read_json_data", return_value=payload),
        ):
            return await study_import_pgn(cast(Any, request))

    async def test_imports_multiple_normalized_chapters_from_client(self) -> None:
        response = await self._request(
            {
                "chapters": [
                    self._chapter("e2e4", name="One", node_id="Node000001"),
                    self._chapter("d2d4", name="Two", node_id="Node000002"),
                ]
            }
        )
        self.assertEqual(response.status, 200)
        result = json.loads(response.body)
        self.assertTrue(result["ok"])
        self.assertEqual(result["imported"], 2)

        docs = (
            await self.db.study_chapter.find({"studyId": self.study.id})
            .sort("order", 1)
            .to_list(10)
        )
        self.assertEqual([doc["name"] for doc in docs], ["Chapter 1", "One", "Two"])
        imported = docs[1]
        self.assertEqual(imported["description"], "Description for One")
        self.assertEqual(imported["tags"], {"Event": "Imported event"})
        node = next(value for key, value in imported["root"].items() if key != "_")
        self.assertEqual(node["m"], "e2e4")
        self.assertEqual(node["s"], "e4")
        self.assertFalse(node.get("c", False))
        self.assertIn("4P3", node["f"])
        imported_comment = imported["root"]["_"]["a"]["c"][0]
        self.assertEqual(imported_comment["a"], "owner")
        self.assertEqual(imported_comment["x"], "Mary")
        self.assertEqual(imported_comment["y"], "mary")

    async def test_import_persists_client_parsed_evaluation(self) -> None:
        chapter = self._chapter("e2e4", name="Evaluated", node_id="Node000010")
        tree = cast(dict[str, object], chapter["tree"])
        nodes = cast(list[dict[str, object]], tree["nodes"])
        # Match the browser-normalized PGN payload: after 1.e4 Black is to move,
        # so a White +0.35 PGN evaluation is stored internally as Black -0.35.
        nodes[0]["turnColor"] = "black"
        nodes[0]["eval"] = {"cp": -35}

        response = await self._request({"chapters": [chapter]})
        self.assertEqual(response.status, 200)

        doc = await self.db.study_chapter.find_one({"studyId": self.study.id, "name": "Evaluated"})
        assert doc is not None
        node = next(value for key, value in doc["root"].items() if key != "_")
        self.assertEqual(node["e"], {"cp": -35})

    async def test_sync_off_import_keeps_existing_shared_chapter(self) -> None:
        response = await self._request(
            {
                "sync": False,
                "chapters": [self._chapter("e2e4", name="Private import", node_id="Node000009")],
            }
        )
        self.assertEqual(response.status, 200)
        study_doc = await self.db.study.find_one({"_id": self.study.id})
        assert study_doc is not None
        self.assertEqual(study_doc["currentChapter"], self.initial_chapter.id)

    async def test_rejects_invalid_later_chapter_without_partial_import(self) -> None:
        invalid = self._chapter("e2e4", name="Invalid", node_id="Node000004")
        invalid_tree = cast(dict[str, object], invalid["tree"])
        invalid_nodes = cast(list[dict[str, object]], invalid_tree["nodes"])
        # Chess legality belongs to the client for bulk import, but cheap payload
        # consistency remains server-owned. The FEN says Black is to move.
        invalid_nodes[0]["turnColor"] = "white"
        response = await self._request(
            {
                "chapters": [
                    self._chapter("e2e4", name="Valid", node_id="Node000003"),
                    invalid,
                ]
            }
        )
        self.assertEqual(response.status, 400)
        result = json.loads(response.body)
        self.assertIn("Imported chapter 2", result["error"])
        self.assertEqual(await self.db.study_chapter.count_documents({"studyId": self.study.id}), 1)

    async def test_imports_alice_chapter_with_mirror_board_fen(self) -> None:
        # Position after 1.e4 d6 2.Bc4 Qxd2, immediately before 3.Bb5#.
        # Alice FEN uses ``|`` inside the placement field to mark pieces that
        # currently occupy the mirror board. pyffish-alice is authoritative for
        # this syntax; generic first-class FEN character checks must not reject it.
        initial_fen = "rnb1kbnr/ppp1pppp/3|p4/8/2|B1|P3/8/PPP|q1PPP/RNBQK1NR w KQkq - 0 3"
        chapter = {
            "name": "Alice mate",
            "variant": "alice",
            "chess960": False,
            "initialFen": initial_fen,
            "orientation": "white",
            "description": "",
            "tags": {"Event": "Alice Chess"},
            "tree": {
                "nodes": [
                    self._node(
                        "NodeAlice1",
                        "c4b5",
                        variant="alice",
                        initial_fen=initial_fen,
                    )
                ]
            },
        }

        response = await self._request({"chapters": [chapter]})
        self.assertEqual(response.status, 200)

        doc = await self.db.study_chapter.find_one({"studyId": self.study.id, "name": "Alice mate"})
        assert doc is not None
        self.assertEqual(doc["initialFen"], initial_fen)
        node = next(value for key, value in doc["root"].items() if key != "_")
        self.assertEqual(node["m"], "c4b5")
        self.assertEqual(node["s"], "Bb5#")

    async def test_accepts_embedded_custom_variant_snapshot_without_live_catalog_entry(
        self,
    ) -> None:
        chapter = self._chapter("e2e4", name="Snapshot", node_id="Node000005")
        chapter["variant"] = "pgncustom"
        chapter["variantIni"] = (
            "[pgncustom:chess]\nstartFen = rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\n"
        )
        response = await self._request({"chapters": [chapter]})
        self.assertEqual(response.status, 200)

        doc = await self.db.study_chapter.find_one({"studyId": self.study.id, "name": "Snapshot"})
        assert doc is not None
        self.assertEqual(doc["variant"], "pgncustom")
        self.assertEqual(
            doc["variantIni"],
            "[pgncustom:chess]\nstartFen = rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\n",
        )
        node = next(value for key, value in doc["root"].items() if key != "_")
        self.assertEqual(node["m"], "e2e4")
        self.assertEqual(node["s"], "e4")

    async def test_other_user_cannot_import_into_private_study(self) -> None:
        with self.assertRaises(web.HTTPNotFound):
            await self._request(
                {"chapters": [self._chapter("e2e4", name="Nope", node_id="Node000006")]},
                username="intruder",
            )


if __name__ == "__main__":
    unittest.main()
