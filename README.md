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

Server and browser engine support are separate capabilities; see [docs/Engine-Capabilities.md](docs/Engine-Capabilities.md).

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


## Supported browsers

Pychess-variants should support almost all browsers. Though older browsers (including any version of Internet Explorer) will not work. For your own sake, please upgrade. Security and performance, think about it!

Only [Fairy-Stockfish analysis](https://www.pychess.org/analysis/chess) might not work on all browsers.
