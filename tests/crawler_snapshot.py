"""Copy the local imported database for crawler tests, preserving data and indexes.

Run: uv run python tests/crawler_snapshot.py
The source is read only; test servers accept only a marked scratch database.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from pymongo import AsyncMongoClient, IndexModel

PREFIX = "pychess-crawler-snapshot-"
SOURCE = "pychess-variants"
MARKER = {"_id": "crawler_snapshot", "source": SOURCE, "local_only": True}


async def validate_snapshot(client, name: str) -> None:
    if not name.startswith(PREFIX) or name == SOURCE:
        raise ValueError(
            "Crawler servers require a scratch database created by crawler_snapshot.py"
        )
    if await client[name].config.find_one(MARKER) is None:
        raise ValueError("Scratch database lacks the crawler snapshot marker")


async def create_snapshot(client) -> str:
    name = PREFIX + uuid.uuid4().hex
    if name in await client.list_database_names():
        raise RuntimeError("Snapshot database already exists")
    source = client[SOURCE]
    for collection in await source.list_collection_names():
        options = await source[collection].options()
        if options.get("viewOn"):
            raise RuntimeError("Views require explicit snapshot handling")
        cursor = await source[collection].aggregate(
            [{"$out": {"db": name, "coll": collection}}], allowDiskUse=True
        )
        await cursor.to_list(length=None)
        indexes = []
        async for raw in await source[collection].list_indexes():
            spec = dict(raw)
            keys = list(spec.pop("key").items())
            if spec["name"] == "_id_":
                continue
            for field in ("v", "ns"):
                spec.pop(field, None)
            indexes.append(IndexModel(keys, **spec))
        if indexes:
            await client[name][collection].create_indexes(indexes)
        print(f"Copied {collection}", flush=True)
    await client[name].config.insert_one({**MARKER, "created_at": datetime.now(UTC)})
    return name


async def main() -> None:
    async with AsyncMongoClient("mongodb://127.0.0.1:27017", tz_aware=True) as client:
        name = await create_snapshot(client)
    print(f"Snapshot ready: {name}", flush=True)
    print(f"uv run python tests/crawler_stresstest.py --snapshot-database {name}")


if __name__ == "__main__":
    asyncio.run(main())
