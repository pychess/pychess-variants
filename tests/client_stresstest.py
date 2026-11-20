"""
Local stress-test runner for websocket-heavy pychess load scenarios.

Before high-load runs, raise open-file limits in both terminals:
1) the server terminal
2) the stress-client terminal

Example:
    ulimit -n 10000

Reason: each active socket/connection consumes a file descriptor. With large
user/spectator counts, default Linux per-process limits (often 1024) are hit
quickly, causing "OSError: [Errno 24] Too many open files".

Production note: Heroku dynos already use a much higher descriptor limit
(reported as 10000), so this local setting is used to mirror that environment:
https://help.heroku.com/WEJQH08E/is-is-possible-to-increase-the-file-descriptor-ulimit-limit
"""

import argparse
import asyncio
import cProfile
import json
import math
import pstats
import random
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from itertools import cycle
from pathlib import Path
from time import monotonic
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp
import pyffish as sf
import test_logger
from const import TEST_PREFIX
from settings import PROD, URI
from websocket_utils import ws_send_json

test_logger.init_test_logger()

sf.set_option("VariantPath", "variants.ini")


def http_to_ws_url(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


LOBBY_URL = http_to_ws_url(URI, "/wsl")
ROUND_URL = http_to_ws_url(URI, "/wsr/")
URLS = ("about", "players", "games", "tv", "variants")
TEST_VARIANTS = (
    "chess",
    "dobutsu",
    "minishogi",
    "gorogoroplus",
    "torishogi",
    "shogi",
    "crazyhouse",
    "capahouse",
    "grandhouse",
    "shinobi",
)
ALL_BOT_PROFILES = ("Random-Mover", "Fairy-Stockfish")
BOT_PROFILES = ("Random-Mover",)
DEFAULT_USER_COUNT = 1000
DEFAULT_SPECTATORS_PER_GAME = 1000
DEFAULT_GAMES_PER_USER = 1
DEFAULT_USER_START_SPREAD_SECS = 120.0
DEFAULT_CHALLENGE_DELAY_MIN_SECS = 0.05
DEFAULT_CHALLENGE_DELAY_MAX_SECS = 0.4
DEFAULT_CHALLENGE_RETRY_SECS = 15.0
DEFAULT_SPECTATOR_REQUEST_GAP_SECS = 0.01
DEFAULT_MAX_SPECTATOR_HTTP_CONCURRENCY = 50
DEFAULT_FEATURED_GAMES = 2
DEFAULT_SPECTATORS_REGULAR_PER_GAME = 2
DEFAULT_LOBBY_RECV_TIMEOUT_SECS = 2.0
DEFAULT_LOBBY_STALE_RECONNECT_SECS = 60.0
DEFAULT_ROUND_RECV_TIMEOUT_SECS = 30.0
DEFAULT_ROUND_MAX_IDLE_CYCLES = 3
DEFAULT_PENDING_CHALLENGE_MAX_WAIT_SECS = 300.0
DEFAULT_ROUND_RECONNECT_BACKOFF_MIN_SECS = 0.3
DEFAULT_ROUND_RECONNECT_BACKOFF_MAX_SECS = 1.0
# Read-only requests that cover distinct page/API handlers and DB queries.
# Keep HTML rates below anonymous browsing admission budgets in local DEV.
PROFILE_HTTP_PATHS = (
    ("games", "/games"),
    ("calendar", "/api/calendar"),
    ("community", "/variants/community"),
    ("stats", "/api/stats"),
    ("players", "/players"),
    ("forum_categories", "/api/forum/categs"),
    ("tournaments", "/tournaments"),
    ("catalogue", "/api/catalogued-variants"),
    ("studies", "/study/all"),
    ("forum", "/forum"),
    ("profile", "/@/gbtami"),
    ("tv", "/tv"),
    ("search_page", "/games/search"),
    ("profile_tournaments", "/@/gbtami/tournaments"),
)


def profile_me(fn):
    def profiled_fn(*args, **kwargs):
        prof = cProfile.Profile()
        ret = prof.runcall(fn, *args, **kwargs)
        ps = pstats.Stats(prof)
        ps.sort_stats("cumulative")
        ps.print_stats(60)
        return ret

    return profiled_fn


vari = cycle(TEST_VARIANTS)


def extract_username(html: str) -> str:
    match = re.search(r'data-username="([^"]+)"', html)
    if match is None:
        # Backward compatibility with older templates.
        match = re.search(r'data-user="([^"]+)"', html)
    if match is None:
        raise RuntimeError("Could not find username in lobby HTML payload.")
    return match.group(1)


def make_cookie_jar() -> aiohttp.CookieJar:
    # Allow cookies for IP hosts (127.0.0.1) and keep secure cookies usable
    # during local HTTP smoke tests when server config marks cookies as secure.
    try:
        return aiohttp.CookieJar(unsafe=True, treat_as_secure_origin=[URI])
    except TypeError:
        return aiohttp.CookieJar(unsafe=True)


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple local smoke stress test client for pychess websocket flows."
    )
    parser.add_argument(
        "-u",
        "--users",
        type=non_negative_int,
        default=DEFAULT_USER_COUNT,
        help=f"Number of concurrent test users (default: {DEFAULT_USER_COUNT}).",
    )
    parser.add_argument(
        "-s",
        "--spectators-per-game",
        type=non_negative_int,
        default=DEFAULT_SPECTATORS_PER_GAME,
        help=f"Number of spectator HTTP clients to spawn per started game (default: {DEFAULT_SPECTATORS_PER_GAME}).",
    )
    parser.add_argument(
        "-g",
        "--games-per-user",
        type=non_negative_int,
        default=DEFAULT_GAMES_PER_USER,
        help=f"Target completed games per test user before it exits (default: {DEFAULT_GAMES_PER_USER}).",
    )
    parser.add_argument(
        "--user-start-spread-secs",
        type=non_negative_float,
        default=DEFAULT_USER_START_SPREAD_SECS,
        help=(
            "Spread initial lobby connects over this random window in seconds "
            f"(default: {DEFAULT_USER_START_SPREAD_SECS})."
        ),
    )
    parser.add_argument(
        "--challenge-delay-min-secs",
        type=non_negative_float,
        default=DEFAULT_CHALLENGE_DELAY_MIN_SECS,
        help=f"Minimum random delay before sending create_ai_challenge after lobby connect (default: {DEFAULT_CHALLENGE_DELAY_MIN_SECS}).",
    )
    parser.add_argument(
        "--challenge-delay-max-secs",
        type=non_negative_float,
        default=DEFAULT_CHALLENGE_DELAY_MAX_SECS,
        help=f"Maximum random delay before sending create_ai_challenge after lobby connect (default: {DEFAULT_CHALLENGE_DELAY_MAX_SECS}).",
    )
    parser.add_argument(
        "--challenge-retry-secs",
        type=non_negative_float,
        default=DEFAULT_CHALLENGE_RETRY_SECS,
        help=(
            "If a user is still idle in lobby after this many seconds, send another "
            f"create_ai_challenge (default: {DEFAULT_CHALLENGE_RETRY_SECS})."
        ),
    )
    parser.add_argument(
        "--spectator-request-gap-secs",
        type=non_negative_float,
        default=DEFAULT_SPECTATOR_REQUEST_GAP_SECS,
        help=(
            "Delay inserted between launching spectator page requests for a game "
            f"(default: {DEFAULT_SPECTATOR_REQUEST_GAP_SECS})."
        ),
    )
    parser.add_argument(
        "--max-spectator-http-concurrency",
        type=positive_int,
        default=DEFAULT_MAX_SPECTATOR_HTTP_CONCURRENCY,
        help=(
            "Global cap for in-flight spectator HTTP requests across all games "
            f"(default: {DEFAULT_MAX_SPECTATOR_HTTP_CONCURRENCY})."
        ),
    )
    parser.add_argument(
        "--featured-games",
        type=non_negative_int,
        default=DEFAULT_FEATURED_GAMES,
        help=(
            "How many games should use the high spectator count from --spectators-per-game "
            f"(default: {DEFAULT_FEATURED_GAMES}, meaning all games use regular count)."
        ),
    )
    parser.add_argument(
        "--spectators-regular-per-game",
        type=non_negative_int,
        default=DEFAULT_SPECTATORS_REGULAR_PER_GAME,
        help=(
            "Spectator count for non-featured games. "
            f"(default: {DEFAULT_SPECTATORS_REGULAR_PER_GAME})."
        ),
    )
    parser.add_argument(
        "--http-rps",
        type=non_negative_float,
        default=0.0,
        help="Additional read-only HTTP requests per second (off by default).",
    )
    parser.add_argument(
        "--http-duration-secs",
        type=non_negative_float,
        default=0.0,
        help="How long to keep read-only HTTP requests running (off by default).",
    )
    parser.add_argument(
        "--http-concurrency",
        type=positive_int,
        default=4,
        help="Maximum in-flight background HTTP requests (default: 4).",
    )
    parser.add_argument(
        "--test-user-pgn",
        action="store_true",
        help="Export one completed Test-* user's own games using its existing -a test session.",
    )
    parser.add_argument(
        "--pgn-cookie-file",
        type=Path,
        help="Private local file containing your AIOHTTP_SESSION cookie value; enables gbtami PGN export.",
    )
    parser.add_argument(
        "--pgn-max-games",
        type=positive_int,
        default=100,
        help="Limit the number of games exported per PGN request (default: 100).",
    )
    parser.add_argument(
        "--run-duration-secs",
        type=non_negative_float,
        default=0.0,
        help="Stop generating game load after this many seconds (0: wait for all games).",
    )
    parser.add_argument(
        "--human-vs-human",
        action="store_true",
        help=(
            "Pair simulated anonymous users into real casual games. "
            "--users counts players (two per game); localhost -a only."
        ),
    )
    parser.add_argument(
        "--game-minutes",
        type=positive_int,
        default=1,
        help="Initial clock minutes for each game (default: 1).",
    )
    parser.add_argument(
        "--move-delay-secs",
        type=non_negative_float,
        default=0.0,
        help="Extra delay before each test user's move (default: 0).",
    )
    parser.add_argument(
        "--report-interval-secs",
        type=non_negative_float,
        default=0.0,
        help="Print observed concurrent unfinished games every N seconds (0: off).",
    )
    args = parser.parse_args()
    if any(
        not math.isfinite(value)
        for value in (
            args.http_rps,
            args.http_duration_secs,
            args.run_duration_secs,
            args.move_delay_secs,
            args.report_interval_secs,
        )
    ):
        parser.error("HTTP rates and durations must be finite")
    if args.test_user_pgn and (
        PROD or urlsplit(URI).hostname not in {"localhost", "127.0.0.1", "::1"}
    ):
        parser.error("Test-user PGN profiling only supports localhost, never production")
    if args.http_rps > 0:
        if args.http_duration_secs <= 0:
            parser.error("--http-duration-secs must be > 0 when --http-rps is set")
        if PROD or urlsplit(URI).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("Background HTTP profiling only supports localhost, never production")
    elif args.pgn_cookie_file is not None:
        parser.error("--pgn-cookie-file requires --http-rps")
    if args.human_vs_human:
        if PROD or urlsplit(URI).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("--human-vs-human may only be run against a localhost server")
        if args.users < 2 or args.users % 2:
            parser.error("--human-vs-human requires an even --users count >= 2")
        if args.games_per_user != 1:
            parser.error("--human-vs-human currently requires --games-per-user 1")
    if args.challenge_delay_max_secs < args.challenge_delay_min_secs:
        parser.error("--challenge-delay-max-secs must be >= --challenge-delay-min-secs")
    return args


def read_session_cookie(path: Path) -> str:
    """Read a pre-existing LOCAL browser session, never a username/password.

    Accept only the cookie value, or one `AIOHTTP_SESSION=value` entry.
    Do not print it or attach it to anonymous spectator/game clients.
    """
    if path.stat().st_mode & 0o077:
        raise ValueError(f"Cookie file {path} must be private (chmod 600).")
    value = path.read_text(encoding="utf-8").strip()
    if value.startswith("AIOHTTP_SESSION="):
        value = value.partition("=")[2]
    if not value or any(ch.isspace() or ch in ";\r\n" for ch in value):
        raise ValueError(f"Cookie file {path} must contain only an AIOHTTP_SESSION value.")
    return value


@dataclass
class HttpRequestStats:
    counts: Counter[str] = field(default_factory=Counter)
    statuses: Counter[str] = field(default_factory=Counter)
    elapsed_ms: list[float] = field(default_factory=list)
    bytes_received: int = 0
    dropped: int = 0
    pgn_ok: int = 0
    pgn_empty: int = 0

    def record(self, label: str, status: int | str, elapsed_ms: float, received: int) -> None:
        self.counts[label] += 1
        self.statuses[f"{label}:{status}"] += 1
        self.elapsed_ms.append(elapsed_ms)
        self.bytes_received += received
        if label == "pgn":
            if status == 200 and received > 0:
                self.pgn_ok += 1
            else:
                self.pgn_empty += 1

    def report(self) -> None:
        latencies = sorted(self.elapsed_ms)
        p95 = latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else 0.0
        print("=== BACKGROUND HTTP SUMMARY ===")
        print(f"requests_by_path={dict(sorted(self.counts.items()))}")
        print(f"statuses_by_path={dict(sorted(self.statuses.items()))}")
        print(f"http_p95_ms={p95:.1f} http_max_ms={max(latencies, default=0.0):.1f}")
        print(
            f"http_bytes_received={self.bytes_received} http_dropped_at_concurrency_cap={self.dropped}"
        )
        print(f"pgn_nonempty_exports={self.pgn_ok} pgn_empty_or_failed={self.pgn_empty}")
        if self.pgn_empty:
            print("PGN warning: empty/failed responses may mean expired or unauthorized cookie.")


async def run_http_workload(
    *,
    rps: float,
    duration: float,
    concurrency: int,
    pgn_cookie: str | None,
    pgn_max_games: int,
) -> HttpRequestStats:
    """Independent traffic during gameplay, with one shared concurrency limit.

    PGN requires the authenticated gbtami session and is sent at most once per
    120 seconds, below the server's explicit export admission budget.
    """
    stats = HttpRequestStats()
    throttle = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=30)
    pending: set[asyncio.Task[None]] = set()
    start = monotonic()
    stop = start + duration
    next_pgn = start + min(10, duration / 3)
    paths = cycle(PROFILE_HTTP_PATHS)

    async with aiohttp.ClientSession(cookie_jar=make_cookie_jar(), timeout=timeout) as public:
        # The authentication cookie must NOT be attached to spectator/game users.
        if pgn_cookie is not None:
            authenticated = aiohttp.ClientSession(
                cookie_jar=make_cookie_jar(),
                cookies={"AIOHTTP_SESSION": pgn_cookie},
                timeout=timeout,
            )
        else:
            authenticated = None
        try:

            async def fetch(label: str, path: str, session: aiohttp.ClientSession) -> None:
                async with throttle:
                    began = monotonic()
                    status: int | str = "connection_error"
                    received = 0
                    try:
                        async with session.get(URI.rstrip("/") + path) as resp:
                            status = resp.status
                            async for chunk in resp.content.iter_chunked(65536):
                                received += len(chunk)
                            # Some authorization failures return HTTP 200 + an
                            # empty body. Classify these separately in the report.
                            if label == "pgn" and resp.content_type != "text/pgn":
                                status = f"{resp.status}:{resp.content_type}"
                    except (aiohttp.ClientError, TimeoutError, OSError) as exc:
                        status = type(exc).__name__
                    stats.record(label, status, (monotonic() - began) * 1000, received)

            interval = 1.0 / rps
            next_http = start
            while monotonic() < stop:
                now = monotonic()
                if authenticated is not None and now >= next_pgn:
                    if len(pending) < concurrency:
                        task = asyncio.create_task(
                            fetch(
                                "pgn",
                                f"/api/games/user/gbtami/pgn?max={pgn_max_games}",
                                authenticated,
                            )
                        )
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                    else:
                        stats.dropped += 1
                    next_pgn = now + 120
                if now >= next_http:
                    if len(pending) < concurrency:
                        label, path = next(paths)
                        task = asyncio.create_task(fetch(label, path, public))
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                    else:
                        stats.dropped += 1
                    next_http = now + interval
                await asyncio.sleep(
                    max(0.01, min(0.2, next_http - monotonic(), stop - monotonic()))
                )
            if pending:
                await asyncio.gather(*pending)
        finally:
            if authenticated is not None:
                await authenticated.close()
    return stats


class TestUserPgnExporter:
    """Export at most one finished test user's own games during a profiling run.

    Uses the same aiohttp session that authenticated the Test-* user for
    gameplay. No copied browser cookie, credential, or admin privilege is needed.
    The one-export limit also leaves room for an optional gbtami export under
    the shared local PGN rate limit (two requests per 120 seconds).
    """

    def __init__(self, max_games: int):
        self.max_games = max_games
        self._lock = asyncio.Lock()
        self.attempted = False
        self.username: str | None = None
        self.status: int | str | None = None
        self.bytes_received = 0
        self.elapsed_ms = 0.0

    async def maybe_export(self, session: aiohttp.ClientSession, username: str) -> None:
        if not username.startswith(TEST_PREFIX):
            return
        async with self._lock:
            if self.attempted:
                return
            self.attempted = True
            self.username = username

        start = monotonic()
        try:
            path = f"/api/games/user/{quote(username, safe='')}/pgn?max={self.max_games}"
            async with asyncio.timeout(30):
                async with session.get(URI.rstrip("/") + path) as response:
                    self.status = response.status
                    async for chunk in response.content.iter_chunked(65536):
                        self.bytes_received += len(chunk)
                    if response.content_type != "text/pgn":
                        self.status = f"{response.status}:{response.content_type}"
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            self.status = type(exc).__name__
        finally:
            self.elapsed_ms = (monotonic() - start) * 1000

    def report(self) -> None:
        if not self.attempted:
            print("test_user_pgn=skipped (no completed non-aborted Test–* game)")
            return
        print(
            "test_user_pgn="
            f"user:{self.username} status:{self.status} bytes:{self.bytes_received} "
            f"elapsed_ms:{self.elapsed_ms:.1f}"
        )
        if self.status != 200 or self.bytes_received == 0:
            print("Test-user PGN warning: export was rejected or had no saved game to export.")


class SpectatorAllocator:
    def __init__(self, featured_games: int, featured_count: int, regular_count: int):
        self.featured_games = featured_games
        self.featured_count = featured_count
        self.regular_count = regular_count
        self.games_seen = 0
        self._assigned_games: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def count_for_game(self, game_id: str) -> int:
        async with self._lock:
            if game_id in self._assigned_games:
                return 0
            self.games_seen += 1
            if self.featured_games > 0 and self.games_seen <= self.featured_games:
                count = self.featured_count
            else:
                count = self.regular_count
            self._assigned_games[game_id] = count
            return count


class BotChallengeScheduler:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._next_token = 0
        self._fairy_pending_tokens: set[str] = set()
        self._fairy_active_games: set[str] = set()

    async def reserve_profile(self) -> tuple[str, str | None]:
        async with self._lock:
            fairy_busy = bool(self._fairy_pending_tokens or self._fairy_active_games)
            if not fairy_busy:
                token = f"fairy-{self._next_token}"
                self._next_token += 1
                self._fairy_pending_tokens.add(token)
                return "Fairy-Stockfish", token
            return random.choice(BOT_PROFILES), None

    async def bind_game(self, token: str | None, game_id: str, profile: str | None) -> None:
        if token is None or profile != "Fairy-Stockfish":
            return
        async with self._lock:
            self._fairy_pending_tokens.discard(token)
            self._fairy_active_games.add(game_id)

    async def release_pending(self, token: str | None, profile: str | None) -> None:
        if token is None or profile != "Fairy-Stockfish":
            return
        async with self._lock:
            self._fairy_pending_tokens.discard(token)

    async def release_game(self, game_id: str, profile: str | None) -> None:
        if profile != "Fairy-Stockfish":
            return
        async with self._lock:
            self._fairy_active_games.discard(game_id)


class RunStats:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.total_games = 0
        self.aborted_games = 0
        self.by_status: Counter[int] = Counter()
        self.by_result: Counter[str] = Counter()
        self.by_game_length_ply: Counter[int] = Counter()
        self.games_without_ply = 0
        self.aborts_by_phase: Counter[str] = Counter()
        self.aborts_by_end_source: Counter[str] = Counter()
        self.aborts_by_turn: Counter[str] = Counter()
        self.aborts_by_moves_sent: Counter[str] = Counter()
        self.aborts_by_variant: Counter[str] = Counter()
        self.aborts_by_elapsed_bucket: Counter[str] = Counter()
        self.games_by_bot_profile: Counter[str] = Counter()
        self.aborts_by_bot_profile: Counter[str] = Counter()
        self.by_status_by_bot_profile: dict[str, Counter[int]] = defaultdict(Counter)
        self.by_result_by_bot_profile: dict[str, Counter[str]] = defaultdict(Counter)
        self.challenges_sent_by_profile: Counter[str] = Counter()
        self.new_games_by_actual_bot_profile: Counter[str] = Counter()
        self._seen_game_start_ids: set[str] = set()
        self._seen_game_end_ids: set[str] = set()
        self._unfinished_game_ids: set[str] = set()
        self.peak_unfinished_games = 0
        self.challenge_to_game_start_count_by_bot_profile: Counter[str] = Counter()
        self.challenge_to_game_start_sum_by_bot_profile: defaultdict[str, float] = defaultdict(
            float
        )
        self.challenge_to_game_start_min_by_bot_profile: dict[str, float] = {}
        self.challenge_to_game_start_max_by_bot_profile: dict[str, float] = {}

    async def record_challenge_sent(self, bot_profile: str | None) -> None:
        profile_key = bot_profile if isinstance(bot_profile, str) else "unknown"
        async with self._lock:
            self.challenges_sent_by_profile[profile_key] += 1

    async def record_game_start(
        self,
        game_id: str,
        actual_bot_profile: str | None,
        challenge_to_start_latency_secs: float | None,
    ) -> None:
        profile_key = actual_bot_profile if isinstance(actual_bot_profile, str) else "unknown"
        async with self._lock:
            if game_id in self._seen_game_start_ids:
                return
            self._seen_game_start_ids.add(game_id)
            self._unfinished_game_ids.add(game_id)
            self.peak_unfinished_games = max(
                self.peak_unfinished_games, len(self._unfinished_game_ids)
            )
            self.new_games_by_actual_bot_profile[profile_key] += 1
            if isinstance(challenge_to_start_latency_secs, (int, float)):
                latency = max(0.0, float(challenge_to_start_latency_secs))
                self.challenge_to_game_start_count_by_bot_profile[profile_key] += 1
                self.challenge_to_game_start_sum_by_bot_profile[profile_key] += latency
                current_min = self.challenge_to_game_start_min_by_bot_profile.get(profile_key)
                current_max = self.challenge_to_game_start_max_by_bot_profile.get(profile_key)
                if current_min is None or latency < current_min:
                    self.challenge_to_game_start_min_by_bot_profile[profile_key] = latency
                if current_max is None or latency > current_max:
                    self.challenge_to_game_start_max_by_bot_profile[profile_key] = latency

    async def record_game_end(
        self,
        game_id: str,
        result: str,
        status: int,
        ply: int | None,
        abort_diag: dict[str, object] | None = None,
        bot_profile: str | None = None,
    ) -> None:
        async with self._lock:
            if game_id in self._seen_game_end_ids:
                return
            self._seen_game_end_ids.add(game_id)
            self._unfinished_game_ids.discard(game_id)
            profile_key = bot_profile if isinstance(bot_profile, str) else "unknown"
            self.total_games += 1
            self.games_by_bot_profile[profile_key] += 1
            if status == 0:
                self.aborted_games += 1
                self.aborts_by_bot_profile[profile_key] += 1
                if abort_diag is not None:
                    self.aborts_by_phase[abort_diag.get("phase", "unknown")] += 1
                    self.aborts_by_end_source[abort_diag.get("end_source", "unknown")] += 1
                    self.aborts_by_turn[abort_diag.get("turn", "unknown")] += 1
                    self.aborts_by_moves_sent[abort_diag.get("moves_sent", "unknown")] += 1
                    self.aborts_by_variant[abort_diag.get("variant", "unknown")] += 1
                    self.aborts_by_elapsed_bucket[abort_diag.get("elapsed", "unknown")] += 1
            self.by_status[status] += 1
            self.by_result[result] += 1
            self.by_status_by_bot_profile[profile_key][status] += 1
            self.by_result_by_bot_profile[profile_key][result] += 1
            if ply is None:
                self.games_without_ply += 1
            else:
                self.by_game_length_ply[ply] += 1

    async def activity_snapshot(self) -> tuple[int, int, int, int]:
        """Starts, unfinished games, high-water mark, and observed ends.

        Unfinished means no terminal message was seen by the test client;
        it does not guarantee the round websocket is still connected.
        """
        async with self._lock:
            return (
                len(self._seen_game_start_ids),
                len(self._unfinished_game_ids),
                self.peak_unfinished_games,
                self.total_games,
            )

    async def snapshot(
        self,
    ) -> tuple[
        int,
        int,
        dict[int, int],
        dict[str, int],
        dict[int, int],
        int,
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, dict[int, int]],
        dict[str, dict[str, int]],
        dict[str, int],
        dict[str, int],
        dict[str, dict[str, float | int]],
    ]:
        async with self._lock:
            latency_by_bot_profile: dict[str, dict[str, float | int]] = {}
            for profile, count in self.challenge_to_game_start_count_by_bot_profile.items():
                if count <= 0:
                    continue
                total = self.challenge_to_game_start_sum_by_bot_profile[profile]
                min_latency = self.challenge_to_game_start_min_by_bot_profile.get(profile, 0.0)
                max_latency = self.challenge_to_game_start_max_by_bot_profile.get(profile, 0.0)
                latency_by_bot_profile[profile] = {
                    "count": count,
                    "avg_secs": round(total / count, 3),
                    "min_secs": round(min_latency, 3),
                    "max_secs": round(max_latency, 3),
                }
            return (
                self.total_games,
                self.aborted_games,
                dict(self.by_status),
                dict(self.by_result),
                dict(self.by_game_length_ply),
                self.games_without_ply,
                dict(self.aborts_by_phase),
                dict(self.aborts_by_end_source),
                dict(self.aborts_by_turn),
                dict(self.aborts_by_moves_sent),
                dict(self.aborts_by_variant),
                dict(self.aborts_by_elapsed_bucket),
                dict(self.games_by_bot_profile),
                dict(self.aborts_by_bot_profile),
                {
                    profile: dict(status_counter)
                    for profile, status_counter in self.by_status_by_bot_profile.items()
                },
                {
                    profile: dict(result_counter)
                    for profile, result_counter in self.by_result_by_bot_profile.items()
                },
                dict(self.challenges_sent_by_profile),
                dict(self.new_games_by_actual_bot_profile),
                latency_by_bot_profile,
            )


class HumanPair:
    """Coordinate one casual seek between two independent test-user sessions."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.ready = asyncio.Event()
        self.challenge_sent_at: float | None = None

    def register(self, role: str, username: str) -> None:
        self.names[role] = username
        if len(self.names) == 2:
            self.ready.set()

    @property
    def creator_name(self) -> str | None:
        return self.names.get("creator")


class TestUser:
    def __init__(
        self,
        spectators_per_game: int = DEFAULT_SPECTATORS_PER_GAME,
        games_target: int = DEFAULT_GAMES_PER_USER,
        challenge_delay_min_secs: float = DEFAULT_CHALLENGE_DELAY_MIN_SECS,
        challenge_delay_max_secs: float = DEFAULT_CHALLENGE_DELAY_MAX_SECS,
        challenge_retry_secs: float = DEFAULT_CHALLENGE_RETRY_SECS,
        game_minutes: int = 1,
        move_delay_secs: float = 0.0,
        spectator_request_gap_secs: float = DEFAULT_SPECTATOR_REQUEST_GAP_SECS,
        spectator_http_semaphore: asyncio.Semaphore | None = None,
        spectator_allocator: SpectatorAllocator | None = None,
        bot_scheduler: BotChallengeScheduler | None = None,
        run_stats: RunStats | None = None,
        test_user_pgn_exporter: TestUserPgnExporter | None = None,
        human_pair: HumanPair | None = None,
        human_role: str | None = None,
    ):
        self.username = ""
        self.seeks = []
        self.playing = False
        self.games_completed = 0
        self.games_target = games_target
        self.spectators_per_game = spectators_per_game
        self.spectator_request_gap_secs = spectator_request_gap_secs
        self.challenge_delay_min_secs = challenge_delay_min_secs
        self.challenge_delay_max_secs = challenge_delay_max_secs
        self.challenge_retry_secs = challenge_retry_secs
        self.game_minutes = game_minutes
        self.move_delay_secs = move_delay_secs
        self.spectator_http_semaphore = spectator_http_semaphore
        self.spectator_allocator = spectator_allocator
        self.bot_scheduler = bot_scheduler
        self.run_stats = run_stats
        self.test_user_pgn_exporter = test_user_pgn_exporter
        self.human_pair = human_pair
        self.human_role = human_role
        self.human_seek_sent = False
        self.human_accepted_seek_ids: set[str] = set()
        self.spectators = []
        self.round_tasks: set[asyncio.Task[None]] = set()
        self.active_round_games: set[str] = set()
        self.spectator_tasks: set[asyncio.Task[None]] = set()
        self.pending_challenges: deque[tuple[str, str, float, str | None]] = deque()
        self.game_variants: dict[str, str] = {}
        self.game_bot_profiles: dict[str, str] = {}
        self.game_challenge_sent_at: dict[str, float] = {}
        self.last_challenge_variant: str | None = None
        self.last_challenge_profile: str | None = None
        self.last_challenge_sent_at: float | None = None
        if self.human_pair is not None:
            # Both participants know their test variant before the first board.
            self.last_challenge_variant = "chess"
            self.last_challenge_profile = "Human"
        self.round_diag: dict[str, dict[str, object]] = {}

    def _is_transient_connection_error(self, exc: BaseException) -> bool:
        if self._is_fd_limit_error(exc):
            return True
        if isinstance(exc, (aiohttp.ClientError, ConnectionResetError, asyncio.TimeoutError)):
            return True
        return isinstance(exc, RuntimeError) and str(exc) == "Session is closed"

    def _is_fd_limit_error(self, exc: BaseException) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, OSError) and current.errno == 24:
                return True
            if isinstance(current, aiohttp.ClientConnectorError):
                os_error = current.os_error
                if isinstance(os_error, OSError) and os_error.errno == 24:
                    return True
            current = current.__cause__
        return False

    async def _send_json_safe(self, ws, payload) -> bool:
        try:
            await ws.send_json(payload)
            return True
        except Exception as exc:
            if self._is_transient_connection_error(exc):
                return False
            raise

    def _on_round_task_done(self, task: asyncio.Task[None], game_id: str) -> None:
        self.round_tasks.discard(task)
        self.active_round_games.discard(game_id)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if self._is_transient_connection_error(exc):
                return
            print(f"ROUND task failed for {self.username}: {exc!r}")

    def _on_spectator_task_done(self, task: asyncio.Task[None]) -> None:
        self.spectator_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if self._is_transient_connection_error(exc):
                return
            print(f"SPECTATOR task failed for {self.username}: {exc!r}")

    async def _cancel_round_tasks(self) -> None:
        if not self.round_tasks:
            return
        for task in list(self.round_tasks):
            task.cancel()
        await asyncio.gather(*self.round_tasks, return_exceptions=True)
        self.round_tasks.clear()
        self.active_round_games.clear()
        self.game_variants.clear()
        self.game_bot_profiles.clear()
        self.game_challenge_sent_at.clear()
        self.round_diag.clear()

    def _start_round_task(
        self,
        session: aiohttp.ClientSession,
        wsl,
        game_id: str,
        wplayer: str | None = None,
        bplayer: str | None = None,
        game_variant: str | None = None,
        game_bot_profile: str | None = None,
    ) -> None:
        if game_id in self.active_round_games:
            return
        if game_variant is not None:
            self.game_variants[game_id] = game_variant
        if game_bot_profile is not None:
            self.game_bot_profiles[game_id] = game_bot_profile
        self.playing = True
        task = asyncio.create_task(
            self.go_to_round(
                session,
                wsl,
                game_id,
                wplayer,
                bplayer,
                game_variant,
                game_bot_profile,
            )
        )
        self.round_tasks.add(task)
        self.active_round_games.add(game_id)
        task.add_done_callback(lambda done, gid=game_id: self._on_round_task_done(done, gid))

    async def _cancel_spectator_tasks(self) -> None:
        if not self.spectator_tasks:
            return
        for task in list(self.spectator_tasks):
            task.cancel()
        await asyncio.gather(*self.spectator_tasks, return_exceptions=True)
        self.spectator_tasks.clear()

    def _has_active_round_task(self) -> bool:
        return any(not task.done() for task in self.round_tasks)

    def _inflight_games(self) -> int:
        return len(self.pending_challenges) + len(self.active_round_games)

    def _can_issue_new_challenge(self) -> bool:
        # Keep one game per user in-flight by default when games_target is 1, and
        # never queue more potential games than the remaining target.
        remaining = self.games_target - self.games_completed
        return remaining > self._inflight_games() and not self._has_active_round_task()

    async def _prune_stale_pending_challenges(self) -> None:
        if not self.pending_challenges:
            return
        now = monotonic()
        while self.pending_challenges:
            sent_at = self.pending_challenges[0][2]
            if (now - sent_at) < DEFAULT_PENDING_CHALLENGE_MAX_WAIT_SECS:
                break
            _, profile, _, scheduler_token = self.pending_challenges.popleft()
            if self.bot_scheduler is not None:
                await self.bot_scheduler.release_pending(scheduler_token, profile)

    async def _send_create_ai_challenge(self, wsl) -> bool:
        challenge_variant = next(vari)
        challenge_profile = random.choice(BOT_PROFILES)
        scheduler_token: str | None = None
        if self.bot_scheduler is not None:
            challenge_profile, scheduler_token = await self.bot_scheduler.reserve_profile()
        payload = {
            "type": "create_ai_challenge",
            "profileid": challenge_profile,
            "variant": challenge_variant,
            "rm": challenge_profile == "Random-Mover",
            "fen": "",
            "color": "r",
            "minutes": self.game_minutes,
            "increment": 0,
            "byoyomiPeriod": 0,
            "level": 0,
            "chess960": False,
            "alternateStart": "",
        }
        await asyncio.sleep(
            random.uniform(
                self.challenge_delay_min_secs,
                self.challenge_delay_max_secs,
            )
        )
        try:
            sent = await self._send_json_safe(wsl, payload)
        except Exception:
            if self.bot_scheduler is not None:
                await self.bot_scheduler.release_pending(scheduler_token, challenge_profile)
            raise
        if sent:
            challenge_sent_at = monotonic()
            self.pending_challenges.append(
                (challenge_variant, challenge_profile, challenge_sent_at, scheduler_token)
            )
            self.last_challenge_variant = challenge_variant
            self.last_challenge_profile = challenge_profile
            self.last_challenge_sent_at = challenge_sent_at
            if self.run_stats is not None:
                await self.run_stats.record_challenge_sent(challenge_profile)
        elif self.bot_scheduler is not None:
            await self.bot_scheduler.release_pending(scheduler_token, challenge_profile)
        return sent

    async def _send_create_human_seek(self, wsl) -> bool:
        if self.human_pair is None or self.human_role != "creator":
            return False
        if not self.human_pair.ready.is_set() or self.human_seek_sent:
            return False
        payload = {
            "type": "create_seek",
            "variant": "chess",
            "fen": "",
            "color": "r",
            "minutes": self.game_minutes,
            "increment": 0,
            "byoyomiPeriod": 0,
            "rated": False,
            "chess960": False,
            "target": self.human_pair.names["acceptor"],
        }
        sent = await self._send_json_safe(wsl, payload)
        if sent:
            self.human_seek_sent = True
            sent_at = monotonic()
            self.human_pair.challenge_sent_at = sent_at
            self.pending_challenges.append(("chess", "Human", sent_at, None))
            self.last_challenge_sent_at = sent_at
            if self.run_stats is not None:
                await self.run_stats.record_challenge_sent("Human")
        return sent

    async def _accept_human_seek(self, wsl, seeks: list[dict]) -> None:
        if self.human_pair is None or self.human_role != "acceptor":
            return
        if self._has_active_round_task():
            return
        creator_name = self.human_pair.creator_name
        if creator_name is None:
            return
        for seek in seeks:
            if (
                seek.get("user") != creator_name
                or seek.get("variant") != "chess"
                or seek.get("target") != self.username
                or not isinstance(seek.get("seekID"), str)
            ):
                continue
            seek_id = seek["seekID"]
            if seek_id in self.human_accepted_seek_ids:
                return
            if await self._send_json_safe(wsl, {"type": "accept_seek", "seekID": seek_id}):
                self.human_accepted_seek_ids.add(seek_id)
            return

    def _variant_for_game(self, game_id: str) -> str | None:
        variant = self.game_variants.get(game_id)
        if variant is not None:
            return variant
        if self.pending_challenges:
            return self.pending_challenges[0][0]
        return self.last_challenge_variant

    def _profile_for_game(self, game_id: str) -> str | None:
        profile = self.game_bot_profiles.get(game_id)
        if profile is not None:
            return profile
        if self.pending_challenges:
            return self.pending_challenges[0][1]
        return self.last_challenge_profile

    def _actual_bot_profile(self, wplayer: str | None, bplayer: str | None) -> str | None:
        if isinstance(wplayer, str) and wplayer in ALL_BOT_PROFILES:
            return wplayer
        if isinstance(bplayer, str) and bplayer in ALL_BOT_PROFILES:
            return bplayer
        return None

    async def _bind_game_challenge(
        self, game_id: str
    ) -> tuple[str | None, str | None, float | None]:
        variant = self.game_variants.get(game_id)
        profile = self.game_bot_profiles.get(game_id)
        challenge_sent_at = self.game_challenge_sent_at.get(game_id)
        scheduler_token: str | None = None
        if variant is not None and profile is not None:
            return variant, profile, challenge_sent_at
        if self.pending_challenges:
            variant, profile, challenge_sent_at, scheduler_token = self.pending_challenges.popleft()
        else:
            variant = self.last_challenge_variant
            profile = self.last_challenge_profile
            challenge_sent_at = self.last_challenge_sent_at
        if variant is not None:
            self.game_variants[game_id] = variant
        if profile is not None:
            self.game_bot_profiles[game_id] = profile
        if isinstance(challenge_sent_at, (int, float)):
            sent_at = float(challenge_sent_at)
            self.game_challenge_sent_at[game_id] = sent_at
        else:
            sent_at = None
        if self.bot_scheduler is not None:
            await self.bot_scheduler.bind_game(scheduler_token, game_id, profile)
        return variant, profile, sent_at

    async def _release_bot_slot_for_game(self, game_id: str, profile: str | None = None) -> None:
        if self.bot_scheduler is None:
            return
        resolved_profile = profile if profile is not None else self.game_bot_profiles.get(game_id)
        await self.bot_scheduler.release_game(game_id, resolved_profile)

    async def _record_game_start(
        self,
        game_id: str,
        actual_bot_profile: str | None,
        challenge_sent_at: float | None,
    ) -> None:
        if self.run_stats is None:
            return
        latency_secs: float | None = None
        if self.human_pair is not None:
            # The acceptor normally sees new_game first, but did not send the seek.
            # Both participants must use the creator's timestamp for game latency.
            challenge_sent_at = self.human_pair.challenge_sent_at
        if isinstance(challenge_sent_at, (int, float)):
            latency_secs = max(0.0, monotonic() - challenge_sent_at)
        await self.run_stats.record_game_start(game_id, actual_bot_profile, latency_secs)

    def _diag_for_game(self, game_id: str) -> dict[str, object]:
        diag = self.round_diag.get(game_id)
        if diag is None:
            diag = {
                "round_ws_connected": False,
                "board_msgs": 0,
                "moves_sent": 0,
                "last_tp": None,
                "variant": self._variant_for_game(game_id),
                "bot_profile": self._profile_for_game(game_id),
                "connected_at": None,
            }
            self.round_diag[game_id] = diag
        return diag

    def _mark_round_connected(
        self, game_id: str, variant: str | None, bot_profile: str | None
    ) -> None:
        diag = self._diag_for_game(game_id)
        diag["round_ws_connected"] = True
        diag["connected_at"] = monotonic()
        if variant is not None:
            diag["variant"] = variant
        if bot_profile is not None:
            diag["bot_profile"] = bot_profile

    def _mark_board_seen(self, game_id: str, turn_player: object) -> None:
        diag = self._diag_for_game(game_id)
        board_msgs = diag.get("board_msgs", 0)
        diag["board_msgs"] = int(board_msgs) + 1
        if isinstance(turn_player, str):
            diag["last_tp"] = turn_player

    def _mark_move_sent(self, game_id: str) -> None:
        diag = self._diag_for_game(game_id)
        moves_sent = diag.get("moves_sent", 0)
        diag["moves_sent"] = int(moves_sent) + 1

    def _abort_diag(self, game_id: str, end_source: str) -> dict[str, object]:
        diag = self.round_diag.get(game_id, {})
        connected = bool(diag.get("round_ws_connected"))
        board_msgs = int(diag.get("board_msgs", 0))
        moves_sent = int(diag.get("moves_sent", 0))
        connected_at = diag.get("connected_at")

        if not connected:
            phase = "no_round_ws"
        elif board_msgs == 0:
            phase = "connected_no_board"
        elif moves_sent == 0:
            phase = "board_no_move"
        else:
            phase = "after_move"

        if moves_sent == 0:
            moves_bucket = "none"
        elif moves_sent == 1:
            moves_bucket = "one"
        else:
            moves_bucket = "many"

        last_tp = diag.get("last_tp")
        if isinstance(last_tp, str):
            turn_bucket = "my_turn" if last_tp == self.username else "opp_turn"
        else:
            turn_bucket = "unknown"

        elapsed_bucket = "unknown"
        if isinstance(connected_at, (int, float)):
            elapsed = monotonic() - connected_at
            if elapsed < 1.0:
                elapsed_bucket = "lt1s"
            elif elapsed < 5.0:
                elapsed_bucket = "1to5s"
            elif elapsed < 15.0:
                elapsed_bucket = "5to15s"
            elif elapsed < 30.0:
                elapsed_bucket = "15to30s"
            else:
                elapsed_bucket = "ge30s"

        variant = diag.get("variant")
        if not isinstance(variant, str):
            variant = "unknown"
        bot_profile = diag.get("bot_profile")
        if not isinstance(bot_profile, str):
            bot_profile = "unknown"

        return {
            "phase": phase,
            "end_source": end_source,
            "turn": turn_bucket,
            "moves_sent": moves_bucket,
            "variant": variant,
            "bot_profile": bot_profile,
            "elapsed": elapsed_bucket,
        }

    async def _record_game_end(
        self,
        game_id: str,
        result: str,
        status: int,
        ply: int | None,
        end_source: str = "unknown",
    ) -> None:
        print("END", game_id, result, status)
        abort_diag = self._abort_diag(game_id, end_source) if status == 0 else None
        bot_profile = self._profile_for_game(game_id)
        if self.run_stats is not None:
            await self.run_stats.record_game_end(
                game_id, result, status, ply, abort_diag, bot_profile
            )

    async def get(self, url=None):
        async with aiohttp.ClientSession(cookie_jar=make_cookie_jar()) as session:
            if url is not None:
                async with session.get(url) as resp:
                    print(resp.status)
                    text = await resp.text()
                    print(text[:80])
            else:
                while True:
                    await asyncio.sleep(random.choice((1, 2, 3, 4, 5)))
                    if url is None:
                        url = URI + "/" + random.choice(URLS)

                    async with session.get(url) as resp:
                        print(resp.status)
                        text = await resp.text()
                        print(text[:80])

    async def go_to_lobby(self):
        try:
            async with aiohttp.ClientSession(cookie_jar=make_cookie_jar()) as session:
                while True:
                    await self._prune_stale_pending_challenges()
                    if (
                        self.games_completed >= self.games_target
                        and not self._has_active_round_task()
                        and not self.pending_challenges
                    ):
                        break
                    async with session.get(URI) as resp:
                        if resp.status != 200:
                            raise RuntimeError(
                                f"Lobby GET {resp.url} failed: HTTP {resp.status}; "
                                f"Retry-After={resp.headers.get('Retry-After', 'n/a')}"
                            )
                        text = await resp.text()
                        try:
                            current_username = extract_username(text)
                        except RuntimeError as exc:
                            raise RuntimeError(
                                f"Lobby GET {resp.url} returned HTTP 200 but no username "
                                f"(content-type={resp.content_type}, body_length={len(text)})"
                            ) from exc
                        if self.username != current_username:
                            self.username = current_username
                            print(self.username)

                    try:
                        async with session.ws_connect(LOBBY_URL, headers={"Origin": URI}) as wsl:
                            # await wsl.send_json({"type": "lobby_user_connected", "username": self.username})
                            # await wsl.send_json({"type": "get_seeks"})
                            loop_time = asyncio.get_running_loop().time
                            last_challenge_sent = loop_time()
                            last_lobby_msg = last_challenge_sent
                            self.playing = self._has_active_round_task()

                            async def maybe_send_challenge(now: float) -> float:
                                if self.human_pair is not None:
                                    if self._can_issue_new_challenge() and await self._send_create_human_seek(wsl):
                                        return loop_time()
                                    return last_challenge_sent
                                if (
                                    self._can_issue_new_challenge()
                                    and self.challenge_retry_secs > 0
                                    and (now - last_challenge_sent) >= self.challenge_retry_secs
                                ) and await self._send_create_ai_challenge(wsl):
                                    return loop_time()
                                return last_challenge_sent

                            if self.human_pair is None and (
                                self._can_issue_new_challenge()
                                and await self._send_create_ai_challenge(wsl)
                            ):
                                last_challenge_sent = loop_time()

                            while True:
                                try:
                                    msg = await asyncio.wait_for(
                                        wsl.receive(),
                                        timeout=DEFAULT_LOBBY_RECV_TIMEOUT_SECS,
                                    )
                                except TimeoutError:
                                    now = loop_time()
                                    await self._prune_stale_pending_challenges()
                                    last_challenge_sent = await maybe_send_challenge(now)
                                    if (now - last_lobby_msg) >= DEFAULT_LOBBY_STALE_RECONNECT_SECS:
                                        break
                                    continue

                                await self._prune_stale_pending_challenges()
                                last_lobby_msg = loop_time()
                                # print('Lobby message received from server:', msg)

                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    # print('Lobby message received from server:', data["type"])
                                    if data["type"] == "ping":
                                        await self._send_json_safe(wsl, {"type": "pong"})
                                        last_challenge_sent = await maybe_send_challenge(
                                            loop_time()
                                        )

                                    elif data["type"] == "new_game":
                                        game_id = data["gameId"]
                                        wplayer = data["wplayer"]
                                        bplayer = data["bplayer"]
                                        spectators_for_this_game = self.spectators_per_game
                                        if self.spectator_allocator is not None:
                                            spectators_for_this_game = (
                                                await self.spectator_allocator.count_for_game(
                                                    game_id
                                                )
                                            )
                                        if spectators_for_this_game > 0:
                                            spectator_task = asyncio.create_task(
                                                spectators(
                                                    game_id,
                                                    spectators_for_this_game,
                                                    self.spectator_request_gap_secs,
                                                    self.spectator_http_semaphore,
                                                )
                                            )
                                            self.spectator_tasks.add(spectator_task)
                                            spectator_task.add_done_callback(
                                                self._on_spectator_task_done
                                            )

                                        if self.username in (wplayer, bplayer):
                                            (
                                                game_variant,
                                                game_bot_profile,
                                                challenge_sent_at,
                                            ) = await self._bind_game_challenge(game_id)
                                            actual_bot_profile = self._actual_bot_profile(
                                                wplayer, bplayer
                                            )
                                            if actual_bot_profile is not None:
                                                game_bot_profile = actual_bot_profile
                                                self.game_bot_profiles[game_id] = actual_bot_profile
                                            await self._record_game_start(
                                                game_id,
                                                "Human" if self.human_pair is not None else (actual_bot_profile or game_bot_profile),
                                                challenge_sent_at,
                                            )
                                            self._start_round_task(
                                                session,
                                                wsl,
                                                game_id,
                                                wplayer,
                                                bplayer,
                                                game_variant,
                                                game_bot_profile,
                                            )

                                    elif data["type"] == "game_in_progress":
                                        game_id = data["gameId"]
                                        (
                                            game_variant,
                                            game_bot_profile,
                                            challenge_sent_at,
                                        ) = await self._bind_game_challenge(game_id)
                                        await self._record_game_start(
                                            game_id,
                                            "Human" if self.human_pair is not None else game_bot_profile,
                                            challenge_sent_at,
                                        )
                                        self._start_round_task(
                                            session,
                                            wsl,
                                            game_id,
                                            game_variant=game_variant,
                                            game_bot_profile=game_bot_profile,
                                        )

                                    elif data["type"] == "get_seeks" and self.human_pair is not None:
                                        await self._accept_human_seek(wsl, data.get("seeks", []))
                                    elif data["type"] == "lobby_user_connected":
                                        if data.get("username") == self.username:
                                            print("Connected as %s" % data["username"])
                                            if self.human_pair is not None and self.human_role is not None:
                                                self.human_pair.register(self.human_role, self.username)
                                                last_challenge_sent = await maybe_send_challenge(loop_time())
                                    elif data["type"] == "error" and self.human_pair is not None:
                                        raise RuntimeError(
                                            f"Human matchmaking failed for {self.username}: "
                                            f"{data.get('message')}"
                                        )
                                    elif data["type"] == "error" and self.pending_challenges:
                                        _, profile, _, scheduler_token = (
                                            self.pending_challenges.popleft()
                                        )
                                        if self.bot_scheduler is not None:
                                            await self.bot_scheduler.release_pending(
                                                scheduler_token, profile
                                            )

                                elif msg.type in (
                                    aiohttp.WSMsgType.CLOSED,
                                    aiohttp.WSMsgType.ERROR,
                                    aiohttp.WSMsgType.CLOSING,
                                    aiohttp.WSMsgType.CLOSE,
                                ):
                                    break
                            await wsl.close()
                    except Exception as exc:
                        if not self._is_transient_connection_error(exc):
                            raise
                        # Hitting EMFILE needs a longer cool-off to let sockets close.
                        if self._is_fd_limit_error(exc):
                            await asyncio.sleep(random.uniform(1.0, 3.0))

                    if self.games_completed < self.games_target:
                        await asyncio.sleep(random.uniform(0.1, 0.5))
        finally:
            await self._cancel_round_tasks()
            await self._cancel_spectator_tasks()

    # @profile
    async def go_to_round(
        self,
        session,
        wsl,
        game_id: str,
        wplayer: str | None = None,
        bplayer: str | None = None,
        game_variant: str | None = None,
        game_bot_profile: str | None = None,
    ):
        print("---------ROUND baby")
        game_completed = False
        last_ply: int | None = None
        last_sent_ply: int | None = None
        resolved_variant = game_variant or self._variant_for_game(game_id)
        resolved_bot_profile = game_bot_profile or self._profile_for_game(game_id)
        try:
            mycolor: str | None = None
            if wplayer is not None and self.username == wplayer:
                mycolor = "w"
            elif bplayer is not None and self.username == bplayer:
                mycolor = "b"
            if wplayer is not None and bplayer is not None:
                opp_name = bplayer if self.username == wplayer else wplayer
                if opp_name in ALL_BOT_PROFILES:
                    resolved_bot_profile = opp_name
                    self.game_bot_profiles[game_id] = opp_name

            while not game_completed:
                reconnect_needed = False
                try:
                    async with session.ws_connect(
                        ROUND_URL + game_id, timeout=20.0, headers={"Origin": URI}
                    ) as wsr:
                        self._mark_round_connected(game_id, resolved_variant, resolved_bot_profile)
                        # TODO: am I player or am I spectator ???
                        ok = await self._send_json_safe(
                            wsr,
                            {
                                "type": "game_user_connected",
                                "username": self.username,
                                "gameId": game_id,
                            },
                        )
                        if not ok:
                            reconnect_needed = True
                            continue

                        # TODO: spectator or player chat?
                        await self.send_round_chat(wsr, "Hi!", game_id, "spectator")
                        round_idle_cycles = 0
                        while True:
                            try:
                                msg = await asyncio.wait_for(
                                    wsr.receive(),
                                    timeout=DEFAULT_ROUND_RECV_TIMEOUT_SECS,
                                )
                            except TimeoutError:
                                round_idle_cycles += 1
                                if round_idle_cycles >= DEFAULT_ROUND_MAX_IDLE_CYCLES:
                                    reconnect_needed = True
                                    break
                                await self._send_json_safe(
                                    wsr, {"type": "board", "gameId": game_id}
                                )
                                continue
                            # print('Round message received from server:', msg)
                            round_idle_cycles = 0

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                try:
                                    if "type" not in data:
                                        pass

                                    elif data["type"] == "game_user_connected":
                                        await self._send_json_safe(
                                            wsr, {"type": "ready", "gameId": game_id}
                                        )
                                        await self._send_json_safe(
                                            wsr, {"type": "board", "gameId": game_id}
                                        )

                                    elif data["type"] == "board":
                                        board_variant = data.get("variant")
                                        if isinstance(board_variant, str):
                                            resolved_variant = board_variant
                                            self.game_variants[game_id] = board_variant
                                            diag = self._diag_for_game(game_id)
                                            diag["variant"] = board_variant
                                        board_tp = data.get("tp")
                                        if (
                                            isinstance(board_tp, str)
                                            and board_tp in ALL_BOT_PROFILES
                                        ):
                                            resolved_bot_profile = board_tp
                                            self.game_bot_profiles[game_id] = board_tp
                                            diag = self._diag_for_game(game_id)
                                            diag["bot_profile"] = board_tp
                                        board_ply = data.get("ply")
                                        if isinstance(board_ply, int):
                                            last_ply = board_ply
                                        self._mark_board_seen(game_id, data.get("tp"))
                                        if data["result"] != "*":
                                            await self._record_game_end(
                                                game_id,
                                                data["result"],
                                                data["status"],
                                                board_ply
                                                if isinstance(board_ply, int)
                                                else last_ply,
                                                "board",
                                            )
                                            self.playing = False
                                            if not game_completed:
                                                self.games_completed += 1
                                                game_completed = True
                                                if (
                                                    self.test_user_pgn_exporter is not None
                                                    and data["status"] != 0
                                                ):
                                                    await self.test_user_pgn_exporter.maybe_export(
                                                        session, self.username
                                                    )
                                            await self._release_bot_slot_for_game(
                                                game_id, resolved_bot_profile
                                            )
                                            self.game_variants.pop(game_id, None)
                                            self.game_bot_profiles.pop(game_id, None)
                                            self.game_challenge_sent_at.pop(game_id, None)
                                            self.round_diag.pop(game_id, None)
                                            await self._send_json_safe(wsr, {"type": "logout"})
                                            await self._send_json_safe(wsl, {"type": "logout"})
                                            break

                                        await asyncio.sleep(random.uniform(0, 0.1))
                                        parts = data["fen"].split(" ")
                                        turn_color = parts[1]
                                        variant_for_moves = (
                                            resolved_variant or self._variant_for_game(game_id)
                                        )
                                        if variant_for_moves is None:
                                            continue
                                        resolved_variant = variant_for_moves
                                        should_move = (
                                            (turn_color == mycolor)
                                            if mycolor is not None
                                            else data.get("tp") == self.username
                                        )
                                        if self.human_pair is not None and (
                                            not should_move or last_sent_ply == board_ply
                                        ):
                                            continue
                                        legal_moves = sf.legal_moves(
                                            variant_for_moves, data["fen"], [], False
                                        )
                                        if legal_moves and should_move:
                                            if self.move_delay_secs:
                                                await asyncio.sleep(self.move_delay_secs)
                                            sent = await self._send_json_safe(
                                                wsr,
                                                {
                                                    "type": "move",
                                                    "gameId": game_id,
                                                    "move": random.choice(legal_moves),
                                                    "clocks": data["clocks"],
                                                    "ply": data["ply"] + 1,
                                                },
                                            )
                                            if sent:
                                                self._mark_move_sent(game_id)
                                                if self.human_pair is not None:
                                                    last_sent_ply = board_ply
                                            await asyncio.sleep(0)

                                    elif data["type"] == "setup":
                                        setup_color = (
                                            "white"
                                            if mycolor == "w"
                                            else "black"
                                            if mycolor == "b"
                                            else data.get("color", "white")
                                        )
                                        response = {
                                            "type": "setup",
                                            "gameId": game_id,
                                            "color": setup_color,
                                            "fen": data["fen"],
                                        }
                                        await self._send_json_safe(wsr, response)

                                    elif data["type"] == "gameStart":
                                        print("START", game_id)

                                    elif data["type"] == "gameEnd":
                                        game_end_ply = data.get("ply")
                                        if not isinstance(game_end_ply, int):
                                            game_end_ply = last_ply
                                        await self._record_game_end(
                                            game_id,
                                            data["result"],
                                            data["status"],
                                            game_end_ply,
                                            "gameEnd",
                                        )
                                        self.playing = False
                                        if not game_completed:
                                            self.games_completed += 1
                                            game_completed = True
                                            if (
                                                self.test_user_pgn_exporter is not None
                                                and data["status"] != 0
                                            ):
                                                await self.test_user_pgn_exporter.maybe_export(
                                                    session, self.username
                                                )
                                        await self._release_bot_slot_for_game(
                                            game_id, resolved_bot_profile
                                        )
                                        self.game_variants.pop(game_id, None)
                                        self.game_bot_profiles.pop(game_id, None)
                                        self.game_challenge_sent_at.pop(game_id, None)
                                        self.round_diag.pop(game_id, None)
                                        await self._send_json_safe(wsr, {"type": "logout"})
                                        await self._send_json_safe(wsl, {"type": "logout"})
                                        break
                                except Exception:
                                    print("FAILED wsr msg", msg)

                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.CLOSE,
                            ):
                                reconnect_needed = not game_completed
                                break
                        await wsr.close()
                except Exception as exc:
                    if not self._is_transient_connection_error(exc):
                        raise
                    reconnect_needed = True

                if game_completed or not reconnect_needed:
                    break
                await asyncio.sleep(
                    random.uniform(
                        DEFAULT_ROUND_RECONNECT_BACKOFF_MIN_SECS,
                        DEFAULT_ROUND_RECONNECT_BACKOFF_MAX_SECS,
                    )
                )
        except Exception as exc:
            if not self._is_transient_connection_error(exc):
                raise
        finally:
            if not game_completed:
                self.playing = False
            if game_completed:
                await self._release_bot_slot_for_game(game_id, resolved_bot_profile)
                self.game_variants.pop(game_id, None)
                self.game_bot_profiles.pop(game_id, None)
                self.game_challenge_sent_at.pop(game_id, None)
                self.round_diag.pop(game_id, None)

    async def send_round_chat(self, ws, message, game_id, room):
        await ws_send_json(
            ws,
            {
                "type": "roundchat",
                "message": message,
                "gameId": game_id,
                "user": self.username,
                "room": room,
            },
        )


async def _fetch_spectator_page(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore | None
) -> None:
    try:
        if semaphore is not None:
            async with semaphore, session.get(url) as resp:
                print(resp.status)
                text = await resp.text()
                print(text[:80])
            return
        async with session.get(url) as resp:
            print(resp.status)
            text = await resp.text()
            print(text[:80])
    except Exception as exc:
        if isinstance(exc, (aiohttp.ClientError, ConnectionResetError, asyncio.TimeoutError)):
            return
        print(f"SPECTATOR fetch failed: {exc!r}")


async def spectators(
    game_id: str,
    count: int,
    request_gap_secs: float,
    semaphore: asyncio.Semaphore | None,
):
    if count == 0:
        return
    tasks = []
    url = URI + "/" + game_id
    async with aiohttp.ClientSession(cookie_jar=make_cookie_jar()) as session:
        for i in range(count):
            if request_gap_secs > 0 and i > 0:
                await asyncio.sleep(request_gap_secs)
            tasks.append(asyncio.create_task(_fetch_spectator_page(session, url, semaphore)))
        await asyncio.gather(*tasks, return_exceptions=True)


async def main(args: argparse.Namespace):
    spectator_http_semaphore = asyncio.Semaphore(args.max_spectator_http_concurrency)
    run_stats = RunStats()
    test_user_pgn_exporter = TestUserPgnExporter(args.pgn_max_games) if args.test_user_pgn else None
    bot_scheduler = None if args.human_vs_human else BotChallengeScheduler()
    spectator_allocator = SpectatorAllocator(
        featured_games=args.featured_games,
        featured_count=args.spectators_per_game,
        regular_count=args.spectators_regular_per_game,
    )
    human_pairs = [HumanPair() for _ in range(args.users // 2)] if args.human_vs_human else []
    users = [
        TestUser(
            spectators_per_game=args.spectators_per_game,
            games_target=args.games_per_user,
            challenge_delay_min_secs=args.challenge_delay_min_secs,
            challenge_delay_max_secs=args.challenge_delay_max_secs,
            challenge_retry_secs=args.challenge_retry_secs,
            game_minutes=args.game_minutes,
            move_delay_secs=args.move_delay_secs,
            spectator_request_gap_secs=args.spectator_request_gap_secs,
            spectator_http_semaphore=spectator_http_semaphore,
            spectator_allocator=spectator_allocator,
            bot_scheduler=bot_scheduler,
            run_stats=run_stats,
            test_user_pgn_exporter=test_user_pgn_exporter,
            human_pair=human_pairs[i // 2] if args.human_vs_human else None,
            human_role=("creator" if i % 2 == 0 else "acceptor") if args.human_vs_human else None,
        )
        for i in range(args.users)
    ]

    if args.human_vs_human:
        print(f"Human vs human: {args.users} players, {args.users // 2} paired games")

    async def start_user(user: TestUser):
        if args.user_start_spread_secs > 0:
            await asyncio.sleep(random.uniform(0, args.user_start_spread_secs))
        await user.go_to_lobby()

    pgn_cookie: str | None = None
    if args.pgn_cookie_file is not None:
        pgn_cookie = read_session_cookie(args.pgn_cookie_file)
    http_task = (
        asyncio.create_task(
            run_http_workload(
                rps=args.http_rps,
                duration=args.http_duration_secs,
                concurrency=args.http_concurrency,
                pgn_cookie=pgn_cookie,
                pgn_max_games=args.pgn_max_games,
            )
        )
        if args.http_rps > 0
        else None
    )
    tasks = [asyncio.create_task(start_user(user)) for user in users]

    async def report_activity() -> None:
        began = monotonic()
        while True:
            await asyncio.sleep(args.report_interval_secs)
            started, unfinished, peak, ended = await run_stats.activity_snapshot()
            print(
                f"game_load_elapsed_secs={monotonic() - began:.1f} "
                f"games_started={started} games_unfinished={unfinished} "
                f"peak_unfinished={peak} games_ended={ended}",
                flush=True,
            )

    reporter = (
        asyncio.create_task(report_activity()) if args.report_interval_secs > 0 else None
    )
    try:
        if args.run_duration_secs > 0:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=args.run_duration_secs)
            except TimeoutError:
                print(f"Game load stopped after {args.run_duration_secs:g}s (partial game stats).")
        else:
            await asyncio.gather(*tasks)
    finally:
        if reporter is not None:
            reporter.cancel()
            await asyncio.gather(reporter, return_exceptions=True)
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if http_task is not None:
            # Continue HTTP load to its intended deadline if games ended early.
            http_stats = await http_task
            http_stats.report()
        if test_user_pgn_exporter is not None:
            test_user_pgn_exporter.report()
    (
        total_games,
        aborted_games,
        by_status,
        by_result,
        by_game_length_ply,
        games_without_ply,
        aborts_by_phase,
        aborts_by_end_source,
        aborts_by_turn,
        aborts_by_moves_sent,
        aborts_by_variant,
        aborts_by_elapsed_bucket,
        games_by_bot_profile,
        aborts_by_bot_profile,
        by_status_by_bot_profile,
        by_result_by_bot_profile,
        challenges_sent_by_profile,
        new_games_by_actual_bot_profile,
        challenge_to_game_start_latency_by_bot_profile,
    ) = await run_stats.snapshot()
    abort_ratio = (aborted_games / total_games * 100.0) if total_games else 0.0
    abort_ratio_by_bot_profile = {
        profile: round((aborts_by_bot_profile.get(profile, 0) / games) * 100.0, 1) if games else 0.0
        for profile, games in sorted(games_by_bot_profile.items())
    }
    sorted_status_by_bot_profile = {
        profile: dict(sorted(status_map.items()))
        for profile, status_map in sorted(by_status_by_bot_profile.items())
    }
    sorted_result_by_bot_profile = {
        profile: dict(sorted(result_map.items()))
        for profile, result_map in sorted(by_result_by_bot_profile.items())
    }
    started_games, unfinished_games, peak_unfinished, _ = await run_stats.activity_snapshot()
    print("=== STRESS SUMMARY ===")
    print(f"games_started={started_games}")
    print(f"games_unfinished_at_stop={unfinished_games}")
    print(f"peak_unfinished_games={peak_unfinished}")
    print(f"games_total={total_games}")
    print(f"games_aborted={aborted_games} ({abort_ratio:.1f}%)")
    print(f"by_status={dict(sorted(by_status.items()))}")
    print(f"by_result={dict(sorted(by_result.items()))}")
    print(f"by_game_length_ply={dict(sorted(by_game_length_ply.items()))}")
    print(f"games_without_ply={games_without_ply}")
    print(f"aborts_by_phase={dict(sorted(aborts_by_phase.items()))}")
    print(f"aborts_by_end_source={dict(sorted(aborts_by_end_source.items()))}")
    print(f"aborts_by_turn={dict(sorted(aborts_by_turn.items()))}")
    print(f"aborts_by_moves_sent={dict(sorted(aborts_by_moves_sent.items()))}")
    print(f"aborts_by_variant={dict(sorted(aborts_by_variant.items()))}")
    print(f"aborts_by_elapsed_bucket={dict(sorted(aborts_by_elapsed_bucket.items()))}")
    print(f"games_by_bot_profile={dict(sorted(games_by_bot_profile.items()))}")
    print(f"aborts_by_bot_profile={dict(sorted(aborts_by_bot_profile.items()))}")
    print(f"abort_ratio_by_bot_profile={abort_ratio_by_bot_profile}")
    print(f"by_status_by_bot_profile={sorted_status_by_bot_profile}")
    print(f"by_result_by_bot_profile={sorted_result_by_bot_profile}")
    print(f"challenges_sent_by_profile={dict(sorted(challenges_sent_by_profile.items()))}")
    print(
        f"new_games_by_actual_bot_profile={dict(sorted(new_games_by_actual_bot_profile.items()))}"
    )
    print(
        "challenge_to_game_start_latency_by_bot_profile="
        f"{dict(sorted(challenge_to_game_start_latency_by_bot_profile.items()))}"
    )


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
