# Bring Your Own Chess Engine to PyChess!

**Powerful native analysis and community-run BOT opponents**

Ever wished you could analyze your favorite chess variant with the full power of your computer—or challenge an engine built specifically for that variant? Now you can do both on PyChess.

We're introducing **external analysis engines**, which connect a native engine on your computer to the familiar PyChess analysis board. We're also highlighting **community-run BOT accounts**: an existing feature that lets you host an engine for other players to challenge.

## Faster analysis, more choice

PyChess's built-in Fairy-Stockfish engine runs directly in your browser through WebAssembly (WASM). It's wonderfully convenient: there's nothing to install, and you can start analyzing with a click.

But WebAssembly isn't always the fastest way to use your hardware, and Fairy-Stockfish isn't the only engine worth exploring. With the new [PyChess External Engine](https://github.com/pychess/pychess-external-engine) companion application, you can run a native UCI engine on your own computer and see its analysis directly in PyChess.

A native build may search substantially faster than the browser build, depending on the engine, CPU, position and settings. It also opens the door to specialized engines for particular variants.

**Tested with the external-analysis integration:**

- **[Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish)** — native analysis for its many supported chess variants.
- **[Alice-Stockfish](https://github.com/Belzedar94/Alice-Stockfish)** by Belzedar94 — a dedicated engine for the unusual two-board world of Alice Chess.

**Other engines to explore — compatibility with external analysis is unverified:**

- **[MBCA-10x10](https://github.com/romstad/mbca-10x10)** by Tord Romstad — an engine for Grand Chess.
- **[wakwak](https://github.com/Silverrzz/wakwak)** by Silverrzz — an engine for Duck Chess.
- **[Pikafish](https://github.com/official-pikafish/Pikafish)** — a strong UCI engine for Xiangqi, derived from Stockfish.

These are interesting candidates for further testing. Compatibility depends on the engine's protocol and supported rules; supporting the same variant alone isn't enough.

### How much faster?

![Browser Fairy-Stockfish analysis: depth 22 and 388 knodes per second.](/static/images/bring-your-own-engine/fairy-stockfish-browser.png)

![Native Fairy-Stockfish analysis: depth 23 and 871 knodes per second.](/static/images/bring-your-own-engine/fairy-stockfish-native.png)

*Above: The same position with one thread, 64 MB hash, one variation and NNUE disabled. The browser (14+) and native (130726) engines are different Fairy-Stockfish builds, so this illustrates one setup rather than a controlled benchmark.*

**NPS** means *nodes per second*: how many search-tree nodes the engine investigates each second. The panel shows **knodes/s**, or thousands of nodes per second—about 388,000 in the browser and 871,000 natively in this example. Results vary with the engine, hardware and settings; a higher NPS figure alone doesn't establish greater playing strength.

## Connect your local engine

You'll need [uv](https://docs.astral.sh/uv/getting-started/installation/), a native UCI engine executable, and a PyChess account.

1. Open **[Account → External engines](https://www.pychess.org/account/engines)** and create an engine token. Save it in a local text file.
2. Download or build the engine you want to run.
3. Start the external-engine companion app from a terminal.
4. Open a PyChess analysis board and click the gear beside the analysis engine. Select your registered engine and allow local access if the browser requests it.
5. Turn on the analysis switch to start the engine.

For example, to analyze Alice Chess with Alice-Stockfish and its compatible NNUE network:

```bash
uvx pychess-external-engine \
  --engine /path/to/alice-stockfish \
  --setoption EvalFile /path/to/Alice_v1.nnue \
  --token-file /path/to/your-token
```

Or, with native Fairy-Stockfish:

```bash
uvx pychess-external-engine \
  --engine /path/to/fairy-stockfish \
  --token-file /path/to/your-token
```

Replace the paths with those on your computer, and keep the companion app running during analysis. The engine and any required NNUE network are supplied separately. You can switch back to the built-in browser engine at any time.

The companion app has been verified on Linux x86-64 with Chromium, Edge and Firefox. Windows, macOS and Safari remain unverified; see the [installation guide](https://github.com/pychess/pychess-external-engine/blob/main/docs/installation.md) and [compatibility notes](https://github.com/pychess/pychess-external-engine/blob/main/docs/compatibility.md) for details.

![Alice Chess opening analysis with Alice-Stockfish 1.0 running natively.](/static/images/bring-your-own-engine/alice-stockfish-analysis.png)

## Let other players challenge your engine

To let other players challenge your engine to games, use the [PyChess BOT bridge](https://github.com/gbtami/pychess-bot).

Community members already run dedicated BOT accounts on PyChess, including:

- **[MBCA-Grand](https://www.pychess.org/@/MBCA-Grand)**, Tord Romstad's Grand Chess BOT, powered by [MBCA-10x10](https://github.com/romstad/mbca-10x10), a UCI engine whose evaluation network was trained using Jamie Whiting's [bullet](https://github.com/jw1912/bullet) library.
- **[sin-san](https://www.pychess.org/@/sin-san)** for Janggi, powered by [Sinsan](https://github.com/VectorSophie/sinsan), an AlphaZero-style engine combining a neural network with Monte Carlo tree search.
- **[Prolix](https://www.pychess.org/@/Prolix)** for Shatranj, powered by Chris Bao's [Prolix engine](https://github.com/sscg13/Prolix), an open-source UCI/XBoard engine with NNUE evaluation.

This feature has been available for a while; we're giving it the announcement it deserves.

Your engine and the BOT bridge run on a computer you control. The BOT can accept challenges according to your settings while both remain online.

### Set up your own PyChess BOT

First, create a **separate PyChess account that has never played a game**. Sign in to that account and open **[Account → BOT account tools](https://www.pychess.org/account/bot)** to create a BOT API token. Keep it private. External-analysis tokens cannot be used to run a BOT.

With Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, download and set up the BOT bridge:

```bash
git clone https://github.com/gbtami/pychess-bot.git
cd pychess-bot
uv sync --locked
cp config.yml.default config.yml
```

On Windows, copy `config.yml.default` to `config.yml` using your file manager instead of the `cp` command.

Edit the **copied** `config.yml`, including the following fields, while retaining its other defaults:

```yaml
token: "YOUR_PYCHESS_BOT_TOKEN"
url: "https://www.pychess.org/"
engine:
  dir: "./engines/"
  name: "YOUR_ENGINE_EXECUTABLE"
  protocol: "uci"
```

Place a suitable native engine executable in the configured directory and set the engine-specific options and accepted variants as described in the [BOT quick-start guide](https://github.com/gbtami/pychess-bot/blob/pychess-bot/docs/pychess-quickstart.md).

Before starting the BOT, perform the one-time account conversion using **Upgrade to BOT** on the [BOT account tools page](https://www.pychess.org/account/bot). Alternatively, run:

```bash
uv run python lichess-bot.py -u
```

Then start your BOT:

```bash
uv run python lichess-bot.py
```

The filename `lichess-bot.py` comes from [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot), the open-source project our PyChess fork is based on. **Keep `url` set to `https://www.pychess.org/`** so the bridge connects to PyChess.

## Your computer, your engine, your choice

These two tools make PyChess more flexible for both players and engine developers. Use a powerful native engine for in-depth analysis, experiment with a specialized engine for an unusual variant, or run a BOT so the community can test its strength over the board.

External analysis keeps engine search local to your computer; you don't need to expose a public engine server. As always, engine assistance is **not permitted in ongoing games played by human accounts**.

For full instructions, see [PyChess External Engine](https://github.com/pychess/pychess-external-engine) and [PyChess BOT](https://github.com/gbtami/pychess-bot). Thanks to the developers of Fairy-Stockfish, the specialized variant engines, lichess-bot, and everyone contributing to open-source chess software.

**Happy analyzing—and happy playing against new BOT opponents!**
