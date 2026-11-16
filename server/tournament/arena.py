from __future__ import annotations

import logging
import random
import time
from itertools import product
from typing import TYPE_CHECKING

import rustworkx as rx
from const import ARENA, T_FINISHED

from tournament.tournament import Tournament

if TYPE_CHECKING:
    from user import User

log = logging.getLogger(__name__)


class ArenaTournament(Tournament):
    system = ARENA
    color_streak_limit = 3

    async def finish(self, reason: str | None = None) -> None:
        # Match lila Arena behavior: tournaments that never produced a pairing are
        # junk/empty events, not completed tournament history.
        if not await self.has_pairing_history():
            if reason is not None:
                self.finish_reason = reason
            self.status = T_FINISHED
            await self.destroy()
            return
        await super().finish(reason)

    def just_played_together(self, x: User, y: User) -> bool:
        # Players can play consecutive games with each other
        # only in case when they are the only active players (duel)
        x_data = self.player_data_by_name(x.username)
        y_data = self.player_data_by_name(y.username)
        if x_data is None or y_data is None:
            return False
        return y.username == x_data.prev_opp or x.username == y_data.prev_opp

    def color_streak_problem(self, x: User, y: User) -> bool:
        # Match lila ColorHistory.couldPlay: one player must be able to switch colors.
        x_data = self.player_data_by_name(x.username)
        y_data = self.player_data_by_name(y.username)
        if x_data is None or y_data is None:
            return False
        return (
            x_data.color_streak >= self.color_streak_limit
            and y_data.color_streak >= self.color_streak_limit
        ) or (
            x_data.color_streak <= -self.color_streak_limit
            and y_data.color_streak <= -self.color_streak_limit
        )

    def create_pairing(self, waiting_players: list[User]) -> list[tuple[User, User]]:
        if len(waiting_players) < 2:
            return []

        if len(waiting_players) % 2:
            now = time.monotonic()

            def waiting_since(player: User) -> float:
                data = self.player_data_by_name(player.username)
                return (
                    data.waiting_since
                    if data is not None and data.waiting_since is not None
                    else now
                )

            # Match lila WaitingUsers.evenNumber and PairingSystem.evenOrAll.
            # Equal arrival times leave out the last player in leaderboard order.
            newest = max(reversed(waiting_players), key=waiting_since)
            older_waiters = [p for p in waiting_players if p.username != newest.username]
            pairing = self._create_pairing(older_waiters)
            if pairing:
                return pairing

        return self._create_pairing(waiting_players)

    def _create_pairing(self, waiting_players: list[User]) -> list[tuple[User, User]]:
        start = time.time()
        pairing = []

        nb_waiting_players = len(waiting_players)

        log.info("Waiting players: %s", nb_waiting_players)
        for p in waiting_players:
            log.debug("%20s %s", p.username, self.leaderboard[p])

        def pair_them(x, y):
            x_data = self.player_data_by_name(x.username)
            y_data = self.player_data_by_name(y.username)
            if x_data is None or y_data is None:
                log.warning(
                    "Skipping pairing in %s due missing player data: %s vs %s",
                    self.id,
                    x.username,
                    y.username,
                )
                return

            # Match lila ColorHistory.firstGetsWhite: streak, then balance, then chance.
            x_history = (x_data.color_streak, x_data.color_balance)
            y_history = (y_data.color_streak, y_data.color_balance)
            if x_history < y_history or (x_history == y_history and random.choice((True, False))):
                wp, bp = x, y
            else:
                wp, bp = y, x
            pairing.append((wp, bp))

        if nb_waiting_players == 2:
            x, y = waiting_players
            # A duel has only two available participants. Disconnected idle entrants
            # cannot be paired, so they must not block rematches. Players still in
            # a game count even when their tournament page is disconnected.
            only_two_active_players = (
                sum(
                    not data.paused
                    and not data.withdrawn
                    and (not data.free or bool(self.player_round_sockets(player, data)))
                    for player, data in self.players.items()
                )
                == 2
            )
            if only_two_active_players or (
                not self.just_played_together(x, y) and not self.color_streak_problem(x, y)
            ):
                pair_them(x, y)
            return pairing

        rxg = rx.PyGraph()
        rx_nodes = [rxg.add_node(p.username) for p in waiting_players]
        # print(rx_nodes)
        # print("---")

        rank_by_username = {p.username: i + 1 for i, p in enumerate(self.leaderboard)}
        ranks = [rank_by_username[p.username] for p in waiting_players]
        rank_max = max(ranks)

        # https://github.com/lichess-org/lila/blob/master/modules/tournament/src/main/arena/PairingSystem.scala
        def rank_factor(rank_a, rank_b):
            return 300 + 1700 * (rank_max - min(rank_a, rank_b)) // rank_max

        for pair in product(rx_nodes, rx_nodes):
            player_a = waiting_players[pair[0]]
            player_b = waiting_players[pair[1]]
            if (
                pair[0] != pair[1]
                and (not self.just_played_together(player_a, player_b))
                and (not self.color_streak_problem(player_a, player_b))
            ):
                rank_a = ranks[pair[0]]
                rank_b = ranks[pair[1]]
                player_a_data = self.player_data_by_name(player_a.username)
                player_b_data = self.player_data_by_name(player_b.username)
                if player_a_data is None or player_b_data is None:
                    continue
                rating_a = player_a_data.rating
                rating_b = player_b_data.rating

                # https://github.com/lichess-org/lila/blob/master/modules/tournament/src/main/arena/AntmaPairing.scala
                weight = abs(rank_a - rank_b) * rank_factor(rank_a, rank_b) + abs(
                    rating_a - rating_b
                )

                rxg.add_edge(pair[0], pair[1], weight)

        # print(rxg.edge_index_map())
        # print("---")

        # Pair as many players as possible, then minimize rank/rating distance.
        matching = rx.max_weight_matching(
            rxg, max_cardinality=True, weight_fn=lambda x: -x, verify_optimum=True
        )

        edges = list(rxg.edge_list())
        weights = rxg.edges()
        edge_index: dict[tuple[int, int], int] = {pair: i for i, pair in enumerate(edges)}
        sum_weight = 0
        for pair in matching:
            ind = edge_index[pair] if pair in edge_index else edge_index[(pair[1], pair[0])]
            sum_weight += weights[ind]
            sum_weight += weights[ind]
            log.debug("%r %r %r", rxg[pair[0]], rxg[pair[1]], weights[ind])

            pair_them(waiting_players[pair[0]], waiting_players[pair[1]])

        log.debug("len:%s weight_sum:%s", len(matching), sum_weight)

        for p in pairing:
            log.debug("Pairing: %s %s", p[0].username, p[1].username)

        end = time.time()
        log.info("Pairing time: %r", end - start)
        return pairing
