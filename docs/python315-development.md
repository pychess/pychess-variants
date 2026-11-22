# Optional local Python 3.15

Update uv first: older releases such as 0.11.7 only know the Python 3.15 alpha
builds. The commands below use `uv self update` for a standalone uv installation;
if uv was installed through a package manager, update it through that manager.
Use uv 0.13.7 or newer and a C++ compiler for the source-built py4swiss and
pyffish-alice dependencies. Create a separate environment using the tested patch version:

```bash
uv self update
uv --version                        # 0.13.7 or newer
uv python install 3.15.2
uv venv --python 3.15.2 .venv-3.15
.venv-3.15/bin/python --version      # Python 3.15.2
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
