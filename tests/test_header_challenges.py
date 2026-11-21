import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from glicko2.glicko2 import new_default_perf_map
from header_challenges import get_user_challenges, set_direct_challenge_status
from seek import (
    DIRECT_CHALLENGE_ACCEPTED,
    DIRECT_CHALLENGE_CANCELED,
    DIRECT_CHALLENGE_CREATED,
    DIRECT_CHALLENGE_DECLINED,
    DIRECT_CHALLENGE_OFFLINE,
    Seek,
    create_seek,
    get_seeks,
)
from user import User
from utils import join_seek
from wsl import handle_accept_seek, handle_delete_seek
from variants import VARIANTS

test_logger.init_test_logger()

PERFS = new_default_perf_map(VARIANTS)


class HeaderChallengeTestCase(unittest.IsolatedAsyncioTestCase):
    def make_app_state(self):
        app_state = SimpleNamespace(
            users={},
            seeks={},
            invites={},
            db=None,
            lobby=SimpleNamespace(lobby_broadcast_seeks=AsyncMock()),
            anon_as_test_users=False,
        )
        app_state.public_users = SimpleNamespace(get_profile=self.get_profile(app_state))
        return app_state

    @staticmethod
    def get_profile(app_state):
        async def _get_profile(username: str):
            user = app_state.users.get(username)
            if user is None:
                return None
            return SimpleNamespace(
                username=user.username,
                title=user.title,
                enabled=True,
                blocked=frozenset(user.blocked),
                pm_friends_only=user.pm_friends_only,
            )

        return _get_profile

    async def test_direct_challenge_seek_has_expiry_and_is_not_marked_pending(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        target = User(app_state, username="bob", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        app_state.users[target.username] = target

        seek = Seek("seek1", challenger, "chess", target=target.username)
        app_state.seeks[seek.id] = seek
        challenger.seeks[seek.id] = seek

        await challenger.update_seeks(pending=True)

        self.assertTrue(seek.is_direct_challenge)
        self.assertIsNotNone(seek.expire_at)
        self.assertFalse(seek.pending)

    async def test_get_user_challenges_separates_incoming_and_outgoing(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        carol = User(app_state, username="carol", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob, carol.username: carol})

        outgoing = Seek("seek1", bob, "chess", target=alice.username)
        incoming = Seek("seek2", carol, "atomic", target=bob.username)
        app_state.seeks[outgoing.id] = outgoing
        app_state.seeks[incoming.id] = incoming

        bob_challenges = get_user_challenges(app_state, bob.username)

        self.assertEqual([challenge["id"] for challenge in bob_challenges], ["seek2", "seek1"])
        self.assertTrue(bob_challenges[0]["incoming"])
        self.assertFalse(bob_challenges[1]["incoming"])
        self.assertEqual(bob_challenges[0]["opponent"], "carol")
        self.assertEqual(bob_challenges[1]["opponent"], "alice")

    async def test_get_user_challenges_keeps_terminal_direct_challenge_status(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("seek1", alice, "chess", target=bob.username)
        set_direct_challenge_status(seek, DIRECT_CHALLENGE_DECLINED)
        app_state.seeks[seek.id] = seek

        bob_challenges = get_user_challenges(app_state, bob.username)

        self.assertEqual([], bob_challenges)

    async def test_get_user_challenges_keeps_declined_status_for_challenger(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("seek1", alice, "chess", target=bob.username)
        seek.set_challenge_decline_reason("This time control is too fast for me.")
        set_direct_challenge_status(seek, DIRECT_CHALLENGE_DECLINED)
        app_state.seeks[seek.id] = seek

        alice_challenges = get_user_challenges(app_state, alice.username)

        self.assertEqual(1, len(alice_challenges))
        self.assertEqual(DIRECT_CHALLENGE_DECLINED, alice_challenges[0]["status"])
        self.assertEqual(
            "This time control is too fast for me.", alice_challenges[0]["declineReason"]
        )

    async def test_get_user_challenges_filters_canceled_direct_challenges(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("seek-canceled", alice, "chess", target=bob.username)
        set_direct_challenge_status(seek, DIRECT_CHALLENGE_CANCELED)
        app_state.seeks[seek.id] = seek

        bob_challenges = get_user_challenges(app_state, bob.username)
        alice_challenges = get_user_challenges(app_state, alice.username)

        self.assertEqual([], bob_challenges)
        self.assertEqual([], alice_challenges)

    async def test_unrelated_user_cannot_accept_direct_challenge_over_lobby(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        carol = User(app_state, username="carol", perfs=PERFS)
        app_state.users.update({u.username: u for u in (alice, bob, carol)})
        seek = Seek("seek1", alice, "chess", target=bob.username, player1=alice)
        app_state.seeks[seek.id] = seek
        alice.seeks[seek.id] = seek

        with patch("wsl.ws_send_json", new_callable=AsyncMock) as send:
            await handle_accept_seek(app_state, object(), carol, {"seekID": seek.id})

        self.assertEqual(
            {"type": "error", "message": "Challenge not available"},
            send.await_args.args[1],
        )
        self.assertIsNone(seek.player2)
        self.assertIn(seek.id, app_state.seeks)

    async def test_unrelated_user_cannot_delete_direct_challenge_over_lobby(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        carol = User(app_state, username="carol", perfs=PERFS)
        app_state.users.update({u.username: u for u in (alice, bob, carol)})
        seek = Seek("seek1", alice, "chess", target=bob.username, player1=alice)
        app_state.seeks[seek.id] = seek
        alice.seeks[seek.id] = seek

        await handle_delete_seek(app_state, carol, {"seekID": seek.id})

        self.assertIn(seek.id, app_state.seeks)
        self.assertIn(seek.id, alice.seeks)
        self.assertEqual(DIRECT_CHALLENGE_CREATED, seek.challenge_status)
        app_state.lobby.lobby_broadcast_seeks.assert_not_awaited()

    async def test_accepted_direct_challenge_is_removed_when_game_created(self):
        app_state = self.make_app_state()
        app_state.games = {}
        app_state.realtime_game_creation_lock = asyncio.Lock()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("seek-to-consume", alice, "chess", target=bob.username, player1=alice)
        app_state.seeks[seek.id] = seek
        alice.seeks[seek.id] = seek

        game = SimpleNamespace(corr=False, has_crosstable=False)
        with (
            patch("utils.Game", return_value=game),
            patch("utils.new_id", new=AsyncMock(return_value="game-test")),
            patch("utils.insert_game_to_db", new=AsyncMock()),
        ):
            response = await join_seek(app_state, bob, seek)

        self.assertEqual("new_game", response["type"])
        self.assertEqual("game-test", response["gameId"])
        self.assertNotIn(seek.id, app_state.seeks)
        self.assertNotIn(seek.id, alice.seeks)
        self.assertEqual([], get_user_challenges(app_state, alice.username))
        self.assertEqual([], get_user_challenges(app_state, bob.username))

    async def test_public_seek_is_also_removed_when_game_created(self):
        app_state = self.make_app_state()
        app_state.games = {}
        app_state.realtime_game_creation_lock = asyncio.Lock()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("public-seek", alice, "chess", player1=alice)
        app_state.seeks[seek.id] = seek
        alice.seeks[seek.id] = seek

        game = SimpleNamespace(corr=False, has_crosstable=False)
        with (
            patch("utils.Game", return_value=game),
            patch("utils.new_id", new=AsyncMock(return_value="public-game")),
            patch("utils.insert_game_to_db", new=AsyncMock()),
        ):
            response = await join_seek(app_state, bob, seek)

        self.assertEqual("new_game", response["type"])
        self.assertNotIn(seek.id, app_state.seeks)
        self.assertNotIn(seek.id, alice.seeks)

    async def test_get_user_challenges_keeps_accepted_direct_challenge_status(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        seek = Seek("seek-accepted", alice, "chess", target=bob.username)
        set_direct_challenge_status(seek, DIRECT_CHALLENGE_ACCEPTED)
        app_state.seeks[seek.id] = seek

        bob_challenges = get_user_challenges(app_state, bob.username)

        self.assertEqual(1, len(bob_challenges))
        self.assertEqual(DIRECT_CHALLENGE_ACCEPTED, bob_challenges[0]["status"])

    async def test_get_seeks_filters_terminal_direct_challenges_from_lobby(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        active = Seek("seek-active", alice, "chess", target=bob.username)
        inactive = Seek("seek-offline", alice, "chess", target=bob.username)
        canceled = Seek("seek-canceled", alice, "chess", target=bob.username)
        set_direct_challenge_status(inactive, DIRECT_CHALLENGE_OFFLINE)
        set_direct_challenge_status(canceled, DIRECT_CHALLENGE_CANCELED)
        app_state.seeks.update({active.id: active, inactive.id: inactive, canceled.id: canceled})

        lobby_seeks = get_seeks(bob, app_state.seeks.values())

        self.assertEqual(["seek-active", "seek-offline"], [seek["_id"] for seek in lobby_seeks])

    async def test_get_seeks_filters_accepted_direct_challenges_from_lobby(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})

        accepted = Seek("seek-accepted", alice, "chess", target=bob.username)
        set_direct_challenge_status(accepted, DIRECT_CHALLENGE_ACCEPTED)
        app_state.seeks[accepted.id] = accepted

        lobby_seeks = get_seeks(bob, app_state.seeks.values())

        self.assertEqual([], lobby_seeks)

    async def test_clear_seeks_preserves_direct_challenge(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        target = User(app_state, username="bob", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        app_state.users[target.username] = target

        seek = Seek("seek-preserve", challenger, "chess", target=target.username)
        app_state.seeks[seek.id] = seek
        challenger.seeks[seek.id] = seek

        await challenger.clear_seeks()

        self.assertIn(seek.id, app_state.seeks)
        self.assertIn(seek.id, challenger.seeks)

    async def test_create_seek_replaces_existing_direct_challenge_for_same_target(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        target = User(app_state, username="bob", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        app_state.users[target.username] = target

        data = {
            "variant": "chess",
            "fen": "",
            "color": "r",
            "minutes": 5,
            "increment": 3,
            "byoyomiPeriod": 0,
            "rated": True,
            "chess960": False,
            "target": target.username,
        }

        first = await create_seek(
            app_state.db, app_state.invites, app_state.seeks, challenger, data
        )
        replacement = await create_seek(
            app_state.db, app_state.invites, app_state.seeks, challenger, data
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(replacement)
        self.assertEqual(2, len(app_state.seeks))
        self.assertEqual(DIRECT_CHALLENGE_CANCELED, first.challenge_status)
        self.assertEqual(DIRECT_CHALLENGE_CREATED, replacement.challenge_status)
        self.assertNotEqual(first.id, replacement.id)

    async def test_create_seek_rejects_direct_challenge_when_users_are_blocked(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        target = User(app_state, username="bob", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        app_state.users[target.username] = target
        challenger.blocked.add(target.username)

        created = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "r",
                "minutes": 5,
                "increment": 3,
                "byoyomiPeriod": 0,
                "rated": True,
                "chess960": False,
                "target": target.username,
            },
        )

        self.assertIsNone(created)

    async def test_create_seek_rejects_generic_direct_challenge_to_bot_target(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        target = User(app_state, bot=True, username="engine-bot", title="BOT", perfs=PERFS)
        app_state.users[challenger.username] = challenger
        app_state.users[target.username] = target

        created = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "r",
                "minutes": 5,
                "increment": 3,
                "byoyomiPeriod": 0,
                "rated": True,
                "chess960": False,
                "target": target.username,
            },
        )

        self.assertIsNone(created)
        self.assertEqual({}, app_state.seeks)

    async def test_join_seek_rejects_blocked_users(self):
        app_state = self.make_app_state()
        creator = User(app_state, username="alice", perfs=PERFS)
        joiner = User(app_state, username="bob", perfs=PERFS)
        app_state.users[creator.username] = creator
        app_state.users[joiner.username] = joiner
        creator.blocked.add(joiner.username)

        seek = Seek("seek1", creator, "chess")
        result = await join_seek(app_state, joiner, seek)

        self.assertEqual(
            {"type": "error", "message": "You cannot accept this seek."},
            result,
        )

    async def test_get_user_challenges_hides_blocked_direct_challenge(self):
        app_state = self.make_app_state()
        alice = User(app_state, username="alice", perfs=PERFS)
        bob = User(app_state, username="bob", perfs=PERFS)
        app_state.users.update({alice.username: alice, bob.username: bob})
        bob.blocked.add(alice.username)

        seek = Seek("seek1", alice, "chess", target=bob.username)
        app_state.seeks[seek.id] = seek

        self.assertEqual([], get_user_challenges(app_state, bob.username))

    async def test_terminal_corr_direct_challenges_do_not_count_toward_seek_limit(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)
        app_state.users[challenger.username] = challenger

        for idx in range(10):
            seek = Seek(
                f"seek-{idx}",
                challenger,
                "chess",
                day=3,
                target=f"opponent-{idx}",
                player1=challenger,
            )
            set_direct_challenge_status(seek, DIRECT_CHALLENGE_ACCEPTED)
            app_state.seeks[seek.id] = seek
            challenger.seeks[seek.id] = seek

        created = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "r",
                "minutes": 5,
                "increment": 3,
                "byoyomiPeriod": 0,
                "day": 3,
                "rated": False,
                "chess960": False,
            },
        )

        self.assertIsNotNone(created)

    def test_terminal_corr_direct_challenge_gets_short_expiry(self):
        app_state = self.make_app_state()
        challenger = User(app_state, username="alice", perfs=PERFS)

        seek = Seek("seek-accepted", challenger, "chess", day=3, target="bob", player1=challenger)
        before = datetime.now(UTC)
        set_direct_challenge_status(seek, DIRECT_CHALLENGE_ACCEPTED)
        after = datetime.now(UTC)

        self.assertIsNotNone(seek.expire_at)
        assert seek.expire_at is not None
        self.assertLessEqual(seek.expire_at, after + timedelta(hours=3, seconds=1))
        self.assertGreaterEqual(seek.expire_at, before + timedelta(hours=3) - timedelta(seconds=1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
