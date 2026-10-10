import asyncio
import json
import re
import shutil
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import test_logger
from fairy import FairyBoard
from mongomock_motor import AsyncMongoMockClient
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright, expect
from pychess_global_app_state_utils import get_app_state
from study.builder import StudyChapterBuilder
from study.models import STUDY_CHAPTER_MODES
from study.storage import (
    add_chapter_from_draft,
    create_study_from_draft,
    load_owned_chapter,
    load_owned_study,
    load_study,
)
from study.tree import StudyTree

from server import make_app

test_logger.init_test_logger()


@pytest.mark.asyncio
class TestStudyGUI:
    @pytest.fixture(autouse=True)
    def _enable_all_study_modes(self):
        with patch("study.models.STUDY_ENABLED_CHAPTER_MODES", STUDY_CHAPTER_MODES):
            yield

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

    async def _page_for_user(self, browser, base_url: str, username: str):
        context = await browser.new_context()
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        await context.add_cookies(
            [{"name": "AIOHTTP_SESSION", "value": json.dumps(session_data), "url": base_url}]
        )
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        return context, page

    async def _insert_user(self, app_state, username: str):
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

    @staticmethod
    def _study_ids_from_url(url: str) -> tuple[str, str]:
        match = re.search(r"/study/(\w{8})/(\w{8})$", url)
        assert match is not None, url
        return match.group(1), match.group(2)

    async def _play_board_move(self, page, source: str, target: str):
        board = page.locator("#mainboard cg-board")
        await expect(board).to_be_visible()
        box = await board.bounding_box()
        assert box is not None

        def position(square: str):
            file_index = ord(square[0]) - ord("a")
            rank = int(square[1:])
            return {
                "x": (file_index + 0.5) * box["width"] / 8,
                "y": (8 - rank + 0.5) * box["height"] / 8,
            }

        await board.click(position=position(source))
        await board.click(position=position(target))

    async def _study_node_count(self, app_state, chapter_id: str) -> int:
        doc = await app_state.db.study_chapter.find_one({"_id": chapter_id})
        assert doc is not None
        return sum(1 for node_id in doc["root"] if node_id != "_")

    async def _study_has_node_count(self, app_state, chapter_id: str, expected: int) -> bool:
        return await self._study_node_count(app_state, chapter_id) == expected

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

    @staticmethod
    async def _equals_async(getter, expected):
        return await getter() == expected

    async def _create_conceal_acceptance_study(
        self, app_state, owner: str, writer: str, reader: str
    ):
        def normalized_line(node_ids: tuple[str, ...], moves: tuple[str, ...]):
            board = FairyBoard("chess")
            nodes = []
            parent_id = None
            for node_id, move in zip(node_ids, moves, strict=True):
                san = board.get_san(move)
                board.push(move)
                fields = board.fen.split()
                nodes.append(
                    {
                        "id": node_id,
                        "parentId": parent_id,
                        "order": 0,
                        "move": move,
                        "fen": board.fen,
                        "turnColor": "white" if fields[1] == "w" else "black",
                        "check": board.is_checked(),
                        "san": san,
                    }
                )
                parent_id = node_id
            return nodes

        builder = StudyChapterBuilder(app_state, owner)
        initial_fen = FairyBoard.start_fen("chess")
        first = await builder.from_analysis(
            variant="chess",
            initial_fen=initial_fen,
            mode="conceal",
            conceal_ply=0,
            name="Hidden line",
            tree_payload={
                "nodes": normalized_line(
                    ("Node000001", "Node000002", "Node000003"),
                    ("e2e4", "e7e5", "g1f3"),
                )
            },
        )
        study, chapter = await create_study_from_draft(
            app_state, owner, first, name="Conceal acceptance", visibility="public"
        )
        second = await builder.from_analysis(
            variant="chess",
            initial_fen=initial_fen,
            mode="conceal",
            conceal_ply=0,
            name="Second hidden line",
            tree_payload={
                "nodes": normalized_line(
                    ("Node001001", "Node001002"),
                    ("c2c4", "e7e5"),
                )
            },
        )
        second_chapter = await add_chapter_from_draft(
            app_state, study, second, activate_shared=False
        )
        current = await load_study(app_state, study.id)
        assert current is not None
        current = replace(
            current,
            visibility="public",
            members={owner: "write", writer: "write", reader: "read"},
        )
        await app_state.db.study.replace_one({"_id": study.id}, current.to_document())
        return current, chapter, second_chapter

    async def test_persistence_chapters_and_fresh_app_state(self, aiohttp_server):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client, simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        username = "study_owner"
        await self._insert_user(app_state, username)
        base_url = f"http://{server.host}:{server.port}"

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context, page = await self._page_for_user(browser, base_url, username)
            try:
                await page.goto(f"{base_url}/study")
                await page.locator("[data-study-new-open]").click()
                await page.locator('#study-new-dialog input[name="name"]').fill("Acceptance Study")
                await page.locator('#study-new-dialog button[type="submit"]').click()
                await expect(page.locator("#study-first-chapter-dialog")).to_be_visible()
                await page.locator('#study-first-chapter-form button[type="submit"]').click()
                await page.wait_for_url(
                    re.compile(rf"{re.escape(base_url)}/study/\w{{8}}/\w{{8}}$")
                )
                study_id, first_chapter_id = self._study_ids_from_url(page.url)
                await self._eventually(
                    lambda: len(app_state.study_sockets.get(study_id, set())) == 1
                )

                # Main line: 1.e4 e5. Then make 1...c5 with a nested 2.Nf3/d4 fork.
                await self._play_board_move(page, "e2", "e4")
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, first_chapter_id, 1)
                )
                await self._play_board_move(page, "e7", "e5")
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, first_chapter_id, 2)
                )
                await page.locator("#movelist move.mainline").first.click()
                await self._play_board_move(page, "c7", "c5")
                await self._play_board_move(page, "g1", "f3")
                await page.locator("#movelist move", has_text="c5").click()
                await self._play_board_move(page, "d2", "d4")
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, first_chapter_id, 5)
                )

                # Promote the Sicilian branch to the preferred line, then delete its
                # nested 2.d4 variation through the real movelist context menu.
                c5 = page.locator("#movelist move", has_text="c5")
                await c5.click(button="right")
                await (
                    page.locator(".tree-context-menu")
                    .get_by_role("button", name="Make main line")
                    .click()
                )

                async def sicilian_is_mainline():
                    doc = await app_state.db.study_chapter.find_one({"_id": first_chapter_id})
                    assert doc is not None
                    tree = StudyTree.from_document(doc["root"])
                    nodes = {node.move: node for node in tree.nodes.values()}
                    return nodes["c7c5"].order == 0 and nodes["e7e5"].order == 1

                await self._eventually_async(sicilian_is_mainline)
                d4 = page.locator("#movelist move", has_text="d4")
                await d4.click(button="right")
                await (
                    page.locator(".tree-context-menu")
                    .get_by_role("button", name="Delete from here")
                    .click()
                )
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, first_chapter_id, 4)
                )

                await page.reload()
                await expect(page.locator("#movelist")).to_contain_text("e4")
                await expect(page.locator("#movelist")).to_contain_text("c5")
                await expect(page.locator("#movelist")).to_contain_text("Nf3")
                await expect(page.locator("#movelist")).to_contain_text("e5")
                await expect(page.locator("#movelist")).not_to_contain_text("d4")

                # Annotation tabs belong below the board, and comments remain visible
                # in the move list after changing tools and reopening the chapter.
                await page.locator("#movelist move.mainline").first.click()
                await page.get_by_role("tab", name="Comment this position").click()
                await page.get_by_role("textbox", name="Study comment").fill("Control the centre")
                await expect(page.locator("#movelist")).to_contain_text("Control the centre")
                await page.get_by_role("tab", name="Annotate with glyphs").click()
                await page.locator('[data-nag="3"]').click()
                await expect(page.locator('[data-nag="3"]')).to_have_attribute(
                    "aria-pressed", "true"
                )
                await page.get_by_role("tab", name="Comment this position").click()
                await page.get_by_role("textbox", name="Study comment").fill("Claim the centre")
                await expect(page.locator("#movelist")).to_contain_text("Claim the centre")
                await page.get_by_role("button", name="Edit study", exact=True).click()
                await expect(page.locator("#study-settings")).to_be_visible()
                await page.keyboard.press("Escape")
                await expect(
                    page.get_by_role("button", name="Edit study", exact=True)
                ).to_be_focused()
                await page.reload()
                await expect(page.locator("#movelist")).to_contain_text("Claim the centre")
                await expect(page.locator("#movelist .status")).to_have_count(0)

                # Build three chapters, rename the middle one, then delete it and
                # verify that the formerly third chapter becomes the adjacent current one.
                await page.get_by_role("button", name="Add a new chapter").click()
                add = page.locator("#study-new-chapter")
                await add.locator('input[name="chapterName"]').fill("Middle chapter")
                await add.get_by_role("button", name="Create chapter").click()
                await page.wait_for_url(
                    re.compile(
                        rf"{re.escape(base_url)}/study/{study_id}/(?!{first_chapter_id}$)\w{{8}}$"
                    )
                )
                _, middle_chapter_id = self._study_ids_from_url(page.url)

                await page.get_by_role("button", name="Edit chapter: Middle chapter").click()
                chapter_settings = page.get_by_role("dialog", name="Edit chapter", exact=True)
                await chapter_settings.get_by_role("textbox", name="Name", exact=True).fill(
                    "Renamed middle"
                )
                await chapter_settings.get_by_role("button", name="Save chapter").click()
                await expect(page.locator(".study-chapters")).to_contain_text("2. Renamed middle")

                await page.get_by_role("button", name="Add a new chapter").click()
                add = page.locator("#study-new-chapter")
                await add.locator('input[name="chapterName"]').fill("Last chapter")
                await add.get_by_role("button", name="Create chapter").click()
                await page.wait_for_url(
                    re.compile(
                        rf"{re.escape(base_url)}/study/{study_id}/(?!{middle_chapter_id}$)\w{{8}}$"
                    )
                )
                _, last_chapter_id = self._study_ids_from_url(page.url)

                # The URL can change before the client has mounted the Study UI.
                await expect(page.locator("#mainboard cg-board")).to_be_visible()
                await page.evaluate(
                    "window.studySidebar = document.querySelector('.sidebar-first')"
                )
                await page.get_by_role("link", name="2. Renamed middle").click()
                await page.wait_for_url(f"{base_url}/study/{study_id}/{middle_chapter_id}")
                assert await page.evaluate(
                    "window.studySidebar === document.querySelector('.sidebar-first')"
                )
                assert self._study_ids_from_url(page.url)[1] == middle_chapter_id
                await page.get_by_role("button", name="Edit chapter: Renamed middle").click()
                await (
                    page.get_by_role("dialog", name="Edit chapter", exact=True)
                    .get_by_role("button", name="Delete chapter")
                    .click()
                )
                await (
                    page.locator("#confirm-dialog")
                    .get_by_role("button", name="Delete chapter")
                    .click()
                )
                await page.wait_for_url(f"{base_url}/study/{study_id}/{last_chapter_id}")
                await expect(page.locator(".study-chapters")).to_contain_text("2. Last chapter")
                await expect(page.locator(".study-chapters")).not_to_contain_text("Renamed middle")

                # Study persistence has no in-memory preload dependency: the storage
                # layer can reconstruct both objects from a fresh context that contains
                # only the database handle. Do not start a second aiohttp test server in
                # this event loop because PyChess graceful shutdown cancels loop-wide tasks.
                fresh_storage = SimpleNamespace(db=app_state.db)
                restarted_study = await load_owned_study(fresh_storage, study_id, username)
                restarted_chapter = await load_owned_chapter(
                    fresh_storage, study_id, first_chapter_id, username
                )
                assert restarted_study is not None
                assert restarted_chapter is not None
                restarted_moves = {node.move for node in restarted_chapter.root.nodes.values()}
                assert {"e2e4", "c7c5", "g1f3", "e7e5"} <= restarted_moves
                assert "d2d4" not in restarted_moves
            finally:
                await context.close()
                await browser.close()

    async def test_two_tabs_converge_and_private_access(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        owner = "study_sync_owner"
        intruder = "study_intruder"
        await self._insert_user(app_state, owner)
        await self._insert_user(app_state, intruder)
        base_url = f"http://{server.host}:{server.port}"

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            owner_context, page_a = await self._page_for_user(browser, base_url, owner)
            page_b = await owner_context.new_page()
            intruder_context, intruder_page = await self._page_for_user(browser, base_url, intruder)
            anon_context = await browser.new_context()
            anon_page = await anon_context.new_page()
            try:
                await page_a.goto(f"{base_url}/study")
                await page_a.locator("[data-study-new-open]").click()
                await page_a.locator('#study-new-dialog input[name="name"]').fill("Synced Study")
                await page_a.locator('#study-new-dialog button[type="submit"]').click()
                await expect(page_a.locator("#study-first-chapter-dialog")).to_be_visible()
                await page_a.locator('#study-first-chapter-form button[type="submit"]').click()
                await page_a.wait_for_url(
                    re.compile(rf"{re.escape(base_url)}/study/\w{{8}}/\w{{8}}$")
                )
                study_id, chapter_id = self._study_ids_from_url(page_a.url)
                study_url = f"{base_url}/study/{study_id}/{chapter_id}"
                await page_b.goto(study_url)
                await self._eventually(
                    lambda: len(app_state.study_sockets.get(study_id, set())) == 2
                )

                await self._play_board_move(page_a, "e2", "e4")
                await expect(page_b.locator("#movelist")).to_contain_text("e4", timeout=5000)

                # Study mutations synchronize the shared tree, but Phase 1 intentionally
                # keeps each tab's current path/board position independent. Follow the
                # remote move in tab B before extending that line.
                await page_b.locator("#movelist move", has_text="e4").click()
                await self._play_board_move(page_b, "e7", "e5")
                await expect(page_a.locator("#movelist")).to_contain_text("e5", timeout=5000)
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, chapter_id, 2)
                )

                # Exercise bidirectional synchronization with deterministic edits from
                # both tabs. The focused Study websocket tests cover the stale-revision
                # race/reload path directly; forcing that race through two simultaneous
                # browser clicks makes the GUI acceptance test flaky because one page may
                # be navigating while Playwright is inspecting its DOM.
                await page_a.locator(".btn-controls button:has(.icon-fast-backward)").click()
                await self._play_board_move(page_a, "d2", "d4")
                await expect(page_b.locator("#movelist")).to_contain_text("d4", timeout=5000)

                await page_b.locator(".btn-controls button:has(.icon-fast-backward)").click()
                await self._play_board_move(page_b, "c2", "c4")
                await expect(page_a.locator("#movelist")).to_contain_text("c4", timeout=5000)
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, chapter_id, 4)
                )

                doc = await app_state.db.study_chapter.find_one({"_id": chapter_id})
                assert doc is not None
                accepted_moves = {
                    node["m"] for node_id, node in doc["root"].items() if node_id != "_"
                }
                assert {"e2e4", "e7e5", "d2d4", "c2c4"} <= accepted_moves
                for page in (page_a, page_b):
                    sans = set(await page.locator("#movelist move san").all_text_contents())
                    assert {"e4", "e5", "d4", "c4"} <= sans

                response = await intruder_page.goto(study_url)
                assert response is not None and response.status == 404
                # Private studies return the same not-found response to anonymous
                # viewers and signed-in users without access.
                response = await anon_page.goto(study_url)
                assert response is not None and response.status == 404
                await expect(
                    anon_page.get_by_role("heading", name="404", exact=True)
                ).to_be_visible()
                await expect(
                    anon_page.get_by_role("button", name=re.compile(r"Login"))
                ).to_be_visible()
            finally:
                await owner_context.close()
                await intruder_context.close()
                await anon_context.close()
                await browser.close()

    async def test_save_analysis_to_study(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        username = "study_analysis_owner"
        await self._insert_user(app_state, username)
        base_url = f"http://{server.host}:{server.port}"

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context, page = await self._page_for_user(browser, base_url, username)
            try:
                await page.goto(f"{base_url}/analysis/chess")
                await self._play_board_move(page, "e2", "e4")
                await self._play_board_move(page, "e7", "e5")
                await expect(page.locator("#movelist")).to_contain_text("e4")
                await expect(page.locator("#movelist")).to_contain_text("e5")

                # A standalone page has no initial history payload, but must still
                # create a tree so revisiting a move can add a genuine variation.
                await page.locator("#movelist move", has_text="e4").click()
                await self._play_board_move(page, "c7", "c5")
                await expect(page.locator("#movelist move.mainline", has_text="e5")).to_have_count(
                    1
                )
                await expect(page.locator("#movelist move.sideline", has_text="c5")).to_have_count(
                    1
                )

                # Standalone analysis displays the FEN/PGN panel directly and hides
                # its tab bar, so Save to Study is already visible.
                await page.get_by_role("button", name="Add to Study").click()
                await page.locator(".study-add-dialog__submit").click()
                await page.wait_for_url(
                    re.compile(rf"{re.escape(base_url)}/study/\w{{8}}/\w{{8}}$")
                )
                study_id, chapter_id = self._study_ids_from_url(page.url)

                await expect(page.locator("#movelist")).to_contain_text("e4")
                await expect(page.locator("#movelist")).to_contain_text("e5")
                await self._eventually_async(
                    lambda: self._study_has_node_count(app_state, chapter_id, 3)
                )
                study_doc = await app_state.db.study.find_one({"_id": study_id})
                chapter_doc = await app_state.db.study_chapter.find_one({"_id": chapter_id})
                assert study_doc is not None
                assert chapter_doc is not None
                assert study_doc["owner"] == username
                assert chapter_doc["initialFen"].startswith("rnbqkbnr/pppppppp/")
            finally:
                await context.close()
                await browser.close()

    async def test_conceal_multiclient_acceptance(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        owner = "conceal_owner"
        writer = "conceal_writer"
        reader = "conceal_reader"
        for username in (owner, writer, reader):
            await self._insert_user(app_state, username)
        study, first, second = await self._create_conceal_acceptance_study(
            app_state, owner, writer, reader
        )
        base_url = f"http://{server.host}:{server.port}"
        first_url = f"{base_url}/study/{study.id}/{first.id}"
        second_url = f"{base_url}/study/{study.id}/{second.id}"
        embed_url = f"{base_url}/study/embed/{study.id}/{first.id}"

        async def conceal_ply() -> int:
            doc = await app_state.db.study_chapter.find_one({"_id": first.id})
            assert doc is not None
            return int(doc.get("concealPly", 0))

        async def shared_path() -> str:
            doc = await app_state.db.study.find_one({"_id": study.id})
            assert doc is not None
            return str(doc.get("currentPath") or "")

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            owner_context, owner_page = await self._page_for_user(browser, base_url, owner)
            writer_context, writer_page = await self._page_for_user(browser, base_url, writer)
            reader_context, reader_page = await self._page_for_user(browser, base_url, reader)
            anon_context = await browser.new_context()
            anon_page = await anon_context.new_page()
            embed_context = await browser.new_context()
            embed_page = await embed_context.new_page()
            rejoin_context = None
            try:
                await asyncio.gather(
                    owner_page.goto(first_url),
                    writer_page.goto(first_url),
                    reader_page.goto(first_url),
                    anon_page.goto(first_url),
                    embed_page.goto(embed_url),
                )
                for page in (owner_page, writer_page, reader_page, anon_page, embed_page):
                    await expect(page.locator("#mainboard cg-board")).to_be_visible()

                await self._eventually(
                    lambda: len(app_state.study_sockets.get(study.id, set())) == 5
                )

                # Owner and writer are authoring clients. Read-only and anonymous
                # viewers have SYNC but never REC; embeds have neither shared-state
                # control. Exercise distinct REC/SYNC combinations before revealing.
                for page in (owner_page, writer_page):
                    await expect(page.locator(".study-mode--write")).to_have_attribute(
                        "aria-pressed", "true"
                    )
                    await expect(page.locator(".study-mode--sync")).to_have_attribute(
                        "aria-pressed", "true"
                    )
                for page in (reader_page, anon_page):
                    await expect(page.locator(".study-mode--write")).to_have_count(0)
                    await expect(page.locator(".study-mode--sync")).to_have_attribute(
                        "aria-pressed", "true"
                    )
                await expect(embed_page.locator(".study-mode--write")).to_have_count(0)
                await expect(embed_page.locator(".study-mode--sync")).to_have_count(0)

                await writer_page.locator(".study-mode--write").click()
                await expect(writer_page.locator(".study-mode--write")).to_have_attribute(
                    "aria-pressed", "false"
                )
                await reader_page.locator(".study-mode--sync").click()
                await expect(reader_page.locator(".study-mode--sync")).to_have_attribute(
                    "aria-pressed", "false"
                )

                # Concealed readers receive no next SAN from the rendered tree. The
                # compact embed joins the Study room as a reader too, but exposes no
                # REC/SYNC controls of its own.
                for page in (reader_page, anon_page, embed_page):
                    await expect(page.locator("#movelist")).not_to_contain_text("e4")

                # A writer with REC disabled may browse the full authored tree but
                # does not present or reveal it to readers.
                await writer_page.locator("#movelist move", has_text="e4").click()
                await expect(
                    writer_page.locator("#movelist move.active", has_text="e4")
                ).to_have_count(1)
                await writer_page.wait_for_timeout(150)
                assert await conceal_ply() == 0
                assert await shared_path() == ""
                await expect(reader_page.locator("#movelist")).not_to_contain_text("e4")
                await expect(anon_page.locator("#movelist")).not_to_contain_text("e4")

                # Owner REC+SYNC publication advances the global reveal boundary.
                # The read member has SYNC off, so it learns the revealed SAN but
                # stays at root; the anonymous public viewer follows the presentation.
                await owner_page.locator("#movelist move", has_text="e4").click()
                await self._eventually_async(lambda: self._equals_async(conceal_ply, 1))
                await expect(reader_page.locator("#movelist")).to_contain_text("e4")
                await expect(
                    reader_page.locator("#movelist move.active", has_text="e4")
                ).to_have_count(0)
                await expect(
                    anon_page.locator("#movelist move.active", has_text="e4")
                ).to_have_count(1)
                assert await shared_path() != ""

                # Compact embeds intentionally stay root-only for non-Normal
                # chapters, like the lightweight lila Study embed. The reveal is
                # available after opening the full Study, not inside the iframe.
                await expect(embed_page.locator("#movelist")).not_to_contain_text("e4")
                await expect(embed_page.get_by_role("link", name="Open study")).to_be_visible()

                # Presenting back to root does not un-reveal the already presented
                # move. SYNC-on viewers follow back while the global boundary remains.
                await owner_page.locator(".btn-controls button:has(.icon-fast-backward)").click()
                await self._eventually_async(lambda: self._equals_async(shared_path, ""))
                assert await conceal_ply() == 1
                await expect(anon_page.locator("#movelist move.active")).to_have_count(0)
                await expect(anon_page.locator("#movelist")).to_contain_text("e4")

                # A new read-member session deterministically reconstructs the same
                # persisted reveal state after joining the Study room.
                rejoin_context, rejoin_page = await self._page_for_user(browser, base_url, reader)
                await rejoin_page.goto(first_url)
                await expect(rejoin_page.locator("#mainboard cg-board")).to_be_visible()
                await expect(rejoin_page.locator("#movelist")).to_contain_text("e4")
                await expect(rejoin_page.locator("#movelist")).not_to_contain_text("e5")

                # Client-side chapter navigation must preserve concealment across
                # browser back/forward history: chapter 2 remains fully hidden while
                # chapter 1 retains its one globally revealed ply.
                await reader_page.get_by_role("link", name="2. Second hidden line").click()
                await reader_page.wait_for_url(second_url)
                await expect(reader_page.locator("#movelist")).not_to_contain_text("c4")
                await reader_page.go_back()
                await reader_page.wait_for_url(first_url)
                await expect(reader_page.locator("#movelist")).to_contain_text("e4")
                await expect(reader_page.locator("#movelist")).not_to_contain_text("e5")
                await reader_page.go_forward()
                await reader_page.wait_for_url(second_url)
                await expect(reader_page.locator("#movelist")).not_to_contain_text("c4")
                await reader_page.go_back()
                await reader_page.wait_for_url(first_url)
                await expect(reader_page.locator("#movelist")).to_contain_text("e4")
                await expect(reader_page.locator("#movelist")).not_to_contain_text("e5")

                # A read-only learner may try a different legal move locally. The
                # attempt is visible only on that path and never mutates the Study DB.
                before_guess = await app_state.db.study_chapter.find_one({"_id": first.id})
                assert before_guess is not None
                await self._play_board_move(reader_page, "d2", "d4")
                await expect(reader_page.locator("#movelist")).to_contain_text("d4")
                await reader_page.wait_for_timeout(250)
                after_guess = await app_state.db.study_chapter.find_one({"_id": first.id})
                assert after_guess is not None
                assert after_guess["revision"] == before_guess["revision"]
                assert after_guess["root"] == before_guess["root"]
                await reader_page.locator(".btn-controls button:has(.icon-fast-backward)").click()
                await expect(reader_page.locator("#movelist")).not_to_contain_text("d4")

                # Reset is an explicit author operation: concealPly and shared path
                # return to root atomically and every live reader, including the
                # compact embed, hides the SAN again.
                await owner_page.get_by_role("button", name="Edit chapter: Hidden line").click()
                chapter_dialog = owner_page.get_by_role("dialog", name="Edit chapter", exact=True)
                await chapter_dialog.get_by_role("button", name="Hide moves again").click()
                confirm = owner_page.locator("#confirm-dialog")
                await expect(confirm).to_be_visible()
                await confirm.get_by_role("button", name="Hide moves again").click()
                await self._eventually_async(lambda: self._equals_async(conceal_ply, 0))
                await self._eventually_async(lambda: self._equals_async(shared_path, ""))
                for page in (reader_page, anon_page, rejoin_page, embed_page):
                    await expect(page.locator("#movelist")).not_to_contain_text("e4")
            finally:
                if rejoin_context is not None:
                    await rejoin_context.close()
                await owner_context.close()
                await writer_context.close()
                await reader_context.close()
                await anon_context.close()
                await embed_context.close()
                await browser.close()

    async def test_practice_browser_acceptance_and_analysis_restore(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        username = "practice_owner"
        await self._insert_user(app_state, username)
        builder = StudyChapterBuilder(app_state, username)

        practice_draft = await builder.blank_or_fen(
            variant="chess",
            mode="practice",
            orientation="white",
            name="Engine practice",
        )
        study, practice_chapter = await create_study_from_draft(
            app_state,
            username,
            practice_draft,
            name="Practice acceptance",
            visibility="public",
        )
        normal_draft = await builder.blank_or_fen(
            variant="chess",
            mode="normal",
            orientation="white",
            name="Normal analysis",
        )
        normal_chapter = await add_chapter_from_draft(
            app_state,
            study,
            normal_draft,
            activate_shared=False,
        )
        initial_doc = await app_state.db.study_chapter.find_one({"_id": practice_chapter.id})
        assert initial_doc is not None

        base_url = f"http://{server.host}:{server.port}"
        practice_url = f"{base_url}/study/{study.id}/{practice_chapter.id}"
        normal_url = f"{base_url}/study/{study.id}/{normal_chapter.id}"

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context, page = await self._page_for_user(browser, base_url, username)
            try:
                await page.add_init_script("localStorage.setItem('localAnalysis', 'true')")
                await page.goto(practice_url)
                await expect(page.locator("#mainboard cg-board")).to_be_visible()
                await expect(page.locator(".study-practice")).to_be_visible()
                await expect(page.locator(".study-practice")).to_contain_text(
                    "Your turn", timeout=20_000
                )
                await expect(page.locator(".study-practice__title")).to_have_text(
                    "Practice with computer"
                )
                await expect(page.locator("#ceval")).to_be_visible()
                await expect(page.locator(".movelist-block")).to_be_visible()
                await expect(page.locator("#btn-controls-top")).to_be_visible()
                await expect(page.locator(".study-tool-tabs")).to_be_visible()
                # Training playback is disposable, but a writable Study member keeps
                # structural chapter controls just like on Lichess. They can also
                # leave practice immediately without waiting for the exercise to end.
                await expect(
                    page.get_by_role("button", name="Edit chapter: Engine practice")
                ).to_be_visible()
                await expect(
                    page.get_by_role("button", name="Analysis", exact=True)
                ).to_be_visible()
                assert await page.evaluate("localStorage.getItem('localAnalysis')") == "true"

                await page.get_by_role("button", name="Get a hint").click()
                await expect(page.get_by_role("button", name="See best move")).to_be_visible(
                    timeout=20_000
                )
                await expect(page.locator(".pvbox")).not_to_be_visible()

                await page.wait_for_function(
                    "window.fsf && typeof window.fsf.postMessage === 'function'"
                )
                await page.evaluate(
                    """
                    () => {
                        window.__studyPracticeCommands = [];
                        const fsf = window.fsf;
                        const original = fsf.postMessage.bind(fsf);
                        fsf.postMessage = command => {
                            window.__studyPracticeCommands.push(String(command));
                            original(command);
                        };
                    }
                    """
                )

                await self._play_board_move(page, "e2", "e4")
                await page.wait_for_timeout(100)
                after_move = await app_state.db.study_chapter.find_one({"_id": practice_chapter.id})
                assert after_move is not None
                assert after_move["revision"] == initial_doc["revision"]
                assert after_move["root"] == initial_doc["root"]

                await page.get_by_role("link", name="2. Normal analysis").click()
                await page.wait_for_url(normal_url)
                await expect(page.locator(".study-practice")).to_have_count(0)
                await expect(page.locator("#engine-enabled")).to_be_checked(timeout=20_000)

                command_mark = await page.evaluate("window.__studyPracticeCommands.length")
                await page.wait_for_timeout(750)
                post_exit_commands = await page.evaluate(
                    "mark => window.__studyPracticeCommands.slice(mark)", command_mark
                )
                assert not any(
                    str(command).startswith("go nodes ") for command in post_exit_commands
                )

                final_doc = await app_state.db.study_chapter.find_one({"_id": practice_chapter.id})
                assert final_doc is not None
                assert final_doc["revision"] == initial_doc["revision"]
                assert final_doc["root"] == initial_doc["root"]
            finally:
                await context.close()
                await browser.close()
