import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from glicko2.glicko2 import new_default_perf_map
from lobby import Lobby
from seek import Seek
from user import User
from variants import VARIANTS

test_logger.init_test_logger()
PERFS = new_default_perf_map(VARIANTS)


class UserStore(dict):
    async def get(self, username):
        return super().get(username)


class LobbyTargetedSeeksTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_challenge_refreshes_only_participants(self):
        app_state = SimpleNamespace(users=UserStore(), seeks={})
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        carol = User(app_state, username="carol", perfs=PERFS)
        app_state.users.update({u.username: u for u in (alice, bob, carol)})
        seek = Seek("private-seek", alice, "chess", target=bob.username)
        app_state.seeks[seek.id] = seek

        lobby = Lobby(app_state)
        sockets = {u.username: object() for u in (alice, bob, carol)}
        for username, socket in sockets.items():
            lobby.lobbysockets[username] = {socket}

        with patch("lobby.ws_send_json_many", new_callable=AsyncMock) as send:
            await lobby.lobby_broadcast_seeks((alice.username, bob.username))

        self.assertEqual(2, send.await_count)
        self.assertEqual(
            {alice.username, bob.username},
            {name for name, socket in sockets.items() if any(
                socket in call.args[0] for call in send.await_args_list
            )},
        )
        for call in send.await_args_list:
            self.assertEqual("get_seeks", call.args[1]["type"])
            self.assertEqual([seek.id], [s["_id"] for s in call.args[1]["seeks"]])

        # Public seek updates still refresh the entire connected lobby.
        with patch("lobby.ws_send_json_many", new_callable=AsyncMock) as send_all:
            await lobby.lobby_broadcast_seeks()
        self.assertEqual(3, send_all.await_count)
        carol_payload = next(
            call.args[1]
            for call in send_all.await_args_list
            if sockets[carol.username] in call.args[0]
        )
        self.assertEqual([], carol_payload["seeks"])
