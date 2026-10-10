from __future__ import annotations

"""Regenerate the filtered Racing Kings 1440 start-position catalogue.

Why this filter exists
----------------------
Racing Kings is unusually sensitive to randomized starts: both armies begin on
only two ranks, there are no pawns, and captures can happen immediately.  Some
of the 1,440 published Racing Kings random starts therefore hand White an
obvious material win before meaningful Racing Kings play begins.

The published analysis by ijh/borealowls ranks all 1,440 starts by engine
score.  We use that ranking only to bound the expensive shallow tactical
search: positions ranked 1..448 are above +300 in ``rk1440.pdf`` (rank 448 is
+301, rank 449 is +300).  Engine evaluation itself is *not* the exclusion rule.

A start is excluded when either:

1. White can force a material advantage greater than a minor piece (> 3 with
   Q=9, R=5, B=N=3) within 8 plies.  White is restricted to captures, while
   Black may play any legal defensive move.  This models a short, obvious
   capture sequence rather than general Racing Kings strategy.
2. Across all 1,440 starts, White has an immediate capture after which Black's
   best legal immediate material recovery still leaves White materially ahead.
   This catches low-engine-score but plainly defective starts such as a free
   rook, and favorable one-move exchanges such as rook-for-minor.

The 8-ply horizon was chosen empirically from the published ranking: among the
71 top-448 positions not caught at 8 plies, extending to 10 plies found only 2
more positions, and extending to 12 found none beyond those 2.  Eight plies
therefore gives a natural shallow-tactics cutoff without turning this utility
into a general-purpose engine search.

With pyffish 0.0.90 and the pinned source list this produces 392 exclusions and
1,048 retained starts.  The generated module preserves each source position ID
so ``FairyBoard.posnum`` continues to use the original 0..1439 numbering.

Sources:
- https://github.com/borealowls/Variant960/blob/main/part%201/RKK1440FENS.txt
- https://github.com/borealowls/Variant960/blob/main/rk1440.pdf

Run from the repository root, for example::

    uv run python scripts/generate_racingkings960_fens.py \
        --source /path/to/RKK1440FENS.txt

If ``--source`` is omitted, the pinned source list is downloaded from GitHub.
Use ``--check`` to verify that ``server/fairy/racingkings.py`` is up to date
without rewriting it.
"""

import argparse
import hashlib
import os
from collections.abc import Iterable
from functools import cache
from multiprocessing import Pool
from pathlib import Path
from urllib.request import urlopen

import pyffish as sf

SOURCE_URL = "https://raw.githubusercontent.com/borealowls/Variant960/main/part%201/RKK1440FENS.txt"
SOURCE_SHA256 = "28648c7684743742ac8dff51760ee751e57ff3aefb67feea90d1128c5d5f7fe4"
SOURCE_POSITION_COUNT = 1440
ENGINE_SCAN_COUNT = 448
MAX_TACTICAL_PLIES = 8
MATERIAL_ADVANTAGE_THRESHOLD = 3
EXPECTED_IMMEDIATE_EXCLUSIONS = 168
EXPECTED_ADDITIONAL_SHALLOW_EXCLUSIONS = 224
EXPECTED_TOTAL_EXCLUSIONS = 392
EXPECTED_RETAINED_STARTS = 1048

PIECE_VALUES = {
    "q": 9,
    "r": 5,
    "b": 3,
    "n": 3,
    "Q": 9,
    "R": 5,
    "B": 3,
    "N": 3,
}

# Position IDs, in engine-rank order, for ranks 1..448 of rk1440.pdf.
# The 448th score is +301; rank 449 is +300.
ENGINE_SCAN_POSITION_IDS = (
    511,
    508,
    160,
    689,
    172,
    1398,
    43,
    523,
    712,
    492,
    496,
    388,
    499,
    494,
    702,
    707,
    411,
    485,
    697,
    232,
    1212,
    1207,
    690,
    703,
    487,
    1396,
    252,
    227,
    687,
    699,
    701,
    688,
    705,
    1205,
    714,
    208,
    693,
    400,
    1214,
    1419,
    514,
    1226,
    34,
    262,
    211,
    695,
    700,
    1167,
    502,
    676,
    880,
    685,
    678,
    41,
    974,
    20,
    32,
    467,
    504,
    399,
    1176,
    497,
    506,
    22,
    215,
    159,
    1265,
    171,
    896,
    1049,
    1184,
    774,
    1426,
    498,
    1277,
    1028,
    891,
    271,
    1173,
    225,
    369,
    500,
    1407,
    357,
    274,
    1261,
    213,
    521,
    175,
    512,
    1326,
    1262,
    342,
    112,
    1224,
    1330,
    457,
    509,
    1126,
    1078,
    781,
    366,
    179,
    264,
    1037,
    1045,
    1313,
    1260,
    1040,
    1272,
    1333,
    1253,
    879,
    726,
    1001,
    1270,
    1325,
    354,
    1030,
    1318,
    691,
    352,
    1061,
    131,
    115,
    1216,
    1282,
    127,
    315,
    976,
    994,
    1082,
    313,
    1042,
    1229,
    802,
    1405,
    1070,
    1310,
    257,
    1417,
    755,
    1366,
    1324,
    365,
    1182,
    928,
    739,
    835,
    1234,
    364,
    790,
    1090,
    846,
    378,
    223,
    259,
    795,
    986,
    176,
    371,
    953,
    455,
    982,
    1185,
    1192,
    1301,
    247,
    139,
    376,
    1264,
    283,
    1266,
    1230,
    221,
    407,
    1285,
    1381,
    1414,
    1222,
    793,
    738,
    1170,
    1378,
    829,
    75,
    363,
    448,
    1034,
    1218,
    736,
    184,
    303,
    1063,
    1228,
    1320,
    905,
    1087,
    1194,
    1376,
    1022,
    123,
    163,
    436,
    1364,
    286,
    461,
    19,
    1409,
    355,
    772,
    392,
    980,
    1255,
    1322,
    361,
    445,
    1312,
    294,
    1076,
    989,
    834,
    1179,
    63,
    245,
    1178,
    1180,
    351,
    1314,
    797,
    881,
    261,
    340,
    751,
    1072,
    840,
    510,
    1278,
    459,
    220,
    272,
    844,
    925,
    23,
    884,
    1276,
    1303,
    397,
    743,
    281,
    831,
    27,
    1309,
    784,
    926,
    988,
    992,
    941,
    1124,
    843,
    173,
    770,
    263,
    929,
    932,
    52,
    833,
    997,
    28,
    927,
    1274,
    124,
    1165,
    944,
    111,
    129,
    783,
    451,
    207,
    856,
    893,
    1177,
    796,
    219,
    745,
    930,
    847,
    167,
    733,
    898,
    1075,
    1437,
    748,
    125,
    17,
    438,
    128,
    419,
    1418,
    749,
    938,
    1406,
    119,
    1174,
    1420,
    177,
    752,
    886,
    943,
    526,
    1068,
    185,
    234,
    285,
    722,
    838,
    1217,
    415,
    1157,
    104,
    1074,
    990,
    16,
    447,
    253,
    292,
    837,
    1166,
    1302,
    152,
    353,
    136,
    181,
    256,
    267,
    359,
    449,
    1003,
    1097,
    1371,
    87,
    275,
    403,
    1315,
    15,
    754,
    463,
    1156,
    35,
    857,
    209,
    1385,
    955,
    828,
    821,
    1267,
    165,
    1038,
    1273,
    799,
    823,
    800,
    836,
    1219,
    367,
    818,
    849,
    1181,
    1342,
    242,
    882,
    946,
    1,
    260,
    1168,
    1198,
    1294,
    47,
    390,
    61,
    680,
    1387,
    934,
    1308,
    940,
    788,
    867,
    1051,
    1080,
    1159,
    1436,
    1119,
    1354,
    939,
    255,
    735,
    73,
    517,
    866,
    1158,
    150,
    742,
    848,
    907,
    1327,
    29,
    113,
    1193,
    51,
    747,
    46,
    1084,
    1150,
    1164,
    769,
    841,
    1093,
    765,
    269,
    1186,
    1196,
    322,
    1370,
    1289,
    54,
    1337,
    764,
    1394,
    56,
    768,
    850,
    99,
    186,
    387,
    1026,
    814,
    1154,
    291,
    337,
    121,
    1169,
    3,
    147,
    284,
    325,
    240,
    169,
    1153,
)
ENGINE_SCAN_POSITION_ID_SET = frozenset(ENGINE_SCAN_POSITION_IDS)

START_PREFIX = "8/8/8/8/8/8/"
START_SUFFIX = " w - - 0 1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "server/fairy/racingkings.py"


def _canonical_source_text(lines: Iterable[str]) -> str:
    return "".join(f"{line.strip()}\n" for line in lines if line.strip())


def _load_source(source: Path | None) -> list[str]:
    if source is None:
        with urlopen(SOURCE_URL, timeout=30) as response:
            text = response.read().decode("utf-8")
    else:
        text = source.read_text(encoding="utf-8")

    canonical = _canonical_source_text(text.splitlines())
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(
            "Racing Kings source list does not match the pinned version: "
            f"expected {SOURCE_SHA256}, got {digest}"
        )

    fens = canonical.splitlines()
    if len(fens) != SOURCE_POSITION_COUNT:
        raise SystemExit(f"Expected {SOURCE_POSITION_COUNT} source positions, found {len(fens)}")
    if len(ENGINE_SCAN_POSITION_IDS) != ENGINE_SCAN_COUNT:
        raise SystemExit("Embedded engine-ranking position IDs are incomplete")
    if len(ENGINE_SCAN_POSITION_ID_SET) != ENGINE_SCAN_COUNT:
        raise SystemExit("Embedded engine-ranking position IDs contain duplicates")

    for position_id, fen in enumerate(fens):
        if not fen.startswith(START_PREFIX) or not fen.endswith(START_SUFFIX):
            raise SystemExit(f"Unexpected FEN at source position {position_id}: {fen}")
    return fens


def _partial_fen(fen: str) -> str:
    return fen[len(START_PREFIX) : -len(START_SUFFIX)]


def _board_map(fen: str) -> dict[str, str]:
    board: dict[str, str] = {}
    for row_index, row in enumerate(fen.split()[0].split("/")):
        rank = 8 - row_index
        file_index = 0
        for char in row:
            if char.isdigit():
                file_index += int(char)
                continue
            board[f"{chr(ord('a') + file_index)}{rank}"] = char
            file_index += 1
    return board


def _material_balance(fen: str) -> int:
    return sum(
        PIECE_VALUES[piece] if piece.isupper() else -PIECE_VALUES[piece]
        for piece in fen.split()[0]
        if piece in PIECE_VALUES
    )


def _apply_move(fen: str, move: str) -> str:
    return sf.get_fen("racingkings", fen, [move], True, False, False)


def _normalize_fen(fen: str) -> str:
    # The counters do not affect legality in these short lines.  Normalizing
    # them makes transpositions share the same cache entry.
    fields = fen.split()
    return " ".join([*fields[:4], "0", "1"])


def _legal_captures(fen: str, captured_pieces: str) -> list[tuple[int, str]]:
    board = _board_map(fen)
    captures: list[tuple[int, str]] = []
    for move in sf.legal_moves("racingkings", fen, [], True):
        target = board.get(move[2:4])
        if target is not None and target in captured_pieces:
            captures.append((PIECE_VALUES[target], move))
    captures.sort(reverse=True)
    return captures


def _immediate_material_gain(fen: str) -> int:
    """Best material White can guarantee after one move and Black's reply."""
    best_net = 0
    for captured_value, white_move in _legal_captures(fen, "qrbn"):
        after_white = _apply_move(fen, white_move)
        black_recovery = max(
            (value for value, _move in _legal_captures(after_white, "QRBN")),
            default=0,
        )
        best_net = max(best_net, captured_value - black_recovery)
    return best_net


def _can_force_shallow_material_win(fen: str) -> bool:
    """Return whether White can force >3 material within MAX_TACTICAL_PLIES.

    White may choose captures only.  Black may choose any legal reply, so every
    branch must preserve White's material win for the position to qualify.
    """
    white_capture_moves = MAX_TACTICAL_PLIES // 2

    @cache
    def can_force(position: str, captures_left: int) -> bool:
        if _material_balance(position) > MATERIAL_ADVANTAGE_THRESHOLD:
            return True
        if captures_left <= 0:
            return False

        for _captured_value, white_move in _legal_captures(position, "qrbn"):
            after_white = _apply_move(position, white_move)
            black_moves = sf.legal_moves("racingkings", after_white, [], True)
            if not black_moves:
                if _material_balance(after_white) > MATERIAL_ADVANTAGE_THRESHOLD:
                    return True
                continue

            black_board = _board_map(after_white)
            ordered_black_moves: list[tuple[int, str]] = []
            for black_move in black_moves:
                target = black_board.get(black_move[2:4])
                recovery = (
                    PIECE_VALUES.get(target, 0) if target is not None and target in "QRBN" else 0
                )
                ordered_black_moves.append((recovery, black_move))
            ordered_black_moves.sort(reverse=True)

            forced = True
            for _recovery, black_move in ordered_black_moves:
                after_black = _normalize_fen(_apply_move(after_white, black_move))
                if _material_balance(after_black) > MATERIAL_ADVANTAGE_THRESHOLD:
                    continue
                if captures_left > 1 and can_force(after_black, captures_left - 1):
                    continue
                forced = False
                break
            if forced:
                return True

        return False

    return can_force(_normalize_fen(fen), white_capture_moves)


def _classify_start(job: tuple[int, str]) -> tuple[int, bool, bool]:
    position_id, fen = job
    immediate = _immediate_material_gain(fen) > 0
    shallow = False
    if not immediate and position_id in ENGINE_SCAN_POSITION_ID_SET:
        shallow = _can_force_shallow_material_win(fen)
    return position_id, immediate, shallow


def _render_module(retained: list[tuple[int, str]]) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "# Generated by scripts/generate_racingkings960_fens.py. Do not edit manually.",
        "# Source IDs are the original 0..1439 RKK1440FENS.txt position numbers.",
        f"# Retained {len(retained)} / {SOURCE_POSITION_COUNT} starts; excluded {EXPECTED_TOTAL_EXCLUSIONS}.",
        "",
        "RACINGKINGS_STARTS = (",
    ]
    lines.extend(f'    ({position_id}, "{_partial_fen(fen)}"),' for position_id, fen in retained)
    lines.extend(
        [
            ")",
            "",
            "RACINGKINGS_FENS = tuple(fen for _position_id, fen in RACINGKINGS_STARTS)",
            "RACINGKINGS_FEN_TO_ID = {fen: position_id for position_id, fen in RACINGKINGS_STARTS}",
            "",
        ]
    )
    return "\n".join(lines)


def _generate(source_fens: list[str], workers: int) -> tuple[str, list[int]]:
    jobs = list(enumerate(source_fens))
    if workers == 1:
        results = [_classify_start(job) for job in jobs]
    else:
        with Pool(processes=workers) as pool:
            results = list(pool.imap_unordered(_classify_start, jobs, chunksize=1))
        results.sort()

    immediate_ids = {position_id for position_id, immediate, _shallow in results if immediate}
    shallow_ids = {position_id for position_id, _immediate, shallow in results if shallow}
    excluded_ids = immediate_ids | shallow_ids

    actual = (
        len(immediate_ids),
        len(shallow_ids),
        len(excluded_ids),
        SOURCE_POSITION_COUNT - len(excluded_ids),
    )
    expected = (
        EXPECTED_IMMEDIATE_EXCLUSIONS,
        EXPECTED_ADDITIONAL_SHALLOW_EXCLUSIONS,
        EXPECTED_TOTAL_EXCLUSIONS,
        EXPECTED_RETAINED_STARTS,
    )
    if actual != expected:
        raise SystemExit(
            "Filter result changed; review pyffish/source changes before regenerating: "
            f"expected immediate/additional-shallow/total/retained={expected}, got {actual}"
        )

    retained = [
        (position_id, fen)
        for position_id, fen in enumerate(source_fens)
        if position_id not in excluded_ids
    ]
    return _render_module(retained), sorted(excluded_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="Local RKK1440FENS.txt. Downloads the pinned GitHub source if omitted.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Generated module path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="Worker processes used for classification (default: up to 8).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated module differs from --output.",
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    source_fens = _load_source(args.source)
    generated, excluded_ids = _generate(source_fens, args.workers)

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != generated:
            raise SystemExit(f"{args.output} is out of date")
        print(f"{args.output} is up to date ({len(excluded_ids)} exclusions)")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"Wrote {args.output}: {EXPECTED_RETAINED_STARTS} retained, {len(excluded_ids)} excluded")


if __name__ == "__main__":
    main()
