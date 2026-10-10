from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING, Literal, cast

from broadcast import round_broadcast
from catalogued_variants import (
    catalogued_variant_games_are_persisted,
    increment_catalogued_variant_game_count,
    increment_catalogued_variant_game_count_once,
)
from clock import Clock, CorrClock
from compress import R2C
from const import (
    ABORTED,
    CASUAL,
    CHEAT,
    CLAIM,
    CREATED,
    DARK_FEN,
    DRAW,
    FLAG,
    HIGHSCORE_MIN_GAMES,
    IMPORTED,
    INVALIDMOVE,
    LOSERS,
    MATE,
    MAX_CHAT_LINES,
    MAX_HIGHSCORE_ITEM_LIMIT,
    RATED,
    STALEMATE,
    STARTED,
    VARIANT_960_TO_PGN,
    VARIANTEND,
)
from convert import grand2zero, mirror5, mirror9, uci2usi
from draw import reject_draw
from fairy import (
    BLACK,
    NOTATION_SAN,
    RANDOM_START_VARIANTS,
    WHITE,
    FairyBoard,
    get_fog_fen,
    get_san_moves,
    modded_variant,
)
from glicko2.glicko2 import Rating, gl2
from lobby_panels_cache import refresh_lobby_leaderboard_cache
from rated_start import can_rate_start, can_rate_variant
from settings import URI
from spectators import spectators
from typing_defs import (
    AnalysisStep,
    ClockValues,
    Crosstable,
    GameBoardResponse,
    GameDisplayHistory,
    GameEndResponse,
    GameStep,
    GameSummaryJson,
    PerfEntry,
    TvGameJson,
)
from variants import (
    GRANDS,
    CataloguedServerVariant,
    ServerVariants,
    catalogued_variant_random_start,
    get_server_variant,
    is_catalogued_variant,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
    from ws_types import SpectatorsMessage

MAX_PLY = 600
HISTORICAL_REPLAY_GRACE_PERIOD = timedelta(days=180)

INVALID_PAWN_DROP_MATE = (
    ("P@", "shogi"),
    ("P@", "minishogi"),
    ("P@", "gorogoro"),
    ("P@", "gorogoroplus"),
    ("S@", "torishogi"),
)


class StaleMovePersistenceError(RuntimeError):
    """The database advanced from a different in-memory game position."""


def is_legacy_capablanca_castling_move(move: str) -> bool:
    if len(move) < 4:
        return False
    from_sq = move[:2]
    to_sq = move[2:4]
    return from_sq in ("e1", "e8") and to_sq in ("c1", "i1", "c8", "i8")


def should_use_legacy_capablanca_replay(
    game_variant: str,
    board_variant: str,
    chess960: bool,
    move_stack: Sequence[str],
) -> bool:
    if chess960:
        return False
    if game_variant not in ("capablanca", "capahouse"):
        return False
    if board_variant not in ("embassy", "embassyhouse"):
        return False
    return any(is_legacy_capablanca_castling_move(move) for move in move_stack)


def should_tolerate_historical_replay_failure(
    game_date: datetime,
    game_status: int,
    loaded_at: datetime | None = None,
) -> bool:
    if game_status <= STARTED:
        return False

    if game_date.tzinfo is None:
        game_date = game_date.replace(tzinfo=UTC)

    reference_time = loaded_at if loaded_at is not None else datetime.now(UTC)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=UTC)

    return (reference_time - game_date) >= HISTORICAL_REPLAY_GRACE_PERIOD


class Game:
    wrank: int
    brank: int

    def __init__(
        self,
        app_state: PychessGlobalAppState,
        gameId: str,
        variant: str,
        initial_fen: str,
        wplayer: User,
        bplayer: User,
        base: float = 1,
        inc: int = 0,
        byoyomi_period: int = 0,
        level: int | None = 0,
        rated: int | None = CASUAL,
        chess960: bool | None = False,
        corr: bool = False,
        create: bool = True,
        tournamentId: str | None = None,
        tournamentArrangementId: str | None = None,
        simulId: str | None = None,
        initial_clocks: tuple[int | float, int | float] | None = None,
        new_960_fen_needed_for_rematch: bool = False,
        is_rematch: bool = False,
    ) -> None:
        self.app_state: PychessGlobalAppState = app_state

        self.saved: bool = False

        self.variant: str = variant
        self.initial_fen: str = initial_fen
        self.wplayer: User = wplayer
        self.bplayer: User = bplayer

        catalogued_casual = is_catalogued_variant(variant)
        self.persist_to_db: bool = (
            (not catalogued_casual)
            or (not create)
            or catalogued_variant_games_are_persisted(app_state, variant)
        )
        if catalogued_casual:
            # Uploaded variants are casual-only. They can still be used in
            # normal games, public correspondence games, unrated tournaments,
            # and simuls. Only public catalogued variants create durable game
            # documents; private and unlisted games are in-memory tests decided
            # at creation time.
            rated = CASUAL
            if create:
                chess960 = catalogued_variant_random_start(variant) and (
                    not initial_fen or bool(chess960)
                )
        elif (
            create
            and rated == RATED
            and not can_rate_start(
                variant,
                initial_fen,
                bool(chess960),
                is_rematch=is_rematch,
            )
        ):
            # Do not trust clients to rate casual-only variants or unapproved
            # custom starting positions.
            rated = CASUAL

        self.bot_game: bool = self.bplayer.bot or self.wplayer.bot

        self.all_players: list[User] = [self.wplayer, self.bplayer]
        self.non_bot_players: list[User] = [player for player in self.all_players if not player.bot]

        self.rated: int | None = rated
        self.base: int | float = base
        self.inc: int = inc
        self.level: int = level if level is not None else 0
        self.tournamentId: str | None = tournamentId
        self.tournamentArrangementId: str | None = tournamentArrangementId
        if self.tournamentId is None and self.tournamentArrangementId:
            # RR arrangement ids are namespaced by tournament id, so recover the
            # tournament link even if only the arrangement id is provided.
            self.tournamentId = self.tournamentArrangementId.split(":", 1)[0]
        self.simulId: str | None = simulId
        self.simulHostColor: str | None = None
        self.chess960: bool | None = chess960
        self.corr: bool = corr
        self.create: bool = create
        self.new_960_fen_needed_for_rematch: bool = new_960_fen_needed_for_rematch
        self.imported_by: str = ""

        self.server_variant: ServerVariants | CataloguedServerVariant = get_server_variant(
            variant, chess960
        )
        self.encode_method: Callable[[str], str] = self.server_variant.move_encoding

        self.berserk_time: int | float = self.base * 1000 * 30

        self.browser_title: str = "%s • %s vs %s" % (
            self.server_variant.display_name.title(),
            self.wplayer.username,
            self.bplayer.username,
        )

        # Casual-only variants have no ratings or leaderboards, so avoid
        # creating transient performance entries for them.
        if catalogued_casual or not can_rate_variant(variant, bool(chess960)):
            self.wrating = "1500?"
            self.brating = "1500?"
        else:
            white_rating = wplayer.get_rating(variant, chess960)
            self.wrating = "%s%s" % white_rating.rating_prov
            black_rating = bplayer.get_rating(variant, chess960)
            self.brating = "%s%s" % black_rating.rating_prov
        self.wrdiff: int | str = 0
        self.brdiff: int | str = 0

        # crosstable info (this have to be updated after game creation from db !)
        self.need_crosstable_save: bool = False
        self.has_crosstable: bool = self.persist_to_db and not (
            self.bot_game or self.wplayer.anon or self.bplayer.anon
        )
        if self.has_crosstable:
            if self.wplayer.username < self.bplayer.username:
                self.s1player: str = self.wplayer.username
                self.s2player: str = self.bplayer.username
            else:
                self.s1player = self.bplayer.username
                self.s2player = self.wplayer.username
            self.ct_id: str = self.s1player + "/" + self.s2player
            self.crosstable: Crosstable | str = {
                "_id": self.ct_id,
                "s1": 0,
                "s2": 0,
                "r": [],
            }
        else:
            self.ct_id = ""
            self.crosstable = ""

        self.spectators: set[User] = set()
        self.draw_offers: set[str] = set()
        # (username, ply) for an outstanding two-player takeback proposal.
        # The ply snapshot prevents accepting an offer after the position changed.
        self.takeback_offer: tuple[str, int] | None = None
        self.rematch_offers: set[str] = set()
        self.rematch_id: str | None = None
        self.messages: collections.deque = collections.deque([], MAX_CHAT_LINES)

        self.date: datetime = datetime.now(UTC)
        self.loaded_at: datetime | None = None
        self.analysis: list[AnalysisStep] | None = None

        clocks_init = (base * 1000 * 60) + 0 if base > 0 else inc * 1000
        if initial_clocks is None:
            self.clocks_w: list[int | float] = [clocks_init]
            self.clocks_b: list[int | float] = [clocks_init]
        else:
            self.clocks_w = [initial_clocks[0]]
            self.clocks_b = [initial_clocks[1]]

        self.lastmove: str | None = None
        self.check: bool = False
        self.status: int = CREATED
        # Tracks whether this game currently contributes to the global active
        # game count. Janggi can be STARTED at ply 0 after setup, so status and
        # ply alone are not sufficient lifecycle indicators.
        self.counted_as_active = False
        self.result: str = "*"
        self.last_server_clock: float = monotonic()
        self.last_move_time: datetime | None = None
        # Wall-clock time which elapsed on the current turn before this Game
        # instance was reconstructed after a server restart. ``monotonic()``
        # cannot span processes, so restart recovery records the missing part
        # once. Games with durable clock history use it for authoritative clock
        # decisions; other games retain it only for the existing UI adjustment.
        self.restart_elapsed_ms: int = 0

        self.id: str = gameId

        self.fow: bool = variant == "fogofwar"
        self.jieqi: bool = self.variant == "jieqi"

        # Jieqi captures must be tracked per side; the opponent
        # and spectators must never learn the identities of captured covered pieces.
        self.jieqi_captures: dict[int, list[str]] | None = (
            {WHITE: [], BLACK: []} if self.jieqi else None
        )

        # Stack mirrors move history so takebacks can roll capture identities back safely.
        self.jieqi_capture_stack: list[tuple[int, str] | None] | None = [] if self.jieqi else None

        # One-move hint used to send capture identity to the current mover only.
        self.last_jieqi_capture: str | None = None

        self.n_fold_is_draw = self.server_variant.n_fold_is_draw or self.variant in (
            "makruk",
            "makpong",
            "cambodian",
            "shogi",
            "shoshogi",
            "dobutsu",
            "gorogoro",
            "gorogoroplus",
            "kyotoshogi",
        )
        self.has_counting = self.variant in ("makruk", "makpong", "cambodian", "sittuyin", "asean")
        # Makruk manual counting
        use_manual_counting = self.variant in ("makruk", "makpong", "cambodian")
        self.manual_count = use_manual_counting and not self.bot_game
        self.manual_count_toggled: list[tuple[int, int]] = []
        self.mct: list[tuple[int, int]] | None = None

        # Old USI Shogi games saved using usi2uci() need special handling in create_steps()
        self.usi_format = False

        # Some variants randomize their default start without using Chess960 rules.
        self.random_only = self.variant in RANDOM_START_VARIANTS

        # Calculate the start of manual counting
        count_started = 0
        if self.manual_count:
            count_started = -1
            if self.initial_fen:
                parts = self.initial_fen.split()
                board_state = parts[0]
                side_to_move = parts[1]
                counting_limit = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
                counting_ply = int(parts[4]) if len(parts) >= 5 else 0
                move_number = int(parts[5]) if len(parts) >= 6 else 0

                white_pieces = sum(1 for c in board_state if c.isupper())
                black_pieces = sum(1 for c in board_state if c.islower())
                pawns = sum(1 for c in board_state if c in ("P", "p"))
                if counting_limit > 0 and counting_ply > 0:
                    if pawns == 0 and (white_pieces <= 1 or black_pieces <= 1):
                        # Disable manual count if either side is already down to lone king
                        count_started = 0
                        self.manual_count = False
                    else:
                        last_ply = 2 * move_number - (2 if side_to_move == "w" else 1)
                        count_started = last_ply - counting_ply + 1
                        if count_started < 1:
                            # Move number is too small for the current count
                            count_started = 0
                            self.manual_count = False
                        else:
                            counting_player = (
                                self.bplayer if counting_ply % 2 == 0 else self.wplayer
                            )
                            self.draw_offers.add(counting_player.username)

        if TYPE_CHECKING:
            assert self.chess960 is not None
        board_initial_fen = self.initial_fen
        if catalogued_casual and not create and not board_initial_fen:
            # An absent historical snapshot cannot be recovered by drawing a
            # new random position. Keep the fixed engine default as the fallback.
            if catalogued_variant_random_start(self.variant) or self.chess960:
                log.warning("Community game %s has no saved initial FEN", self.id)
            board_initial_fen = FairyBoard.start_fen(self.variant)
        self.board = FairyBoard(
            self.variant,
            board_initial_fen,
            self.chess960,
            show_promoted=self.server_variant.show_promoted,
            legal_moves_need_history=self.server_variant.legal_moves_need_history,
        )

        # Janggi setup needed when player is not BOT
        if self.variant == "janggi":
            # Janggi custom start position -> no setup phase
            if self.initial_fen:
                self.bsetup = False
                self.wsetup = False
                self.status = STARTED
            else:
                # Red (the second player) have to choose the starting positions of the horses and elephants
                self.bsetup = not self.bplayer.bot
                # Blue (the first player) have to choose the starting positions of the horses and elephants
                self.wsetup = not self.wplayer.bot
                if self.bplayer.bot:
                    self.board.janggi_setup("b")

        self.overtime = False
        self.byoyomi = byoyomi_period > 0
        self.byoyomi_period = byoyomi_period

        # Remaining byoyomi periods by players
        self.byoyomi_periods = [byoyomi_period, byoyomi_period]

        # On page refresh we have to add extra byoyomi times gained by current player to report correct clock time
        # We adjust this in "byoyomi" messages in wsr.py
        self.byo_correction = 0
        # One immutable timing snapshot for every board position, including ply 0.
        # Live byoyomi messages may change the current fields, but not the snapshot
        # for the position at which the turn began. A takeback restores that snapshot.
        self.byoyomi_state_stack: list[tuple[tuple[int, int], bool, int]] = (
            [self.byoyomi_state()] if self.byoyomi else []
        )

        # Snapshot community starts too, so reloads and rematches use the
        # game's actual position even if the variant's default later changes.
        if self.chess960 or self.random_only or catalogued_casual:
            self.initial_fen = self.board.initial_fen

        self.random_mover = (
            "Random-Mover"
            in (
                self.wplayer.username,
                self.bplayer.username,
            )
            or self.wplayer.title == "TEST"
            or self.bplayer.title == "TEST"
        )

        self.has_legal_move = self.board.has_legal_move()
        if self.random_mover:
            self.legal_moves = self.board.legal_moves()

        if self.board.move_stack:
            self.check = self.board.is_checked()

        self.steps: list[GameStep] = [
            {
                "fen": self.initial_fen if self.initial_fen else self.board.initial_fen,
                "san": None,
                "turnColor": "black" if self.board.color == BLACK else "white",
                "check": self.check,
                "clocks": (self.clocks_w[0], self.clocks_b[0]),
            }
        ]

        self.last_move_time = None
        self.stopwatch: Clock | CorrClock
        if self.corr:
            self.stopwatch = CorrClock(self)
        else:
            self.stopwatch = Clock(self)
            if not self.create:
                # ``load_game_from_doc()`` restores the persisted move stack
                # after constructing Game. Do not let a temporary ply-0 clock
                # run while that reconstruction (and any DB reads) is in
                # progress; it is restarted from the real position at the end.
                self.stopwatch.stop()

        if self.create and (not self.corr) and (not self.bplayer.bot):
            self.bplayer.game_in_progress = self.id
        if self.create and (not self.corr) and (not self.wplayer.bot):
            self.wplayer.game_in_progress = self.id

        self.wberserk = False
        self.bberserk = False

        self.move_lock = asyncio.Lock()

    async def cancel_clocks_for_eviction(self) -> None:
        await self.stopwatch.cancel()

    @property
    def persist_clock_history(self) -> bool:
        """Whether in-progress clock arrays must be durable after every move.

        Casual games normally omit incremental clocks because they may be
        taken back. Tournament games never allow takebacks, so their clocks
        must be persisted even when the tournament itself is casual.
        """
        return (
            self.rated == RATED
            or self.tournamentId is not None
            or self.tournamentArrangementId is not None
        )

    def elapsed_on_current_turn_ms(self) -> int:
        """Wall-clock elapsed time on the current turn across restarts."""
        live_elapsed = round((monotonic() - self.last_server_clock) * 1000)
        return max(0, self.restart_elapsed_ms + live_elapsed)

    def authoritative_clock_elapsed_ms(self) -> int:
        """Elapsed time usable for server clock decisions.

        Restart downtime is authoritative only when the game's move clocks are
        durable. Non-tournament casual games deliberately omit clock history
        because takebacks are allowed, so they retain their pre-existing
        restart semantics rather than pretending their reconstructed base
        clocks are exact.
        """
        live_elapsed = round((monotonic() - self.last_server_clock) * 1000)
        restart_elapsed = self.restart_elapsed_ms if self.persist_clock_history else 0
        return max(0, restart_elapsed + live_elapsed)

    def restore_realtime_clock_after_load(self, loaded_at: datetime) -> None:
        """Restore a real-time stopwatch from persisted wall-clock state.

        ``monotonic()`` starts afresh in a new process, therefore the time
        between the persisted turn start and ``loaded_at`` has to be carried
        separately. Once a move is played that restart offset is reset to 0.
        """
        if self.corr or self.status > STARTED:
            return

        self.loaded_at = loaded_at

        turn_started_at = self.last_move_time if self.board.ply > 0 else self.date
        if turn_started_at is not None:
            if turn_started_at.tzinfo is None:
                turn_started_at = turn_started_at.replace(tzinfo=UTC)
            if loaded_at.tzinfo is None:
                loaded_at = loaded_at.replace(tzinfo=UTC)
            self.restart_elapsed_ms = max(
                0,
                round((loaded_at - turn_started_at).total_seconds() * 1000),
            )
        else:
            self.restart_elapsed_ms = 0

        # Start the new monotonic epoch only after the wall-clock restart gap
        # has been captured above.
        self.last_server_clock = monotonic()

        if TYPE_CHECKING:
            assert isinstance(self.stopwatch, Clock)

        if not self.persist_clock_history:
            # Casual non-tournament games can have takebacks and therefore do
            # not persist exact clocks. Preserve their old restart behaviour;
            # restart_elapsed_ms is still useful for the browser-side display
            # adjustment that existed before durable tournament clocks.
            self.stopwatch.restart()
            return

        if self.board.ply < 2 and not self.server_variant.two_boards:
            if self.tournamentId is None and not self.bot_game:
                # Preserve the existing unlimited first-move behaviour of
                # ordinary human games.
                self.stopwatch.restart()
                return
            remaining = self.stopwatch.time_for_first_move - self.restart_elapsed_ms
        else:
            saved = self.clocks_w[-1] if self.board.color == WHITE else self.clocks_b[-1]
            correction = self.byo_correction if self.byoyomi else 0
            remaining = saved + correction - self.restart_elapsed_ms

        # Do not clamp to zero. A negative value lets the clock task and a
        # reconnecting client's flag claim immediately observe that the turn
        # expired while the server was down.
        self.stopwatch.restart(remaining)

    def berserk(self, color: str) -> None:
        if color == "white" and not self.wberserk:
            self.wberserk = True
            self.clocks_w[0] = self.berserk_time
        elif color == "black" and not self.bberserk:
            self.bberserk = True
            self.clocks_b[0] = self.berserk_time

    async def save_berserk(self) -> None:
        if self.app_state.db is None or not self.persist_to_db:
            return

        new_data = {
            "wb": self.wberserk,
            "bb": self.bberserk,
            "cw": self.clocks_w[1:],
            "cb": self.clocks_b[1:],
        }

        # update_one is sufficient — the returned document is never used.
        await self.app_state.db.game.update_one({"_id": self.id}, {"$set": new_data})

    async def play_move(
        self, move: str, clocks: ClockValues | None = None, ply: int | None = None
    ) -> None:
        self.stopwatch.stop()

        self.byo_correction = 0
        if clocks is None:
            clocks = [self.clocks_w[-1], self.clocks_b[-1]]

        if self.status > STARTED:
            return

        if self.board.ply == 0 and not self.counted_as_active:
            self.status = STARTED
            self.counted_as_active = True
            self.app_state.g_cnt[0] += 1
            response = {"type": "g_cnt", "cnt": self.app_state.g_cnt[0]}
            await self.app_state.lobby.lobby_broadcast(response)

        cur_color = self.board.color
        cur_player = self.bplayer if cur_color == BLACK else self.wplayer
        opp_player = self.wplayer if cur_color == BLACK else self.bplayer
        previous_fen = self.board.fen
        previous_ply = self.board.ply

        # Move cancels draw offer
        response = await reject_draw(self, opp_player)
        if response is not None:
            await round_broadcast(self, response, full=True)

        # Playing on cancels an outstanding takeback proposal.
        if self.takeback_offer is not None:
            self.takeback_offer = None
            await round_broadcast(
                self,
                {"type": "takeback_rejected", "message": "Takeback offer canceled"},
                full=True,
            )

        cur_time = monotonic()

        # BOT players doesn't send times used for moves
        if self.bot_game:
            movetime = self.authoritative_clock_elapsed_ms() if self.board.ply >= 2 else 0
            if cur_player.bot and self.board.ply >= 2:
                if self.byoyomi:
                    if self.overtime:
                        clocks[cur_color] = self.inc * 1000  # pyrefly: ignore[unsupported-operation]
                    else:
                        clocks[cur_color] = max(0, self.clocks[cur_color] - movetime)  # pyrefly: ignore[unsupported-operation]
                else:
                    clocks[cur_color] = max(  # pyrefly: ignore[unsupported-operation]
                        0, self.clocks[cur_color] - movetime + (self.inc * 1000)
                    )

                if clocks[cur_color] == 0:
                    if self.byoyomi and self.byoyomi_periods[cur_color] > 0:
                        self.overtime = True
                        clocks[cur_color] = self.inc * 1000  # pyrefly: ignore[unsupported-operation]
                        self.byoyomi_periods[cur_color] -= 1
                    else:
                        w, b = self.board.insufficient_material()
                        if (w and b) or (cur_color == BLACK and w) or (cur_color == WHITE and b):
                            result = "1/2-1/2"
                        else:
                            result = "1-0" if cur_color == BLACK else "0-1"
                        self.update_status(FLAG, result)
                        log.info("result: %s %s", self.result, "flag")
                        await self.save_game()
        else:
            if (ply is not None) and ply <= 2 and self.tournamentId is not None:
                # Just in case for move and berserk messages race
                if self.wberserk:
                    clocks[WHITE] = self.berserk_time  # pyrefly: ignore[unsupported-operation]
                if self.bberserk:
                    clocks[BLACK] = self.berserk_time  # pyrefly: ignore[unsupported-operation]

        self.last_server_clock = cur_time
        self.restart_elapsed_ms = 0

        if self.status <= STARTED:
            try:
                if self.jieqi:
                    # Reset per-move capture hint so stale captures are never reused.
                    self.last_jieqi_capture = None
                san = self.board.get_san(move)

                if self.jieqi:
                    # Capture identity must be read before the board mutates, because
                    # the mapping of covered pieces is consumed by the move.
                    jieqi_capture = self.board.captured_jieqi_piece(move)
                    new_piece = self.board.revealed_piece(move)
                    if new_piece is not None:
                        move = move + new_piece.lower()
                        san = "%s=%s" % (san, new_piece.lower())
                else:
                    jieqi_capture = None

                self.lastmove = move
                if cur_color == WHITE:
                    self.clocks_w.append(clocks[WHITE])
                else:
                    self.clocks_b.append(clocks[BLACK])

                self.board.push(move)

                self.has_legal_move = self.board.has_legal_move()
                if self.random_mover:
                    self.legal_moves = self.board.legal_moves()

                self.update_status()

                self.steps.append(
                    {
                        "fen": self.board.fen,
                        "move": move,
                        "san": san,
                        "turnColor": "black" if self.board.color == BLACK else "white",
                        "check": self.check,
                        "clocks": clocks,
                    }
                )
                if self.byoyomi:
                    self.byoyomi_state_stack.append(self.byoyomi_state())
                if self.jieqi_capture_stack is not None:
                    # Keep a parallel capture stack so takebacks can undo captures cleanly.
                    if jieqi_capture is not None and self.jieqi_captures is not None:
                        # Track hidden captures for the capturer only; the client will
                        # render these without leaking them to the opponent.
                        capture = jieqi_capture.lower()
                        self.last_jieqi_capture = capture
                        self.jieqi_captures[cur_color].append(capture)
                        self.jieqi_capture_stack.append((cur_color, capture))
                    else:
                        self.jieqi_capture_stack.append(None)

                if self.status > STARTED:
                    await self.save_game()
                    if self.corr:
                        await opp_player.notify_game_end(self)
                else:
                    await self.save_move(
                        move,
                        cur_color,
                        previous_fen=previous_fen,
                        previous_ply=previous_ply,
                    )
                    if self.corr and (not opp_player.bot) and (not opp_player.anon):
                        corr_notification_san = None if self.fow else san
                        await opp_player.notify_corr_move(self, corr_notification_san)
                        self.app_state.push_notifier.enqueue_corr_move(
                            opp_player,
                            game_id=self.id,
                            opponent=cur_player.username,
                            san=corr_notification_san,
                        )
                    self.stopwatch.restart()

                if self.simulId is not None:
                    simul = self.app_state.simuls.get(self.simulId)
                    if simul is not None:
                        await simul.game_update(self)

            except StaleMovePersistenceError:
                log.warning(
                    "Discarding stale move state in game %s after persistence compare-and-set failed",
                    self.id,
                )
                self.stopwatch.restart()
                raise
            except Exception:
                log.exception("ERROR: Exception in game %s play_move() %s", self.id, move)
                result = "1-0" if self.board.color == BLACK else "0-1"
                self.update_status(INVALIDMOVE, result)
                await self.save_game()
                if self.corr:
                    await opp_player.notify_game_end(self)

    async def save_move(
        self,
        move: str,
        cur_color: int,
        *,
        previous_fen: str,
        previous_ply: int,
    ) -> None:
        """Persist a single in-progress move to the database.

        ``cur_color`` is the moving side captured before ``board.push()``
        in ``play_move()``; after the push ``board.color`` has already
        flipped to the opponent, so we can't derive it from board state.

        Clock persistence uses ``$push`` (single new value per ply) instead
        of ``$set`` (full ever-growing array) to keep the wire payload O(1)
        regardless of game length. ``save_game()`` writes the authoritative
        full arrays at game end, so the document is always consistent on close.

        Takebacks are available only in non-tournament CASUAL games. Those
        games still omit clock arrays, while tournament games cannot take back
        moves and can safely persist clocks without a matching clock ``$pop``.
        """
        self.last_move_time = datetime.now(UTC)
        move_encoded = self.encode_method(grand2zero(move) if self.variant in GRANDS else move)

        set_data: dict[str, object] = {
            "f": self.board.fen,
            "l": self.last_move_time,
            "s": self.status,
        }
        # Push only the clock that changed this ply; the other array is
        # left untouched until save_game() overwrites both at game end.
        push_data: dict[str, object] = {"m": move_encoded}
        if self.byoyomi:
            periods, overtime, correction = self.byoyomi_state_stack[-1]
            push_data["byost"] = {
                "p": list(periods),
                "o": overtime,
                "c": correction,
            }
            set_data.update(self.byoyomi_state_document())
        if self.persist_clock_history:
            if cur_color == WHITE:
                push_data["cw"] = self.clocks_w[-1]
            else:
                push_data["cb"] = self.clocks_b[-1]

        if self.app_state.db is not None:
            move_index = str(previous_ply)
            persist_filter: dict[str, object] = {
                "_id": self.id,
                "f": previous_fen,
                "s": {"$lte": STARTED},
                f"m.{move_index}": {"$exists": False},
            }
            if previous_ply > 0:
                persist_filter[f"m.{previous_ply - 1}"] = {"$exists": True}

            result = await self.app_state.db.game.update_one(
                persist_filter,
                {"$set": set_data, "$push": push_data},
            )
            if result.modified_count == 1:
                return

            persisted = await self.app_state.db.game.find_one(
                {"_id": self.id},
                projection={"m": 1, "f": 1},
            )
            if persisted is None:
                # In-memory-only games are used by tests and private variants.
                # There is no competing persisted state to protect in this case.
                log.debug("Skipping move persistence for non-persisted game %s", self.id)
                return

            current_encoded_moves = [
                *map(
                    self.encode_method,
                    (
                        map(grand2zero, self.board.move_stack)
                        if self.variant in GRANDS
                        else self.board.move_stack
                    ),
                )
            ]
            if persisted.get("m") == current_encoded_moves and persisted.get("f") == self.board.fen:
                log.info(
                    "Move %s in %s was already persisted by another Game instance",
                    move,
                    self.id,
                )
                return

            raise StaleMovePersistenceError(
                f"Game {self.id} changed in MongoDB before move {move} could be persisted"
            )

    async def pop_move_from_db(self) -> None:
        if self.app_state.db is not None:
            self.last_move_time = datetime.now(UTC)
            new_data = {"f": self.board.fen, "l": self.last_move_time}
            pop_data = {"m": 1}
            if self.byoyomi:
                pop_data["byost"] = 1
            await self.app_state.db.game.update_one(
                {"_id": self.id}, {"$set": new_data, "$pop": pop_data}
            )

    def byoyomi_state(self) -> tuple[tuple[int, int], bool, int]:
        return (
            (self.byoyomi_periods[WHITE], self.byoyomi_periods[BLACK]),
            self.overtime,
            self.byo_correction,
        )

    def restore_byoyomi_state(self, state: tuple[tuple[int, int], bool, int]) -> None:
        periods, self.overtime, self.byo_correction = state
        self.byoyomi_periods = list(periods)

    def byoyomi_state_document(self) -> dict[str, object]:
        return {
            "byop": list(self.byoyomi_periods),
            "byoo": self.overtime,
            "byoc": self.byo_correction,
        }

    async def save_byoyomi_state(self) -> None:
        if self.byoyomi and self.app_state.db is not None:
            await self.app_state.db.game.update_one(
                {"_id": self.id}, {"$set": self.byoyomi_state_document()}
            )

    async def save_manual_count_state(self) -> None:
        if not self.manual_count or not self.persist_to_db or self.app_state.db is None:
            return
        await self.app_state.db.game.update_one(
            {"_id": self.id},
            {
                "$set": {
                    "mc": self.board.count_started,
                    "mct": self.manual_count_toggled,
                }
            },
        )

    async def save_takeback_state(self) -> None:
        if self.app_state.db is None:
            return
        state: dict[str, object] = {
            "f": self.board.fen,
            "s": self.status,
            "l": self.last_move_time,
        }
        if self.byoyomi:
            state.update(self.byoyomi_state_document())
        await self.app_state.db.game.update_one({"_id": self.id}, {"$set": state})

    async def save_setup(self) -> None:
        """Used by Janggi prelude phase"""
        new_data = {
            "f": self.board.fen,
            "l": datetime.now(UTC),
            "s": self.status,
            "if": self.board.fen,
            "ws": self.wsetup,
            "bs": self.bsetup,
        }
        if self.app_state.db is not None:
            # update_one is sufficient — the returned document is never used.
            await self.app_state.db.game.update_one({"_id": self.id}, {"$set": new_data})

    async def save_game(self) -> None:
        if self.saved:
            return
        self.saved = True

        if self.tournamentId is None and self.tournamentArrangementId:
            self.tournamentId = self.tournamentArrangementId.split(":", 1)[0]

        if self.rated == IMPORTED:
            log.exception("Save IMPORTED game %s ???", self.id)
            return

        self.stopwatch.stop()
        await self.stopwatch.cancel()

        if self.counted_as_active:
            self.counted_as_active = False
            self.app_state.g_cnt[0] -= 1
            response = {"type": "g_cnt", "cnt": self.app_state.g_cnt[0]}
            await self.app_state.lobby.lobby_broadcast(response)

        self.app_state.schedule_game_cache_removal(self)

        if (
            self.board.ply < 3
            and self.persist_to_db
            and (self.app_state.db is not None)
            and (self.tournamentId is None)
            and (self.tournamentArrangementId is None)
            and (self.simulId is None)
        ):
            result = await self.app_state.db.game.delete_one({"_id": self.id})
            log.debug(
                "Removed too short game %s from db. Deleted %s game.",
                self.id,
                result.deleted_count,
            )
        else:
            rating_update: tuple[Rating, Rating] | None = None
            if self.result != "*" and self.rated == RATED:
                # Calculate rating deltas before the authoritative game write so
                # p0/p1 are part of the durable finished-game record. Applying
                # the user-rating side effects happens only after that write.
                rating_update = self.prepare_rating_update()

            tournament_effects_pending = (
                self.tournamentId is not None
                and self.persist_to_db
                and self.app_state.db is not None
                and self.result in ("1-0", "0-1", "1/2-1/2")
            )

            new_data = {
                "f": self.board.fen,
                "p": self.board.ply,
                "s": self.status,
                "r": R2C[self.result],
                "m": [
                    *map(
                        self.encode_method,
                        (
                            map(grand2zero, self.board.move_stack)
                            if self.variant in GRANDS
                            else self.board.move_stack
                        ),
                    )
                ],
            }

            if rating_update is not None:
                if tournament_effects_pending:
                    applied_at = datetime.now(UTC)
                    new_data["p0"] = {
                        **self.p0,
                        "n": self.tournament_rating_effect_entry(
                            self.wplayer, rating_update[0], applied_at
                        ),
                    }
                    new_data["p1"] = {
                        **self.p1,
                        "n": self.tournament_rating_effect_entry(
                            self.bplayer, rating_update[1], applied_at
                        ),
                    }
                else:
                    new_data["p0"] = self.p0
                    new_data["p1"] = self.p1

            if tournament_effects_pending:
                # fx=1 means the authoritative result is durable but one or more
                # global result side effects may still need restart recovery.
                new_data["fx"] = 1

            # Janggi game starts with a prelude phase to set up horses and elephants, so
            # initial FEN may be different compared to one we used when db game document was created
            if self.variant == "janggi":
                new_data["if"] = self.board.initial_fen

            if self.persist_clock_history:
                new_data["cw"] = self.clocks_w[1:]
                new_data["cb"] = self.clocks_b[1:]

            if self.tournamentId is not None:
                new_data["wb"] = self.wberserk
                new_data["bb"] = self.bberserk
                round_no = getattr(self, "round", None)
                if round_no is not None:
                    new_data["rn"] = round_no

            if self.manual_count:
                manual_count_toggled = list(self.manual_count_toggled)
                if self.board.count_started > 0:
                    manual_count_toggled.append((self.board.count_started, self.board.ply + 1))
                new_data["mct"] = manual_count_toggled
                # A finished game has no outstanding manual count, even if the
                # count was active immediately before the result was recorded.
                new_data["mc"] = -1

            if self.persist_to_db and self.app_state.db is not None:
                # Persist the authoritative final game state before any external
                # result side effects. If the process dies after this write,
                # tournament startup recovery can still reconstruct the result.
                await self.app_state.db.game.update_one({"_id": self.id}, {"$set": new_data})

            if tournament_effects_pending:
                await self.complete_tournament_final_side_effects(new_data)
            else:
                if self.result != "*":
                    if rating_update is not None:
                        await self.apply_rating_update(*rating_update)
                    if self.persist_to_db:
                        await self.update_players_game_counts()
                        if (
                            (not self.bot_game)
                            and (not self.wplayer.anon)
                            and (not self.bplayer.anon)
                        ):
                            await self.save_crosstable()

                if (
                    self.persist_to_db
                    and self.app_state.db is not None
                    and is_catalogued_variant(self.variant)
                    and self.result in ("1-0", "0-1", "1/2-1/2")
                ):
                    await increment_catalogued_variant_game_count(self.app_state, self.variant)

            if self.tournamentId is not None:
                try:
                    # In case of server restart we have to wait for loading ongoing tournaments
                    await self.app_state.tournaments_loaded.wait()
                    await self.app_state.tournaments[self.tournamentId].game_update(self)
                except Exception:
                    log.exception("Exception in tournament game_update()")

    async def update_players_game_counts(self) -> None:
        if self.result not in ("1-0", "0-1", "1/2-1/2"):
            return

        rated = self.rated == RATED
        if self.result == "1-0":
            white_result = 1
            black_result = -1
        elif self.result == "0-1":
            white_result = -1
            black_result = 1
        else:
            white_result = 0
            black_result = 0

        if not self.wplayer.anon:
            await self.wplayer.increment_game_count(white_result, rated)
        if not self.bplayer.anon:
            await self.bplayer.increment_game_count(black_result, rated)

    def set_crosstable(self) -> None:
        if (
            (not self.has_crosstable)
            or (self.board.ply < 3 and self.tournamentId is None)
            or self.result == "*"
        ):
            return
        crosstable: Crosstable = self.crosstable  # type: ignore[assignment]

        if any(result.startswith(self.id) for result in crosstable["r"]):
            log.info("Crosstable was already updated with %s result", self.id)
            return

        if self.result == "1/2-1/2":
            s1 = s2 = 5
            tail = "="
        elif (self.result == "1-0" and self.s1player == self.wplayer.username) or (
            self.result == "0-1" and self.s1player == self.bplayer.username
        ):
            s1 = 10
            s2 = 0
            tail = "+"
        else:
            s1 = 0
            s2 = 10
            tail = "-"

        crosstable["s1"] += s1
        crosstable["s2"] += s2
        crosstable["r"].append("%s%s" % (self.id, tail))
        crosstable["r"] = crosstable["r"][-20:]

        self.need_crosstable_save = True

    async def save_crosstable(self) -> None:
        if not self.need_crosstable_save:
            log.info("Crosstable update for %s was already saved to mongodb", self.id)
            return
        crosstable: Crosstable = self.crosstable  # type: ignore[assignment]

        new_data = {
            "s1": crosstable["s1"],
            "s2": crosstable["s2"],
            "r": crosstable["r"],
        }
        try:
            # update_one(upsert=True) is sufficient — the returned document
            # is never used and find_one_and_update costs an extra round-trip.
            await self.app_state.db.crosstable.update_one(
                {"_id": self.ct_id}, {"$set": new_data}, upsert=True
            )
        except Exception:
            log.error("Failed to save new crosstable to mongodb!")

        self.need_crosstable_save = False

    def get_highscore(self, variant: str, chess960: bool) -> tuple[int, int]:
        len_hs = len(self.app_state.highscore[variant + ("960" if chess960 else "")])
        if len_hs > 0:
            return (
                self.app_state.highscore[variant + ("960" if chess960 else "")].peekitem()[1],
                len_hs,
            )
        return (0, 0)

    async def set_highscore(
        self,
        variant: str,
        chess960: bool,
        value: dict[str, int],
        *,
        raise_on_error: bool = False,
    ) -> bool:
        variant_key = variant + ("960" if chess960 else "")
        variant_scores = self.app_state.highscore[variant_key]
        prev_top = (
            (variant_scores.peekitem(0)[0], int(variant_scores.peekitem(0)[1]))
            if len(variant_scores) > 0
            else None
        )
        variant_scores.update(value)
        new_top = (
            (variant_scores.peekitem(0)[0], int(variant_scores.peekitem(0)[1]))
            if len(variant_scores) > 0
            else None
        )

        new_data = {"scores": dict(variant_scores.items()[:MAX_HIGHSCORE_ITEM_LIMIT])}
        try:
            # update_one(upsert=True) is sufficient — the returned document
            # is never used and find_one_and_update costs an extra round-trip.
            await self.app_state.db.highscore.update_one(
                {"_id": variant_key},
                {"$set": new_data},
                upsert=True,
            )
        except Exception:
            log.error("Failed to save new %s highscore to mongodb!", variant)
            if raise_on_error:
                raise
        return prev_top != new_top

    def prepare_rating_update(self) -> tuple[Rating, Rating]:
        if self.result == "1-0":
            (white_score, black_score) = (1.0, 0.0)
        elif self.result == "1/2-1/2":
            (white_score, black_score) = (0.5, 0.5)
        elif self.result == "0-1":
            (white_score, black_score) = (0.0, 1.0)
        else:
            raise RuntimeError("game.result: unexpected result code")

        wr_old = int(self.wrating.rstrip("?"))
        br_old = int(self.brating.rstrip("?"))

        wcurr = self.wplayer.get_rating(self.variant, self.chess960)
        bcurr = self.bplayer.get_rating(self.variant, self.chess960)

        white_rating = gl2.create_rating(wr_old, wcurr.phi, wcurr.sigma, wcurr.ltime)
        black_rating = gl2.create_rating(br_old, bcurr.phi, bcurr.sigma, bcurr.ltime)

        wr = gl2.rate(white_rating, [(white_score, black_rating)])
        br = gl2.rate(black_rating, [(black_score, white_rating)])

        wrdiff = wr.mu - white_rating.mu
        self.wrdiff = int(round(wrdiff, 0))
        self.p0 = {"e": self.wrating, "d": self.wrdiff}

        brdiff = br.mu - black_rating.mu
        self.brdiff = int(round(brdiff, 0))
        self.p1 = {"e": self.brating, "d": self.brdiff}

        return (
            gl2.create_rating(wcurr.mu + wrdiff, wr.phi, wr.sigma, wr.ltime),
            gl2.create_rating(bcurr.mu + brdiff, br.phi, br.sigma, br.ltime),
        )

    def tournament_rating_effect_entry(
        self, player: User, rating: Rating, applied_at: datetime
    ) -> PerfEntry:
        chess960 = self.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        variant_key = self.variant + ("960" if chess960 else "")
        previous = player.perfs.get(variant_key)
        return {
            "gl": {"r": rating.mu, "d": rating.phi, "v": rating.sigma},
            "la": applied_at,
            "nb": (0 if previous is None else previous["nb"]) + 1,
        }

    @staticmethod
    def result_for_player(result: str, *, white: bool) -> int:
        if result == "1-0":
            return 1 if white else -1
        if result == "0-1":
            return -1 if white else 1
        return 0

    async def apply_tournament_user_side_effects_once(self, game_doc: Mapping[str, object]) -> None:
        """Apply tournament rating/count changes atomically per player.

        A finished tournament game is persisted with ``fx=1`` before this runs.
        Each user update carries a bounded game-id marker in the same MongoDB
        operation as the rating/count changes, making retries after restart safe.
        """
        if self.result not in ("1-0", "0-1", "1/2-1/2"):
            return

        rated = self.rated == RATED
        chess960 = bool(self.chess960)
        variant_key = self.variant + ("960" if chess960 else "")
        p0 = game_doc.get("p0")
        p1 = game_doc.get("p1")
        white_perf = p0.get("n") if rated and isinstance(p0, Mapping) else None
        black_perf = p1.get("n") if rated and isinstance(p1, Mapping) else None

        white_perf_entry = cast(PerfEntry, white_perf) if isinstance(white_perf, dict) else None
        black_perf_entry = cast(PerfEntry, black_perf) if isinstance(black_perf, dict) else None
        await self.wplayer.apply_tournament_game_effect_once(
            self.id,
            self.result_for_player(self.result, white=True),
            rated,
            variant_key=variant_key,
            perf_entry=white_perf_entry,
        )
        await self.bplayer.apply_tournament_game_effect_once(
            self.id,
            self.result_for_player(self.result, white=False),
            rated,
            variant_key=variant_key,
            perf_entry=black_perf_entry,
        )

    async def update_tournament_highscore_side_effect(self) -> None:
        if self.rated != RATED:
            return

        chess960 = self.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        variant_key = self.variant + ("960" if chess960 else "")
        should_rebuild_lobby_leaderboard = False
        for player in (self.wplayer, self.bplayer):
            perf = player.perfs.get(variant_key)
            if perf is None or perf["nb"] < HIGHSCORE_MIN_GAMES:
                continue
            _id = "%s|%s" % (player.username, player.title)
            changed_top = await self.set_highscore(
                self.variant,
                chess960,
                {_id: int(round(perf["gl"]["r"], 0))},
                raise_on_error=True,
            )
            should_rebuild_lobby_leaderboard = should_rebuild_lobby_leaderboard or changed_top

        if should_rebuild_lobby_leaderboard:
            await refresh_lobby_leaderboard_cache(self.app_state)

    async def ensure_tournament_crosstable_side_effect(self) -> None:
        if (not self.has_crosstable) or self.app_state.db is None:
            return
        current = await self.app_state.db.crosstable.find_one({"_id": self.ct_id})
        if current is None:
            self.crosstable = {
                "_id": self.ct_id,
                "s1": 0,
                "s2": 0,
                "r": [],
            }
        else:
            self.crosstable = current
        self.need_crosstable_save = False
        self.set_crosstable()
        if not self.need_crosstable_save:
            return
        crosstable: Crosstable = self.crosstable  # type: ignore[assignment]
        await self.app_state.db.crosstable.update_one(
            {"_id": self.ct_id},
            {
                "$set": {
                    "s1": crosstable["s1"],
                    "s2": crosstable["s2"],
                    "r": crosstable["r"],
                }
            },
            upsert=True,
        )
        self.need_crosstable_save = False

    async def complete_tournament_final_side_effects(
        self, game_doc: Mapping[str, object], *, users_only: bool = False
    ) -> None:
        """Complete retry-safe global side effects for a finished tournament game."""
        await self.apply_tournament_user_side_effects_once(game_doc)
        if users_only:
            return

        await self.update_tournament_highscore_side_effect()
        await self.ensure_tournament_crosstable_side_effect()
        if is_catalogued_variant(self.variant):
            await increment_catalogued_variant_game_count_once(
                self.app_state, self.variant, self.id
            )

        if self.app_state.db is not None:
            await self.app_state.db.game.update_one({"_id": self.id, "fx": 1}, {"$set": {"fx": 2}})

    async def apply_rating_update(self, new_white_rating: Rating, new_black_rating: Rating) -> None:
        chess960 = self.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        await self.wplayer.set_rating(self.variant, chess960, new_white_rating)
        await self.bplayer.set_rating(self.variant, chess960, new_black_rating)

        should_rebuild_lobby_leaderboard = False
        w_nb = self.wplayer.perfs[self.variant + ("960" if chess960 else "")]["nb"]
        if w_nb >= HIGHSCORE_MIN_GAMES:
            _id = "%s|%s" % (self.wplayer.username, self.wplayer.title)
            changed_top = await self.set_highscore(
                self.variant,
                chess960,
                {_id: int(round(new_white_rating.mu, 0))},
            )
            should_rebuild_lobby_leaderboard = should_rebuild_lobby_leaderboard or changed_top

        b_nb = self.bplayer.perfs[self.variant + ("960" if chess960 else "")]["nb"]
        if b_nb >= HIGHSCORE_MIN_GAMES:
            _id = "%s|%s" % (self.bplayer.username, self.bplayer.title)
            changed_top = await self.set_highscore(
                self.variant,
                chess960,
                {_id: int(round(new_black_rating.mu, 0))},
            )
            should_rebuild_lobby_leaderboard = should_rebuild_lobby_leaderboard or changed_top

        if should_rebuild_lobby_leaderboard:
            await refresh_lobby_leaderboard_cache(self.app_state)

    async def update_ratings(self) -> None:
        await self.apply_rating_update(*self.prepare_rating_update())

    def get_player_at(self, color: int, board: FairyBoard) -> User:
        return self.bplayer if color == BLACK else self.wplayer

    def is_player(self, user: User) -> bool:
        return user.username in (self.wplayer.username, self.bplayer.username)

    @property
    def fen(self) -> str:
        return self.board.fen

    @property
    def preview_fen(self) -> str:
        return self.board.fen

    @property
    def posnum(self) -> int:
        return self.board.posnum

    @property
    def ply(self) -> int:
        return self.board.ply

    def update_status(self, status: int | None = None, result: str | None = None) -> None:
        if self.status > STARTED:
            return

        def result_string_from_value(color: int, game_result_value: int) -> str:
            if game_result_value < 0:
                return "1-0" if color == BLACK else "0-1"
            if game_result_value > 0:
                return "0-1" if color == BLACK else "1-0"
            return "1/2-1/2"

        if status is not None:
            self.status = status
            if result is not None:
                self.result = result

            self.set_crosstable()
            self.update_in_plays()

            return

        if self.board.move_stack:
            self.check = self.board.is_checked()

        w, b = self.board.insufficient_material()
        if w and b:
            self.status = DRAW
            self.result = "1/2-1/2"

        if not self.has_legal_move:
            game_result_value = self.board.game_result()
            self.result = result_string_from_value(self.board.color, game_result_value)

            if self.board.is_immediate_game_end()[0]:
                self.status = VARIANTEND
            elif self.check:
                self.status = MATE

                if self.variant == "atomic" and game_result_value == 0:
                    # If Fairy game_result() is 0 it is not mate but stalemate
                    self.status = STALEMATE

                # Draw if the checkmating player is the one counting
                if self.board.count_started > 0:
                    counting_side = "b" if self.board.count_started % 2 == 0 else "w"
                    if self.result == ("1-0" if counting_side == "w" else "0-1"):
                        self.status = DRAW
                        self.result = "1/2-1/2"

                # Pawn drop mate
                # TODO: remove this when https://github.com/ianfab/Fairy-Stockfish/issues/48 resolves
                if (self.board.move_stack[-1][0:2], self.variant) in INVALID_PAWN_DROP_MATE:
                    self.status = INVALIDMOVE
            else:
                self.status = STALEMATE

        else:
            # end the game by 50 move rule and repetition automatically
            is_game_end, game_result_value = self.board.is_optional_game_end()
            if is_game_end and (
                game_result_value != 0
                or (game_result_value == 0 and self.n_fold_is_draw)
                or (self.wplayer.bot or self.bplayer.bot)
                or self.variant == "ataxx"
            ):
                self.result = result_string_from_value(self.board.color, game_result_value)

                self.status = CLAIM if game_result_value != 0 else DRAW

        if self.has_counting:
            parts = self.board.fen.split()
            if parts[3].isdigit():
                counting_limit = int(parts[3])
                counting_ply = int(parts[4])
                if counting_ply > counting_limit:
                    self.status = DRAW
                    self.result = "1/2-1/2"

        if self.board.ply > MAX_PLY:
            self.status = DRAW
            self.result = "1/2-1/2"

        # Shatranj K vs K
        # TODO: remove when https://github.com/fairy-stockfish/Fairy-Stockfish/issues/833 resolves
        if (
            self.variant == "shatranj"
            and len([p for p in self.board.fen.split()[0] if p.isalpha()]) == 2
        ):
            self.status = DRAW
            self.result = "1/2-1/2"

        if self.status > STARTED:
            self.set_crosstable()
            self.update_in_plays()

    def update_in_plays(self) -> None:
        if not self.bplayer.bot:
            self.bplayer.game_in_progress = None
        if not self.wplayer.bot:
            self.wplayer.game_in_progress = None

        if self.corr:
            try:
                self.wplayer.correspondence_games.remove(self)
                self.bplayer.correspondence_games.remove(self)
            except ValueError:
                pass

    def print_game(self) -> None:
        print(self.pgn)
        print(self.board.print_pos())

    @property
    def pgn(self) -> str:
        move_stack = list(self.board.move_stack)
        mlist = move_stack
        if not self.jieqi:
            initial_fen = self.initial_fen if self.initial_fen else self.board.initial_fen
            # Keep legacy behavior first, then retry with modded castling semantics.
            san_variants = [self.variant]
            san_variant = modded_variant(self.variant, bool(self.chess960), initial_fen)
            if san_variant != self.variant:
                san_variants.append(san_variant)

            san_ok = False
            for variant_name in san_variants:
                try:
                    mlist = get_san_moves(
                        variant_name,
                        initial_fen,
                        move_stack,
                        self.chess960,
                        NOTATION_SAN,
                    )
                    san_ok = True
                    break
                except Exception:
                    pass

            # Some historical records can contain a trailing move that no longer
            # validates with current engine rules. Keep PGN generation resilient.
            if (not san_ok) and len(move_stack) > 1:
                for variant_name in san_variants:
                    try:
                        mlist = get_san_moves(
                            variant_name,
                            initial_fen,
                            move_stack[:-1],
                            self.chess960,
                            NOTATION_SAN,
                        )
                        san_ok = True
                        break
                    except Exception:
                        pass

        moves = " ".join(
            (
                move if ind % 2 == 1 else "%s. %s" % (((ind + 1) // 2) + 1, move)
                for ind, move in enumerate(mlist)
            )
        )
        # Archived browser views no longer materialize steps. Stored analysis is
        # sufficient to retain annotations in the existing server PGN response.
        analysis = (
            self.analysis
            if len(self.steps) == 1 and self.analysis is not None and not self.usi_format
            else [step.get("analysis") for step in self.steps]
        )
        if not self.server_variant.two_boards and any(
            row and row.get("advice") for row in analysis
        ):
            from game_analysis import annotated_game_moves

            moves = annotated_game_moves(mlist, self.board.initial_fen, analysis)
        no_setup = self.board.initial_fen == FairyBoard.start_fen("chess") and not self.chess960
        # Use lichess format for crazyhouse games to support easy import
        setup_fen = (
            self.board.initial_fen
            if self.variant != "crazyhouse"
            else self.board.initial_fen.replace("[]", "")
        )
        tc = "-" if self.base + self.inc == 0 else "%s+%s" % (int(self.base * 60), self.inc)
        return '[Event "{}"]\n[Site "{}"]\n[Date "{}"]\n[Round "-"]\n[White "{}"]\n[Black "{}"]\n[Result "{}"]\n[TimeControl "{}"]\n[WhiteElo "{}"]\n[BlackElo "{}"]\n[Variant "{}"]\n{fen}{setup}\n{} {}\n'.format(
            "PyChess "
            + ("rated" if self.rated == RATED else "casual" if self.rated == CASUAL else "imported")
            + " game",
            URI + "/" + self.id,
            self.date.strftime("%Y.%m.%d"),
            self.wplayer.username,
            self.bplayer.username,
            self.result,
            tc,
            self.wrating,
            self.brating,
            self.variant.capitalize()
            if not self.chess960 or is_catalogued_variant(self.variant)
            else VARIANT_960_TO_PGN[self.variant],
            moves,
            self.result,
            fen="" if no_setup else '[FEN "%s"]\n' % setup_fen,
            setup="" if no_setup else '[SetUp "1"]\n',
        )

    @property
    def uci_usi(self) -> str:
        if self.variant[-5:] == "shogi":
            mirror = mirror9 if self.variant in ("shogi", "shoshogi") else mirror5
            return "position sfen %s moves %s" % (
                self.board.initial_sfen,
                " ".join(map(uci2usi, map(mirror, self.board.move_stack))),
            )
        return "position fen %s moves %s" % (
            self.board.initial_fen,
            " ".join(self.board.move_stack),
        )

    @property
    def clocks(self) -> tuple[int | float, int | float]:
        return (self.clocks_w[-1], self.clocks_b[-1])

    @property
    def is_claimable_draw(self) -> bool:
        return self.board.is_claimable_draw()

    @property
    def spectator_list(self) -> SpectatorsMessage:
        return spectators(self.spectators)

    def analysis_start(self, username: str) -> str:
        return (
            '{"type": "analysisStart", "username": "%s", "game": {"id": "%s", "skill_level": "%s", "chess960": "%s"}}\n'
            % (username, self.id, self.level, self.chess960)
        )

    @property
    def game_start(self) -> str:
        """BOT API stream event response"""
        return (
            '{"type": "gameStart", "game": {"id": "%s", "skill_level": "%s", "chess960": "%s"}}\n'
            % (
                self.id,
                self.level,
                self.chess960,
            )
        )

    @property
    def game_end(self) -> str:
        return '{"type": "gameEnd", "game": {"id": "%s"}}\n' % self.id

    @property
    def game_full(self) -> str:
        """BOT API Stream Bot game data and state"""
        return (
            '{"type": "gameFull", "id": "%s", "variant": {"name": "%s"}, "white": {"name": "%s"}, "black": {"name": "%s"}, "initialFen": "%s", "createdAt": %s, "state": %s}\n'
            % (
                self.id,
                self.variant,
                self.wplayer.username,
                self.bplayer.username,
                self.initial_fen,
                int(self.date.timestamp()),
                self.game_state[:-1],
            )
        )

    @property
    def game_state(self) -> str:
        """BOT API Stream Bot game state"""
        clocks = self.clocks
        return (
            '{"type": "gameState", "moves": "%s", "wtime": %s, "btime": %s, "winc": %s, "binc": %s, "wdraw": %s, "bdraw": %s, "wtakeback": %s, "btakeback": %s, "status": "%s"}\n'
            % (
                " ".join(self.board.move_stack),
                clocks[WHITE],
                clocks[BLACK],
                self.inc,
                self.inc,
                str(False).lower(),
                str(False).lower(),
                str(False).lower(),
                str(False).lower(),
                "started",
            )
        )

    async def abort_by_server(self) -> GameEndResponse:
        self.update_status(ABORTED)
        await self.save_game()
        response: GameEndResponse = {
            "type": "gameEnd",
            "status": self.status,
            "result": "Game aborted.",
            "gameId": self.id,
            "pgn": self.pgn,
        }
        return response

    def ceval_detection_allowed(self) -> bool:
        return (
            self.status <= STARTED
            and not self.corr
            and not self.bot_game
            and not self.server_variant.two_boards
            and not self.server_variant.hidden_info
        )

    def ceval_detection_matches(self, *, variant: str, chess960: bool, fen: str) -> bool:
        return self.board.fen.split(" ", 1)[0] == fen.split(" ", 1)[0]

    async def cheat_by_ceval(self, user: User) -> GameEndResponse:
        if self.result == "*":
            result = "0-1" if user.username == self.wplayer.username else "1-0"
            self.update_status(CHEAT, result)
            log.warning("%s cheat_by_ceval(%s) %s", self.id, user.username, result)
            await self.save_game()
            if self.simulId is not None:
                simul = self.app_state.simuls.get(self.simulId)
                if simul is not None:
                    await simul.game_update(self)

        response: GameEndResponse = {
            "type": "gameEnd",
            "status": self.status,
            "result": self.result,
            "gameId": self.id,
            "pgn": self.pgn,
            "ct": self.crosstable,
            "rdiffs": (
                {"brdiff": self.brdiff, "wrdiff": self.wrdiff}
                if self.status > STARTED and self.rated == RATED
                else ""
            ),
        }
        if self.jieqi and self.jieqi_captures is not None:
            response["jieqiCaptures"] = list(self.jieqi_captures[WHITE]) + list(
                self.jieqi_captures[BLACK]
            )
            if self.jieqi_capture_stack is not None:
                response["jieqiCaptureStack"] = [
                    capture[1] if capture else None for capture in self.jieqi_capture_stack
                ]
        return response

    async def game_ended(self, user: User, reason: str) -> GameEndResponse:
        """Abort, resign, flag, abandon"""
        if self.result == "*":
            if reason == "abort":
                result = "*"
            elif self.variant == "janggi" and reason == "flag" and (self.bsetup or self.wsetup):
                if self.bsetup:
                    # In Janggi game the second player (red, who have to do the setup first!) failed to do the setup phase in time
                    result = "1-0"
                elif self.wsetup:
                    # the first player (blue) failed to do the setup phase in time
                    result = "0-1"
            else:
                if reason == "flag":
                    w, b = self.board.insufficient_material()
                    if (
                        (w and b)
                        or (self.board.color == BLACK and w)
                        or (self.board.color == WHITE and b)
                    ):
                        result = "1/2-1/2"
                    else:
                        result = "0-1" if user.username == self.wplayer.username else "1-0"
                else:
                    result = "0-1" if user.username == self.wplayer.username else "1-0"

            self.update_status(LOSERS[reason], result)
            log.debug("%s game_ended(%s, %s) %s", self.id, user.username, reason, result)
            await self.save_game()
            if self.simulId is not None:
                simul = self.app_state.simuls.get(self.simulId)
                if simul is not None:
                    await simul.game_update(self)

            if self.corr:
                cur_player = (
                    self.wplayer if user.username == self.wplayer.username else self.bplayer
                )
                opp_player = (
                    self.wplayer if user.username == self.bplayer.username else self.bplayer
                )
                if reason == "resign":
                    await opp_player.notify_game_end(self)
                else:
                    await cur_player.notify_game_end(self)
                    await opp_player.notify_game_end(self)

        response: GameEndResponse = {
            "type": "gameEnd",
            "status": self.status,
            "result": self.result,
            "gameId": self.id,
            "pgn": self.pgn,
            "ct": self.crosstable,
            "rdiffs": (
                {"brdiff": self.brdiff, "wrdiff": self.wrdiff}
                if self.status > STARTED and self.rated == RATED
                else ""
            ),
        }
        if self.jieqi and self.jieqi_captures is not None:
            response["jieqiCaptures"] = list(self.jieqi_captures[WHITE]) + list(
                self.jieqi_captures[BLACK]
            )
            if self.jieqi_capture_stack is not None:
                response["jieqiCaptureStack"] = [
                    capture[1] if capture else None for capture in self.jieqi_capture_stack
                ]
        return response

    def start_manual_count(self) -> None:
        if self.manual_count:
            cur_player = self.bplayer if self.board.color == BLACK else self.wplayer
            opp_player = self.wplayer if self.board.color == BLACK else self.bplayer
            self.draw_offers.discard(opp_player.username)
            self.draw_offers.add(cur_player.username)
            self.board.count_started = self.board.ply + 1

    def stop_manual_count(self) -> None:
        if self.manual_count:
            cur_player = self.bplayer if self.board.color == BLACK else self.wplayer
            opp_player = self.wplayer if self.board.color == BLACK else self.bplayer
            self.draw_offers.discard(cur_player.username)
            self.draw_offers.discard(opp_player.username)
            self.manual_count_toggled.append((self.board.count_started, self.board.ply + 1))
            self.board.count_started = -1

    def create_steps(self) -> None:
        # log.debug("create_steps() START")
        tolerate_historical_replay_failure = should_tolerate_historical_replay_failure(
            self.date,
            self.status,
            self.loaded_at,
        )
        if self.mct is not None:
            manual_count_toggled = iter(self.mct)
            count_started = -1
            count_ended = -1

        replay_jieqi_captures = {WHITE: [], BLACK: []} if self.jieqi_captures is not None else None
        replay_jieqi_capture_stack: list[tuple[int, str] | None] | None = (
            [] if self.jieqi_capture_stack is not None else None
        )

        if self.analysis is not None:
            self.steps[0]["analysis"] = self.analysis[0]

        moves_to_replay = list(self.board.move_stack)
        replay_board = FairyBoard(
            self.variant,
            self.board.initial_fen,
            bool(self.chess960),
            count_started=self.board.count_started,
            show_promoted=self.server_variant.show_promoted,
            legal_moves_need_history=self.server_variant.legal_moves_need_history,
        )
        if self.board.jieqi_initial_covered_pieces is not None:
            replay_board.jieqi_initial_covered_pieces = dict(
                self.board.jieqi_initial_covered_pieces
            )
            replay_board.jieqi_covered_pieces = dict(self.board.jieqi_initial_covered_pieces)

        if should_use_legacy_capablanca_replay(
            self.variant,
            self.board.variant,
            bool(self.chess960),
            moves_to_replay,
        ):
            # Historical Capablanca games can contain old castling coordinates
            # (e-file king to c/i-file, e.g. e8i8). Modern board construction
            # maps this start position to Embassy rules, where these moves are
            # invalid. Rebuild steps on an unmodded Capablanca board so legacy
            # archives still replay without corrupting move history.
            # FairyBoard constructor applies modded_variant() automatically.
            # Force the original stored variant here to preserve old move coords.
            replay_board.variant = self.variant

        replay_completed = True
        replay_check = self.check
        for ply, move in enumerate(moves_to_replay):
            try:
                if self.mct is not None:
                    # print("Ply", ply, "Move", move)
                    if ply + 1 >= count_ended:
                        try:
                            replay_board.count_started = -1
                            count_started, count_ended = next(manual_count_toggled)
                            # print("New count interval", (count_started, count_ended))
                        except StopIteration:
                            # print("Piece's honour counting started")
                            count_started = 0
                            count_ended = MAX_PLY + 1
                            replay_board.count_started = 0
                    if ply + 1 == count_started:
                        # print("Count started", count_started)
                        replay_board.count_started = ply

                if self.jieqi and move[-1].isalpha():
                    move = move[:-1]

                san = replay_board.get_san(move)

                if self.jieqi:
                    # Replay uses the current board mapping, so capture identity
                    # must be determined before pushing the move and mutating it.
                    jieqi_capture = replay_board.captured_jieqi_piece(move)
                    new_piece = replay_board.revealed_piece(move)
                    if new_piece is not None:
                        move = move + new_piece.lower()
                        san = "%s=%s" % (san, new_piece.lower())
                else:
                    jieqi_capture = None

                pushed = replay_board.push(
                    move,
                    raise_on_error=not tolerate_historical_replay_failure,
                )
                if not pushed:
                    replay_completed = False
                    log.warning(
                        "Stopped step reconstruction for historical game %s %s %s after invalid replay move %s",
                        self.id,
                        self.variant,
                        self.date.isoformat(),
                        move,
                    )
                    break
                replay_check = replay_board.is_checked()
                turnColor = "black" if replay_board.color == BLACK else "white"

                if self.usi_format:
                    turnColor = "black" if turnColor == "white" else "white"
                step: GameStep = {
                    "fen": replay_board.fen,
                    "move": move,
                    "san": san,
                    "turnColor": turnColor,
                    "check": replay_check,
                }

                if len(self.clocks_w) > 1 and not self.corr:
                    move_number = ((ply + 1) // 2) + (1 if ply % 2 == 0 else 0)
                    step["clocks"] = (
                        self.clocks_w[move_number],
                        self.clocks_b[move_number - 1 if ply % 2 == 0 else move_number],
                    )

                if replay_jieqi_capture_stack is not None:
                    mover_color = WHITE if step["turnColor"] == "black" else BLACK
                    if jieqi_capture is not None and replay_jieqi_captures is not None:
                        # Rebuild capture history without exposing it in steps or SAN.
                        replay_jieqi_captures[mover_color].append(jieqi_capture.lower())
                        replay_jieqi_capture_stack.append((mover_color, jieqi_capture.lower()))
                    else:
                        replay_jieqi_capture_stack.append(None)

                self.steps.append(step)

                if (self.analysis is not None) and (not self.usi_format):
                    try:
                        self.steps[-1]["analysis"] = self.analysis[ply + 1]
                    except IndexError:
                        log.error("IndexError in create_steps() %d %s %s", ply, move, san)

            except Exception:
                replay_completed = False
                if tolerate_historical_replay_failure:
                    log.warning(
                        "Stopped step reconstruction for historical game %s %s %s after replay exception on %s",
                        self.id,
                        self.variant,
                        self.date.isoformat(),
                        move,
                    )
                else:
                    log.exception(
                        "Exception in create_steps() %s %s %s %s %s",
                        self.id,
                        self.variant,
                        replay_board.initial_fen,
                        move,
                        moves_to_replay,
                    )
                break
        if replay_completed:
            self.check = replay_check
            if replay_jieqi_captures is not None:
                self.jieqi_captures = replay_jieqi_captures
                self.jieqi_capture_stack = replay_jieqi_capture_stack
                self.last_jieqi_capture = None
                self.board.jieqi_covered_pieces = replay_board.jieqi_covered_pieces
        # log.debug("create_steps() OK")

    def ensure_steps(self) -> None:
        if len(self.board.move_stack) > 0 and len(self.steps) == 1:
            self.create_steps()

    def display_history(self) -> GameDisplayHistory:
        """Pack finished-game display inputs without native engine replay."""
        moves = list(self.board.move_stack)
        variant = self.board.variant
        if should_use_legacy_capablanca_replay(self.variant, variant, bool(self.chess960), moves):
            variant = self.variant
        history: GameDisplayHistory = {
            "variant": variant,
            "chess960": bool(self.chess960),
            "moves": moves,
            "showPromoted": self.board.show_promoted,
            "countStarted": self.board.count_started,
            "usi": self.usi_format,
        }
        if len(self.clocks_w) > 1 and not self.corr:
            history["clocksWhite"] = list(self.clocks_w)
            history["clocksBlack"] = list(self.clocks_b)
        analysis = (
            [step.get("analysis") for step in self.steps] if len(self.steps) > 1 else self.analysis
        )
        if analysis is not None:
            history["analysis"] = analysis[:1] if self.usi_format else analysis
        if self.mct is not None:
            history["countIntervals"] = list(self.mct)
        elif self.manual_count:
            intervals = list(self.manual_count_toggled)
            if self.board.count_started > 0:
                intervals.append((self.board.count_started, self.board.ply + 1))
            history["countIntervals"] = intervals
        if self.board.jieqi_initial_covered_pieces is not None:
            history["jieqiCovered"] = dict(self.board.jieqi_initial_covered_pieces)
        return history

    def get_board(
        self,
        full: bool = False,
        persp_color: int | None = None,
        *,
        client_history: bool = False,
    ) -> GameBoardResponse:
        browser_replay = client_history and full and self.status > STARTED
        if not browser_replay:
            self.ensure_steps()

        fen, lastmove = self.board.fen, self.lastmove

        clocks: list[int | float]
        if full:
            steps = [dict(self.steps[0])] if browser_replay else self.steps

            # To not touch self.clocks_w and self.clocks_b we are creating deep copy from clocks
            try:
                clocks = [self.clocks[WHITE], self.clocks[BLACK]]
            except IndexError:
                clocks_init = (self.base * 1000 * 60) + 0 if self.base > 0 else self.inc * 1000
                clocks = [clocks_init, clocks_init]

            if self.status == STARTED and self.board.ply >= 2 and (not self.corr):
                # We have to adjust current player latest saved clock time
                # otherwise he will get free extra time on browser page refresh
                # (also needed for spectators entering to see correct clock times)
                clocks[self.board.color] = max(
                    0,
                    clocks[self.board.color]
                    + self.byo_correction
                    - self.elapsed_on_current_turn_ms(),
                )
            crosstable = self.crosstable
        else:
            clocks = list(self.clocks)
            steps = [self.steps[-1]]
            crosstable = self.crosstable if self.status > STARTED else ""

        if self.fow and self.status <= STARTED:
            steps = get_fog_steps(steps, persp_color)
            fen = steps[-1]["fen"]
            if (persp_color is None) or (persp_color == self.board.color):
                lastmove = ""

        date = ""
        if self.corr:
            assert isinstance(self.stopwatch, CorrClock)
            clock_mins = int(self.stopwatch.mins * 60 * 1000)
            base_mins = self.base * 24 * 60 * 60 * 1000
            clocks = [
                base_mins if self.board.color == BLACK else clock_mins,
                base_mins if self.board.color == WHITE else clock_mins,
            ]
            date = (datetime.now(UTC) + timedelta(minutes=self.stopwatch.mins)).isoformat()

        response: GameBoardResponse = {
            "type": "board",
            "gameId": self.id,
            "variant": self.variant,
            "status": self.status,
            "result": self.result,
            "fen": fen,
            "lastMove": lastmove,
            "tp": self.turn_player,
            "steps": steps,
            "check": self.check,
            "ply": self.board.ply,
            "positionId": self.position_id(),
            "clocks": clocks,
            "byo": self.byoyomi_periods if self.byoyomi else "",
            "pgn": self.pgn if self.status > STARTED else "",
            "rdiffs": (
                {"brdiff": self.brdiff, "wrdiff": self.wrdiff}
                if self.status > STARTED and self.rated == RATED
                else ""
            ),
            "date": date,
            "uci_usi": self.uci_usi if self.status > STARTED else "",
            "ct": crosstable,
            "berserk": {"w": self.wberserk, "b": self.bberserk},
            "by": self.imported_by,
        }
        if browser_replay:
            response["history"] = self.display_history()
        if self.jieqi and self.jieqi_captures is not None:
            if self.status > STARTED:
                # After game end, reveal captured covered identities to everyone.
                response["jieqiCaptures"] = list(self.jieqi_captures[WHITE]) + list(
                    self.jieqi_captures[BLACK]
                )
                if self.jieqi_capture_stack is not None:
                    response["jieqiCaptureStack"] = [
                        capture[1] if capture else None for capture in self.jieqi_capture_stack
                    ]
            elif persp_color is not None:
                # During the game, only the capturer sees covered identities.
                response["jieqiCaptures"] = list(self.jieqi_captures[persp_color])
                if self.jieqi_capture_stack is not None:
                    # Include a per-move capture stack (only the viewer's captures) so the
                    # client can render captures correctly while navigating the move list.
                    response["jieqiCaptureStack"] = [
                        capture[1] if capture and capture[0] == persp_color else None
                        for capture in self.jieqi_capture_stack
                    ]
        return response

    def game_json(self, player: User) -> GameSummaryJson:
        color: Literal["w", "b"] = "w" if self.wplayer == player else "b"
        opp_player = self.bplayer if color == "w" else self.wplayer
        opp_rating = self.brating if color == "w" else self.wrating
        response: GameSummaryJson = {
            "gameId": self.id,
            "title": opp_player.title,
            "name": opp_player.username,
            "rating": int(opp_rating.rstrip("?")),
            "color": color,
            "result": self.result,
            # Keep termination status alongside result so tournament views can apply variant-specific points.
            "status": int(self.status),
        }
        return response

    @property
    def tv_game_json(self) -> TvGameJson:
        chess960 = self.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        response: TvGameJson = {
            "type": "tv_game",
            "gameId": self.id,
            "variant": self.variant,
            "fen": self.board.fen,
            "wt": self.wplayer.title,
            "bt": self.bplayer.title,
            "w": self.wplayer.username,
            "b": self.bplayer.username,
            "wr": self.wrating,
            "br": self.brating,
            "chess960": chess960,
            "base": self.base,
            "inc": self.inc,
            "byoyomi": self.byoyomi_period,
            "lastMove": self.lastmove,
        }
        return response

    @property
    def turn_player(self) -> str:
        return self.wplayer.username if self.board.color == WHITE else self.bplayer.username

    def position_id(self) -> str:
        digest = hashlib.blake2s(digest_size=12)
        digest.update(self.board.fen.encode("utf-8"))
        return digest.hexdigest()

    async def takeback(self, requester: User) -> None:
        """Rewind the move(s) the requester is asking to replay.

        A request made immediately after the requester's move rewinds one ply.
        A request made on the requester's turn rewinds the opponent's last move
        and the requester's preceding move, matching lichess takeback behavior.
        """
        # Defense in depth: callers must never mutate rated game history.
        if (
            self.rated != CASUAL
            or self.board.ply < 2
            or (self.byoyomi and len(self.byoyomi_state_stack) != self.board.ply + 1)
        ):
            return

        self.stopwatch.stop()
        turn_player = self.bplayer if self.board.color == BLACK else self.wplayer
        plies = 2 if requester.username == turn_player.username else 1

        def pop_jieqi_capture() -> None:
            # Takebacks must also undo any stored Jieqi capture identities.
            if self.jieqi_capture_stack is None or not self.jieqi_capture_stack:
                return
            capture = self.jieqi_capture_stack.pop()
            if capture is None or self.jieqi_captures is None:
                return
            color, _piece = capture
            try:
                if self.jieqi_captures[color]:
                    self.jieqi_captures[color].pop()
            except Exception:
                log.exception("Failed to rollback Jieqi capture for %s", self.id)

        for _ in range(plies):
            # The side opposite the current turn made the move being removed.
            mover_color = BLACK if self.board.color == WHITE else WHITE
            mover_clock = self.clocks_b if mover_color == BLACK else self.clocks_w
            self.board.pop()
            pop_jieqi_capture()
            if len(mover_clock) > 1:
                mover_clock.pop()
            self.steps.pop()
            if self.byoyomi:
                self.byoyomi_state_stack.pop()
                self.restore_byoyomi_state(self.byoyomi_state_stack[-1])
            await self.pop_move_from_db()

        if self.board.ply == 0 and self.counted_as_active:
            self.counted_as_active = False
            self.app_state.g_cnt[0] -= 1
            await self.app_state.lobby.lobby_broadcast(
                {"type": "g_cnt", "cnt": self.app_state.g_cnt[0]}
            )
            if self.variant != "janggi" or self.bsetup or self.wsetup:
                self.status = CREATED

        self.has_legal_move = self.board.has_legal_move()
        if self.random_mover:
            self.legal_moves = self.board.legal_moves()
        self.lastmove = self.board.move_stack[-1] if self.board.move_stack else None
        self.check = self.board.is_checked()
        await self.save_takeback_state()
        self.last_server_clock = monotonic()
        self.restart_elapsed_ms = 0
        self.stopwatch.restart()

    def handle_chat_message(self, chat_message: Mapping[str, object]) -> None:
        self.messages.append(chat_message)


def get_fog_steps(steps: Sequence[GameStep], persp_color: int | None) -> list[GameStep]:
    if persp_color is None:
        return [{"fen": DARK_FEN} for step in steps]
    else:
        return [
            {
                "fen": get_fog_fen(step["fen"], persp_color),
                "san": "?",
                "turnColor": step["turnColor"],
            }
            for step in steps
        ]
