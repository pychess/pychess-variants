"""Stored two-board history metadata and explicit authoritative replay."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from const import MATE, POCKET_PATTERN
from fairy import BLACK, WHITE

if TYPE_CHECKING:
    from bug.game_bug import GameBug

log = logging.getLogger(__name__)


def clock_columns(game: GameBug, doc):
    # Two-board documents include the initial clock entry, unlike single-board games.
    base = game.base * 60000 if game.base > 0 else game.inc * 1000
    columns = [[base], [base], [base], [base]]
    if "cw" in doc:
        columns[:2] = [doc["cw"] or [base], doc["cb"] or [base]]
    if "cwB" in doc:
        columns[2:] = [doc["cwB"] or [base], doc["cbB"] or [base]]
    return columns


def step_metadata(doc, columns, ply):
    # Retain the archive reader's treatment of missing/zero clocks as null.
    values = [column[ply] if ply < len(column) and column[ply] else None for column in columns]
    timestamps = doc.get("ts") or []
    metadata = {
        "clocks": values[:2],
        "clocksB": values[2:],
        "ts": int(timestamps[ply]) if ply < len(timestamps) else 0,
    }
    analysis = doc.get("a") or []
    if ply < len(analysis):
        metadata["analysis"] = analysis[ply]
    chat = doc.get("c") or {}
    if "m" + str(ply) in chat:
        metadata["chat"] = [
            {"message": entry["m"], "username": entry["u"], "time": entry["t"]}
            for entry in chat["m" + str(ply)]
        ]
    return metadata


def replay_history(game: GameBug, doc, moves):
    """Replay on demand; active restoration and backend analysis share this path."""
    columns = clock_columns(game, doc)
    restored_clocks = {
        board: list(values) for board, values in game.gameClocks.last_move_clocks.items()
    }
    restored_ts: dict[str, int] = {}
    board_ply = {"a": 0, "b": 0}
    last_moves = {"a": "", "b": ""}
    timestamps = doc.get("ts") or []
    for index, move in enumerate(moves):
        try:
            board_name = "a" if doc["o"][index] == 0 else "b"
            board = game.boards[board_name]
            last_moves[board_name] = move
            if move[1:2] != "@":
                captured = board.piece_to_partner(move)
                if captured is not None:
                    partner = game.boards["b" if board_name == "a" else "a"]
                    partner.fen = POCKET_PATTERN.sub(r"[\1%s]" % captured, partner.fen)
            san = board.get_san(move)
            if doc["s"] != MATE and san.endswith("#"):
                san = san.replace("#", "+")
            board.push(move)
            check = board.is_checked()
            if board_name == "a":
                game.checkA = check
            else:
                game.checkB = check
            step = {
                "fen": game.boards["a"].fen,
                "fenB": game.boards["b"].fen,
                "move": last_moves["a"],
                "moveB": last_moves["b"],
                "boardName": board_name,
                "san": san,
                # Keep the historical reader's per-board parity convention.
                "turnColor": "white" if (board_ply[board_name] + 1) % 2 == 0 else "black",
                "check": check,
                **step_metadata(doc, columns, index + 1),
            }
            mover_color = WHITE if board_ply[board_name] % 2 == 0 else BLACK
            mover = (
                (game.wplayerA if mover_color == WHITE else game.bplayerA)
                if board_name == "a"
                else (game.wplayerB if mover_color == WHITE else game.bplayerB)
            )
            game.lastmovePerBoardAndUser[board_name][mover.username] = move
            mover_clocks = step["clocks"] if board_name == "a" else step["clocksB"]
            if mover_clocks[mover_color] is not None:
                restored_clocks[board_name][mover_color] = mover_clocks[mover_color]
            if index + 1 < len(timestamps):
                restored_ts[board_name] = int(timestamps[index + 1])
            board_ply[board_name] += 1
            game.steps.append(step)
            game.lastmove = move
        except Exception:
            log.exception(
                "Stopped two-board history replay %s at move %s: %s", game.id, index + 1, move
            )
            break
    return restored_clocks, restored_ts
