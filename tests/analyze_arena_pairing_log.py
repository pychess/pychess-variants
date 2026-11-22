"""Summarize measured Arena pairing CPU/wall time from the real server's INFO log.

Usage: python tests/analyze_arena_pairing_log.py /tmp/pychess-arenas-server.log
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path

PAIRING_RE = re.compile(
    r"ARENA_PAIRING tid=(?P<tid>\w{8}) waiting=(?P<waiting>\d+) "
    r"edges=(?P<edges>\d+) paired=(?P<paired>\d+) "
    r"cpu_ms=(?P<cpu>[0-9.]+) wall_ms=(?P<wall>[0-9.]+)"
)


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    pos = (len(ordered) - 1) * fraction
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Captured pychess server log")
    args = parser.parse_args()
    waves: dict[str, list[dict[str, float]]] = defaultdict(list)
    for line in args.file.read_text(encoding="utf-8", errors="replace").splitlines():
        if match := PAIRING_RE.search(line):
            groups = match.groupdict()
            waves[groups["tid"]].append(
                {key: float(value) for key, value in groups.items() if key != "tid"}
            )
    if not waves:
        raise SystemExit("No ARENA_PAIRING entries found; confirm INFO server logging is enabled")
    for tid, rows in sorted(waves.items()):
        cpu = [row["cpu"] for row in rows]
        wall = [row["wall"] for row in rows]
        print(
            f"arena={tid} pairing_calls={len(rows)} "
            f"max_waiting={int(max(row['waiting'] for row in rows))} "
            f"max_edges={int(max(row['edges'] for row in rows))} "
            f"total_pairs={int(sum(row['paired'] for row in rows))} "
            f"cpu_ms_p50={percentile(cpu, 0.50):.2f} "
            f"cpu_ms_p95={percentile(cpu, 0.95):.2f} "
            f"cpu_ms_max={max(cpu):.2f} "
            f"wall_ms_p95={percentile(wall, 0.95):.2f}"
        )


if __name__ == "__main__":
    main()
