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

INSTALL_OPTIONS=()
# Optional local CPython 3.15 wheels (PyPI is used by default).
if [[ -n "${PYCHESS_CP315_WHEELS:-}" ]]; then
  if [[ ! -d "$PYCHESS_CP315_WHEELS" ]]; then
    echo "Wheel directory does not exist: $PYCHESS_CP315_WHEELS" >&2
    exit 1
  fi
  INSTALL_OPTIONS+=(--find-links "$PYCHESS_CP315_WHEELS")
fi

# Build from the GitHub v0.3.1 release's source archive. PyPI has neither a
# compatible wheel nor a source distribution for this version. uv caches the
# build; repeat runs normally reuse the installed package.
if ! "$PYTHON" -c 'from importlib.metadata import version; from py4swiss.engines import DutchEngine; assert version("py4swiss") == "0.3.1"' >/dev/null 2>&1; then
  if ! command -v g++ >/dev/null 2>&1; then
    echo "Building py4swiss needs a C++ compiler (g++)." >&2
    echo "On Ubuntu: sudo apt install build-essential" >&2
    exit 1
  fi
fi

# Resolve runtime requirements for this interpreter independently of uv.lock.
# In particular, Pydantic and its exactly pinned core must resolve together to
# releases with CPython 3.15 wheels. The override supplies py4swiss's source.
# Require wheels for the engines and native dependencies with known 3.15 wheels;
# source-only packages (including py4swiss) may still build normally.
echo "Installing PyChess runtime dependencies for Python 3.15 (independent of uv.lock)..."
uv pip install --python "$PYTHON" "${INSTALL_OPTIONS[@]}" \
  --requirement "$ROOT/pyproject.toml" \
  --overrides "$ROOT/requirements/python315-overrides.in" \
  --only-binary pyffish --only-binary pyffish-alice \
  --only-binary pydantic-core --only-binary cffi \
  --only-binary numpy --only-binary markupsafe

# Verify the binary modules used by the server before launching the profiler.
"$PYTHON" - <<'PY'
from importlib.metadata import version
from py4swiss.engines import DutchEngine
import pydantic_core
import pyffish
import pyffish_alice

assert version("py4swiss") == "0.3.1"
print(f'pydantic=={version("pydantic")}')
print(f'pydantic-core=={version("pydantic-core")}')
print(f'pyffish=={version("pyffish")}')
print(f'pyffish-alice=={version("pyffish-alice")}')
print("Python 3.15 native packages imported successfully.")
PY

echo "Starting local Tachyon profiler..."
exec "$PYTHON" scripts/profile_local_server.py "$@"
