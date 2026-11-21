import asyncio
import logging
import random
from datetime import UTC, datetime

from const import (
    ARENA,
    BYEGAME,
    RR,
    STARTED,
    SWISS,
    TEST_PREFIX,
    VARIANTEND,
)
from draw import draw
from fairy import BLACK
from game import MAX_PLY
from glicko2.glicko2 import new_default_perf
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import play_move

from tournament.arena import ArenaTournament
from tournament.rr import RRTournament
from tournament.swiss import SwissTournament
from tournament.tournament import Tournament, upsert_tournament_to_db

log = logging.getLogger(__name__)

# from misc import timeit

AUTO_PLAY_TOURNAMENT_NAME = "Auto Play Tournament"
AUTO_PLAY_TOURNAMENT_ID = "12345678"


def _janggi_point_count_result(fen: str) -> str:
    board = fen.split(" ", 1)[0]
    cho_points = 0.0
    han_points = 1.5
    for piece in board:
        if piece == "P":
            cho_points += 2
        elif piece in ("A", "B"):
            cho_points += 3
        elif piece == "N":
            cho_points += 5
        elif piece == "C":
            cho_points += 7
        elif piece == "R":
            cho_points += 13
        elif piece == "p":
            han_points += 2
        elif piece in ("a", "b"):
            han_points += 3
        elif piece == "n":
            han_points += 5
        elif piece == "c":
            han_points += 7
        elif piece == "r":
            han_points += 13
    return "1-0" if cho_points > han_points else "0-1"


async def create_auto_play_tournament(app):
    app_state = get_app_state(app)
    tid = AUTO_PLAY_TOURNAMENT_ID
    if tid in app_state.tournaments:
        tournament = app_state.tournaments[tid]
        return

    await app_state.db.tournament.delete_one({"_id": tid})
    await app_state.db.tournament_player.delete_many({"tid": tid})
    await app_state.db.tournament_pairing.delete_many({"tid": tid})

    # tournament = ArenaTestTournament(
    tournament = SwissTestTournament(
        app_state,
        tid,
        variant="janggi",
        name=AUTO_PLAY_TOURNAMENT_NAME,
        chess960=False,
        base=1,
        before_start=0.5,
        minutes=10,
        created_by="PyChess",
        rounds=5,
        round_interval=10,
    )

    app_state.tournaments[tid] = tournament
    app_state.tourneysockets[tid] = {}

    await upsert_tournament_to_db(tournament, app_state)

    if tournament.nb_players == 0:
        await tournament.join_players(15)


class TestTournament(Tournament):
    clock_interval = 0.02

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_tasks = set()

    async def join_players(self, nb_players, rating=None):
        for i in range(1, nb_players + 1):
            name = "%sUser_%s" % (TEST_PREFIX, i)
            player = User(
                self.app_state,
                username=name,
                title="TEST",
            )
            if rating is not None:
                player.perfs[self.variant] = new_default_perf()
                player.perfs[self.variant]["gl"]["r"] = rating
            self.app_state.users[player.username] = player
            player.tournament_sockets[self.id] = {None}
            result = await self.join(player)
            if result is not None:
                log.debug(
                    "AUTO JOIN refused: %s in tournament %s (%s)",
                    player.username,
                    self.id,
                    result,
                )

    async def _auto_complete_janggi_setup(self, game) -> None:
        if game.variant != "janggi":
            return
        if not game.bsetup and not game.wsetup:
            return

        if game.bsetup:
            game.board.janggi_setup("b")
            game.bsetup = False
        if game.wsetup:
            game.board.janggi_setup("w")
            game.wsetup = False

        game.initial_fen = game.board.initial_fen
        game.steps[0]["fen"] = game.board.initial_fen
        await game.save_setup()

    async def create_new_pairings(self, waiting_players, *, publish_pairings: bool = True):
        now = datetime.now(UTC).strftime("%H:%M:%S")
        log.info("--- create_new_pairings at %s ---" % now)
        self.print_leaderboard()
        pairing, games = await Tournament.create_new_pairings(
            self,
            waiting_players,
            publish_pairings=publish_pairings,
        )

        # aouto play test games
        # for wp, bp in pairing:
        #     print("%s - %s" % (wp.username, bp.username))
        log.info("--- create_new_pairings done ---")

        for game in games:
            if game.status == BYEGAME:  # ByeGame
                continue
            self.app_state.games[game.id] = game
            await self._auto_complete_janggi_setup(game)
            if self.id == AUTO_PLAY_TOURNAMENT_ID:
                # Keep the optional developer autoplay tournament realistic.
                self.game_tasks.add(asyncio.create_task(self.play_random(game)))
            elif self.with_clock and game.wplayer.title == "TEST" and game.bplayer.title == "TEST":
                self.game_tasks.add(asyncio.create_task(self.finish_test_game(game)))

        return pairing, games

    async def finish_test_game(self, game) -> None:
        """Finish synthetic TEST-vs-TEST games through the real game-end path."""
        if game.status == BYEGAME:  # ByeGame
            return

        # Tournament tests exercise pairing, scoring, persistence, and lifecycle
        # behavior. Replaying dozens of random legal moves per synthetic game makes
        # those tests needlessly slow; the move engine has dedicated tests. A real
        # resignation still runs Game.save_game() and Tournament.game_update().
        game.status = max(game.status, STARTED)
        loser = game.wplayer if sum(game.id.encode()) % 2 == 0 else game.bplayer
        await game.game_ended(loser, "resign")

    # @timeit
    async def play_random(self, game):
        """Play random moves for TEST players"""
        if game.status == BYEGAME:  # ByeGame
            return

        if self.system == ARENA:
            if random.choice((True, False)):
                game.berserk("white")

            if random.choice((True, False)):
                game.berserk("black")

            await asyncio.sleep(random.choice((0, 0.1, 0.3, 0.5, 0.7)))

        while game.status <= STARTED:
            if game.variant == "janggi" and (game.bsetup or game.wsetup):
                # Respect Janggi setup order; autoplay must wait for setup completion.
                await asyncio.sleep(0.01)
                continue

            game.status = max(game.status, STARTED)

            cur_player = game.bplayer if game.board.color == BLACK else game.wplayer
            opp_player = game.wplayer if game.board.color == BLACK else game.bplayer
            if cur_player.title == "TEST":
                ply = random.randint(20, int(MAX_PLY / 10))
                if game.board.ply == ply or game.board.ply > 60:
                    player = game.wplayer if ply % 2 == 0 else game.bplayer
                    if game.variant == "janggi" and game.board.ply > 60:
                        game.update_status(VARIANTEND, _janggi_point_count_result(game.board.fen))
                        await game.save_game()
                        response = {
                            "type": "gameEnd",
                            "status": game.status,
                            "result": game.result,
                            "gameId": game.id,
                            "pgn": game.pgn,
                            "ct": game.crosstable,
                            "rdiffs": "",
                        }
                    elif game.board.ply > 60:
                        response = await draw(game, cur_player.username, agreement=True)
                    else:
                        response = await game.game_ended(player, "resign")
                    if opp_player.title != "TEST":
                        await opp_player.send_game_message(game.id, response)
                else:
                    move = random.choice(game.legal_moves)
                    clocks = [game.clocks_w[-1], game.clocks_b[-1]]
                    try:
                        await play_move(self.app_state, cur_player, game, move, clocks=clocks)
                    except IndexError:
                        # Test teardown can abort/reset a game while this helper task is still moving.
                        # Exit quietly to avoid surfacing cleanup races as test failures.
                        return
            await asyncio.sleep(0.01)


class ArenaTestTournament(TestTournament, ArenaTournament):
    system = ARENA

    def create_pairing(self, waiting_players: list[User]) -> list[tuple[User, User]]:
        return ArenaTournament.create_pairing(self, waiting_players)


class RRTestTournament(TestTournament, RRTournament):
    system = RR

    def create_pairing(self, waiting_players: list[User]) -> list[tuple[User, User]]:
        return RRTournament.create_pairing(self, waiting_players)

    async def start_arrangement_game(self, arrangement_id: str, *, challenger: str | None = None):
        arrangement = self.arrangement_by_id(arrangement_id)
        if arrangement is None:
            raise AssertionError(f"Unknown arrangement {arrangement_id}")

        challenger_name = arrangement.white if challenger is None else challenger
        challenger_user = self.app_state.users[challenger_name]
        challenge_error = await self.create_arrangement_challenge(challenger_user, arrangement_id)
        if challenge_error is not None:
            raise AssertionError(challenge_error)

        opponent_name = arrangement.opponent(challenger_name)
        if opponent_name is None:
            raise AssertionError(
                f"Arrangement {arrangement_id} has no opponent for {challenger_name}"
            )

        opponent_user = self.app_state.users[opponent_name]
        response = await self.accept_arrangement_challenge(opponent_user, arrangement_id)
        if response["type"] != "new_game":
            raise AssertionError(f"Unexpected RR challenge response: {response}")
        return self.app_state.games[response["gameId"]]


class SwissTestTournament(TestTournament, SwissTournament):
    system = SWISS

    def create_pairing(self, waiting_players: list[User]) -> list[tuple[User, User]]:
        return SwissTournament.create_pairing(self, waiting_players)
