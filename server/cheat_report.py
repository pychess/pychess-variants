from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from game import Game
    from pymongo.asynchronous.database import AsyncDatabase
    from user import User

log = logging.getLogger(__name__)

CHEAT_REPORT_COLLECTION = "cheat_report"
CEVAL_AUTO_LOSE_CONFIG_NAME = "ceval.auto_lose"
CEVAL_REPORT_REASON = "ceval_cross_tab"
CEVAL_REPORT_ACTION_REPORTED_ONLY: Literal["reported_only"] = "reported_only"
CEVAL_REPORT_ACTION_AUTO_FORFEIT: Literal["auto_forfeit"] = "auto_forfeit"
CevalReportAction = Literal["reported_only", "auto_forfeit"]


async def ceval_auto_lose_enabled(db: AsyncDatabase | None) -> bool:
    if db is None:
        return False

    doc = await db.config.find_one({"name": CEVAL_AUTO_LOSE_CONFIG_NAME}, projection={"value": 1})
    return bool(doc is not None and doc.get("value") is True)


async def append_ceval_cheat_report(
    db: AsyncDatabase | None,
    *,
    game: Game,
    user: User,
    reported_fen: str,
    reported_variant: str,
    reported_chess960: bool,
    min_report_ply: int,
    action: CevalReportAction,
) -> None:
    if db is None:
        return

    opponent = (
        game.bplayer.username if user.username == game.wplayer.username else game.wplayer.username
    )

    report = {
        "createdAt": datetime.now(UTC),
        "kind": CEVAL_REPORT_REASON,
        "action": action,
        "gameId": game.id,
        "suspect": user.username,
        "opponent": opponent,
        "variant": game.variant,
        "chess960": bool(game.chess960),
        "rated": bool(game.rated),
        "tournamentId": game.tournamentId,
        "simulId": game.simulId,
        "ply": game.board.ply,
        "minReportPly": min_report_ply,
        "reportedVariant": reported_variant,
        "reportedChess960": reported_chess960,
        "reportedFen": reported_fen,
        "liveFen": game.board.fen,
        "boardFen": reported_fen.split(" ", 1)[0],
    }

    try:
        await db[CHEAT_REPORT_COLLECTION].insert_one(report)
    except Exception:
        log.exception("Failed to store ceval cheat report for game %s", game.id)


MAX_OVERLAY_SVG_BYTES = 32 * 1024


def valid_overlay_svg(value: object) -> str | None:
    """Bound untrusted evidence; it is never rendered or parsed by the server."""
    if not isinstance(value, str) or not value.startswith("<svg"):
        return None
    if len(value.encode("utf-8", errors="replace")) > MAX_OVERLAY_SVG_BYTES:
        return None
    return value


async def append_overlay_cheat_report(
    db: AsyncDatabase | None, *, game: Game, user: User, svg: str | None = None
) -> None:
    """Store unverified evidence once per player/game, never impose sanctions."""
    if db is None:
        return
    report_key = {
        "kind": "external_overlay",
        "gameId": game.id,
        "suspect": user.username,
    }
    opponent = (
        game.bplayer.username if user.username == game.wplayer.username else game.wplayer.username
    )
    evidence = {"overlaySvg": svg} if svg is not None else {}
    try:
        await db[CHEAT_REPORT_COLLECTION].update_one(
            report_key,
            {
                "$setOnInsert": {
                    **report_key,
                    "createdAt": datetime.now(UTC),
                    "action": "reported_only",
                    "source": "unverified_client_dom",
                    "opponent": opponent,
                    "variant": game.variant,
                    "rated": bool(game.rated),
                    "ply": game.board.ply,
                    **evidence,
                }
            },
            upsert=True,
        )
    except Exception:
        log.exception("Failed to store overlay report for game %s", game.id)
