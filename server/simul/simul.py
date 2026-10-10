from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import settings
from const import CASUAL, STARTED, T_ABORTED, T_CREATED, T_FINISHED, T_STARTED
from game import Game
from newid import new_id
from team import is_enabled_team_member
from tournament_director import is_tournament_director
from utils import REALTIME_GAME_IN_PROGRESS_MESSAGE, insert_game_to_db, realtime_game_conflict
from variants import get_server_variant, is_catalogued_variant
from websocket_utils import ws_send_json_many

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
    from ws_types import ChatLine


# Lichess ties simul admission to its general realtime-playing capacity (100).
# PyChess runs on a much smaller server, so keep one host from creating more than
# 50 live games at once. Keep this as a single explicit constant so it can be
# raised later if production measurements show that is safe.
MAX_SIMUL_OPPONENTS = 50
MAX_SIMUL_VARIANTS = 20
SIMUL_ERASED_USER = "<erased>"


def split_simul_variant_key(variant_key: str) -> tuple[str, bool]:
    chess960 = False if is_catalogued_variant(variant_key) else variant_key.endswith("960")
    return (variant_key[:-3] if chess960 else variant_key), chess960


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in settings.ADMINS)


def _is_top_ten_in_any_variant(
    app_state: PychessGlobalAppState, username: str, variants: list[str]
) -> bool:
    for variant_key in variants:
        scores = app_state.highscore.get(variant_key)
        if scores is None:
            continue
        for identity in scores.keys()[:10]:
            top_username, _separator, _title = str(identity).partition("|")
            if top_username == username:
                return True
    return False


def is_simul_featurable(
    app_state: PychessGlobalAppState,
    host: User,
    variants: list[str],
    entry_team_id: str | None,
) -> bool:
    """Return whether a simul may be featured on the public simul home page.

    Team-restricted simuls are intentionally never featured globally. Otherwise
    PyChess features established hosts: titled players, site admins, tournament
    directors, or a current Top 10 player in any offered rated variant.
    """
    if host.anon or host.bot or entry_team_id is not None:
        return False
    if host.title and host.title != "BOT":
        return True
    if _is_admin_username(host.username):
        return True
    if is_tournament_director(host, app_state):
        return True
    return _is_top_ten_in_any_variant(app_state, host.username, variants)


class Simul:
    """
    Standalone Simul class
    """

    def __init__(
        self,
        app_state,
        simul_id,
        name,
        created_by,
        variants=None,
        variant="chess",
        chess960=False,
        rated=False,
        base=1,
        inc=0,
        host_color="random",
        description="",
        fen="",
        host_extra_time=0,
        host_extra_time_per_player=0,
        estimated_start_at=None,
        entry_min_rating=0,
        entry_max_rating=0,
        entry_min_rated_games=0,
        entry_min_account_age_days=0,
        entry_titled_only=False,
        entry_team_id=None,
        entry_team_name=None,
        featurable=False,
    ):
        self.app_state = app_state
        self.id = simul_id
        self.name = name
        self.created_by = created_by
        if variants is None:
            variants = [variant + ("960" if chess960 else "")]
        self.variants = list(dict.fromkeys(variants))
        if not self.variants:
            raise ValueError("A simul must offer at least one variant")
        if len(self.variants) > MAX_SIMUL_VARIANTS:
            raise ValueError(f"A simul can offer at most {MAX_SIMUL_VARIANTS} variants")
        if fen and len(self.variants) != 1:
            raise ValueError("A custom starting position requires exactly one simul variant")
        self.fen = fen
        self.rated = rated
        self.base = base
        self.inc = inc
        self.host_color = host_color
        self.description = description
        self.host_extra_time = host_extra_time
        self.host_extra_time_per_player = host_extra_time_per_player
        self.estimated_start_at = estimated_start_at
        self.entry_min_rating = entry_min_rating
        self.entry_max_rating = entry_max_rating
        self.entry_min_rated_games = entry_min_rated_games
        self.entry_min_account_age_days = entry_min_account_age_days
        self.entry_titled_only = entry_titled_only
        self.entry_team_id = entry_team_id
        self.entry_team_name = entry_team_name
        self.featurable = featurable

        self.players: dict[str, User] = {}
        self.player_variants: dict[str, str] = {}
        self.pending_players: dict[str, User] = {}
        self.pending_player_variants: dict[str, str] = {}
        self.games: dict[str, Game] = {}
        self.ongoing_games: set[Game] = set()
        self.host_game_id: str | None = None
        self._admission_error: str | None = None
        self.clock_task: asyncio.Task[None] | None = None
        self.status = T_CREATED
        self.created_at = datetime.now(UTC)
        self.host_seen_at = self.created_at
        self.starts_at: datetime | None = None
        self.ends_at: datetime | None = None
        self.spectators: set[User] = set()
        self.tourneychat = []

    @classmethod
    async def create(cls, app_state, simul_id, name, created_by, **kwargs):
        simul = cls(app_state, simul_id, name, created_by, **kwargs)
        host = await app_state.users.get(created_by)
        if host:
            simul.players[created_by] = host
            simul.player_variants[created_by] = simul.variants[0]
            simul.refresh_featurable(host)
        return simul

    def refresh_featurable(self, host: User) -> None:
        self.featurable = is_simul_featurable(
            self.app_state,
            host,
            self.variants,
            self.entry_team_id,
        )

    @property
    def primary_variant_key(self) -> str:
        return self.variants[0]

    @property
    def variant(self) -> str:
        variant, _chess960 = split_simul_variant_key(self.primary_variant_key)
        return variant

    @property
    def chess960(self) -> bool:
        _variant, chess960 = split_simul_variant_key(self.primary_variant_key)
        return chess960

    def player_json(self, user: User, variant_key: str) -> dict[str, object]:
        variant, chess960 = split_simul_variant_key(variant_key)
        return {
            "name": user.username,
            "title": user.title,
            "rating": user.get_rating_value(variant, chess960),
            "variant": variant_key,
        }

    def host_clock_initial_ms(self) -> int:
        total_seconds = (self.base * 60) + self.host_extra_time
        return max(total_seconds, 20) * 1000

    def host_extra_time_valid(self) -> bool:
        total_seconds = (self.base * 60) + self.host_extra_time
        if total_seconds == 0:
            return self.inc >= 10
        return total_seconds > 0

    def players_json(self) -> list[dict[str, object]]:
        return [
            self.player_json(player, self.player_variants.get(key, self.primary_variant_key))
            for key, player in self.players.items()
        ]

    def pending_players_json(self) -> list[dict[str, object]]:
        return [
            self.player_json(
                player, self.pending_player_variants.get(key, self.primary_variant_key)
            )
            for key, player in self.pending_players.items()
        ]

    def game_json(self, game: Game) -> dict[str, object]:
        host_side = game.simulHostColor
        if host_side not in ("w", "b"):
            raise ValueError(f"Simul game {game.id} is missing persisted host side")
        return {
            "gameId": game.id,
            "wplayer": game.wplayer.username,
            "bplayer": game.bplayer.username,
            "hostSide": "white" if host_side == "w" else "black",
            "variant": game.variant + ("960" if game.chess960 else ""),
            "fen": game.fen,
            "lastMove": game.lastmove,
            "rated": bool(game.rated),
            "base": game.base,
            "inc": game.inc,
            "byo": game.byoyomi_period,
            "status": game.status,
            "result": game.result,
        }

    def all_games_json(self) -> list[dict[str, object]]:
        return [self.game_json(game) for game in self.games.values()]

    @property
    def opponent_count(self) -> int:
        return max(0, len(self.players) - (self.created_by in self.players))

    def capacity_error(self) -> str | None:
        if self.opponent_count >= MAX_SIMUL_OPPONENTS:
            return f"This simul already has the maximum of {MAX_SIMUL_OPPONENTS} accepted players."
        return None

    def join(self, user: User, variant_key: str | None = None) -> bool:
        if variant_key is None:
            if len(self.variants) != 1:
                return False
            variant_key = self.primary_variant_key
        if self.status != T_CREATED:
            return False
        if (
            user.username == self.created_by
            or user.username in self.players
            or user.username in self.pending_players
            or variant_key not in self.variants
            or self.capacity_error() is not None
        ):
            return False
        self.pending_players[user.username] = user
        self.pending_player_variants[user.username] = variant_key
        return True

    async def entry_condition_error(self, user: User, variant_key: str | None = None) -> str | None:
        if user.anon:
            return "Anonymous users cannot join simuls."
        if user.bot:
            return "BOT accounts cannot join simuls."

        if variant_key is None:
            if len(self.variants) != 1:
                return "Choose one of the variants offered by this simul."
            variant_key = self.primary_variant_key
        if variant_key not in self.variants:
            return "This variant is not offered by this simul."

        variant, chess960 = split_simul_variant_key(variant_key)
        perf_key = variant + ("960" if chess960 else "")
        perf = user.perfs.get(perf_key, {})
        try:
            rated_games = int(perf.get("nb", 0))
        except (TypeError, ValueError):
            rated_games = 0

        if self.entry_min_rated_games > 0 and rated_games < self.entry_min_rated_games:
            return "This simul requires at least %s rated %s games." % (
                self.entry_min_rated_games,
                perf_key.upper() if chess960 else variant.title(),
            )

        if self.entry_min_account_age_days > 0:
            account_age = datetime.now(UTC) - user.created_at
            if account_age < timedelta(days=self.entry_min_account_age_days):
                return "This simul requires accounts to be at least %s days old." % (
                    self.entry_min_account_age_days,
                )

        rating = user.get_rating_value(variant, chess960)
        if self.entry_min_rating > 0 and rating < self.entry_min_rating:
            return "Your rating is below the minimum allowed for this simul."
        if self.entry_max_rating > 0 and rating > self.entry_max_rating:
            return "Your rating is above the maximum allowed for this simul."

        if self.entry_team_id is not None and not await is_enabled_team_member(
            self.app_state, self.entry_team_id, user.username
        ):
            team_name = self.entry_team_name or self.entry_team_id
            return f"You must be a member of {team_name} to join this simul."

        return None

    def approve(self, username: str | None) -> bool:
        if self.status != T_CREATED or self.capacity_error() is not None:
            return False
        if username in self.pending_players:
            user = self.pending_players[username]
            variant_key = self.pending_player_variants[username]
            del self.pending_players[username]
            del self.pending_player_variants[username]
            self.players[username] = user
            self.player_variants[username] = variant_key
            return True
        return False

    def deny(self, username: str | None) -> bool:
        if self.status != T_CREATED:
            return False
        if username is None or username == self.created_by:
            return False
        if username in self.pending_players:
            del self.pending_players[username]
            self.pending_player_variants.pop(username, None)
            return True
        if username in self.players:
            del self.players[username]
            self.player_variants.pop(username, None)
            return True
        return False

    def withdraw(self, user: User) -> bool:
        if self.status != T_CREATED or user.username == self.created_by:
            return False
        if user.username in self.pending_players:
            del self.pending_players[user.username]
            self.pending_player_variants.pop(user.username, None)
            return True
        if user.username in self.players:
            del self.players[user.username]
            self.player_variants.pop(user.username, None)
            return True
        return False

    def add_spectator(self, user: User):
        self.spectators.add(user)

    def remove_spectator(self, user: User):
        self.spectators.discard(user)

    async def broadcast(self, response):
        sockets = []
        for spectator in self.spectators:
            if self.id in spectator.simul_sockets:
                sockets.extend(list(spectator.simul_sockets[self.id]))
        await ws_send_json_many(sockets, response)

    async def broadcast_spotlight(self) -> None:
        from lobby_spotlights import broadcast_lobby_spotlights

        await broadcast_lobby_spotlights(self.app_state)

    async def simul_chat_save(self, response: ChatLine) -> None:
        self.tourneychat.append(response)
        if self.app_state.db is None:
            return

        response_db: ChatLine = {
            "type": response["type"],
            "user": response["user"],
            "message": response["message"],
        }
        if "room" in response:
            response_db["room"] = response["room"]
        if "time" in response:
            response_db["time"] = response["time"]
        response_db["sid"] = self.id
        await self.app_state.db.simul_chat.insert_one(response_db)

    def set_variants(self, variants: list[str]) -> list[str]:
        if not variants:
            raise ValueError("A simul must offer at least one variant")
        if len(variants) > MAX_SIMUL_VARIANTS:
            raise ValueError(f"A simul can offer at most {MAX_SIMUL_VARIANTS} variants")
        self.variants = list(dict.fromkeys(variants))
        removed: list[str] = []

        for key in tuple(self.pending_players):
            if self.pending_player_variants.get(key) not in self.variants:
                removed.append(self.pending_players[key].username)
                del self.pending_players[key]
                self.pending_player_variants.pop(key, None)

        for key in tuple(self.players):
            if key == self.created_by:
                self.player_variants[key] = self.primary_variant_key
                continue
            if self.player_variants.get(key) not in self.variants:
                removed.append(self.players[key].username)
                del self.players[key]
                self.player_variants.pop(key, None)
        return removed

    def missing_opponents(self) -> list[tuple[User, str]]:
        """Return accepted opponent slots that do not yet have a simul game."""
        missing = [
            (player, self.player_variants.get(key, self.primary_variant_key))
            for key, player in self.players.items()
            if key != self.created_by
        ]

        for game in self.games.values():
            if not missing:
                break
            if game.simulHostColor == "w":
                opponent_name = game.bplayer.username
            elif game.simulHostColor == "b":
                opponent_name = game.wplayer.username
            else:
                continue

            game_variant = game.variant + ("960" if game.chess960 else "")

            match_index = next(
                (
                    i
                    for i, (player, variant_key) in enumerate(missing)
                    if player.username == opponent_name and variant_key == game_variant
                ),
                None,
            )
            if match_index is None:
                # GDPR anonymization can change the persisted simul participant name
                # before the corresponding historical game document is scrubbed. Every
                # existing game still consumes one accepted-opponent slot, so prefer an
                # erased placeholder and otherwise consume the first unmatched slot.
                match_index = next(
                    (
                        i
                        for i, (player, variant_key) in enumerate(missing)
                        if player.username == SIMUL_ERASED_USER and variant_key == game_variant
                    ),
                    next(
                        (
                            i
                            for i, (_player, variant_key) in enumerate(missing)
                            if variant_key == game_variant
                        ),
                        None,
                    ),
                )
            if match_index is not None:
                missing.pop(match_index)

        return missing

    async def create_games(self, *, admission_locked: bool = False) -> list[Game]:
        if not admission_locked:
            async with self.app_state.realtime_game_creation_lock:
                return await self.create_games(admission_locked=True)

        created_games: list[Game] = []
        host = self.players.get(self.created_by)
        if host is None:
            return created_games

        # Game creation is intentionally idempotent per accepted opponent. A server
        # restart can occur after the simul is marked started but before every game
        # has been inserted; recovery calls this method again to fill only the gaps.
        opponents = self.missing_opponents()
        random.shuffle(opponents)

        game_table = self.app_state.db.game if self.app_state.db else None

        for opponent, variant_key in opponents:
            conflict = realtime_game_conflict(
                self.app_state,
                (host, opponent),
                allowed_simul_id=self.id,
                simul_host_username=self.created_by,
            )
            if conflict is not None:
                player, _active_game = conflict
                # Recovery can encounter an opponent who started another game
                # after accepting the simul but before the missing board was
                # recreated. Never manufacture a second realtime game.
                self._admission_error = f"{player.username}: {REALTIME_GAME_IN_PROGRESS_MESSAGE}"
                continue

            game_id = await new_id(game_table)
            variant, chess960 = split_simul_variant_key(variant_key)
            server_variant = get_server_variant(variant, chess960)

            if self.host_color == "white":
                wp, bp = host, opponent
            elif self.host_color == "black":
                wp, bp = opponent, host
            else:  # random
                if random.choice([True, False]):
                    wp, bp = host, opponent
                else:
                    wp, bp = opponent, host

            host_side = "w" if wp is host else "b"
            host_initial_ms = self.host_clock_initial_ms()
            opponent_initial_ms = (self.base * 60 * 1000) if self.base > 0 else self.inc * 1000
            if wp is host:
                initial_clocks = (host_initial_ms, opponent_initial_ms)
            else:
                initial_clocks = (opponent_initial_ms, host_initial_ms)

            game = Game(
                self.app_state,
                game_id,
                server_variant.uci_variant,
                self.fen,
                wp,
                bp,
                base=self.base,
                inc=self.inc,
                rated=CASUAL,
                chess960=server_variant.chess960,
                simulId=self.id,
                initial_clocks=initial_clocks,
            )
            game.simulHostColor = host_side
            self.games[game.id] = game
            self.ongoing_games.add(game)
            self.app_state.games[game_id] = game
            await insert_game_to_db(game, self.app_state)
            created_games.append(game)

            response = {"type": "new_game", **self.game_json(game)}
            await self.broadcast(response)
        return created_games

    def start_error(self) -> str | None:
        if self._admission_error is not None:
            return self._admission_error
        if self.status != T_CREATED:
            return "This simul has already started"
        if self.opponent_count < 2:
            return "Cannot start simul with fewer than 2 opponents"
        if self.opponent_count > MAX_SIMUL_OPPONENTS:
            return f"Cannot start simul with more than {MAX_SIMUL_OPPONENTS} opponents"
        if not self.host_extra_time_valid():
            return "Invalid host extra time for this clock setup"
        return None

    async def start(self) -> bool:
        self._admission_error = None
        if self.start_error() is not None:
            return False

        async with self.app_state.realtime_game_creation_lock:
            host = self.players.get(self.created_by)
            if host is None:
                return False
            conflict = realtime_game_conflict(self.app_state, self.players.values())
            if conflict is not None:
                player, _active_game = conflict
                self._admission_error = f"{player.username}: {REALTIME_GAME_IN_PROGRESS_MESSAGE}"
                return False

            self.status = T_STARTED
            self.starts_at = datetime.now(UTC)
            self.host_extra_time += (len(self.players) - 1) * self.host_extra_time_per_player
            from simul.simuls import upsert_simul_to_db

            await upsert_simul_to_db(self)
            await self.create_games(admission_locked=True)
            await upsert_simul_to_db(self)

        await self.broadcast({"type": "simul_started"})
        await self.broadcast_spotlight()
        self.clock_task = asyncio.create_task(self.clock(), name=f"simul-clock-{self.id}")
        return True

    async def finish(self):
        if self.status == T_STARTED:
            self.status = T_FINISHED
            self.ends_at = datetime.now(UTC)
            self.host_game_id = None
            if self.clock_task is not None:
                self.clock_task.cancel()
            from simul.simuls import upsert_simul_to_db

            await upsert_simul_to_db(self)
            await self.broadcast({"type": "simul_finished"})

    async def abort(self):
        if self.status == T_CREATED:
            self.status = T_ABORTED
            self.ends_at = datetime.now(UTC)
            from simul.simuls import upsert_simul_to_db

            await upsert_simul_to_db(self)
            await self.broadcast_spotlight()

    async def game_update(self, game):
        response = {
            "type": "game_update",
            "gameId": game.id,
            "fen": game.fen,
            "lastMove": game.lastmove,
            "status": game.status,
            "result": game.result,
        }
        if game.status > STARTED:
            self.ongoing_games.discard(game)
            if len(self.ongoing_games) == 0:
                await self.finish()
        await self.broadcast(response)

    async def clock(self):
        while self.status == T_STARTED:
            if len(self.ongoing_games) == 0:
                await self.finish()
                break

            finished_games = {g for g in self.ongoing_games if g.status > STARTED}
            self.ongoing_games -= finished_games

            await asyncio.sleep(5)
