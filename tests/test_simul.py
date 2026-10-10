import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from html import unescape
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
import test_logger
import wsr as round_wss
from const import ABORTED, CASUAL, MATE, T_CREATED, T_FINISHED, T_STARTED
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state import PychessGlobalAppState
from pychess_global_app_state_utils import get_app_state
from simul import wss as simul_wss
from simul.simul import MAX_SIMUL_OPPONENTS, SIMUL_ERASED_USER, Simul
from simul.simuls import (
    erase_user_from_simuls,
    get_hosted_simuls,
    get_simul_home_lists,
    load_active_simuls,
    load_simul,
    upsert_simul_to_db,
)
from typedefs import pychess_global_app_state_key
from user import User

from server import make_app

test_logger.init_test_logger()

log = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestGUI:
    async def test_simul_creation_and_pairing(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        NB_PLAYERS = 5
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Test Simul", created_by=host_username)
        app_state.simuls[sid] = simul

        assert len(simul.players) == 1  # Host is automatically a player

        for i in range(2, NB_PLAYERS + 1):
            player = User(app_state, username=f"TestUser_{i}")
            app_state.users[player.username] = player
            simul.join(player)
            simul.approve(player.username)

        assert len(simul.players) == NB_PLAYERS

        await simul.start()

        assert simul.status == T_STARTED
        assert len(simul.ongoing_games) == NB_PLAYERS - 1

        for game in simul.ongoing_games:
            assert game.wplayer.username == host_username or game.bplayer.username == host_username
            assert game.simulId == sid
            assert game.rated == CASUAL

        if app_state.db is not None:
            game_doc = await app_state.db.game.find_one({"sid": sid})
            assert game_doc is not None
            assert game_doc["sh"] in ("w", "b")
            game = simul.games[game_doc["_id"]]
            assert simul.game_json(game)["hostSide"] == (
                "white" if game_doc["sh"] == "w" else "black"
            )
            simul_doc = await app_state.db.simul.find_one({"_id": sid})
            assert simul_doc is not None
            assert simul_doc["status"] == T_STARTED
            assert len(simul_doc["players"]) == NB_PLAYERS

    async def test_simul_custom_start_position(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="FenHost")
        player1 = User(app_state, username="FenPlayer1")
        player2 = User(app_state, username="FenPlayer2")
        for user in (host, player1, player2):
            app_state.users[user.username] = user
        session = await self._session_for_user(host.username)
        fen = "8/8/8/8/8/4k3/8/4K2R w - - 0 1"

        try:
            response = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data={
                    "name": "From Position",
                    "variants": "chess",
                    "position": fen,
                    "host_color": "white",
                    "base": "5",
                    "inc": "0",
                    "hostExtraTime": "0",
                    "hostExtraTimePerPlayer": "0",
                    "entryMinRatedGames": "0",
                    "entryMinRating": "0",
                    "entryMaxRating": "0",
                    "entryMinAccountAgeDays": "0",
                },
                allow_redirects=False,
            )
            assert response.status == 302
            simul_id = response.headers["Location"].rsplit("/", 1)[-1]
            simul = app_state.simuls[simul_id]
            assert simul.fen == fen
            simul_doc = await app_state.db.simul.find_one({"_id": simul_id})
            assert simul_doc is not None
            assert simul_doc["fen"] == fen

            app_state.simuls.pop(simul_id)
            simul = await load_simul(app_state, simul_id)
            assert simul is not None
            assert simul.fen == fen

            for player in (player1, player2):
                assert simul.join(player) is True
                assert simul.approve(player.username) is True
            assert await simul.start() is True
            assert {game.initial_fen for game in simul.games.values()} == {fen}

            rejected = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data=[
                    ("name", "Mixed From Position"),
                    ("variants", "chess"),
                    ("variants", "atomic"),
                    ("position", fen),
                    ("host_color", "random"),
                    ("base", "5"),
                    ("inc", "0"),
                    ("hostExtraTime", "0"),
                    ("hostExtraTimePerPlayer", "0"),
                    ("entryMinRatedGames", "0"),
                    ("entryMinRating", "0"),
                    ("entryMaxRating", "0"),
                    ("entryMinAccountAgeDays", "0"),
                ],
                allow_redirects=False,
            )
            assert rejected.status == 400
            assert "requires exactly one simul variant" in await rejected.text()
        finally:
            await session.close()

    async def test_simul_applicants_choose_offered_variants(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="Host")
        chess_player = User(app_state, username="ChessPlayer")
        atomic_player = User(app_state, username="AtomicPlayer")
        for user in (host, chess_player, atomic_player):
            app_state.users[user.username] = user

        simul = await Simul.create(
            app_state,
            id8(),
            name="Mixed Simul",
            created_by=host.username,
            variants=["chess", "atomic"],
        )
        app_state.simuls[simul.id] = simul

        assert simul.join(chess_player, "chess") is True
        assert simul.join(atomic_player, "atomic") is True
        assert simul.approve(chess_player.username) is True
        assert simul.approve(atomic_player.username) is True
        assert await simul.start() is True

        assert {simul.game_json(game)["variant"] for game in simul.games.values()} == {
            "chess",
            "atomic",
        }
        simul_doc = await app_state.db.simul.find_one({"_id": simul.id})
        assert simul_doc is not None
        assert simul_doc["variants"] == ["chess", "atomic"]
        assert {
            (player["user"], player["variant"])
            for player in simul_doc["players"]
            if not player["host"]
        } == {(chess_player.username, "chess"), (atomic_player.username, "atomic")}

    async def test_simul_join_approve_and_deny(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Test Simul", created_by=host_username)
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        app_state.users[player2.username] = player2
        simul.join(player2)

        player3 = User(app_state, username="TestUser_3")
        app_state.users[player3.username] = player3
        simul.join(player3)

        assert len(simul.pending_players) == 2

        simul.approve(player2.username)
        assert len(simul.pending_players) == 1
        assert len(simul.players) == 2  # Host + player2
        assert player2.username in simul.players

        simul.deny(player3.username)
        assert len(simul.pending_players) == 0
        assert player3.username not in simul.players

        simul.deny(player2.username)
        assert player2.username not in simul.players
        assert len(simul.players) == 1  # Host only

        assert simul.deny(host_username) is False
        assert host_username in simul.players

        assert simul.join(player2) is True
        assert simul.withdraw(player2) is True
        assert player2.username not in simul.pending_players

        assert simul.join(player2) is True
        assert simul.approve(player2.username) is True
        assert simul.withdraw(player2) is True
        assert player2.username not in simul.players
        assert simul.withdraw(host) is False
        assert host_username in simul.players

    async def test_gdpr_erasure_removes_created_simul_registration(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="Host")
        applicant = User(app_state, username="Applicant")
        app_state.users[host.username] = host
        app_state.users[applicant.username] = applicant

        owned = await Simul.create(app_state, "owned", name="Owned", created_by=applicant.username)
        app_state.simuls[owned.id] = owned
        await upsert_simul_to_db(owned)

        joined = await Simul.create(app_state, "joined", name="Joined", created_by=host.username)
        assert joined.join(applicant) is True
        assert joined.approve(applicant.username) is True
        app_state.simuls[joined.id] = joined
        await upsert_simul_to_db(joined)

        await erase_user_from_simuls(app_state, applicant.username)

        assert await app_state.db.simul.find_one({"_id": owned.id}) is None
        assert owned.id not in app_state.simuls
        joined_doc = await app_state.db.simul.find_one({"_id": joined.id})
        assert joined_doc is not None
        assert [player["user"] for player in joined_doc["players"]] == [host.username]
        assert joined_doc["pendingPlayers"] == []
        assert applicant.username not in joined.players
        assert applicant.username not in joined.pending_players

    async def test_gdpr_erasure_anonymizes_started_simul_history(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="Host")
        player1 = User(app_state, username="Player1")
        player2 = User(app_state, username="Player2")
        for player in (host, player1, player2):
            app_state.users[player.username] = player

        simul = await Simul.create(app_state, "history", name="History", created_by=host.username)
        for player in (player1, player2):
            assert simul.join(player) is True
            assert simul.approve(player.username) is True
        app_state.simuls[simul.id] = simul
        assert await simul.start() is True

        game_sides = {game.id: simul.game_json(game)["hostSide"] for game in simul.games.values()}
        await erase_user_from_simuls(app_state, player1.username)
        await erase_user_from_simuls(app_state, host.username)

        simul_doc = await app_state.db.simul.find_one({"_id": simul.id})
        assert simul_doc is not None
        assert simul_doc["createdBy"] == SIMUL_ERASED_USER
        assert player1.username not in {player["user"] for player in simul_doc["players"]}
        assert host.username not in {player["user"] for player in simul_doc["players"]}
        assert [player["user"] for player in simul_doc["players"]].count(SIMUL_ERASED_USER) == 2

        assert simul.created_by == SIMUL_ERASED_USER
        assert player1.username not in simul.players
        assert host.username not in simul.players
        assert [player.username for player in simul.players.values()].count(SIMUL_ERASED_USER) == 2
        for game in simul.games.values():
            assert simul.game_json(game)["hostSide"] == game_sides[game.id]

        await upsert_simul_to_db(simul)
        rewritten = await app_state.db.simul.find_one({"_id": simul.id})
        assert rewritten is not None
        assert player1.username not in {player["user"] for player in rewritten["players"]}
        assert host.username not in {player["user"] for player in rewritten["players"]}
        assert [player["user"] for player in rewritten["players"]].count(SIMUL_ERASED_USER) == 2

        if simul.clock_task is not None:
            simul.clock_task.cancel()
        app_state.simuls.pop(simul.id, None)
        for game_id in tuple(game_sides):
            app_state.games.pop(game_id, None)
        reloaded = await load_simul(app_state, simul.id)
        assert reloaded is not None
        assert reloaded.created_by == SIMUL_ERASED_USER
        assert [player.username for player in reloaded.players.values()].count(
            SIMUL_ERASED_USER
        ) == 2
        for game in reloaded.games.values():
            assert reloaded.game_json(game)["hostSide"] == game_sides[game.id]
        if reloaded.clock_task is not None:
            reloaded.clock_task.cancel()

    async def test_simul_participant_cap(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="TestUser_host")
        app_state.users[host.username] = host
        simul = await Simul.create(app_state, id8(), name="Capped Simul", created_by=host.username)

        for i in range(MAX_SIMUL_OPPONENTS - 1):
            player = User(app_state, username=f"Accepted_{i}")
            assert simul.join(player) is True
            assert simul.approve(player.username) is True

        last_accepted = User(app_state, username="Accepted_last")
        waiting = User(app_state, username="Still_waiting")
        assert simul.join(last_accepted) is True
        assert simul.join(waiting) is True
        assert simul.approve(last_accepted.username) is True
        assert simul.opponent_count == MAX_SIMUL_OPPONENTS

        assert simul.approve(waiting.username) is False
        assert waiting.username in simul.pending_players

        late_player = User(app_state, username="Too_late")
        assert simul.join(late_player) is False
        assert late_player.username not in simul.pending_players

        simul.players[waiting.username] = simul.pending_players.pop(waiting.username)
        assert simul.opponent_count == MAX_SIMUL_OPPONENTS + 1
        with patch.object(simul, "create_games", new=AsyncMock()) as create_games:
            assert await simul.start() is False
        create_games.assert_not_awaited()
        assert simul.status == T_CREATED

    async def test_simul_capacity_errors_are_sent_to_joiner_and_host(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="TestUser_host")
        app_state.users[host.username] = host
        simul = await Simul.create(app_state, "sid", name="Capped Simul", created_by=host.username)

        for i in range(MAX_SIMUL_OPPONENTS):
            player = User(app_state, username=f"Accepted_{i}")
            simul.pending_players[player.username] = player
            simul.players[player.username] = simul.pending_players.pop(player.username)

        waiting = User(app_state, username="Still_waiting")
        simul.pending_players[waiting.username] = waiting
        late_player = User(app_state, username="Too_late")
        join_ws = SimpleNamespace(send_str=AsyncMock())
        host_ws = SimpleNamespace(send_str=AsyncMock())

        with patch.object(simul_wss, "get_simul", new=AsyncMock(return_value=simul)):
            await simul_wss.handle_join(
                app_state, late_player, join_ws, {"type": "join", "simulId": simul.id}
            )
            await simul_wss.handle_approve_player(
                app_state,
                host_ws,
                host,
                {"type": "approve_player", "simulId": simul.id, "username": waiting.username},
            )

        expected = f"maximum of {MAX_SIMUL_OPPONENTS} accepted players"
        assert expected in join_ws.send_str.call_args.args[0]
        assert expected in host_ws.send_str.call_args.args[0]
        assert waiting.username in simul.pending_players
        assert waiting.username not in simul.players

    async def test_simul_requires_two_opponents_to_start(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Test Simul", created_by=host_username)
        app_state.simuls[sid] = simul

        assert await simul.start() is False
        assert simul.start_error() == "Cannot start simul with fewer than 2 opponents"
        assert simul.status == T_CREATED

        player = User(app_state, username="TestUser_2")
        app_state.users[player.username] = player
        assert simul.join(player) is True
        assert simul.approve(player.username) is True

        assert await simul.start() is False
        assert simul.start_error() == "Cannot start simul with fewer than 2 opponents"
        assert simul.status == T_CREATED

    async def _session_for_user(self, username: str):
        session = aiohttp.ClientSession()
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        value = json.dumps(session_data)
        session.cookie_jar.update_cookies({"AIOHTTP_SESSION": value})
        return session

    async def _connect_ws(self, username: str, port: int):
        session = await self._session_for_user(username)
        ws = await session.ws_connect(
            f"ws://127.0.0.1:{port}/wss", headers={"Origin": f"http://127.0.0.1:{port}"}
        )
        return session, ws

    async def _receive_until_type(self, ws, expected_type: str, max_messages: int = 6):
        for _ in range(max_messages):
            msg = await ws.receive_json()
            if msg.get("type") == expected_type:
                return msg
        raise AssertionError(f"Did not receive expected ws message type: {expected_type}")

    async def test_simul_websocket(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
            anon_as_test_users=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Test Simul", created_by=host_username)
        app_state.simuls[sid] = simul
        previous_host_seen_at = datetime.now(UTC) - timedelta(days=1)
        simul.host_seen_at = previous_host_seen_at

        player2 = User(app_state, username="TestUser_2")
        app_state.users[player2.username] = player2

        host_session, host_ws = await self._connect_ws(host_username, server.port)
        player_session, player_ws = await self._connect_ws(player2.username, server.port)

        try:
            await host_ws.send_json(
                {"type": "simul_user_connected", "username": host_username, "simulId": sid}
            )
            msg = await host_ws.receive_json()
            assert msg["type"] == "simul_user_connected"
            assert msg["username"] == host_username
            assert msg["players"][0]["name"] == host_username
            assert simul.host_seen_at > previous_host_seen_at

            await player_ws.send_json(
                {"type": "simul_user_connected", "username": player2.username, "simulId": sid}
            )
            msg = await player_ws.receive_json()
            assert msg["type"] == "simul_user_connected"

            await player_ws.send_json({"type": "join", "simulId": sid})
            msg = await self._receive_until_type(host_ws, "player_joined")
            assert msg["type"] == "player_joined"
            assert msg["player"]["name"] == player2.username
            assert player2.username in simul.pending_players
            if app_state.db is not None:
                simul_doc = await app_state.db.simul.find_one({"_id": sid})
                assert simul_doc is not None
                assert player2.username in {
                    player["user"] for player in simul_doc["pendingPlayers"]
                }
                assert host_username in {player["user"] for player in simul_doc["players"]}
                assert abs((simul_doc["hostSeenAt"] - simul.host_seen_at).total_seconds()) < 0.001

            await player_ws.close()
            await asyncio.sleep(0)
            assert player2.username in simul.pending_players
            if app_state.db is not None:
                simul_doc = await app_state.db.simul.find_one({"_id": sid})
                assert simul_doc is not None
                assert player2.username in {
                    player["user"] for player in simul_doc["pendingPlayers"]
                }

            reconnect_session, reconnect_ws = await self._connect_ws(player2.username, server.port)
            try:
                await reconnect_ws.send_json(
                    {"type": "simul_user_connected", "username": player2.username, "simulId": sid}
                )
                msg = await reconnect_ws.receive_json()
                assert msg["type"] == "simul_user_connected"
                assert player2.username in {player["name"] for player in msg["pendingPlayers"]}

                await host_ws.send_json(
                    {"type": "approve_player", "simulId": sid, "username": player2.username}
                )
                msg = await self._receive_until_type(host_ws, "player_approved")
                assert msg["type"] == "player_approved"
                assert msg["player"]["name"] == player2.username
                assert player2.username in simul.players
                assert player2.username not in simul.pending_players
                if app_state.db is not None:
                    simul_doc = await app_state.db.simul.find_one({"_id": sid})
                    assert simul_doc is not None
                    assert player2.username in {player["user"] for player in simul_doc["players"]}
                    assert player2.username not in {
                        player["user"] for player in simul_doc["pendingPlayers"]
                    }

                await reconnect_ws.close()
                await asyncio.sleep(0)
                assert player2.username in simul.players

                withdraw_session, withdraw_ws = await self._connect_ws(
                    player2.username, server.port
                )
                try:
                    await withdraw_ws.send_json(
                        {
                            "type": "simul_user_connected",
                            "username": player2.username,
                            "simulId": sid,
                        }
                    )
                    msg = await withdraw_ws.receive_json()
                    assert msg["type"] == "simul_user_connected"
                    assert player2.username in {player["name"] for player in msg["players"]}

                    await withdraw_ws.send_json({"type": "withdraw", "simulId": sid})
                    msg = await self._receive_until_type(host_ws, "player_withdrawn")
                    assert msg["username"] == player2.username
                    assert player2.username not in simul.players
                    assert player2.username not in simul.pending_players
                    if app_state.db is not None:
                        simul_doc = await app_state.db.simul.find_one({"_id": sid})
                        assert simul_doc is not None
                        assert player2.username not in simul_doc["players"]
                        assert player2.username not in {
                            player["user"] for player in simul_doc["pendingPlayers"]
                        }
                finally:
                    await withdraw_ws.close()
                    await withdraw_session.close()
            finally:
                await reconnect_ws.close()
                await reconnect_session.close()
        finally:
            await host_ws.close()
            await host_session.close()
            await player_session.close()

    async def test_host_game_presence_is_broadcast_and_persisted(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)

        host = User(app_state, username="PresenceHost")
        watcher = User(app_state, username="PresenceWatcher")
        opponents = [User(app_state, username=f"PresenceOpponent_{i}") for i in range(2)]
        for user in (host, watcher, *opponents):
            app_state.users[user.username] = user

        simul = await Simul.create(app_state, id8(), name="Presence", created_by=host.username)
        app_state.simuls[simul.id] = simul
        for opponent in opponents:
            assert simul.join(opponent) is True
            assert simul.approve(opponent.username) is True
        assert await simul.start() is True

        watcher_session, watcher_ws = await self._connect_ws(watcher.username, server.port)
        host_session = await self._session_for_user(host.username)
        host_round_ws = None
        try:
            await watcher_ws.send_json(
                {"type": "simul_user_connected", "username": watcher.username, "simulId": simul.id}
            )
            connected = await self._receive_until_type(watcher_ws, "simul_user_connected")
            assert connected["hostGameId"] is None

            game_id = next(iter(simul.games))
            host_round_ws = await host_session.ws_connect(
                f"ws://127.0.0.1:{server.port}/wsr/{game_id}",
                headers={"Origin": f"http://127.0.0.1:{server.port}"},
            )
            host_game = await self._receive_until_type(watcher_ws, "host_game")
            assert host_game["gameId"] == game_id
            assert simul.host_game_id == game_id

            simul_doc = await app_state.db.simul.find_one({"_id": simul.id})
            assert simul_doc is not None
            assert simul_doc["hostGameId"] == game_id
        finally:
            if host_round_ws is not None:
                await host_round_ws.close()
            await host_session.close()
            await watcher_ws.close()
            await watcher_session.close()
            if simul.clock_task is not None:
                simul.clock_task.cancel()
                try:
                    await simul.clock_task
                except asyncio.CancelledError:
                    pass

    async def test_simul_creation_rejects_two_board_variant(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        session = await self._session_for_user(host_username)

        try:
            response = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data={
                    "name": "No Two Board Simul",
                    "variants": "bughouse",
                    "host_color": "random",
                    "base": "3",
                    "inc": "0",
                },
            )
            assert response.status == 400
            assert "Two-board variants are not allowed in simuls" in await response.text()
            assert len(app_state.simuls) == 0
        finally:
            await session.close()

    async def test_simul_new_excludes_two_board_variants(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        session = await self._session_for_user(host_username)

        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul/new")
            assert response.status == 200
            html = await response.text()
            assert 'value="chess"' in html
            assert 'value="bughouse"' not in html
            assert 'value="bughouse960"' not in html
            assert 'name="description"' in html
            assert 'name="hostExtraTime"' in html
            assert 'name="hostExtraTimePerPlayer"' in html
            assert 'name="entryMinRatedGames"' in html
            assert 'name="entryMinRating"' in html
            assert 'name="entryMaxRating"' in html
            assert 'name="entryMinAccountAgeDays"' in html
            assert 'name="estimatedStartAt"' in html
        finally:
            await session.close()

    async def test_simul_new_uses_lichess_clock_choices_and_defaults(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        session = await self._session_for_user(host_username)

        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul/new")
            assert response.status == 200
            html = await response.text()

            clock_time_select = html.split('id="form3-clockTime"', 1)[1].split("</select>", 1)[0]
            clock_increment_select = html.split('id="form3-clockIncrement"', 1)[1].split(
                "</select>", 1
            )[0]

            assert [
                int(value) for value in re.findall(r'<option value="(\d+)"', clock_time_select)
            ] == [
                5,
                10,
                15,
                20,
                30,
                40,
                50,
                60,
                70,
                80,
                90,
                120,
                140,
                160,
                180,
            ]
            assert [
                int(value) for value in re.findall(r'<option value="(\d+)"', clock_increment_select)
            ] == [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                10,
                15,
                20,
                25,
                30,
                40,
                50,
                60,
                90,
                120,
                150,
                180,
            ]
            assert '<option value="20" selected="selected">20 minutes</option>' in clock_time_select
            assert (
                '<option value="60" selected="selected">60 seconds</option>'
                in clock_increment_select
            )
        finally:
            await session.close()

    async def test_anon_simuls_page_hides_host_button(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        session = aiohttp.ClientSession()

        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul")
            assert response.status == 200
            html = await response.text()
            assert "HOST A NEW SIMUL" not in html
            assert 'href="/simul/new"' not in html
        finally:
            await session.close()

    async def test_anon_cannot_open_or_create_simuls(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        session = aiohttp.ClientSession()

        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul/new")
            assert response.status == 403

            response = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data={
                    "name": "Anon Simul",
                    "variants": "chess",
                    "host_color": "random",
                    "base": "3",
                    "inc": "0",
                },
            )
            assert response.status == 403
            assert len(app_state.simuls) == 0
        finally:
            await session.close()

    async def test_simul_creation_persists_description_and_entry_conditions(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        session = await self._session_for_user(host_username)

        try:
            response = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data={
                    "name": "Entry Checked Simul",
                    "description": "Club practice only",
                    "variants": "chess",
                    "host_color": "white",
                    "base": "5",
                    "inc": "3",
                    "hostExtraTime": "600",
                    "hostExtraTimePerPlayer": "30",
                    "entryMinRatedGames": "20",
                    "entryMinRating": "1500",
                    "entryMaxRating": "2100",
                    "entryMinAccountAgeDays": "30",
                },
                allow_redirects=False,
            )
            assert response.status == 302
            location = response.headers["Location"]
            simul_id = location.rsplit("/", 1)[-1]

            simul = app_state.simuls[simul_id]
            assert simul.description == "Club practice only"
            assert simul.host_extra_time == 600
            assert simul.host_extra_time_per_player == 30
            assert simul.entry_titled_only is False
            assert simul.entry_min_rated_games == 20
            assert simul.entry_min_rating == 1500
            assert simul.entry_max_rating == 2100
            assert simul.entry_min_account_age_days == 30

            simul_doc = await app_state.db.simul.find_one({"_id": simul_id})
            assert simul_doc is not None
            assert simul_doc["description"] == "Club practice only"
            assert simul_doc["hostExtraTime"] == 600
            assert simul_doc["hostExtraTimePerPlayer"] == 30
            assert simul_doc.get("entryTitledOnly") is None
            assert simul_doc["entryMinRatedGames"] == 20
            assert simul_doc["entryMinRating"] == 1500
            assert simul_doc["entryMaxRating"] == 2100
            assert simul_doc["entryMinAccountAgeDays"] == 30
        finally:
            await session.close()

    async def test_simul_creation_persists_estimated_start_time(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        session = await self._session_for_user(host_username)
        estimated_start = (datetime.now(UTC) + timedelta(hours=2)).replace(second=0, microsecond=0)

        try:
            response = await session.post(
                f"http://127.0.0.1:{server.port}/simul",
                data={
                    "name": "Scheduled Simul",
                    "description": "Later today",
                    "variants": "chess",
                    "host_color": "random",
                    "base": "5",
                    "inc": "0",
                    "hostExtraTime": "0",
                    "hostExtraTimePerPlayer": "0",
                    "entryMinRatedGames": "0",
                    "entryMinRating": "0",
                    "entryMaxRating": "0",
                    "entryMinAccountAgeDays": "0",
                    "estimatedStartAt": estimated_start.isoformat(),
                },
                allow_redirects=False,
            )
            assert response.status == 302
            simul_id = response.headers["Location"].rsplit("/", 1)[-1]

            simul = app_state.simuls[simul_id]
            assert simul.estimated_start_at == estimated_start

            simul_doc = await app_state.db.simul.find_one({"_id": simul_id})
            assert simul_doc is not None
            assert simul_doc["estimatedStartAt"] == estimated_start
        finally:
            await session.close()

    async def test_site_admin_can_edit_and_cancel_created_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="Host")
        moderator = User(app_state, username="mod")
        outsider = User(app_state, username="outsider")
        for user in (host, moderator, outsider):
            app_state.users[user.username] = user

        simul = await Simul.create(
            app_state, id8(), name="Needs moderation", created_by=host.username
        )
        app_state.simuls[simul.id] = simul
        await upsert_simul_to_db(simul)

        moderator_session = await self._session_for_user(moderator.username)
        outsider_session = await self._session_for_user(outsider.username)
        try:
            with (
                patch("views.simul.ADMINS", [moderator.username]),
                patch("views.ADMINS", [moderator.username]),
            ):
                denied = await outsider_session.get(
                    f"http://127.0.0.1:{server.port}/simul/{simul.id}/edit"
                )
                assert denied.status == 403

                edit_page = await moderator_session.get(
                    f"http://127.0.0.1:{server.port}/simul/{simul.id}/edit"
                )
                assert edit_page.status == 200
                assert "Edit Needs moderation" in await edit_page.text()

                updated = await moderator_session.post(
                    f"http://127.0.0.1:{server.port}/simul/{simul.id}/edit",
                    data={
                        "name": "Clean simul name",
                        "description": "Moderated description",
                        "variants": "chess",
                        "host_color": "random",
                        "base": "3",
                        "inc": "0",
                        "hostExtraTime": "0",
                        "hostExtraTimePerPlayer": "0",
                        "entryMinRatedGames": "0",
                        "entryMinRating": "0",
                        "entryMaxRating": "0",
                        "entryMinAccountAgeDays": "0",
                        "estimatedStartAt": "",
                    },
                    allow_redirects=False,
                )
                assert updated.status == 302
                assert simul.name == "Clean simul name"

                edit_log = await app_state.db.mod_log.find_one({"action": "simul_edited"})
                assert edit_log is not None
                assert edit_log["mod"] == moderator.username
                assert edit_log["user"] == host.username
                assert simul.id in edit_log["details"]

                cancelled = await moderator_session.post(
                    f"http://127.0.0.1:{server.port}/simul/{simul.id}/cancel",
                    allow_redirects=False,
                )
                assert cancelled.status == 302
                assert simul.id not in app_state.simuls
                assert await app_state.db.simul.find_one({"_id": simul.id}) is None

                cancel_log = await app_state.db.mod_log.find_one({"action": "simul_cancelled"})
                assert cancel_log is not None
                assert cancel_log["mod"] == moderator.username
                assert cancel_log["user"] == host.username
        finally:
            await moderator_session.close()
            await outsider_session.close()

    async def test_site_admin_cannot_cancel_started_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host = User(app_state, username="Host")
        moderator = User(app_state, username="mod")
        opponent = User(app_state, username="Opponent")
        opponent2 = User(app_state, username="Opponent2")
        for user in (host, moderator, opponent, opponent2):
            app_state.users[user.username] = user

        simul = await Simul.create(app_state, id8(), name="Running simul", created_by=host.username)
        for player in (opponent, opponent2):
            assert simul.join(player)
            assert simul.approve(player.username)
        app_state.simuls[simul.id] = simul
        assert await simul.start()

        moderator_session = await self._session_for_user(moderator.username)
        try:
            with (
                patch("views.simul.ADMINS", [moderator.username]),
                patch("views.ADMINS", [moderator.username]),
            ):
                response = await moderator_session.post(
                    f"http://127.0.0.1:{server.port}/simul/{simul.id}/cancel",
                    allow_redirects=False,
                )
                assert response.status == 400
                assert simul.status == T_STARTED
                assert simul.id in app_state.simuls
        finally:
            if simul.clock_task is not None:
                simul.clock_task.cancel()
            await moderator_session.close()

    async def test_simul_join_rejected_by_rating_entry_conditions(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
            anon_as_test_users=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username, title="FM")
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state,
            sid,
            name="Restricted Simul",
            created_by=host_username,
            entry_min_rating=1800,
        )
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        app_state.users[player2.username] = player2

        host_session, host_ws = await self._connect_ws(host_username, server.port)
        player_session, player_ws = await self._connect_ws(player2.username, server.port)

        try:
            await host_ws.send_json(
                {"type": "simul_user_connected", "username": host_username, "simulId": sid}
            )
            await host_ws.receive_json()

            await player_ws.send_json(
                {"type": "simul_user_connected", "username": player2.username, "simulId": sid}
            )
            await player_ws.receive_json()

            await player_ws.send_json({"type": "join", "simulId": sid})
            msg = await self._receive_until_type(player_ws, "error")
            assert msg["message"] == "Your rating is below the minimum allowed for this simul."
            assert player2.username not in simul.pending_players
            assert player2.username not in simul.players
        finally:
            await host_ws.close()
            await player_ws.close()
            await host_session.close()
            await player_session.close()

    async def test_simul_team_membership_entry_condition(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        assert app_state.db is not None

        await app_state.db.team.insert_one(
            {"_id": "variant-fans", "name": "Variant Fans", "enabled": True}
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": "member@variant-fans",
                "team": "variant-fans",
                "user": "member",
            }
        )

        simul = Simul(
            app_state,
            "team-simul",
            name="Team Simul",
            created_by="host",
            entry_team_id="variant-fans",
            entry_team_name="Variant Fans",
        )
        member = User(app_state, username="member")
        outsider = User(app_state, username="outsider")

        assert await simul.entry_condition_error(member) is None
        assert await simul.entry_condition_error(outsider) == (
            "You must be a member of Variant Fans to join this simul."
        )

    async def test_bot_user_cannot_join_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        bot_user = User(app_state, bot=True, username="bot-simul")
        ws = SimpleNamespace(send_str=AsyncMock())
        simul = SimpleNamespace(
            entry_condition_error=AsyncMock(return_value="BOT accounts cannot join simuls."),
            join=lambda user: False,
        )

        with patch.object(simul_wss, "get_simul", new=AsyncMock(return_value=simul)):
            await simul_wss.handle_join(app_state, bot_user, ws, {"type": "join", "simulId": "sid"})

        assert "BOT accounts cannot join simuls" in ws.send_str.call_args.args[0]

    async def test_anonymous_user_cannot_join_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        anon_user = User(app_state, anon=True, username="Anon-simul")
        ws = SimpleNamespace(send_str=AsyncMock())
        simul = Simul(app_state, "sid", name="Test Simul", created_by="host")

        with patch.object(simul_wss, "get_simul", new=AsyncMock(return_value=simul)):
            await simul_wss.handle_join(
                app_state, anon_user, ws, {"type": "join", "simulId": "sid"}
            )

        assert "Anonymous users cannot join simuls" in ws.send_str.call_args.args[0]
        assert anon_user.username not in simul.pending_players

    async def test_bot_user_cannot_host_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        bot_user = User(app_state, bot=True, username="bot-host")
        app_state.users[bot_user.username] = bot_user
        session = await self._session_for_user(bot_user.username)

        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul")
            assert response.status == 200
            html = await response.text()
            assert "HOST A NEW SIMUL" not in html
            assert 'href="/simul/new"' not in html

            response = await session.get(f"http://127.0.0.1:{server.port}/simul/new")
            assert response.status == 403

            response = await session.post(f"http://127.0.0.1:{server.port}/simul", data={})
            assert response.status == 403
            assert len(app_state.simuls) == 0
        finally:
            await session.close()

    async def test_simul_takeback_is_rejected_server_side(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        user = User(app_state, username="simul-player")
        ws = SimpleNamespace(send_str=AsyncMock())
        game = SimpleNamespace(
            server_variant=SimpleNamespace(two_boards=False),
            simulId="sid",
        )

        with patch.object(round_wss, "handle_takeback", new=AsyncMock()) as handle_takeback:
            await round_wss.process_message(
                app_state,
                user,
                ws,
                {"type": "takeback", "gameId": "game"},
                game,
            )

        handle_takeback.assert_not_awaited()
        assert "Takebacks are disabled in simuls" in ws.send_str.call_args.args[0]

    async def test_simul_host_extra_time_applies_only_to_host(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state,
            sid,
            name="Extra Time Simul",
            created_by=host_username,
            base=5,
            inc=0,
            host_color="white",
            host_extra_time=600,
            host_extra_time_per_player=30,
        )
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        player3 = User(app_state, username="TestUser_3")
        app_state.users[player2.username] = player2
        app_state.users[player3.username] = player3
        simul.join(player2)
        simul.join(player3)
        simul.approve(player2.username)
        simul.approve(player3.username)

        started = await simul.start()
        assert started is True
        assert simul.host_extra_time == 660

        for game in simul.games.values():
            if game.wplayer.username == host_username:
                assert game.clocks_w[0] == 960000
                assert game.clocks_b[0] == 300000
            else:
                assert game.clocks_w[0] == 300000
                assert game.clocks_b[0] == 960000

        if app_state.db is not None:
            game_doc = await app_state.db.game.find_one({"sid": sid})
            assert game_doc is not None
            assert game_doc["cw0"] in (960000, 300000)
            assert game_doc["cb0"] in (960000, 300000)

    async def test_simul_websocket_host_can_remove_approved_player(self, aiohttp_server):
        app = make_app(
            db_client=AsyncMongoMockClient(tz_aware=True),
            simple_cookie_storage=True,
            anon_as_test_users=True,
        )
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Test Simul", created_by=host_username)
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        app_state.users[player2.username] = player2

        host_session, host_ws = await self._connect_ws(host_username, server.port)
        player_session, player_ws = await self._connect_ws(player2.username, server.port)

        try:
            await host_ws.send_json(
                {"type": "simul_user_connected", "username": host_username, "simulId": sid}
            )
            msg = await host_ws.receive_json()
            assert msg["type"] == "simul_user_connected"

            await player_ws.send_json(
                {"type": "simul_user_connected", "username": player2.username, "simulId": sid}
            )
            msg = await player_ws.receive_json()
            assert msg["type"] == "simul_user_connected"

            await player_ws.send_json({"type": "join", "simulId": sid})
            msg = await self._receive_until_type(host_ws, "player_joined")
            assert msg["player"]["name"] == player2.username

            await host_ws.send_json(
                {"type": "approve_player", "simulId": sid, "username": player2.username}
            )
            msg = await self._receive_until_type(host_ws, "player_approved")
            assert msg["player"]["name"] == player2.username
            assert player2.username in simul.players

            await host_ws.send_json(
                {"type": "deny_player", "simulId": sid, "username": player2.username}
            )
            msg = await self._receive_until_type(host_ws, "player_denied")
            assert msg["username"] == player2.username
            msg = await self._receive_until_type(player_ws, "player_denied")
            assert msg["username"] == player2.username
            assert player2.username not in simul.players
            assert player2.username not in simul.pending_players
            if app_state.db is not None:
                simul_doc = await app_state.db.simul.find_one({"_id": sid})
                assert simul_doc is not None
                assert player2.username not in simul_doc["players"]
                assert player2.username not in {
                    player["user"] for player in simul_doc["pendingPlayers"]
                }
        finally:
            await host_ws.close()
            await player_ws.close()
            await host_session.close()
            await player_session.close()

    async def test_started_simul_reloads_after_restart(self, aiohttp_server):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        await aiohttp_server(app)
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state, sid, name="Persistent Simul", created_by=host_username
        )
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        player3 = User(app_state, username="TestUser_3")
        for player in (player2, player3):
            app_state.users[player.username] = player
            simul.join(player)
            simul.approve(player.username)

        started = await simul.start()
        assert started is True
        assert simul.status == T_STARTED
        assert len(simul.games) == 2
        assert simul.clock_task is not None

        reloaded_app = make_app(db_client=db_client)
        reloaded_app[pychess_global_app_state_key] = PychessGlobalAppState(reloaded_app)
        reloaded_state = get_app_state(reloaded_app)
        await load_active_simuls(reloaded_state)

        reloaded_simul = reloaded_state.simuls.get(sid)
        assert reloaded_simul is not None
        assert reloaded_simul.status == T_STARTED
        assert host_username in reloaded_simul.players
        assert player2.username in reloaded_simul.players
        assert player3.username in reloaded_simul.players
        assert len(reloaded_simul.games) == 2
        assert len(reloaded_simul.ongoing_games) == 2
        assert reloaded_simul.clock_task is not None

        if reloaded_simul.clock_task is not None:
            reloaded_simul.clock_task.cancel()
            try:
                await reloaded_simul.clock_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.parametrize("fail_at", [1, 2])
    async def test_restart_completes_interrupted_or_partial_start(self, fail_at):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        app[pychess_global_app_state_key] = PychessGlobalAppState(app)
        app_state = get_app_state(app)
        host = User(app_state, username="PartialHost")
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state,
            id8(),
            name="Interrupted Start",
            created_by=host.username,
            base=5,
            inc=3,
            host_extra_time=10,
            host_extra_time_per_player=7,
        )
        app_state.simuls[simul.id] = simul
        opponents = [User(app_state, username=f"PartialPlayer_{i}") for i in range(3)]
        for opponent in opponents:
            app_state.users[opponent.username] = opponent
            assert simul.join(opponent) is True
            assert simul.approve(opponent.username) is True

        from utils import insert_game_to_db as persist_game

        inserts = 0

        async def interrupted_insert(game, state):
            nonlocal inserts
            inserts += 1
            if inserts == fail_at:
                raise RuntimeError("simulated restart during simul start")
            await persist_game(game, state)

        with (
            patch("simul.simul.insert_game_to_db", side_effect=interrupted_insert),
            pytest.raises(RuntimeError, match="simulated restart during simul start"),
        ):
            await simul.start()

        assert simul.status == T_STARTED
        assert await app_state.db.game.count_documents({"sid": simul.id}) == fail_at - 1
        persisted = await app_state.db.simul.find_one({"_id": simul.id})
        assert persisted is not None
        assert persisted["status"] == T_STARTED
        assert persisted["hostExtraTime"] == 31

        restarted_app = make_app(db_client=db_client)
        restarted_app[pychess_global_app_state_key] = PychessGlobalAppState(restarted_app)
        restarted_state = get_app_state(restarted_app)
        await load_active_simuls(restarted_state)

        recovered = restarted_state.simuls.get(simul.id)
        assert recovered is not None
        assert recovered.status == T_STARTED
        assert recovered.host_extra_time == 31
        assert len(recovered.games) == len(opponents)
        assert len(recovered.ongoing_games) == len(opponents)
        assert await restarted_state.db.game.count_documents({"sid": simul.id}) == len(opponents)

        paired_opponents = []
        for game in recovered.games.values():
            paired_opponents.append(
                game.bplayer.username if game.simulHostColor == "w" else game.wplayer.username
            )
        assert sorted(paired_opponents) == sorted(player.username for player in opponents)
        assert recovered.missing_opponents() == []

        recovered_ids = set(recovered.games)
        if recovered.clock_task is not None:
            recovered.clock_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await recovered.clock_task

        second_restart_app = make_app(db_client=db_client)
        second_restart_app[pychess_global_app_state_key] = PychessGlobalAppState(second_restart_app)
        second_restart_state = get_app_state(second_restart_app)
        await load_active_simuls(second_restart_state)
        second_recovery = second_restart_state.simuls.get(simul.id)
        assert second_recovery is not None
        assert set(second_recovery.games) == recovered_ids
        assert await second_restart_state.db.game.count_documents({"sid": simul.id}) == len(
            opponents
        )
        if second_recovery.clock_task is not None:
            second_recovery.clock_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second_recovery.clock_task

    async def test_host_round_navigation_survives_restart(self, aiohttp_server):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        app[pychess_global_app_state_key] = PychessGlobalAppState(app)
        app_state = get_app_state(app)
        host = User(app_state, username="RestartHost")
        app_state.users[host.username] = host
        await app_state.db.user.insert_one({"_id": host.username, "enabled": True})

        simul = await Simul.create(
            app_state, id8(), name="Restart Navigation", created_by=host.username
        )
        app_state.simuls[simul.id] = simul
        for i in range(2):
            opponent = User(app_state, username=f"RestartOpponent_{i}")
            app_state.users[opponent.username] = opponent
            await app_state.db.user.insert_one({"_id": opponent.username, "enabled": True})
            assert simul.join(opponent) is True
            assert simul.approve(opponent.username) is True
        assert await simul.start() is True
        if simul.clock_task is not None:
            simul.clock_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await simul.clock_task

        restarted_app = make_app(
            db_client=db_client, simple_cookie_storage=True, anon_as_test_users=True
        )
        restarted_app[pychess_global_app_state_key] = PychessGlobalAppState(restarted_app)
        restarted_state = get_app_state(restarted_app)
        await load_active_simuls(restarted_state)
        recovered = restarted_state.simuls.get(simul.id)
        assert recovered is not None
        assert len(recovered.games) == 2

        server = await aiohttp_server(restarted_app, host="127.0.0.1")
        game_ids = list(recovered.games)
        session = await self._session_for_user(host.username)
        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/{game_ids[0]}")
            assert response.status == 200
            html = await response.text()
            assert f'data-simulid="{simul.id}"' in html
            assert 'data-simulhost="True"' in html
            # The round page must contain every simul game, not only the current one,
            # because the ongoing-games controller uses this list for skip/navigation.
            simul_games_attr = html.split('data-simulgames="', 1)[1].split('"', 1)[0]
            round_simul_games = json.loads(unescape(simul_games_attr))
            assert {game["gameId"] for game in round_simul_games} == set(game_ids)
        finally:
            await session.close()
            if recovered.clock_task is not None:
                recovered.clock_task.cancel()
                try:
                    await recovered.clock_task
                except asyncio.CancelledError:
                    pass

    async def test_restart_skips_stale_created_simuls_but_keeps_on_demand_loading(self):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        app[pychess_global_app_state_key] = PychessGlobalAppState(app)
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        host = User(app_state, username=host_username)
        app_state.users[host.username] = host
        now = datetime.now(UTC)

        recent_sid = id8()
        recent = await Simul.create(
            app_state, recent_sid, name="Recent Created Simul", created_by=host_username
        )
        recent.created_at = now - timedelta(minutes=30)
        recent.host_seen_at = now - timedelta(minutes=15)
        await upsert_simul_to_db(recent, app_state)

        stale_sid = id8()
        stale = await Simul.create(
            app_state, stale_sid, name="Stale Created Simul", created_by=host_username
        )
        stale.created_at = now - timedelta(hours=3)
        stale.host_seen_at = now - timedelta(hours=2)
        await upsert_simul_to_db(stale, app_state)

        restarted_app = make_app(db_client=db_client)
        restarted_app[pychess_global_app_state_key] = PychessGlobalAppState(restarted_app)
        restarted_state = get_app_state(restarted_app)
        await load_active_simuls(restarted_state)

        assert recent_sid in restarted_state.simuls
        assert stale_sid not in restarted_state.simuls

        loaded_stale = await load_simul(restarted_state, stale_sid)
        assert loaded_stale is not None
        assert loaded_stale.status == T_CREATED
        assert abs((loaded_stale.host_seen_at - stale.host_seen_at).total_seconds()) < 0.001

    async def test_short_finished_simul_game_persists_and_reloads(self, aiohttp_server):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state, sid, name="Persistent Short Simul", created_by=host_username
        )
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        player3 = User(app_state, username="TestUser_3")
        for player in (player2, player3):
            app_state.users[player.username] = player
            simul.join(player)
            simul.approve(player.username)

        started = await simul.start()
        assert started is True
        assert len(simul.games) == 2

        games = list(simul.games.values())
        for game in games:
            game.update_status(MATE, "1-0")
            await game.save_game()
            await simul.game_update(game)
        game = games[0]

        if app_state.db is not None:
            game_doc = await app_state.db.game.find_one({"_id": game.id})
            assert game_doc is not None
            assert game_doc["sid"] == sid

        reloaded_app = make_app(db_client=db_client)
        reloaded_app[pychess_global_app_state_key] = PychessGlobalAppState(reloaded_app)
        reloaded_state = get_app_state(reloaded_app)
        reloaded_simul = await load_simul(reloaded_state, sid)
        assert reloaded_simul is not None
        assert reloaded_simul.status == T_FINISHED
        assert game.id in reloaded_simul.games

    async def test_finished_simul_listed_after_restart(self, aiohttp_server):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username, title="FM")
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state, sid, name="Restart Visible Simul", created_by=host_username
        )
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        player3 = User(app_state, username="TestUser_3")
        for player in (player2, player3):
            app_state.users[player.username] = player
            simul.join(player)
            simul.approve(player.username)

        started = await simul.start()
        assert started is True

        for game in simul.games.values():
            game.update_status(MATE, "1-0")
            await game.save_game()
            await simul.game_update(game)
        assert simul.status == T_FINISHED

        restarted_app = make_app(db_client=db_client)
        restarted_app[pychess_global_app_state_key] = PychessGlobalAppState(restarted_app)
        restarted_state = get_app_state(restarted_app)

        my_simuls, created_simuls, started_simuls, finished_simuls = await get_simul_home_lists(
            restarted_state
        )

        assert my_simuls == []
        assert created_simuls == []
        assert started_simuls == []
        assert any(
            entry.id == sid and entry.name == "Restart Visible Simul" for entry in finished_simuls
        )

    async def test_simul_home_queries_statuses_independently(self):
        db_client = AsyncMongoMockClient(tz_aware=True)
        app = make_app(db_client=db_client)
        app[pychess_global_app_state_key] = PychessGlobalAppState(app)
        app_state = get_app_state(app)
        now = datetime.now(UTC)

        created_id = "created1"
        started_id = "started1"
        stale_id = "stale001"
        await app_state.db.simul.insert_many(
            [
                {
                    "_id": created_id,
                    "name": "Older Active Created",
                    "createdBy": "host-created",
                    "featurable": True,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now - timedelta(hours=3),
                    "hostSeenAt": now - timedelta(minutes=5),
                    "status": T_CREATED,
                    "players": [{"user": "host-created", "variant": "chess", "host": True}],
                    "pendingPlayers": [],
                },
                {
                    "_id": started_id,
                    "name": "Older Running Simul",
                    "createdBy": "host-started",
                    "featurable": False,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now - timedelta(hours=4),
                    "hostSeenAt": now - timedelta(hours=4),
                    "startsAt": now - timedelta(hours=2),
                    "status": T_STARTED,
                    "players": [
                        {"user": "host-started", "variant": "chess", "host": True},
                        {"user": "player", "variant": "chess", "host": False},
                    ],
                    "pendingPlayers": [],
                },
                {
                    "_id": stale_id,
                    "name": "Stale Created",
                    "createdBy": "host-stale",
                    "featurable": True,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now - timedelta(hours=5),
                    "hostSeenAt": now - timedelta(hours=2),
                    "status": T_CREATED,
                    "players": [{"user": "host-stale", "variant": "chess", "host": True}],
                    "pendingPlayers": [],
                },
            ]
        )

        finished_docs = []
        for i in range(35):
            finished_docs.append(
                {
                    "_id": f"f{i:07d}",
                    "name": f"Finished {i}",
                    "createdBy": "host-finished",
                    "featurable": True,
                    "variants": ["chess"],
                    "base": 3,
                    "inc": 0,
                    "createdAt": now - timedelta(minutes=i),
                    "hostSeenAt": now - timedelta(hours=1),
                    "startsAt": now - timedelta(minutes=70 - i),
                    "endsAt": now - timedelta(minutes=35 - i),
                    "status": T_FINISHED,
                    "players": [
                        {"user": "host-finished", "variant": "chess", "host": True},
                        {"user": "player", "variant": "chess", "host": False},
                    ],
                    "pendingPlayers": [],
                }
            )
        await app_state.db.simul.insert_many(finished_docs)

        my_simuls, created, started, finished = await get_simul_home_lists(app_state)

        assert my_simuls == []
        assert [entry.id for entry in created] == [created_id]
        assert [entry.id for entry in started] == [started_id]
        assert len(finished) == 20
        assert finished[0].id == "f0000034"
        assert stale_id not in {entry.id for entry in created}

    async def test_hosted_simuls_are_paginated_with_host_results(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app[pychess_global_app_state_key] = PychessGlobalAppState(app)
        app_state = get_app_state(app)
        now = datetime.now(UTC)
        host = "TestUser_1"

        docs = []
        for i in range(23):
            docs.append(
                {
                    "_id": f"h{i:07d}",
                    "name": f"Hosted {i}",
                    "createdBy": host,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now - timedelta(minutes=i),
                    "status": T_FINISHED,
                    "players": [
                        {"user": host, "variant": "chess", "host": True},
                        {"user": f"player-{i}", "variant": "chess", "host": False},
                    ],
                    "pendingPlayers": [],
                }
            )
        docs.extend(
            [
                {
                    "_id": "other001",
                    "name": "Someone else's simul",
                    "createdBy": "TestUser_2",
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now,
                    "status": T_FINISHED,
                    "players": [
                        {"user": "TestUser_2", "variant": "chess", "host": True},
                        {"user": "player", "variant": "chess", "host": False},
                    ],
                    "pendingPlayers": [],
                },
                {
                    "_id": "active01",
                    "name": "Still active",
                    "createdBy": host,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now + timedelta(minutes=1),
                    "status": T_CREATED,
                    "players": [{"user": host, "variant": "chess", "host": True}],
                    "pendingPlayers": [],
                },
            ]
        )
        await app_state.db.simul.insert_many(docs)
        await app_state.db.game.insert_many(
            [
                {"_id": "win00001", "sid": "h0000000", "r": "a", "sh": "w"},
                {"_id": "draw0001", "sid": "h0000000", "r": "c", "sh": "b"},
                {"_id": "loss0001", "sid": "h0000000", "r": "a", "sh": "b"},
            ]
        )

        first_page, total = await get_hosted_simuls(app_state, host, 1)
        second_page, second_total = await get_hosted_simuls(app_state, host, 2)

        assert total == second_total == 23
        assert len(first_page) == 20
        assert [entry.id for entry in first_page[:2]] == ["h0000000", "h0000001"]
        assert [entry.id for entry in second_page] == ["h0000020", "h0000021", "h0000022"]
        assert (first_page[0].wins, first_page[0].draws, first_page[0].losses) == (1, 1, 1)

    async def test_simul_home_lists_signed_in_players_pending_and_accepted(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        server = await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        username = "TestUser_2"
        app_state.users[username] = User(app_state, username=username)
        now = datetime.now(UTC)

        await app_state.db.simul.insert_many(
            [
                {
                    "_id": "pending1",
                    "name": "Pending Application",
                    "createdBy": "TestUser_1",
                    "featurable": False,
                    "variants": ["chess"],
                    "base": 5,
                    "inc": 3,
                    "createdAt": now - timedelta(minutes=10),
                    "hostSeenAt": now,
                    "estimatedStartAt": now + timedelta(hours=1),
                    "status": T_CREATED,
                    "players": [{"user": "TestUser_1", "variant": "chess", "host": True}],
                    "pendingPlayers": [{"user": username, "variant": "chess", "host": False}],
                },
                {
                    "_id": "accepted",
                    "name": "Accepted Application",
                    "createdBy": "TestUser_3",
                    "featurable": False,
                    "variants": ["chess"],
                    "base": 10,
                    "inc": 0,
                    "createdAt": now - timedelta(minutes=5),
                    "hostSeenAt": now,
                    "estimatedStartAt": now + timedelta(hours=2),
                    "status": T_CREATED,
                    "players": [
                        {"user": "TestUser_3", "variant": "chess", "host": True},
                        {"user": username, "variant": "chess", "host": False},
                    ],
                    "pendingPlayers": [],
                },
                {
                    "_id": "hosted01",
                    "name": "Own Hosted Simul",
                    "createdBy": username,
                    "featurable": False,
                    "variants": ["chess"],
                    "base": 3,
                    "inc": 2,
                    "createdAt": now,
                    "hostSeenAt": now,
                    "status": T_CREATED,
                    "players": [{"user": username, "variant": "chess", "host": True}],
                    "pendingPlayers": [],
                },
            ]
        )

        my_simuls, _created, _started, _finished = await get_simul_home_lists(
            app_state, username=username
        )
        assert [(entry.id, entry.participation) for entry in my_simuls] == [
            ("hosted01", "host"),
            ("accepted", "accepted"),
            ("pending1", "pending"),
        ]

        session = await self._session_for_user(username)
        try:
            response = await session.get(f"http://127.0.0.1:{server.port}/simul")
            assert response.status == 200
            html = await response.text()
            assert "Your simuls" in html
            assert "Own Hosted Simul" in html
            assert "Pending Application" in html
            assert "Accepted Application" in html
            assert ">Pending<" in html
            assert ">Accepted<" in html
        finally:
            await session.close()

    async def test_aborted_simul_game_finishes_simul(self, aiohttp_server):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(app_state, sid, name="Abort Simul", created_by=host_username)
        app_state.simuls[sid] = simul

        player2 = User(app_state, username="TestUser_2")
        player3 = User(app_state, username="TestUser_3")
        for player in (player2, player3):
            app_state.users[player.username] = player
            simul.join(player)
            simul.approve(player.username)

        started = await simul.start()
        assert started is True
        assert simul.status == T_STARTED
        assert len(simul.games) == 2
        assert len(simul.ongoing_games) == 2

        for game in tuple(simul.games.values()):
            await game.game_ended(host, "abort")
            assert game.status == ABORTED
        assert len(simul.ongoing_games) == 0
        assert simul.status == T_FINISHED

    async def test_simul_disconnect_only_cleans_socket_presence(self, aiohttp_server, monkeypatch):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        await aiohttp_server(app, host="127.0.0.1")
        app_state = get_app_state(app)
        host_username = "TestUser_1"
        sid = id8()

        host = User(app_state, username=host_username)
        app_state.users[host.username] = host

        simul = await Simul.create(
            app_state, sid, name="Persistent Simul", created_by=host_username
        )
        app_state.simuls[sid] = simul

        player = User(app_state, username="TestUser_2")
        app_state.users[player.username] = player
        simul.join(player)
        simul.approve(player.username)
        simul.add_spectator(player)

        fake_ws = object()
        player.simul_sockets[sid] = {fake_ws}
        upsert = AsyncMock()
        broadcast = AsyncMock()
        monkeypatch.setattr(simul_wss, "upsert_simul_to_db", upsert)
        monkeypatch.setattr(simul, "broadcast", broadcast)

        await simul_wss.finally_logic(app_state, fake_ws, player)

        assert player.username in simul.players
        assert sid not in player.simul_sockets
        assert player not in simul.spectators
        upsert.assert_not_awaited()
        broadcast.assert_not_awaited()
