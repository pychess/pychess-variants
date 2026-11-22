from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NotRequired, TypedDict

from catalogued.variants import (
    can_create_catalogued_seek,
    catalogued_variant_games_are_persisted,
)
from const import CORR_SEEK_EXPIRE_WEEKS, INVITE_SEEK_EXPIRE, SYSTEM_USER
from json_utils import json_dumps
from misc import time_control_str
from newid import new_id
from rated_start import can_rate_start
from variants import catalogued_variant_random_start, get_server_variant, is_catalogued_variant

log = logging.getLogger(__name__)

MAX_USER_SEEKS = 10
ANON_RESTRICTED_SEEK_MESSAGE = (
    "Anonymous users cannot create or join correspondence or bughouse seeks."
)
SEEK_LIMIT_REACHED_MESSAGE = "You already have too many active seeks or challenges."
TWO_BOARD_TARGETED_SEEK_MESSAGE = (
    "Two-board variants are not available for invites or direct challenges."
)
DUPLICATE_DIRECT_CHALLENGE_MESSAGE = "You already have an open challenge for this player."
DECLINE_REASON_MESSAGES: dict[str, str] = {
    "generic": "I'm not accepting challenges at the moment.",
    "later": "This is not the right time for me, please ask again later.",
    "tooFast": "This time control is too fast for me, please challenge again with a slower game.",
    "tooSlow": "This time control is too slow for me, please challenge again with a faster game.",
    "timeControl": "I'm not accepting challenges with this time control.",
    "rated": "Please send me a rated challenge instead.",
    "casual": "Please send me a casual challenge instead.",
    "standard": "I'm not accepting variant challenges right now.",
    "variant": "I'm not willing to play this variant right now.",
    "noBot": "I'm not accepting challenges from bots.",
    "onlyBot": "I'm only accepting challenges from bots.",
}
SPECIAL_SEEK_TARGETS = {"", "BOT_challenge", "Invite-friend"}
DIRECT_CHALLENGE_CREATED = "created"
DIRECT_CHALLENGE_OFFLINE = "offline"
DIRECT_CHALLENGE_CANCELED = "canceled"
DIRECT_CHALLENGE_DECLINED = "declined"
DIRECT_CHALLENGE_ACCEPTED = "accepted"
ACTIVE_DIRECT_CHALLENGE_STATUSES = frozenset({DIRECT_CHALLENGE_CREATED, DIRECT_CHALLENGE_OFFLINE})
BOT_CHALLENGE_CREATED = "created"
BOT_CHALLENGE_DECLINED = "declined"
DIRECT_CHALLENGE_SHORT_EXPIRE = timedelta(hours=3)
DIRECT_CHALLENGE_BLOCKED_MESSAGE = "You cannot challenge this user."
ESTIMATE_MOVES = 40

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase
    from user import User


class SeekJson(TypedDict):
    _id: str
    seekID: str
    user: str
    bot: bool
    title: str
    variant: str
    chess960: bool | None
    target: str
    player1: str
    player2: str
    bugPlayer1: str
    bugPlayer2: str
    fen: str
    color: str
    rated: bool | int | None
    rrmin: int
    rrmax: int
    rating: int
    base: int | float
    inc: int
    byoyomi: int
    day: int | float
    gameId: str
    tournamentId: NotRequired[str]
    rrArrangementId: NotRequired[str]
    expireAt: NotRequired[str]
    challengeStatus: NotRequired[str]
    challengeDeclineReason: NotRequired[str]
    botChallengeStatus: NotRequired[str]
    botChallengeDeclineReason: NotRequired[str]


class SeekDbJson(TypedDict):
    _id: str
    seekID: str
    user: str
    bot: bool
    title: str
    variant: str
    chess960: bool | None
    target: str
    player1: str
    player2: str
    bugPlayer1: str
    bugPlayer2: str
    fen: str
    color: str
    rated: bool | int | None
    rrmin: int
    rrmax: int
    rating: int
    base: int | float
    inc: int
    byoyomi: int
    day: int | float
    gameId: str
    tournamentId: NotRequired[str]
    rrArrangementId: NotRequired[str]
    expireAt: NotRequired[datetime]
    challengeStatus: NotRequired[str]
    challengeDeclineReason: NotRequired[str]
    botChallengeStatus: NotRequired[str]
    botChallengeDeclineReason: NotRequired[str]


class SeekCreateData(TypedDict):
    variant: str
    fen: str
    color: str
    minutes: int
    increment: int
    byoyomiPeriod: int
    day: NotRequired[int]
    rated: NotRequired[bool | None]
    rrmin: NotRequired[int | None]
    rrmax: NotRequired[int | None]
    chess960: NotRequired[bool | None]
    target: NotRequired[str]
    reserveGameId: NotRequired[bool]
    tournamentId: NotRequired[str]
    rrArrangementId: NotRequired[str]


class Seek:
    def __init__(
        self,
        seek_id: str,
        creator: User,
        variant: str,
        fen: str = "",
        color: str = "r",
        base: float = 5,
        inc: int = 5,
        byoyomi_period: int = 0,
        day: float = 0,
        level: int = 6,
        rated: bool | int | None = False,
        rrmin: int | None = None,
        rrmax: int | None = None,
        chess960: bool | None = False,
        target: str = "",
        player1: User | None = None,
        player2: User | None = None,
        bugPlayer1: User | None = None,
        bugPlayer2: User | None = None,
        game_id: str | None = None,
        tournament_id: str | None = None,
        rr_arrangement_id: str | None = None,
        expire_at: datetime | str | None = None,
        challenge_status: str | None = None,
        challenge_decline_reason: str | None = None,
        bot_challenge_status: str | None = None,
        bot_challenge_decline_reason: str | None = None,
        reused_fen: bool = False,
        is_rematch: bool = False,
    ) -> None:
        self.id: str = seek_id
        self.creator: User = creator
        self.variant: str = variant
        self.color: str = color
        self.fen: str = "" if fen is None else fen
        if is_catalogued_variant(variant):
            rated = False
            chess960 = catalogued_variant_random_start(variant) and (not self.fen or bool(chess960))
        elif rated and not can_rate_start(
            variant,
            self.fen,
            bool(chess960),
            is_rematch=is_rematch,
        ):
            rated = False
        self.rated: bool | int | None = rated
        self.rating: int = creator.get_rating_value(variant, chess960)
        self.rrmin: int = rrmin if (rrmin is not None and rrmin != -1000) else -10000
        self.rrmax: int = rrmax if (rrmax is not None and rrmax != 1000) else 10000
        self.base: int | float = base
        self.inc: int = inc
        self.byoyomi_period: int = byoyomi_period
        server_variant = get_server_variant(variant, chess960)
        self.day: int | float = 0 if server_variant.two_boards else day
        self.level: int = 0 if creator.username == "Random-Mover" else level
        self.chess960: bool | None = chess960
        self.target: str = target if target is not None else ""
        self.player1: User | None = player1
        self.player2: User | None = player2
        self.bugPlayer1: User | None = bugPlayer1
        self.bugPlayer2: User | None = bugPlayer2

        self.game_id: str | None = game_id
        self.tournament_id: str | None = tournament_id
        self.rr_arrangement_id: str | None = rr_arrangement_id
        self.challenge_status: str | None = challenge_status if self.is_direct_challenge else None
        self.challenge_decline_reason: str | None = (
            challenge_decline_reason if self.is_direct_challenge else None
        )
        if self.is_direct_challenge and self.challenge_status is None:
            self.challenge_status = DIRECT_CHALLENGE_CREATED
        self.bot_challenge_status: str | None = (
            bot_challenge_status if self.is_bot_challenge else None
        )
        self.bot_challenge_decline_reason: str | None = (
            bot_challenge_decline_reason if self.is_bot_challenge else None
        )
        if self.is_bot_challenge and self.bot_challenge_status is None:
            self.bot_challenge_status = BOT_CHALLENGE_CREATED

        if expire_at is not None:
            parsed_expire_at = self._parse_expire_at(expire_at)
            if parsed_expire_at is None:
                log.warning("Invalid seek expireAt for %s: %r", seek_id, expire_at)
                self.expire_at = None
            else:
                self.expire_at = parsed_expire_at
        else:
            self.expire_at = self.default_expire_at()

        # True if this is 960 variant 1st, 3rd etc. rematch seek
        self.reused_fen: bool = reused_fen
        self.is_rematch: bool = is_rematch

        # Seek is pending when it is not corr, and user has no live lobby websocket
        self.pending: bool = False

    def __str__(self) -> str:
        fen = "fen='%s', " % self.fen if self.fen else ""
        game_id = "game_id='%s', " % self.game_id if self.game_id else ""
        return (
            "<Seek: id='%s', " % self.id
            + "user='%s', " % self.creator.username
            + "variant='%s', " % self.variant
            + "color='%s', " % self.color
            + fen
            + "rated='%s', " % self.rated
            + "level='%d', " % self.level
            + "base='%s', " % self.base
            + "inc='%s', " % self.inc
            + "chess960='%s', " % self.chess960
            + "rated='%s', " % self.rated
            + "rrmin='%d', " % self.rrmin
            + "rrmax='%d', " % self.rrmax
            + game_id
            + "pending='%d', " % self.pending
            + "target='%s', " % self.target
            + "challenge_status='%s', " % self.challenge_status
            + "day='%d'>" % self.day
        )

    def default_expire_at(self) -> datetime | None:
        if self.target == "Invite-friend":
            return datetime.now(UTC) + INVITE_SEEK_EXPIRE
        if (
            self.is_direct_challenge
            and self.challenge_status not in ACTIVE_DIRECT_CHALLENGE_STATUSES
        ):
            return datetime.now(UTC) + DIRECT_CHALLENGE_SHORT_EXPIRE
        if self.is_bot_challenge and self.bot_challenge_status != BOT_CHALLENGE_CREATED:
            return datetime.now(UTC) + DIRECT_CHALLENGE_SHORT_EXPIRE
        if self.day > 0:
            return datetime.now(UTC) + CORR_SEEK_EXPIRE_WEEKS
        if self.is_direct_challenge:
            return datetime.now(UTC) + INVITE_SEEK_EXPIRE
        if self.is_bot_challenge:
            return datetime.now(UTC) + INVITE_SEEK_EXPIRE
        return None

    def set_challenge_status(self, status: str) -> None:
        if not self.is_direct_challenge:
            return
        self.challenge_status = status
        if status != DIRECT_CHALLENGE_DECLINED:
            self.challenge_decline_reason = None
        self.expire_at = self.default_expire_at()

    def set_challenge_decline_reason(self, reason: str | None) -> None:
        if not self.is_direct_challenge:
            return
        self.challenge_decline_reason = reason

    def set_bot_challenge_status(self, status: str) -> None:
        if not self.is_bot_challenge:
            return
        self.bot_challenge_status = status
        if status != BOT_CHALLENGE_DECLINED:
            self.bot_challenge_decline_reason = None
        self.expire_at = self.default_expire_at()

    def set_bot_challenge_decline_reason(self, reason: str | None) -> None:
        if not self.is_bot_challenge:
            return
        self.bot_challenge_decline_reason = reason

    @property
    def seek_json(self) -> SeekJson:
        seek_json: SeekJson = {
            "_id": self.id,
            "seekID": self.id,
            "user": self.creator.username,
            "bot": self.creator.bot,
            "title": self.creator.title,
            "variant": self.variant,
            "chess960": self.chess960,
            "target": self.target,
            "player1": self.player1.username if self.player1 is not None else "",
            "player2": self.player2.username if self.player2 is not None else "",
            "bugPlayer1": self.bugPlayer1.username if self.bugPlayer1 is not None else "",
            "bugPlayer2": self.bugPlayer2.username if self.bugPlayer2 is not None else "",
            "fen": self.fen,
            "color": self.color,
            "rated": self.rated,
            "rrmin": self.rrmin,
            "rrmax": self.rrmax,
            "rating": self.rating,
            "base": self.base,
            "inc": self.inc,
            "byoyomi": self.byoyomi_period,
            "day": self.day,
            "gameId": self.game_id if self.game_id is not None else "",
        }
        if self.tournament_id is not None:
            seek_json["tournamentId"] = self.tournament_id
        if self.rr_arrangement_id is not None:
            seek_json["rrArrangementId"] = self.rr_arrangement_id
        if self.expire_at is not None:
            seek_json["expireAt"] = self.expire_at.isoformat()
        if self.challenge_status is not None:
            seek_json["challengeStatus"] = self.challenge_status
        if self.challenge_decline_reason:
            seek_json["challengeDeclineReason"] = self.challenge_decline_reason
        if self.bot_challenge_status is not None:
            seek_json["botChallengeStatus"] = self.bot_challenge_status
        if self.bot_challenge_decline_reason:
            seek_json["botChallengeDeclineReason"] = self.bot_challenge_decline_reason
        return seek_json

    @property
    def seek_db_json(self) -> SeekDbJson:
        seek_json: SeekDbJson = {
            "_id": self.id,
            "seekID": self.id,
            "user": self.creator.username,
            "bot": self.creator.bot,
            "title": self.creator.title,
            "variant": self.variant,
            "chess960": self.chess960,
            "target": self.target,
            "player1": self.player1.username if self.player1 is not None else "",
            "player2": self.player2.username if self.player2 is not None else "",
            "bugPlayer1": self.bugPlayer1.username if self.bugPlayer1 is not None else "",
            "bugPlayer2": self.bugPlayer2.username if self.bugPlayer2 is not None else "",
            "fen": self.fen,
            "color": self.color,
            "rated": self.rated,
            "rrmin": self.rrmin,
            "rrmax": self.rrmax,
            "rating": self.rating,
            "base": self.base,
            "inc": self.inc,
            "byoyomi": self.byoyomi_period,
            "day": self.day,
            "gameId": self.game_id if self.game_id is not None else "",
        }
        if self.tournament_id is not None:
            seek_json["tournamentId"] = self.tournament_id
        if self.rr_arrangement_id is not None:
            seek_json["rrArrangementId"] = self.rr_arrangement_id
        if self.expire_at is not None:
            seek_json["expireAt"] = self.expire_at
        if self.challenge_status is not None:
            seek_json["challengeStatus"] = self.challenge_status
        if self.challenge_decline_reason:
            seek_json["challengeDeclineReason"] = self.challenge_decline_reason
        if self.bot_challenge_status is not None:
            seek_json["botChallengeStatus"] = self.bot_challenge_status
        if self.bot_challenge_decline_reason:
            seek_json["botChallengeDeclineReason"] = self.bot_challenge_decline_reason
        return seek_json

    @property
    def is_direct_challenge(self) -> bool:
        return is_direct_challenge_target(self.target)

    @property
    def is_active_direct_challenge(self) -> bool:
        return (
            self.is_direct_challenge and self.challenge_status in ACTIVE_DIRECT_CHALLENGE_STATUSES
        )

    @property
    def is_rr_challenge(self) -> bool:
        return self.rr_arrangement_id is not None

    @property
    def is_bot_challenge(self) -> bool:
        return self.target == "BOT_challenge"

    @property
    def is_active_bot_challenge(self) -> bool:
        return self.is_bot_challenge and self.bot_challenge_status == BOT_CHALLENGE_CREATED

    def is_expired(self) -> bool:
        if self.expire_at is None:
            return False
        expire_at = self.expire_at
        if expire_at.tzinfo is None:
            expire_at = expire_at.replace(tzinfo=UTC)
        return expire_at <= datetime.now(UTC)

    @property
    def discord_msg(self) -> str:
        tc = time_control_str(self.base, self.inc, self.byoyomi_period, self.day)
        tail960 = "960" if self.chess960 and not is_catalogued_variant(self.variant) else ""
        return "%s: **%s%s** %s" % (self.creator.username, self.variant, tail960, tc)

    @staticmethod
    def _parse_expire_at(expire_at: datetime | str) -> datetime | None:
        if isinstance(expire_at, datetime):
            parsed = expire_at
        elif isinstance(expire_at, str):
            candidate = expire_at
            if candidate.endswith("Z"):
                candidate = candidate[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError:
                return None
        else:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


def resolve_decline_reason(reason: str | None, *, allow_custom: bool = False) -> str:
    reason_key = "" if reason is None else str(reason).strip()
    if reason_key in DECLINE_REASON_MESSAGES:
        return DECLINE_REASON_MESSAGES[reason_key]
    if allow_custom and reason_key:
        return reason_key[:300]
    return DECLINE_REASON_MESSAGES["generic"]


def is_anon_restricted_seek(
    user: User, variant: str, chess960: bool | None, day: float = 0
) -> bool:
    server_variant = get_server_variant(variant, chess960)
    return user.anon and (day > 0 or server_variant.two_boards)


def is_direct_challenge_target(target: str | None) -> bool:
    return (target or "") not in SPECIAL_SEEK_TARGETS


def is_targeted_two_board_seek(variant: str, chess960: bool | None, target: str | None) -> bool:
    # Two-board variants need the dedicated 4-seat bughouse flow.
    # Generic invites and direct challenges only model one or two seats,
    # so allowing them here can create malformed games.
    server_variant = get_server_variant(variant, chess960)
    return server_variant.two_boards and (
        (target or "") == "Invite-friend" or is_direct_challenge_target(target)
    )


def find_duplicate_direct_challenge(
    seeks: dict[str, Seek],
    creator: User,
    data: SeekCreateData,
) -> Seek | None:
    target = data.get("target", "")
    if not is_direct_challenge_target(target):
        return None

    for seek in seeks.values():
        if (
            seek.is_direct_challenge
            and not seek.is_rr_challenge
            and seek.is_active_direct_challenge
            and not seek.is_expired()
            and seek.creator.username == creator.username
            and seek.target == target
        ):
            return seek

    return None


def seek_counts_toward_limit(seek: Seek) -> bool:
    return (
        (not seek.is_rr_challenge)
        and (not seek.is_expired())
        and (not seek.is_direct_challenge or seek.is_active_direct_challenge)
        and (not seek.is_bot_challenge or seek.is_active_bot_challenge)
    )


def should_persist_seek_on_shutdown(seek: Seek) -> bool:
    if seek.is_expired():
        return False
    if seek.is_direct_challenge:
        return seek.is_active_direct_challenge
    if seek.is_bot_challenge:
        return True
    if seek.day > 0:
        return True
    return seek.creator.online


def should_restore_persisted_seek(seek: Seek) -> bool:
    if seek.is_expired():
        return False
    if seek.is_direct_challenge:
        return seek.is_active_direct_challenge
    if seek.is_bot_challenge:
        return True
    return True


def user_reached_seek_limit(user: User, day: float) -> bool:
    if day == 0:
        seeks_in_bucket = [seek for seek in user.seeks.values() if seek.day == 0]
    else:
        seeks_in_bucket = [seek for seek in user.seeks.values() if seek.day != 0]
    return (
        len([seek for seek in seeks_in_bucket if seek_counts_toward_limit(seek)]) >= MAX_USER_SEEKS
    )


async def create_seek(
    db: AsyncDatabase | None,
    invites: dict[str, Seek],
    seeks: dict[str, Seek],
    user: User,
    data: SeekCreateData,
    empty: bool = False,
    engine: User | None = None,
    *,
    tournament_id: str | None = None,
    rr_arrangement_id: str | None = None,
) -> Seek | None:
    """Seek can be
    - invite (has reserved new game id stored in app[invites], and target is 'Invite-friend')
    - challenge (has another username as target)
    - normal seek (no target)

    Empty seek is a seek where the seeker doesn't play
    Currently there is no limit for them since they're used for tournament organisation purposes
    They can only be created by trusted users
    """
    if is_catalogued_variant(data["variant"]):
        data = dict(data)  # type: ignore[assignment]
        data["rated"] = False
        data["chess960"] = catalogued_variant_random_start(data["variant"]) and (
            not data.get("fen") or bool(data.get("chess960"))
        )
    day = data.get("day", 0)
    chess960: bool | None = data.get("chess960")
    try:
        get_server_variant(data["variant"], chess960)
    except KeyError:
        log.info(
            "Rejecting seek creation for unavailable variant %s",
            data["variant"],
        )
        return None
    if is_anon_restricted_seek(user, data["variant"], chess960, day):
        log.info(
            "Rejecting restricted seek creation by anon user %s (variant=%s day=%s)",
            user.username,
            data["variant"],
            day,
        )
        return None

    if is_catalogued_variant(data["variant"]):
        username = None if user.anon else user.username
        if not can_create_catalogued_seek(user.app_state, data["variant"], username):
            log.info(
                "Rejecting inaccessible catalogued seek creation by %s (variant=%s)",
                user.username,
                data["variant"],
            )
            return None
        if day > 0 and not catalogued_variant_games_are_persisted(user.app_state, data["variant"]):
            log.info(
                "Rejecting private/unlisted catalogued correspondence seek by %s (variant=%s)",
                user.username,
                data["variant"],
            )
            return None

    duplicate = (
        None
        if rr_arrangement_id is not None
        else find_duplicate_direct_challenge(seeks, user, data)
    )
    if duplicate is not None:
        log.info(
            "Replacing direct challenge by %s against %s",
            user.username,
            data.get("target", ""),
        )
        duplicate.set_challenge_status(DIRECT_CHALLENGE_CANCELED)

    if rr_arrangement_id is None and user_reached_seek_limit(user, day) and not empty:
        return None

    target = data.get("target", "")
    if is_direct_challenge_target(target):
        if target == SYSTEM_USER:
            log.info("Rejecting direct challenge to system account %s by %s", target, user.username)
            return None
        target_profile = await user.app_state.public_users.get_profile(target)
        if target_profile is None:
            return None
        if target_profile.title == "BOT":
            log.info(
                "Rejecting generic direct challenge to BOT %s by %s",
                target,
                user.username,
            )
            return None
        if rr_arrangement_id is None and (
            target in user.blocked or user.username in target_profile.blocked
        ):
            log.info(
                "Rejecting direct challenge by %s against %s because users are blocked",
                user.username,
                target,
            )
            return None

    reserve_game_id = data.get("reserveGameId", False)
    if is_targeted_two_board_seek(data["variant"], chess960, target):
        log.info(
            "Rejecting targeted two-board seek by %s (variant=%s target=%s)",
            user.username,
            data["variant"],
            target,
        )
        return None

    if target in ("BOT_challenge", "Invite-friend") or reserve_game_id:
        if TYPE_CHECKING:
            assert db is not None
        game_id = await new_id(db.game)
    else:
        game_id = None

    seek_id = await new_id(None if db is None else db.seek)
    rated: bool | None = data.get("rated")
    seek = Seek(
        seek_id,
        user,
        data["variant"],
        fen=data["fen"],
        color=data["color"],
        base=data["minutes"],
        inc=data["increment"],
        byoyomi_period=data["byoyomiPeriod"],
        day=day,
        rated=rated,
        rrmin=data.get("rrmin"),
        rrmax=data.get("rrmax"),
        chess960=chess960,
        target=target,
        player1=None if empty else user,
        player2=engine if target == "BOT_challenge" else None,
        game_id=game_id,
        tournament_id=tournament_id,
        rr_arrangement_id=rr_arrangement_id,
    )

    log.debug("adding seek: %s" % seek)
    seeks[seek.id] = seek
    user.seeks[seek.id] = seek

    if target in ("BOT_challenge", "Invite-friend") or reserve_game_id:
        invites[game_id] = seek  # type: ignore[index]

    return seek


def _catalogued_seek_visible_to_user(user: User, seek: Seek) -> bool:
    if not is_catalogued_variant(seek.variant):
        return True
    username = None if user.anon else user.username
    return can_create_catalogued_seek(user.app_state, seek.variant, username)


def get_seeks(user: User, seeks: Iterable[Seek]) -> list[SeekJson]:
    return [
        seek.seek_json
        for seek in seeks
        if (
            not seek.pending
            and not seek.is_expired()
            and (not seek.is_direct_challenge or seek.is_active_direct_challenge)
            and _catalogued_seek_visible_to_user(user, seek)
            and user.compatible_with_seek(seek)
        )
    ]


def challenge(seek: Seek) -> str:
    """BOT API stream event response"""
    perf_name = get_server_variant(seek.variant, seek.chess960).server_name
    if seek.day > 0:
        time_control: dict[str, object] = {"type": "correspondence", "daysPerTurn": seek.day}
        speed = "correspondence"
    else:
        estimated_game_time = (60 * float(seek.base)) + (ESTIMATE_MOVES * seek.inc)
        if estimated_game_time < 30:
            speed = "ultraBullet"
        elif estimated_game_time < 180:
            speed = "bullet"
        elif estimated_game_time < 480:
            speed = "blitz"
        elif estimated_game_time < 1500:
            speed = "rapid"
        else:
            speed = "classical"
        time_control = {
            "type": "clock",
            "limit": int(float(seek.base) * 60),
            "increment": seek.inc,
        }

    color = {"w": "white", "b": "black"}.get(seek.color, "random")
    payload = {
        "type": "challenge",
        "challenge": {
            "id": seek.game_id,
            "challenger": {
                "name": seek.creator.username,
                "rating": seek.rating,
                "title": seek.creator.title,
            },
            "variant": {"key": "standard" if seek.variant == "chess" else seek.variant},
            "rated": bool(seek.rated),
            "timeControl": time_control,
            "color": color,
            "finalColor": "white" if color == "random" else color,
            "speed": speed,
            "perf": {"name": perf_name},
            "level": seek.level,
            "chess960": bool(seek.chess960),
        },
    }
    return json_dumps(payload) + "\n"
