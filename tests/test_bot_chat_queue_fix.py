import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from wsr import handle_bugroundchat, handle_roundchat

test_logger.init_test_logger()


class RoundChatBotQueueTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_roundchat_enqueues_valid_json_for_bots(self) -> None:
        bot_queue: asyncio.Queue[str] = asyncio.Queue()
        bot = SimpleNamespace(bot=True, username="Fairy-Stockfish", game_queues={"g1": bot_queue})
        human = SimpleNamespace(bot=False, username="black", send_game_message=AsyncMock())
        sender = SimpleNamespace(username="white")
        chat_flood = SimpleNamespace(allow_message=lambda source, text: True)
        app_state = SimpleNamespace(
            users={bot.username: bot, human.username: human},
            chat_flood=chat_flood,
        )

        class RecordingGame:
            id = "g1"
            wplayer = bot
            bplayer = human

            def is_player(self, user) -> bool:
                return user.username == "white"

            def __init__(self) -> None:
                self.messages: list[dict[str, object]] = []

            def handle_chat_message(self, message: dict[str, object]) -> None:
                self.messages.append(message)

        game = RecordingGame()

        with patch("wsr.round_broadcast", new=AsyncMock()):
            await handle_roundchat(
                app_state,
                None,
                sender,
                {
                    "type": "roundchat",
                    "gameId": "g1",
                    "message": 'All of the first moves are "@"s',
                    "room": "player",
                },
                game,
            )

        queued = await bot_queue.get()
        event = json.loads(queued)
        self.assertEqual(event["type"], "chatLine")
        self.assertEqual(event["username"], "white")
        self.assertEqual(event["room"], "player")
        self.assertEqual(event["text"], 'All of the first moves are "@"s')

    async def test_timed_out_roundchat_is_dropped(self) -> None:
        sender = SimpleNamespace(username="white", silence=60)
        app_state = SimpleNamespace(chat_flood=SimpleNamespace(allow_message=lambda *_: True))
        game = SimpleNamespace(id="g1", messages=[])

        with patch("wsr.round_broadcast", new=AsyncMock()) as rb:
            await handle_roundchat(
                app_state,
                None,
                sender,
                {
                    "type": "roundchat",
                    "gameId": "g1",
                    "message": "blocked",
                    "room": "spectator",
                },
                game,
            )

        self.assertEqual([], game.messages)
        rb.assert_not_awaited()

    async def test_roundchat_drops_rejected_flood_message(self) -> None:
        bot_queue: asyncio.Queue[str] = asyncio.Queue()
        bot = SimpleNamespace(bot=True, username="Fairy-Stockfish", game_queues={"g1": bot_queue})
        human = SimpleNamespace(bot=False, username="black", send_game_message=AsyncMock())
        sender = SimpleNamespace(username="white")
        chat_flood = SimpleNamespace(allow_message=lambda source, text: False)
        app_state = SimpleNamespace(
            users={bot.username: bot, human.username: human},
            chat_flood=chat_flood,
        )

        class RecordingGame:
            id = "g1"
            wplayer = bot
            bplayer = human

            def is_player(self, user) -> bool:
                return user.username == "white"

            def __init__(self) -> None:
                self.messages: list[dict[str, object]] = []

            def handle_chat_message(self, message: dict[str, object]) -> None:
                self.messages.append(message)

        game = RecordingGame()

        with patch("wsr.round_broadcast", new=AsyncMock()):
            await handle_roundchat(
                app_state,
                None,
                sender,
                {
                    "type": "roundchat",
                    "gameId": "g1",
                    "message": "repeat repeat repeat",
                    "room": "player",
                },
                game,
            )

        self.assertEqual(game.messages, [])
        self.assertTrue(bot_queue.empty())
        human.send_game_message.assert_not_awaited()

    async def test_roundchat_sanitizes_message_for_humans_and_bots(self) -> None:
        bot_queue: asyncio.Queue[str] = asyncio.Queue()
        bot = SimpleNamespace(bot=True, username="Fairy-Stockfish", game_queues={"g1": bot_queue})
        human = SimpleNamespace(bot=False, username="black", send_game_message=AsyncMock())
        sender = SimpleNamespace(username="white")
        chat_flood = SimpleNamespace(allow_message=lambda source, text: True)
        app_state = SimpleNamespace(
            users={bot.username: bot, human.username: human},
            chat_flood=chat_flood,
        )

        class RecordingGame:
            id = "g1"
            wplayer = bot
            bplayer = human

            def is_player(self, user) -> bool:
                return user.username == "white"

            def __init__(self) -> None:
                self.messages: list[dict[str, object]] = []

            def handle_chat_message(self, message: dict[str, object]) -> None:
                self.messages.append(message)

        game = RecordingGame()

        with patch("wsr.round_broadcast", new=AsyncMock()):
            await handle_roundchat(
                app_state,
                None,
                sender,
                {
                    "type": "roundchat",
                    "gameId": "g1",
                    "message": "visit https://tinyurl.com/abc",
                    "room": "player",
                },
                game,
            )

        self.assertEqual("visit [redacted]", game.messages[0]["message"])
        human.send_game_message.assert_awaited_once()
        human_msg = human.send_game_message.await_args.args[1]
        self.assertEqual("visit [redacted]", human_msg["message"])

        queued = await bot_queue.get()
        event = json.loads(queued)
        self.assertEqual("visit [redacted]", event["text"])

    async def test_shadowbanned_roundchat_is_only_echoed_to_sender(self) -> None:
        bot_queue: asyncio.Queue[str] = asyncio.Queue()
        bot = SimpleNamespace(bot=True, username="Fairy-Stockfish", game_queues={"g1": bot_queue})
        human = SimpleNamespace(bot=False, username="black", send_game_message=AsyncMock())
        sender = SimpleNamespace(username="white", shadowban=True, send_game_message=AsyncMock())
        chat_flood = SimpleNamespace(allow_message=lambda source, text: True)
        app_state = SimpleNamespace(
            users={bot.username: bot, human.username: human},
            chat_flood=chat_flood,
        )

        class RecordingGame:
            id = "g1"
            wplayer = bot
            bplayer = human

            def is_player(self, user) -> bool:
                return user.username == "white"

            def __init__(self) -> None:
                self.messages: list[dict[str, object]] = []

            def handle_chat_message(self, message: dict[str, object]) -> None:
                self.messages.append(message)

        game = RecordingGame()

        with patch("wsr.round_broadcast", new=AsyncMock()) as rb:
            await handle_roundchat(
                app_state,
                None,
                sender,
                {
                    "type": "roundchat",
                    "gameId": "g1",
                    "message": "this stays hidden",
                    "room": "player",
                },
                game,
            )

        sender.send_game_message.assert_awaited_once()
        human.send_game_message.assert_not_awaited()
        self.assertTrue(bot_queue.empty())
        self.assertEqual([], game.messages)
        rb.assert_not_awaited()

    async def test_shadowbanned_bugroundchat_is_only_echoed_to_sender(self) -> None:
        sender = SimpleNamespace(
            username="whiteA",
            shadowban=True,
            send_game_message=AsyncMock(),
        )
        users = {"whiteA": sender}

        class RecordingGame:
            id = "g1"
            ply = 2
            status = 1
            wplayerA = SimpleNamespace(username="whiteA")
            bplayerA = SimpleNamespace(username="blackA")
            wplayerB = SimpleNamespace(username="whiteB")
            bplayerB = SimpleNamespace(username="blackB")
            gameClocks = SimpleNamespace(elapsed_since_last_move=lambda: 17)

            def is_player(self, user) -> bool:
                return user.username == "whiteA"

            def __init__(self) -> None:
                self.chat_calls: list[tuple[str, str]] = []

            def handle_chat_message(self, user, message, room):
                self.chat_calls.append((message, room))
                return {"username": user.username, "message": message, "room": room, "time": 17}

        game = RecordingGame()

        with patch("wsr.round_broadcast", new=AsyncMock()) as rb:
            await handle_bugroundchat(
                users,
                sender,
                {
                    "type": "bugroundchat",
                    "gameId": "g1",
                    "message": "hidden message",
                    "room": "player",
                },
                game,
            )

        sender.send_game_message.assert_awaited_once()
        sent_game_id, sent_payload = sender.send_game_message.await_args.args
        self.assertEqual("g1", sent_game_id)
        self.assertEqual("bugroundchat", sent_payload["type"])
        self.assertEqual("hidden message", sent_payload["message"])
        self.assertEqual([], game.chat_calls)
        rb.assert_not_awaited()


if __name__ == "__main__":
    unittest.main(verbosity=2)
