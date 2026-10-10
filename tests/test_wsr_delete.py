import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from const import CASUAL, IMPORTED
from wsr import handle_delete, process_message


class RoundDeleteAuthorizationTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.delete_result = SimpleNamespace(deleted_count=1)
        self.game_collection = SimpleNamespace(
            delete_one=AsyncMock(return_value=self.delete_result)
        )
        self.db = SimpleNamespace(game=self.game_collection)
        self.app_state = SimpleNamespace(db=self.db)
        self.ws = AsyncMock()

    def imported_game(self, *, game_id="game-owned", imported_by="owner"):
        return SimpleNamespace(
            id=game_id,
            rated=IMPORTED,
            imported_by=imported_by,
        )

    async def test_importer_can_delete_own_imported_game(self):
        user = SimpleNamespace(username="owner")
        game = self.imported_game()

        with patch("wsr.ws_send_json", new=AsyncMock()) as send:
            await handle_delete(self.db, self.ws, user, game)

        self.game_collection.delete_one.assert_awaited_once_with(
            {"_id": game.id, "y": IMPORTED, "by": user.username}
        )
        send.assert_awaited_once_with(self.ws, {"type": "deleted"})

    async def test_non_importer_cannot_delete_imported_game(self):
        attacker = SimpleNamespace(username="attacker")
        game = self.imported_game(imported_by="victim")

        with patch("wsr.ws_send_json", new=AsyncMock()) as send:
            await handle_delete(self.db, self.ws, attacker, game)

        self.game_collection.delete_one.assert_not_awaited()
        send.assert_awaited_once_with(
            self.ws,
            {"type": "error", "message": "You are not allowed to delete this game."},
        )

    async def test_importer_cannot_delete_non_imported_game(self):
        user = SimpleNamespace(username="owner")
        game = SimpleNamespace(id="played-game", rated=CASUAL, imported_by="owner")

        with patch("wsr.ws_send_json", new=AsyncMock()) as send:
            await handle_delete(self.db, self.ws, user, game)

        self.game_collection.delete_one.assert_not_awaited()
        send.assert_awaited_once_with(
            self.ws,
            {"type": "error", "message": "You are not allowed to delete this game."},
        )

    async def test_message_game_id_is_ignored_including_mongo_operator_object(self):
        user = SimpleNamespace(username="owner")
        game = self.imported_game(game_id="socket-game")
        malicious_message = {"type": "delete", "gameId": {"$ne": ""}}

        with patch("wsr.ws_send_json", new=AsyncMock()):
            await process_message(self.app_state, user, self.ws, malicious_message, game)

        self.game_collection.delete_one.assert_awaited_once_with(
            {"_id": "socket-game", "y": IMPORTED, "by": "owner"}
        )

    async def test_database_guard_failure_does_not_report_success(self):
        self.delete_result.deleted_count = 0
        user = SimpleNamespace(username="owner")
        game = self.imported_game()

        with patch("wsr.ws_send_json", new=AsyncMock()) as send:
            await handle_delete(self.db, self.ws, user, game)

        send.assert_awaited_once_with(
            self.ws,
            {"type": "error", "message": "Game could not be deleted."},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
