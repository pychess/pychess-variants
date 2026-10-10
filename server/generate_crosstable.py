from __future__ import annotations

import logging

from variants import TWO_BOARD_VARIANT_CODES

log = logging.getLogger(__name__)


async def generate_crosstable(app_state, username=None):
    db = app_state.db
    ct = {}

    if username is None:
        cursor = db.game.find().sort("d")
    else:
        cursor = db.game.find({"us": username}).sort("d")
        log.info("START generate_crosstable %s", username)

    async for doc in cursor:
        if doc["v"] in TWO_BOARD_VARIANT_CODES:
            continue  # todo:bughouse has no crosstable implemented at the moment

        game_id = doc["_id"]
        wp, bp = doc["us"]
        result = doc["r"]

        if wp < bp:
            s1p = wp
            s2p = bp
        else:
            s1p = bp
            s2p = wp
        ct_id = s1p + "/" + s2p
        # print(ct_id, game_id)
        # R2C = {"1-0": "a", "0-1": "b", "1/2-1/2": "c", "*": "d"}
        if (
            result == "d"
            or wp.startswith("Anon")
            or bp.startswith("Anon")
            or wp == "Random-Mover"
            or wp == "Fairy-Stockfish"
            or wp == "Alice-Stockfish"
            or bp == "Random-Mover"
            or bp == "Fairy-Stockfish"
            or bp == "Alice-Stockfish"
        ):
            continue

        if result == "c":
            s1 = s2 = 5
            tail = "="
        elif (result == "a" and s1p == wp) or (result == "b" and s1p == bp):
            s1 = 10
            s2 = 0
            tail = "+"
        else:
            s1 = 0
            s2 = 10
            tail = "-"

        if ct_id not in ct:
            ct[ct_id] = {
                "_id": ct_id,
                "s1": s1,
                "s2": s2,
                "r": ["%s%s" % (game_id, tail)],
            }
        else:
            ct[ct_id]["s1"] += s1
            ct[ct_id]["s2"] += s2
            ct[ct_id]["r"].append("%s%s" % (game_id, tail))

    for i, item in enumerate(sorted(ct.values(), key=lambda x: x["_id"])):
        # print(i, item)
        ct[item["_id"]]["r"] = ct[item["_id"]]["r"][-20:]
        # print(i, item)

    if username is None:
        await db.crosstable.drop()
        # bulk insert to crosstable
        if len(ct) > 0:
            await db.crosstable.insert_many(ct.values())
    else:
        for key, value in ct.items():
            # print(key, value)
            await db.crosstable.find_one_and_update({"_id": key}, {"$set": value}, upsert=True)
    log.info("DONE generate_crosstable %s", username)
