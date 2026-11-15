#!/usr/bin/env bash
# Read-only HTTP requests and -a test-user bot games against LOCAL DEV ONLY.
# Run in the second terminal after scripts/profile_local_server.py prints "Sampling".
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DEFAULT_PYTHON="$ROOT/.venv-py315/bin/python"
if [[ ! -x "$DEFAULT_PYTHON" ]]; then
  DEFAULT_PYTHON="$ROOT/.venv/bin/python"
fi
PYTHON="${PYCHESS_PROFILE_PYTHON:-$DEFAULT_PYTHON}"
if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" >&2
  exit 1
fi
ulimit -n 10000 2>/dev/null || true
export PYTHONPATH="$ROOT/server:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"
OPTIONS=(
  --users 20 --games-per-user 1 --user-start-spread-secs 12
  --spectators-per-game 6 --featured-games 1 --spectators-regular-per-game 2
  --max-spectator-http-concurrency 12
  --http-rps 2 --http-concurrency 4 --http-duration-secs 110
  --run-duration-secs 110
  --pgn-max-games 100 --test-user-pgn
)
echo "Will export one completed Test–* user's own PGNs using its test session."
COOKIE_FILE="${PYCHESS_STRESS_PGN_COOKIE_FILE:-$HOME/.config/pychess/stress-session-cookie}"
if [[ -f "$COOKIE_FILE" ]]; then
  echo "Will request up to 100 authenticated gbtami PGNs from local DEV."
  OPTIONS+=(--pgn-cookie-file "$COOKIE_FILE")
else
  echo "No gbtami cookie file; skipping optional large gbtami PGN export."
fi
exec "$PYTHON" tests/client_stresstest.py "${OPTIONS[@]}" "$@"
