"""Loopback JS/WASM transfers alongside the crawler; never fetch external assets."""

from __future__ import annotations

import asyncio
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import aiohttp

PRODUCTION_STATIC_ROOT = "https://cdn.jsdelivr.net/gh/pychess/pychess-variants@1.11.88/static"


class PageAssets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        url = (
            values.get("src") if tag == "script" else values.get("href") if tag == "link" else None
        )
        if url and urlsplit(url).path.endswith((".js", ".wasm")):
            self.urls.append(url)


def local_asset_path(base: str, value: str) -> str | None:
    origin = urlsplit(base)
    asset = urlsplit(urljoin(base, value))
    if (asset.scheme, asset.netloc) != (origin.scheme, origin.netloc):
        return None
    if not asset.path.startswith("/static/") or not asset.path.endswith((".js", ".wasm")):
        return None
    return asset.path + (f"?{asset.query}" if asset.query else "")


def slow_socket(address):
    family, kind, protocol, _, _ = address
    sock = socket.socket(family, kind, protocol)
    # Also bound kernel buffering: sleeping between reads alone can let a small
    # file finish sending into the client's socket buffer immediately.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
    return sock


class AssetLoad:
    def __init__(self, run) -> None:
        self.run = run
        self.files: list[dict] = []
        self.external: list[str] = []
        self.inflight = 0
        self.peak_inflight = 0
        self.timings: dict[str, dict[str, float]] = {}

    async def prepare(self) -> None:
        args = self.run.args
        base = self.run.fixture["url"]
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=args.timeout),
        ) as session:
            async with session.get(
                base + "/analysis/chess", headers=self.run.probe_headers(), allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Asset discovery page returned {response.status}")
                try:
                    html = await response.content.readexactly(1024 * 1024 + 1)
                except asyncio.IncompleteReadError as exc:
                    html = exc.partial
                if len(html) > 1024 * 1024:
                    raise RuntimeError("Asset discovery page exceeds 1 MiB")
            parser = PageAssets()
            parser.feed(html.decode("utf-8"))
            paths: dict[str, str] = {}
            for value in parser.urls:
                path = local_asset_path(base, value)
                if path is None:
                    self.external.append(value)
                else:
                    paths[urlsplit(path).path.rsplit("/", 1)[1]] = path
            if "pychess-variants.js" not in paths or "ffish.wasm" not in paths:
                raise RuntimeError("Analysis page did not reference local main JS and ffish WASM")
            version = urlsplit(paths["pychess-variants.js"]).query
            # Runtime-loaded assets: fairyStockfish.ts, headerRealtime.ts,
            # ongoingRealtime.ts, and the Alice rules module in main.ts.
            for name in (
                "stockfish.js",
                "stockfish.wasm",
                "stockfish.worker.js",
                "ffish-alice.wasm",
                "header-realtime-worker.js",
                "ongoing-realtime-worker.js",
            ):
                query = f"?{version}" if version and not name.startswith("stockfish.") else ""
                paths.setdefault(name, f"/static/{name}{query}")
            for name, path in paths.items():
                kind = "wasm" if name.endswith(".wasm") else "js"
                if args.asset_kind not in {"all", kind}:
                    continue
                async with session.head(
                    base + path,
                    headers={**self.run.probe_headers(), "Accept-Encoding": args.asset_encoding},
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(
                            f"Asset {name} returned {response.status}; run yarn prod"
                        )
                    expected_type = "application/wasm" if kind == "wasm" else "javascript"
                    if expected_type not in response.headers.get("Content-Type", ""):
                        raise RuntimeError(f"Asset {name} has unexpected Content-Type")
                    if args.asset_cache != "cold" and not response.headers.get("ETag"):
                        raise RuntimeError(f"Asset {name} lacks an ETag for conditional requests")
                    self.files.append(
                        {
                            "name": name,
                            "path": path,
                            "kind": kind,
                            "wire_bytes": int(response.headers.get("Content-Length", 0)),
                            "encoding": response.headers.get("Content-Encoding", "identity"),
                            "etag": response.headers.get("ETag"),
                            "cache_control": response.headers.get("Cache-Control"),
                        }
                    )
            if not self.files:
                raise RuntimeError("No JS/WASM assets selected")

    async def transfer(self, session, asset: dict, index: int, stats) -> None:
        args = self.run.args
        headers = {
            "Accept-Encoding": args.asset_encoding,
            "X-Forwarded-For": (
                f"198.19.{(index // 254) % 254}.{index % 254 + 1}"
                if args.identity == "rotate"
                else "198.19.0.1"
            ),
            "User-Agent": "LocalCrawlerAssetSimulation/1",
        }
        warm = args.asset_cache == "warm" or (
            args.asset_cache == "mixed" and ((index - 1) // len(self.files)) % 2 == 1
        )
        if warm:
            if not asset["etag"]:
                raise RuntimeError("Warm asset requests require an ETag")
            headers["If-None-Match"] = asset["etag"]
        self.inflight += 1
        self.peak_inflight = max(self.peak_inflight, self.inflight)
        started = time.monotonic()
        received = 0
        try:
            async with session.get(
                self.run.fixture["url"] + asset["path"], headers=headers, allow_redirects=False
            ) as response:
                stats.headers.add((time.monotonic() - started) * 1000)
                body_started = time.monotonic()
                status: int | str = response.status
                async for chunk in response.content.iter_chunked(16384):
                    stats.received_bytes += len(chunk)
                    received += len(chunk)
                    if args.asset_kib_per_second:
                        delay = max(
                            0,
                            received / (args.asset_kib_per_second * 1024)
                            - (time.monotonic() - body_started),
                        )
                        if delay:
                            try:
                                await asyncio.wait_for(self.run.stop_load.wait(), timeout=delay)
                            except TimeoutError:
                                pass
                    if self.run.stop_load.is_set():
                        status = "Stopped"
                        break
                if status == 200 and received != asset["wire_bytes"]:
                    status = "BodySizeMismatch"
                if warm and status == 200:
                    status = "Expected304"
        except (aiohttp.ClientError, TimeoutError) as exc:
            status = type(exc).__name__
        finally:
            self.inflight -= 1
        stats.record(status, (time.monotonic() - started) * 1000)

    async def flood(self, seconds: float) -> None:
        args = self.run.args
        tasks: set[asyncio.Task] = set()
        offered = self.run.requests("asset_load")
        started = time.monotonic()
        deadline = started + seconds
        scheduled = started
        index = 0

        def finished(task):
            tasks.discard(task)
            if not task.cancelled() and (error := task.exception()) is not None:
                self.run.failures.append(f"asset task failed: {type(error).__name__}")

        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            connector=aiohttp.TCPConnector(
                limit=args.asset_concurrency,
                socket_factory=slow_socket if args.asset_kib_per_second else None,
            ),
            timeout=aiohttp.ClientTimeout(total=args.asset_timeout),
            auto_decompress=False,
            read_bufsize=16384,
        ) as session:
            try:
                while scheduled < deadline and not self.run.stop_load.is_set():
                    await asyncio.sleep(max(0, scheduled - time.monotonic()))
                    if self.run.stop_load.is_set():
                        break
                    missed = max(0, int((time.monotonic() - scheduled) * args.asset_rps))
                    offered.offered += 1 + missed
                    offered.client_dropped += missed
                    scheduled += (1 + missed) / args.asset_rps
                    index += 1 + missed
                    if len(tasks) >= args.asset_concurrency:
                        offered.client_dropped += 1
                        continue
                    asset = self.files[(index - 1) % len(self.files)]
                    stats = self.run.requests("asset:" + asset["name"])
                    stats.offered += 1
                    task = asyncio.create_task(self.transfer(session, asset, index, stats))
                    tasks.add(task)
                    task.add_done_callback(finished)
                offering_finished = time.monotonic()
                # Keep probes/telemetry running while outstanding transfers drain.
                # The attack phase includes this bounded, asset-timeout-limited tail.
                if tasks:
                    await asyncio.gather(*tasks)
                self.timings[self.run.phase] = {
                    "offering_seconds": round(offering_finished - started, 3),
                    "drain_seconds": round(time.monotonic() - offering_finished, 3),
                }
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
