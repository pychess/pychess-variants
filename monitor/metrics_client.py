from __future__ import annotations

import os
from typing import Any

import aiohttp

DEFAULT_METRICS_URL = "https://www.pychess.org/metrics"


def metrics_url() -> str:
    return os.getenv("PYCHESS_MONITOR_URL", DEFAULT_METRICS_URL)


def monitor_token() -> str:
    return os.getenv("PYCHESS_MONITOR_TOKEN", "")


async def fetch_metrics(
    session: aiohttp.ClientSession,
    *,
    url: str | None = None,
    token: str | None = None,
    inspect_tasks: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    resolved_url = url or metrics_url()
    resolved_token = monitor_token() if token is None else token
    if not resolved_token:
        raise ValueError("PYCHESS_MONITOR_TOKEN is not set")

    params = {}
    if inspect_tasks:
        params["inspect"] = "True"
    if summary_only:
        params["summary"] = "True"
    headers = {"Authorization": f"Bearer {resolved_token}"}
    async with session.get(resolved_url, headers=headers, params=params or None) as response:
        response.raise_for_status()
        data = await response.json()
        if not isinstance(data, dict):
            raise TypeError("Metrics response is not a JSON object")
        return data


def monitor_view(data: dict[str, Any]) -> dict[str, Any]:
    """Adapt lightweight counters to the TUI's existing table schema.

    Empty detail tables mean no heap/object snapshot was requested. Summary
    counters remain live; no old heap rows or allocation sizes are carried over.
    """
    if data.get("mode") != "summary":
        return data
    state = data.get("state", {})
    process = data.get("process_memory", {})
    details = {
        category: []
        for category in (
            "users",
            "seeks",
            "games",
            "tasks",
            "queues",
            "connections",
            "anon_users",
            "started_games_no_round_sockets",
            "anon_summary",
            "registered_summary",
            "tournaments",
            "simuls",
            "fishnet_works",
            "caches",
            "state",
            "streams",
            "process_memory",
        )
    }
    for category, key in (
        ("process_memory", "process_memory"),
        ("state", "state"),
        ("streams", "streams"),
        ("registered_summary", "registered"),
        ("anon_summary", "anonymous"),
    ):
        details[category] = [data.get(key, {})]
    details["caches"] = data.get("caches", [])
    counts = {category: len(rows) for category, rows in details.items()}
    for category in ("users", "seeks", "games", "tournaments", "simuls", "fishnet_works"):
        counts[category] = state.get(category, 0)
    counts["tasks"] = state.get("active_tasks", 0)
    counts["connections"] = state.get("lobby_connections", 0)
    counts["anon_users"] = data.get("anonymous", {}).get("anon_total", 0)
    counts["caches"] = sum(row.get("currsize", 0) for row in details["caches"])
    counts["process_memory"] = process.get("rss_kib", 0)
    return {
        **data,
        "object_details": details,
        "object_counts": counts,
        # Only RSS is measured in summaries; zero must not be shown as a heap-size measurement.
        "object_sizes": {"process_memory": process.get("rss_kib", 0)},
        "top_allocations": [],
    }
