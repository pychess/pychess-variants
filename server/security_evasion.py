from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import web
from client_ip import get_client_ip
from settings import SECRET_KEY

BAN_SIGNAL_COLLECTION = "security_ban_signal"
BAN_SIGNAL_TTL_DAYS = 180
# Require multiple banned-account sources before fp-only auto-close
# to reduce false positives from shared/browser-like fingerprints.
BAN_SIGNAL_FP_ONLY_MIN_SOURCES = 2


@dataclass(frozen=True)
class ClientSignals:
    ip_hash: str | None
    fp_hash: str | None
    ipfp_hash: str | None

    def has_any(self) -> bool:
        return self.ip_hash is not None or self.fp_hash is not None or self.ipfp_hash is not None


def _normalize_signal_part(value: str | None, *, lower: bool = True, max_len: int = 256) -> str:
    if value is None:
        return ""
    compact = " ".join(value.strip().split())
    if lower:
        compact = compact.lower()
    return compact[:max_len]


def _hmac_hash(label: str, value: str) -> str:
    payload = f"evasion-v1|{label}|{value}".encode("utf-8", errors="ignore")
    digest = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()
    return digest[:40]


def get_client_fingerprint_source(request: web.Request) -> str | None:
    headers = request.headers
    # `pcfp` is an optional client-side hint cookie set from base.html.
    cookie_fp = _normalize_signal_part(request.cookies.get("pcfp"), lower=False, max_len=512)
    parts = (
        ("ua", _normalize_signal_part(headers.get("User-Agent"), lower=False)),
        ("lang", _normalize_signal_part(headers.get("Accept-Language"))),
        ("ch", _normalize_signal_part(headers.get("Sec-CH-UA"), lower=False)),
        ("plat", _normalize_signal_part(headers.get("Sec-CH-UA-Platform"), lower=False)),
        ("mob", _normalize_signal_part(headers.get("Sec-CH-UA-Mobile"), lower=False)),
        ("js", cookie_fp),
    )
    compact = "|".join(f"{name}={value}" for name, value in parts if value)
    return compact if compact else None


def collect_client_signals(request: web.Request) -> ClientSignals:
    ip = get_client_ip(request)
    fp_source = get_client_fingerprint_source(request)

    ip_hash = _hmac_hash("ip", ip) if ip else None
    fp_hash = _hmac_hash("fp", fp_source) if fp_source else None

    ipfp_hash: str | None = None
    if ip and fp_source:
        ipfp_hash = _hmac_hash("ipfp", f"{ip}|{fp_source}")

    return ClientSignals(ip_hash=ip_hash, fp_hash=fp_hash, ipfp_hash=ipfp_hash)


def _signal_doc_id(kind: str, value_hash: str) -> str:
    return f"{kind}:{value_hash}"


def signal_ids_from_client_signals(signals: ClientSignals) -> list[str]:
    ids: list[str] = []
    if signals.ip_hash:
        ids.append(_signal_doc_id("ip", signals.ip_hash))
    if signals.fp_hash:
        ids.append(_signal_doc_id("fp", signals.fp_hash))
    if signals.ipfp_hash:
        ids.append(_signal_doc_id("ipfp", signals.ipfp_hash))
    return ids


def signal_ids_from_user_doc(user_doc: Mapping[str, Any] | dict[str, Any]) -> list[str]:
    signal_hashes = _extract_user_signal_hashes(user_doc)
    ids: list[str] = []
    for kind in ("ip", "fp", "ipfp"):
        for value_hash in signal_hashes[kind]:
            ids.append(_signal_doc_id(kind, value_hash))
    return ids


def _extract_user_signal_hashes(
    user_doc: Mapping[str, Any] | dict[str, Any],
) -> dict[str, set[str]]:
    security: dict[str, Any] = user_doc.get("security", {}) if isinstance(user_doc, dict) else {}
    result: dict[str, set[str]] = {"ip": set(), "fp": set(), "ipfp": set()}
    for kind, field in (("ip", "ipHashes"), ("fp", "fpHashes"), ("ipfp", "ipfpHashes")):
        values = security.get(field, [])
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value:
                    result[kind].add(value)
    return result


async def remember_user_signals(db: Any, username: str, signals: ClientSignals) -> None:
    if (db is None) or (not signals.has_any()):
        return

    update_doc: dict[str, Any] = {"$set": {"security.updatedAt": datetime.now(UTC)}}
    add_to_set: dict[str, str] = {}
    if signals.ip_hash:
        add_to_set["security.ipHashes"] = signals.ip_hash
    if signals.fp_hash:
        add_to_set["security.fpHashes"] = signals.fp_hash
    if signals.ipfp_hash:
        add_to_set["security.ipfpHashes"] = signals.ipfp_hash
    if add_to_set:
        update_doc["$addToSet"] = add_to_set

    await db.user.find_one_and_update({"_id": username}, update_doc)


async def add_ban_signals_from_user(db: Any, username: str) -> int:
    if db is None:
        return 0

    user_doc = await db.user.find_one({"_id": username}, projection={"security": 1})
    if user_doc is None:
        return 0

    signal_hashes = _extract_user_signal_hashes(user_doc)
    if not any(signal_hashes.values()):
        return 0

    now = datetime.now(UTC)
    expire_at = now + timedelta(days=BAN_SIGNAL_TTL_DAYS)
    inserted_or_updated = 0
    collection = getattr(db, BAN_SIGNAL_COLLECTION)

    for kind, values in signal_hashes.items():
        for value_hash in values:
            inserted_or_updated += 1
            await collection.find_one_and_update(
                {"_id": _signal_doc_id(kind, value_hash)},
                {
                    "$setOnInsert": {"createdAt": now},
                    "$set": {"kind": kind, "updatedAt": now, "expireAt": expire_at},
                    "$addToSet": {"sources": username},
                },
                upsert=True,
            )

    return inserted_or_updated


async def remove_ban_signals_from_user(db: Any, username: str) -> tuple[int, int]:
    if db is None:
        return 0, 0

    collection = getattr(db, BAN_SIGNAL_COLLECTION)
    cursor = collection.find({"sources": username}, projection={"_id": 1})
    docs = await cursor.to_list(length=4096)
    signal_ids = [doc.get("_id") for doc in docs if isinstance(doc, dict) and doc.get("_id")]
    if not signal_ids:
        return 0, 0

    now = datetime.now(UTC)
    await collection.update_many(
        {"_id": {"$in": signal_ids}}, {"$pull": {"sources": username}, "$set": {"updatedAt": now}}
    )
    delete_result = await collection.delete_many(
        {"_id": {"$in": signal_ids}, "sources": {"$size": 0}}
    )
    deleted_count = getattr(delete_result, "deleted_count", 0) or 0
    return len(signal_ids), int(deleted_count)


async def is_signup_blocked_by_signals(db: Any, signals: ClientSignals) -> tuple[bool, str]:
    if (db is None) or (not signals.has_any()):
        return False, ""

    ids = signal_ids_from_client_signals(signals)
    if not ids:
        return False, ""

    collection = getattr(db, BAN_SIGNAL_COLLECTION)
    cursor = collection.find({"_id": {"$in": ids}}, projection={"kind": 1, "sources": 1})
    docs = await cursor.to_list(length=8)
    matched_kinds = {
        doc.get("kind")
        for doc in docs
        if isinstance(doc, dict) and isinstance(doc.get("kind"), str)
    }
    fp_source_count = 0
    for doc in docs:
        if not isinstance(doc, dict) or doc.get("kind") != "fp":
            continue
        sources = doc.get("sources")
        if isinstance(sources, list):
            fp_source_count = max(fp_source_count, len(sources))

    if "ipfp" in matched_kinds:
        return True, "ipfp"
    if "ip" in matched_kinds and "fp" in matched_kinds:
        return True, "ip+fp"
    if fp_source_count >= BAN_SIGNAL_FP_ONLY_MIN_SOURCES:
        return True, f"fp>={BAN_SIGNAL_FP_ONLY_MIN_SOURCES}"
    return False, ""
