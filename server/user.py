from __future__ import annotations

import asyncio
import random
import re
from asyncio import Queue
from collections.abc import Container, Coroutine, Mapping
from datetime import MINYEAR, UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp_session
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from broadcast import round_broadcast
from catalogued_rules import PIECE_OPTION_NAMES
from const import (
    ANON_PREFIX,
    BLOCK,
    CATEGORY_VARIANT_CODES,
    CATEGORY_VARIANT_GROUPS,
    CATEGORY_VARIANT_LISTS,
    CATEGORY_VARIANT_SETS,
    CATEGORY_VARIANTS,
    FOLLOW,
    GAME_CATEGORY_ALL,
    MAX_USER_BLOCK,
    STARTED,
    SYSTEM_USER,
    TEST_PREFIX,
    normalize_game_category,
    reserved,
)
from glicko2.glicko2 import MU, Rating, gl2, sparse_perf_map
from json_utils import json_response
from newid import id8
from notify import notify
from preferences import effective_game_category, effective_theme
from pymongo.errors import DuplicateKeyError
from request_protection import enforce_new_anonymous_identity_limit
from typedefs import REQUEST_NEW_SESSION_KEY
from user_stats import DEFAULT_USER_COUNT, normalize_user_count
from websocket_utils import ws_send_json_many

if TYPE_CHECKING:
    from typing_defs import (
        NotificationContent,
        NotificationDocument,
        PerfEntry,
        PerfGl,
        UserBlocksResponse,
        UserCount,
        UserJson,
        UserStatusJson,
    )
from redirects import safe_redirect_path
from request_utils import read_post_data
from settings import (
    LOCALHOST,
    URI,
)
from variants import RATED_VARIANTS, VARIANTS

if TYPE_CHECKING:
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from seek import Seek

import logging

from pychess_global_app_state_utils import get_app_state

log = logging.getLogger(__name__)

# Matches the registered-username limit enforced in login.py, so a test name is
# never longer than a name a real account could hold.
TEST_USERNAME_MAX_LENGTH = 20

# How many random pairs to try before falling back to a numeric suffix.
TEST_USERNAME_ATTEMPTS = 10


def _camel_case(value: str) -> str:
    return "".join(word.capitalize() for word in re.split(r"[^A-Za-z0-9]+", value) if word)


# Piece labels the server already ships, CamelCased so that multi-word and
# hyphenated entries stay usable: "shogi pawn" -> "ShogiPawn". 38 entries
# collapse to 37 distinct words, all alphanumeric and letter-initial.
_TEST_NAME_WORDS = sorted({_camel_case(name) for name in PIECE_OPTION_NAMES.values()})


def _test_name_pair() -> str:
    """Two different piece words, trimmed to the length budget, e.g. KnightCannon."""
    first, second = random.sample(_TEST_NAME_WORDS, 2)
    return (first + second)[: TEST_USERNAME_MAX_LENGTH - len(TEST_PREFIX)]


def _generate_test_username(taken: Container[str]) -> str:
    """A readable, unused name for a -a mode guest, e.g. Test–KnightCannon."""
    for _ in range(TEST_USERNAME_ATTEMPTS):
        username = TEST_PREFIX + _test_name_pair()
        if username not in taken:
            return username

    # Every attempt collided. Add a counter, trimming the pair so the counter
    # fits the budget rather than overflowing it — dropping the counter instead
    # would hand back a name that is already in use. Piece words hold no digits,
    # so each counter yields a distinct name and this terminates.
    pair = _test_name_pair()
    counter = 2
    while True:
        suffix = str(counter)
        trimmed = pair[: TEST_USERNAME_MAX_LENGTH - len(TEST_PREFIX) - len(suffix)]
        username = TEST_PREFIX + trimmed + suffix
        if username not in taken:
            return username
        counter += 1


SILENCE = 15 * 60
ANON_TIMEOUT = 10 * 60
# Fresh anons that never established any socket connection are likely one-off
# page hits (often crawlers/no-cookie clients). Keep them much shorter-lived.
ANON_NEVER_CONNECTED_TIMEOUT = 60
PENDING_SEEK_TIMEOUT = 10
ABANDON_TIMEOUT = 30


class RatingResetError(Exception):
    """Raised when new User object created with perft=None, but user already exists in leaderboards"""


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _as_required_utc(dt: datetime) -> datetime:
    normalized = _as_utc(dt)
    assert normalized is not None
    return normalized


class User:
    def __init__(
        self,
        app_state: PychessGlobalAppState,
        bot: bool = False,
        username: str | None = None,
        anon: bool = False,
        title: str = "",
        perfs: Mapping[str, Mapping[str, object]] | None = None,
        pperfs: Mapping[str, Mapping[str, object]] | None = None,
        count: UserCount | None = None,
        enabled: bool = True,
        shadowban: bool = False,
        lang: str | None = None,
        theme: str = "dark",
        game_category: str = "all",
        pm_friends_only: bool = False,
        corr_push: bool = True,
        rr_push: bool = False,
        catalogued_variant_favorites: list[str] | set[str] | None = None,
        oauth_id: str = "",
        oauth_provider: str = "",
        created_at: datetime | None = None,
        swiss_ban_until: datetime | None = None,
        swiss_ban_hours: int = 0,
        swiss_ban_game_id: str | None = None,
        patron: bool = False,
        chat_timeout_until: datetime | None = None,
        tournament_points: float = 0,
        forum_posts: int = 0,
        variant_count: int = 0,
        auth_version: int = 0,
    ) -> None:
        self.app_state: PychessGlobalAppState = app_state
        self.bot: bool = bot
        self.anon: bool = anon
        self.lang: str | None = lang
        self.theme: str = theme
        self.game_category: str = "all"
        self.game_category_set: bool = False
        self.pm_friends_only: bool = pm_friends_only
        self.corr_push_enabled: bool = corr_push
        self.rr_push_enabled: bool = rr_push
        self.catalogued_variant_favorites: set[str] = {
            str(name) for name in (catalogued_variant_favorites or []) if isinstance(name, str)
        }
        self.oauth_id: str = oauth_id
        self.oauth_provider: str = oauth_provider
        self.auth_version: int = auth_version
        self.created_at: datetime = (
            datetime(MINYEAR, 1, 1, tzinfo=UTC)
            if created_at is None
            else _as_required_utc(created_at)
        )
        self.swiss_ban_until: datetime | None = _as_utc(swiss_ban_until)
        self.swiss_ban_hours: int = swiss_ban_hours
        self.swiss_ban_game_id: str | None = swiss_ban_game_id
        self.chat_timeout_until: datetime | None = _as_utc(chat_timeout_until)
        self.notifications: list[NotificationDocument] | None = None
        self.update_game_category(game_category)

        if username is None:
            self.anon = not self.app_state.anon_as_test_users
            self.username: str = (
                ANON_PREFIX + id8() if self.anon else _generate_test_username(self.app_state.users)
            )
        else:
            self.username = username

        self.seeks: dict[str, Seek] = {}

        self.ready_for_auto_pairing: bool = False
        self.lobby_sockets: set[WebSocketResponse] = set()
        # Every browser-authenticated websocket is also registered here by
        # process_ws(), so logout can revoke already-open channels atomically.
        self.authenticated_sockets: set[WebSocketResponse] = set()
        self.tournament_sockets: dict[
            str, set[WebSocketResponse | None]
        ] = {}  # {tournamentId: set()}
        self.simul_sockets: dict[str, set[WebSocketResponse]] = {}  # {simulId: set()}
        self.study_sockets: dict[str, set[WebSocketResponse]] = {}  # {studyId: set()}

        self.notify_channels: set[Queue[str]] = set()
        self.inbox_channels: set[Queue[str]] = set()
        self.challenge_channels: set[Queue[str]] = set()
        self.challenge_offline_task: asyncio.Task[None] | None = None

        self.puzzles: dict[
            str, int
        ] = {}  # {pizzleId: vote} where vote 0 = not voted, 1 = up, -1 = down
        self.puzzle_variant: str | None = None

        self.game_sockets: dict[str, set[WebSocketResponse]] = {}
        self.title: str = title
        self.game_in_progress: str | None = None
        self.abandon_game_tasks: dict[str, asyncio.Task[None]] = {}
        self.background_tasks: set[asyncio.Task[None]] = set()
        self.correspondence_games: list[Game] = []

        # Reverse-index of game ids this user is currently spectating, kept in
        # sync with game.spectators.add()/discard() (see wsr.py). Lets
        # clear_spectator_references() drop stale spectator entries in
        # O(watched games) instead of scanning every active game on the server.
        self.watched_games: set[str] = set()

        self.blocked: set[str] = set()
        self.following: set[str] = set()

        if self.bot:
            self.enable_bot_account()

        self.online: bool = False
        self.ever_connected: bool = False

        if perfs is None and (not self.anon) and (not self.bot):
            # User() with perfs=None can be dangerous
            _id = "%s|%s" % (self.username, self.title)
            hs = app_state.highscore
            if any(_id in hs[variant] for variant in RATED_VARIANTS):
                raise RatingResetError(
                    "%s User() called with perfs=None. Use await users.get() instead.", username
                )

        self.perfs = sparse_perf_map(RATED_VARIANTS, perfs)
        self.pperfs = sparse_perf_map(RATED_VARIANTS, pperfs)
        self.count = normalize_user_count(count)
        self.tournament_points = tournament_points
        self.forum_posts = forum_posts
        self.variant_count = variant_count
        self.tournament_game_effect_ids: set[str] = set()

        self.enabled: bool = enabled
        self.shadowban: bool = shadowban
        self.patron: bool = patron

        self.last_seen: datetime = datetime(MINYEAR, 1, 1, tzinfo=UTC)

        # last game played
        self.tv: str | None = None

        # purge inactive anon users after ANON_TIMEOUT sec
        if self.anon and not reserved(self.username):
            task = self.create_background_task(
                self.remove(),
                name="user-remove-%s" % self.username,
            )
            self.remove_anon_task: asyncio.Task[None] | None = task
        else:
            self.remove_anon_task = None

    def enable_bot_account(self) -> None:
        self.bot = True
        self.title = "BOT"
        if not hasattr(self, "event_queue"):
            self.event_queue = asyncio.Queue()
        if not hasattr(self, "game_queues"):
            self.game_queues = {}
        if not hasattr(self, "active_game_streams"):
            self.active_game_streams = set()
        if not hasattr(self, "bot_online_expire_task"):
            self.bot_online_expire_task: asyncio.Task[None] | None = None
        if not hasattr(self, "bot_supported_variants"):
            # External BOTs replace this during their authenticated event-stream
            # handshake. None is reserved for PyChess's built-in BOTs.
            self.bot_supported_variants: set[str] | None = None

    async def remove(self) -> None:
        def can_remove_anon() -> bool:
            self.update_online()
            return not (
                self.online
                or self.game_in_progress is not None
                or self.correspondence_games
                or self.is_user_active_in_game()
                or self.is_user_active_in_lobby()
            )

        async def remove_from_cache() -> None:
            for seek_id, seek in tuple(self.seeks.items()):
                self.app_state.seeks.pop(seek_id, None)
                if seek.game_id is not None:
                    self.app_state.invites.pop(seek.game_id, None)
                self.seeks.pop(seek_id, None)

            await self.clear_spectator_references()

            # This task may race with other anon cleanup paths that already removed
            # or replaced the cache entry for this username.
            current = self.app_state.users.data.get(self.username)
            if current is self:
                del self.app_state.users[self.username]
            elif current is None:
                log.debug("User.remove() skipped, %s is already gone", self.username)
            else:
                log.debug(
                    "User.remove() skipped, %s cache points to a different instance",
                    self.username,
                )

        # Fast-path: if an anon user never connected any socket, do not keep it
        # around for the full reconnect timeout window.
        if URI != LOCALHOST and not self.ever_connected:
            await asyncio.sleep(ANON_NEVER_CONNECTED_TIMEOUT)
            if (not self.ever_connected) and can_remove_anon():
                # Give a second chance to account for races around first socket open.
                await asyncio.sleep(3)
                if (not self.ever_connected) and can_remove_anon():
                    await remove_from_cache()
                    self.remove_anon_task = None
                    return

        while True:
            await asyncio.sleep(1 if URI == LOCALHOST else ANON_TIMEOUT)
            if can_remove_anon():
                # give them a second chance
                await asyncio.sleep(3)
                if can_remove_anon():
                    await remove_from_cache()
                    break
        self.remove_anon_task = None

    async def clear_spectator_references(self) -> None:
        # Previously scanned every active game on the server (O(total games))
        # to find which ones this user happened to be spectating. With
        # watched_games kept in sync at add/discard time, this is now
        # O(games this user is actually watching), which is almost always 0 or 1.
        game_ids = tuple(self.watched_games)
        self.watched_games.clear()

        affected_games = []
        for game_id in game_ids:
            game = self.app_state.games.get(game_id)
            if game is not None and self in game.spectators:
                game.spectators.discard(self)
                affected_games.append(game)

        for game in affected_games:
            await round_broadcast(game, game.spectator_list, full=True)

    def _background_task_done(self, task: asyncio.Task[None]) -> None:
        self.background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except Exception:
            log.exception(
                "Failed to inspect background task %s for %s",
                task.get_name(),
                self.username,
            )
            return
        if exc is not None:
            log.error(
                "Background task %s failed for %s",
                task.get_name(),
                self.username,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def create_background_task(
        self,
        coro: Coroutine[Any, Any, None],
        *,
        name: str,
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(coro, name=name)
        self.background_tasks.add(task)
        task.add_done_callback(self._background_task_done)
        return task

    def abandon_task_done(self, task: asyncio.Task[None], game_id: str) -> None:
        try:
            del self.abandon_game_tasks[game_id]
        except KeyError:
            pass

    async def abandon_game(self, game: Game) -> None:
        abandon_timeout = ABANDON_TIMEOUT * (2 if game.base >= 3 else 1)
        await asyncio.sleep(abandon_timeout)
        if game.status <= STARTED and not self.is_user_active_in_game(game.id):
            response = await game.game_ended(self, "abandon")
            # `full=True` so the PLAYERS are told, not only the spectators: `round_broadcast()`
            # builds its recipients as `non_bot_players if full else ()`. Without it this reached
            # nobody who was playing, and a hand-rolled fallback delivered to a single opponent
            # derived from `game.wplayer`/`game.bplayer` — board A's pair on a GameBug, so at most
            # one of the four seats ever heard that the game had ended.
            await round_broadcast(game, response, full=True)

            # Bots are the one thing a broadcast cannot reach, by the same definition above, so
            # they still need their queue. Mirrors `Clock._notify_bot_game_end()`, which is how
            # the flag path — the one ending that was always correct — does it.
            if game.bot_game:
                for player in game.all_players:
                    if player.bot and game.id in player.game_queues:
                        await player.game_queues[game.id].put(game.game_end)

            await self.app_state.maybe_remove_finished_game_from_cache_now(game)

    def update_online(self) -> None:
        self.online = (
            len(self.game_sockets) > 0
            or len(self.authenticated_sockets) > 0
            or len(self.lobby_sockets) > 0
            or len(self.challenge_channels) > 0
            or len(self.tournament_sockets) > 0
            or len(self.simul_sockets) > 0
            or len(self.study_sockets) > 0
        )
        if self.online:
            self.ever_connected = True

    def get_rating_value(self, variant: str, chess960: bool | None) -> int:
        perf = self.perfs.get(variant + ("960" if chess960 else ""))
        return int(round(perf["gl"]["r"], 0)) if perf is not None else MU

    def get_rating(self, variant: str, chess960: bool | None) -> Rating:
        variant_key = variant + ("960" if chess960 else "")
        perf = self.perfs.get(variant_key)
        if perf is None:
            return gl2.create_rating()
        gl = perf["gl"]
        return gl2.create_rating(gl["r"], gl["d"], gl["v"], perf["la"])

    def get_puzzle_rating(self, variant: str, chess960: bool | None) -> Rating:
        perf = self.pperfs.get(variant + ("960" if chess960 else ""))
        if perf is None:
            return gl2.create_rating()
        gl = perf["gl"]
        return gl2.create_rating(gl["r"], gl["d"], gl["v"], perf["la"])

    @property
    def silence(self) -> int:
        if self.chat_timeout_until is None:
            return 0
        remaining = (self.chat_timeout_until - datetime.now(UTC)).total_seconds()
        return max(0, int(remaining) + (1 if remaining > int(remaining) else 0))

    def set_silence(self, until: datetime | None = None) -> datetime:
        timeout_until = until or (datetime.now(UTC) + timedelta(seconds=SILENCE))
        self.chat_timeout_until = _as_required_utc(timeout_until)
        return self.chat_timeout_until

    async def persist_test_identity(self) -> None:
        """Give a `-a` mode guest a database document, so its name outlives the process.

        THIS IS PARITY, NOT A NEW CAPABILITY. Registered users survive a restart for exactly one
        reason: `Users.get()` queries `db.user` and finds a document. Test users did not, because
        `db.user` held no `Test-...` record at all, so every restart handed each browser a new name
        and no browser could reclaim the seat it held — seats are keyed by username.

        Nothing about cookie trust changes. A name asserted only by a session cookie still does not
        become a user: `_load_registered_user()` finds no document and returns `NONE_USER`. What is
        different is that the document now exists, so the identity is verified against the database
        exactly as a registered user's is.

        Guarded by `is_test_user()`, which is False in production whatever the name, so a real
        account carrying the prefix is never touched and a production database is never written to.

        `ct` is deliberately NOT written here. The first-visit category modal should still appear
        once; `set_game_category()` writes `ct` when the guest answers it, and that write — which
        until now matched no document and did nothing — finally lands, so the answer survives the
        next restart.
        """
        if not self.app_state.is_test_user(self.username):
            return
        if self.app_state.db is None:
            return

        try:
            await self.app_state.db.user.insert_one(
                {
                    "_id": self.username,
                    "title": self.title,
                    "perfs": {},
                    "pperfs": {},
                    "count": dict(DEFAULT_USER_COUNT),
                    "enabled": True,
                    "shadowban": False,
                    "createdAt": datetime.now(UTC),
                }
            )
        except DuplicateKeyError:
            # A name this server minted already exists in the database, from an earlier run whose
            # document outlived it. Reusing it is correct: the point of the document is that the
            # identity is the same one. `_generate_test_username()` only checks the in-memory
            # store, so after a restart this is reachable rather than exotic.
            log.info("Test user %s already has a document; reusing it.", self.username)
        except Exception:
            # A guest must still be able to play if the write fails; it only loses the restart.
            log.exception("Could not persist test user %s", self.username)

    async def set_rating(self, variant: str, chess960: bool, rating: Rating) -> None:
        if self.anon:
            return
        variant_key = variant + ("960" if chess960 else "")
        gl: PerfGl = {"r": rating.mu, "d": rating.phi, "v": rating.sigma}
        la = datetime.now(UTC)
        previous = self.perfs.get(variant_key)
        entry: PerfEntry = {
            "gl": gl,
            "la": la,
            "nb": (0 if previous is None else previous["nb"]) + 1,
        }
        self.perfs[variant_key] = entry

        if self.app_state.db is not None:
            await self.app_state.db.user.update_one(
                {"_id": self.username}, {"$set": {f"perfs.{variant_key}": entry}}
            )

    async def set_puzzle_rating(self, variant: str, chess960: bool, rating: Rating) -> None:
        if self.anon:
            return
        variant_key = variant + ("960" if chess960 else "")
        gl: PerfGl = {"r": rating.mu, "d": rating.phi, "v": rating.sigma}
        la = datetime.now(UTC)
        previous = self.pperfs.get(variant_key)
        entry: PerfEntry = {
            "gl": gl,
            "la": la,
            "nb": (0 if previous is None else previous["nb"]) + 1,
        }
        self.pperfs[variant_key] = entry

        if self.app_state.db is not None:
            await self.app_state.db.user.find_one_and_update(
                {"_id": self.username}, {"$set": {f"pperfs.{variant_key}": entry}}
            )

    async def apply_tournament_game_effect_once(
        self,
        game_id: str,
        result: int,
        rated: bool,
        *,
        variant_key: str,
        perf_entry: PerfEntry | None = None,
    ) -> bool:
        """Apply one tournament game's user side effects atomically and at most once.

        The bounded game-id list is only an idempotency guard for the tiny window
        between the authoritative finished-game write and ``fx=2`` on that game.
        Startup repairs pending games before accepting traffic, so a short recent
        history is sufficient and avoids unbounded user-document growth.
        """
        if self.anon:
            return False

        inc: dict[str, int] = {"count.game": 1}
        if rated:
            inc["count.rated"] = 1
        if result > 0:
            inc["count.win"] = 1
        elif result < 0:
            inc["count.loss"] = 1
        else:
            inc["count.draw"] = 1

        if self.app_state.db is None:
            return False

        update: dict[str, Any] = {
            "$inc": inc,
            "$push": {
                "tournamentGameEffectIds": {
                    "$each": [game_id],
                    "$slice": -32,
                }
            },
        }
        if perf_entry is not None:
            update["$set"] = {f"perfs.{variant_key}": perf_entry}

        result_doc = await self.app_state.db.user.update_one(
            {
                "_id": self.username,
                "tournamentGameEffectIds": {"$ne": game_id},
            },
            update,
        )
        # Tournament auto-play tests use intentionally in-memory-only users.
        # Preserve their normal rating/count behavior without weakening the
        # production DB idempotency contract.
        if result_doc.modified_count == 0 and (
            not self.app_state.is_test_user(self.username)
            or game_id in self.tournament_game_effect_ids
        ):
            return False

        self.tournament_game_effect_ids.add(game_id)
        self.count["game"] += 1
        if rated:
            self.count["rated"] += 1
        if result > 0:
            self.count["win"] += 1
        elif result < 0:
            self.count["loss"] += 1
        else:
            self.count["draw"] += 1
        if perf_entry is not None:
            self.perfs[variant_key] = perf_entry
        return True

    async def increment_game_count(self, result: int, rated: bool) -> None:
        if self.anon:
            return

        self.count["game"] += 1
        if rated:
            self.count["rated"] += 1
        if result > 0:
            self.count["win"] += 1
        elif result < 0:
            self.count["loss"] += 1
        else:
            self.count["draw"] += 1

        if self.app_state.db is not None:
            inc = {"count.game": 1}
            if rated:
                inc["count.rated"] = 1
            if result > 0:
                inc["count.win"] = 1
            elif result < 0:
                inc["count.loss"] = 1
            else:
                inc["count.draw"] = 1
            await self.app_state.db.user.update_one({"_id": self.username}, {"$inc": inc})

    async def notify_game_end(self, game: Game) -> None:
        opp_name = (
            game.wplayer.username
            if game.bplayer.username == self.username
            else game.bplayer.username
        )

        if game.result in ("1/2-1/2", "*"):
            win = None
        else:
            if (game.result == "1-0" and game.wplayer.username == self.username) or (
                game.result == "0-1" and game.bplayer.username == self.username
            ):
                win = True
            else:
                win = False

        notif_type = "gameAborted" if game.result == "*" else "gameEnd"
        content: NotificationContent = {
            "id": game.id,
            "opp": opp_name,
            "win": win,
        }
        await notify(self.app_state.db, self, notif_type, content)

    async def notify_corr_move(self, game: Game, san: str | None) -> None:
        opp_name = (
            game.wplayer.username
            if game.bplayer.username == self.username
            else game.bplayer.username
        )
        content: NotificationContent = {
            "id": game.id,
            "opp": opp_name,
        }
        if not game.fow and san:
            content["san"] = san
        await notify(self.app_state.db, self, "corrMove", content)

    async def notified(self) -> None:
        if self.notifications is not None:
            self.notifications = [{**notif, "read": True} for notif in self.notifications]

        if self.app_state.db is not None:
            await self.app_state.db.notify.update_many(
                {"notifies": self.username}, {"$set": {"read": True}}
            )

    def as_json(self, requester: str) -> UserJson:
        return {
            "_id": self.username,
            "title": self.title,
            "online": True if self.username == requester else self.online,
            "simul": len(self.simul_sockets) > 0,
        }

    async def clear_seeks(self) -> None:
        if len(self.seeks) > 0:
            for seek_id in tuple(self.seeks):
                game_id = self.seeks[seek_id].game_id
                # preserve invites (seek with game_id), corr seeks, and direct challenges
                if (
                    game_id is None
                    and self.seeks[seek_id].day == 0
                    and not self.seeks[seek_id].is_direct_challenge
                ):
                    del self.app_state.seeks[seek_id]
                    del self.seeks[seek_id]

            await self.app_state.lobby.lobby_broadcast_seeks()

    def remove_from_auto_pairings(self) -> None:
        try:
            del self.app_state.auto_pairing_users[self]
        except KeyError:
            pass
        [
            variant_tc
            for variant_tc in self.app_state.auto_pairings
            if self.app_state.auto_pairings[variant_tc].discard(self)
        ]
        self.ready_for_auto_pairing = False

    def delete_pending_auto_pairing(self) -> None:
        async def delete_auto_pairing() -> None:
            await asyncio.sleep(PENDING_SEEK_TIMEOUT)

            if not self.ready_for_auto_pairing:
                self.remove_from_auto_pairings()

        self.create_background_task(
            delete_auto_pairing(),
            name="delete-auto-pending-%s" % self.username,
        )

    def update_auto_pairing(self, ready: bool = True) -> None:
        self.ready_for_auto_pairing = ready
        if not ready:
            self.delete_pending_auto_pairing()

    def delete_pending_seek(self, seek: Seek) -> None:
        async def delete_seek(seek: Seek) -> None:
            await asyncio.sleep(PENDING_SEEK_TIMEOUT)

            if seek.pending:
                removed_user_seek = self.seeks.pop(seek.id, None)
                removed_global_seek = self.app_state.seeks.pop(seek.id, None)
                if removed_user_seek is None and removed_global_seek is None:
                    log.debug("delete_pending_seek() %s already removed", seek.id)
                elif removed_user_seek is None or removed_global_seek is None:
                    log.warning(
                        "delete_pending_seek() partial cleanup for %s user_removed=%s global_removed=%s",
                        seek.id,
                        removed_user_seek is not None,
                        removed_global_seek is not None,
                    )

        self.create_background_task(
            delete_seek(seek),
            name="delete-pending-seek-%s" % seek.id,
        )

    async def update_seeks(self, pending: bool = True) -> None:
        if len(self.seeks) > 0:
            for seek in self.seeks.values():
                # preserve invites (seek with game_id), corr seeks, and direct challenges
                if seek.game_id is None and seek.day == 0 and not seek.is_direct_challenge:
                    seek.pending = pending
                    if pending:
                        self.delete_pending_seek(seek)
            await self.app_state.lobby.lobby_broadcast_seeks()

    async def send_game_message(self, game_id: str, message: Mapping[str, object]) -> None:
        # todo: for now just logging dropped messages, but at some point should evaluate whether to queue them when no socket
        #       or include info about the complete round state in some more general message that is always
        #       sent on reconnect so client doesn't lose state
        ws_set = self.game_sockets.get(game_id)
        if ws_set is None or len(ws_set) == 0:
            return
        # TODO: make this switchable somehow
        #    if self.title != "TEST":
        #        log.debug("No ws for that game. Dropping message %s for %s", message, self.username)
        #        log.debug(
        #            "Currently user %s has these game_sockets: %r", self.username, self.game_sockets
        #        )
        #    return
        await ws_send_json_many(ws_set, message)

    async def close_all_game_sockets(self) -> None:
        for ws_set in tuple(self.game_sockets.values()):
            for ws in tuple(ws_set):
                try:
                    await ws.close()
                except Exception:
                    log.error("close_all_game_sockets() Exception for %s %s", self.username, ws)
        self.game_sockets.clear()
        self.update_online()

    def is_user_active_in_game(self, game_id: str | None = None) -> bool:
        # todo: maybe also check if ws is still open or that the sets corresponding to (each) game_id are not empty?
        if game_id is None:
            return len(self.game_sockets) > 0
        else:
            return game_id in self.game_sockets

    def is_user_active_in_correspondence_game(self) -> bool:
        return any(game.id in self.game_sockets for game in self.correspondence_games)

    def is_user_active_in_lobby(self) -> bool:
        return len(self.lobby_sockets) > 0  # todo: check also if open maybe?

    def add_ws_for_game(self, game_id: str, ws: WebSocketResponse) -> None:
        if game_id not in self.game_sockets:
            self.game_sockets[game_id] = set()
        self.game_sockets[game_id].add(ws)

    def remove_ws_for_game(self, game_id: str, ws: WebSocketResponse) -> bool:
        if game_id in self.game_sockets:
            try:
                self.game_sockets[game_id].remove(ws)
            except KeyError:
                return False
            if len(self.game_sockets[game_id]) == 0:
                del self.game_sockets[game_id]
            return True
        else:
            return False

    def auto_compatible_with_other_user(
        self, other_user: User, variant: str, chess960: bool
    ) -> bool:
        """Users are compatible when their auto pairing rating ranges are ok
        and the users are not blocked by any direction"""

        self_rating = self.get_rating_value(variant, chess960)
        self_rrmin, self_rrmax = self.app_state.auto_pairing_users[self]

        other_rating = other_user.get_rating_value(variant, chess960)
        other_rrmin, other_rrmax = self.app_state.auto_pairing_users[other_user]

        return (
            (other_user.username not in self.blocked)
            and (self.username not in other_user.blocked)
            and self_rating >= other_rating + other_rrmin
            and self_rating <= other_rating + other_rrmax
            and other_rating >= self_rating + self_rrmin
            and other_rating <= self_rating + self_rrmax
        )

    def auto_compatible_with_seek(self, seek: Seek) -> bool:
        """Seek is auto pairing compatible when the rating ranges are ok
        and the users are not blocked by any direction"""

        if seek.target not in ("", self.username, seek.creator.username):
            return False

        self_rating = self.get_rating_value(seek.variant, seek.chess960)
        seek_user = self.app_state.users[seek.creator.username]

        auto_rrmin, auto_rrmax = self.app_state.auto_pairing_users[self]

        return (
            (seek_user.username not in self.blocked)
            and (self.username not in seek_user.blocked)
            and self_rating >= seek.rating + seek.rrmin
            and self_rating <= seek.rating + seek.rrmax
            and seek.rating >= self_rating + auto_rrmin
            and seek.rating <= self_rating + auto_rrmax
        )

    def compatible_with_seek(self, seek: Seek) -> bool:
        """Seek is compatible when my rating is inside the seek rating range
        and the users are not blocked by any direction"""

        if seek.target not in ("", self.username, seek.creator.username):
            return False

        self_rating = self.get_rating_value(seek.variant, seek.chess960)
        seek_user = self.app_state.users[seek.creator.username]
        return (
            (seek_user.username not in self.blocked)
            and (self.username not in seek_user.blocked)
            and self_rating >= seek.rating + seek.rrmin
            and self_rating <= seek.rating + seek.rrmax
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return "%s %s bot=%s anon=%s chess=%s" % (
            self.title,
            self.username,
            self.bot,
            self.anon,
            self.get_rating_value("chess", False),
        )

    def update_game_category(self, game_category: str) -> None:
        normalized = normalize_game_category(game_category)
        self.game_category = normalized
        self.category_variants = CATEGORY_VARIANTS[normalized]
        self.category_variant_groups = CATEGORY_VARIANT_GROUPS[normalized]
        self.category_variant_list = CATEGORY_VARIANT_LISTS[normalized]
        self.category_variant_set = CATEGORY_VARIANT_SETS[normalized]
        self.category_variant_codes = CATEGORY_VARIANT_CODES[normalized]


async def mint_guest_user(
    app_state: PychessGlobalAppState,
    request: web.Request,
    session: aiohttp_session.Session,
    *,
    arriving_at: str,
) -> User:
    """Materialize the browser's guest identity, wherever it first lands.

    ONE FUNCTION BECAUSE IT IS ONE RULE. A guest is created lazily, at whichever entry point the
    browser reaches first — a page render, a websocket connection, or the puzzle page — so there
    are three CALLERS by nature. There is no earlier common point: anonymous page rendering is
    deliberately stateless, and materializing an identity for every request that never needs one is
    what that statelessness exists to avoid.

    What there is no reason for is three COPIES of the five lines. They drifted apart once already:
    when test users gained a database document, the puzzle page was missed, so a browser whose first
    landing was `/puzzle` got the one identity that still evaporated on restart.

    `arriving_at` names the entry point for the log line, which is the only thing that differed
    between the three.
    """
    enforce_new_anonymous_identity_limit(request)
    user = User(
        app_state,
        anon=not app_state.anon_as_test_users,
        theme=effective_theme(session, None),
        game_category=effective_game_category(session, None),
    )
    app_state.users[user.username] = user
    # A -a test user gets a database document so its name survives a restart; a no-op for anonymous
    # users and in production. See User.persist_test_identity().
    await user.persist_test_identity()
    session["user_name"] = user.username
    request[REQUEST_NEW_SESSION_KEY] = True
    log.info("+++ New %s guest user %s connected.", arriving_at, user.username)
    return user


async def set_theme(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)
    theme = post_data.get("theme")

    if isinstance(theme, str):
        session = await aiohttp_session.get_session(request)
        session_user = session.get("user_name")
        if isinstance(session_user, str) and session_user in app_state.users:
            user = app_state.users[session_user]
            user.theme = theme
            if app_state.db is not None:
                await app_state.db.user.find_one_and_update(
                    {"_id": user.username}, {"$set": {"theme": theme}}
                )
        session["theme"] = theme

    return web.Response(status=204)


async def set_game_category(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)
    game_category = post_data.get("game_category")

    if isinstance(game_category, str):
        referer = request.headers.get("REFERER")
        session = await aiohttp_session.get_session(request)
        session_user = session.get("user_name")
        normalized = normalize_game_category(game_category)
        if isinstance(session_user, str) and session_user in app_state.users:
            user = app_state.users[session_user]
            user.update_game_category(normalized)
            user.game_category_set = True
            if app_state.db is not None:
                await app_state.db.user.find_one_and_update(
                    {"_id": user.username}, {"$set": {"ct": normalized}}
                )
        session["game_category"] = normalized
        redirect_url = safe_redirect_path(referer)
        if referer and normalized != GAME_CATEGORY_ALL:
            parsed = urlparse(redirect_url)
            path_parts = [part for part in parsed.path.split("/") if part]
            if path_parts:
                section = path_parts[0]
                variant_segment = path_parts[1] if len(path_parts) > 1 else None
                current_variant = (
                    path_parts[1] if len(path_parts) > 1 and path_parts[1] in VARIANTS else None
                )
                if current_variant not in CATEGORY_VARIANT_SETS[normalized]:
                    default_variant = (
                        CATEGORY_VARIANT_LISTS[normalized][0]
                        if CATEGORY_VARIANT_LISTS[normalized]
                        else "chess"
                    )
                    if section == "puzzle":
                        redirect_url = f"/puzzle/{default_variant}"
                    elif section == "analysis":
                        redirect_url = f"/analysis/{default_variant}"
                    elif section == "editor":
                        redirect_url = f"/editor/{default_variant}"
                    elif section == "variants" and variant_segment in VARIANTS:
                        redirect_url = f"/variants/{default_variant}"
        return web.HTTPFound(redirect_url)
    else:
        raise web.HTTPNotFound()


async def set_pm_friends_only(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon:
        return web.Response(status=403)

    raw = str(post_data.get("pm_friends_only", "")).strip().lower()
    value = raw in {"1", "true", "yes", "on"}
    user.pm_friends_only = value
    if app_state.db is not None:
        await app_state.db.user.find_one_and_update(
            {"_id": user.username}, {"$set": {"pmf": value}}
        )
    return web.Response(status=204)


async def set_corr_push(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon:
        return web.Response(status=403)

    raw = str(post_data.get("corr_push", "")).strip().lower()
    value = raw in {"1", "true", "yes", "on"}
    user.corr_push_enabled = value
    if app_state.db is not None:
        await app_state.db.user.find_one_and_update(
            {"_id": user.username}, {"$set": {"cps": value}}
        )
    return web.Response(status=204)


async def set_rr_push(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon:
        return web.Response(status=403)

    raw = str(post_data.get("rr_push", "")).strip().lower()
    value = raw in {"1", "true", "yes", "on"}
    user.rr_push_enabled = value
    if app_state.db is not None:
        await app_state.db.user.find_one_and_update(
            {"_id": user.username}, {"$set": {"rps": value}}
        )
    return web.Response(status=204)


def _relation_id(user1: str, user2: str) -> str:
    return f"{user1}/{user2}"


async def follow_user(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    profileId = request.match_info["profileId"]

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon or profileId == user.username:
        return web.Response(status=403)

    post_data = await read_post_data(request)
    if post_data is None:
        return json_response({})
    follow = post_data.get("follow") == "true"
    rel_id = _relation_id(user.username, profileId)
    try:
        if follow:
            previous_relation = await app_state.db.relation.find_one_and_update(
                {"_id": rel_id},
                {"$set": {"u1": user.username, "u2": profileId, "r": FOLLOW}},
                upsert=True,
            )
            user.following.add(profileId)
            user.blocked.discard(profileId)
            if previous_relation is None or previous_relation.get("r") != FOLLOW:
                await app_state.timeline.publish(
                    "follow",
                    user,
                    {"target": profileId},
                    friends_only=True,
                )
        else:
            await app_state.db.relation.delete_one({"_id": rel_id, "r": FOLLOW})
            user.following.discard(profileId)
    except Exception:
        log.error("follow_user() Exception. Failed to update relation for %s", session_user)

    return json_response({})


async def block_user(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    profileId = request.match_info["profileId"]

    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon or profileId == user.username or profileId.casefold() == SYSTEM_USER.casefold():
        return web.Response(status=403)

    post_data = await read_post_data(request)
    if post_data is None:
        return json_response({})

    block = post_data.get("block") == "true"

    if block and profileId not in user.blocked and len(user.blocked) >= MAX_USER_BLOCK:
        return json_response({"error": "blocked_quota_reached"}, status=400)

    rel_id = _relation_id(user.username, profileId)
    try:
        if block:
            await app_state.db.relation.find_one_and_update(
                {"_id": rel_id},
                {"$set": {"u1": user.username, "u2": profileId, "r": BLOCK}},
                upsert=True,
            )
            user.blocked.add(profileId)
            user.following.discard(profileId)
            await app_state.timeline.remove_between(user.username, profileId)
        else:
            await app_state.db.relation.delete_one({"_id": rel_id, "r": BLOCK})
            user.blocked.discard(profileId)
    except Exception:
        log.error(
            "block_user() Exception. Failed to save new relation for %s to mongodb!", session_user
        )

    return json_response({})


async def get_blocked_users(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)

    if user.anon:
        await asyncio.sleep(3)
        return json_response({})

    response: UserBlocksResponse = {"blocks": list(user.blocked)}
    return json_response(response)


async def get_status(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)

    ids_param = request.rel_url.query.get("ids")
    if ids_param is None:
        raise web.HTTPBadRequest(text="missing ids")

    ids = [uid for uid in ids_param.split(",") if uid]
    if not ids:
        raise web.HTTPBadRequest(text="missing ids")

    status_list: list[UserStatusJson] = []
    for uid in ids:
        user = await app_state.users.get(uid)
        status_entry: UserStatusJson = {"online": user.online, "id": uid}
        if user.patron:
            status_entry["patron"] = True
        status_list.append(status_entry)

    return json_response(status_list)
