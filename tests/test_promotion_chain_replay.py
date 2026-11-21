from __future__ import annotations

import json
import shutil
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp_jinja2
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from catalogued.documents import _is_active_catalogued_doc
from catalogued.http import restore_catalogued_variant
from catalogued.variants import (
    can_create_catalogued_seek,
    catalogued_variant_allows_fishnet,
    catalogued_variant_client_doc_for_game,
    register_historical_catalogued_variant_doc,
)
from compress import encode_move_standard
from const import RESIGN
from game import Game
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import load_game, pgn
from variants import unregister_catalogued_server_variant
from wsr import handle_analysis

from server import make_app

NAME = "promotion_chain_replay_test"
ROOT = "7k/8/8/8/8/8/P7/7K w - - 0 1"
FINAL = "1+E2k3/8/8/8/8/8/8/7K b - - 4 6"
MOVES = ["a2a3+", "h8g7", "a3a4+", "g7h6", "a4a5+", "h6g6", "a5a6+", "g6f7", "a6b6", "f7e8", "b6b8"]
INI = (
    f"[{NAME}:chess]\ncustomPiece1=c:mfW\ncustomPiece2=d:mfW\ncustomPiece3=e:mfW\n"
    "promotedPieceType=p:c c:d d:e e:q\npromotionPieceTypes=-\n"
    "mandatoryPawnPromotion=false\npromotionRegionWhite=*1 *2 *3 *4 *5 *6 *7 *8\n"
    "promotionRegionBlack=*1 *2 *3 *4 *5 *6 *7 *8\n"
)


class PromotionChainReplayTest(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.addCleanup(unregister_catalogued_server_variant, NAME)
        self.state = get_app_state(self.app)
        self.white = User(self.state, username="chain_white")
        self.black = User(self.state, username="chain_black")
        self.state.users[self.white.username] = self.white
        self.state.users[self.black.username] = self.black
        await self.state.db.user.insert_many(
            [
                {"_id": self.white.username},
                {"_id": self.black.username},
            ]
        )
        self.doc = {
            "_id": "Chain001",
            "v": NAME,
            "vini": INI,
            "vd": "Chain replay",
            "vby": "chain_author",
            "us": [self.white.username, self.black.username],
            "if": ROOT,
            "f": FINAL,
            "m": [encode_move_standard(m) for m in MOVES],
            "s": RESIGN,
            "r": "a",
            "b": 5,
            "i": 0,
            "y": 0,
            "z": 0,
            "d": datetime(2026, 10, 1, tzinfo=UTC),
        }
        await self.state.db.game.insert_one(self.doc)

    async def test_cold_load_replays_entire_chain_and_exports_pgn_without_reactivation(self):
        game = await load_game(self.state, "Chain001")
        self.assertIsNotNone(game)
        game.ensure_steps()
        self.assertEqual(len(game.steps), len(MOVES) + 1)
        self.assertEqual(game.steps[-1]["fen"], FINAL)
        self.assertEqual(game.result, "1-0")
        self.assertEqual(game.status, RESIGN)
        self.assertIn("Ea6=Q+", game.pgn)
        self.assertIn("Qb8+", pgn(self.doc))
        self.assertTrue(game.server_variant.replay_only)
        self.assertTrue(self.state.catalogued_variants[NAME]["archived"])
        self.assertFalse(can_create_catalogued_seek(self.state, NAME, "chain_author"))
        self.assertFalse(catalogued_variant_allows_fishnet(self.state, NAME))
        metadata = await catalogued_variant_client_doc_for_game(self.state, game, "")
        self.assertIsNotNone(metadata)
        self.assertTrue(metadata["replayOnly"])

    async def test_profile_listing_before_direct_game_load_still_restores_replay_metadata(self):
        register_historical_catalogued_variant_doc(self.doc)
        self.assertNotIn(NAME, self.state.catalogued_variants)
        game = await load_game(self.state, "Chain001")
        self.assertTrue(game.server_variant.replay_only)
        self.assertTrue(self.state.catalogued_variants[NAME]["archived"])

    async def test_legacy_game_can_load_archived_catalogue_rules_without_inline_snapshot(self):
        await self.state.db.game.update_one({"_id": "Chain001"}, {"$unset": {"vini": ""}})
        await self.state.db.catalogued_variant.insert_one(
            {
                "_id": NAME,
                "name": NAME,
                "ini": INI,
                "archived": True,
                "enabled": False,
            }
        )
        game = await load_game(self.state, "Chain001")
        game.ensure_steps()
        self.assertEqual(game.steps[-1]["fen"], FINAL)

    async def test_all_new_opponents_and_analysis_are_blocked_after_replay_registration(self):
        game = await load_game(self.state, "Chain001")
        for opponent in (
            self.black,
            self.state.users["Random-Mover"],
            self.state.users["Fairy-Stockfish"],
        ):
            with self.subTest(opponent=opponent.username), self.assertRaises(ValueError):
                Game(self.state, "NewChain", NAME, ROOT, self.white, opponent)
        with patch("wsr.ws_send_json", new_callable=AsyncMock) as send:
            await handle_analysis(self.state, object(), {"gameId": game.id}, game)
            send.assert_awaited_once()
        self.assertFalse(self.state.fishnet_works)

    async def test_game_page_is_available_to_anonymous_spectators(self):
        response = await self.client.get("/Chain001?ply=7")
        self.assertEqual(response.status, 200)
        self.assertIn(NAME, await response.text())
        response = await self.client.get(f"/api/catalogued-variants/{NAME}/piece-disguised.css")
        self.assertEqual(response.status, 200)

    async def test_profile_listing_includes_chain_games_without_reactivating_rules(self):
        self.white.game_category = "all"
        self.client.session.cookie_jar.update_cookies(
            {
                "AIOHTTP_SESSION": json.dumps(
                    {
                        "session": {"user_name": self.white.username},
                        "created": int(datetime.now(UTC).timestamp()),
                    }
                ),
            }
        )
        response = await self.client.get(f"/api/games/user/{self.white.username}")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual([doc["_id"] for doc in payload], ["Chain001"])
        self.assertFalse(can_create_catalogued_seek(self.state, NAME, "chain_author"))


class PromotionChainAdmissionTest(unittest.IsolatedAsyncioTestCase):
    async def test_current_rules_are_blocked_even_before_the_author_archives_them(self):
        doc = {"name": NAME, "ini": INI, "author": "author", "enabled": True}
        state = SimpleNamespace(catalogued_variants={NAME: doc})
        self.assertFalse(_is_active_catalogued_doc(doc))
        self.assertFalse(can_create_catalogued_seek(state, NAME, "author"))
        self.assertFalse(catalogued_variant_allows_fishnet(state, NAME))
        with patch("catalogued.promotions.FSF_SUPPORTS_PROMOTION_CHAINING", True):
            self.assertTrue(_is_active_catalogued_doc(doc))
            self.assertTrue(can_create_catalogued_seek(state, NAME, "author"))
            self.assertTrue(catalogued_variant_allows_fishnet(state, NAME))

    async def test_archived_restore_rejects_before_database_update(self):
        collection = SimpleNamespace(update_one=AsyncMock())
        state = SimpleNamespace(db={"catalogued_variant": collection})
        doc = {"name": NAME, "ini": INI, "archived": True}
        with (
            patch(
                "catalogued.http._load_owned_doc",
                AsyncMock(return_value=(state, "author", NAME, doc)),
            ),
            self.assertRaises(web.HTTPBadRequest),
        ):
            await restore_catalogued_variant(SimpleNamespace())
        collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_replays_chain_without_search_or_new_moves(aiohttp_server, tmp_path):
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright, expect

    app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
    server = await aiohttp_server(app, host="127.0.0.1")
    aiohttp_jinja2.get_env(app).globals["home"] = f"http://{server.host}:{server.port}"
    state = get_app_state(app)
    for name in ("chain_white", "chain_black"):
        state.users[name] = User(state, username=name)
    await state.db.game.insert_one(
        {
            "_id": "Chain001",
            "v": NAME,
            "vini": INI,
            "vd": "Chain replay",
            "vby": "chain_author",
            "us": ["chain_white", "chain_black"],
            "if": ROOT,
            "f": FINAL,
            "m": [encode_move_standard(m) for m in MOVES],
            "s": RESIGN,
            "r": "a",
            "b": 5,
            "i": 0,
            "y": 0,
            "z": 0,
            "d": datetime(2026, 10, 1, tzinfo=UTC),
        }
    )
    try:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                executable = shutil.which("chromium-browser") or shutil.which("chromium")
                if "Executable doesn't exist" not in str(error) or executable is None:
                    raise
                browser = await playwright.chromium.launch(
                    headless=True, executable_path=executable
                )
            page = await browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.add_init_script("""
                localStorage.localAnalysis = 'true';
                window.chainSearches = [];
                let engine;
                Object.defineProperty(window, 'fsf', {
                    configurable: true,
                    get: () => engine,
                    set: value => {
                        engine = value;
                        const send = value.postMessage.bind(value);
                        value.postMessage = command => {
                            if (typeof command === 'string' && command.startsWith('go '))
                                window.chainSearches.push(command);
                            send(command);
                        };
                    },
                });
            """)
            try:
                response = await page.goto(f"http://{server.host}:{server.port}/Chain001?ply=0")
                assert response.status == 200
                moves = page.locator("#movelist move[data-path]")
                await expect(moves).to_have_count(len(MOVES))
                await expect(page.locator("#fullfen")).to_have_value(ROOT)
                await moves.nth(6).click()
                await expect(page.locator("#fullfen")).to_have_value(
                    "8/8/+E5k1/8/8/8/8/7K b - - 0 4"
                )
                await moves.nth(0).click()
                await expect(page.locator("#fullfen")).to_have_value(
                    "7k/8/8/8/8/+P7/8/7K b - - 0 1"
                )
                await moves.last.click()
                await expect(page.locator("#fullfen")).to_have_value(FINAL)
                assert await page.locator("#request-analysis button").count() == 0
                assert await page.locator("cg-board square.move-dest").count() == 0
                assert await page.evaluate("window.chainSearches") == []
                assert not errors, errors
                await page.screenshot(path=str(tmp_path / "promotion-chain-replay.png"))
            finally:
                (tmp_path / "replay-page.html").write_text(await page.content())
                await page.screenshot(path=str(tmp_path / "promotion-chain-replay.png"))
                await browser.close()
    finally:
        unregister_catalogued_server_variant(NAME)
