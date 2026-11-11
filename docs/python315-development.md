# Optional local Python 3.15

Use a current uv release (0.13.7 or newer) and a C++ compiler for the source-built
py4swiss and pyffish-alice dependencies. Create a separate environment:

```bash
uv python install 3.15
uv venv --python 3.15 .venv-3.15
uv pip install --python .venv-3.15/bin/python -r pyproject.toml --extra dev \
  --overrides requirements/python315-overrides.in \
  --find-links "$HOME/pyffish-wheels"
source .venv-3.15/bin/activate
python server/server.py
# Or start the server with the sampling profiler:
python -m profiling.sampling run server/server.py
```

The local overrides select pyffish 0.0.91 (from local wheels until published) and
the py4swiss 0.3.1 GitHub source archive. Other dependencies resolve from PyPI.
After activation, use plain `python`, `pytest`, `ruff`, and `pyrefly`, or
`uv run --active --no-sync --python 3.15` to preserve the local dependency selection.
The default `.python-version` stays at 3.14 for Heroku; this setup does not sync or
update the production lockfile.
