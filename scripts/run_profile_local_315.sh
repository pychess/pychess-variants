#!/usr/bin/env bash
# Set up an isolated CPython 3.15 environment and start local Tachyon profiling.
# Does not modify .venv, .python-version, pyproject.toml, or uv.lock.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv-py315"
PYTHON="$VENV/bin/python"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  if [[ -e "$VENV" ]]; then
    echo "$VENV exists but is not a usable virtual environment; inspect it before retrying." >&2
    exit 1
  fi
  uv venv --python 3.15 "$VENV"
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 15) else 1)'; then
  echo "Expected Python 3.15 in $VENV; existing environment was not modified." >&2
  exit 1
fi

echo "Using $("$PYTHON" --version) at $PYTHON"

# Preserve locked dependencies except for the three native modules. py4swiss
# has no CPython 3.15 wheel or sdist on PyPI; pyffish/pyffish-alice need the
# newer CPython 3.15 wheels, which may have different versions than uv.lock.
# This export does not modify uv.lock or the regular .venv.
REQUIREMENTS="$(mktemp "${TMPDIR:-/tmp}/pychess-profile-reqs.XXXXXXXX.txt")"
trap 'rm -f "$REQUIREMENTS"' EXIT
uv export --frozen --no-dev --no-emit-project \
  --no-emit-package py4swiss \
  --no-emit-package pyffish \
  --no-emit-package pyffish-alice \
  --no-hashes --no-header --no-annotate --output-file "$REQUIREMENTS"

INSTALL_OPTIONS=()
# Optional local CPython 3.15 wheels (PyPI is used by default).
if [[ -n "${PYCHESS_CP315_WHEELS:-}" ]]; then
  if [[ ! -d "$PYCHESS_CP315_WHEELS" ]]; then
    echo "Wheel directory does not exist: $PYCHESS_CP315_WHEELS" >&2
    exit 1
  fi
  INSTALL_OPTIONS+=(--find-links "$PYCHESS_CP315_WHEELS")
fi

echo "Installing locked PyChess runtime dependencies (excluding native overrides)..."
uv pip install --python "$PYTHON" "${INSTALL_OPTIONS[@]}" --requirement "$REQUIREMENTS"

# Prefer released CPython 3.15 wheels from PyPI. Require binary wheels so a
# missing release fails clearly rather than silently compiling Fairy-Stockfish.
echo "Installing CPython 3.15 pyffish and pyffish-alice wheels from PyPI..."
uv pip install --python "$PYTHON" "${INSTALL_OPTIONS[@]}" \
  --only-binary pyffish --only-binary pyffish-alice \
  --upgrade pyffish pyffish-alice

# Build from the GitHub v0.3.1 release's source archive. PyPI has neither a
# compatible wheel nor a source distribution for this version. uv caches the
# build; repeat runs normally reuse the installed package.
if ! "$PYTHON" -c 'from importlib.metadata import version; from py4swiss.engines import DutchEngine; assert version("py4swiss") == "0.3.1"' >/dev/null 2>&1; then
  if ! command -v g++ >/dev/null 2>&1; then
    echo "Building py4swiss needs a C++ compiler (g++)." >&2
    echo "On Ubuntu: sudo apt install build-essential" >&2
    exit 1
  fi
  echo "Building py4swiss 0.3.1 from the GitHub release source archive..."
  uv pip install --python "$PYTHON" --no-deps \
    'https://github.com/Moritz72/py4swiss/archive/refs/tags/v0.3.1.tar.gz'
fi

# Verify the binary modules used by the server before launching the profiler.
"$PYTHON" - <<'PY'
from importlib.metadata import version
from py4swiss.engines import DutchEngine
import pyffish
import pyffish_alice

assert version("py4swiss") == "0.3.1"
print(f'pyffish=={version("pyffish")}')
print(f'pyffish-alice=={version("pyffish-alice")}')
print("Python 3.15 native packages imported successfully.")
PY

echo "Starting local Tachyon profiler..."
exec "$PYTHON" scripts/profile_local_server.py "$@"
