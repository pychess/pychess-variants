from __future__ import annotations

from fairy.fairy_board import FEN_OK, FairyBoard
from utils import MAX_CUSTOM_FEN_LENGTH, fen_board_width, pocket_variant_material_fits_engine


def validated_study_position(
    runtime_variant: str, fen: str, *, chess960: bool, show_promoted: bool
) -> FairyBoard:
    """Check one client-derived position before native move generation.

    Bulk imports deliberately do not replay or engine-validate every node. Stored
    node FENs must instead pass this admission check when an edit or Fishnet PV
    needs a position-local board. The native FEN validator checks syntax/geometry,
    but does not bound pocket material, so apply the existing material guard first.
    """
    fields = fen.split()
    if (
        len(fen) > MAX_CUSTOM_FEN_LENGTH
        or not fen.isascii()
        or "\x00" in fen
        or len(fields) < 4
        or fields[1] not in ("w", "b")
    ):
        raise ValueError("Invalid stored Study FEN")
    # The native validator splits on literal spaces; normalize whitespace first.
    board = FairyBoard(
        runtime_variant,
        initial_fen=" ".join(fields),
        chess960=chess960,
        show_promoted=show_promoted,
    )
    start_fen = FairyBoard.start_fen(board.variant)
    placement = fields[0]
    start_placement = start_fen.split()[0]
    start_ranks = start_placement.split("[", 1)[0].split("/")
    ranks = placement.split("[", 1)[0].split("/")
    width = fen_board_width(start_placement)
    # The native validator writes to a fixed-width character board while parsing
    # ranks. Reject oversized ranks before handing even validation this input.
    if any(fen_board_width(rank) > width for rank in ranks[: len(start_ranks)]):
        raise ValueError("Invalid stored Study FEN geometry")
    if (
        "[" in start_placement or "[" in placement or len(ranks) > len(start_ranks)
    ) and not pocket_variant_material_fits_engine(board.fen, start_fen):
        raise ValueError("Stored Study FEN exceeds engine material limits")
    status = board.sf.validate_fen(board.fen, board.variant, chess960)
    if status != FEN_OK and not chess960 and board.variant in ("seirawan", "shouse"):
        # File-letter gating rights remain valid after the king has moved.
        status = board.sf.validate_fen(board.fen, board.variant, True)
    if status != FEN_OK:
        raise ValueError("Invalid stored Study FEN")
    return board
