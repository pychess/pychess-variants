import asyncio
import collections
import logging
from datetime import UTC, datetime
from time import time_ns
from typing import TYPE_CHECKING

from compress import R2C
from const import (
    ABORTED,
    CASUAL,
    DRAW,
    IMPORTED,
    LOSERS,
    MATE,
    MAX_CHAT_LINES,
    POCKET_PATTERN,
    RATED,
    STARTED,
)
from convert import grand2zero
from fairy import BLACK, WHITE, FairyBoard
from pychess_global_app_state import PychessGlobalAppState
from spectators import spectators
from user import User
from variants import GRANDS, get_server_variant

from bug.game_bug_clocks import GameBugClocks
from bug.history import clock_columns, replay_history, step_metadata

log = logging.getLogger(__name__)

# A backlog this deep means the database is not keeping up and the one-ply loss window is widening.
MOVE_PERSIST_QUEUE_WARN_DEPTH = 3
# How long save_game() waits for queued plies before writing the authoritative arrays anyway.
MOVE_PERSIST_DRAIN_TIMEOUT = 5.0

MAX_HIGH_SCORE = 10
MAX_PLY = 2 * 600
KEEP_TIME = 1800  # keep game in app[games_key] for KEEP_TIME secs


class GameBug:
    white_rating: object
    black_rating: object
    bsetup: bool
    wsetup: bool

    def __init__(
        self,
        app_state: PychessGlobalAppState,
        gameId,
        variant,
        initial_fen,
        wplayerA,
        bplayerA,
        wplayerB,
        bplayerB,
        base: float = 1,
        inc=0,
        level=0,
        rated=CASUAL,
        chess960=False,
        create=True,
        tournamentId=None,
        new_960_fen_needed_for_rematch=False,
    ):
        self.app_state = app_state

        self.saved = False

        # Per-ply persistence: one producer under `move_lock`, one consumer, so writes land in
        # order. See `_queue_move_persist()`.
        self._persist_queue: asyncio.Queue = asyncio.Queue()
        self._persist_task: asyncio.Task | None = None

        self.variant = variant
        self.initial_fen = initial_fen
        self.wplayerA = wplayerA
        self.bplayerA = bplayerA
        self.wplayerB = wplayerB
        self.bplayerB = bplayerB
        self.team1 = [self.wplayerA.username, self.bplayerB.username]
        self.team2 = [self.bplayerA.username, self.wplayerB.username]
        self.rated = rated
        self.base = base
        self.inc = inc
        self.level = level if level is not None else 0
        self.tournamentId = tournamentId
        # Always None: a bughouse game is never a round-robin arrangement. Declared anyway
        # because this class duck-types the common game interface rather than inheriting it,
        # and the SHARED Clock reads this attribute — `first_move_timeout_reason()` in
        # clock.py, which decides whether an unstarted game is aborted or flagged. Missing, it
        # raised AttributeError inside `Clock.countdown()`, killing the clock task: the server
        # then never timed the game out at all, and the only thing that ended it was a client
        # sending its own `flag`. Same reason `simulId` below is declared.
        self.tournamentArrangementId: str | None = None
        self.simulId: str | None = None
        self.chess960 = chess960
        self.create = create
        self.new_960_fen_needed_for_rematch = new_960_fen_needed_for_rematch
        self.imported_by = ""

        self.server_variant = get_server_variant(variant, chess960)
        self.encode_method = self.server_variant.move_encoding

        self.berserk_time = self.base * 1000 * 30

        self.browser_title = "%s • %s+%s vs %s+%s" % (
            self.server_variant.display_name.title(),
            self.wplayerA.username,
            self.bplayerB.username,
            self.wplayerB.username,
            self.bplayerA.username,
        )

        # rating info
        self.white_rating_a = wplayerA.get_rating(variant, chess960)
        self.white_rating_b = wplayerB.get_rating(variant, chess960)
        self.wrating_a = "%s%s" % self.white_rating_a.rating_prov
        self.wrating_b = "%s%s" % self.white_rating_b.rating_prov
        self.wrdiff: int | str = 0
        self.black_rating_a = bplayerA.get_rating(variant, chess960)
        self.black_rating_b = bplayerB.get_rating(variant, chess960)
        self.brating_a = "%s%s" % self.black_rating_a.rating_prov
        self.brating_b = "%s%s" % self.black_rating_b.rating_prov
        self.brdiff: int | str = 0

        # crosstable info
        self.need_crosstable_save = False
        self.bot_game = False

        self.spectators = set()
        # Kept because shared code still reads it; bughouse never writes to it. A set of
        # usernames compared against wplayer/bplayer has no four-player reading, and
        # save_draw_offer() persists it into the wd/bd columns, which describe one board.
        self.draw_offers = set()
        # THE TWO TEAM OFFERS. Both belong to a team here rather than to a player, which
        # is the whole difference from the single-board game.
        #
        # `draw_offer_team` is the team that has offered; either member of the OTHER team
        # answers it. Held as the team's own list object, so `is` settles membership and
        # no second copy can drift from team1/team2.
        #
        # `resign_offer` is the username of the player who asked their partner to resign.
        # One name gives both facts needed: which team is resigning, and which of the two
        # is the one who may confirm (the other one).
        #
        # NEITHER SURVIVES A RESTART, AND THAT IS ACCEPTED — decided 2026-09-12 after
        # weighing it, so nobody spends an afternoon on it again. An offer is an intention,
        # not a fact about the position: restoring it would mean persisting intentions in
        # the document, which it has never held, and the alternative of cancelling offers
        # whenever a socket drops needs a server-side hook plus a message the clients do
        # not have — both far past what the case is worth.
        #
        # WHAT IT COSTS IS ONE MISREAD PRESS, and it announces itself. A client that lived
        # through the restart still shows the control; the next move does not clear it
        # (`cancel_team_offers_on_move` only speaks when this state is set), so the press
        # comes. Then `handle_draw_bughouse` sees no offer and records a NEW one from the
        # presser's team, broadcast to all four with `full=True`; `handle_resign_request`
        # does the same for the team. So the button does the wrong thing exactly once, no
        # game ends wrongly, nothing is left stuck, and every client is told the new truth
        # by the press itself. A client that reloaded shows nothing and was right all along.
        self.draw_offer_team: list[str] | None = None
        self.resign_offer: str | None = None
        self.takeback_offer: tuple[str, int] | None = None
        self.rematch_offers = set()
        self.rematch_id: str | None = None
        self.messages = collections.deque([], MAX_CHAT_LINES)
        self.date = datetime.now(UTC)

        self.lastmove = None
        self._history_doc: dict | None = None
        self._history_moves: list[str] = []
        self._history_replayed = False
        self.lastmovePerBoardAndUser = {"a": {}, "b": {}}
        self.status = STARTED  # CREATED
        self.result: str = "*"
        self.id = gameId
        # Bughouse variants do not have a Janggi-style setup phase.
        self.bsetup = False
        self.wsetup = False

        start_fen = initial_fen if initial_fen else FairyBoard.start_fen(variant, chess960)
        if chess960:
            self.initial_fen = start_fen

        fenA, fenB = map(str.strip, start_fen.split("|"))

        self.boards = {
            "a": FairyBoard(self.variant, fenA, self.chess960),
            "b": FairyBoard(self.variant, fenB, self.chess960),
        }

        self.gameClocks = GameBugClocks(self)

        self.overtime = False

        self.has_legal_moveA = self.boards["a"].has_legal_move()
        self.has_legal_moveB = self.boards["b"].has_legal_move()

        self.checkA = self.boards["a"].is_checked()
        self.checkB = self.boards["b"].is_checked()

        self.steps = [
            {
                "fen": self.boards["a"].initial_fen,
                "fenB": self.boards["b"].initial_fen,
                "san": None,
                "clocks": self.gameClocks.ply_clocks["a"][0],
                "clocksB": self.gameClocks.ply_clocks["b"][0],
                "ts": time_ns(),
            }
        ]

        if self.create and not self.bplayerA.bot:
            self.bplayerA.game_in_progress = self.id
        if self.create and not self.wplayerA.bot:
            self.wplayerA.game_in_progress = self.id
        if self.create and not self.bplayerB.bot:
            self.bplayerB.game_in_progress = self.id
        if self.create and not self.wplayerB.bot:
            self.wplayerB.game_in_progress = self.id

        self.move_lock = asyncio.Lock()

    async def cancel_clocks_for_eviction(self) -> None:
        await self.gameClocks.cancel_stopwatches()

    def berserk(self, color):
        pass

    def handle_chat_message(self, user, message, room):
        self.ensure_steps()
        cur_ply = len(self.steps) - 1
        time = self.gameClocks.elapsed_since_last_move()
        step_chat = {"message": message, "username": user.username, "time": time, "room": room}
        self.steps[cur_ply].setdefault("chat", []).append(step_chat)
        return step_chat

    def construct_chat_list(self):
        chat = {}
        for ply, step in enumerate(self.steps):
            if "chat" in step:
                chat["m" + str(ply)] = []
                for msg in step["chat"]:
                    if msg["room"] != "spectator":
                        chat["m" + str(ply)].append(
                            {"t": msg["time"], "u": msg["username"], "m": msg["message"]}
                        )
        return chat

    async def play_move(
        self, move, clocks=None, clocks_b=None, board="a"
    ):  # , last_move_captured_role=None
        log.debug(
            "play_move %r %r %r %r", move, clocks, clocks_b, board
        )  # , last_move_captured_role

        if self.status > STARTED:
            log.warning("play_move: game %s already ended", self.id)
            return
        if self.ply == 0:  # game is considered started right off the bat - notify lobbies
            self.app_state.g_cnt[0] += 1
            response = {"type": "g_cnt", "cnt": self.app_state.g_cnt[0]}
            await self.app_state.lobby.lobby_broadcast(response)

        cur_player_a = self.bplayerA if self.boards["a"].color == BLACK else self.wplayerA
        cur_player_b = self.bplayerB if self.boards["b"].color == BLACK else self.wplayerB
        cur_player = cur_player_a if board == "a" else cur_player_b

        if self.status <= STARTED:
            # NOTHING CHANGES UNTIL THE MOVE IS KNOWN GOOD.
            #
            # This used to be decided further down, by whichever engine call happened to throw
            # first — and by then the clocks had been stopped, `last_move_clocks` overwritten with
            # numbers the refusing client sent, an extra entry appended to `ply_clocks`, and a
            # captured piece possibly already dropped into the partner's pocket. Measured on a
            # fresh game: ONE refused move left `ply_clocks` holding three entries for a board with
            # one move and one step, the opponent's stored clock replaced by the sender's value,
            # and that board's stopwatch stopped and never restarted.
            #
            # It did not matter while a refused move ended the game — the damage died with it.
            # `bughouse-reject-invalid-move-without-ending` made the game CONTINUE, which turned a
            # one-off into state that persists and can be repeated at will. The guard is the other
            # half of that change, not a separate improvement.
            #
            # `legal_moves_no_history()` rather than `legal_moves()`: its own comment says it
            # exists for exactly this case, because bughouse cannot recreate a board's history
            # (pieces arrive from the other board) and the history-based generator would be wrong
            # here. It answers in the same UCI form clients send.
            if move not in self.boards[board].legal_moves_no_history():
                log.warning(
                    "Game %s refusing %s on board %s: not legal in this position",
                    self.id,
                    move,
                    board,
                )
                raise ValueError("%s is not legal in this position" % move)

            self.gameClocks.update_clocks(board, clocks, clocks_b)
            try:
                # COMPUTED before the push, because it reads the pre-move position; APPLIED after
                # it, because it writes to the OTHER board and `push()` can only roll back its own.
                # Applying it first meant a failure anywhere below left a piece in the partner's
                # pocket for a move that never happened, which nothing would ever take back.
                last_move_captured_role = self.boards[board].piece_to_partner(move)

                san = self.boards[board].get_san(move)
                self.lastmove = move
                self.lastmovePerBoardAndUser[board][cur_player.username] = move
                self.boards[board].push(move)

                # Past the last thing that can fail, so the two boards cannot disagree.
                if last_move_captured_role is not None:
                    partner_board = "a" if board == "b" else "b"
                    log.debug("lastMoveCapturedRole: %s", last_move_captured_role)
                    log.debug("self.boards[partner_board].fen: %s", self.boards[partner_board].fen)
                    # todo: this doesnt work after first move when starting game from custom initial fen that doesnt
                    #       have square brackets - either add them or dont consider it valid if missing pockets
                    self.boards[partner_board].fen = POCKET_PATTERN.sub(
                        r"[\1%s]" % last_move_captured_role, self.boards[partner_board].fen
                    )

                self.has_legal_moveA = self.boards["a"].has_legal_move()
                self.has_legal_moveB = self.boards["b"].has_legal_move()

                self.update_status()

                if self.status != MATE and san.endswith("#"):
                    san = san.replace("#", "+")

                move_a = move if board == "a" else ""
                move_b = move if board == "b" else ""
                check = self.checkB if board == "b" else self.checkA
                self.steps.append(
                    {
                        "fen": self.boards["a"].fen,
                        "fenB": self.boards["b"].fen,
                        "move": move_a,
                        "moveB": move_b,
                        "boardName": board,
                        "san": san,
                        "turnColor": (
                            "black" if self.boards[board].color == BLACK else "white"
                        ),  # can be derived from
                        # the fen and that is what i am actually doing - consider stop sending this value
                        "check": check,  # ignored. deriving  at the client the check status for each board from fens
                        # Four values, one of them real — see `game_bug_clocks.update_clocks`. The
                        # analysis page reconstructs the rest from the movers' own values.
                        "clocks": clocks,
                        "clocksB": clocks_b,
                        "ts": time_ns(),  # redundancy, but i am want to record how server time corresponds to sent
                    }
                )

                # Queue the ply BEFORE the end-of-game branch: a mating move is still a ply, and
                # `save_game()` drains this queue before it writes the final arrays.
                self._queue_move_persist(board, move)

                if self.status > STARTED:
                    await self.save_game()
                self.gameClocks.restart(board)
            except Exception:
                # THIS SHOULD NO LONGER HAPPEN, and that is the point of the guard above.
                #
                # It used to be where an illegal move was noticed — by whichever engine call threw
                # first — so it fired routinely, with a stack trace, for the ordinary case of a
                # client sending a move for a position it had already left. An ERROR that happens
                # in normal operation teaches everyone to ignore it.
                #
                # Now illegality is refused before anything is touched, so reaching here means
                # something is genuinely wrong: a malformed FEN, a position without the pocket
                # brackets the substitution above assumes (see the todo), or an engine that failed
                # on a move we had just certified as legal. All of those are worth a stack trace.
                #
                # It has never protected any state and does not now: `push()` rolls back its own
                # board, everything before it is read-only, and the pocket write is placed after
                # the push so a failure cannot leave the two boards disagreeing. Logging and
                # re-raising is the whole job — the re-raise is what lets `utils_bug.play_move()`
                # resync the sender in ONE place rather than two.
                log.exception("ERROR: Exception in game %s play_move() %s", self.id, move)
                raise

    def _queue_move_persist(self, board: str, move: str) -> None:
        """Queue this ply's database write, built from the ply's own values.

        THE PAYLOAD IS BUILT NOW, SYNCHRONOUSLY, not when the write runs. By the time the worker
        reaches it the game may be several plies further on, and a payload that read `self.boards`
        at that point would persist the wrong position under this ply's index.

        Ordering is structural rather than defended: `play_move()` runs under `game.move_lock`
        (`wsr.py`), so there is exactly one producer, and exactly one consumer drains the queue.
        `m` is decoded positionally on load, so two plies applied out of order do not merely arrive
        late — they decode to a different game.
        """
        if self.app_state.db is None:
            return

        step = self.steps[-1]
        # `m` holds one entry per move while `steps` also holds the initial position at index 0,
        # so the move just appended is `m[len(steps) - 2]`.
        move_index = len(self.steps) - 2

        encoded = self.encode_method(grand2zero(move) if self.variant in GRANDS else move)

        push_data = {
            "m": encoded,
            "o": 0 if board == "a" else 1,
            "ts": step["ts"],
            # One entry per array per ply, so all four stay index-aligned with `m` the way
            # `save_game()` writes them whole. DEPRECATED CONTENT, and knowingly so: only the
            # mover's own entry is authoritative (see `GameBugClocks.update_clocks`). It is
            # persisted in the existing shape so every reader — the analysis page, the movelist,
            # `load_game_bug_from_doc` — keeps working unchanged.
            "cw": step["clocks"][WHITE],
            "cb": step["clocks"][BLACK],
            "cwB": step["clocksB"][WHITE],
            "cbB": step["clocksB"][BLACK],
        }
        set_data = {"f": self.fen, "s": self.status}

        # Compare-and-set, in the spirit of the one-board `Game.save_move()`: apply only to an
        # unfinished game that does not already hold this ply and does hold the one before it.
        # A duplicate or out-of-order write then becomes a no-op instead of a corruption.
        persist_filter: dict = {
            "_id": self.id,
            "s": {"$lte": STARTED},
            f"m.{move_index}": {"$exists": False},
        }
        if move_index > 0:
            persist_filter[f"m.{move_index - 1}"] = {"$exists": True}

        write = (move_index, move, persist_filter, set_data, push_data)

        if self._persist_task is None:
            self._persist_task = asyncio.create_task(
                self._drain_move_persist_queue(), name="bug-persist-%s" % self.id
            )
        self._persist_queue.put_nowait(write)

        # BOUND THE LOSS WINDOW. One ply in flight is the accepted risk; a slow database must not
        # quietly turn that into many. Beyond a small depth the queue stops being a buffer and
        # becomes a backlog, so say so.
        depth = self._persist_queue.qsize()
        if depth > MOVE_PERSIST_QUEUE_WARN_DEPTH:
            log.warning(
                "Game %s move persistence is %s plies behind; the database is not keeping up",
                self.id,
                depth,
            )

    async def _drain_move_persist_queue(self) -> None:
        """One consumer, so the writes land in the order they were produced."""
        while True:
            write = await self._persist_queue.get()
            try:
                if write is None:
                    return
                move_index, move, persist_filter, set_data, push_data = write
                result = await self.app_state.db.game.update_one(
                    persist_filter, {"$set": set_data, "$push": push_data}
                )
                if result.modified_count != 1:
                    # Not fatal: the filter is what makes a replayed or duplicated write harmless,
                    # so a miss usually means the ply is already recorded. Worth a line, because
                    # the other way to miss is a document that has moved on without us.
                    log.info(
                        "Game %s ply %s (%s) was not persisted; already present or superseded",
                        self.id,
                        move_index,
                        move,
                    )
            except Exception:
                log.exception("Failed to persist ply for game %s", self.id)
            finally:
                self._persist_queue.task_done()

    async def _finish_move_persistence(self) -> None:
        """Let every queued ply land before the end-of-game write overwrites the arrays."""
        if self._persist_task is None:
            return
        try:
            await asyncio.wait_for(self._persist_queue.join(), timeout=MOVE_PERSIST_DRAIN_TIMEOUT)
        except TimeoutError:
            log.warning("Game %s move persistence did not drain before save_game()", self.id)

        self._persist_queue.put_nowait(None)
        task, self._persist_task = self._persist_task, None
        try:
            await asyncio.wait_for(task, timeout=MOVE_PERSIST_DRAIN_TIMEOUT)
        except TimeoutError:
            task.cancel()

    async def save_game(self):
        if self.saved:
            return
        self.saved = True

        # Before the authoritative arrays are written whole, so the last ply cannot race the close.
        await self._finish_move_persistence()

        if self.rated == IMPORTED:
            log.exception("Save IMPORTED game %s ???", self.id)
            return

        await self.gameClocks.cancel_stopwatches()

        self.app_state.g_cnt[0] -= 1
        response = {"type": "g_cnt", "cnt": self.app_state.g_cnt[0]}
        await self.app_state.lobby.lobby_broadcast(response)

        self.app_state.schedule_game_cache_removal(self)

        # always save them, even if no moves - todo: will optimize eventually, just want it simple now
        # and have trace of all games for later investigation
        if False:
            result = await self.app_state.db.game.delete_one({"_id": self.id})
            log.debug(
                "Removed too short game %s from db. Deleted %s game.",
                self.id,
                result.deleted_count,
            )
        else:
            if self.result != "*":
                if self.rated == RATED:
                    await self.update_ratings()
                await self.update_players_game_counts()

            if self.tournamentId is not None:
                try:
                    await self.app_state.tournaments[self.tournamentId].game_update(self)
                except Exception:
                    log.exception("Exception in tournament game_update()")
            moves = [x["move"] + x["moveB"] for x in self.steps[1:]]
            new_data = {
                "d": self.date,
                "f": self.boards["a"].fen + " | " + self.boards["b"].fen,
                "s": self.status,
                "r": R2C[self.result],
                "m": [
                    *map(
                        self.encode_method,
                        (map(grand2zero, moves) if self.variant in GRANDS else moves),
                    )
                ],
                "o": [0 if x["boardName"] == "a" else 1 for x in self.steps[1:]],
                "c": self.construct_chat_list(),
                # `.get`, not `[...]`: a game rebuilt from a document written before per-ply
                # persistence has no `ts` array to rebuild its steps from, and one missing
                # timestamp must not cost the whole ending. See the matching note in
                # `load_game_bug_from_doc()`.
                "ts": [x.get("ts", 0) for x in self.steps],
                "cw": self.gameClocks.get_ply_clocks_for_board_and_color("a", WHITE),
                "cb": self.gameClocks.get_ply_clocks_for_board_and_color("a", BLACK),
                "cwB": self.gameClocks.get_ply_clocks_for_board_and_color("b", WHITE),
                "cbB": self.gameClocks.get_ply_clocks_for_board_and_color("b", BLACK),
            }

            if self.app_state.db is not None:
                await self.app_state.db.game.find_one_and_update(
                    {"_id": self.id}, {"$set": new_data}
                )

    async def update_ratings(self):
        pass  # todo no rating in bughouse for now

    async def update_players_game_counts(self) -> None:
        if self.result not in ("1-0", "0-1", "1/2-1/2"):
            return

        rated = self.rated == RATED
        if self.result == "1-0":
            result_by_username = {
                self.wplayerA.username: 1,
                self.bplayerB.username: 1,
                self.bplayerA.username: -1,
                self.wplayerB.username: -1,
            }
        elif self.result == "0-1":
            result_by_username = {
                self.bplayerA.username: 1,
                self.wplayerB.username: 1,
                self.wplayerA.username: -1,
                self.bplayerB.username: -1,
            }
        else:
            result_by_username = {
                self.wplayerA.username: 0,
                self.bplayerA.username: 0,
                self.wplayerB.username: 0,
                self.bplayerB.username: 0,
            }

        seen: set[str] = set()
        for player in self.all_players:
            if player.anon or player.username in seen:
                continue
            seen.add(player.username)
            await player.increment_game_count(result_by_username.get(player.username, 0), rated)

    @property
    def corr(self):
        return False

    @property
    def all_players(self):
        return [self.wplayerA, self.bplayerA, self.wplayerB, self.bplayerB]

    @property
    def non_bot_players(self):
        return set(filter(lambda p: not p.bot, self.all_players))

    def team_of(self, username: str) -> list[str] | None:
        """The team list a player belongs to, or None for a spectator.

        Returns the actual team1/team2 object rather than a copy, so callers can compare
        teams with `is` and never have to hold a username set of their own.
        """
        if username in self.team1:
            return self.team1
        if username in self.team2:
            return self.team2
        return None

    def partner_of(self, username: str) -> str | None:
        """The other member of this player's team, or None for a spectator."""
        team = self.team_of(username)
        if team is None:
            return None
        return next((name for name in team if name != username), None)

    @property
    def wplayer(self):
        return self.wplayerA  # temporary for compatibitly everywhere this stuff is accessed now

    @property
    def bplayer(self):
        return self.bplayerA  # temporary for compatibitly everywhere this stuff is accessed now

    @property
    def byoyomi_period(self):
        return 0

    @property
    def crosstable(self):
        return ""

    @property
    def wrating(self) -> str:
        return self.wrating_a  # temporary for compatibitly everywhere this stuff is accessed now

    @property
    def brating(self) -> str:
        return self.brating_a  # temporary for compatibitly everywhere this stuff is accessed now

    @property
    def fen(self):
        return self.boards["a"].fen + " | " + self.boards["b"].fen

    @property
    def preview_fen(self):
        # Generic lobby/game previews only render one board, so keep using board A there.
        return self.boards["a"].fen

    @property
    def posnum(self):
        return -1

    @property
    def ply(self):
        return self.boards["a"].ply + self.boards["b"].ply

    def get_player_at(self, color, board):
        if board == self.boards["a"]:
            return self.bplayerA if color == BLACK else self.wplayerA
        else:
            return self.bplayerB if color == BLACK else self.wplayerB

    def is_player(self, user: User) -> bool:
        return user.username in (
            self.wplayerA.username,
            self.bplayerA.username,
            self.wplayerB.username,
            self.bplayerB.username,
        )

    def update_status(self, status: int | None = None, result: str | None = None):
        if self.status > STARTED:
            return

        if status is not None:
            self.status = status
            if result is not None:
                self.result = result
            self.remove_players_game_in_progress()
            return

        self.checkA = self.boards["a"].is_checked()
        self.checkB = self.boards["b"].is_checked()

        self.check_checkmate_on_board_and_update_status("a")
        self.check_checkmate_on_board_and_update_status("b")

        if self.boards["a"].ply + self.boards["b"].ply > MAX_PLY:
            self.status = DRAW
            self.result = "1/2-1/2"

        if self.status > STARTED:
            self.remove_players_game_in_progress()

    def remove_players_game_in_progress(self):
        if not self.bplayerA.bot:
            self.bplayerA.game_in_progress = None
        if not self.wplayerA.bot:
            self.wplayerA.game_in_progress = None
        if not self.bplayerB.bot:
            self.bplayerB.game_in_progress = None
        if not self.wplayerB.bot:
            self.wplayerB.game_in_progress = None

    @staticmethod
    def result_string_from_value(game_result_value, board_which_ended):
        if board_which_ended == "a":
            if game_result_value < 0:
                return "0-1"  # black wins on first board => team 2 wins
            if game_result_value > 0:
                return "1-0"  # white wins on first board => team 1 wins
            return "1/2-1/2"
        if board_which_ended == "b":
            if game_result_value < 0:
                return "1-0"  # black wins on second board => team 1 wins
            if game_result_value > 0:
                return "0-1"  # white wins on second board => team 2 wins
            return "1/2-1/2"

    def check_checkmate_on_board_and_update_status(self, board: str):
        # it is not mate if there are possible move dests on the given board
        # todo: if it is check that is blockable, but no pieces in pocket, dests might be empty but it is not mate
        if board == "a" and self.has_legal_moveA or board == "b" and self.has_legal_moveB:
            return False

        # did it really end - chess rules for checkmate do not apply here if it is possible to block the check
        # with a piece that partner could potentially give. Check same position, but with full pocket
        # to confirm it is really checkmate even if we wait for partner
        fen_before = self.boards[board].fen
        self.boards[board].fen = POCKET_PATTERN.sub("[qrbnpQRBNP]", fen_before)
        count_valid_moves_with_full_pockets = len(self.boards[board].legal_moves_no_history())
        self.boards[board].fen = fen_before

        if count_valid_moves_with_full_pockets == 0:
            # this always returns -32000 todo: maybe delete that function if cant figure out why
            # game_result_value =  self.boards[board].game_result_no_history()
            # if it is whites turn then black wins => -1, else white wins => +1
            game_result_value = -1 if self.boards[board].color == WHITE else 1
            result = GameBug.result_string_from_value(game_result_value, board)
            if TYPE_CHECKING:
                assert result is not None
            self.result = result
            self.status = MATE
            return True
        return False

    def print_game(self):
        log.info("pgn: %s", self.pgn)
        self.boards["a"].print_pos()
        self.boards["b"].print_pos()

    @property
    def board(self):
        # todo: potentially code that expects such property might be need to be changed in places related to
        #       draw request and tournaments if we implement those for bughouse.
        #
        # todo: The only other place where this might be called for bughouse game object is in game_api.py/get_games.
        #       Leaving it like this for now, doesn't seem critical.
        #
        # todo: Other places I have reviewed seem to only work with single-board game.py object. Often are related to
        #       some specific variant logic - maybe consider encapsulating such logic in game.py object somehow
        #       and avoid exposing board object directly.

        # Still in case this gets accidently called for game_bug.py objects, logging here an error and returning a
        # valid board object for board "A" so it doesn't crash:
        log.error(
            "game.board property called for a bughouse game object. Returning info just for board A"
        )
        return self.boards["a"]

    @property
    def pgn(self):
        return "serverside bpgn export not implemented"  # as far as I can tell this is never used - its only sent on
        # gameEnd message, but never read on client

    @property
    def uci_usi(self):
        return "position fen %s moves %s" % (
            self.boards["a"].initial_fen + " | " + self.boards["b"].initial_fen,
            " ".join(self.boards["a"].move_stack) + " | " + " ".join(self.boards["b"].move_stack),
        )

    @property
    def is_claimable_draw(self):  # todo not sure this makes much sense in bughouse
        return False

    @property
    def spectator_list(self):
        return spectators(self.spectators)

    def analysis_start(self, username):
        return (
            '{"type": "analysisStart", "username": "%s", "game": {"id": "%s", "skill_level": "%s", "chess960": "%s"}}\n'
            % (username, self.id, self.level, self.chess960)
        )

    @property
    def game_start(self):
        return (
            '{"type": "gameStart", "game": {"id": "%s", "skill_level": "%s", "chess960": "%s"}}\n'
            % (
                self.id,
                self.level,
                self.chess960,
            )
        )

    @property
    def game_end(
        self,
    ):  # only used by bot code, so not relevant for now for bughouse but keeping it anyway
        return '{"type": "gameEnd", "game": {"id": "%s"}}\n' % self.id

    async def abort(self):
        self.update_status(ABORTED)
        await self.save_game()
        return {
            "type": "gameEnd",
            "status": self.status,
            "result": "Game aborted.",
            "gameId": self.id,
            "pgn": self.pgn,
        }

    def game_end_payload(self):
        """The gameEnd message, shared by every way a bughouse game can finish."""
        return {
            "type": "gameEnd",
            "status": self.status,
            "result": self.result,
            "gameId": self.id,
            "pgn": self.pgn,
            # "ct": self.crosstable,
            "rdiffs": (
                {"brdiff": self.brdiff, "wrdiff": self.wrdiff}
                if self.status > STARTED and self.rated == RATED
                else ""
            ),
        }

    async def game_ended(self, user, reason):
        """Abort, resign, flag, abandone"""
        if self.result == "*":
            if reason == "abort":
                result = "*"
            else:
                result = "0-1" if user.username in self.team1 else "1-0"

            self.update_status(LOSERS[reason], result)
            await self.save_game()

        return self.game_end_payload()

    async def game_drawn(self):
        """Both teams agreed a draw.

        The counterpart of game_ended() for the one result that is nobody's loss, and the
        reason bughouse does not go through draw.py's draw(): that function decides
        agreement from `is_claimable_draw` and the two-player draw_offers set, and
        persists the outcome into wd/bd columns that describe a single board. Agreement
        here is settled before this is called — by the offer belonging to one team and the
        acceptance coming from the other.
        """
        if self.result == "*":
            self.update_status(DRAW, "1/2-1/2")
            await self.save_game()

        return self.game_end_payload()

    def ensure_steps(self) -> None:
        if self._history_doc is None or self._history_replayed:
            return
        self._history_replayed = True
        for board in self.boards.values():
            board.fen = board.initial_fen
            board.move_stack = []
            board.ply = 0
            board.color = WHITE if board.fen.split()[1] == "w" else BLACK
        self.checkA = self.boards["a"].is_checked()
        self.checkB = self.boards["b"].is_checked()
        replay_history(self, self._history_doc, self._history_moves)

    def display_history(self):
        if self._history_doc is None or self._history_replayed:
            return None
        columns = clock_columns(self, self._history_doc)
        return {
            "variant": self.variant,
            "chess960": self.chess960,
            "moves": self._history_moves,
            "boards": ["a" if board == 0 else "b" for board in self._history_doc["o"]],
            "metadata": [
                step_metadata(self._history_doc, columns, ply)
                for ply in range(1, len(self._history_moves) + 1)
            ],
        }

    def get_board(self, full=False, persp_color=None, *, client_history=False):
        history = (
            self.display_history() if full and client_history and self.status > STARTED else None
        )
        if history is None:
            self.ensure_steps()
        [clocks_a, clocks_b] = self.gameClocks.get_clocks_for_board_msg(full)
        if full:
            steps = self.steps
        else:
            steps = (self.steps[-1],)

        response = {
            "type": "board",
            "gameId": self.id,
            "status": self.status,
            "result": self.result,
            "fen": self.boards["a"].fen + " | " + self.boards["b"].fen,
            "lastMove": self.lastmove,
            "steps": steps,
            "check": self.checkA,
            "checkB": self.checkB,
            "ply": self.ply,
            "clocks": clocks_a,
            "clocksB": clocks_b,
            "pgn": self.pgn if self.status > STARTED else "",
            "rdiffs": (
                {"brdiff": self.brdiff, "wrdiff": self.wrdiff}
                if self.status > STARTED and self.rated == RATED
                else ""
            ),
            "uci_usi": self.uci_usi if self.status > STARTED else "",
            "rmA": "",
            "rmB": "",
            "berserk": {"w": False, "b": False},
            "by": self.imported_by,
        }
        if history is not None:
            response["twoBoardHistory"] = history
        return response

    @property
    def turn_player(self):
        # Bughouse has two boards; keep the existing compatibility behavior here
        # by deriving turn info from board A directly without touching game.board.
        return self.wplayer.username if self.boards["a"].color == WHITE else self.bplayer.username

    def game_json(self, player):
        color = "w" if self.wplayerA == player or self.wplayerB == player else "b"
        opp_rating, opp_player = (
            (self.bplayerA, self.black_rating_a)
            if self.wplayerA == player
            else (
                (self.wplayerA, self.white_rating_a)
                if self.bplayerA == player
                else (
                    (self.wplayerB, self.white_rating_b)
                    if self.bplayerB == player
                    else (self.bplayerB, self.black_rating_b)
                )
            )
        )
        opp_rating, prov = opp_rating.rating_prov
        return {
            "gameId": self.id,
            "title": opp_player.title,
            "name": opp_player.username,
            "rating": opp_rating,
            "prov": prov,
            "color": color,
            "result": self.result,
        }
