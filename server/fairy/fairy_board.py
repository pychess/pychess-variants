from __future__ import annotations

import logging
import random
import re
from functools import lru_cache
from typing import TYPE_CHECKING

from const import CATEGORIES
from variants import catalogued_variant_random_start, is_catalogued_variant

# -*- coding: utf-8 -*-
from fairy.ataxx import ATAXX_FENS
from fairy.caparandom import caparandom_id_from_rank8, caparandom_rank8
from fairy.chess960 import CHESS960_FENS
from fairy.cwda import cwda_engine_variant
from fairy.jieqi import BLACK_PIECES, RED_PIECES, apply_move_and_transform, make_initial_mapping
from fairy.paradigm import PARADIGM_FENS
from fairy.racingkings import RACINGKINGS_FEN_TO_ID, RACINGKINGS_FENS

log = logging.getLogger(__name__)

try:
    import pyffish as sf

    sf.set_option("VariantPath", "variants.ini")
except ImportError:
    log.error("No pyffish module installed!")

try:
    import pyffish_alice as sf_alice
except ImportError:
    log.error("No pyffish-alice module installed!")

FEN_OK = sf.FEN_OK
NOTATION_LAN = sf.NOTATION_LAN
NOTATION_SAN = sf.NOTATION_SAN
NOTATION_JANGGI = sf.NOTATION_JANGGI
NOTATION_XIANGQI_WXF = sf.NOTATION_XIANGQI_WXF
NOTATION_SHOGI_HODGES_NUMBER = sf.NOTATION_SHOGI_HODGES_NUMBER

WHITE, BLACK = 0, 1
FILES = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]

STANDARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
CONSERVATIVE_CAPA_FEN = "arnbqkbnrc/pppppppppp/10/10/10/10/PPPPPPPPPP/ARNBQKBNRC w KQkq - 0 1"
LOOKING_GLASS_ALICE_FEN = "|r|n|b|q|k|b|n|r/|p|p|p|p|p|p|p|p/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1"
MANCHU_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/9/9/M1BAKAB2 w - - 0 1"
MANCHU_R_FEN = "m1bakab1r/9/9/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
JIEQI_FEN = "r~n~b~a~ka~b~n~r~/9/1c~5c~1/p~1p~1p~1p~1p~/9/9/P~1P~1P~1P~1P~/1C~5C~1/9/R~N~B~A~KA~B~N~R~ w - - 0 1"

RANDOM_START_VARIANTS = frozenset(("ataxx", "paradigm"))


def _normalize_variant_and_chess960(variant: str | None, chess960: bool) -> tuple[str, bool]:
    normalized_variant = (variant or "chess").strip()
    normalized_chess960 = chess960

    # Community names are literal engine keys; only site variants use the
    # suffix to select randomized starts and Chess960 castling.
    if normalized_variant.endswith("960") and not is_catalogued_variant(normalized_variant):
        normalized_variant = normalized_variant[:-3]
        normalized_chess960 = True

    if not normalized_variant:
        return "chess", normalized_chess960
    return normalized_variant, normalized_chess960


def file_of(piece: str, rank: str) -> int:
    """
    Returns the 0-based file of the specified piece in the rank.
    Returns -1 if the piece is not in the rank.
    """
    pos = rank.find(piece)
    if pos >= 0:
        return sum(int(p) if p.isdigit() else 1 for p in rank[:pos])
    else:
        return -1


def modded_variant(variant: str, chess960: bool, initial_fen: str) -> str:
    """Some variants need to be treated differently by pyffish."""
    if variant == "cwda":
        return cwda_engine_variant(initial_fen)
    if not chess960 and variant in ("capablanca", "capahouse") and initial_fen:
        """
        E-file king in a Capablanca/Capahouse variant.
        The game will be treated as an Embassy game for the purpose of castling
        if either side still has embassy-style castling available from the
        current setup.
        """
        parts = initial_fen.split()
        ranks = parts[0].split("/")
        castling = parts[2]
        white_can_castle = (
            castling != "-" and ("K" in castling or "Q" in castling) and file_of("K", ranks[7]) == 4
        )
        black_can_castle = (
            castling != "-" and ("k" in castling or "q" in castling) and file_of("k", ranks[0]) == 4
        )
        if white_can_castle or black_can_castle:
            return "embassyhouse" if "house" in variant else "embassy"
    return variant


def _color_from_initial_fen(initial_fen: str, variant: str) -> int:
    parts = initial_fen.split()
    if len(parts) < 2 or parts[1] not in ("w", "b"):
        raise ValueError(
            f"Invalid initial FEN for variant {variant!r}: "
            "expected an explicit side to move ('w' or 'b')."
        )
    return WHITE if parts[1] == "w" else BLACK


class FairyBoard:
    def __init__(
        self,
        variant: str,
        initial_fen="",
        chess960=False,
        count_started=0,
        disabled_fen="",
        show_promoted: bool = False,
        legal_moves_need_history: bool = False,
    ):
        normalized_variant, normalized_chess960 = _normalize_variant_and_chess960(variant, chess960)
        initial_color = (
            _color_from_initial_fen(initial_fen, normalized_variant) if initial_fen else None
        )
        self.variant = modded_variant(normalized_variant, normalized_chess960, initial_fen)
        self.sf = sf_alice if normalized_variant == "alice" else sf
        self.chess960 = normalized_chess960
        self.sfen = False
        self.show_promoted = show_promoted or variant in (
            "makruk",
            "makpong",
            "cambodian",
            "bughouse",
            "supply",
            "makbug",
        )
        self.legal_moves_need_history = legal_moves_need_history or variant in ("janggi", "ataxx")
        self.nnue = initial_fen == ""

        self.movelist_supported = self.variant != "jieqi"
        self.jieqi_covered_pieces = None
        self.jieqi_initial_covered_pieces = None

        if initial_fen:
            self.initial_fen = initial_fen
        else:
            if self.variant == "jieqi":
                self.initial_fen = JIEQI_FEN
                self.set_jieqi_initial_pieces(
                    random.sample(BLACK_PIECES, 15), random.sample(RED_PIECES, 15)
                )
                # print("---", self.initial_fen)
                # print(self.jieqi_covered_pieces)
            else:
                self.initial_fen = FairyBoard.start_fen(
                    variant, chess960 or variant in RANDOM_START_VARIANTS, disabled_fen
                )
        self.move_stack: list[str] = []
        self.ply = 0
        self.color = (
            initial_color
            if initial_color is not None
            else _color_from_initial_fen(self.initial_fen, self.variant)
        )
        self.fen = self.initial_fen
        self.manual_count = count_started != 0
        self.count_started = count_started

        if self.variant == "janggi":
            self.notation = NOTATION_JANGGI
        elif self.variant in CATEGORIES["shogi"]:
            self.notation = NOTATION_SHOGI_HODGES_NUMBER
        elif self.variant in (
            "xiangqi",
            "xiangqihouse",
            "supply",
            "manchu",
            "minixiangqi",
            "jieqi",
        ):
            self.notation = NOTATION_XIANGQI_WXF
        else:
            self.notation = NOTATION_SAN

    @staticmethod
    def start_fen(variant: str | None, chess960=False, disabled_fen=""):
        normalized_variant, normalized_chess960 = _normalize_variant_and_chess960(variant, chess960)

        if is_catalogued_variant(normalized_variant):
            default_fen = sf.start_fen(normalized_variant)
            if not normalized_chess960 or not catalogued_variant_random_start(normalized_variant):
                return default_fen
            # Only replace back ranks and castling rights; keep the variant's
            # pawns, middle ranks, hands and additional FEN fields intact.
            fields = default_fen.split()
            placement, bracket, pockets = fields[0].partition("[")
            rows = placement.split("/")
            candidates = list(CHESS960_FENS)
            random.shuffle(candidates)
            for rank in candidates:
                rows[0], rows[-1] = rank, rank.upper()
                fields[0] = "/".join(rows) + bracket + pockets
                rights = FILES[rank.rindex("r")] + FILES[rank.index("r")]
                fields[2] = rights.upper() + rights
                new_fen = " ".join(fields)
                if (
                    fields[0] != disabled_fen.split(" ", 1)[0]
                    and sf.validate_fen(new_fen, normalized_variant, True) == FEN_OK
                ):
                    return new_fen
            raise ValueError(f"No valid randomized start for {normalized_variant}")

        if normalized_chess960 or normalized_variant in RANDOM_START_VARIANTS:
            new_fen = FairyBoard.shuffle_start(normalized_variant)
            while new_fen == disabled_fen:
                new_fen = FairyBoard.shuffle_start(normalized_variant)
        elif normalized_variant == "alice":
            new_fen = sf_alice.start_fen("alice")
        else:
            new_fen = sf.start_fen(normalized_variant)

        if normalized_variant in ("bughouse", "supply", "makbug"):
            return new_fen + " | " + new_fen
        elif normalized_variant == "manchu":
            return MANCHU_R_FEN
        else:
            return new_fen

    @property
    def posnum(self):
        if self.chess960:
            if self.variant == "racingkings":
                return RACINGKINGS_FEN_TO_ID.get(self.initial_fen[12:29], -1)
            try:
                if self.variant in ("capablanca", "capahouse"):
                    rank8 = self.initial_fen.split("/", 1)[0]
                    return caparandom_id_from_rank8(rank8)
                return CHESS960_FENS.index(self.initial_fen[:8])
            except ValueError:
                # Legacy/corrupted chess960 FEN can be outside known start positions.
                return -1
        else:
            return -1

    @property
    def initial_sfen(self):
        return self.sf.get_fen(self.variant, self.initial_fen, [], False, True)

    def set_jieqi_initial_pieces(self, black_pieces, red_pieces):
        self.black_pieces = list(black_pieces)
        self.red_pieces = list(red_pieces)
        initial_mapping = make_initial_mapping(self.black_pieces, self.red_pieces)
        self.jieqi_initial_covered_pieces = initial_mapping
        self.jieqi_covered_pieces = dict(initial_mapping)

    def push(self, move, append=True, *, raise_on_error=True):
        previous_fen = self.fen
        previous_color = self.color
        previous_ply = self.ply
        previous_stack_length = len(self.move_stack)
        previous_jieqi_mapping = (
            dict(self.jieqi_covered_pieces) if self.jieqi_covered_pieces is not None else None
        )
        try:
            # log.debug("move=%s, fen=%s", move, self.fen
            if append:
                self.move_stack.append(move)
                self.ply += 1
            self.color = WHITE if self.color == BLACK else BLACK
            if self.jieqi_covered_pieces is not None:
                if self.jieqi_initial_covered_pieces is None:
                    self.jieqi_initial_covered_pieces = dict(self.jieqi_covered_pieces)
                self.fen = apply_move_and_transform(self.fen, move, self.jieqi_covered_pieces)
                # print(move, self.fen)
            else:
                self.fen = self.sf.get_fen(
                    self.variant,
                    self.fen,
                    [move],
                    self.chess960,
                    self.sfen,
                    self.show_promoted,
                    self.count_started,
                )
        except Exception:
            del self.move_stack[previous_stack_length:]
            self.fen = previous_fen
            self.color = previous_color
            self.ply = previous_ply
            if previous_jieqi_mapping is not None:
                self.jieqi_covered_pieces = previous_jieqi_mapping
            if raise_on_error:
                log.error(
                    "sf.get_fen() failed on %s %s %s %s %s %s %s",
                    self.variant,
                    self.fen,
                    move,
                    self.chess960,
                    self.sfen,
                    self.show_promoted,
                    self.count_started,
                )
                raise
            return False
        return True

    def pop(self, remove=True):
        if remove and not self.move_stack:
            raise IndexError("pop from empty list")

        moves = self.move_stack[:-1] if remove else self.move_stack
        jieqi_mapping = None
        if self.jieqi_initial_covered_pieces is not None:
            jieqi_mapping = dict(self.jieqi_initial_covered_pieces)
            fen = self.initial_fen
            for move in moves:
                fen = apply_move_and_transform(fen, move, jieqi_mapping)
        else:
            fen = self.sf.get_fen(
                self.variant,
                self.initial_fen,
                moves,
                self.chess960,
                self.sfen,
                self.show_promoted,
                self.count_started,
            )

        if remove:
            self.move_stack.pop()
        self.ply -= 1
        self.color = not self.color
        self.fen = fen
        if jieqi_mapping is not None:
            self.jieqi_covered_pieces = jieqi_mapping

    def get_san(self, move):
        return self.sf.get_san(self.variant, self.fen, move, self.chess960, self.notation)

    def has_legal_move(self):
        if self.legal_moves_need_history:
            return (
                len(
                    self.sf.legal_moves(
                        self.variant, self.initial_fen, self.move_stack, self.chess960
                    )
                )
                > 0
            )
        else:
            return bool(self.legal_moves())

    def legal_moves(self):
        # move legality can depend on history, e.g., passing and bikjang
        if self.legal_moves_need_history:
            return self.sf.legal_moves(
                self.variant, self.initial_fen, self.move_stack, self.chess960
            )
        else:
            if self.jieqi_covered_pieces:
                moves = self.sf.legal_moves(self.variant, self.fen, [], self.chess960)
                for invalid_move in self.invalid_jieqi_advisor_moves():
                    try:
                        moves.remove(invalid_move)
                    except ValueError:
                        # Fake advisor invalid_move (go out from the palace) exists it the
                        # given position, but it is NOT a valid move by other reason
                        # f.e. leaves the king in check
                        pass
                return moves
            else:
                return self.sf.legal_moves(self.variant, self.fen, [], self.chess960)

    def legal_moves_no_history(self):
        # move legality can depend on history, but for bughouse we can't recreate history so we need this version
        return self.sf.legal_moves(self.variant, self.fen, [], self.chess960)

    def is_checked(self):
        return self.sf.gives_check(self.variant, self.fen, [], self.chess960)

    def insufficient_material(self):
        return self.sf.has_insufficient_material(self.variant, self.fen, [], self.chess960)

    def is_immediate_game_end(self):
        if self.movelist_supported:
            immediate_end, result = self.sf.is_immediate_game_end(
                self.variant, self.initial_fen, self.move_stack, self.chess960
            )
        else:
            immediate_end, result = self.sf.is_immediate_game_end(
                self.variant, self.fen, [], self.chess960
            )
        return immediate_end, result

    def is_optional_game_end(self):
        if self.movelist_supported:
            return self.sf.is_optional_game_end(
                self.variant,
                self.initial_fen,
                self.move_stack,
                self.chess960,
                self.count_started,
            )
        else:
            return self.sf.is_optional_game_end(
                self.variant,
                self.fen,
                [],
                self.chess960,
                self.count_started,
            )

    def is_claimable_draw(self):
        optional_end, result = self.is_optional_game_end()
        return optional_end and result == 0

    def game_result(self):
        if self.movelist_supported:
            return self.sf.game_result(
                self.variant, self.initial_fen, self.move_stack, self.chess960
            )
        else:
            return self.sf.game_result(self.variant, self.fen, [], self.chess960)

    def game_result_no_history(self):
        return self.sf.game_result(self.variant, self.fen, [], self.chess960)

    def piece_to_partner(self, move):
        return self.sf.piece_to_partner(self.variant, self.fen, [move], self.chess960)

    def print_pos(self):
        print()
        uni_pieces = {
            "R": "♜",
            "N": "♞",
            "B": "♝",
            "Q": "♛",
            "K": "♚",
            "P": "♟",
            "r": "♖",
            "n": "♘",
            "b": "♗",
            "q": "♕",
            "k": "♔",
            "p": "♙",
            ".": "·",
            "/": "\n",
        }
        fen = self.fen
        if "[" in fen:
            board, _rest = fen.split("[")
        else:
            board = fen.split()[0]
        board = board.replace("+", "")
        board = re.sub(r"\d", (lambda m: "." * int(m.group(0))), board)
        print("", " ".join(uni_pieces.get(p, p) for p in board))

    def janggi_setup(self, color):
        if color == "b":
            left = random.choice(("nb", "bn"))
            right = random.choice(("nb", "bn"))
            fen = "r%sa1a%sr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ABNR w - - 0 1" % (
                left,
                right,
            )
        else:
            left = random.choice(("NB", "BN"))
            right = random.choice(("NB", "BN"))
            parts = self.initial_fen.split("/")
            parts[-1] = "R%sA1A%sR w - - 0 1" % (left, right)
            fen = "/".join(parts)
        log.debug("Janggi setup (%s) generated initial FEN: %s", color, fen)
        self.initial_fen = fen
        self.fen = self.initial_fen

    def revealed_piece(self, move):
        src = move[0:3] if move[2].isdigit() else move[0:2]
        return self.jieqi_covered_pieces.get(src)

    def captured_jieqi_piece(self, move):
        """
        Return the real piece letter for a covered piece captured by this move.

        Jieqi stores hidden identities in jieqi_covered_pieces. We need to peek at
        the destination square before the move is applied, because applying the
        move mutates the mapping and would erase the captured identity.
        """
        if not self.jieqi_covered_pieces:
            return None

        # The move may include a trailing reveal suffix or a check marker, so strip
        # the suffix first to parse the destination square reliably.
        move_str = move
        if len(move_str) < 4:
            return None
        if move_str[-1].isalpha():
            move_str = move_str[:-1]

        if move_str[2].isdigit():
            dst = move_str[3:].rstrip("+")
        else:
            dst = move_str[2:].rstrip("+")

        return self.jieqi_covered_pieces.get(dst)

    def invalid_jieqi_advisor_moves(self):
        if TYPE_CHECKING:
            assert self.jieqi_covered_pieces is not None
        if self.color == WHITE:
            if "d1" in self.jieqi_covered_pieces:
                yield "d1c2"
            if "f1" in self.jieqi_covered_pieces:
                yield "f1g2"
        else:
            if "d10" in self.jieqi_covered_pieces:
                yield "d10c9"
            if "f10" in self.jieqi_covered_pieces:
                yield "f10g9"

    @staticmethod
    def shuffle_start(variant):
        """Create random initial position.
        The king is placed somewhere between the two rooks.
        The bishops are placed on opposite-colored squares.
        Same for queen and archbishop in caparandom."""

        if variant == "ataxx":
            return random.choice(ATAXX_FENS)
        elif variant == "paradigm":
            return random.choice(PARADIGM_FENS)
        elif variant == "racingkings":
            return "8/8/8/8/8/8/%s w - - 0 1" % random.choice(RACINGKINGS_FENS)

        capa = variant in ("capablanca", "capahouse")
        seirawan = variant in ("seirawan", "shouse")

        if capa:
            rank8 = caparandom_rank8()
        else:
            rank8 = random.choice(CHESS960_FENS)

        if seirawan:
            castl = (
                "kq"
                + FILES[rank8.index("b")]
                + FILES[rank8.rindex("b")]
                + FILES[rank8.index("q")]
                + FILES[rank8.index("n")]
                + FILES[rank8.rindex("n")]
            )
        else:
            castl = FILES[rank8.index("r")] + FILES[rank8.rindex("r")]

        rank8 = "".join(rank8)
        if capa:
            body = "/pppppppppp/10/10/10/10/PPPPPPPPPP/"
        else:
            body = "/pppppppp/8/8/8/8/PPPPPPPP/"

        if variant in ("crazyhouse", "capahouse", "bughouse"):
            holdings = "[]"
        elif seirawan:
            holdings = "[HEhe]"
        else:
            holdings = ""

        checks = "3+3 " if variant == "3check" else ""

        if variant == "horde":
            fen = (
                rank8
                + "/pppppppp/8/1PP2PP1/PPPPPPPP/PPPPPPPP/PPPPPPPP/PPPPPPPP"
                + " w "
                + castl
                + " - "
                + "0 1"
            )
        elif variant == "antichess":
            fen = rank8 + body + rank8.upper() + " w - - 0 1"
        else:
            fen = (
                rank8
                + body
                + rank8.upper()
                + holdings
                + " w "
                + castl.upper()
                + castl
                + " - "
                + checks
                + "0 1"
            )
        return fen


FOG_FEN_CACHE_SIZE = 4096


@lru_cache(maxsize=FOG_FEN_CACHE_SIZE)
def get_fog_fen(fen, persp_color):
    parts = fen.split(" ")

    fen_color = "w" if parts[1] == "w" else "b"
    opp_color = "w" if persp_color == WHITE else "b"

    # set the perspective color to sf.get_fog_fen()
    parts[1] = parts[1].replace(fen_color, opp_color)

    # remove castling rights of the player in fog
    # because the resulting fog FEN may have no king
    if persp_color == WHITE:
        parts[2] = "".join(letter for letter in parts[2] if letter.isupper())
    else:
        parts[2] = "".join(letter for letter in parts[2] if letter.islower())
    fen = " ".join(parts)

    fen = sf.get_fog_fen(fen, "fogofwar")

    # restore original FEN color
    parts = fen.split(" ")
    parts[1] = parts[1].replace(opp_color, fen_color)
    fen = " ".join(parts)

    return fen


def get_san_moves(variant, fen, mlist, chess960, notation):
    normalized_variant, normalized_chess960 = _normalize_variant_and_chess960(variant, chess960)
    if normalized_variant == "alice":
        return sf_alice.get_san_moves(normalized_variant, fen, mlist, normalized_chess960, notation)
    else:
        return sf.get_san_moves(normalized_variant, fen, mlist, normalized_chess960, notation)


def validate_fen(fen, variant, chess960):
    normalized_variant, normalized_chess960 = _normalize_variant_and_chess960(variant, chess960)
    if normalized_variant == "alice":
        return sf_alice.validate_fen(fen, normalized_variant, normalized_chess960)
    else:
        return sf.validate_fen(fen, normalized_variant, normalized_chess960)


if __name__ == "__main__":
    board = FairyBoard("shogi")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("placement")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("makruk")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("sittuyin")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("capablanca")
    print(board.fen)
    for move in (
        "e2e4",
        "d7d5",
        "e4d5",
        "c8i2",
        "d5d6",
        "i2j1",
        "d6d7",
        "j1e6",
        "d7e8c",
    ):
        print("push move", move)
        board.push(move)
        board.print_pos()
        print(board.fen)
    print(board.legal_moves())

    FEN = "r8r/1nbqkcabn1/ppppppp1pp/10/9P/10/10/PPPPPPPPp1/1NBQKC2N1/R5RAB1[p] b - - 0 5"
    board = FairyBoard("grandhouse", initial_fen=FEN)
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("minishogi")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    board = FairyBoard("kyotoshogi")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())

    print("--- SHOGUN ---")
    print(FairyBoard.start_fen("shogun"))
    board = FairyBoard("shogun")
    for move in ("c2c4", "b8c6", "b2b4", "b7b5", "c4b5", "c6b8"):
        print("push move", move, board.get_san(move))
        if board.move_stack:
            print(
                "is_checked(), insuff material, draw?",
                board.is_checked(),
                board.insufficient_material(),
                board.is_claimable_draw(),
            )
        board.push(move)
        board.print_pos()
        print(board.fen)
        print(board.legal_moves())

    FEN = "rnb+fkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB+FKBNR w KQkq - 0 1"
    board = FairyBoard("shogun", initial_fen=FEN)
    for move in (
        "c2c4",
        "h7h6",
        "c4c5",
        "h6h5",
        "c5c6+",
        "h8h6",
        "c6b7",
        "g7g6",
        "b7a8",
        "c8a6",
        "a8b7",
        "b8c6",
        "d1b3",
        "a6e2+",
        "b3b6",
        "e7e6",
        "b6c7",
        "P@h4",
        "c7c8",
        "e2c4",
        "f1c4",
        "h6h8",
        "c4e6+",
        "g8h6",
        "b2b4",
        "h8g8",
        "b4b5",
        "g6g5",
        "b5c6",
        "f8e7",
        "c6c7",
        "d7e6",
        "c8b8",
        "B@b6",
    ):
        print("push move", move, board.get_san(move))
        if board.move_stack:
            print(
                "is_checked(), insuff material, draw?",
                board.is_checked(),
                board.insufficient_material(),
                board.is_claimable_draw(),
            )
        board.push(move)
        board.print_pos()
        print(board.fen)
        print(board.legal_moves())

    board = FairyBoard("shouse")
    for move in (
        "e2e4",
        "E@d4",
        "g1f3",
        "e7e6",
        "b1c3",
        "H@b6",
        "d2d3",
        "f8b4",
        "c1e3",
        "d4b5",
        "e3b6",
        "a7b6",
        "d1d2e",
        "B@c6",
        "f1e2",
        "b5h5",
    ):
        print("push move", move, board.get_san(move))
        if board.move_stack:
            print(
                "is_checked(), insuff material, draw?",
                board.is_checked(),
                board.insufficient_material(),
                board.is_claimable_draw(),
            )
        board.push(move)
        board.print_pos()
        print(board.fen)
        print(board.legal_moves())

    board = FairyBoard("empire")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())
    print([board.get_san(move) for move in board.legal_moves()])

    board = FairyBoard("ordamirror")
    print(board.fen)
    board.print_pos()
    print(board.legal_moves())
    print([board.get_san(move) for move in board.legal_moves()])

    print(sf.version())
    print(sf.info())
    print(sf.variants())

    board = FairyBoard(
        "janggi",
        initial_fen="1nba2b2/4ka1R1/1cc6/p1p1p1p1p/9/9/P1P1P1PP1/1C5C1/4AK3/RNBA2BN1 w - - 0 1",
    )
    for move in (
        "h9f9",
        "e9f9",
        "f2f2",
    ):
        print("push move", move, board.get_san(move))
        if board.move_stack:
            print(
                "is_checked(), insuff material, draw?",
                board.is_checked(),
                board.insufficient_material(),
                board.is_claimable_draw(),
            )
        board.push(move)
        board.print_pos()
        print(board.fen)
        print(board.legal_moves())

    FEN = "6n2/3wc3b/1b4m2/9/4+g4/2r6/4+G+GW2/2N6/3GM1R2[C] w - - 4 14"
    board = FairyBoard("xiangfu", initial_fen=FEN)
    print(board.fen)
    board.print_pos()
    print(board.is_checked())
    print(board.legal_moves())
