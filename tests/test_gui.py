import asyncio
import json
import re
import shutil
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import test_logger
from const import T_FINISHED
from game import Game
from mongomock_motor import AsyncMongoMockClient
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright, expect
from pychess_global_app_state_utils import get_app_state
from tournament.tournament import SCORE_SHIFT
from user import User
from utils import insert_game_to_db

from server import make_app

test_logger.init_test_logger()


@pytest.mark.asyncio
class TestGUI:
    @pytest.mark.parametrize(
        "name", ["janggi", "janggitraditional", "janggimodern", "janggicasual"]
    )
    @pytest.mark.parametrize("width,theme", [(1280, "light"), (390, "dark")])
    async def test_janggi_family_setup_pass_bikjang_points_and_replay(
        self, aiohttp_server, name, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from const import STARTED, VARIANTEND
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        if name != "janggi":
            doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
            register_catalogued_variant_doc(state, doc)
        counted = name in ("janggi", "janggimodern")
        bikjang = name in ("janggi", "janggitraditional")
        players = []
        for side in ("blue", "red"):
            username = "janggi-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        game = Game(state, "JangSetp", name, "", *players, base=5, inc=5, byoyomi_period=1)
        state.games[game.id] = game
        await insert_game_to_db(game, state)

        async def points(page, white="72", black="73.5"):
            if counted:
                await expect(page.locator("#misc-infow")).to_have_text(white)
                await expect(page.locator("#misc-infob")).to_have_text(black)
            else:
                for info in await page.locator("#misc-infow, #misc-infob").all():
                    await expect(info).to_have_text("")

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages, errors = [], []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await expect(page.locator("#mainboard.janggi9x10.janggi")).to_be_visible()
                    await points(page)
                    await expect(
                        page.get_by_role("button", name="Pass", exact=True)
                    ).to_be_visible()
                    pages.append(page)
                await expect(pages[1].locator("#flipLeft")).to_be_visible()
                assert await pages[0].locator("#flipLeft").count() == 0
                await pages[1].locator("#flipLeft").click()
                await pages[1].locator("#janggi-setup-buttons button").nth(1).click()
                await self._eventually(lambda: not game.bsetup and game.wsetup)
                await pages[1].reload()
                await expect(pages[0].locator("#flipRight")).to_be_visible()
                await pages[0].locator("#flipRight").click()
                await pages[0].locator("#janggi-setup-buttons button").nth(1).click()
                await self._eventually(lambda: not game.bsetup and not game.wsetup)
                assert game.status == STARTED
                initial = game.board.initial_fen
                assert (
                    initial
                    != "rnba1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ABNR w - - 0 1"
                )

                async def play(move=None, ctrl_pass=False):
                    ply = game.board.ply
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    if move:
                        await page.evaluate(
                            "move => {window.cg.selectSquare(move.slice(0,2));window.cg.selectSquare(move.slice(2,4));}",
                            move.replace("10", ":"),
                        )
                    elif ctrl_pass:
                        await page.evaluate("""() => {
                            const cg = window.cg;
                            const entry = [...cg.state.movable.dests].find(([key, dests]) => dests.includes(key));
                            cg.state.stats.ctrlKey = true;
                            cg.selectSquare(entry[0]);
                        }""")
                    else:
                        await page.get_by_role("button", name="Pass", exact=True).click()
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    if ctrl_pass:
                        await page.evaluate("() => {window.cg.state.stats.ctrlKey = false;}")

                await play("a4a5")
                await play("a7a6")
                await play(ctrl_pass=True)
                assert game.board.move_stack[-1] == "e2e2"
                for page in pages:
                    await page.wait_for_function("() => window.cg.state.turnColor === 'black'")
                await play()
                await self._eventually(lambda: game.result != "*")
                assert game.status == VARIANTEND
                assert game.result == ("0-1" if counted else "1/2-1/2")
                final_fen = game.board.fen
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.initial_fen == initial
                assert restored.board.fen == final_fen
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=4")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await points(page)
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(initial)
                for ply in range(1, 5):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])

                # A challenge can be accepted, or its facing kings can be separated.
                position = "9/4k4/9/p8/9/4P4/9/9/4K4/R8 w - - 0 1"
                for game_id, reply in (("JangBikj", None), ("JangExit", "e9d9")):
                    game = Game(state, game_id, name, position, *players, base=5)
                    state.games[game.id] = game
                    await insert_game_to_db(game, state)
                    for page in pages:
                        await page.goto(f"{base_url}/{game.id}")
                    await play("e5d5")
                    await pages[1].wait_for_function("() => window.cg.state.turnColor === 'black'")
                    assert await pages[1].evaluate(
                        "() => window.cg.state.movable.dests.get('a7')?.includes('a6') || false"
                    ) == (not bikjang)
                    await play(reply)
                    if bikjang and reply is None:
                        await self._eventually(lambda active_game=game: active_game.result != "*")
                        assert game.result == ("1-0" if counted else "1/2-1/2")
                    else:
                        assert game.result == "*"
                        if reply:
                            await play("a1a7")
                            for page in pages:
                                await points(page, "15", "1.5")
                        await game.game_ended(players[0], "resign")

                # An ordinary check cannot be answered by passing or Ctrl-clicking the king.
                check_fen = position.replace("4P4/9/9", "4P4/9/4r4")
                game = Game(state, "JangChek", name, check_fen, *players, base=5)
                state.games[game.id] = game
                await insert_game_to_db(game, state)
                page = pages[0]
                sent_moves = []

                def record_frame(payload):
                    if isinstance(payload, str) and payload.startswith("{"):
                        message = json.loads(payload)
                        if message.get("type") == "move":
                            sent_moves.append(message)

                page.on("websocket", lambda socket: socket.on("framesent", record_frame))
                await page.goto(f"{base_url}/{game.id}")
                await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                await page.get_by_role("button", name="Pass", exact=True).click()
                await page.evaluate("""() => {
                    window.cg.state.stats.ctrlKey = true;
                    window.cg.selectSquare('e2');
                    window.cg.state.stats.ctrlKey = false;
                }""")
                await page.screenshot(path=f"/tmp/{name}-{width}-{theme}.png")
                assert sent_moves == []
                assert game.board.ply == 0
                await game.game_ended(players[0], "resign")
                assert errors == []
            finally:
                await browser.close()
                if name != "janggi":
                    unregister_catalogued_server_variant(name)

    @pytest.mark.parametrize("color", ["white", "black"])
    @pytest.mark.parametrize(
        "piece,choice,suffix", [("p", "pp", "+"), ("p", "q", "q"), ("s", "q", "q")]
    )
    async def test_wolf_mixed_promotion_picker(self, aiohttp_server, color, piece, choice, suffix):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("wolf", FSF_CATALOGUED_BUILTIN_VARIANTS["wolf"])
        register_catalogued_variant_doc(state, doc)
        players = []
        for side in ("white", "black"):
            username = "wolf-" + side
            await state.db.user.insert_one({"_id": username, "enabled": True, "ct": "all"})
            user = User(state, username=username)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        initial = (
            f"7k/{piece.upper()}7/8/8/8/8/8/8/8/7K w - - 0 1"
            if color == "white"
            else f"7k/8/8/8/8/8/8/8/{piece}7/7K b - - 0 1"
        )
        game = Game(state, "WolfPrmt", "wolf", initial, *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                context, page = await self._playwright_page_for_user(
                    browser, base_url, "wolf-" + color
                )
                await context.add_init_script("localStorage.setItem('autoPromote','false');")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(f"{base_url}/{game.id}")
                await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                await page.evaluate(
                    "color => { window.cg.selectSquare(color === 'white' ? 'a9' : 'a2'); window.cg.selectSquare(color === 'white' ? 'a:' : 'a1'); }",
                    color,
                )
                roles = ["q", "w", "f", "r", "b"] + (["pp"] if piece == "p" else [])
                await expect(page.locator("#extension_choice piece")).to_have_count(len(roles))
                for role in roles:
                    await expect(
                        page.locator(f"#extension_choice piece.{role}-piece")
                    ).to_be_visible()
                if piece == "s":
                    assert await page.locator("#extension_choice piece.pp-piece").count() == 0
                await page.locator(f"#extension_choice piece.{choice}-piece").click()
                await self._eventually(lambda: game.board.ply == 1)
                assert game.board.move_stack == [("a9a10" if color == "white" else "a2a1") + suffix]
                await page.wait_for_function(
                    "({dest, role}) => window.cg.state.boardState.pieces.get(dest)?.role === role",
                    arg={"dest": "a:" if color == "white" else "a1", "role": choice + "-piece"},
                )
                if choice == "pp":
                    assert ("+P" if color == "white" else "+p") in game.board.fen
                # Persist at least three plies, then replay the intrinsic +P role.
                from utils import load_game

                for _ in range(2):
                    await game.play_move(game.board.legal_moves()[0])
                final_fen = game.board.fen
                await game.game_ended(players[0], "resign")
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.fen == final_fen
                assert restored.board.move_stack == game.board.move_stack
                await page.goto(f"{base_url}/{game.id}?ply=1")
                await expect(page.locator("#fullfen")).to_have_value(game.steps[1]["fen"])
                await expect(
                    page.locator(f"#mainboard piece.{choice}-piece.{color}")
                ).to_be_visible()
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(initial)
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("wolf")

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_wolf_alfaerie_board_and_previews(self, aiohttp_server, width, theme):
        import base64
        from pathlib import Path

        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("wolf", FSF_CATALOGUED_BUILTIN_VARIANTS["wolf"])
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        players = []
        for side in ("white", "black"):
            username = "wolf-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        game = Game(state, "WolfArts", "wolf", "", *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)
        assets = {
            "k": "king",
            "q": "queen",
            "r": "rook",
            "b": "bishop",
            "p": "pawn",
            "w": "chancellor",
            "f": "cardinal",
            "s": "sergeant",
            "n": "nightrider",
            "pp": "amazonrider",
            "e": "amazonrider",
        }
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                _, page = await self._playwright_page_for_user(
                    browser, base_url, players[0].username
                )
                await page.set_viewport_size({"width": width, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(f"{base_url}/{game.id}")
                await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                await expect(page.locator("#mainboard.catalogued8x10.wolf")).to_be_visible()
                bounds = await page.locator("#mainboard cg-board").bounding_box()
                assert bounds is not None
                assert abs(bounds["height"] / bounds["width"] - 1.25) < 0.01
                sheets = await page.evaluate(
                    "() => [...document.styleSheets].map(s => s.href || '')"
                )
                assert any("/piece-css/wolf/alfaerie.css" in href for href in sheets)
                for color in ("white", "black"):
                    for role, asset in assets.items():
                        expected = base64.b64encode(
                            Path(
                                f"static/images/pieces/alfaerie/{color[0]}{asset}.svg"
                            ).read_bytes()
                        ).decode()
                        actual = await page.locator("#mainboard cg-board").evaluate(
                            """(board, {role, color}) => {
                                const piece = document.createElement('piece');
                                piece.className = `${role}-piece ${color} ally`;
                                board.append(piece);
                                const style = getComputedStyle(piece);
                                const result = {image: style.backgroundImage,
                                    width: parseFloat(style.width), height: parseFloat(style.height)};
                                piece.remove();
                                return result;
                            }""",
                            {"role": role, "color": color},
                        )
                        assert expected in actual["image"], (role, color)
                        assert abs(actual["width"] - bounds["width"] / 8) < 1
                        assert abs(actual["height"] - bounds["height"] / 10) < 1
                await page.screenshot(path=f"/tmp/wolf-{width}-{theme}.png")
                await page.locator("#btn-settings").click()
                await page.locator("#btn-board").click()
                await page.select_option("#settings-variant", "wolf")
                thumbnail = page.locator("label.piece.piece0.wolf")
                await expect(thumbnail).to_be_visible()
                assert "wchancellor.svg" in await thumbnail.evaluate(
                    "el => getComputedStyle(el).backgroundImage"
                )
                await page.goto(base_url + "/variants/community")
                preview = page.locator('.catalogued-start-board-preview[data-variant="wolf"]')
                await preview.scroll_into_view_if_needed()
                await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                image = await preview.locator("piece.w-piece.white").evaluate(
                    "el => getComputedStyle(el).backgroundImage"
                )
                expected = base64.b64encode(
                    Path("static/images/pieces/alfaerie/wchancellor.svg").read_bytes()
                ).decode()
                assert expected in image
                assert errors == []
                await game.game_ended(players[0], "resign")
            finally:
                await browser.close()
                unregister_catalogued_server_variant("wolf")

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_karouk_cambodian_leaps_promotion_first_check_and_counting(
        self, aiohttp_server, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from const import DRAW, VARIANTEND
        from utils import load_game, sanitize_fen
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("karouk", FSF_CATALOGUED_BUILTIN_VARIANTS["karouk"])
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        assert sanitize_fen("karouk", doc["startFen"], False)[0]
        players = []
        for side in ("white", "black"):
            username = "karouk-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        game = Game(state, "KarStart", "karouk", "", *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)

        async def badges(page, values):
            await expect(page.locator("#mainboard .cg-custom-svgs text")).to_have_text(values)

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages, errors = [], []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await badges(page, ["1", "1"])
                    await expect(page.locator("#mainboard.makruk8x8.makruk")).to_be_visible()
                    assert await page.locator("#count").count() == 0
                    piece = page.locator("#mainboard piece.k-piece").first
                    assert await piece.evaluate(
                        "el => [getComputedStyle(el).backgroundImage, getComputedStyle(el, '::before').backgroundImage].some(image => image !== 'none')"
                    )
                    pages.append(page)

                async def play(move):
                    ply = game.board.ply
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        "move => {window.cg.selectSquare(move.slice(0,2));window.cg.selectSquare(move.slice(2,4));}",
                        move,
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                    assert await page.locator("#extension_choice piece").count() == 0

                for move in ("e3e4", "d6d5", "e1e3", "e8g7", "d1b2"):
                    await play(move)
                    assert game.result == "*"
                assert game.board.fen.split()[2] == "d"
                await game.game_ended(players[0], "resign")

                initial = "4k3/8/8/P7/8/8/3R4/4K3 w - - 1+1 0 1"
                moves = ["a5a6m", "e8f8", "d2d3", "f8g8", "d3g3"]
                game = Game(state, "KarCheck", "karouk", initial, *players, base=5)
                state.games[game.id] = game
                await insert_game_to_db(game, state)
                for page in pages:
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                for ply, move in enumerate(moves):
                    await play(move)
                    for page in pages:
                        await badges(page, ["1", "0"] if ply == len(moves) - 1 else ["1", "1"])
                        assert await page.locator("#count").count() == 0
                        if ply == 0:
                            await expect(page.locator("#misc-infob")).to_have_text("4/16")
                    if ply < len(moves) - 1:
                        assert game.result == "*"
                await self._eventually(lambda: game.result == "1-0")
                assert game.status == VARIANTEND
                assert "M~" in game.board.fen
                final_fen = game.board.fen
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                assert restored.result == "1-0"
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=5")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.get_by_title("First move", exact=True).click()
                await badges(page, ["1", "1"])
                for ply in range(1, 6):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])
                    if ply == 1:
                        await expect(page.locator("#misc-infob")).to_have_text("4/16")
                await page.screenshot(path=f"/tmp/karouk-{width}-{theme}.png")

                # The engine still adjudicates the inherited Cambodian counting draw.
                count_fen = "4k3/8/8/8/8/8/3R4/4K3 w - 30 1+1 30 16"
                game = Game(state, "KarCount", "karouk", count_fen, *players, base=5)
                state.games[game.id] = game
                await insert_game_to_db(game, state)
                await pages[0].goto(f"{base_url}/{game.id}")
                await play("d2d3")
                await self._eventually(lambda: game.result == "1/2-1/2")
                assert game.status == DRAW
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("karouk")

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_breakthrough_quiet_diagonals_goal_ranks_and_saved_analysis(
        self, aiohttp_server, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from const import STALEMATE, VARIANTEND
        from utils import load_game, sanitize_fen
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc(
            "breakthrough", FSF_CATALOGUED_BUILTIN_VARIANTS["breakthrough"]
        )
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        assert sanitize_fen("breakthrough", doc["startFen"], False)[0]
        players = []
        for side in ("white", "black"):
            username = "breakthrough-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        initial = "7p/7p/8/8/8/2Pp4/8/8 w - - 0 1"
        moves = ["c3d4", "h7h6", "d4e5", "h6h5", "e5f6", "h5g4", "f6g7", "g4f3", "g7h8"]
        game = Game(state, "BreakTst", "breakthrough", initial, *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)

        async def goal_marks(board):
            marks = await board.evaluate("""el => {
                const bounds = el.getBoundingClientRect();
                return ['::before', '::after'].map(pseudo => {
                    const style = getComputedStyle(el, pseudo);
                    return {content: style.content, width: parseFloat(style.width),
                        height: parseFloat(style.height), top: parseFloat(style.top),
                        shadow: style.boxShadow, pointer: style.pointerEvents,
                        boardWidth: bounds.width, boardHeight: bounds.height};
                });
            }""")
            for index, mark in enumerate(marks):
                assert mark["content"] == '""'
                assert abs(mark["width"] - mark["boardWidth"]) < 1
                assert abs(mark["height"] - mark["boardHeight"] / 8) < 1
                assert abs(mark["top"] - index * mark["boardHeight"] * 7 / 8) < 1
                assert mark["shadow"] != "none"
                assert mark["pointer"] == "none"

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages, errors = [], []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await expect(
                        page.locator("#mainboard.standard8x8.standard.campmate")
                    ).to_be_visible()
                    await goal_marks(page.locator("#mainboard cg-board"))
                    board = await page.locator("#mainboard cg-board").bounding_box()
                    assert board is not None
                    assert abs(board["width"] - board["height"]) < 1
                    for color in ("white", "black"):
                        piece = page.locator(f"#mainboard piece.p-piece.{color}").first
                        assert (
                            await piece.evaluate("el => getComputedStyle(el).backgroundImage")
                            != "none"
                        )
                    assert await page.locator('button[title="Pass"]').count() == 0
                    pages.append(page)
                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        "move => {window.cg.selectSquare(move.slice(0,2));window.cg.selectSquare(move.slice(2,4));}",
                        move,
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                    assert await page.locator("#extension_choice piece").count() == 0
                    for player_page in pages:
                        await player_page.wait_for_function(
                            "fen => window.cg.getFen() === fen", arg=game.board.fen.split()[0]
                        )
                        await player_page.wait_for_function(
                            "() => window.cg.state.boardState.pieces.get('d3')?.color === 'black'"
                        )
                    if ply < len(moves) - 1:
                        assert game.result == "*"
                await self._eventually(lambda: game.result == "1-0")
                assert game.status == VARIANTEND
                assert not game.check
                final_fen = game.board.fen
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                assert restored.result == "1-0"
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=9")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await goal_marks(page.locator("#mainboard cg-board"))
                await page.get_by_title("First move", exact=True).click()
                for ply in range(1, 10):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])
                await page.screenshot(path=f"/tmp/breakthrough-{width}-{theme}.png")

                from urllib.parse import urlencode

                await page.goto(base_url + "/analysis/breakthrough?" + urlencode({"fen": initial}))
                board = page.locator("#mainboard cg-board")
                await expect(board).to_be_visible()
                await goal_marks(board)
                await board.scroll_into_view_if_needed()
                for key in ("c3", "d4"):
                    bounds = await board.bounding_box()
                    assert bounds is not None
                    await page.mouse.click(
                        bounds["x"] + bounds["width"] * (ord(key[0]) - ord("a") + 0.5) / 8,
                        bounds["y"] + bounds["height"] * (8 - int(key[1]) + 0.5) / 8,
                    )
                await expect(page.locator("#fullfen")).to_have_value(game.steps[1]["fen"])
                assert await page.locator("#extension_choice piece").count() == 0
                await page.goto(base_url + "/variants/community")
                preview = page.locator(
                    '.catalogued-start-board-preview[data-variant="breakthrough"]'
                )
                await preview.scroll_into_view_if_needed()
                await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                assert await preview.locator("piece.p-piece").count() == 32
                await goal_marks(preview.locator("cg-board"))

                # Black can reach rank 1; capturing the last enemy pawn wins too.
                for game_id, fen, move, result, status in (
                    ("BreakBlk", "8/P7/8/8/8/8/7p/8 b - - 0 1", "h2h1", "0-1", VARIANTEND),
                    ("BreakCap", "8/8/8/8/8/8/2p5/1P6 w - - 0 1", "b1c2", "1-0", STALEMATE),
                ):
                    game = Game(state, game_id, "breakthrough", fen, *players, base=5)
                    state.games[game.id] = game
                    await insert_game_to_db(game, state)
                    page = pages[game.board.color]
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        "move => {window.cg.selectSquare(move.slice(0,2));window.cg.selectSquare(move.slice(2,4));}",
                        move,
                    )
                    await self._eventually(
                        lambda active_game=game, expected=result: active_game.result == expected
                    )
                    assert game.status == status
                    assert await page.locator("#extension_choice piece").count() == 0
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("breakthrough")

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_check_shogi_first_check_wins_with_drops_promotion_and_replay(
        self, aiohttp_server, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from const import VARIANTEND
        from utils import load_game, sanitize_fen
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("checkshogi", FSF_CATALOGUED_BUILTIN_VARIANTS["checkshogi"])
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        assert sanitize_fen("checkshogi", doc["startFen"], False)[0]
        players = []
        for side in ("white", "black"):
            username = "checkshogi-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        game = Game(state, "CheckIni", "checkshogi", "", *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)
        initial = "4k4/9/9/9/9/9/2p6/2R6/4K4[] w - - 1+1 0 1"
        moves = ["c2c3", "e9f9", "P@a4", "f9g9", "c3c7+", "g9h9", "c7h7"]

        async def badges(page, values):
            await expect(page.locator("#mainboard .cg-custom-svgs text")).to_have_text(values)

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages, errors = [], []
                for player in players:
                    context, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await context.add_init_script("localStorage.setItem('autoPromote', 'false');")
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await badges(page, ["1", "1"])
                    await expect(page.locator("#mainboard.shogi9x9.shogi")).to_be_visible()
                    piece = page.locator("#mainboard piece.k-piece").first
                    assert await piece.evaluate(
                        "el => [getComputedStyle(el).backgroundImage, getComputedStyle(el, '::before').backgroundImage].some(image => image !== 'none')"
                    )
                    pages.append(page)
                await game.game_ended(players[0], "resign")
                game = Game(state, "CheckTst", "checkshogi", initial, *players, base=5)
                state.games[game.id] = game
                await insert_game_to_db(game, state)
                for page in pages:
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await badges(page, ["1", "1"])
                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        """move => {
                        if (move.includes('@')) window.cg.selectPocket({role:'p-piece', color:window.cg.state.turnColor});
                        else window.cg.selectSquare(move.slice(0,2));
                        window.cg.selectSquare(move.includes('@') ? move.slice(-2) : move.slice(2,4));
                    }""",
                        move,
                    )
                    if move.endswith("+"):
                        await page.locator("#extension_choice piece.pr-piece").click()
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                    for player_page in pages:
                        await badges(
                            player_page, ["1", "0"] if ply == len(moves) - 1 else ["1", "1"]
                        )
                    if ply < len(moves) - 1:
                        assert game.result == "*"
                await self._eventually(lambda: game.result == "1-0")
                assert game.status == VARIANTEND
                assert game.check
                final_fen = game.board.fen
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                assert restored.result == "1-0"
                assert restored.status == VARIANTEND
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=7")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await badges(page, ["1", "0"])
                await page.get_by_title("First move", exact=True).click()
                await badges(page, ["1", "1"])
                for ply in range(1, 8):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])
                await page.screenshot(path=f"/tmp/checkshogi-{width}-{theme}.png")

                # Analysis can finish on a checking drop; no checkmate is needed.
                from urllib.parse import urlencode

                pawn_fen = "4k4/9/9/9/9/9/9/9/4K4[P] w - - 1+1 0 1"
                await page.goto(f"{base_url}/analysis/checkshogi?" + urlencode({"fen": pawn_fen}))
                await badges(page, ["1", "1"])
                await page.locator(".pocketrow piece.p-piece.white").click()
                board = page.locator("#mainboard cg-board")
                await board.scroll_into_view_if_needed()
                bounds = await board.bounding_box()
                assert bounds is not None
                await page.mouse.click(
                    bounds["x"] + bounds["width"] * 4.5 / 9,
                    bounds["y"] + bounds["height"] * 1.5 / 9,
                )
                await expect(page.locator("#fullfen")).to_have_value(
                    re.compile(r" b - - 0\+1 0 1$")
                )
                await badges(page, ["1", "0"])
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("checkshogi")

    @pytest.mark.parametrize("name,files,ranks", [("clobber", 5, 6), ("clobber10", 10, 10)])
    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_clobber_captures_last_move_wins_and_analysis(
        self, aiohttp_server, name, files, ranks, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game, sanitize_fen
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        assert sanitize_fen(name, doc["startFen"], False)[0]
        players = []
        for side in ("white", "black"):
            username = "clobber-" + side
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            user = User(state, username=username, theme=theme)
            user.game_category_set = True
            state.users[username] = user
            players.append(user)
        game = Game(state, "ClobberT", name, "", *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)

        async def no_material_scores(page):
            assert all(
                not text.strip()
                for text in await page.locator("#misc-infow, #misc-infob").all_text_contents()
            )

        def squares(move):
            match = re.fullmatch(r"([a-j](?:10|[1-9]))([a-j](?:10|[1-9]))", move)
            assert match is not None
            return [key.replace("10", ":") for key in match.groups()]

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages, errors = [], []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await no_material_scores(page)
                    bounds = await page.locator("#mainboard cg-board").bounding_box()
                    assert bounds is not None
                    assert abs(bounds["height"] / bounds["width"] - ranks / files) < 0.01
                    piece = page.locator("#mainboard piece.p-piece").first
                    image = await piece.evaluate("el => getComputedStyle(el).backgroundImage")
                    assert image != "none"
                    assert await page.locator('button[title="Pass"]').count() == 0
                    pages.append(page)

                for ply in range(5):
                    legal = game.board.legal_moves()
                    if ply < 2:
                        edge = str(ranks) if ply == 0 else "1"
                        move = next(
                            move
                            for move in legal
                            if squares(move)[1][1:] == edge.replace("10", ":")
                        )
                    else:
                        move = legal[0]
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        "keys => keys.forEach(key => window.cg.selectSquare(key))", squares(move)
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                    for page in pages:
                        await page.wait_for_function(
                            "fen => window.cg.getFen() === fen", arg=game.board.fen.split()[0]
                        )
                        await no_material_scores(page)
                moves, final_fen = list(game.board.move_stack), game.board.fen
                await game.game_ended(players[0], "resign")
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=5")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.get_by_title("First move", exact=True).click()
                for ply in range(6):
                    await no_material_scores(page)
                    if ply < 5:
                        await page.get_by_title("Next move", exact=True).click()
                        await expect(page.locator("#fullfen")).to_have_value(
                            game.steps[ply + 1]["fen"]
                        )

                await page.goto(f"{base_url}/analysis/{name}")
                await no_material_scores(page)
                board = page.locator("#mainboard cg-board")
                await board.scroll_into_view_if_needed()
                bounds = await board.bounding_box()
                assert bounds is not None
                for key in squares(moves[0]):
                    x, y = ord(key[0]) - ord("a"), ord(key[1]) - ord("1")
                    await page.mouse.click(
                        bounds["x"] + bounds["width"] * (x + 0.5) / files,
                        bounds["y"] + bounds["height"] * (ranks - y - 0.5) / ranks,
                    )
                await expect(page.locator("#fullfen")).to_have_value(game.steps[1]["fen"])
                await no_material_scores(page)
                await page.screenshot(path=f"/tmp/{name}-analysis-{width}-{theme}.png")
                await page.goto(base_url + "/variants/community")
                preview = page.locator(f'.catalogued-start-board-preview[data-variant="{name}"]')
                await preview.scroll_into_view_if_needed()
                await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                mini = await preview.locator("cg-board").bounding_box()
                assert mini is not None
                assert abs(mini["height"] / mini["width"] - ranks / files) < 0.01
                assert await preview.locator("piece.p-piece").count() == files * ranks

                # White wins by blocking Black, despite having fewer discs.
                rows = (
                    ["p" + str(files - 1)]
                    + [str(files)] * (ranks - 3)
                    + ["2p" + str(files - 3), "Pp" + str(files - 2)]
                )
                game = Game(
                    state, "ClobEndT", name, "/".join(rows) + " w - - 0 1", *players, base=5
                )
                state.games[game.id] = game
                await insert_game_to_db(game, state)
                await pages[0].goto(f"{base_url}/{game.id}")
                await pages[0].wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                await pages[0].evaluate(
                    "() => {window.cg.selectSquare('a1'); window.cg.selectSquare('b1');}"
                )
                await self._eventually(lambda: game.result == "1-0")
                await no_material_scores(pages[0])
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant(name)

    @pytest.mark.parametrize("name", ["flipello", "flipello10", "flipersi"])
    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_reversi_placement_flipping_pass_scoring_and_replay(
        self, aiohttp_server, name, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game, sanitize_fen
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
        register_catalogued_variant_doc(state, doc)
        await state.db.catalogued_variant.insert_one(doc)
        assert sanitize_fen(name, doc["startFen"], False)[0]
        assert not sanitize_fen(name, doc["startFen"].replace("[", "[P"), False)[0]
        players = []
        for suffix in ("white", "black"):
            username = "reversi-" + suffix
            await state.db.user.insert_one(
                {"_id": username, "enabled": True, "ct": "all", "theme": theme}
            )
            player = User(state, username=username, theme=theme)
            player.game_category_set = True
            state.users[username] = player
            players.append(player)
        game = Game(state, "ReversiT", name, "", *players, base=5)
        state.games[game.id] = game
        await insert_game_to_db(game, state)
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:

                async def check_counts(page, fen):
                    placement = fen.split()[0].split("[")[0]
                    await expect(page.locator("#misc-infow")).to_have_text(
                        str(placement.count("P"))
                    )
                    await expect(page.locator("#misc-infob")).to_have_text(
                        str(placement.count("p"))
                    )
                    await expect(page.locator("#misc-infow")).to_have_class(
                        re.compile(r"\btext-color-red\b")
                    )
                    await expect(page.locator("#misc-infob")).to_have_class(
                        re.compile(r"\btext-color-blue\b")
                    )

                async def check_count_colors(page):
                    for side, channel in (("w", 0), ("b", 2)):
                        indicator = page.locator("#misc-info" + side)
                        await expect(indicator).to_be_visible()
                        color = await indicator.evaluate("el => getComputedStyle(el).color")
                        rgb = [int(value) for value in re.findall(r"\d+", color)[:3]]
                        assert rgb[channel] > rgb[2 - channel]

                pages = []
                errors = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await expect(page.locator("#mainboard.ataxx")).to_be_visible()
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await check_counts(page, game.board.fen)
                    await check_count_colors(page)
                    pages.append(page)

                async def play(move):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    ply = game.board.ply
                    if "@" in move:
                        await page.evaluate(
                            """dest => {
                            window.cg.selectPocket({role: 'p-piece', color: window.cg.state.turnColor});
                            window.cg.selectSquare(dest);
                        }""",
                            move[2:],
                        )
                    else:
                        await page.get_by_title("Pass", exact=True).click()
                    await self._eventually(lambda: game.board.ply == ply + 1)
                    assert game.board.move_stack[-1] == move
                    expected = game.board.fen.split()[0].split("[")[0]
                    await page.wait_for_function(
                        "fen => window.cg.getFen().split('[')[0] === fen", arg=expected
                    )
                    for player_page in pages:
                        await check_counts(player_page, game.board.fen)

                # Reach the first flipping move even in Flipersi's empty opening.
                for _ in range(5):
                    await play(game.board.legal_moves()[0])
                assert game.board.fen != doc["startFen"]
                await pages[0].keyboard.press("f")
                await check_counts(pages[0], game.board.fen)
                await pages[0].keyboard.press("f")
                await check_counts(pages[0], game.board.fen)
                for page in pages:
                    images = await page.locator("#mainboard piece.p-piece").evaluate_all(
                        "pieces => pieces.map(piece => getComputedStyle(piece).backgroundImage)"
                    )
                    assert images and all(image != "none" for image in images)
                    assert await page.locator('button[title="Pass"]').count() == (
                        0 if name == "flipersi" else 1
                    )
                await (
                    pages[0]
                    .locator("#mainboard")
                    .screenshot(path=f"/tmp/{name}-{width}-{theme}.png")
                )
                final_fen = game.board.fen
                moves = list(game.board.move_stack)
                await game.game_ended(players[0], "resign")
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=5")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.get_by_title("First move", exact=True).click()
                await check_counts(page, doc["startFen"])
                for ply in range(1, 6):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])
                    await check_counts(page, game.steps[ply]["fen"])

                # Analysis accepts the same pocket placement and updates flipped discs.
                await page.goto(f"{base_url}/analysis/{name}")
                await check_counts(page, doc["startFen"])
                await check_count_colors(page)
                await page.locator(".pocketrow piece.p-piece.white").click()
                await page.locator("#mainboard cg-board").scroll_into_view_if_needed()
                bounds = await page.locator("#mainboard cg-board").bounding_box()
                assert bounds is not None
                if width < 800:
                    assert bounds["width"] <= width
                    assert await page.evaluate(
                        "() => parseFloat(getComputedStyle(document.querySelector('.analysis-app')).gridTemplateColumns) <= innerWidth"
                    )
                    assert await page.evaluate(
                        "() => document.documentElement.scrollWidth <= innerWidth"
                    )
                size = 10 if name == "flipello10" else 8
                file = ord(moves[0][2]) - ord("a")
                rank = int(moves[0][3:])
                await page.mouse.click(
                    bounds["x"] + bounds["width"] * (file + 0.5) / size,
                    bounds["y"] + bounds["height"] * (size - rank + 0.5) / size,
                )
                await expect(page.locator("#fullfen")).to_have_value(game.steps[1]["fen"])
                await check_counts(page, game.steps[1]["fen"])
                await page.screenshot(path=f"/tmp/{name}-analysis-{width}-{theme}.png")

                if name != "flipersi":
                    size = 10 if name == "flipello10" else 8
                    rows = ["p" * size] * (size - 2) + [
                        "pp1" + "p" * (size - 3),
                        "Pp1" + "p" * (size - 3),
                    ]
                    game = Game(
                        state, "RevPassT", name, "/".join(rows) + "[Pp] b - - 0 1", *players, base=5
                    )
                    state.games[game.id] = game
                    await insert_game_to_db(game, state)
                    for page in pages:
                        await page.goto(f"{base_url}/{game.id}")
                        await page.wait_for_function(
                            "() => window.cg?.state.movable.dests?.size > 0"
                        )
                    for move in ("b1b1", "P@c1", "d1d1", "a1a1"):
                        await play(move)
                    await self._eventually(lambda: game.result == "0-1")
                    final_fen = game.board.fen
                    state.games.pop(game.id)
                    restored = await load_game(state, game.id)
                    assert restored is not None
                    assert restored.result == "0-1"
                    assert restored.board.fen == final_fen
                    await pages[0].goto(f"{base_url}/{game.id}?ply=4")
                    await expect(pages[0].locator("#fullfen")).to_have_value(final_fen)
                else:
                    rows = ["pppppppp"] * 6 + ["pp1ppppp", "Pp1ppppp"]
                    game = Game(
                        state, "RevStopT", name, "/".join(rows) + "[Pp] w - - 0 1", *players, base=5
                    )
                    state.games[game.id] = game
                    await insert_game_to_db(game, state)
                    for page in pages:
                        await page.goto(f"{base_url}/{game.id}")
                        await page.wait_for_function(
                            "() => window.cg?.state.movable.dests?.size > 0"
                        )
                    await play("P@c1")
                    await self._eventually(lambda: game.result == "0-1")
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant(name)

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_micro_shogi_capture_flips_drops_styles_and_replay(
        self, aiohttp_server, width, theme
    ):
        import base64
        from pathlib import Path

        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("micro", FSF_CATALOGUED_BUILTIN_VARIANTS["micro"])
        register_catalogued_variant_doc(app_state, doc)
        await app_state.db.catalogued_variant.insert_one(doc)
        players = []
        for name in ("micro-white", "micro-black"):
            await app_state.db.user.insert_one(
                {"_id": name, "enabled": True, "ct": "all", "theme": theme}
            )
            player = User(app_state, username=name, theme=theme)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        initial_fen = "kp2/4/2p1/4/2PK[] w - - 0 1"
        game = Game(app_state, "MicroTst", "micro", initial_fen, *players, base=5)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)
        moves = [
            "c1c2",
            "a5a4",
            "c2c3+",
            "a4a5",
            "c3b5-",
            "a5a4",
            "+P@b2",
            "a4a5",
            "P@c2",
            "a5b4",
            "b2c4",
        ]

        async def check_artwork(page, style):
            expected = {}
            kanji = {
                "p": "0FU",
                "pp": "0KE",
                "l": "0KY",
                "pl": "0GI",
                "b": "0KA",
                "pb": "0TO",
                "r": "0HI",
                "pr": "0KI",
            }
            firi = {
                "p": "p",
                "pp": "n",
                "l": "l",
                "pl": "s",
                "b": "b",
                "pb": "pp",
                "r": "r",
                "pr": "g",
                "k": "k",
            }
            orientation = await page.evaluate("() => window.cg.state.orientation")
            for color in ("white", "black"):
                for role in (*kanji, "k"):
                    if style == "kanji":
                        image = kanji.get(role, "0GY" if color == "white" else "0OU")
                        image_path = f"static/images/pieces/shogi/ctk/{image}.svg"
                    elif style == "firi":
                        prefix = "b" if color == "white" else "w"
                        image_path = f"static/images/pieces/firi/{prefix}{firi[role]}.svg"
                    else:
                        side = "ally" if color == orientation else "enemy"
                        image_path = f"static/images/pieces/disguised/shogi-{side}.svg"
                    expected[f"{role}-piece.{color}"] = base64.b64encode(
                        Path(image_path).read_bytes()
                    ).decode()
            missing = await page.evaluate(
                """({expected, orientation}) => {
                    const board = document.querySelector('#mainboard cg-board');
                    return Object.entries(expected).flatMap(([key, artwork]) => {
                        const probe = document.createElement('piece');
                        const [role, color] = key.split('.');
                        probe.className = role + ' ' + color + ' ' + (color === orientation ? 'ally' : 'enemy');
                        board.appendChild(probe);
                        const images = getComputedStyle(probe).backgroundImage + getComputedStyle(probe, '::before').backgroundImage;
                        probe.remove();
                        return images.includes(artwork) ? [] : [key];
                    });
                }""",
                {"expected": expected, "orientation": orientation},
            )
            assert missing == []

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                errors = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await expect(page.locator("#mainboard.shogi4x5.microshogi")).to_be_visible()
                    board = await page.locator("#mainboard cg-board").bounding_box()
                    assert board is not None
                    assert abs(board["height"] / board["width"] - 300 / 208) < 0.01
                    piece = await page.locator("#mainboard piece.k-piece").first.bounding_box()
                    assert piece is not None
                    assert abs(piece["width"] / board["width"] - 0.25) < 0.01
                    assert abs(piece["height"] / board["height"] - 0.2) < 0.01
                    await page.locator("#btn-settings").click()
                    await page.locator("#btn-board").click()
                    await page.select_option("#settings-variant", "micro")
                    for index, style in enumerate(("kanji", "firi", "disguised")):
                        await page.locator(f"label.piece.piece{index}.microshogi").click()
                        await page.wait_for_function(
                            "style => [...document.styleSheets].some(sheet => sheet.href?.includes('/piece-css/microshogi/' + style + '.css'))",
                            arg=style,
                        )
                        await check_artwork(page, style)
                    await page.locator("label.piece.piece0.microshogi").click()
                    await page.locator("#btn-settings").click()
                    pages.append(page)
                await (
                    pages[0]
                    .locator("#mainboard")
                    .screenshot(path=f"/tmp/micro-{width}-{theme}.png")
                )

                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        """move => {
                            if (move.includes('@')) window.cg.selectPocket({role: 'p-piece', color: 'white'});
                            else window.cg.selectSquare(move.slice(0, 2));
                            const dest = move.includes('@') ? move.slice(-2) : move.slice(2, 4);
                            window.cg.selectSquare(dest);
                        }""",
                        move,
                    )
                    if "@" in move:
                        role = "pp-piece" if move.startswith("+") else "p-piece"
                        await page.locator(f"#extension_choice piece.{role}").click()
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                final_fen = game.board.fen
                await game.game_ended(players[0], "resign")
                app_state.games.pop(game.id)
                restored = await load_game(app_state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen

                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply={len(moves)}")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.get_by_title("First move", exact=True).click()
                for ply in range(1, len(moves) + 1):
                    await page.get_by_title("Next move", exact=True).click()
                    await expect(page.locator("#fullfen")).to_have_value(game.steps[ply]["fen"])
                await page.goto(base_url + "/variants/community")
                preview = page.locator('.catalogued-start-board-preview[data-variant="micro"]')
                await preview.scroll_into_view_if_needed()
                await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                mini = await preview.locator("cg-board").bounding_box()
                assert mini is not None
                assert abs(mini["height"] / mini["width"] - 300 / 208) < 0.01
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("micro")

    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_snailtrail_walls_and_saved_analysis(self, aiohttp_server, width, theme):
        import base64
        from pathlib import Path

        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        register_catalogued_variant_doc(
            app_state,
            _build_fsf_builtin_doc("snailtrail", FSF_CATALOGUED_BUILTIN_VARIANTS["snailtrail"]),
        )
        players = []
        for name in ("snail-white", "snail-black"):
            await app_state.db.user.insert_one(
                {"_id": name, "enabled": True, "ct": "all", "theme": theme}
            )
            player = User(app_state, username=name, theme=theme)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        game = Game(app_state, "SnailTst", "snailtrail", "", *players, base=5)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)
        moves = ["a1b2,b2a1", "g7f6,f6g7", "b2c3,c3b2", "f6e5,e5f6", "c3d4,d4c3", "e5e4,e4e5"]

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                errors = []
                for player in players:
                    context, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await context.add_init_script(f"localStorage.setItem('theme', '{theme}');")
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await expect(page.locator("body")).to_have_attribute("data-theme", theme)
                    for color, image_name in (("white", "wK.svg"), ("black", "bK.svg")):
                        artwork = base64.b64encode(
                            Path(f"static/images/pieces/merida/{image_name}").read_bytes()
                        ).decode()
                        assert await page.locator(f"#mainboard piece.p-piece.{color}").evaluate(
                            "(piece, artwork) => getComputedStyle(piece).backgroundImage.includes(artwork)",
                            artwork,
                        )
                    await page.locator("#btn-settings").click()
                    await page.locator("#btn-board").click()
                    await page.select_option("#settings-variant", "snailtrail")
                    for style, index in (("disguised", 1), ("classic", 0), ("disguised", 1)):
                        await page.locator(f"label.piece.piece{index}.snailtrail").click()
                        await expect(page.locator(f"#piece{index}")).to_be_checked()
                        for color, prefix in (("white", "w"), ("black", "b")):
                            image_path = (
                                f"static/images/pieces/disguised/{prefix}.svg"
                                if style == "disguised"
                                else f"static/images/pieces/merida/{prefix}K.svg"
                            )
                            artwork = base64.b64encode(Path(image_path).read_bytes()).decode()
                            await expect(page.locator("#mainboard")).to_have_class(
                                re.compile(rf"\bpiece-style-snailtrail-{style}\b")
                            )
                            await page.wait_for_function(
                                "data => { const piece = document.querySelector(data.selector); "
                                "return piece && getComputedStyle(piece).backgroundImage.includes(data.artwork); }",
                                arg={
                                    "selector": f"#mainboard piece.p-piece.{color}",
                                    "artwork": artwork,
                                },
                                timeout=5000,
                            )
                    await page.locator("#btn-settings").click()
                    pages.append(page)

                served_css = await pages[0].evaluate(
                    "() => [...document.styleSheets].map(sheet => sheet.href).filter(Boolean)"
                )
                assert any("piece-css/snailtrail/classic.css" in href for href in served_css)
                assert any("piece-css/snailtrail/disguised.css" in href for href in served_css)
                assert any("extensions.css" in href for href in served_css)

                assert set(
                    await pages[0].evaluate(
                        "() => window.cg.state.premovable.premoveFunc(window.cg.state.boardState, 'a1', false)"
                    )
                ) == {"b1", "a2", "b2"}
                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        "move => { window.cg.selectSquare(move.slice(0, 2)); window.cg.selectSquare(move.slice(2, 4)); }",
                        move,
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.board.move_stack[-1] == move
                    assert game.board.fen.count("*") == ply + 1
                    await expect(page.locator("#mainboard piece._-piece")).to_have_count(ply + 1)
                    assert await page.locator("#mainboard piece._-piece").first.evaluate(
                        "piece => getComputedStyle(piece).backgroundImage.includes('/images/pieces/brick.svg')"
                    )
                    assert not await page.evaluate(
                        "() => window.cg.state.boardState.pieces.has('a0')"
                    )
                final_fen = game.board.fen
                await game.game_ended(players[0], "resign")
                app_state.games.pop(game.id)
                restored = await load_game(app_state, game.id)
                assert restored is not None
                assert restored.board.fen == final_fen
                assert restored.board.move_stack == moves
                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply={len(moves)}")
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await expect(page.locator("#mainboard piece._-piece")).to_have_count(len(moves))
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#mainboard piece._-piece")).to_have_count(0)
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#mainboard piece._-piece")).to_have_count(len(moves))
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("snailtrail")

    async def test_chessgi_first_rank_pawn_drops_in_analysis(self, aiohttp_server):
        from urllib.parse import urlencode

        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from fairy.fairy_board import sf
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        get_env(app).globals["home"] = f"http://{server.host}:{server.port}"
        register_catalogued_variant_doc(
            app_state,
            _build_fsf_builtin_doc("chessgi", FSF_CATALOGUED_BUILTIN_VARIANTS["chessgi"]),
        )
        initial_fen = "7k/8/8/8/8/8/8/K7[Pp] w - - 0 1"
        moves = ["P@e1", "P@e8", "e1e2", "e8e7"]
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                page = await browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(
                    f"http://{server.host}:{server.port}/analysis/chessgi?"
                    + urlencode({"fen": initial_fen})
                )
                board = page.locator("#mainboard cg-board")
                await expect(board).to_be_visible()

                async def square(key):
                    bounds = await board.bounding_box()
                    assert bounds is not None
                    await page.mouse.click(
                        bounds["x"] + (ord(key[0]) - ord("a") + 0.5) * bounds["width"] / 8,
                        bounds["y"] + (8 - int(key[1]) + 0.5) * bounds["height"] / 8,
                    )

                for ply, move in enumerate(moves):
                    if "@" in move:
                        color = "white" if ply == 0 else "black"
                        await page.locator(f".pocketrow piece.p-piece.{color}").click()
                    else:
                        await square(move[:2])
                    await square(move[2:4])
                    await expect(page.locator("#fullfen")).to_have_value(
                        sf.get_fen("chessgi", initial_fen, moves[: ply + 1])
                    )
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(initial_fen)
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(
                    sf.get_fen("chessgi", initial_fen, moves)
                )
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("chessgi")

    @pytest.mark.parametrize("variant_name", ["loop", "chessgi", "crazyhouse"])
    @pytest.mark.parametrize("promotion", ["q", "n"])
    async def test_loop_promoted_capture_drop_and_replay(
        self, aiohttp_server, variant_name, promotion
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        if variant_name in ("loop", "chessgi"):
            register_catalogued_variant_doc(
                app_state,
                _build_fsf_builtin_doc(variant_name, FSF_CATALOGUED_BUILTIN_VARIANTS[variant_name]),
            )
        players = []
        for name in ("loop-white", "loop-black"):
            await app_state.db.user.insert_one({"_id": name, "enabled": True, "ct": "all"})
            player = User(app_state, username=name)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        initial_fen = "7k/6P1/8/8/8/8/K7/6r1[] w - - 0 1"
        game = Game(app_state, "LoopTest", variant_name, initial_fen, *players, base=5)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)
        pocket_role = "p" if variant_name == "crazyhouse" else promotion
        moves = [f"g7g8{promotion}", "g1g8", "a2a3", f"{pocket_role.upper()}@e5"]

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                errors = []
                for player in players:
                    context, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await context.add_init_script("localStorage.setItem('autoPromote', 'false');")
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    pages.append(page)

                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        """move => {
                            if (move[1] === '@') {
                                window.cg.selectPocket({role: move[0].toLowerCase() + '-piece', color: 'black'});
                            } else window.cg.selectSquare(move.slice(0, 2));
                            window.cg.selectSquare(move.slice(2, 4));
                        }""",
                        move,
                    )
                    if ply == 0:
                        await page.locator(f"#extension_choice piece.{promotion}-piece").click()
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    if ply == 0:
                        assert f"{promotion.upper()}~" in game.board.fen
                    if ply == 1:
                        assert f"[{pocket_role}]" in game.board.fen
                        await pages[1].reload()
                        await pages[1].wait_for_function(
                            "role => window.cg?.state.boardState.pockets?.black.get(role + '-piece') === 1",
                            arg=pocket_role,
                        )
                final_fen = game.board.fen
                assert "[]" in final_fen
                await game.game_ended(players[0], "resign")
                app_state.games.pop(game.id)
                restored = await load_game(app_state, game.id)
                assert restored is not None
                assert restored.board.fen == final_fen
                assert restored.board.move_stack == moves

                page = pages[1]
                await page.goto(f"{base_url}/{game.id}?ply=2")
                await expect(page.locator("main.analysis-app")).to_be_visible()
                await expect(page.locator("#fullfen")).to_have_value(game.steps[2]["fen"])
                await expect(
                    page.locator(f"#pocket1 piece.{pocket_role}-piece.black")
                ).to_be_visible()
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(initial_fen)
                assert errors == []
            finally:
                await browser.close()
                if variant_name in ("loop", "chessgi"):
                    unregister_catalogued_server_variant(variant_name)

    @pytest.mark.parametrize("capture_centre", [False, True])
    @pytest.mark.parametrize(
        "width,theme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")]
    )
    async def test_jesonmor_centre_win_and_saved_analysis(
        self, aiohttp_server, capture_centre, width, theme
    ):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from const import STARTED, VARIANTEND
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        doc = _build_fsf_builtin_doc("jesonmor", FSF_CATALOGUED_BUILTIN_VARIANTS["jesonmor"])
        register_catalogued_variant_doc(app_state, doc)
        await app_state.db.catalogued_variant.insert_one(doc)
        players = []
        for name in ("jeson-white", "jeson-black"):
            await app_state.db.user.insert_one(
                {"_id": name, "enabled": True, "ct": "all", "theme": theme}
            )
            player = User(app_state, username=name, theme=theme)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        game = Game(app_state, "JesonMor", "jesonmor", "", *players, base=5)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)
        moves = ["e1d3", "e9d7", "d3e5"]
        moves += ["d7e5", "h1f2"] if capture_centre else ["d7e9"]

        async def centre_mark(board):
            mark = await board.evaluate("""el => {
                const bounds = el.getBoundingClientRect();
                const style = getComputedStyle(el, '::before');
                return {content: style.content, width: parseFloat(style.width),
                    height: parseFloat(style.height), left: parseFloat(style.left),
                    top: parseFloat(style.top), pointer: style.pointerEvents,
                    shadow: style.boxShadow, boardWidth: bounds.width, boardHeight: bounds.height};
            }""")
            assert mark["content"] == '""'
            assert abs(mark["width"] - mark["boardWidth"] / 9) < 1
            assert abs(mark["height"] - mark["boardHeight"] / 9) < 1
            assert abs(mark["left"] - mark["boardWidth"] * 4 / 9) < 1
            assert abs(mark["top"] - mark["boardHeight"] * 4 / 9) < 1
            assert mark["pointer"] == "none"
            assert mark["shadow"] != "none"

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                errors = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.set_viewport_size({"width": width, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await expect(
                        page.locator("#mainboard.standard9x9.standard.jesonmor")
                    ).to_be_visible()
                    await expect(page.locator("#mainboard cg-board piece.n-piece")).to_have_count(
                        18
                    )
                    assert await page.locator("#mainboard piece.n-piece").first.evaluate(
                        "piece => getComputedStyle(piece).backgroundImage !== 'none'"
                    )
                    await centre_mark(page.locator("#mainboard cg-board"))
                    pages.append(page)

                await pages[0].keyboard.press("f")
                await centre_mark(pages[0].locator("#mainboard cg-board"))
                await pages[0].keyboard.press("f")

                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    if move.endswith("e5"):
                        await page.evaluate("key => window.cg.selectSquare(key)", move[:2])
                        board = page.locator("#mainboard cg-board")
                        await board.scroll_into_view_if_needed()
                        bounds = await board.bounding_box()
                        assert bounds is not None
                        await page.mouse.click(
                            bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
                        )
                    else:
                        await page.evaluate(
                            "move => { window.cg.selectSquare(move.slice(0, 2)); window.cg.selectSquare(move.slice(2, 4)); }",
                            move,
                        )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    if ply < len(moves) - 1:
                        assert game.status == STARTED
                await self._eventually_async(
                    lambda: app_state.db.game.find_one({"_id": game.id, "s": VARIANTEND})
                )
                assert game.status == VARIANTEND
                assert game.result == ("0-1" if capture_centre else "1-0")
                final_fen = game.board.fen
                app_state.games.pop(game.id)
                restored = await load_game(app_state, game.id)
                assert restored is not None
                assert restored.board.move_stack == moves
                assert restored.board.fen == final_fen
                assert restored.result == game.result
                assert restored.status == VARIANTEND

                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply={len(moves)}")
                await expect(page.locator("main.analysis-app")).to_be_visible()
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await centre_mark(page.locator("#mainboard cg-board"))
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(game.initial_fen)
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await page.goto(f"{base_url}/analysis/jesonmor")
                await expect(
                    page.locator("#mainboard.standard9x9.standard.jesonmor")
                ).to_be_visible()
                await expect(page.locator("#mainboard cg-board piece.n-piece")).to_have_count(18)
                await centre_mark(page.locator("#mainboard cg-board"))
                await page.locator("#mainboard").screenshot(
                    path=f"/tmp/jesonmor-mark-{width}-{theme}-{capture_centre}.png"
                )
                await page.goto(base_url + "/variants/community")
                preview = page.locator('.catalogued-start-board-preview[data-variant="jesonmor"]')
                await preview.scroll_into_view_if_needed()
                await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                await centre_mark(preview.locator("cg-board"))
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("jesonmor")

    async def test_euroshogi_play_promote_drop_and_saved_analysis(self, aiohttp_server):
        from aiohttp_jinja2 import get_env
        from catalogued.builtin_data import FSF_CATALOGUED_BUILTIN_VARIANTS
        from catalogued.documents import _build_fsf_builtin_doc
        from catalogued.variants import register_catalogued_variant_doc
        from utils import load_game
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        get_env(app).globals["home"] = base_url
        register_catalogued_variant_doc(
            app_state,
            _build_fsf_builtin_doc("euroshogi", FSF_CATALOGUED_BUILTIN_VARIANTS["euroshogi"]),
        )
        players = []
        for name in ("euro-white", "euro-black"):
            await app_state.db.user.insert_one({"_id": name, "enabled": True, "ct": "all"})
            player = User(app_state, username=name)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        initial_fen = "7k/8/8/P7/3N4/8/8/K7[B] w 0 1"
        game = Game(app_state, "EuroTest", "euroshogi", initial_fen, *players, base=5)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                errors = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await expect(page.locator("#mainboard.standard8x8.shogi")).to_be_visible()
                    pages.append(page)

                # The sideways step is unique to EuroShogi's knight.
                assert set(
                    await pages[0].evaluate(
                        "() => window.cg.state.premovable.premoveFunc("
                        "window.cg.state.boardState, 'd4', false)"
                    )
                ) == {"c4", "e4", "c6", "e6"}
                moves = ("d4e4", "h8g8", "a5a6+", "g8h8", "B@d5")
                for ply, move in enumerate(moves):
                    page = pages[game.board.color]
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    await page.evaluate(
                        """move => {
                            if (move[1] === '@') {
                                window.cg.selectPocket({ role: 'b-piece', color: 'white' });
                            } else window.cg.selectSquare(move.slice(0, 2));
                            window.cg.selectSquare(move.slice(2, 4));
                        }""",
                        move,
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                assert "+P" in game.board.fen
                assert game.board.move_stack == list(moves)
                assert await pages[0].locator("#extension_choice").count() == 0
                await game.game_ended(players[0], "resign")
                final_fen = game.board.fen
                app_state.games.pop(game.id)
                restored = await load_game(app_state, game.id)
                assert restored is not None
                assert restored.board.fen == final_fen
                assert restored.board.move_stack == list(moves)

                page = pages[0]
                await page.goto(f"{base_url}/{game.id}?ply=5")
                await expect(page.locator("main.analysis-app")).to_be_visible()
                await page.get_by_title("Last move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(final_fen)
                await expect(page.locator("#mainboard piece.pp-piece")).to_be_visible()
                assert await page.locator("#mainboard piece.pp-piece").evaluate(
                    "piece => getComputedStyle(piece, '::before').backgroundImage !== 'none'"
                    " || getComputedStyle(piece).backgroundImage !== 'none'"
                )
                await page.get_by_title("First move", exact=True).click()
                await expect(page.locator("#fullfen")).to_have_value(initial_fen)
                await page.goto(f"{base_url}/analysis/euroshogi")
                await expect(page.locator("#mainboard.standard8x8.shogi")).to_be_visible()
                await expect(page.locator("#mainboard cg-board piece")).to_have_count(32)
                assert errors == []
            finally:
                await browser.close()
                unregister_catalogued_server_variant("euroshogi")

    async def test_catalogued_loading_for_previews_editor_and_simul(self, aiohttp_server):
        from catalogued.variants import register_catalogued_variant_doc
        from fairy import FairyBoard
        from simul.simul import Simul
        from variants import unregister_catalogued_server_variant

        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        parent, child = "loading-parent", "loading-child"
        fen = FairyBoard.start_fen("chess")
        for name, base, rule in (
            (parent, "chess", "doubleStep = false"),
            (child, parent, "stalemateValue = draw"),
        ):
            doc = {
                "_id": name,
                "name": name,
                "displayName": name,
                "ini": f"[{name}:{base}]\n{rule}\n",
                "baseVariant": base,
                "startFen": fen,
                "width": 8,
                "height": 8,
                "pieces": ["p", "n", "b", "r", "q", "k"],
                "visibility": "public",
                "updatedAt": datetime.now(UTC),
            }
            register_catalogued_variant_doc(app_state, doc)
            await app_state.db.catalogued_variant.insert_one(doc)

        host = User(app_state, username="LoadingHost")
        players = [User(app_state, username=f"LoadingPlayer{i}") for i in range(2)]
        for user in [host, *players]:
            app_state.users[user.username] = user
            await app_state.db.user.insert_one({"_id": user.username, "enabled": True})
        simul = await Simul.create(
            app_state,
            "loadsimu",
            name="Loading Simul",
            created_by=host.username,
            variants=["chess", child],
            base=30,
        )
        app_state.simuls[simul.id] = simul
        for player, variant in zip(players, ["chess", child]):
            assert simul.join(player, variant)
            assert simul.approve(player.username)
        assert await simul.start()
        chess_game = next(game for game in simul.games.values() if game.variant == "chess")
        base_url = f"http://{server.host}:{server.port}"

        try:
            async with async_playwright() as playwright:
                browser = await self._launch_browser(playwright)
                try:
                    anon = await browser.new_page()
                    await anon.goto(base_url + "/variants/community")
                    preview = anon.locator(
                        f'.catalogued-start-board-preview[data-variant="{child}"]'
                    )
                    await preview.scroll_into_view_if_needed()
                    await expect(preview).to_have_attribute("data-chessground-mounted", "true")
                    await expect(preview.locator(".cg-wrap cg-board")).to_be_visible()
                    await anon.close()

                    context, page = await self._playwright_page_for_user(
                        browser, base_url, host.username
                    )
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    for path in (f"/seek/{child}", f"/@/Fairy-Stockfish/play/{child}"):
                        await page.goto(base_url + path + "?fen=" + fen)
                        await expect(page.locator("main.lobby")).to_be_visible()
                        await expect(page.locator("#variant")).to_have_value(child)
                        payload = json.loads(
                            await page.locator("body").get_attribute("data-catalogued-variants")
                        )
                        assert [doc["name"] for doc in payload] == [parent, child]

                    await page.goto(base_url + "/analysis/" + child)
                    await expect(page.locator(".cg-wrap cg-board").first).to_be_visible()
                    await page.goto(base_url + "/" + chess_game.id)
                    await expect(
                        page.locator(".ongoing-games-container .cg-wrap cg-board")
                    ).to_be_visible()
                    assert await page.locator(".ongoing-game-error").count() == 0
                    assert errors == []
                    await context.close()
                finally:
                    await browser.close()
        finally:
            for name in (child, parent):
                unregister_catalogued_server_variant(name)

    async def _launch_browser(self, playwright):
        try:
            return await playwright.chromium.launch(headless=True)
        except PlaywrightError as err:
            # Local dev fallback: Playwright currently has no bundled Chromium for ubuntu26.04.
            if "Executable doesn't exist" not in str(err):
                raise
            system_chromium = shutil.which("chromium-browser") or shutil.which("chromium")
            if not system_chromium:
                raise
            return await playwright.chromium.launch(headless=True, executable_path=system_chromium)

    async def _playwright_page_for_user(self, browser, base_url: str, username: str):
        context = await browser.new_context()
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        await context.add_cookies(
            [{"name": "AIOHTTP_SESSION", "value": json.dumps(session_data), "url": base_url}]
        )
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        return context, page

    async def _eventually(self, predicate, timeout: float = 10.0, interval: float = 0.1):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = predicate()
            if result:
                return result
            await asyncio.sleep(interval)
        raise AssertionError("Timed out waiting for condition")

    async def _eventually_async(self, predicate, timeout: float = 10.0, interval: float = 0.1):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = await predicate()
            if result:
                return result
            await asyncio.sleep(interval)
        raise AssertionError("Timed out waiting for condition")

    async def _open_rr_arrangement(self, page, white: str, black: str):
        modal = page.locator("#rr-modal .rr-arr-modal")
        if await modal.count() > 0 and await modal.first.is_visible():
            return
        await page.locator(f'td[title="{white} vs {black}"]').first.click()
        await expect(page.locator("#rr-modal .rr-arr-modal")).to_be_visible()

    async def _suggest_rr_time(self, page, white: str, black: str, when_local: datetime):
        await self._open_rr_arrangement(page, white, black)
        await page.locator("#rr-modal .rr-arr-user-bottom .flatpickr-input-wrap").click()
        day = page.locator(
            "#rr-modal .rr-arr-user-bottom .flatpickr-day.today:not(.flatpickr-disabled)"
        ).first
        if await day.count() == 0:
            day = page.locator(
                "#rr-modal .rr-arr-user-bottom .flatpickr-day.selected:not(.flatpickr-disabled)"
            ).first
        if await day.count() == 0:
            day = page.locator(
                "#rr-modal .rr-arr-user-bottom .flatpickr-day:not(.prevMonthDay):not(.nextMonthDay):not(.flatpickr-disabled)"
            ).first
        await day.click()
        await page.locator("#rr-modal .rr-arr-user-bottom .flatpickr-hour").fill(
            f"{when_local.hour:02d}"
        )
        await page.locator("#rr-modal .rr-arr-user-bottom .flatpickr-minute").fill(
            f"{when_local.minute:02d}"
        )
        await page.get_by_role("button", name="Confirm").click()

    async def _accept_rr_time(self, page, white: str, black: str):
        await self._open_rr_arrangement(page, white, black)
        await page.locator("#rr-modal .rr-arr-user-top .fbt").click()

    async def _create_rr_challenge(self, page, white: str, black: str):
        await self._open_rr_arrangement(page, white, black)
        await page.get_by_role("button", name="Create challenge").click()

    async def _accept_rr_challenge(self, page, white: str, black: str):
        await self._open_rr_arrangement(page, white, black)
        await page.get_by_role("button", name="Accept challenge").click()

    async def test_main_page_buttons(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        server = await aiohttp_server(app)

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"http://{server.host}:{server.port}/")

            await page.wait_for_selector("main.lobby", state="visible")

            # Test "Play with AI" button
            await page.locator(".seekbuttons >> text=Play with AI").click()
            dialog = page.locator("dialog.modal")
            await expect(dialog).to_be_visible()
            await expect(dialog).to_contain_text("Play with AI")
            await page.keyboard.press("Escape")

            # Test "Play with a friend" button
            await page.locator(".seekbuttons >> text=Play with a friend").click()
            dialog = page.locator("dialog.modal")
            await expect(dialog).to_be_visible()
            await expect(dialog).to_contain_text("Play with a friend")
            await page.keyboard.press("Escape")

            # Test "Create a game" button
            await page.locator(".seekbuttons >> text=Create a game").click()
            dialog = page.locator("dialog.modal")
            await expect(dialog).to_be_visible()
            await expect(dialog).to_contain_text("Create a game")
            await page.keyboard.press("Escape")

            await browser.close()

    async def test_correspondence_notification_settings(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        username = "notification-settings-user"
        await app_state.db.user.insert_one(
            {"_id": username, "enabled": True, "ct": "all", "cps": False}
        )
        base_url = f"http://{server.host}:{server.port}"

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                context, page = await self._playwright_page_for_user(browser, base_url, username)
                await context.grant_permissions(["notifications"])
                other_page = await context.new_page()
                for tab in (page, other_page):
                    await tab.goto(base_url)
                    await tab.locator("#btn-settings").click()
                    await tab.locator("#btn-notifications").click()
                browser_toggle = page.locator("#corr-browser-enabled")
                await expect(browser_toggle).to_be_checked()
                await expect(page.locator("#corr-push-enabled")).not_to_be_checked()

                async with page.expect_response("**/pref/corr-browser") as saved:
                    await browser_toggle.uncheck()
                assert (await saved.value).status == 204
                await expect(browser_toggle).to_be_enabled()
                await expect(other_page.locator("#corr-browser-enabled")).not_to_be_checked()
                stored = await app_state.db.user.find_one({"_id": username})
                assert stored["cbs"] is False
                assert stored["cps"] is False

                await page.reload()
                await page.locator("#btn-settings").click()
                await page.locator("#btn-notifications").click()
                await expect(browser_toggle).not_to_be_checked()
                async with page.expect_response("**/pref/corr-browser") as saved:
                    await browser_toggle.check()
                assert (await saved.value).status == 204
                await expect(other_page.locator("#corr-browser-enabled")).to_be_checked()

                await page.locator("#settings-notifications .back").click()
                await page.locator("#btn-privacy").click()
                await expect(page.locator("#settings-privacy input")).to_have_count(1)
                await expect(page.get_by_label("Only friends can message me")).to_be_visible()
            finally:
                await browser.close()

    @pytest.mark.parametrize("periods", [1, 3])
    async def test_zero_main_time_byoyomi_resets_after_moves_and_refresh(
        self, aiohttp_server, periods
    ):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        players = []
        for name in ("byoyomi-white", "byoyomi-black"):
            await app_state.db.user.insert_one({"_id": name, "enabled": True, "ct": "all"})
            player = User(app_state, username=name)
            app_state.users[name] = player
            players.append(player)
        game = Game(
            app_state,
            "ByoTest1",
            "torishogi",
            "",
            *players,
            base=0,
            inc=60,
            byoyomi_period=periods,
        )
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_selector("#mainboard cg-board")
                    pages.append(page)
                for ply in range(4):
                    page = pages[game.board.color]
                    if ply == 2:
                        await page.reload()
                    await page.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                    if ply >= 2:
                        await asyncio.sleep(0.2)
                    move = next(
                        move
                        for move in game.board.legal_moves()
                        if len(move) == 4 and "@" not in move
                    )
                    await page.evaluate(
                        "move => { window.cg.selectSquare(move.slice(0, 2)); "
                        "window.cg.selectSquare(move.slice(2, 4)); }",
                        move,
                    )
                    await self._eventually(lambda expected=ply + 1: game.board.ply == expected)
                    assert game.clocks == (60000, 60000)
                assert game.byoyomi_periods == [periods - 1, periods - 1]
            finally:
                await browser.close()

    @pytest.mark.parametrize("giver_color", [0, 1])
    async def test_moretime_survives_next_move_and_refresh(self, aiohttp_server, giver_color):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        base_url = f"http://{server.host}:{server.port}"
        players = []
        for name in ("moretime-white", "moretime-black"):
            await app_state.db.user.insert_one({"_id": name, "enabled": True, "ct": "all"})
            player = User(app_state, username=name)
            player.game_category_set = True
            app_state.users[name] = player
            players.append(player)
        game = Game(app_state, "MoreTime", "chess", "", *players, base=5, inc=0)
        app_state.games[game.id] = game
        await insert_game_to_db(game, app_state)
        await game.play_move("e2e4")
        await game.play_move("e7e5")
        if giver_color == 1:
            await game.play_move("g1f3")
        recipient_color = 1 - giver_color

        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                pages = []
                for player in players:
                    _, page = await self._playwright_page_for_user(
                        browser, base_url, player.username
                    )
                    await page.goto(f"{base_url}/{game.id}")
                    await page.wait_for_selector("#mainboard cg-board")
                    pages.append(page)
                giver = pages[giver_color]
                recipient = pages[recipient_color]
                await giver.wait_for_function("() => window.cg?.state.movable.dests?.size > 0")
                await giver.get_by_title("Give 15 seconds", exact=True).click()
                await expect(giver.locator("#clock0 .sec")).to_have_text("15")
                await expect(recipient.locator("#clock1 .sec")).to_have_text("15")

                ply = game.board.ply
                move = "g1f3" if giver_color == 0 else "g8f6"
                await giver.evaluate(
                    "move => { window.cg.selectSquare(move.slice(0, 2)); "
                    "window.cg.selectSquare(move.slice(2, 4)); }",
                    move,
                )
                await self._eventually(lambda: game.board.ply == ply + 1)
                await expect(recipient.locator("#clock1 .clock.running")).to_be_visible()
                assert game.clocks[recipient_color] == 315000
                await expect(recipient.locator("#clock1 .min")).to_have_text("05")
                await expect(recipient.locator("#clock1 .sec")).to_have_text(re.compile(r"1[0-5]"))

                await recipient.reload()
                await expect(recipient.locator("#clock1 .sec")).to_have_text(re.compile(r"1[0-5]"))
                # Give time again while the opponent's clock is running.
                # The recipient can flip the board without changing who gets the gift.
                await recipient.keyboard.press("f")
                await expect(recipient.locator("#clock0 .clock.running")).to_be_visible()
                await giver.get_by_title("Give 15 seconds", exact=True).click()
                await self._eventually(lambda: game.clocks[recipient_color] == 330000)
                await expect(recipient.locator("#clock0 .sec")).to_have_text(
                    re.compile(r"[23][0-9]")
                )
                await recipient.reload()
                await expect(recipient.locator("#clock1 .sec")).to_have_text(
                    re.compile(r"[23][0-9]")
                )
            finally:
                await browser.close()

    async def test_casual_only_variant_disables_rating_controls(self, aiohttp_server):
        username = "casual_only_host"
        with patch("settings.TOURNAMENT_DIRECTORS", [username]):
            app = make_app(
                db_client=AsyncMongoMockClient(tz_aware=True),
                simple_cookie_storage=True,
            )
            server = await aiohttp_server(app, host="127.0.0.1")
            app_state = get_app_state(app)
            base_url = f"http://{server.host}:{server.port}"
            await app_state.db.user.insert_one(
                {
                    "_id": username,
                    "enabled": True,
                    "createdAt": datetime.now(UTC) - timedelta(days=30),
                    "lang": "en",
                    "theme": "dark",
                    "ct": "all",
                    "perfs": {},
                    "pperfs": {},
                }
            )

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context, page = await self._playwright_page_for_user(browser, base_url, username)
                try:
                    await page.goto(base_url)
                    await page.get_by_role("button", name="Create a game").click()
                    await page.select_option("#variant", "cwda")
                    await expect(page.locator("#rated")).to_be_disabled()
                    await expect(page.locator("#casual")).to_be_checked()

                    await page.goto(f"{base_url}/tournaments/new")
                    await page.select_option("#form3-variant", "cwda")
                    await expect(page.locator("#form3-rated")).to_be_disabled()
                    await expect(page.locator("#form3-entryMinRatedGames")).to_be_disabled()
                    await expect(page.locator("#form3-entryMinRating")).to_be_disabled()
                    await expect(page.locator("#form3-entryMaxRating")).to_be_disabled()
                finally:
                    await context.close()
                    await browser.close()

    async def test_round_robin_full_browser_flow(self, aiohttp_server):
        with patch("settings.TOURNAMENT_DIRECTORS", ["rr_host"]):
            app = make_app(
                db_client=AsyncMongoMockClient(tz_aware=True),
                simple_cookie_storage=True,
            )
            server = await aiohttp_server(app, host="127.0.0.1")
            app_state = get_app_state(app)
            base_url = f"http://{server.host}:{server.port}"

            usernames = ["rr_host", "rr_player2", "rr_player3"]
            created_at = datetime.now(UTC) - timedelta(days=30)
            for username in usernames:
                await app_state.db.user.insert_one(
                    {
                        "_id": username,
                        "enabled": True,
                        "createdAt": created_at,
                        "lang": "en",
                        "theme": "dark",
                        "ct": "all",
                        "perfs": {},
                        "pperfs": {},
                    }
                )

            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                contexts = []
                try:
                    pages = {}
                    for username in usernames:
                        context, page = await self._playwright_page_for_user(
                            browser, base_url, username
                        )
                        contexts.append(context)
                        pages[username] = page

                    host_page = pages["rr_host"]
                    tournament_name = f"RR Browser Flow {int(time.time())}"
                    await host_page.goto(f"{base_url}/tournaments/new")
                    await host_page.wait_for_selector("#tournament-form", state="visible")
                    await host_page.fill("#form3-name", tournament_name)
                    await host_page.select_option("#form3-system", "1")
                    await host_page.select_option("#form3-rrMaxPlayers", "3")
                    await host_page.select_option("#form3-clockTime", "1.0")
                    await host_page.select_option("#form3-clockIncrement", "0")
                    await host_page.select_option("#form3-minutes", "20")
                    await host_page.select_option("#form3-waitMinutes", "1")
                    await host_page.get_by_role("button", name="Create a new tournament").click()
                    await expect(host_page).to_have_url(re.compile(r".*/tournaments$"))

                    tournament_doc = await self._eventually_async(
                        lambda: app_state.db.tournament.find_one({"name": tournament_name}),
                        timeout=10.0,
                    )
                    tournament_id = tournament_doc["_id"]
                    tournament_url = f"{base_url}/tournament/{tournament_id}"

                    for username in usernames:
                        page = pages[username]
                        await page.goto(tournament_url)
                        await page.wait_for_selector("#action", state="visible")
                        await page.locator("#action").click()

                    tournament = app_state.tournaments[tournament_id]
                    await self._eventually(lambda: tournament.nb_players == 3, timeout=10.0)

                    await tournament.start(datetime.now(UTC))
                    await self._eventually(lambda: tournament.status != 0, timeout=5.0)

                    for username in usernames:
                        await pages[username].goto(tournament_url)
                        await pages[username].wait_for_selector("#rr-crosstable", state="visible")

                    pairings = tournament.arrangement_list()
                    assert len(pairings) == 3

                    scheduled_at_local = datetime.now().astimezone() + timedelta(hours=2)
                    scheduled_at_local = scheduled_at_local.replace(second=0, microsecond=0)

                    for arrangement in pairings:
                        challenger_page = pages[arrangement.white]
                        opponent_page = pages[arrangement.black]

                        await self._suggest_rr_time(
                            challenger_page,
                            arrangement.white,
                            arrangement.black,
                            scheduled_at_local,
                        )
                        await self._eventually(
                            lambda arr=arrangement: arr.white_date is not None,
                            timeout=5.0,
                        )
                        await self._accept_rr_time(
                            opponent_page, arrangement.white, arrangement.black
                        )
                        await self._eventually(
                            lambda arr=arrangement: arr.scheduled_at is not None,
                            timeout=5.0,
                        )

                        await self._create_rr_challenge(
                            challenger_page, arrangement.white, arrangement.black
                        )
                        await self._eventually(
                            lambda arr=arrangement: arr.status == "challenged",
                            timeout=5.0,
                        )
                        await self._accept_rr_challenge(
                            opponent_page, arrangement.white, arrangement.black
                        )
                        await self._eventually(
                            lambda arr=arrangement: bool(arr.game_id),
                            timeout=5.0,
                        )
                        game_id = arrangement.game_id
                        assert game_id is not None

                        white_page = pages[arrangement.white]
                        black_page = pages[arrangement.black]
                        await expect(white_page).to_have_url(
                            re.compile(rf"{re.escape(base_url)}/{game_id}$")
                        )
                        await expect(black_page).to_have_url(
                            re.compile(rf"{re.escape(base_url)}/{game_id}$")
                        )
                        await expect(white_page.locator("cg-board")).to_be_visible()
                        await expect(black_page.locator("cg-board")).to_be_visible()

                        game = app_state.games[game_id]
                        await white_page.locator("button#draw").click()
                        await expect(
                            white_page.locator("#confirm-dialog .confirm-dialog-confirm")
                        ).to_be_visible()
                        await white_page.locator("#confirm-dialog .confirm-dialog-confirm").click()
                        await expect(black_page.locator("#offer-dialog .accept")).to_be_visible()
                        await black_page.locator("#offer-dialog .accept").click()
                        await expect(
                            black_page.locator("#confirm-dialog .confirm-dialog-confirm")
                        ).to_be_visible()
                        await black_page.locator("#confirm-dialog .confirm-dialog-confirm").click()
                        await self._eventually(
                            lambda g=game: g.result == "1/2-1/2",
                            timeout=5.0,
                        )
                        await self._eventually(
                            lambda arr=arrangement: arr.status == "finished",
                            timeout=5.0,
                        )

                        await white_page.goto(tournament_url)
                        await black_page.goto(tournament_url)
                        await white_page.wait_for_selector("#rr-crosstable", state="visible")
                        await black_page.wait_for_selector("#rr-crosstable", state="visible")

                    await self._eventually(
                        lambda: tournament.status == T_FINISHED,
                        timeout=10.0,
                    )

                    await host_page.goto(tournament_url)
                    await host_page.wait_for_selector("#rr-crosstable", state="visible")
                    assert sorted(
                        tournament.leaderboard_score_by_username(username) // SCORE_SHIFT
                        for username in usernames
                    ) == [2, 2, 2]
                    assert (
                        await host_page.locator(
                            "#rr-crosstable .r-table-wrap-scores tbody tr"
                        ).count()
                        == 3
                    )
                    assert await host_page.locator("#rr-crosstable td.rr-cell.draw").count() == 6
                finally:
                    for context in contexts:
                        await context.close()
                    await browser.close()

    async def test_editor_play_with_machine(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        # When tests has redirects port have to be fixed
        # By default aiohttp_server fixture randomize the port
        server = await aiohttp_server(app, host="127.0.0.1", port=8080)

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"http://{server.host}:{server.port}/editor/chess")

            await page.wait_for_selector(".editor-app", state="visible")

            await page.locator("#challengeAI").click()

            AI_URL_RE = re.compile(
                r"http://127\.0\.0\.1:8080/@/Fairy-Stockfish/play/[^/?]+\?fen=.*"
            )
            await page.wait_for_url(AI_URL_RE)

            dialog = page.locator("dialog.modal")
            await expect(dialog).to_be_visible()
            await expect(dialog).to_contain_text("Challenge Fairy-Stockfish to a game")

            await browser.close()

    async def test_editor_continue_from_here(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        # When tests has redirects port have to be fixed
        # By default aiohttp_server fixture randomize the port
        server = await aiohttp_server(app, host="127.0.0.1", port=8080)

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"http://{server.host}:{server.port}/editor/chess")

            await page.wait_for_selector(".editor-app", state="visible")

            await page.locator("#createseek").click()

            SEEK_URL_RE = re.compile(r"http://127\.0\.0\.1:8080/seek/[^/?]+\?fen=.*")
            await page.wait_for_url(SEEK_URL_RE)

            dialog = page.locator("dialog.modal")
            await expect(dialog).to_be_visible()
            await expect(dialog).to_contain_text("Create a game")

            await browser.close()
