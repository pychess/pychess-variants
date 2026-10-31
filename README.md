## [www.pychess.org](https://www.pychess.org)

[![Python-CI](https://github.com/pychess/pychess-variants/actions/workflows/ci.yml/badge.svg)](https://github.com/pychess/pychess-variants/actions/workflows/ci.yml)
[![Nodejs-CI](https://github.com/pychess/pychess-variants/actions/workflows/nodejs.yml/badge.svg)](https://github.com/pychess/pychess-variants/actions/workflows/nodejs.yml)
[![Discord](https://img.shields.io/discord/634298688663191582?label=Discord&logo=discord&style=flat)](https://discord.gg/aPs8RKr)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pychess/pychess-variants)

---
![pychess-variants.png](https://github.com/pychess/pychess-variants/blob/c9617275f6f927b5a15d4424c4a847a73489c805/static/images/pychess-variants.png)

Pychess-variants is a free, open-source chess server designed to play chess variants.

Currently supported games are listed on https://www.pychess.org/variants

For move generation, validation, analysis and engine play it uses:
- [Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish)
- [fairy-stockfish.wasm](https://github.com/fairy-stockfish/fairy-stockfish.wasm)
- [fairyfishnet](https://github.com/gbtami/fairyfishnet) fork of [fishnet](https://github.com/lichess-org/fishnet)

On client side it is based on
[chessgroundx](https://github.com/gbtami/chessgroundx) fork of [chessground](https://github.com/lichess-org/chessground)

##

As you know, pychess-variants is a free server and it will remain free forever. However, maintaining and improving the server costs time and money.

If you like our work and find our server useful, please donate through [Patreon](https://www.patreon.com/pychess) or directly through [paypal](https://www.paypal.com/paypalme/gbtami) !!
Your contribution will be greatly appreciated and help me continue to develop this awesome server.

## Installation

### Prerequisites
* You need MongoDB up and running. [Mongo daemon](https://www.mongodb.com/docs/manual/installation/)


### Project setup
```bash
# Sync Python dependencies into the project virtualenv
uv sync --extra dev

# Optionally activate the virtualenv for interactive work
source .venv/bin/activate

yarn install                            # Install node requirements
yarn dev                                # Compile typescript files to javascript
yarn md                                 # Compile md files to html
```

All Python commands below should be run with `uv run ...` unless you have already activated `.venv`.

The project now targets Python 3.14+.

### TypeScript and JavaScript checks
```bash
yarn format
yarn check-format
yarn lint
yarn typecheck
yarn test
```

### Start server
```bash
uv run server/server.py
```

### Python checks and tests
```bash
uv run ruff format --target-version py313 .
uv run ruff check .
uv run pyrefly check
env PYTHONPATH=server uv run python -m unittest discover -s tests
env PYTHONPATH=server:tests uv run python -m unittest tests.some_test_module
uv run python -m playwright install
env PYTHONPATH=server uv run python -m pytest tests/test_e2e.py
env PYTHONPATH=server uv run python -m pytest tests/test_gui.py
```

### Docker setup
If you want to avoid installing dependencies (mongo, node, python) you can instead run the server locally in docker using compose. To start it, simply run:
```bash
docker compose up --build
```
This recompiles the frontend and starts the server and DB. Once it is up, you can connect to `localhost:8080` in your browser.
For more detailed Docker workflows, including contributor checks and the optional `ci` service, see [docker/README.md](docker/README.md).

### Import a blog on behalf of its author

`scripts/migrate_legacy_blogs_to_ublog.py` imports into the current `ublog_post2`
collection. It defaults to a dry run without connecting to MongoDB. Existing posts
are skipped, preserving browser edits, publication state, views, and likes.

For a Markdown file that is absent from `server/blog_legacy_metadata.json`, provide
the author's exact PyChess username and explicit metadata. For example:

```bash
env PYTHONPATH=server uv run python scripts/migrate_legacy_blogs_to_ublog.py \
  --markdown-file 'static/blogs/Yokai Halloween.md' \
  --author CouchTomato87 \
  --title 'Yokai Shogi Arrives for Halloween!' \
  --intro 'New variants' \
  --date 2026-10-31 \
  --image /static/images/Hyakki.jpg \
  --image-alt 'Yokai parade' \
  --topics announcement,shogi \
  --official --publish
```

Review the preview, set `MONGO_HOST` in your environment to the production MongoDB
URI, and repeat with `--apply` to write. The database defaults to `pychess-variants`;
use `--mongo-db` to override it. The author must already have an enabled account.
Run the command from a checkout containing the intended version of the Markdown
file and its images.

Omit `--publish` to create an unpublished draft owned by the author. With
`--publish`, the post becomes visible immediately; `--date` sets its date and does
not schedule publication. Choose the intended date explicitly: dates embedded in
the old HTML preamble are discarded. `--official` includes the post in the site
blog stream while retaining the supplied author. This utility does not emit a
follower timeline event or create a discussion topic.

The file name determines the stable legacy ID (`Yokai_Halloween` above). Use
`--blog-id` with a file to override that ID, or use `--blog-id ID` alone to select
exactly one existing catalog entry. Without either selector, the script imports
the legacy catalog, with optional `--from-id`, `--limit`, and `--author-policy`.
Legacy HTML is converted to the strict Markdown format used by the current site.
