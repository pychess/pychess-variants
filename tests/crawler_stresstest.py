"""Local crawler load test with an isolated server process and a 512 MiB budget.

Run from the repository root with: uv run python tests/crawler_stresstest.py
See docs/crawler-stress-testing.md for workloads, limits, and interpretation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import signal
import statistics
import sys
import tempfile
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import aiohttp
from crawler_assets import PRODUCTION_STATIC_ROOT, AssetLoad
from yarl import URL

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_LIMIT = 4096


def make_output_directory(path: str | None) -> Path:
    if path is None:
        return Path(tempfile.mkdtemp(prefix="pychess-crawler-"))
    output = Path(path)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    return output


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return number


@dataclass
class Latencies:
    count: int = 0
    samples: list[float] = field(default_factory=list)
    maximum: float = 0
    random: random.Random = field(default_factory=lambda: random.Random(0), repr=False)

    def add(self, milliseconds: float) -> None:
        self.count += 1
        self.maximum = max(self.maximum, milliseconds)
        if len(self.samples) < SAMPLE_LIMIT:
            self.samples.append(milliseconds)
        else:
            slot = self.random.randrange(self.count)
            if slot < SAMPLE_LIMIT:
                self.samples[slot] = milliseconds

    def summary(self) -> dict[str, float | int]:
        ordered = sorted(self.samples)
        return {
            "count": self.count,
            "sample_count": len(ordered),
            "p50_ms": round(ordered[math.ceil(len(ordered) * 0.5) - 1], 3) if ordered else 0,
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3) if ordered else 0,
            "max_ms": round(self.maximum, 3),
        }


@dataclass
class Requests:
    offered: int = 0
    client_dropped: int = 0
    statuses: Counter[str] = field(default_factory=Counter)
    accepted: Latencies = field(default_factory=Latencies)
    rejected: Latencies = field(default_factory=Latencies)
    failed: Latencies = field(default_factory=Latencies)
    headers: Latencies = field(default_factory=Latencies)
    last_status: int | str | None = None
    received_bytes: int = 0

    def record(self, status: int | str, elapsed_ms: float) -> None:
        self.last_status = status
        self.statuses[str(status)] += 1
        if status == 429:
            self.rejected.add(elapsed_ms)
        elif isinstance(status, int) and status < 400:
            self.accepted.add(elapsed_ms)
        else:
            self.failed.add(elapsed_ms)

    def summary(self) -> dict[str, Any]:
        return {
            "offered": self.offered,
            "client_dropped": self.client_dropped,
            "statuses": dict(self.statuses),
            "last_status": self.last_status,
            "received_bytes": self.received_bytes,
            "accepted": self.accepted.summary(),
            "rejected": self.rejected.summary(),
            "failed": self.failed.summary(),
            "headers": self.headers.summary(),
        }


def process_memory(pid: int) -> dict[str, float]:
    values = {}
    for line in Path(f"/proc/{pid}/status").read_text(encoding="ascii").splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmSwap", "VmHWM"}:
            values[key] = int(value.split()[0]) / 1024
    if "VmRSS" not in values:
        raise ProcessLookupError(f"Server process {pid} is no longer running")
    return {
        "rss_mib": values["VmRSS"],
        "swap_mib": values.get("VmSwap", 0),
        "rss_plus_swap_mib": values["VmRSS"] + values.get("VmSwap", 0),
        "peak_rss_mib": values.get("VmHWM", values["VmRSS"]),
    }


def cgroup_stats(pid: int) -> dict[str, Any]:
    """Read cgroup v2 counters without assuming a container or a machine-wide root."""
    result: dict[str, Any] = {}
    for line in Path(f"/proc/{pid}/cgroup").read_text(encoding="ascii").splitlines():
        if not line.startswith("0::"):
            continue
        directory = Path("/sys/fs/cgroup") / line[3:].lstrip("/")
        for name in (
            "memory.current",
            "memory.peak",
            "memory.max",
            "memory.swap.current",
            "memory.swap.max",
            "cpu.max",
        ):
            path = directory / name
            if path.exists():
                raw = path.read_text(encoding="ascii").strip()
                result[name] = int(raw) if raw.isdecimal() else raw
        for name in ("memory.events", "memory.stat", "cpu.stat"):
            events = directory / name
            if events.exists():
                result[name] = {
                    key: int(value)
                    for key, value in (row.split() for row in events.read_text().splitlines())
                }
    return result


def fixture_environment(static_root: str = PRODUCTION_STATIC_ROOT) -> dict[str, str]:
    env = dict(os.environ)
    # No production services or credentials belong in this disposable fixture.
    for key in (
        "DISCORD_TOKEN",
        "LICHESS_API_TOKEN",
        "PYCHESS_MONITOR_TOKEN",
        "PUSH_VAPID_PUBLIC_KEY",
        "PUSH_VAPID_PRIVATE_KEY",
        "PUSH_VAPID_SUBJECT",
        "TWITCH_CLIENT_ID",
        "TWITCH_CLIENT_SECRET",
        "FERNET_KEY",
    ):
        env.pop(key, None)
    env.update(
        {
            "CLIENT_IP_MODE": "heroku",
            "URI": "http://localhost",
            "PROD": "true",
            "BOT_TOKENS": "{}",
            "FISHNET_KEYS": "{}",
            "STATIC_ROOT": static_root,
            "MONGO_HOST": "mongodb://127.0.0.1:27017",
            "PYTHONPATH": os.pathsep.join((str(ROOT / "server"), str(ROOT / "tests"), str(ROOT))),
        }
    )
    return env


class Run:
    def __init__(self, args: argparse.Namespace, output: Path):
        self.args = args
        self.output = output
        self.phase = "startup"
        self.stats: dict[str, dict[str, Requests]] = {}
        self.samples: list[dict[str, Any]] = []
        self.startup_samples: list[dict[str, Any]] = []
        self.stop_load = asyncio.Event()
        self.stop = asyncio.Event()
        self.failures: list[str] = []
        self.fixture: dict[str, Any] = {}
        self.started = time.monotonic()
        self.request_index = 0
        self.assets = AssetLoad(self)

    def requests(self, kind: str) -> Requests:
        return self.stats.setdefault(self.phase, {}).setdefault(kind, Requests())

    async def http(self, session, path: str, headers: dict[str, str], stats: Requests) -> None:
        started = time.monotonic()
        try:
            async with session.get(
                self.fixture["url"] + path, headers=headers, allow_redirects=False
            ) as response:
                # Drain in bounded chunks: the generator must not retain HTML payloads.
                async for _chunk in response.content.iter_chunked(65536):
                    stats.received_bytes += len(_chunk)
                status: int | str = response.status
        except (aiohttp.ClientError, TimeoutError) as exc:
            status = type(exc).__name__
        stats.record(status, (time.monotonic() - started) * 1000)

    async def flood(self, seconds: float) -> None:
        tasks: set[asyncio.Task] = set()
        stats = self.requests("crawler")
        started = time.monotonic()
        deadline = started + seconds
        scheduled = started
        timeout = aiohttp.ClientTimeout(total=self.args.timeout)
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            connector=aiohttp.TCPConnector(limit=self.args.concurrency),
            timeout=timeout,
        ) as session:
            while scheduled < deadline and not self.stop_load.is_set():
                await asyncio.sleep(max(0, scheduled - time.monotonic()))
                if self.stop_load.is_set():
                    break
                now = time.monotonic()
                missed = max(0, int((now - scheduled) * self.args.rps))
                stats.offered += 1 + missed
                stats.client_dropped += missed
                scheduled += (1 + missed) / self.args.rps
                self.request_index += 1 + missed
                index = self.request_index
                if len(tasks) >= self.args.concurrency:
                    stats.client_dropped += 1
                    continue
                path = self.attack_path(index)
                address = f"198.18.{(index // 254) % 254}.{index % 254 + 1}"
                headers = {
                    "X-Forwarded-For": address if self.args.identity == "rotate" else "198.18.0.1",
                    "User-Agent": f"LocalCrawlerSimulation/{index % 7}",
                    "Accept": "application/json" if index % 2 else "text/html",
                }
                if self.args.anonymous_cookie:
                    cookie = SimpleCookie()
                    cookie["AIOHTTP_SESSION"] = json.dumps(
                        {
                            "created": int(time.time()),
                            "session": {"user_name": self.fixture["anonymous_user"]},
                        }
                    )
                    headers["Cookie"] = cookie.output(header="").strip()
                task = asyncio.create_task(self.http(session, path, headers, stats))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            if tasks:
                await asyncio.gather(*tasks)

    def attack_path(self, index: int) -> str:
        profiles = self.fixture.get("profile_names")
        catalogue = self.fixture.get("catalogue_names")

        def variant(offset: int) -> str:
            return (
                catalogue[offset % len(catalogue)]
                if catalogue
                else f"crawlerfixture{offset % self.args.catalogue:04d}"
            )

        if self.args.scenario != "catalogue" and index % 5 == 0:
            profile = (
                profiles[(index // 5) % len(profiles)]
                if profiles
                else f"CrawlerProfile{(index // 5) % self.args.profiles:04d}"
            )
            return f"/@/{quote(profile, safe='')}?crawl={index}"
        if self.args.scenario == "catalogue" or (self.args.scenario == "mixed" and index % 5 == 1):
            if index % 2:
                return "/api/catalogued-variants"
            return "/api/catalogued-variants?" + urlencode(
                [
                    ("name", variant(index + offset))
                    for offset in range(
                        min(32, len(catalogue) if catalogue else self.args.catalogue)
                    )
                ]
            )
        paths = (
            "/",
            "/blogs",
            "/video",
            "/variants/community",
            "/analysis/chess",
            f"/variants/{quote(variant(index), safe='')}",
        )
        return paths[index % len(paths)] + f"?crawl={index}"

    def probe_headers(self, authenticated: bool = False) -> dict[str, str]:
        headers = {"X-Forwarded-For": "192.0.2.200"}
        if authenticated:
            cookie = SimpleCookie()
            cookie["AIOHTTP_SESSION"] = self.fixture["cookie"]
            headers["Cookie"] = cookie.output(header="").strip()
        return headers

    async def probes(self) -> None:
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=self.args.timeout),
        ) as session:
            while not self.stop.is_set():
                await asyncio.gather(
                    *(
                        self.http(session, path, self.probe_headers(auth), self.requests(kind))
                        for path, auth, kind in (
                            ("/about", True, "authenticated_html"),
                            (self.fixture["game_path"], True, "game"),
                            ("/about", False, "anonymous_html"),
                        )
                    )
                )
                await self.pause(self.args.probe_interval)

    async def websocket_probe(self) -> None:
        async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
            ws = None
            try:
                while not self.stop.is_set():
                    stats = self.requests("websocket")
                    started = time.monotonic()
                    try:
                        async with asyncio.timeout(self.args.timeout):
                            if ws is None or ws.closed:
                                ws = await session.ws_connect(
                                    self.fixture["url"] + "/wsr" + self.fixture["game_path"],
                                    autoping=False,
                                    headers={
                                        **self.probe_headers(True),
                                        "Origin": self.fixture["url"],
                                    },
                                )
                            payload = b"crawler-liveness"
                            await ws.ping(payload)
                            while True:
                                message = await ws.receive()
                                if (
                                    message.type == aiohttp.WSMsgType.PONG
                                    and message.data == payload
                                ):
                                    break
                                if message.type == aiohttp.WSMsgType.PING:
                                    await ws.pong(message.data)
                                if message.type in {
                                    aiohttp.WSMsgType.CLOSE,
                                    aiohttp.WSMsgType.CLOSED,
                                    aiohttp.WSMsgType.ERROR,
                                }:
                                    raise ConnectionError("normal-user websocket closed")
                        status: int | str = 200
                    except (aiohttp.ClientError, TimeoutError, ConnectionError) as exc:
                        status = type(exc).__name__
                        if ws is not None:
                            await ws.close()
                        ws = None
                    stats.record(status, (time.monotonic() - started) * 1000)
                    await self.pause(self.args.probe_interval)
            finally:
                if ws is not None:
                    await ws.close()

    async def pause(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def monitor(self) -> None:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.args.timeout)
        ) as session:
            with (self.output / "samples.jsonl").open("w", encoding="utf-8") as stream:
                while not self.stop.is_set():
                    sample: dict[str, Any] = {
                        "elapsed_s": round(time.monotonic() - self.started, 3),
                        "phase": self.phase,
                        "asset_inflight": self.assets.inflight,
                    }
                    try:
                        sample.update(process_memory(self.fixture["pid"]))
                        sample["cgroup"] = cgroup_stats(self.fixture["pid"])
                    except (OSError, ValueError, ProcessLookupError):
                        self.failures.append("server process exited or memory sampling failed")
                        self.stop_load.set()
                        self.stop.set()
                        return
                    memory = sample["rss_plus_swap_mib"]
                    if self.args.constrain:
                        memory = max(memory, sample["cgroup"].get("memory.current", 0) / 1024**2)
                    sample["budget_usage_mib"] = memory
                    observed_peak = max(memory, sample["peak_rss_mib"])
                    if self.args.constrain:
                        observed_peak = max(
                            observed_peak, sample["cgroup"].get("memory.peak", 0) / 1024**2
                        )
                    if observed_peak >= self.args.memory_budget_mib * 0.9:
                        if not self.stop_load.is_set():
                            self.failures.append(
                                "90% memory stop threshold reached; crawler load stopped"
                            )
                        self.stop_load.set()
                    try:
                        async with session.get(
                            self.fixture["url"] + "/api/crawler-fixture-probe",
                            headers={
                                **self.probe_headers(),
                                "X-Crawler-Probe": self.fixture["probe_key"],
                            },
                        ) as response:
                            response.raise_for_status()
                            sample["server"] = await response.json()
                    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                        sample["telemetry_error"] = type(exc).__name__
                    self.samples.append(sample)
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    await self.pause(1)

    async def phase_for(self, name: str, seconds: float, flood: bool = False) -> None:
        self.phase = name
        print(
            f"{name}: {seconds:g}s"
            + (
                f"; crawler {0 if self.args.scenario == 'assets' else self.args.rps:g}/s, "
                f"JS/WASM {self.args.asset_rps:g}/s"
                if flood
                else ""
            ),
            flush=True,
        )
        if flood:
            loads = []
            if self.args.scenario != "assets":
                loads.append(self.flood(seconds))
            if self.args.asset_rps:
                loads.append(self.assets.flood(seconds))
            await asyncio.gather(*loads)
        else:
            await self.pause(seconds)

    def report(self) -> dict[str, Any]:
        failures = list(self.failures)

        def peak_usage(sample):
            return max(
                sample["budget_usage_mib"],
                sample["peak_rss_mib"],
                sample.get("cgroup", {}).get("memory.peak", 0) / 1024**2
                if self.args.constrain
                else 0,
            )

        peak = max(
            (peak_usage(sample) for sample in self.startup_samples + self.samples),
            default=0,
        )
        target = self.args.memory_budget_mib * self.args.max_memory_percent / 100
        if peak > target:
            failures.append(
                f"memory {peak:.1f} MiB exceeds {self.args.max_memory_percent:g}% target ({target:.1f} MiB)"
            )
        baseline = [
            sample["budget_usage_mib"] for sample in self.samples if sample["phase"] == "baseline"
        ]
        final_phase = f"recovery-{self.args.cycles}"
        recovery = [
            sample["budget_usage_mib"] for sample in self.samples if sample["phase"] == final_phase
        ]
        server_samples = [sample["server"] for sample in self.samples if "server" in sample]
        maximum_lag = max((sample["event_loop_lag_ms"] for sample in server_samples), default=0)
        if maximum_lag > self.args.max_loop_lag_ms:
            failures.append(
                f"event-loop delay {maximum_lag:.1f} ms exceeds {self.args.max_loop_lag_ms:g} ms"
            )
        if len(server_samples) != len(self.samples) or not server_samples:
            failures.append("one or more server telemetry samples failed")
        growth = (
            statistics.median(recovery[-3:]) - statistics.median(baseline[-3:])
            if baseline and recovery
            else None
        )
        if growth is None:
            failures.append("baseline or final recovery memory samples missing")
        elif growth > self.args.max_growth_mib:
            failures.append(
                f"post-recovery memory growth {growth:.1f} MiB exceeds {self.args.max_growth_mib:g} MiB"
            )
        summaries = {}
        for phase, groups in self.stats.items():
            if phase.startswith("attack-"):
                for kind in ("authenticated_html", "game", "websocket"):
                    if kind not in groups or groups[kind].accepted.count < 3:
                        failures.append(
                            f"{phase}/{kind}: fewer than three successful probe samples"
                        )
            summaries[phase] = {kind: stats.summary() for kind, stats in groups.items()}
            for kind, stats in groups.items():
                if kind in {"authenticated_html", "game", "websocket"}:
                    if any(status != "200" for status in stats.statuses):
                        failures.append(f"{phase}/{kind}: normal-user probe failed or was rejected")
                    if stats.accepted.summary()["p95_ms"] > self.args.max_probe_p95_ms:
                        failures.append(
                            f"{phase}/{kind}: p95 exceeds {self.args.max_probe_p95_ms:g} ms"
                        )
                if kind in {"crawler", "asset_load"}:
                    if (
                        stats.client_dropped
                        > stats.offered * self.args.max_client_drop_percent / 100
                    ):
                        failures.append(
                            f"{phase}/{kind}: generator dropped {stats.client_dropped} offered requests"
                        )
                    if any(not key.isdecimal() or int(key) >= 500 for key in stats.statuses):
                        failures.append(f"{phase}: crawler encountered server/transport errors")
                if kind.startswith("asset:") and any(
                    status not in {"200", "304"} for status in stats.statuses
                ):
                    failures.append(f"{phase}/{kind}: asset transfer failed")
            if "asset_load" in groups:
                offered = groups["asset_load"]
                completed = sum(
                    sum(stats.statuses.values())
                    for kind, stats in groups.items()
                    if kind.startswith("asset:")
                )
                if offered.offered != completed + offered.client_dropped:
                    failures.append(f"{phase}: asset completion counts do not match offered load")
        if self.args.recovery_seconds >= 65:
            anonymous = self.stats.get(final_phase, {}).get("anonymous_html")
            if anonymous is None or anonymous.last_status != 200:
                failures.append(
                    "anonymous browsing did not recover after its full admission window"
                )
        return {
            "passed": not failures,
            "failures": failures,
            "configuration": vars(self.args),
            "fixture": {
                key: value
                for key, value in self.fixture.items()
                if key not in {"cookie", "probe_key", "profile_names", "catalogue_names"}
            },
            "startup_peak_mib": max(
                (peak_usage(sample) for sample in self.startup_samples),
                default=0,
            ),
            "peak_budget_usage_mib": round(peak, 3),
            "peak_rss_mib": max(
                (sample["peak_rss_mib"] for sample in self.startup_samples + self.samples),
                default=0,
            ),
            "baseline_median_mib": round(statistics.median(baseline), 3) if baseline else None,
            "peak_headroom_mib": round(self.args.memory_budget_mib - peak, 3),
            "target_mib": round(target, 3),
            "post_recovery_growth_mib": round(growth, 3) if growth is not None else None,
            "max_event_loop_lag_ms": maximum_lag,
            "max_event_loop_lag_ms_by_phase": {
                phase: max(
                    (
                        sample["server"]["event_loop_lag_ms"]
                        for sample in self.samples
                        if sample["phase"] == phase and "server" in sample
                    ),
                    default=0,
                )
                for phase in dict.fromkeys(sample["phase"] for sample in self.samples)
            },
            "server_state": {
                "first": server_samples[0] if server_samples else {},
                "last": server_samples[-1] if server_samples else {},
                "peaks": {
                    name: max((sample[name] for sample in server_samples), default=0)
                    for name in (
                        "users",
                        "anonymous_users",
                        "public_profiles",
                        "games",
                        "tasks",
                        "limiter_keys",
                        "html_inflight",
                        "profile_inflight",
                    )
                },
            },
            "peak_cgroup_memory_mib": max(
                (
                    sample.get("cgroup", {}).get("memory.peak", 0) / 1024**2
                    for sample in self.startup_samples + self.samples
                ),
                default=0,
            ),
            "memory_limit_enforced": self.args.constrain,
            "full_recovery_window_observed": self.args.recovery_seconds >= 65,
            "assets": {
                "files": self.assets.files,
                "external_references_not_fetched": self.assets.external,
                "peak_inflight": self.assets.peak_inflight,
                "auto_decompress": False,
                "phase_timings": self.assets.timings,
            },
            "phases": summaries,
        }


async def main(args: argparse.Namespace) -> int:
    output = make_output_directory(args.output)
    print(f"Results: {output}", flush=True)
    ready = output / "fixture-ready.json"
    pid_file = output / "server.pid"
    probe_key = uuid.uuid4().hex
    command = [
        sys.executable,
        "-c",
        (
            "import os, runpy, sys\nfrom pathlib import Path\n"
            "Path(os.environ['CRAWLER_PID_FILE']).write_text(str(os.getpid()), encoding='ascii')\n"
            "sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')"
        ),
        str(ROOT / "tests/crawler_fixture.py"),
        "--ready-file",
        str(ready),
        "--probe-key",
        probe_key,
        "--catalogue",
        str(args.catalogue),
        "--profiles",
        str(args.profiles),
        "--backend-delay-ms",
        str(args.backend_delay_ms),
        "--log-level",
        args.log_level,
    ]
    if args.snapshot_database:
        command.extend(("--snapshot-database", args.snapshot_database))
    if args.constrain:
        command = [
            "systemd-run",
            "--user",
            "--scope",
            "--quiet",
            f"--property=MemoryMax={int(args.memory_budget_mib * 1024**2)}",
            "--property=MemorySwapMax=0",
            "--property=CPUQuota=100%",
            *command,
        ]
    run = Run(args, output)
    with (output / "server.log").open("w", encoding="utf-8") as log:
        process = await asyncio.create_subprocess_exec(
            *command,
            env={**fixture_environment(args.static_root), "CRAWLER_PID_FILE": str(pid_file)},
            cwd=ROOT,
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            with (output / "startup-samples.jsonl").open("w", encoding="utf-8") as stream:
                async with asyncio.timeout(args.startup_timeout):
                    while not ready.exists():
                        if process.returncode is not None:
                            raise RuntimeError(
                                f"fixture failed to start; see {output / 'server.log'}"
                            )
                        if pid_file.exists():
                            try:
                                pid = int(pid_file.read_text(encoding="ascii"))
                                sample = process_memory(pid)
                                sample["cgroup"] = cgroup_stats(pid)
                                sample["elapsed_s"] = round(time.monotonic() - run.started, 3)
                                sample["budget_usage_mib"] = max(
                                    sample["rss_plus_swap_mib"],
                                    sample["cgroup"].get("memory.current", 0) / 1024**2
                                    if args.constrain
                                    else 0,
                                )
                                run.startup_samples.append(sample)
                                stream.write(json.dumps(sample) + "\n")
                                stream.flush()
                            except (OSError, ValueError, ProcessLookupError):
                                pass
                        await asyncio.sleep(0.25)
            run.fixture = json.loads(ready.read_text(encoding="utf-8"))
            run.fixture["probe_key"] = probe_key
            if args.anonymous_cookie:
                # Materialize one guest through the normal websocket flow in a private jar.
                async with (
                    aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session,
                    session.ws_connect(
                        run.fixture["url"] + "/wsl",
                        headers={
                            "X-Forwarded-For": "192.0.2.201",
                            "Origin": run.fixture["url"],
                        },
                    ),
                ):
                    cookies = session.cookie_jar.filter_cookies(URL(run.fixture["url"]))
                    cookie = json.loads(cookies["AIOHTTP_SESSION"].value)
                    run.fixture["anonymous_user"] = cookie["session"]["user_name"]
            if args.constrain:
                observed = cgroup_stats(run.fixture["pid"])
                if observed.get("memory.max") != int(args.memory_budget_mib * 1024**2):
                    raise RuntimeError("server cgroup memory limit was not applied")
            if args.asset_rps:
                await run.assets.prepare()
            workers = [
                asyncio.create_task(work())
                for work in (run.probes, run.websocket_probe, run.monitor)
            ]
            try:
                await run.phase_for("baseline", args.baseline_seconds)
                for cycle in range(1, args.cycles + 1):
                    if run.stop.is_set():
                        break
                    if not run.stop_load.is_set():
                        await run.phase_for(f"attack-{cycle}", args.attack_seconds, flood=True)
                    await run.phase_for(f"recovery-{cycle}", args.recovery_seconds)
            finally:
                run.stop.set()
                await asyncio.gather(*workers)
            report = run.report()
            (output / "report.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "passed",
                            "failures",
                            "peak_budget_usage_mib",
                            "post_recovery_growth_mib",
                            "max_event_loop_lag_ms",
                            "memory_limit_enforced",
                            "full_recovery_window_observed",
                        )
                    },
                    indent=2,
                ),
                flush=True,
            )
            return 0 if report["passed"] else 1
        except (RuntimeError, TimeoutError) as exc:
            run.failures.append(f"startup/run failed: {type(exc).__name__}: {exc}")
            report = run.report()
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "passed": False,
                        "failures": report["failures"],
                        "startup_peak_mib": report["startup_peak_mib"],
                    }
                ),
                flush=True,
            )
            return 1
        finally:
            # The early PID file also covers startup failure before HTTP readiness.
            server_pid = run.fixture.get("pid")
            if server_pid is None and pid_file.exists():
                server_pid = int(pid_file.read_text(encoding="ascii"))
            if server_pid and process.returncode is None:
                try:
                    os.kill(server_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except TimeoutError:
                if server_pid:
                    try:
                        os.kill(server_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.returncode is None:
                    process.kill()
                await process.wait()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    parser.add_argument(
        "--snapshot-database", help="Marked local scratch DB from crawler_snapshot.py"
    )
    parser.add_argument("--startup-timeout", type=positive, default=300)
    parser.add_argument(
        "--constrain",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use a user systemd scope for the server's memory/CPU cap (default: enabled).",
    )
    parser.add_argument("--memory-budget-mib", type=positive, default=512)
    parser.add_argument("--max-memory-percent", type=positive, default=80)
    parser.add_argument("--max-growth-mib", type=positive, default=32)
    parser.add_argument("--max-probe-p95-ms", type=positive, default=250)
    parser.add_argument("--max-loop-lag-ms", type=positive, default=250)
    parser.add_argument("--max-client-drop-percent", type=positive, default=1)
    parser.add_argument("--catalogue", type=positive_int, default=200)
    parser.add_argument("--profiles", type=positive_int, default=1000)
    parser.add_argument("--backend-delay-ms", type=float, default=0)
    parser.add_argument("--log-level", choices=("WARNING", "INFO", "DEBUG"), default="WARNING")
    parser.add_argument("--baseline-seconds", type=positive, default=10)
    parser.add_argument("--attack-seconds", type=positive, default=60)
    parser.add_argument("--recovery-seconds", type=positive, default=65)
    parser.add_argument("--cycles", type=positive_int, default=2)
    parser.add_argument("--rps", type=positive, default=50)
    parser.add_argument("--concurrency", type=positive_int, default=64)
    parser.add_argument("--probe-interval", type=positive, default=1)
    parser.add_argument("--timeout", type=positive, default=3)
    parser.add_argument("--identity", choices=("single", "rotate"), default="rotate")
    parser.add_argument(
        "--scenario", choices=("mixed", "browsing", "catalogue", "assets"), default="mixed"
    )
    parser.add_argument(
        "--static-root",
        default=PRODUCTION_STATIC_ROOT,
        help="Template STATIC_ROOT; external assets are never fetched",
    )
    parser.add_argument(
        "--asset-rps",
        type=nonnegative,
        default=0,
        help="Additional JS/WASM requests/s; assets-only scenario defaults to --rps",
    )
    parser.add_argument("--asset-concurrency", type=positive_int, default=32)
    parser.add_argument("--asset-kind", choices=("all", "js", "wasm"), default="all")
    parser.add_argument("--asset-encoding", choices=("br", "gzip", "identity"), default="br")
    parser.add_argument("--asset-cache", choices=("cold", "warm", "mixed"), default="cold")
    parser.add_argument(
        "--asset-kib-per-second",
        type=nonnegative,
        default=0,
        help="Read rate per asset connection; zero drains as quickly as possible",
    )
    parser.add_argument("--asset-timeout", type=positive, default=120)
    parser.add_argument("--anonymous-cookie", action="store_true")
    args = parser.parse_args(argv)
    if args.scenario == "assets" and not args.asset_rps:
        args.asset_rps = args.rps
    if not 0 < args.max_memory_percent < 90:
        parser.error("--max-memory-percent must be below the 90% automatic stop threshold")
    if not math.isfinite(args.backend_delay_ms) or args.backend_delay_ms < 0:
        parser.error("--backend-delay-ms must be a finite non-negative number")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parse_args())))
