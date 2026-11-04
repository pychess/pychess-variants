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
