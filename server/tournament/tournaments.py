from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol, cast

import aiohttp_session
from aiohttp import web
from compress import C2R, R2C
from const import (
    ARENA,
    BYEGAME,
    CATEGORIES,
    MAX_CHAT_LINES,
    RR,
    SHIELD,
    STARTED,
    SWISS,
    T_ABORTED,
    T_ARCHIVED,
    T_CREATED,
    T_FINISHED,
    T_STARTED,
    TEST_PREFIX,
    TRANSLATED_FREQUENCY_NAMES,
    TRANSLATED_PAIRING_SYSTEM_NAMES,
    VARIANTEND,
)
from newid import id8, new_id

from tournament.arena import ArenaTournament

if TYPE_CHECKING:
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
from catalogued_variants import (
    CATALOGUED_VARIANT_COLLECTION,
    is_public_catalogued_variant,
    register_historical_catalogued_variant_doc,
)
from pychess_global_app_state_utils import get_app_state
from rated_start import can_rate_start, can_rate_variant
from settings import DEV
from team import PERMISSION_TOURNAMENTS, get_team, has_team_permission
from typing_defs import (
    TournamentArrangementDoc,
    TournamentCreateData,
    TournamentDoc,
    TournamentPairingDoc,
    TournamentPlayerDoc,
    TournamentPoint,
)
from user import User
from utils import load_game
from variants import ALL_VARIANTS, C2V, VARIANTS, get_server_variant, is_catalogued_variant
from ws_types import ChatLine

from tournament.auto_play_tournament import (
    AUTO_PLAY_TOURNAMENT_ID,
    ArenaTestTournament,
    RRTestTournament,
    SwissTestTournament,
)
from tournament.rr import RRTournament
from tournament.swiss import SwissTournament
from tournament.swiss.tournament_ops import _persist_late_entry_round_history
from tournament.tournament import (
    AUTO_ROUND_INTERVAL,
    MANUAL_ROUND_INTERVAL,
    RR_DEFAULT_MAX_PLAYERS,
    RR_MAX_SUPPORTED_PLAYERS,
    SCORE_SHIFT,
    SWISS_MAX_PLAYERS,
    ByeGame,
    GameData,
    PlayerData,
    Tournament,
    upsert_tournament_to_db,
)

log = logging.getLogger(__name__)

WinnerEntry = tuple[str, str, str, str]
ScheduledTournamentEntry = tuple[str, str, bool, datetime, int, str]
TournamentTables = tuple[list[Tournament], list[Tournament], list[Tournament]]


async def _resolve_tournament_variant(
    app_state: PychessGlobalAppState, tournament_doc: TournamentDoc
) -> str | None:
    """Resolve a persisted tournament variant without trusting the live catalogue forever.

    New catalogued tournaments persist an inline INI snapshot.  Older archived
    tournaments can fall back to the archived catalogue document.  A legacy orphan
    whose variant was deleted before snapshots existed is skipped instead of making
    tournament list/startup requests fail.
    """

    code = str(tournament_doc.get("v") or "")
    variant = C2V.get(code)
    if variant is not None:
        return variant

    historical_doc: Mapping[str, Any] | None = (
        tournament_doc if tournament_doc.get("vini") else None
    )
    if historical_doc is None and app_state.db is not None:
        historical_doc = await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": code})

    if historical_doc is not None:
        try:
            register_historical_catalogued_variant_doc(historical_doc)
        except Exception:
            log.exception(
                "Failed to restore catalogued variant %s for tournament %s",
                code,
                tournament_doc.get("_id", ""),
            )
        else:
            variant = C2V.get(code)
            if variant is not None:
                return variant

    log.warning(
        "Skipping tournament %s with unavailable variant %s",
        tournament_doc.get("_id", ""),
        code,
    )
    return None


COMMUNITY_ARENA_MAX_CREATIONS_PER_24H = 1
COMMUNITY_ARENA_CREATION_WINDOW = timedelta(days=1)
FIXED_ROUND_MAX_CREATIONS_PER_24H = 5
FIXED_ROUND_CREATION_WINDOW = timedelta(days=1)
COMMUNITY_ARENA_MAX_SCHEDULE_AHEAD = timedelta(days=1)
COMMUNITY_ARENA_SYSTEM_BUFFER = timedelta(minutes=15)
COMMUNITY_ARENA_MIN_MINUTES = 20
COMMUNITY_ARENA_MAX_MINUTES = 120
COMMUNITY_ARENA_CLOCK_TIMES: frozenset[float] = frozenset(
    (
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
        1.5,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
        7.0,
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
        40.0,
        50.0,
        60.0,
    )
)
COMMUNITY_ARENA_CLOCK_INCREMENTS: frozenset[int] = frozenset(
    (0, 1, 2, 3, 4, 5, 6, 7, 10, 15, 20, 25, 30, 40, 50, 60)
)
COMMUNITY_ARENA_WAIT_MINUTES: frozenset[int] = frozenset((1, 2, 3, 5, 10, 15, 20, 30, 45, 60))
SWISS_MIN_ROUNDS = 3
SWISS_MAX_ROUNDS = 15
SWISS_MAX_FORBIDDEN_PAIRING_LINES = 2048
SWISS_MAX_MANUAL_PAIRING_LINES = SWISS_MAX_PLAYERS

ROUND_INTERVAL_SECONDS: frozenset[int] = frozenset(
    (
        5,
        10,
        20,
        30,
        45,
        60,
        120,
        180,
        300,
        600,
        900,
        1200,
        1800,
        2700,
        3600,
        86400,
        172800,
        604800,
    )
)


class Translation(Protocol):
    def gettext(self, message: str) -> str: ...


def _align_player_games_with_points(player_data: PlayerData) -> None:
    if not player_data.points:
        return

    # Round-aware Swiss states should not be re-ordered by point-shape heuristics.
    if any(getattr(game, "round", None) is not None for game in player_data.games):
        return

    non_bye_games = [game for game in player_data.games if not isinstance(game, ByeGame)]
    bye_games = [game for game in player_data.games if isinstance(game, ByeGame)]

    rebuilt: list[Game | GameData | ByeGame] = []
    non_bye_index = 0
    bye_index = 0

    for point in player_data.points:
        if point == "-":
            if bye_index < len(bye_games):
                rebuilt.append(bye_games[bye_index])
                bye_index += 1
            else:
                rebuilt.append(ByeGame())
            continue

        if non_bye_index >= len(non_bye_games):
            break

        rebuilt.append(non_bye_games[non_bye_index])
        non_bye_index += 1

    while non_bye_index < len(non_bye_games):
        rebuilt.append(non_bye_games[non_bye_index])
        non_bye_index += 1

    while bye_index < len(bye_games):
        rebuilt.append(bye_games[bye_index])
        bye_index += 1

    player_data.games = rebuilt


def _fixed_round_entry_point_value(point: object, variant: str) -> int:
    if point == "-":
        return 7 if variant == "janggi" else 2
    if isinstance(point, (tuple, list)) and len(point) > 0 and isinstance(point[0], int):
        return point[0]
    return 0


def _swiss_unplayed_point_from_token(token: str, variant: str):
    if token == "U":
        return "-"
    if token == "H":
        if variant == "janggi":
            return (2, 0)
        return (1, 0)
    if token == "F":
        return (7, 0) if variant == "janggi" else (2, 0)
    return (0, 0)


def _nonempty_pairing_lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _validate_swiss_pairing_inputs(forbidden_pairings: str, manual_pairings: str) -> None:
    forbidden_lines = _nonempty_pairing_lines(forbidden_pairings)
    if len(forbidden_lines) > SWISS_MAX_FORBIDDEN_PAIRING_LINES:
        raise web.HTTPBadRequest(
            text=(
                "Swiss forbidden pairings are limited to "
                f"{SWISS_MAX_FORBIDDEN_PAIRING_LINES} lines."
            )
        )

    manual_lines = _nonempty_pairing_lines(manual_pairings)
    if len(manual_lines) > SWISS_MAX_MANUAL_PAIRING_LINES:
        raise web.HTTPBadRequest(
            text=f"Swiss manual pairings are limited to {SWISS_MAX_MANUAL_PAIRING_LINES} lines."
        )

    used_names: set[str] = set()
    for line_no, line in enumerate(manual_lines, start=1):
        parts = line.lower().split()
        if len(parts) != 2:
            raise web.HTTPBadRequest(text=f"Invalid Swiss manual pairing on line {line_no}.")

        left_name, right_name = parts
        if left_name == right_name:
            raise web.HTTPBadRequest(
                text=f"Invalid Swiss manual pairing on line {line_no}: a player cannot play themself."
            )

        names = (left_name,) if right_name == "1" else (left_name, right_name)
        duplicate_name = next((name for name in names if name in used_names), None)
        if duplicate_name is not None:
            raise web.HTTPBadRequest(
                text=(
                    f"Invalid Swiss manual pairing on line {line_no}: "
                    f"{duplicate_name} is paired more than once."
                )
            )
        used_names.update(names)


def _parse_round_interval(
    value: Any,
    *,
    system: int,
    default_value: int,
) -> int:
    if system == ARENA:
        return 0

    if value in (None, "", "auto"):
        return AUTO_ROUND_INTERVAL
    if value == "manual":
        return MANUAL_ROUND_INTERVAL

    try:
        interval = int(value)
    except (TypeError, ValueError):
        return default_value

    if interval in ROUND_INTERVAL_SECONDS:
        return interval
    return default_value


def _parse_rr_max_players(value: Any, *, default_value: int) -> int:
    try:
        rr_max_players = int(value)
    except (TypeError, ValueError):
        rr_max_players = default_value

    return max(3, min(RR_MAX_SUPPORTED_PLAYERS, rr_max_players))


def _infer_swiss_point_from_game(
    tournament: Tournament,
    game: Game | GameData | ByeGame,
    username: str,
):
    if isinstance(game, ByeGame):
        return _swiss_unplayed_point_from_token(getattr(game, "token", "U"), tournament.variant)

    result = game.result
    if result not in ("1-0", "0-1", "1/2-1/2"):
        return None

    if result == "1/2-1/2":
        return (0 if tournament.variant == "janggi" else 1, 1)

    is_white = game.wplayer.username == username
    won = (result == "1-0" and is_white) or (result == "0-1" and not is_white)

    if tournament.variant == "janggi":
        if getattr(game, "status", None) == VARIANTEND:
            return (4 if won else 2, 1)
        return (7 if won else 0, 1)

    return (2 if won else 0, 1)


def _pairing_round_from_game_doc(
    tournament: Tournament,
    game_doc: Mapping[str, Any],
) -> int | None:
    round_no = game_doc.get("rn")
    if isinstance(round_no, int):
        return round_no
    if tournament.system == ARENA:
        return None
    if tournament.pairing_in_progress_round is not None:
        return tournament.pairing_in_progress_round
    if tournament.current_round > 0:
        return tournament.current_round
    return 1


async def _repair_missing_pairing_docs_from_games(tournament: Tournament) -> None:
    game_table = tournament.app_state.db.game
    pairing_table = tournament.app_state.db.tournament_pairing

    pairing_ids = {
        doc["_id"]
        async for doc in pairing_table.find({"tid": tournament.id}, projection={"_id": 1})
    }
    repaired_ids: list[str] = []

    async for game_doc in game_table.find({"tid": tournament.id}):
        game_id = game_doc["_id"]
        if game_id in pairing_ids:
            continue

        usernames = game_doc.get("us", [])
        if len(usernames) != 2:
            continue

        result_code = game_doc.get("r", R2C["*"])
        result = C2R.get(result_code)
        if result is None:
            continue

        white_rating_doc = game_doc.get("p0", {})
        black_rating_doc = game_doc.get("p1", {})
        pairing_game = GameData(
            game_id,
            usernames[0],
            str(white_rating_doc.get("e", "1500?")),
            usernames[1],
            str(black_rating_doc.get("e", "1500?")),
            result,
            game_doc["d"],
            bool(game_doc.get("wb", False)),
            bool(game_doc.get("bb", False)),
            status=game_doc["s"],
            ply=game_doc.get("p", len(game_doc.get("m", []))),
            round_no=_pairing_round_from_game_doc(tournament, game_doc),
            wrdiff=white_rating_doc.get("d", 0),
            brdiff=black_rating_doc.get("d", 0),
        )
        await tournament.db_update_pairing(pairing_game)
        repaired_ids.append(game_id)

    if repaired_ids:
        log.warning(
            "Recovered %s missing tournament pairing docs from db.game in %s: %s",
            len(repaired_ids),
            tournament.id,
            repaired_ids,
        )


async def _repair_swiss_state_from_history(tournament: Tournament) -> None:
    repaired_users: list[str] = []

    for player_data in tournament.players.values():
        repaired = False
        username = player_data.username

        initial_points = list(player_data.points)
        initial_games = list(player_data.games)

        _align_player_games_with_points(player_data)

        while len(player_data.points) < len(player_data.games):
            game = player_data.games[len(player_data.points)]
            inferred = _infer_swiss_point_from_game(tournament, game, username)
            if inferred is None:
                log.warning(
                    "Swiss load repair could not infer point for %s in %s at round index %s",
                    username,
                    tournament.id,
                    len(player_data.points),
                )
                break
            player_data.points.append(inferred)
            repaired = True

        while len(player_data.points) > len(player_data.games):
            next_point = player_data.points[len(player_data.games)]
            if next_point != "-":
                log.warning(
                    "Swiss load repair found extra non-bye point without game for %s in %s",
                    username,
                    tournament.id,
                )
                break
            player_data.games.append(ByeGame())
            repaired = True

        _align_player_games_with_points(player_data)

        if player_data.points != initial_points or player_data.games != initial_games:
            repaired = True

        if not repaired:
            continue

        total_points = sum(
            _fixed_round_entry_point_value(point, tournament.variant)
            for point in player_data.points
        )
        full_score = tournament.compose_leaderboard_score(total_points, player_data)
        if tournament.leaderboard_player_by_username(username) is not None:
            tournament.set_leaderboard_score_by_username(username, full_score)
        repaired_users.append(username)

    if not repaired_users:
        return

    log.warning(
        "Swiss load repair adjusted player state from pairing history in %s: %s",
        tournament.id,
        sorted(repaired_users),
    )

    for username in repaired_users:
        await tournament.db_update_player(username, "GAME_END")


async def _recover_incomplete_fixed_round_pairing_round(
    tournament: Tournament,
    stored_round: int | None,
) -> int | None:
    round_no = tournament.pairing_in_progress_round
    if round_no is None:
        return stored_round

    if round_no <= 0:
        tournament.pairing_in_progress_round = None
        return stored_round

    system_name = "Swiss" if tournament.system == SWISS else "RR"
    expected_usernames = {
        player_data.username
        for player_data in tournament.players.values()
        if not player_data.withdrawn and player_data.joined_round <= round_no
    }
    accounted_usernames = {
        player_data.username
        for player_data in tournament.players.values()
        if any(getattr(game, "round", None) == round_no for game in player_data.games)
    }
    round_is_complete = expected_usernames.issubset(accounted_usernames)

    if round_is_complete:
        tournament.current_round = max(tournament.current_round, round_no)
        await tournament.save_current_round()
        log.warning(
            "Recovered %s round %s in %s from persisted pairing state after interrupted commit",
            system_name,
            round_no,
            tournament.id,
        )
        return tournament.current_round

    pairing_table = tournament.app_state.db.tournament_pairing
    pairing_docs = await pairing_table.find({"tid": tournament.id, "rn": round_no}).to_list(
        length=None
    )
    game_ids = [doc["_id"] for doc in pairing_docs if doc.get("s") != BYEGAME]

    if game_ids:
        await tournament.app_state.db.game.delete_many({"_id": {"$in": game_ids}})
    else:
        await tournament.app_state.db.game.delete_many({"tid": tournament.id, "r": R2C["*"]})
    if pairing_docs:
        await pairing_table.delete_many({"tid": tournament.id, "rn": round_no})

    rolled_back_users: list[str] = []
    rolled_back_game_ids = {
        game.id for game in tournament.ongoing_games if getattr(game, "round", None) == round_no
    }
    for player_data in tournament.players.values():
        _align_player_games_with_points(player_data)

        rebuilt_games: list[Game | GameData | ByeGame] = []
        rebuilt_points: list[TournamentPoint] = []
        changed = False

        for index, game in enumerate(player_data.games):
            if getattr(game, "round", None) == round_no:
                changed = True
                continue
            rebuilt_games.append(game)
            if index < len(player_data.points):
                rebuilt_points.append(player_data.points[index])

        if not changed:
            continue

        player_data.games = rebuilt_games
        player_data.points = rebuilt_points
        player_data.free = True
        rolled_back_users.append(player_data.username)

    tournament.ongoing_games = {
        game for game in tournament.ongoing_games if getattr(game, "round", None) != round_no
    }
    for game_id in rolled_back_game_ids:
        tournament.app_state.games.pop(game_id, None)

    for player_data in tournament.players.values():
        total_points = sum(
            _fixed_round_entry_point_value(point, tournament.variant)
            for point in player_data.points
        )
        if tournament.leaderboard_player_by_username(player_data.username) is not None:
            tournament.set_leaderboard_score_by_username(
                player_data.username,
                tournament.compose_leaderboard_score(total_points, player_data),
            )

    if tournament.system == SWISS:
        tournament.recalculate_berger_tiebreak()
    tournament.current_round = max(0, round_no - 1)
    tournament.pairing_in_progress_round = None
    tournament.manual_pairings_in_progress = None
    await tournament.app_state.db.tournament.update_one(
        {"_id": tournament.id},
        {
            "$set": {"cr": tournament.current_round},
            "$unset": {
                "pairingInProgressRound": "",
                "manualPairingsInProgress": "",
            },
        },
    )
    for username in rolled_back_users:
        await tournament.db_update_player(username, "GAME_END")

    log.warning(
        "Rolled back incomplete %s round %s in %s after interrupted pairing commit",
        system_name,
        round_no,
        tournament.id,
    )
    return tournament.current_round


def _community_arena_start_time(
    *,
    tournament: Tournament | None,
    start_date: datetime | None,
    wait_minutes: int,
    now: datetime,
) -> datetime:
    if start_date is not None:
        return start_date
    if tournament is not None:
        return tournament.created_at + timedelta(minutes=wait_minutes)
    return now + timedelta(minutes=wait_minutes)


def _validate_user_arena_schedule(
    app_state: PychessGlobalAppState,
    username: str,
    *,
    team_id: str,
    tournament: Tournament | None,
    start_date: datetime | None,
    wait_minutes: int,
    minutes: int,
    now: datetime,
) -> None:
    if minutes < COMMUNITY_ARENA_MIN_MINUTES or minutes > COMMUNITY_ARENA_MAX_MINUTES:
        raise web.HTTPBadRequest(
            text=(
                f"User-created Arenas must last between {COMMUNITY_ARENA_MIN_MINUTES} and "
                f"{COMMUNITY_ARENA_MAX_MINUTES} minutes."
            )
        )

    if wait_minutes not in COMMUNITY_ARENA_WAIT_MINUTES:
        raise web.HTTPBadRequest(text="Invalid Arena start delay.")

    # Team Arenas keep the normal Arena validity and daily creation limits, but they are
    # intentionally exempt from public Community Arena scheduling protections. Team leaders
    # need to be able to announce events days or weeks in advance without blocking themselves
    # from creating another Arena or having to avoid the site-wide system tournament schedule.
    if team_id:
        return

    proposed_start = _community_arena_start_time(
        tournament=tournament,
        start_date=start_date,
        wait_minutes=wait_minutes,
        now=now,
    )
    if proposed_start > now + COMMUNITY_ARENA_MAX_SCHEDULE_AHEAD:
        raise web.HTTPBadRequest(
            text="Community Arenas can be scheduled at most 24 hours in advance."
        )

    proposed_end = proposed_start + timedelta(minutes=minutes)

    if tournament is None:
        for existing in app_state.tournaments.values():
            if (
                existing.created_by == username
                and existing.system == ARENA
                and not existing.frequency
                and existing.status in (T_CREATED, T_STARTED)
            ):
                raise web.HTTPTooManyRequests(
                    text="You already have an active or scheduled Arena tournament."
                )

    for protected in app_state.tournaments.values():
        if protected is tournament:
            continue
        if protected.created_by != "PyChess" or protected.status not in (T_CREATED, T_STARTED):
            continue
        if (
            proposed_start < protected.ends_at + COMMUNITY_ARENA_SYSTEM_BUFFER
            and proposed_end > protected.starts_at - COMMUNITY_ARENA_SYSTEM_BUFFER
        ):
            raise web.HTTPBadRequest(
                text=(
                    "Community Arena schedule conflicts with the protected system tournament "
                    f'"{protected.name}". Please leave at least 15 minutes before and after '
                    "system tournaments."
                )
            )


async def _claim_community_arena_creation_slot(
    app_state: PychessGlobalAppState, username: str, now: datetime
) -> str | None:
    if app_state.db is None:
        return None
    if COMMUNITY_ARENA_MAX_CREATIONS_PER_24H < 1:
        raise RuntimeError("COMMUNITY_ARENA_MAX_CREATIONS_PER_24H must be at least 1")

    cutoff = now - COMMUNITY_ARENA_CREATION_WINDOW
    claim_id = id8()
    while True:
        account = await app_state.db.user.find_one(
            {"_id": username},
            {"arenaCreationHistory": 1, "lastArenaCreatedAt": 1},
        )
        if account is None:
            raise web.HTTPForbidden(text="Tournament creation requires a registered account.")

        raw_history = account.get("arenaCreationHistory")
        history_exists = "arenaCreationHistory" in account
        if isinstance(raw_history, list):
            current_history = list(raw_history)
        elif history_exists:
            current_history = []
        else:
            legacy_created_at = account.get("lastArenaCreatedAt")
            current_history = (
                [{"at": legacy_created_at, "id": "legacy"}]
                if isinstance(legacy_created_at, datetime)
                else []
            )

        recent_history = [
            entry
            for entry in current_history
            if isinstance(entry, dict)
            and isinstance(entry.get("at"), datetime)
            and entry["at"] > cutoff
        ]
        if len(recent_history) >= COMMUNITY_ARENA_MAX_CREATIONS_PER_24H:
            raise web.HTTPTooManyRequests(
                text=(
                    "Community Arena creation is limited to "
                    f"{COMMUNITY_ARENA_MAX_CREATIONS_PER_24H} tournament"
                    f"{'s' if COMMUNITY_ARENA_MAX_CREATIONS_PER_24H != 1 else ''} "
                    "every 24 hours."
                )
            )

        new_history = [
            *recent_history,
            {"at": now, "id": claim_id},
        ][-COMMUNITY_ARENA_MAX_CREATIONS_PER_24H:]

        if history_exists:
            quota_filter: dict[str, object] = {
                "_id": username,
                "arenaCreationHistory": raw_history,
            }
        else:
            quota_filter = {"_id": username, "arenaCreationHistory": {"$exists": False}}
            legacy_created_at = account.get("lastArenaCreatedAt")
            quota_filter["lastArenaCreatedAt"] = (
                legacy_created_at if isinstance(legacy_created_at, datetime) else {"$exists": False}
            )

        result = await app_state.db.user.update_one(
            quota_filter,
            {
                "$set": {"arenaCreationHistory": new_history},
                "$unset": {"lastArenaCreatedAt": ""},
            },
        )
        if result.modified_count == 1:
            return claim_id
        # Another request changed the quota history between our read and write. Re-read it
        # and either claim the next available slot or reject the now-full rolling window.


async def _release_community_arena_creation_slot(
    app_state: PychessGlobalAppState, username: str, claim_id: str | None
) -> None:
    if app_state.db is None or claim_id is None:
        return
    await app_state.db.user.update_one(
        {"_id": username},
        {"$pull": {"arenaCreationHistory": {"id": claim_id}}},
    )


async def _claim_fixed_round_creation_slot(
    app_state: PychessGlobalAppState, username: str, now: datetime
) -> str | None:
    if app_state.db is None:
        return None
    if FIXED_ROUND_MAX_CREATIONS_PER_24H < 1:
        raise RuntimeError("FIXED_ROUND_MAX_CREATIONS_PER_24H must be at least 1")

    cutoff = now - FIXED_ROUND_CREATION_WINDOW
    claim_id = id8()
    while True:
        account = await app_state.db.user.find_one(
            {"_id": username},
            {"fixedRoundCreationHistory": 1},
        )
        if account is None:
            raise web.HTTPForbidden(text="Tournament creation requires a registered account.")

        raw_history = account.get("fixedRoundCreationHistory")
        history_exists = "fixedRoundCreationHistory" in account
        current_history = list(raw_history) if isinstance(raw_history, list) else []
        recent_history = [
            entry
            for entry in current_history
            if isinstance(entry, dict)
            and isinstance(entry.get("at"), datetime)
            and entry["at"] > cutoff
        ]
        if len(recent_history) >= FIXED_ROUND_MAX_CREATIONS_PER_24H:
            raise web.HTTPTooManyRequests(
                text=(
                    "Team Round-Robin/Swiss tournament creation is limited to "
                    f"{FIXED_ROUND_MAX_CREATIONS_PER_24H} tournament"
                    f"{'s' if FIXED_ROUND_MAX_CREATIONS_PER_24H != 1 else ''} "
                    "every 24 hours per user."
                )
            )

        new_history = [
            *recent_history,
            {"at": now, "id": claim_id},
        ][-FIXED_ROUND_MAX_CREATIONS_PER_24H:]

        quota_filter: dict[str, object] = {"_id": username}
        quota_filter["fixedRoundCreationHistory"] = (
            raw_history if history_exists else {"$exists": False}
        )
        result = await app_state.db.user.update_one(
            quota_filter,
            {"$set": {"fixedRoundCreationHistory": new_history}},
        )
        if result.modified_count == 1:
            return claim_id
        # Another request changed the quota history between our read and write. Re-read it
        # and either claim the next available slot or reject the now-full rolling window.


async def _release_fixed_round_creation_slot(
    app_state: PychessGlobalAppState, username: str, claim_id: str | None
) -> None:
    if app_state.db is None or claim_id is None:
        return
    await app_state.db.user.update_one(
        {"_id": username},
        {"$pull": {"fixedRoundCreationHistory": {"id": claim_id}}},
    )


async def creator_can_manage_tournament(
    app_state: PychessGlobalAppState,
    tournament: Tournament,
    username: str,
) -> bool:
    """Whether the original creator still has organizer rights for this tournament.

    Non-Team tournaments keep the historical creator-based policy. Team tournaments
    additionally require that the Team is still enabled and the creator still holds
    the Team tournament permission. Site-wide tournament-director overrides are kept
    outside this helper so HTTP and websocket callers can apply them explicitly.
    """

    if username != tournament.creator:
        return False
    if not tournament.team_id:
        return True
    if await get_team(app_state, tournament.team_id) is None:
        return False
    return await has_team_permission(
        app_state,
        tournament.team_id,
        username,
        PERMISSION_TOURNAMENTS,
    )


async def create_or_update_tournament(
    app_state: PychessGlobalAppState,
    username: str,
    form: Mapping[str, Any],
    tournament: Tournament | None = None,
    *,
    creator_is_director: bool = True,
    editor_is_admin: bool = False,
) -> None:
    """Manual tournament creation from /tournaments/new form input values"""

    variant = str(form.get("variant", ""))
    position = str(form.get("position", ""))
    variant960 = False if is_catalogued_variant(variant) else variant.endswith("960")
    variant_name = variant[:-3] if variant960 else variant
    if is_catalogued_variant(variant_name) and not is_public_catalogued_variant(
        app_state, variant_name
    ):
        raise web.HTTPBadRequest(
            text="Only public user-defined variants can be used in tournaments."
        )
    try:
        server_variant = get_server_variant(variant_name, variant960)
    except KeyError:
        raise web.HTTPBadRequest(text="Unknown tournament variant.") from None
    if server_variant.two_boards:
        raise web.HTTPBadRequest(text="Two-board variants are not supported in tournaments.")

    rated = (
        form.get("rated", "") == "1"
        and not is_catalogued_variant(variant_name)
        and can_rate_start(variant_name, position, variant960)
    )
    try:
        base = float(form["clockTime"])
        inc = int(form["clockIncrement"])
        bp = int(form["byoyomiPeriod"])
    except (KeyError, TypeError, ValueError):
        raise web.HTTPBadRequest(text="Invalid tournament time control.") from None
    if bp > 0 and not server_variant.byo:
        raise web.HTTPBadRequest(text="Byoyomi is not supported for this tournament variant.")
    frequency = tournament.frequency if tournament is not None else ""
    team_id = tournament.team_id if tournament is not None else str(form.get("teamId", "")).strip()

    if tournament is None:
        try:
            system = int(form.get("system", ARENA))
        except (TypeError, ValueError):
            system = ARENA
        if system not in (ARENA, RR, SWISS):
            system = ARENA
        if team_id:
            team = await get_team(app_state, team_id)
            if team is None:
                raise web.HTTPBadRequest(text="Tournament team not found.")
            if not await has_team_permission(app_state, team_id, username, PERMISSION_TOURNAMENTS):
                raise web.HTTPForbidden(
                    text=(
                        "You need the tournament permission in this team to create this tournament."
                    )
                )
        elif system in (RR, SWISS) and not (creator_is_director and DEV):
            raise web.HTTPBadRequest(
                text="Round-Robin and Swiss tournaments must belong to a team."
            )
    else:
        # Editing keeps existing pairing type to avoid mutating tournament class behavior.
        system = tournament.system
        if (
            team_id
            and not editor_is_admin
            and not await creator_can_manage_tournament(app_state, tournament, username)
        ):
            raise web.HTTPForbidden(
                text=("You need the tournament permission in this team to manage this tournament.")
            )

    raw_rounds = form.get("rounds", 0)
    try:
        rounds = int(raw_rounds)
    except (TypeError, ValueError):
        if system == SWISS:
            raise web.HTTPBadRequest(text="Invalid Swiss round count.") from None
        rounds = 0
    if system == ARENA:
        rounds = 0
    elif system == RR:
        if tournament is not None and tournament.status != T_CREATED:
            rounds = tournament.rounds
        else:
            rounds = 0
    else:
        if not SWISS_MIN_ROUNDS <= rounds <= SWISS_MAX_ROUNDS:
            raise web.HTTPBadRequest(
                text=f"Swiss tournaments must have {SWISS_MIN_ROUNDS} to {SWISS_MAX_ROUNDS} rounds."
            )
        if (
            tournament is not None
            and tournament.status != T_CREATED
            and rounds < tournament.current_round
        ):
            raise web.HTTPBadRequest(
                text=(
                    "Swiss round count cannot be lower than the current round "
                    f"({tournament.current_round})."
                )
            )

    default_rr_max_players = (
        tournament.rr_join_limit() if tournament is not None else RR_DEFAULT_MAX_PLAYERS
    )
    rr_max_players = _parse_rr_max_players(
        form.get("rrMaxPlayers"),
        default_value=default_rr_max_players,
    )
    rr_requires_approval = form.get("rrRequiresApproval", "") == "1"
    rr_joining_closed = (
        bool(getattr(tournament, "rr_joining_closed", False)) if tournament else False
    )
    if system != RR:
        rr_max_players = 0
        rr_requires_approval = False
        rr_joining_closed = False

    default_round_interval = (
        AUTO_ROUND_INTERVAL if tournament is None else getattr(tournament, "round_interval", 0)
    )
    round_interval = _parse_round_interval(
        form.get("roundInterval"),
        system=system,
        default_value=default_round_interval,
    )

    try:
        entry_min_rating = int(form.get("entryMinRating", 0) or 0)
    except (TypeError, ValueError):
        entry_min_rating = 0
    try:
        entry_max_rating = int(form.get("entryMaxRating", 0) or 0)
    except (TypeError, ValueError):
        entry_max_rating = 0
    try:
        entry_min_rated_games = int(form.get("entryMinRatedGames", 0) or 0)
    except (TypeError, ValueError):
        entry_min_rated_games = 0
    if not can_rate_variant(variant_name, variant960):
        entry_min_rating = 0
        entry_max_rating = 0
        entry_min_rated_games = 0
    try:
        entry_min_account_age_days = int(form.get("entryMinAccountAgeDays", 0) or 0)
    except (TypeError, ValueError):
        entry_min_account_age_days = 0
    forbidden_pairings = (form.get("forbiddenPairings", "") or "").replace("\r\n", "\n").strip()
    manual_pairings = (form.get("manualPairings", "") or "").replace("\r\n", "\n").strip()

    if system != SWISS:
        forbidden_pairings = ""
        manual_pairings = ""
    else:
        _validate_swiss_pairing_inputs(forbidden_pairings, manual_pairings)

    if entry_max_rating > 0 and entry_min_rating > entry_max_rating:
        entry_min_rating, entry_max_rating = entry_max_rating, entry_min_rating

    if system != ARENA:
        frequency = ""

    start_date: datetime | None
    raw_start_date = form.get("startDate", "")
    try:
        if raw_start_date:
            start_date = datetime.fromisoformat(str(raw_start_date).rstrip("Z")).replace(tzinfo=UTC)
        else:
            start_date = None
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid tournament start date.") from None

    end_date: datetime | None
    try:
        if system == RR and form.get("endDate"):
            end_date = datetime.fromisoformat(str(form["endDate"]).rstrip("Z")).replace(tzinfo=UTC)
        else:
            end_date = None
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid tournament end date.") from None

    now = datetime.now(UTC)
    if start_date is not None and start_date <= now:
        raise web.HTTPBadRequest(text="Tournament start date must be in the future.")

    try:
        minutes = int(form["minutes"])
        wait_minutes = int(form["waitMinutes"])
    except (KeyError, TypeError, ValueError):
        raise web.HTTPBadRequest(text="Invalid tournament duration or start delay.") from None
    effective_start_date = start_date
    if end_date is not None:
        if effective_start_date is None:
            effective_start_date = now + timedelta(minutes=wait_minutes)
            start_date = effective_start_date
        if end_date <= effective_start_date:
            raise web.HTTPBadRequest(text="Tournament end date must be after the start date.")
        delta_minutes = int(max(1, (end_date - effective_start_date).total_seconds() // 60))
        if (
            end_date > effective_start_date
            and (end_date - effective_start_date).total_seconds() % 60
        ):
            delta_minutes += 1
        minutes = max(1, delta_minutes)

    submitted_name = str(form.get("name", "")).strip()
    name = submitted_name
    # Create meaningful tournament name in case we forget to change it :)
    if name == "":
        name = server_variant.display_name.title()

    description = str(form.get("description", ""))
    password = str(form.get("password", ""))

    if not creator_is_director and not editor_is_admin:
        if base not in COMMUNITY_ARENA_CLOCK_TIMES or inc not in COMMUNITY_ARENA_CLOCK_INCREMENTS:
            raise web.HTTPBadRequest(text="Invalid tournament time control.")
        if bp not in (0, 1, 2, 3) or (base <= 0 and inc <= 0):
            raise web.HTTPBadRequest(text="Invalid tournament time control.")
        if len(submitted_name) > 30 or (submitted_name and len(submitted_name) < 2):
            raise web.HTTPBadRequest(text="Tournament name must be between 2 and 30 characters.")
        if len(description) > 1000:
            raise web.HTTPBadRequest(text="Tournament description is limited to 1000 characters.")
        if len(password) > 30:
            raise web.HTTPBadRequest(text="Tournament password is limited to 30 characters.")
        if len(position) > 2048:
            raise web.HTTPBadRequest(text="Tournament starting position is too long.")
        if tournament is not None and (
            tournament.frequency
            or tournament.status != T_CREATED
            or (tournament.system in (RR, SWISS) and not tournament.team_id)
        ):
            raise web.HTTPForbidden(text="This tournament cannot be edited by its creator.")
        if system == ARENA:
            _validate_user_arena_schedule(
                app_state,
                username,
                team_id=team_id,
                tournament=tournament,
                start_date=start_date,
                wait_minutes=wait_minutes,
                minutes=minutes,
                now=now,
            )

    if frequency == SHIELD:
        name = "%s Shield Arena" % server_variant.display_name.title()

    data: TournamentCreateData = {
        "name": name,
        "password": password,
        "createdBy": username,
        "rated": rated,
        "variant": variant_name,
        "chess960": variant960,
        "base": base,
        "inc": inc,
        "bp": bp,
        "system": system,
        "beforeStart": wait_minutes,
        "startDate": start_date,
        "frequency": frequency,
        "minutes": minutes,
        "fen": position,
        "rounds": rounds,
        "rrMaxPlayers": rr_max_players,
        "rrRequiresApproval": rr_requires_approval,
        "rrJoiningClosed": rr_joining_closed,
        "roundInterval": round_interval,
        "entryMinRating": entry_min_rating,
        "entryMaxRating": entry_max_rating,
        "entryMinRatedGames": entry_min_rated_games,
        "entryMinAccountAgeDays": entry_min_account_age_days,
        "forbiddenPairings": forbidden_pairings,
        "manualPairings": manual_pairings,
        "teamId": team_id,
        "description": description,
    }
    if tournament is None:
        if creator_is_director:
            tournament = await new_tournament(app_state, data)
        elif system == ARENA:
            claim_id = await _claim_community_arena_creation_slot(app_state, username, now)
            try:
                tournament = await new_tournament(app_state, data)
            except Exception:
                await _release_community_arena_creation_slot(app_state, username, claim_id)
                raise
        else:
            claim_id = await _claim_fixed_round_creation_slot(app_state, username, now)
            try:
                tournament = await new_tournament(app_state, data)
            except Exception:
                await _release_fixed_round_creation_slot(app_state, username, claim_id)
                raise
    else:
        allow_started_position_edit = (
            tournament.status != T_CREATED
            and tournament.system in (ARENA, SWISS)
            and bool(tournament.fen)
        )
        if tournament.status != T_CREATED:
            if data["variant"] != tournament.variant or data["chess960"] != tournament.chess960:
                raise web.HTTPForbidden(
                    text="Variant cannot be changed after the tournament has started."
                )
            if (
                data["base"] != tournament.base
                or data["inc"] != tournament.inc
                or data["bp"] != tournament.byoyomi_period
            ):
                raise web.HTTPForbidden(
                    text="Time control cannot be changed after the tournament has started."
                )
            if data["startDate"] is not None and data["startDate"] != tournament.starts_at:
                raise web.HTTPForbidden(
                    text="Start date cannot be changed after the tournament has started."
                )
            if data["fen"] != tournament.fen and not allow_started_position_edit:
                raise web.HTTPForbidden(
                    text="Starting position cannot be changed after the tournament has started."
                )

        # We want to update some data of the tournament created by new_tournament() before.
        # upsert=True will do this update at the end of upsert_tournament_to_db()
        tournament.name = data["name"]
        tournament.password = data["password"]
        if tournament.status == T_CREATED:
            tournament.variant = data["variant"]
            tournament.chess960 = data["chess960"]
            tournament.base = data["base"]
            tournament.inc = data["inc"]
            tournament.bp = data["bp"]
        tournament.rated = data["rated"]
        if tournament.status == T_CREATED or tournament.system == SWISS:
            tournament.rounds = data["rounds"]
        tournament.rr_max_players = data["rrMaxPlayers"]
        tournament.rr_requires_approval = data["rrRequiresApproval"]
        tournament.rr_joining_closed = data["rrJoiningClosed"]
        tournament.round_interval = data["roundInterval"]
        tournament.entry_min_rating = data["entryMinRating"]
        tournament.entry_max_rating = data["entryMaxRating"]
        tournament.entry_min_rated_games = data["entryMinRatedGames"]
        tournament.entry_min_account_age_days = data["entryMinAccountAgeDays"]
        tournament.entry_titled_only = False
        tournament.forbidden_pairings = data["forbiddenPairings"]
        tournament.manual_pairings = data["manualPairings"]
        tournament.beforeStart = data["beforeStart"]
        if tournament.status == T_CREATED:
            previous_starts_at = tournament.starts_at
            tournament.starts_at = data["startDate"]  # type: ignore[assignment]
            if tournament.system == SWISS and tournament.starts_at != previous_starts_at:
                # Start reminders are tied to one scheduled start. A pre-start reschedule
                # should get fresh Discord/participant reminders at the new time.
                tournament.notify1 = False
                tournament.notify2 = False
        tournament.frequency = data["frequency"]
        tournament.minutes = data["minutes"]
        if tournament.status == T_CREATED or allow_started_position_edit:
            tournament.fen = data["fen"]
        tournament.description = data["description"]
        tournament.team_id = data.get("teamId", "")

        # re-calculate created_at, starts_at, ends_at etc.
        tournament.initialize()
        await upsert_tournament_to_db(tournament, app_state)

    await broadcast_tournament_creation(
        app_state, tournament, announce_to_discord=creator_is_director
    )


async def broadcast_tournament_creation(
    app_state: PychessGlobalAppState,
    tournament: Tournament,
    *,
    announce_to_discord: bool = True,
) -> None:
    await tournament.broadcast_spotlight()
    if announce_to_discord:
        await app_state.discord.send_to_discord("create_tournament", tournament.create_discord_msg)


async def new_tournament(
    app_state: PychessGlobalAppState, data: TournamentCreateData
) -> Tournament:
    if "tid" not in data:
        tid = await new_id(app_state.db.tournament)
    else:
        tid = data["tid"]

    tournament_class: type[Tournament]
    if data["system"] == ARENA:
        tournament_class = ArenaTournament
    elif data["system"] == SWISS:
        tournament_class = SwissTournament
    elif data["system"] == RR:
        tournament_class = RRTournament
    else:
        raise ValueError("Unknown tournament system")

    tournament = tournament_class(
        app_state,
        tid,
        variant=data["variant"],
        base=data["base"],
        inc=data["inc"],
        byoyomi_period=data.get("bp", 0),
        rated=data.get("rated", True),
        chess960=data.get("chess960", False),
        fen=data.get("fen", ""),
        rounds=data.get("rounds", 0),
        rr_max_players=data.get("rrMaxPlayers", 0),
        rr_requires_approval=data.get("rrRequiresApproval", False),
        rr_joining_closed=data.get("rrJoiningClosed", False),
        round_interval=data.get("roundInterval", 0),
        entry_min_rating=data.get("entryMinRating", 0),
        entry_max_rating=data.get("entryMaxRating", 0),
        entry_min_rated_games=data.get("entryMinRatedGames", 0),
        entry_min_account_age_days=data.get("entryMinAccountAgeDays", 0),
        entry_titled_only=False,
        forbidden_pairings=data.get("forbiddenPairings", ""),
        manual_pairings=data.get("manualPairings", ""),
        team_id=data.get("teamId", ""),
        created_by=data["createdBy"],
        before_start=data.get("beforeStart", 5),
        minutes=data.get("minutes", 45),
        starts_at=data.get("startDate"),
        frequency=data.get("frequency", ""),
        name=data["name"],
        password=data.get("password", ""),
        description=data.get("description", ""),
        created_at=data.get("createdAt"),
        status=data.get("status"),
        finish_reason=data.get("finishReason"),
        with_clock=data.get("with_clock", True),
    )

    app_state.tournaments[tid] = tournament
    app_state.tourneysockets[tid] = {}

    await upsert_tournament_to_db(tournament, app_state)

    return tournament


async def get_winners(
    app_state: PychessGlobalAppState,
    shield: bool,
    variant: str | None = None,
    variants: Iterable[str] | None = None,
) -> dict[str, list[WinnerEntry]]:
    raw_winners: dict[str, list[tuple[str, str, str]]] = {}
    if variants is None:
        if variant is None:
            variants = VARIANTS
            limit = 5
        else:
            variants = (variant,)
            limit = 50
    else:
        limit = 5

    winner_usernames: set[str] = set()
    for current_variant in variants:
        variant960 = current_variant.endswith("960")
        uci_variant = current_variant[:-3] if variant960 else current_variant

        v = get_server_variant(uci_variant, variant960)
        z = 1 if variant960 else 0

        filter_cond = {
            "v": v.code,
            "z": z,
            "status": {"$in": [T_FINISHED, T_ARCHIVED]},
            "nbGames": {"$gt": 0},
            "nbPlayers": {"$gte": 3},
        }
        if shield:
            filter_cond["fr"] = SHIELD

        winners: list[tuple[str, str, str]] = []
        cursor = app_state.db.tournament.find(filter_cond, sort=[("startsAt", -1)], limit=limit)
        async for doc in cursor:
            tournament_doc: TournamentDoc = doc
            if "winner" in tournament_doc:
                starts_at = tournament_doc["startsAt"]
                winner = tournament_doc["winner"]
                winners.append(
                    (
                        winner,
                        starts_at.strftime("%Y.%m.%d"),
                        tournament_doc["_id"],
                    )
                )
                winner_usernames.add(winner)

        raw_winners[current_variant] = winners

    titles = await app_state.public_users.get_titles(winner_usernames)
    return {
        variant: [
            (username, titles.get(username, ""), date, tid) for username, date, tid in winners
        ]
        for variant, winners in raw_winners.items()
    }


async def get_scheduled_tournaments(
    app_state: PychessGlobalAppState, nb_max: int = 30
) -> list[ScheduledTournamentEntry]:
    """Return max 30 already scheduled tournaments from mongodb"""
    cursor = app_state.db.tournament.find({"$or": [{"status": T_STARTED}, {"status": T_CREATED}]})
    cursor.sort("startsAt", -1)
    nb_tournament = 0
    tournaments: list[ScheduledTournamentEntry] = []

    async for doc in cursor:
        tournament_doc: TournamentDoc = doc
        if (
            tournament_doc["status"] in (T_CREATED, T_STARTED)
            and tournament_doc["createdBy"] == "PyChess"
            and tournament_doc.get("fr", "") != ""
        ):
            variant = await _resolve_tournament_variant(app_state, tournament_doc)
            if variant is None:
                continue
            nb_tournament += 1
            if nb_tournament > nb_max:
                break
            tournaments.append(
                (
                    tournament_doc["fr"],
                    variant,
                    bool(tournament_doc["z"]),
                    tournament_doc["startsAt"],
                    tournament_doc["minutes"],
                    tournament_doc["_id"],
                )
            )
    return tournaments


async def get_latest_tournaments(app_state: PychessGlobalAppState, lang: str) -> TournamentTables:
    started: list[Tournament] = []
    scheduled: list[Tournament] = []
    completed: list[Tournament] = []

    cursor = app_state.db.tournament.find()
    cursor.sort("startsAt", -1)
    nb_tournament = 0
    async for doc in cursor:
        tournament_doc: TournamentDoc = doc
        variant = await _resolve_tournament_variant(app_state, tournament_doc)
        if variant is None:
            continue
        nb_tournament += 1
        if nb_tournament > 31:
            break

        tid = tournament_doc["_id"]
        if tid in app_state.tournaments:
            tournament = app_state.tournaments[tid]
        else:
            tournament_class: type[Tournament]
            if tournament_doc["system"] == ARENA:
                tournament_class = ArenaTournament
            elif tournament_doc["system"] == SWISS:
                tournament_class = SwissTournament
            elif tournament_doc["system"] == RR:
                tournament_class = RRTournament
            elif TYPE_CHECKING:
                tournament_class = ArenaTournament

            tournament = tournament_class(
                app_state,
                tid,
                variant,
                base=tournament_doc["b"],
                inc=tournament_doc["i"],
                byoyomi_period=int(bool(tournament_doc.get("bp"))),
                rated=tournament_doc.get("y"),
                chess960=bool(tournament_doc.get("z")),
                fen=tournament_doc.get("f"),
                rounds=tournament_doc["rounds"],
                rr_max_players=tournament_doc.get(
                    "rrMaxPlayers",
                    min(RR_MAX_SUPPORTED_PLAYERS, max(3, tournament_doc["rounds"] + 1))
                    if tournament_doc["system"] == RR and tournament_doc["rounds"] > 0
                    else 0,
                ),
                rr_requires_approval=tournament_doc.get("rrRequiresApproval", False),
                rr_joining_closed=tournament_doc.get("rrJoiningClosed", False),
                round_interval=tournament_doc.get("ri", 0),
                entry_min_rating=tournament_doc.get("entryMinRating", 0),
                entry_max_rating=tournament_doc.get("entryMaxRating", 0),
                entry_min_rated_games=tournament_doc.get("entryMinRatedGames", 0),
                entry_min_account_age_days=tournament_doc.get("entryMinAccountAgeDays", 0),
                entry_titled_only=False,
                forbidden_pairings=tournament_doc.get("forbiddenPairings", ""),
                manual_pairings=tournament_doc.get("manualPairings", ""),
                team_id=tournament_doc.get("teamId", ""),
                created_by=tournament_doc["createdBy"],
                created_at=tournament_doc["createdAt"],
                minutes=tournament_doc["minutes"],
                starts_at=tournament_doc.get("startsAt"),
                name=tournament_doc["name"],
                description=tournament_doc.get("d", ""),
                frequency=tournament_doc.get("fr", ""),
                status=tournament_doc["status"],
                finish_reason=tournament_doc.get("finishReason"),
                with_clock=False,
            )
            tournament.nb_players = tournament_doc["nbPlayers"]
            tournament.rr_pending_players = set(tournament_doc.get("rrPendingPlayers", []))
            tournament.rr_denied_players = set(tournament_doc.get("rrDeniedPlayers", []))

        if tournament.frequency:
            try:
                tournament.translated_name = app_state.tourneynames[lang][
                    (
                        tournament.variant + ("960" if tournament.chess960 else ""),
                        tournament.frequency,
                        tournament.system,
                    )
                ]
            except KeyError:
                tournament.translated_name = tournament.name
        else:
            tournament.translated_name = tournament.name

        if tournament_doc["status"] == T_STARTED:
            started.append(tournament)
        elif tournament_doc["status"] < T_STARTED:
            scheduled.append(tournament)
        elif tournament_doc["status"] > T_STARTED:
            completed.append(tournament)

    scheduled = sorted(scheduled, key=lambda tournament: tournament.starts_at)

    return (started, scheduled, completed)


async def get_tournament_name(request: web.Request, tournament_id: str | None) -> str:
    """Return Tournament name from app cache or from database"""
    app_state = get_app_state(request.app)
    # todo: similar logic for determining lang already exists in index.py, except this "l" param. If it is specific for
    #       when called via the game_api move that there and re-use the rest about session+user from index.py
    #       finally change param of this function to get_tournament_name(app_state, tournament_id, lang)
    lang = request.rel_url.query.get("l")
    if lang is None:
        session = await aiohttp_session.get_session(request)
        session_user: str | None = session.get("user_name")
        if session_user is None:
            lang = "en"
        else:
            try:
                lang = app_state.users[session_user].lang
            except KeyError:
                lang = "en"
        if lang is None:
            lang = "en"

    if tournament_id in app_state.tourneynames[lang]:
        return app_state.tourneynames[lang][tournament_id]

    tournaments = app_state.tournaments
    name = ""

    if tournament_id in tournaments:
        tournament = tournaments[tournament_id]
        if tournament.frequency:
            try:
                name = app_state.tourneynames[lang][
                    (
                        tournament.variant + ("960" if tournament.chess960 else ""),
                        tournament.frequency,
                        tournament.system,
                    )
                ]
            except KeyError:
                name = tournament.name
        else:
            name = tournament.name
    else:
        doc = await app_state.db.tournament.find_one({"_id": tournament_id})
        if doc is not None:
            tournament_doc: TournamentDoc = doc
            frequency = tournament_doc.get("fr", "")
            variant = await _resolve_tournament_variant(app_state, tournament_doc)
            if frequency and variant is not None:
                chess960 = bool(tournament_doc.get("z"))
                variant_key = variant + ("960" if chess960 else "")
                try:
                    name = app_state.tourneynames[lang][
                        (variant_key, frequency, tournament_doc["system"])
                    ]
                except KeyError:
                    name = "%s %s %s" % (variant_key, frequency, tournament_doc["system"])
            else:
                name = tournament_doc["name"]
        app_state.tourneynames[lang][tournament_id] = name

    return name


async def load_tournament(
    app_state: PychessGlobalAppState,
    tournament_id: str,
    tournament_klass: type[Tournament] | None = None,
) -> Tournament | None:
    """Return Tournament object from app cache or from database"""
    if tournament_id in app_state.tournaments:
        tournament = app_state.tournaments[tournament_id]
        app_state.schedule_tournament_cache_removal(tournament)
        return tournament

    doc = await app_state.db.tournament.find_one({"_id": tournament_id})

    if doc is None:
        return None

    tournament_doc: TournamentDoc = doc
    variant = await _resolve_tournament_variant(app_state, tournament_doc)
    if variant is None:
        return None

    stored_round = tournament_doc.get("cr")
    pairing_in_progress_round = tournament_doc.get("pairingInProgressRound")
    manual_pairings_in_progress = tournament_doc.get("manualPairingsInProgress")

    auto_play = tournament_id == AUTO_PLAY_TOURNAMENT_ID
    tournament_class: type[Tournament]

    if tournament_doc["system"] == ARENA:
        tournament_class = ArenaTestTournament if auto_play else ArenaTournament
    elif tournament_doc["system"] == SWISS:
        tournament_class = SwissTestTournament if auto_play else SwissTournament
    elif tournament_doc["system"] == RR:
        tournament_class = RRTestTournament if auto_play else RRTournament
    elif tournament_klass is not None:
        tournament_class = tournament_klass
    elif TYPE_CHECKING:
        tournament_class = ArenaTournament

    tournament = tournament_class(
        app_state,
        tournament_doc["_id"],
        variant,
        base=tournament_doc["b"],
        inc=tournament_doc["i"],
        byoyomi_period=int(bool(tournament_doc.get("bp"))),
        rated=bool(tournament_doc.get("y")),
        chess960=bool(tournament_doc.get("z")),
        fen=tournament_doc.get("f"),
        rounds=tournament_doc["rounds"],
        rr_max_players=tournament_doc.get(
            "rrMaxPlayers",
            min(RR_MAX_SUPPORTED_PLAYERS, max(3, tournament_doc["rounds"] + 1))
            if tournament_doc["system"] == RR and tournament_doc["rounds"] > 0
            else 0,
        ),
        rr_requires_approval=tournament_doc.get("rrRequiresApproval", False),
        rr_joining_closed=tournament_doc.get("rrJoiningClosed", False),
        round_interval=tournament_doc.get("ri", 0),
        entry_min_rating=tournament_doc.get("entryMinRating", 0),
        entry_max_rating=tournament_doc.get("entryMaxRating", 0),
        entry_min_rated_games=tournament_doc.get("entryMinRatedGames", 0),
        entry_min_account_age_days=tournament_doc.get("entryMinAccountAgeDays", 0),
        entry_titled_only=False,
        forbidden_pairings=tournament_doc.get("forbiddenPairings", ""),
        manual_pairings=tournament_doc.get("manualPairings", ""),
        team_id=tournament_doc.get("teamId", ""),
        created_by=tournament_doc.get("createdBy", "PyChess"),
        created_at=tournament_doc["createdAt"],
        before_start=tournament_doc.get("beforeStart", 0),
        minutes=tournament_doc["minutes"],
        starts_at=tournament_doc.get("startsAt"),
        name=tournament_doc["name"],
        password=tournament_doc.get("password", ""),
        description=tournament_doc.get("d", ""),
        frequency=tournament_doc.get("fr", ""),
        status=tournament_doc["status"],
        finish_reason=tournament_doc.get("finishReason"),
        with_clock=False,
    )
    tournament.rr_pending_players = set(tournament_doc.get("rrPendingPlayers", []))
    tournament.rr_denied_players = set(tournament_doc.get("rrDeniedPlayers", []))
    if stored_round is not None:
        tournament.current_round = stored_round
    tournament.pairing_in_progress_round = pairing_in_progress_round
    tournament.manual_pairings_in_progress = manual_pairings_in_progress
    tournament.next_round_starts_at = tournament_doc.get("nextRoundStartsAt")

    app_state.tournaments[tournament_id] = tournament
    app_state.tourneysockets[tournament_id] = {}

    tournament.winner = tournament_doc.get("winner", "")

    player_table = app_state.db.tournament_player
    cursor = player_table.find({"tid": tournament_id})
    nb_players = 0

    def _rating_and_provisional(raw_rating: str | int) -> tuple[int, str]:
        if isinstance(raw_rating, int):
            return (raw_rating, "")

        rating_text = str(raw_rating)
        provisional = "?" if rating_text.endswith("?") else ""
        if provisional:
            rating_text = rating_text[:-1]

        try:
            return (int(rating_text), provisional)
        except ValueError:
            return (1500, provisional)

    async def ensure_pairing_participant(username: str, raw_rating: str | int) -> User:
        player = tournament.get_player_by_name(username)
        if player is not None:
            return player

        user = await app_state.users.get(username)
        if user.username != username:
            # Missing user doc (for example hard-deleted account): keep pairing replay usable.
            user = User(app_state, username=username, enabled=False)
            app_state.users[username] = user

        rating, provisional = _rating_and_provisional(raw_rating)
        player_data = PlayerData(user.title, user.username, rating, provisional)
        if tournament.status == T_STARTED:
            # A recovered participant in an already started tournament must not be auto-paired.
            player_data.paused = True
        tournament.register_player(user, player_data)

        if tournament.leaderboard_player_by_username(username) is None:
            tournament.leaderboard.setdefault(user, 0)
            tournament.nb_players += 1

        log.warning(
            "Recovered missing tournament participant %s in %s from pairing history",
            username,
            tournament_id,
        )
        return user

    if tournament.status == T_CREATED:
        try:
            cursor.sort("r", -1)
        except AttributeError:
            log.exception(
                "A unittest MagickMock cursor object"
            )  # todo: logic here shouldnt depend on unit tests

    async for doc in cursor:
        player_doc: TournamentPlayerDoc = doc
        uid = player_doc["uid"]
        if uid.startswith(TEST_PREFIX):
            user = User(app_state, username=uid, title="TEST")
            app_state.users[user.username] = user
        else:
            user = await app_state.users.get(uid)
            if user.username != uid:
                user = User(app_state, username=uid, enabled=False)
                app_state.users[uid] = user

        withdrawn = player_doc.get("wd", False)

        player_data = PlayerData(user.title, user.username, player_doc["r"], player_doc["pr"])
        tournament.register_player(user, player_data)
        player_data.id = player_doc["_id"]
        # Legacy persisted memberships predate deployment of joinedAt.
        player_data.joined_at = player_doc.get("joinedAt", tournament.starts_at)
        player_data.paused = player_doc["a"]
        player_data.withdrawn = withdrawn
        normalized_points: list[TournamentPoint] = []
        for point in player_doc["p"]:
            if isinstance(point, list) and len(point) == 2:
                normalized_points.append(cast(TournamentPoint, (point[0], point[1])))
            else:
                normalized_points.append(cast(TournamentPoint, point))
        player_data.points = normalized_points
        if tournament.system == SWISS:
            player_data.joined_round = player_doc["jr"]
        else:
            player_data.joined_round = player_doc.get("jr", 1)
        player_data.nb_win = player_doc["w"]
        player_data.nb_berserk = player_doc.get("b", 0)
        player_data.performance = player_doc["e"]
        player_data.berger = player_doc.get("g", 0)
        player_data.win_streak = player_doc["f"]

        if not withdrawn:
            tie_break = (
                player_data.performance if tournament.system in (ARENA, RR) else player_data.berger
            )
            tournament.leaderboard.update({user: SCORE_SHIFT * (player_doc["s"]) + tie_break})
            nb_players += 1

        if auto_play and tournament.status in (T_CREATED, T_STARTED):
            user.tournament_sockets[tournament.id] = {None}
            await tournament.join(user)

    tournament.nb_players = nb_players

    # Late Swiss joins persist their complete synthetic H/Z history in the player
    # document before the corresponding pairing rows.  Repair any rows lost to a
    # restart before replaying pairing history below.
    if tournament.system == SWISS:
        for player, player_data in tournament.players.items():
            if player_data.joined_round > 1:
                await _persist_late_entry_round_history(tournament, player)

    # tournament.print_leaderboard()

    if tournament.status != T_CREATED:
        # The recovery scan reads db.game by tournament id. Running it for not-yet-started
        # tournaments is wasted work and was dominating restart time when many future events
        # were loaded at boot.
        await _repair_missing_pairing_docs_from_games(tournament)

    pairing_table = app_state.db.tournament_pairing
    cursor = pairing_table.find({"tid": tournament_id})
    try:
        cursor.sort("d", 1)
    except AttributeError:
        log.exception(
            "A unittest MagickMock cursor object"
        )  # todo: logic here shouldn't depend on unit tests

    w_win, b_win, draw, berserk = 0, 0, 0, 0
    finished_pairings: list[Game | GameData] = []
    async for doc in cursor:
        pairing_doc: TournamentPairingDoc = doc
        if tournament.system == RR and pairing_doc.get("an", False):
            # RR annul/replay keeps the historical pairing document for auditability,
            # but an annulled result must not re-enter player score history on restart.
            continue
        pair_status = pairing_doc.get("s")
        pair_round = pairing_doc.get("rn")
        if tournament.system == SWISS and pair_round is None:
            raise RuntimeError(
                "Swiss pairing %s in %s is missing required round metadata"
                % (pairing_doc["_id"], tournament_id)
            )

        bye_token = pairing_doc.get("bt")
        _id = pairing_doc["_id"]
        wp, bp = pairing_doc["u"]
        wrating = pairing_doc["wr"]
        brating = pairing_doc["br"]
        date = pairing_doc["d"]

        if pair_status == BYEGAME:
            if tournament.system == SWISS:
                if bye_token is None:
                    raise RuntimeError(
                        "Swiss bye pairing %s in %s is missing required bye token"
                        % (_id, tournament_id)
                    )
            else:
                bye_token = "U"
            assert bye_token is not None
            bye_player = await ensure_pairing_participant(wp, wrating)
            bye_player_data = tournament.player_data_by_name(bye_player.username)
            if bye_player_data is not None:
                bye_game = ByeGame(token=bye_token, round_no=pair_round)
                bye_game.date = date
                bye_player_data.games.append(bye_game)
            continue

        res = pairing_doc["r"]
        result = C2R.get(res)
        if result is None:
            log.warning(
                "Skipping pairing %s in %s with unknown result code %s",
                _id,
                tournament_id,
                res,
            )
            continue
        # Skip aborted/unfinished games if tournament is over
        if result == "*" and tournament.status in (T_ABORTED, T_FINISHED, T_ARCHIVED):
            continue

        wberserk = pairing_doc.get("wb", False)
        bberserk = pairing_doc.get("bb", False)
        pair_ply = pairing_doc.get("p")

        game = None
        if tournament.status in (T_CREATED, T_STARTED) and result == "*":
            game = await load_game(app_state, _id)
            if game is None:
                continue
            if TYPE_CHECKING:
                assert isinstance(game, Game)
            game.round = pair_round  # type: ignore[attr-defined]
            if game.status > STARTED and game.result != "*":
                result = game.result
                res = R2C[result]
                wberserk = game.wberserk
                bberserk = game.bberserk
                wplayer = await ensure_pairing_participant(game.wplayer.username, game.wrating)
                bplayer = await ensure_pairing_participant(game.bplayer.username, game.brating)
                game = GameData(
                    game.id,
                    wplayer.username,
                    game.wrating,
                    bplayer.username,
                    game.brating,
                    result,
                    game.date,
                    wberserk,
                    bberserk,
                    wtitle=wplayer.title,
                    btitle=bplayer.title,
                    status=game.status,
                    ply=game.board.ply,
                    round_no=pair_round,
                    wrdiff=game.wrdiff,
                    brdiff=game.brdiff,
                )
                tournament.nb_games_finished += 1
                await tournament.db_update_pairing(game)
                finished_pairings.append(game)
            else:
                tournament.ongoing_games.add(game)
                tournament.update_game_ranks(game)
        if game is None:
            wplayer = await ensure_pairing_participant(wp, wrating)
            bplayer = await ensure_pairing_participant(bp, brating)
            game = GameData(
                _id,
                wplayer.username,
                wrating,
                bplayer.username,
                brating,
                result,
                date,
                wberserk,
                bberserk,
                wtitle=wplayer.title,
                btitle=bplayer.title,
                status=pair_status,
                ply=pair_ply,
                round_no=pair_round,
                wrdiff=pairing_doc.get("wrd", 0),
                brdiff=pairing_doc.get("brd", 0),
            )
            tournament.nb_games_finished += 1
            finished_pairings.append(game)

        if res == "a":
            w_win += 1
        elif res == "b":
            b_win += 1
        elif res == "c":
            draw += 1

        if wberserk:
            berserk += 1
        if bberserk:
            berserk += 1

        tournament.update_players(game)

    tournament.w_win = w_win
    tournament.b_win = b_win
    tournament.draw = draw
    tournament.nb_berserk = berserk

    recovered_score_ids: list[str] = []
    for pairing_game in finished_pairings:
        if not tournament.game_needs_score_recovery(pairing_game):
            continue
        await tournament.recover_game_update(pairing_game)
        recovered_score_ids.append(pairing_game.id)

    if recovered_score_ids:
        log.warning(
            "Recovered tournament player scoring from finished game history in %s: %s",
            tournament.id,
            recovered_score_ids,
        )

    for player_data in tournament.players.values():
        _align_player_games_with_points(player_data)

    if tournament.system == SWISS:
        stored_round = await _recover_incomplete_fixed_round_pairing_round(tournament, stored_round)
    if tournament.system == SWISS:
        await _repair_swiss_state_from_history(tournament)

    if tournament.system == SWISS:
        tournament.recalculate_berger_tiebreak()

    if stored_round is None and tournament.system == SWISS:
        stored_round = max(
            (len(player.games) for player in tournament.players.values()),
            default=0,
        )
        if stored_round == 0:
            stored_round = max(
                (len(player.points) for player in tournament.players.values()),
                default=0,
            )
        tournament.current_round = stored_round

    if tournament.system == RR:
        assert isinstance(tournament, RRTournament)
        arrangement_table = app_state.db.tournament_arrangement
        arrangement_cursor = arrangement_table.find({"tid": tournament_id})
        arrangement_docs: list[TournamentArrangementDoc] = await arrangement_cursor.to_list(
            length=None
        )
        await tournament.load_arrangements(arrangement_docs)

    cursor = app_state.db.tournament_chat.find(
        {"tid": tournament.id},
        projection={
            "_id": 0,
            "type": 1,
            "user": 1,
            "message": 1,
            "room": 1,
            "time": 1,
        },
    )
    docs: list[ChatLine] = await cursor.to_list(length=MAX_CHAT_LINES)
    tournament.tourneychat = docs

    if tournament.status == T_STARTED:
        has_points = any(player.points for player in tournament.players.values())
        if (
            tournament.nb_games_finished == 0
            and len(tournament.ongoing_games) == 0
            and not has_points
        ):
            tournament.first_pairing = True

    if tournament.status in (T_CREATED, T_STARTED):
        tournament.clock_task = asyncio.create_task(tournament.clock(), name="tournament-clock")

    app_state.schedule_tournament_cache_removal(tournament)
    return tournament


def translated_tournament_name(
    variant: str,
    frequency: str,
    system: int,
    lang_translation: Translation,
) -> str:
    # Weekly makruk category == SEAturday
    frequency = "S" if variant in CATEGORIES["makruk"] and frequency == "m" else frequency
    if frequency == "s":
        return "%s %s %s" % (
            lang_translation.gettext(ALL_VARIANTS[variant].translated_name),
            lang_translation.gettext(TRANSLATED_FREQUENCY_NAMES[frequency]),
            lang_translation.gettext(TRANSLATED_PAIRING_SYSTEM_NAMES[system]),
        )
    else:
        return "%s %s %s" % (
            lang_translation.gettext(TRANSLATED_FREQUENCY_NAMES[frequency]),
            lang_translation.gettext(ALL_VARIANTS[variant].translated_name),
            lang_translation.gettext(TRANSLATED_PAIRING_SYSTEM_NAMES[system]),
        )
