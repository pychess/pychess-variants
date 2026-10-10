from __future__ import annotations

import asyncio
import collections
import gettext
import os
from collections.abc import Coroutine, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from operator import neg
from time import monotonic
from typing import TYPE_CHECKING, Any, TypeVar

import aiohttp_jinja2
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from pymongo import UpdateOne
from pythongettext.msgfmt import Msgfmt, PoSyntaxError
from sortedcollections import ValueSortedDict
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    wait_exponential_jitter,
)

if TYPE_CHECKING:
    from bug.game_bug import GameBug
    from typing_defs import TournamentCalendarEvent
    from ws_types import LobbyLeaderboardEntry, TournamentWinnerEntry

import logging
import sys

from ai import BOT_task
from broadcast import round_broadcast
from chat_flood import ChatFlood
from cheat_report import CEVAL_AUTO_LOSE_CONFIG_NAME
from const import (
    ABORTED,
    ARENA,
    HTTP_ANON_USER,
    LANGUAGES,
    MONTHLY,
    NONE_USER,
    SCHEDULE_MAX_DAYS,
    SHIELD,
    STARTED,
    SYSTEM_USER,
    T_CREATED,
    T_STARTED,
    TEST_PREFIX,
    WEEKLY,
    reserved,
)
from database.startup import ensure_after_startup_indexes, prepare_database_schema
from discord_bot import DiscordBot, FakeDiscordBot
from game import Game
from gc_telemetry import start_gc_telemetry
from generate_crosstable import generate_crosstable
from generate_highscore import generate_highscore
from generate_shield import generate_shield
from lobby import Lobby
from lobby_panels_cache import (
    refresh_lobby_leaderboard_cache,
    refresh_lobby_tournament_winners_cache,
)
from logger import DEFAULT_LOGGING_CONFIG
from public_users import PublicUsers
from push_notifications import PushNotifier
from puzzle import rename_puzzle_fields
from seek import Seek, should_persist_seek_on_shutdown, should_restore_persisted_seek
from settings import (
    DEV,
    DISCORD_TOKEN,
    FISHNET_KEYS,
    LOCALHOST,
    NNUE_DOWNLOAD_ROOT,
    PROD,
    SOURCE_VERSION,
    STATIC_ROOT,
    URI,
    local_static_url,
    static_url,
)
from simul.simul import Simul
from simul.simuls import load_active_simuls
from startup_timer import StartupTimer
from timeline import Timeline
from tournament.scheduler import (
    MONTHLY_VARIANTS,
    NEW_MONTHLY_VARIANTS,
    PAUSED_MONTHLY_VARIANTS,
    SEATURDAY,
    SHIELDS,
    WEEKLY_VARIANTS,
    create_scheduled_tournaments,
    new_scheduled_tournaments,
)
from tournament.tournament import Tournament, player_json
from tournament.tournaments import (
    get_scheduled_tournaments,
    load_tournament,
    translated_tournament_name,
)
from twitch import Twitch
from typedefs import anon_as_test_users_key, client_key
from user import User
from users import NotInDbUsers, Users
from utils import load_game_from_doc, send_bot_game_start_unless_streaming
from variants import RATED_VARIANTS, VARIANTS, get_server_variant
from videos import VIDEOS
from youtube import Youtube

from lang import LOCALE

log = logging.getLogger(__name__)

GAME_KEEP_TIME = 1800  # keep game in app[games_key] for GAME_KEEP_TIME secs
TOURNAMENT_KEEP_TIME = 5 * 60  # retain an idle finished tournament after its last access
TOURNAMENT_ACTIVE_RECHECK_INTERVAL = 60  # never evict while a viewer socket is active
GAME_ACTIVE_RECHECK_INTERVAL = 60  # nor a game, while a player or spectator is attached to it
REGISTERED_USER_CACHE_TTL = 30 * 60
REGISTERED_USER_CACHE_SWEEP_INTERVAL = 5 * 60
TOURNAMENT_EFFECT_RECOVERY_DELAY = 60
T = TypeVar("T")

_TEST_TRANSLATIONS_CACHE: dict[str, gettext.NullTranslations] | None = None
_TEST_TOURNEYNAMES_CACHE: dict[str, dict[Any, str]] | None = None


def is_test_run() -> bool:
    return any("pytest" in arg for arg in sys.argv) or any("unittest" in arg for arg in sys.argv)


async def _upsert_static_docs(collection: Any, docs: Iterable[Mapping[str, Any]]) -> int:
    static_docs = [doc for doc in docs if doc.get("_id") is not None]
    if not static_docs:
        return 0

    if is_test_run():
        # mongomock 4.3.0 is not compatible with modern PyMongo UpdateOne
        # bulk writes. Keep test startup semantics equivalent without exercising
        # that third-party incompatibility; the bulk path has a focused unit test.
        for doc in static_docs:
            doc_id = doc["_id"]
            update = {key: value for key, value in doc.items() if key != "_id"}
            await collection.update_one({"_id": doc_id}, {"$set": update}, upsert=True)
        return len(static_docs)

    operations = []
    for doc in static_docs:
        doc_id = doc["_id"]
        update = {key: value for key, value in doc.items() if key != "_id"}
        operations.append(UpdateOne({"_id": doc_id}, {"$set": update}, upsert=True))

    await collection.bulk_write(operations, ordered=False)
    return len(static_docs)


async def recover_pending_tournament_game_side_effects(
    app_state: PychessGlobalAppState,
    *,
    users_only: bool,
    tournament_ids: list[str] | None = None,
) -> int:
    """Replay durable tournament result side effects left pending by a restart.

    ``fx=1`` is written in the same authoritative game update as the final
    result.  The first startup pass repairs user ratings/counters before active
    tournaments can resume pairing.  A second pass, after highscore/crosstable
    caches exist, completes the remaining idempotent effects and flips ``fx``
    to 2.
    """
    if app_state.db is None:
        return 0
    if tournament_ids == []:
        return 0

    recovered = 0
    query: dict[str, object] = {
        "tid": {"$exists": True} if tournament_ids is None else {"$in": tournament_ids},
        "fx": 1,
        "s": {"$gt": STARTED},
    }
    cursor = app_state.db.game.find(query).sort([("d", 1), ("_id", 1)])
    if tournament_ids is not None:
        # Startup recovery must use the existing tournament-game index. Without
        # the hint MongoDB may choose a collection scan for the new, sparse ``fx``
        # field before its background index has been built.
        cursor.hint("tid_1")
    async for doc in cursor:
        game = await load_game_from_doc(app_state, doc, cache_finished=False)
        if not isinstance(game, Game):
            continue
        await game.complete_tournament_final_side_effects(doc, users_only=users_only)
        recovered += 1
    return recovered


# Local test cache retention; keep this small for test runs, but use the
# production-like TTL for interactive localhost usage.
LOCALHOST_CACHE_KEEP_TIME = 1 if is_test_run() else TOURNAMENT_KEEP_TIME


class PychessGlobalAppState:
    tourney_calendar: list[TournamentCalendarEvent] | None

    def __init__(self, app: web.Application):
        from server_metrics import FullMetricsSnapshot
        from typedefs import db_key

        startup = StartupTimer(log, "PychessGlobalAppState.__init__")

        with startup.phase("initialize core state"):
            self.app = app
            self.anon_as_test_users = app[anon_as_test_users_key]

            self.shutdown = False
            self.full_metrics_snapshot = FullMetricsSnapshot()
            self.tournaments_loaded = asyncio.Event()
            self.correspondence_games_loaded = asyncio.Event()

            self.db_client = app[client_key]
            self.db: Any = app[db_key]
            self.users = self.__init_users()
            self.public_users = PublicUsers(self)
            self.disable_new_anons = False
            self.lobby = Lobby(self)
            self.timeline = Timeline(self)
            self.catalogued_variants: dict[str, dict[str, Any]] = {}
            self.chat_flood = ChatFlood()
            # one dict per tournament! {tournamentId: {user.username: user.tournament_sockets, ...}, ...}
            self.tourneysockets: dict[str, dict[str, set[WebSocketResponse | None]]] = {}
            # Study rooms are created lazily when the first browser opens /wsstudy/<id>
            # and removed as soon as their last websocket leaves. No Study is preloaded.
            self.study_sockets: dict[str, set[WebSocketResponse]] = {}
            # Serialize Study operations while allowing unrelated Studies to progress
            # independently. Ref-count queued/active users so room cleanup cannot replace
            # a lock while an HTTP/websocket/Fishnet operation is waiting on it.
            self.study_mutation_locks: dict[str, asyncio.Lock] = {}
            self.study_mutation_lock_refs: dict[str, int] = {}
            # Study mutations are sequenced per Study, but Fishnet admission also
            # needs a tiny cross-Study critical section to enforce one request per
            # account without retaining one lock per user.
            self.study_analysis_request_lock = asyncio.Lock()
            self.study_socket_users: dict[str, dict[WebSocketResponse, str]] = {}
            self.background_tasks: set[asyncio.Task[Any]] = set()
            # Serialize the tiny admission window for realtime game creation.
            # This prevents two concurrent accepts/AI starts/pairings from both
            # observing a player as free and creating overlapping live games.
            self.realtime_game_creation_lock = asyncio.Lock()
            self.game_remove_tasks: dict[str, asyncio.Task[None]] = {}
            self.tournament_remove_tasks: dict[str, asyncio.Task[None]] = {}
            self.tournament_cache_access: dict[str, float] = {}

            # translated scheduled tournament names {(variant, frequency, t_type): tournament.name, ...}
            self.tourneynames: dict[str, dict] = {lang: {} for lang in LANGUAGES}

            self.tournaments: dict[str, Tournament] = {}
            self.simuls: dict[str, Simul] = {}

            self.tourney_calendar = None

            # lichess allows 7 team message per week, so we will send one (cumulative) per day only
            # TODO: save/restore from db
            self.sent_lichess_team_msg: list[date] = []

            self.seeks: dict[str, Seek] = {}
            self.auto_pairing_users: dict[User, tuple[int, int]] = {}
            self.auto_pairings: dict[tuple[str, bool, int, int, int], set[User]] = {}
            self.games: dict[str, Game | GameBug] = {}
            # Concurrent HTTP/websocket loads and background correspondence restore
            # must share one construction task. Otherwise distinct live Game objects
            # can accept the same move with independent in-process move locks.
            self.game_load_tasks: dict[str, asyncio.Task[Game | GameBug | None]] = {}
            self.invites: dict[str, Seek] = {}
            self.game_channels: set[asyncio.Queue[str]] = set()
            self.invite_channels: dict[str, set[asyncio.Queue[str]]] = {}
            self.highscore = {variant: ValueSortedDict(neg) for variant in RATED_VARIANTS}
            self.lobby_leaderboard: list[LobbyLeaderboardEntry] = []
            self.lobby_tournament_winners: list[TournamentWinnerEntry] = []
            self.shield = {}
            self.shield_owners = {}  # {variant: username, ...}
            self.daily_puzzle_ids = {}  # {date or date:category: puzzle._id, ...}

            # monthly game stats per variant
            self.stats = {}
            self.stats_humans = {}

            # counters for games
            self.g_cnt = [0]

            # last game played
            self.tv: str | None = None

        with startup.phase("initialize streaming + worker helpers"):
            self.twitch = self.__init_twitch()
            self.youtube = Youtube(self.app)

            # fishnet active workers
            self.workers = set()
            self.fishnet_worker_last_seen: dict[str, float] = {}
            # Optional engine capabilities are timestamped independently because
            # multiple worker processes may share the same fishnet API key.
            self.fishnet_worker_capability_last_seen: dict[tuple[str, str], float] = {}
            # fishnet works
            self.fishnet_works = {}
            # Per-work custom variants.ini payloads by sha256. Built-in engine
            # variants need none; other jobs fetch only their definition chain.
            self.fishnet_variant_payloads: dict[str, dict[str, str]] = {}
            # fishnet worker tasks
            self.fishnet_queue = asyncio.PriorityQueue()
            # fishnet workers monitor
            self.fishnet_monitor = self.__init_fishnet_monitor()
            self.fishnet_versions = {}

            # Configure translations
            self.translations = {}

            #####
            # This is set by __start_gc_stats_logger() if telemetry is enabled.
            self.gc_stats_task = None

        with startup.phase("initialize discord"):
            self.__init_discord()

        with startup.phase("start bots"):
            self.__start_bots()

        with startup.phase("initialize translations"):
            self.__init_translations()

        with startup.phase("start gc telemetry"):
            self.__start_gc_stats_logger()

        with startup.phase("start push notifier"):
            self.started_at = datetime.now(UTC)
            self.push_notifier = PushNotifier(self)
            if self.push_notifier.enabled:
                self.create_background_task(self.push_notifier.run(), name="push-notifier")

        with startup.phase("start registered user cache cleanup"):
            self.create_background_task(
                self._registered_user_cache_cleanup(),
                name="registered-user-cache-cleanup",
            )

        startup.log_summary()

    async def _restore_persisted_seeks(self) -> None:
        if self.db is None:
            return

        async for doc in self.db.seek.find():
            try:
                get_server_variant(doc["variant"], doc["chess960"])
            except KeyError:
                log.warning(
                    "Dropping persisted seek %s for unavailable variant %s",
                    doc.get("_id"),
                    doc.get("variant"),
                )
                await self.db.seek.delete_one({"_id": doc["_id"]})
                continue

            user = await self.users.get(doc["user"])
            if user is None:
                continue

            game_id = doc.get("gameId") or None
            player2_name = doc.get("player2") or ""
            player2 = None if player2_name == "" else await self.users.get(str(player2_name))
            seek = Seek(
                doc["_id"],
                user,
                doc["variant"],
                fen=doc["fen"],
                color=doc["color"],
                base=doc.get("base", 5),
                inc=doc.get("inc", 5),
                byoyomi_period=doc.get("byoyomi", 0),
                day=doc["day"],
                rated=doc["rated"],
                rrmin=doc.get("rrmin"),
                rrmax=doc.get("rrmax"),
                chess960=doc["chess960"],
                target=doc.get("target"),
                game_id=game_id,
                player1=user,
                player2=player2,
                tournament_id=doc.get("tournamentId"),
                rr_arrangement_id=doc.get("rrArrangementId"),
                expire_at=doc.get("expireAt"),
                challenge_status=doc.get("challengeStatus"),
                challenge_decline_reason=doc.get("challengeDeclineReason"),
                bot_challenge_status=doc.get("botChallengeStatus"),
                bot_challenge_decline_reason=doc.get("botChallengeDeclineReason"),
            )
            if not should_restore_persisted_seek(seek):
                log.debug("Skipping non-restorable seek from database: %s", seek.id)
                continue
            log.debug("Loading seek from database: %s", seek)
            self.seeks[seek.id] = seek
            user.seeks[seek.id] = seek
            if game_id is not None:
                self.invites[game_id] = seek

    async def init_from_db(self):
        startup = StartupTimer(log, "PychessGlobalAppState.init_from_db")
        if self.db is None:
            log.debug("[startup] PychessGlobalAppState.init_from_db skipped: no database")
            startup.log_summary()
            return

        # Read tournaments, users and highscore from db
        try:
            with startup.phase("prepare database schema"):
                schema_result = await prepare_database_schema(
                    self.db,
                    local_development=not PROD,
                )
                db_collections = schema_result.initial_collections
                log.info(
                    "[startup] MongoDB schema mode=%s collections_created=%s "
                    "indexes_dropped=%s indexes_created=%s",
                    schema_result.mode.value,
                    len(schema_result.created_collections),
                    len(schema_result.dropped_indexes),
                    len(schema_result.created_indexes),
                )

                puzzle = await self.db.puzzle.find_one()
                puzzle_doc_rename_needed = (puzzle is not None) and ("variant" in puzzle)
                if puzzle_doc_rename_needed:
                    await rename_puzzle_fields(self.db)

            with startup.phase("load catalogued casual variants"):
                if is_test_run():
                    self.catalogued_variants = {}
                else:
                    from catalogued_variants import init_catalogued_variants

                    await init_catalogued_variants(self)

            with startup.phase("load Alice-Stockfish bot account"):
                alice_stockfish_doc = await self.db.user.find_one({"_id": "Alice-Stockfish"})
                if alice_stockfish_doc is not None and alice_stockfish_doc.get("title") == "BOT":
                    alice_stockfish = await self.users.get("Alice-Stockfish")
                    self.create_background_task(
                        BOT_task(alice_stockfish, self),
                        name="BOT-Alice-Stockfish",
                    )
                else:
                    log.debug(
                        "Alice-Stockfish BOT account is unavailable; Alice AI games will "
                        "fall back to Random-Mover"
                    )

            # RR arrangement documents refer to challenge invite ids. Restore persisted
            # seeks first so tournament load can distinguish a live graceful-restart
            # challenge from a genuinely stale crash-left arrangement.
            with startup.phase("restore persisted seeks"):
                await self._restore_persisted_seeks()

            with startup.phase("recover tournament user result side effects"):
                active_tournament_ids = [
                    doc["_id"]
                    async for doc in self.db.tournament.find(
                        {"status": T_STARTED}, projection={"_id": 1}
                    )
                ]
                recovered = await recover_pending_tournament_game_side_effects(
                    self,
                    users_only=True,
                    tournament_ids=active_tournament_ids,
                )
                if recovered:
                    log.warning(
                        "Recovered user result side effects for %s tournament games", recovered
                    )

            with startup.phase("restore tournaments"):
                from profile_counts import refresh_tournament_points

                async for pending in self.db.tournament.find(
                    {"profilePointsPending": True}, {"_id": 1}
                ):
                    await refresh_tournament_points(self, pending["_id"])
                cursor = self.db.tournament.find(
                    {"$or": [{"status": T_STARTED}, {"status": T_CREATED}]}
                )
                cursor.sort("startsAt", -1)
                to_date = (datetime.now(UTC) + timedelta(days=SCHEDULE_MAX_DAYS)).date()
                async for doc in cursor:
                    if doc["status"] == T_STARTED or (
                        doc["status"] == T_CREATED and doc["startsAt"].date() <= to_date
                    ):
                        await load_tournament(self, doc["_id"])
                self.tournaments_loaded.set()

            with startup.phase("create missing scheduled tournaments"):
                if not is_test_run():
                    already_scheduled = await get_scheduled_tournaments(self)
                    new_tournaments_data = new_scheduled_tournaments(already_scheduled)
                    await create_scheduled_tournaments(self, new_tournaments_data)

            with startup.phase("restore highscore + lobby caches"):
                self.create_background_task(generate_shield(self), name="generate-shield")

                if "highscore" not in db_collections:
                    await generate_highscore(self)
                cursor = self.db.highscore.find()
                async for doc in cursor:
                    if doc["_id"] in self.highscore:
                        self.highscore[doc["_id"]] = ValueSortedDict(neg, doc["scores"])

                if "crosstable" not in db_collections:
                    await generate_crosstable(self)

                await refresh_lobby_leaderboard_cache(self)
                await refresh_lobby_tournament_winners_cache(self)

            with startup.phase("restore daily puzzle cache"):
                if "dailypuzzle" in db_collections:
                    cursor = self.db.dailypuzzle.find()
                    docs = await cursor.to_list(length=None)
                    self.daily_puzzle_ids = {doc["_id"]: doc["puzzleId"] for doc in docs}

            with startup.phase("restore autopairings"):
                # Load auto pairings from database
                async for doc in self.db.autopairing.find():
                    variant_tc = tuple(doc["variant_tc"])
                    if variant_tc not in self.auto_pairings:
                        self.auto_pairings[variant_tc] = set()

                    for username, rrange in doc["users"]:
                        user = await self.users.get(username)
                        self.auto_pairings[variant_tc].add(user)
                        if user not in self.auto_pairing_users:
                            self.auto_pairing_users[user] = rrange

            # Read games in play and start their clocks.
            #
            # Correspondence games can be numerous and are not latency-critical during
            # Heroku restart recovery. Load live non-correspondence games before aiohttp
            # starts accepting traffic, then restore correspondence games in the background.
            today = datetime.now(UTC)
            active_game_filter = {"r": "d", "$or": [{"s": -2}, {"s": -1}]}

            async def restore_active_game_doc(doc, *, corr: bool) -> bool:
                game_id = doc["_id"]
                try:
                    game = await load_game_from_doc(self, doc)
                except NotInDbUsers:
                    log.error("Failed to load game %s", game_id)
                    return False

                if game is None:
                    return False

                self.games[game_id] = game
                if not corr:
                    # Both game types now restore their own clocks at load time, from the persisted
                    # position and the wall-clock downtime. Restarting them again here would reset
                    # each board to its last-move value and hand back the time the server was down.
                    pass

                if game.bot_game:
                    if TYPE_CHECKING:
                        assert isinstance(game, Game)
                    if len(game.board.move_stack) > 0 and len(game.steps) == 1:
                        game.create_steps()
                    bot_player = game.wplayer if game.wplayer.bot else game.bplayer
                    bot_player.game_queues[game_id] = asyncio.Queue()
                    await send_bot_game_start_unless_streaming(bot_player, game)
                    await bot_player.game_queues[game_id].put(game.game_full)

                if game.ply > 0:
                    self.g_cnt[0] += 1
                return True

            async def restore_active_games(cursor, *, corr: bool) -> tuple[int, int]:
                loaded = 0
                skipped = 0
                async for doc in cursor:
                    if corr:
                        # Don't load old never-started correspondence games.
                        if doc["s"] == -2 and doc["d"] < today - timedelta(days=doc.get("b", 1)):
                            skipped += 1
                            continue
                    else:
                        # Don't load old unfinished games.
                        if doc["d"] < today - timedelta(days=1):
                            skipped += 1
                            continue

                    if doc["s"] >= ABORTED:
                        skipped += 1
                        continue

                    if await restore_active_game_doc(doc, corr=corr):
                        loaded += 1
                    else:
                        skipped += 1
                return loaded, skipped

            with startup.phase("restore active live games"):
                live_cursor = self.db.game.find(
                    {
                        **active_game_filter,
                        "c": {"$ne": True},
                        "d": {"$gte": today - timedelta(days=1)},
                    }
                )
                live_cursor.sort("d", -1)
                live_loaded, live_skipped = await restore_active_games(live_cursor, corr=False)
                log.info(
                    "Loaded active live games from db: %s loaded, %s skipped",
                    live_loaded,
                    live_skipped,
                )

            async def load_correspondence_games_from_db() -> None:
                try:
                    corr_cursor = self.db.game.find({**active_game_filter, "c": True})
                    corr_cursor.sort("d", -1)
                    corr_loaded, corr_skipped = await restore_active_games(corr_cursor, corr=True)
                    log.info(
                        "Loaded active correspondence games from db: %s loaded, %s skipped",
                        corr_loaded,
                        corr_skipped,
                    )
                except Exception:
                    log.exception("Failed to load active correspondence games from db")
                finally:
                    self.correspondence_games_loaded.set()

            with startup.phase("restore simuls + static content"):
                await load_active_simuls(self)

                if not is_test_run():
                    video_count = await _upsert_static_docs(self.db.video, VIDEOS)
                    log.debug("[startup] synced %s static video documents", video_count)

                if not is_test_run() and os.getenv("LEGACY_BLOG_BOOTSTRAP", "1") == "1":
                    # Run legacy bootstrap only for an empty target collection.
                    # This keeps first deploy fully automatic while preventing
                    # rewrites of migrated posts on every subsequent restart.
                    ublog_post_count = await self.db.ublog_post.count_documents({}, limit=1)
                    if ublog_post_count == 0:
                        from legacy_blog_migration import build_legacy_ublog_docs

                        legacy_blog_author_policy = os.getenv("LEGACY_BLOG_AUTHOR_POLICY", "keep")
                        if legacy_blog_author_policy not in (
                            "keep",
                            "official-as-pychess",
                        ):
                            legacy_blog_author_policy = "keep"
                        legacy_count = await _upsert_static_docs(
                            self.db.ublog_post,
                            build_legacy_ublog_docs(
                                author_policy=legacy_blog_author_policy,
                                strip_preamble=True,
                            ),
                        )
                        log.info(
                            "[startup] bootstrapped %s legacy blog documents",
                            legacy_count,
                        )

            with startup.phase("restore fishnet + config + user migrations"):
                if "fishnet" in db_collections:
                    cursor = self.db.fishnet.find()
                    async for doc in cursor:
                        FISHNET_KEYS[doc["_id"]] = doc["name"]
                        self.fishnet_monitor[doc["name"]] = collections.deque([], 50)

                if "config" not in db_collections:
                    await self.db.config.insert_one(
                        {"name": "logging.config", "value": DEFAULT_LOGGING_CONFIG}
                    )
                await self.db.config.update_one(
                    {"name": CEVAL_AUTO_LOSE_CONFIG_NAME},
                    {"$setOnInsert": {"value": False}},
                    upsert=True,
                )

                await self.db.user.update_many(
                    {"username_lower": {"$exists": False}},
                    [{"$set": {"username_lower": {"$toLower": "$_id"}}}],
                )

                # TODO: remove this after OAuth2 PR deployed !!!
                userCollectionHasLichessOauth2Fields = await self.db.user.find_one(
                    {
                        "_id": "Fairy-Stockfish",
                        "oauth_id": "fairy-stockfish",
                        "oauth_provider": "lichess",
                    }
                )
                if userCollectionHasLichessOauth2Fields is None:
                    await self.db.user.update_many(
                        {},  # Empty filter to select all documents
                        [
                            {
                                "$set": {
                                    "oauth_id": {"$toLower": "$_id"},
                                    "oauth_provider": "lichess",
                                }
                            }
                        ],
                    )

            with startup.phase("schedule correspondence restore"):
                self.create_background_task(
                    load_correspondence_games_from_db(),
                    name="load-correspondence-games",
                )

            async def finish_tournament_effect_recovery() -> None:
                # ``fx`` was introduced with durable tournament result recovery. Building
                # its first index can scan the large game collection, so never make that
                # one-time operation part of Heroku's boot deadline.
                await ensure_after_startup_indexes(
                    self.db,
                    delay_seconds=TOURNAMENT_EFFECT_RECOVERY_DELAY,
                )
                recovered = await recover_pending_tournament_game_side_effects(
                    self, users_only=False
                )
                if recovered:
                    log.warning(
                        "Completed result side effects for %s recovered tournament games",
                        recovered,
                    )

            with startup.phase("schedule remaining tournament effect recovery"):
                self.create_background_task(
                    finish_tournament_effect_recovery(),
                    name="finish-tournament-effect-recovery",
                )

        except Exception:
            log.error("init_from_db() Exception")
            raise
        finally:
            startup.log_summary()

    def __init_translations(self):
        global _TEST_TOURNEYNAMES_CACHE, _TEST_TRANSLATIONS_CACHE

        use_test_cache = is_test_run()
        if (
            not use_test_cache
            or _TEST_TRANSLATIONS_CACHE is None
            or _TEST_TOURNEYNAMES_CACHE is None
        ):
            translations: dict[str, gettext.NullTranslations] = {}
            tourney_names: dict[str, dict[Any, str]] = {lang: {} for lang in LANGUAGES}
            base = os.path.dirname(__file__)
            for lang in LANGUAGES:
                # Generate compiled mo file once per process. Rebuilding every
                # aiohttp test application dominated Python test startup time.
                folder = os.path.join(base, "../lang/", lang, "LC_MESSAGES")
                poname = os.path.join(folder, "server.po")
                moname = os.path.join(folder, "server.mo")
                try:
                    with open(poname, "rb") as po_file:
                        po_lines = [line for line in po_file if line[:8] != b"#, fuzzy"]
                        mo = Msgfmt(po_lines).get()
                        with open(moname, "wb") as mo_file:
                            mo_file.write(mo)
                except PoSyntaxError:
                    log.error("PoSyntaxError in %s", poname)

                try:
                    translation = gettext.translation("server", localedir="lang", languages=[lang])
                except FileNotFoundError:
                    log.warning("Missing translations file for lang %s", lang)
                    translation = gettext.NullTranslations()

                translations[lang] = translation
                translation.install()

                for variant in tuple(VARIANTS.keys()) + PAUSED_MONTHLY_VARIANTS:
                    if (
                        variant in MONTHLY_VARIANTS
                        or variant in NEW_MONTHLY_VARIANTS
                        or variant in SEATURDAY
                        or variant in PAUSED_MONTHLY_VARIANTS
                    ):
                        tname = translated_tournament_name(variant, MONTHLY, ARENA, translation)
                        tourney_names[lang][(variant, MONTHLY, ARENA)] = tname
                    if variant in SEATURDAY or variant in WEEKLY_VARIANTS:
                        tname = translated_tournament_name(variant, WEEKLY, ARENA, translation)
                        tourney_names[lang][(variant, WEEKLY, ARENA)] = tname
                    if variant in SHIELDS:
                        tname = translated_tournament_name(variant, SHIELD, ARENA, translation)
                        tourney_names[lang][(variant, SHIELD, ARENA)] = tname

            if use_test_cache:
                _TEST_TRANSLATIONS_CACHE = translations
                _TEST_TOURNEYNAMES_CACHE = tourney_names
        else:
            translations = _TEST_TRANSLATIONS_CACHE
            tourney_names = _TEST_TOURNEYNAMES_CACHE

        self.translations = translations
        # Tournament ids are added dynamically to this mapping, so each app
        # gets its own copy while test apps share the immutable base translations.
        self.tourneynames = {lang: names.copy() for lang, names in tourney_names.items()}

        # https://github.com/aio-libs/aiohttp-jinja2/issues/187#issuecomment-2519831516
        class _Translations:
            @staticmethod
            def gettext(message: str):
                return self.translations[LOCALE.get()].gettext(message)

            @staticmethod
            def ngettext(singular: str, plural: str, num: int):
                return self.translations[LOCALE.get()].ngettext(singular, plural, num)

        env: Any = aiohttp_jinja2.get_env(self.app)
        env.install_gettext_translations(_Translations, newstyle=True)

        env.globals["static"] = static_url
        env.globals["local_static"] = local_static_url
        env.globals["js"] = "/static/pychess-variants.js%s" % SOURCE_VERSION
        env.globals["dev"] = DEV
        env.globals["app_name"] = "PyChess"
        env.globals["languages"] = LANGUAGES
        env.globals["asseturl"] = STATIC_ROOT
        env.globals["nnue_download_root"] = NNUE_DOWNLOAD_ROOT
        env.globals["home"] = URI

    def __start_bots(self):
        rm = self.users["Random-Mover"]
        ai = self.users["Fairy-Stockfish"]
        self.create_background_task(BOT_task(ai, self), name="BOT-RM")
        self.create_background_task(BOT_task(rm, self), name="BOT-FSF")

    def __init_fishnet_monitor(self) -> dict:
        result = {}
        # print(FISHNET_KEYS)
        for key in FISHNET_KEYS:
            result[FISHNET_KEYS[key]] = collections.deque([], 50)
        return result

    def __init_discord(self):
        if self.db is None:
            self.discord = FakeDiscordBot()
            return

        # create Discord bot
        if DEV:
            self.discord = FakeDiscordBot()
        else:
            if DISCORD_TOKEN == "":
                log.warning("DISCORD_TOKEN is missing/empty; Discord bot disabled")
                self.discord = FakeDiscordBot()
                return

            bot = DiscordBot(self)
            self.discord = bot
            self.create_background_task(
                self.__run_discord_bot(bot, DISCORD_TOKEN),
                name="Discord-BOT",
            )

    async def __run_discord_bot(self, bot: DiscordBot, token: str) -> None:
        # Keep retrying startup/login on transient failures so relay can recover
        # automatically after brief network/API hiccups during dyno boot.
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(Exception),
            wait=wait_exponential_jitter(initial=1, max=120),
            reraise=True,
            before_sleep=before_sleep_log(log, logging.WARNING),
        ):
            with attempt:
                await bot.start(token)

    def __init_twitch(self) -> Twitch:
        result = Twitch(self.app)
        if not DEV:
            pass
            # TODO: make twitch SECRET permanent
            # asyncio.create_task(result.init_subscriptions(), name="Twitch-subscriptions")
        return result

    def __start_gc_stats_logger(self):
        # Keep GC telemetry isolated in its own module to reduce changes here.
        # The helper starts a task only when GC_STATS_INTERVAL is configured.
        self.gc_stats_task = start_gc_telemetry(lambda: self.shutdown)

    def is_test_user(self, username: str) -> bool:
        """Whether this name belongs to a guest of the -a (anon_as_test_users) dev mode.

        False in production whatever the name, so a real account that happens to
        carry the prefix is never treated as a guest.
        """
        return self.anon_as_test_users and username.startswith(TEST_PREFIX)

    def registered_user_cache_references(self) -> set[User]:
        """Return users owned by live server state outside the global user cache."""
        protected = set(self.auto_pairing_users)
        for users in self.auto_pairings.values():
            protected.update(users)

        for seek_map in (self.seeks, self.invites):
            for seek in seek_map.values():
                protected.add(seek.creator)
                if seek.player1 is not None:
                    protected.add(seek.player1)
                if seek.player2 is not None:
                    protected.add(seek.player2)
                if seek.bugPlayer1 is not None:
                    protected.add(seek.bugPlayer1)
                if seek.bugPlayer2 is not None:
                    protected.add(seek.bugPlayer2)

        for game in self.games.values():
            protected.update(game.all_players)
            protected.update(game.spectators)

        for tournament in self.tournaments.values():
            protected.update(tournament.players)
            protected.update(tournament.player_keys_by_name.values())
            protected.update(tournament.bye_players)
            protected.update(tournament.spectators)

        for simul in self.simuls.values():
            protected.update(simul.players.values())
            protected.update(simul.pending_players.values())
            protected.update(simul.spectators)

        return protected

    async def _registered_user_cache_cleanup(self) -> None:
        while not self.shutdown:
            await asyncio.sleep(REGISTERED_USER_CACHE_SWEEP_INTERVAL)
            if self.shutdown:
                return
            evicted = self.users.prune_registered_cache(
                self.registered_user_cache_references(),
                max_idle_seconds=REGISTERED_USER_CACHE_TTL,
            )
            if evicted:
                log.info(
                    "Evicted %d idle registered users from cache; %d users remain",
                    len(evicted),
                    len(self.users),
                )

    def _background_task_done(self, task: asyncio.Task[Any]) -> None:
        self.background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except Exception:
            log.exception("Failed to inspect background task %s", task.get_name())
            return
        if exc is not None:
            log.error(
                "Background task %s failed",
                task.get_name(),
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def track_background_task(self, task: asyncio.Task[T]) -> asyncio.Task[T]:
        self.background_tasks.add(task)
        task.add_done_callback(self._background_task_done)
        return task

    def create_background_task(
        self,
        coro: Coroutine[Any, Any, T],
        *,
        name: str,
    ) -> asyncio.Task[T]:
        task = asyncio.create_task(coro, name=name)
        return self.track_background_task(task)

    def schedule_game_cache_removal(self, game: Game | GameBug):
        task = self.game_remove_tasks.get(game.id)
        if task is not None and not task.done():
            return

        task = asyncio.create_task(
            self.remove_from_cache(game),
            name="game-remove-%s" % game.id,
        )
        self.game_remove_tasks[game.id] = task

        def _cleanup_task(done: asyncio.Task[None], game_id: str = game.id) -> None:
            self.game_remove_tasks.pop(game_id, None)
            self._background_task_done(done)

        task.add_done_callback(_cleanup_task)

    async def _evict_game_from_cache(self, game: Game | GameBug) -> None:
        # Cancel any still-running clocks to break task -> game references
        # even when a finished game was loaded from DB and never saved in-memory.
        await game.cancel_clocks_for_eviction()

        # Fishnet queue items are independent references and can outlive a
        # worker or its game. Once a game is evicted, none of its move/analysis
        # work can produce a useful result, so remove both the work and queue IDs.
        from fishnet import drop_fishnet_work_for_game

        drop_fishnet_work_for_game(self, game.id)

        if game.id == self.tv:
            self.tv = None

        if game.id in self.games:
            del self.games[game.id]

        if game.bot_game:
            for player in game.all_players:
                if not player.bot:
                    continue
                removed = player.game_queues.pop(game.id, None)
                if removed is None:
                    # The queue may already be gone when cleanup runs after
                    # reconnect/disconnect races or repeated cache removals.
                    log.debug("%s already missing from %s.game_queues", game.id, player.username)

        for player in game.all_players:
            if player.game_in_progress == game.id:
                player.game_in_progress = None

        # Opportunistically remove idle anon users once their last cached game
        # falls out of memory, to avoid long-lived user-remove tasks and stale
        # user objects that are no longer reachable from any active socket/game.
        for player in game.all_players:
            await self._maybe_remove_idle_anon_user(player)

        log.debug("Removed %s OK", game.id)

    async def remove_game_from_cache_now(self, game: Game | GameBug) -> None:
        task = self.game_remove_tasks.get(game.id)
        current = asyncio.current_task()
        if task is not None and task is not current and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.game_remove_tasks.pop(game.id, None)
        await self._evict_game_from_cache(game)

    def game_is_held(self, game: Game | GameBug) -> bool:
        """Is anything still using this game, so its cache entry must stay?

        Both eviction paths ask this. The immediate path below has always refused to evict a game
        whose players or spectators are still connected; the scheduled path used to sleep out the
        keep time and then evict regardless. One shared predicate is what keeps them from drifting
        apart again, and that drift had a user-visible cost: see `remove_from_cache()`.
        """
        from fishnet import has_pending_analysis_work_for_game

        if has_pending_analysis_work_for_game(self, game.id):
            return True

        if any(player.is_user_active_in_game(game.id) for player in game.non_bot_players):
            return True

        return any(
            spectator.is_user_active_in_game(game.id) for spectator in tuple(game.spectators)
        )

    async def maybe_remove_finished_game_from_cache_now(self, game: Game | GameBug) -> None:
        if game.status <= STARTED or game.id not in self.games:
            return

        if self.game_is_held(game):
            return

        await self.remove_game_from_cache_now(game)

    def __init_users(self) -> Users:
        result = Users(self)
        result[SYSTEM_USER] = User(self, username=SYSTEM_USER, perfs={})
        result["Random-Mover"] = User(self, bot=True, username="Random-Mover")
        result["Fairy-Stockfish"] = User(self, bot=True, username="Fairy-Stockfish")
        # Shared, stateless identity for ordinary anonymous HTTP page views.
        # It is reserved, so User.__init__ does not create a cleanup task.
        result[HTTP_ANON_USER] = User(self, anon=True, username=HTTP_ANON_USER)
        result["Random-Mover"].online = True

        # To handle old anon user sessions with names prefixed with "Anon-" (hyphen!)
        # we will use this disabled(!) technical NONE_USER
        result[NONE_USER] = User(self, anon=True, username=NONE_USER)
        result[NONE_USER].enabled = False
        return result

    async def remove_from_cache(self, game):
        await asyncio.sleep(LOCALHOST_CACHE_KEEP_TIME if URI == LOCALHOST else GAME_KEEP_TIME)

        # The keep time is not the whole rule: an audience holds the entry.
        #
        # Why it matters. `round_socket_handler` resolves the game once, when the socket opens, and
        # holds that reference for the life of the connection. Evicting while sockets are still
        # attached means the next client to connect finds nothing cached, loads the document, and
        # gets a SECOND object for the same game. Sockets from either side of the eviction then
        # operate on different instances, and any state that accumulates on the game object
        # diverges with them -- `rematch_offers` most visibly, since every player's request lands on
        # whichever instance their own socket holds. The offers still reach every client, because
        # they are broadcast through the shared `User` objects rather than through the game, so the
        # players see each other agreeing while no set ever reaches the number needed to start the
        # rematch. Observed with a four-player bughouse game, where four participants make the split
        # easy to hit, but nothing about it is variant-specific.
        #
        # Deferred, not dropped: a game whose viewers all leave still has to be released, or the
        # cache grows without bound, so this re-asks on an interval -- the shape
        # `TOURNAMENT_ACTIVE_RECHECK_INTERVAL` already uses for tournaments. The loop also ends if
        # something else evicted the game meanwhile, so a deferred task cannot outlive the entry it
        # was armed for and go on holding a reference to it.
        while game.id in self.games and self.game_is_held(game):
            await asyncio.sleep(GAME_ACTIVE_RECHECK_INTERVAL)

        await self._evict_game_from_cache(game)

    @staticmethod
    def _tournament_referenced_users(tournament: Tournament) -> set[User]:
        users = set(tournament.players)
        users.update(tournament.player_keys_by_name.values())
        users.update(tournament.bye_players)
        users.update(tournament.spectators)
        return users

    @staticmethod
    def _tournament_socket_is_active(ws: WebSocketResponse | None) -> bool:
        return ws is not None and not getattr(ws, "closed", False)

    def tournament_has_active_sockets(self, tournament_id: str) -> bool:
        central_socket_sets = self.tourneysockets.get(tournament_id, {}).values()
        if any(
            self._tournament_socket_is_active(ws) for ws_set in central_socket_sets for ws in ws_set
        ):
            return True

        tournament = self.tournaments.get(tournament_id)
        return tournament is not None and any(
            self._tournament_socket_is_active(ws)
            for user in self._tournament_referenced_users(tournament)
            for ws in user.tournament_sockets.get(tournament_id, ())
        )

    def tournament_cache_stats(self) -> dict[str, int]:
        tournament_users: set[User] = set()
        finished_users: set[User] = set()
        finished_tournaments = 0
        tournaments_with_active_sockets = 0
        active_sockets = 0

        for tournament_id, tournament in self.tournaments.items():
            referenced_users = self._tournament_referenced_users(tournament)
            tournament_users.update(referenced_users)
            if tournament.status > T_STARTED:
                finished_tournaments += 1
                finished_users.update(referenced_users)

            tournament_active_sockets = sum(
                int(self._tournament_socket_is_active(ws))
                for ws_set in self.tourneysockets.get(tournament_id, {}).values()
                for ws in ws_set
            )
            active_sockets += tournament_active_sockets
            tournaments_with_active_sockets += int(tournament_active_sockets > 0)

        return {
            "finished_tournaments": finished_tournaments,
            "tournament_user_references": len(tournament_users),
            "finished_tournament_user_references": len(finished_users),
            "tournaments_with_active_sockets": tournaments_with_active_sockets,
            "tournament_active_sockets": active_sockets,
        }

    def schedule_tournament_cache_removal(self, tournament: Tournament):
        if tournament is None or tournament.status <= T_STARTED:
            return

        self.tournament_cache_access[tournament.id] = monotonic()
        task = self.tournament_remove_tasks.get(tournament.id)
        if task is not None and not task.done():
            return

        task = asyncio.create_task(
            self.remove_tournament_from_cache(tournament.id),
            name="tournament-remove-%s" % tournament.id,
        )
        self.tournament_remove_tasks[tournament.id] = task

        def _cleanup_task(done_task, tournament_id=tournament.id):
            if self.tournament_remove_tasks.get(tournament_id) is done_task:
                self.tournament_remove_tasks.pop(tournament_id, None)

        task.add_done_callback(_cleanup_task)

    async def remove_tournament_from_cache(self, tournament_id: str):
        keep_time = LOCALHOST_CACHE_KEEP_TIME if URI == LOCALHOST else TOURNAMENT_KEEP_TIME
        active_recheck = (
            LOCALHOST_CACHE_KEEP_TIME if URI == LOCALHOST else TOURNAMENT_ACTIVE_RECHECK_INTERVAL
        )
        while True:
            last_access = self.tournament_cache_access.get(tournament_id)
            if last_access is None:
                return
            remaining = keep_time - (monotonic() - last_access)
            if remaining > 0:
                await asyncio.sleep(remaining)
                continue

            tournament = self.tournaments.get(tournament_id)
            if tournament is None or tournament.status <= T_STARTED:
                self.tournament_cache_access.pop(tournament_id, None)
                return
            if self.tournament_has_active_sockets(tournament_id):
                await asyncio.sleep(active_recheck)
                continue
            break

        if tournament.clock_task is not None and not tournament.clock_task.done():
            tournament.clock_task.cancel()
            try:
                await tournament.clock_task
            except asyncio.CancelledError:
                pass

        referenced_users = self._tournament_referenced_users(tournament)
        sockets: set[WebSocketResponse] = set()
        socket_map = self.tourneysockets.pop(tournament_id, {})
        for ws_set in socket_map.values():
            sockets.update(ws for ws in ws_set if ws is not None)
        for user in referenced_users:
            ws_set = user.tournament_sockets.pop(tournament_id, ())
            sockets.update(ws for ws in ws_set if ws is not None)
            user.update_online()

        for ws in sockets:
            try:
                await ws.close()
            except Exception:
                log.debug("Failed to close tournament socket for %s", tournament_id)

        if tournament_id in self.tournaments:
            del self.tournaments[tournament_id]
        self.tournament_cache_access.pop(tournament_id, None)

        player_json.cache_clear()
        log.debug("Removed tournament %s OK", tournament_id)

    async def _maybe_remove_idle_anon_user(self, user: User):
        # This cleanup is intentionally conservative: only remove anon users that
        # are offline, have no active games/seeks, and are not reserved system users.
        if user is None or (not user.anon) or reserved(user.username):
            return

        # Refresh online status based on socket sets to avoid stale flags.
        user.update_online()
        if user.online:
            return

        if user.game_in_progress is not None:
            return
        if user.correspondence_games:
            return
        if user.is_user_active_in_game() or user.is_user_active_in_lobby():
            return

        # Clear any pending abandon timers that would keep the user alive.
        for task in tuple(user.abandon_game_tasks.values()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        user.abandon_game_tasks.clear()

        for task in tuple(user.background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        user.background_tasks.clear()
        user.remove_anon_task = None

        # Remove from auto pairing and any leftover seek references so stale
        # lobby state does not keep this user alive.
        user.remove_from_auto_pairings()
        removed_seek = False
        for seek_id in tuple(user.seeks):
            if seek_id in self.seeks:
                del self.seeks[seek_id]
                removed_seek = True
            del user.seeks[seek_id]
        if removed_seek:
            # Inform active lobby clients that these seeks are gone.
            await self.lobby.lobby_broadcast_seeks()

        await user.clear_spectator_references()

        # Drop any lobby/tournament socket bookkeeping entries if they linger.
        self.lobby.lobbysockets.pop(user.username, None)
        for tid in tuple(self.tourneysockets):
            self.tourneysockets[tid].pop(user.username, None)

        # Finally remove the user from the global cache.
        if user.username in self.users:
            del self.users[user.username]

    async def server_shutdown(self):
        self.shutdown = True

        log.debug("\nServer shutdown activated\n")

        # notify users
        msg = "Server will restart in about 30 seconds. Sorry for the inconvenience!"
        response = {"type": "roundchat", "user": "", "message": msg, "room": "player"}
        for game in [game for game in self.games.values() if not game.corr]:
            await round_broadcast(game, response, full=True)

        # Save restart-surviving seeks using one DB document shape.
        persisted_seeks = [
            seek.seek_db_json
            for seek in self.seeks.values()
            if should_persist_seek_on_shutdown(seek)
        ]
        await self.db.seek.delete_many({})
        if len(persisted_seeks) > 0:
            for seek in persisted_seeks:
                log.debug("saving seek to database: %s" % seek)
            await self.db.seek.insert_many(persisted_seeks)

        # save auto pairings
        await self.db.autopairing.delete_many({})
        auto_pairings = [
            {
                "variant_tc": variant_tc,
                "users": [
                    (user.username, self.auto_pairing_users[user])
                    for user in self.auto_pairings[variant_tc]
                ],
            }
            for variant_tc in self.auto_pairings
        ]
        if len(auto_pairings) > 0:
            await self.db.autopairing.insert_many(auto_pairings)

        # terminate BOT users
        for user in [user for user in self.users.values() if user.bot]:
            await user.event_queue.put('{"type": "terminated"}')

        # close game_sockets
        for user in [user for user in self.users.values() if not user.bot]:
            await user.close_all_game_sockets()

        # close lobbysockets
        await self.lobby.close_lobby_sockets()

        # close tourneysockets
        for tid in self.tourneysockets:
            for username in tuple(self.tourneysockets[tid].keys()):
                ts_dict = self.users[username].tournament_sockets
                if tid in ts_dict:
                    ws_set = ts_dict[tid]
                    for ws in tuple(ws_set):
                        if ws is None:
                            continue
                        await ws.close()

        # Study rooms are lazy, so only currently open browser tabs need closing.
        for ws_set in tuple(self.study_sockets.values()):
            for ws in tuple(ws_set):
                await ws.close()

        log.debug("--- Cancel running tasks---")
        for task in asyncio.all_tasks():
            taskname = task.get_name()

            # Let the server cancel itself at the end of graceful shutdown
            if taskname.startswith("_run_app"):
                continue

            # AsyncMongoClient will be closed in server on_cleanup()
            if taskname.startswith("pymongo"):
                continue

            if taskname.startswith("Task-"):
                taskname = taskname + " " + task.get_coro().__name__

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                log.debug("%s cancelled" % taskname)

    def online_count(self):
        return sum(1 for user in self.users.values() if user.online)

    def auto_pairing_count(self):
        return sum(1 for user in self.auto_pairing_users if user.ready_for_auto_pairing)

    def __str__(self):
        return self.__stringify(str)

    def __repr__(self):
        return self.__stringify(repr)

    def __stringify(self, strfunc):
        attribs = vars(self)
        values = []
        for attr in attribs:
            value = getattr(self, attr)
            values.append(strfunc(value))
        clsname = type(self).__name__
        variabs = ", ".join(values)
        return f"{clsname}({variabs})"
