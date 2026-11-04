"""Disposable loopback-only server for crawler_stresstest.py; never use in production."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import time
from collections import Counter, deque
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from const import STARTED
from game import Game
from logger import DEFAULT_LOGGING_CONFIG
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from pymongo import AsyncMongoClient
from request_protection import request_protection_middleware
from settings import MONGO_DB_NAME
from typedefs import REQUEST_RATE_LIMIT_BUCKET_KEY, request_protection_state_key
from user import User
from utils import insert_game_to_db, play_move

from server import make_app


async def serve(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.WARNING)
    if args.snapshot_database:
        from crawler_snapshot import validate_snapshot

        database = AsyncMongoClient("mongodb://127.0.0.1:27017", tz_aware=True)
        await validate_snapshot(database, args.snapshot_database)
    else:
        database = AsyncMongoMockClient(tz_aware=True)
    db_name = args.snapshot_database or MONGO_DB_NAME
    db = database[db_name]
    logging_config = deepcopy(DEFAULT_LOGGING_CONFIG)
    for handler in logging_config["handlers"].values():
        handler["level"] = args.log_level
    for logger in logging_config["loggers"].values():
        logger["level"] = args.log_level
    await db.config.update_one(
        {"name": "logging.config"}, {"$set": {"value": logging_config}}, upsert=True
    )
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    for index in range(0 if args.snapshot_database else args.catalogue):
        name = f"crawlerfixture{index:04d}"
        await db.catalogued_variant.insert_one(
            {
                "_id": name,
                "name": name,
                "displayName": name,
                "author": "CrawlerAuthor",
                "visibility": "public",
                "ini": f"[{name}:chess]\nstalemateValue = draw\n# " + "padding " * 128,
                "baseVariant": "chess",
                "startFen": fen,
                "width": 8,
                "height": 8,
                "pieces": ["p", "n", "b", "r", "q", "k"],
                "createdAt": datetime.now(UTC),
                "updatedAt": datetime.now(UTC),
            }
        )
    probe_names = ["CrawlerPlayerA", "CrawlerPlayerB", "CrawlerAuthor"]
    if not args.snapshot_database:
        probe_names += [f"CrawlerProfile{index:04d}" for index in range(args.profiles)]
    for username in probe_names:
        if await db.user.find_one({"_id": username}):
            raise RuntimeError("Probe identity already exists; use a fresh snapshot")
        await db.user.insert_one({"_id": username, "enabled": True, "ct": "all"})

    with patch("server.MONGO_DB_NAME", db_name):
        app = make_app(db_client=database, simple_cookie_storage=True, with_openapi=True)
    counts: Counter[str] = Counter()
    lag: deque[float] = deque(maxlen=600)

    @web.middleware
    async def count_requests(request, handler):
        status = 500
        try:
            response = await handler(request)
            status = response.status
            return response
        except web.HTTPException as exc:
            status = exc.status
            raise
        finally:
            bucket = request.get(REQUEST_RATE_LIMIT_BUCKET_KEY, "unlimited")
            counts[f"{bucket}:{status}"] += 1

    @web.middleware
    async def backend_delay(request, handler):
        protection = app[request_protection_state_key]
        if args.backend_delay_ms and (
            protection.is_public_browsing_request(request) or request.path.startswith("/@/")
        ):
            await asyncio.sleep(args.backend_delay_ms / 1000)
        return await handler(request)

    app.middlewares.insert(0, count_requests)
    position = app.middlewares.index(request_protection_middleware)
    app.middlewares.insert(position + 1, backend_delay)

    async def instrumentation(_app):
        async def watch_loop():
            while True:
                expected = time.monotonic() + 0.1
                await asyncio.sleep(0.1)
                lag.append(max(0.0, (time.monotonic() - expected) * 1000))

        task = asyncio.create_task(watch_loop(), name="crawler-fixture-loop-sampler")
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app.cleanup_ctx.append(instrumentation)

    async def telemetry(request):
        if request.headers.get("X-Crawler-Probe") != args.probe_key:
            raise web.HTTPForbidden()
        state = get_app_state(app)
        protection = app[request_protection_state_key]
        maximum_lag = max(lag, default=0)
        lag.clear()
        return web.json_response(
            {
                "event_loop_lag_ms": round(maximum_lag, 3),
                "users": len(state.users),
                "anonymous_users": sum(user.anon for user in state.users.values()),
                "public_profiles": len(state.public_users._profiles),
                "games": len(state.games),
                "tasks": len(asyncio.all_tasks()),
                "limiter_keys": len(protection._limiter._events),
                "html_inflight": protection._anonymous_html_inflight,
                "profile_inflight": protection._anonymous_profile_inflight,
                "html_rate_events": len(protection._anonymous_html_events),
                "counts": dict(counts),
            }
        )

    app.router.add_get("/api/crawler-fixture-probe", telemetry)
    runner = web.AppRunner(app, access_log=None)

    async def mock_static_upserts(collection, docs):
        # mongomock cannot execute modern PyMongo UpdateOne bulk operations.
        # Only replace that startup write; retain normal catalogue loading,
        # background tasks, translations and runtime cache lifetimes.
        count = 0
        for doc in docs:
            if doc.get("_id") is not None:
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {key: value for key, value in doc.items() if key != "_id"}},
                    upsert=True,
                )
                count += 1
        return count

    if args.snapshot_database:
        await runner.setup()
    else:
        with patch("pychess_global_app_state._upsert_static_docs", mock_static_upserts):
            await runner.setup()
    state = get_app_state(app)
    await state.correspondence_games_loaded.wait()
    restored = {
        "games": len(state.games),
        "correspondence_games": sum(game.corr for game in state.games.values()),
        "users": len(state.users),
        "tasks": len(asyncio.all_tasks()),
    }
    white = User(state, username="CrawlerPlayerA")
    black = User(state, username="CrawlerPlayerB")
    for user in (white, black):
        state.users[user.username] = user
    game = Game(state, "CrAwL001", "chess", "", white, black, base=30, create=True)
    game.status = STARTED
    state.games[game.id] = game
    await insert_game_to_db(game, state)
    await play_move(state, white, game, "e2e4")
    await play_move(state, black, game, "e7e5")
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    address = runner.addresses[0]
    payload = {
        "url": f"http://127.0.0.1:{address[1]}",
        "pid": os.getpid(),
        "game_path": f"/{game.id}",
        "cookie": json.dumps(
            {"created": int(time.time()), "session": {"user_name": white.username}}
        ),
        "catalogue": len(state.catalogued_variants),
        "profiles": args.profiles,
        "snapshot_database": args.snapshot_database,
        "restored_state": restored,
        "log_level": args.log_level,
        "html_limit": app[request_protection_state_key]._ANON_HTML_GLOBAL_LIMIT.max_requests,
        "html_max_inflight": app[request_protection_state_key]._ANON_HTML_MAX_INFLIGHT,
    }
    if args.snapshot_database:
        payload["profile_names"] = [
            doc["_id"]
            async for doc in db.user.find(
                {"enabled": True, "_id": {"$nin": probe_names}}, {"_id": 1}
            ).limit(args.profiles)
        ]
        from catalogued.variants import is_public_catalogued_variant

        payload["catalogue_names"] = [
            name for name in state.catalogued_variants if is_public_catalogued_variant(state, name)
        ]
        if not payload["profile_names"] or not payload["catalogue_names"]:
            raise RuntimeError("Snapshot has no public profile or catalogue targets")
    ready = Path(args.ready_file)
    temporary = ready.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(ready)
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--probe-key", required=True)
    parser.add_argument("--snapshot-database")
    parser.add_argument("--catalogue", type=int, default=200)
    parser.add_argument("--profiles", type=int, default=300)
    parser.add_argument("--backend-delay-ms", type=float, default=0)
    parser.add_argument("--log-level", choices=("WARNING", "INFO", "DEBUG"), default="WARNING")
    asyncio.run(serve(parser.parse_args()))
