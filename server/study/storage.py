from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any, Literal, cast

from fairy import FairyBoard

from study.annotations import StudyAnnotations
from study.builder import StudyChapterDraft
from study.conceal import preferred_mainline_depth_for_path, reconciled_conceal_ply
from study.constants import (
    STUDY_CHAPTER_MAX_BSON_BYTES,
    STUDY_CHAPTER_NAME_MAX_LENGTH,
    STUDY_MAX_CHAPTERS,
    STUDY_MAX_MEMBERS,
    STUDY_MAX_TOPICS,
    STUDY_NAME_MAX_LENGTH,
    STUDY_PREVIEW_NB_CHAPTERS,
    STUDY_TOPIC_MAX_LENGTH,
    STUDY_TOPIC_MIN_LENGTH,
)
from study.document import encode_chapter
from study.models import (
    Study,
    StudyChapter,
    StudyMemberRole,
    StudyOrientation,
    StudySource,
    StudyVisibility,
    make_chapter,
    make_study,
    study_chapter_mode,
    study_chapter_mode_enabled,
    study_member_role,
    study_search_query_tokens,
    study_search_tokens,
    study_topics,
    study_user_selection,
    study_visibility,
)
from study.permissions import STUDY_FEATURE_KEYS, can_write_study
from study.tree import StudyGamebook, StudyTree


class StudyStorageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StudySharedPositionResult:
    study: Study
    changed: bool
    chapter_revision: int
    conceal_ply: int | None = None
    conceal_changed: bool = False


STUDY_LIST_PAGE_SIZE = 16
StudyListOrder = Literal["updated", "newest", "oldest", "alphabetical"]
_STUDY_LIST_ORDERS = frozenset(("updated", "newest", "oldest", "alphabetical"))
_STUDY_SEARCH_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
_STUDY_SEARCH_QUERY_MAX_LENGTH = 100


def study_list_order(value: object) -> StudyListOrder:
    order = str(value or "updated")
    if order not in _STUDY_LIST_ORDERS:
        return "updated"
    return cast(StudyListOrder, order)


def _study_list_sort(order: StudyListOrder) -> list[tuple[str, int]]:
    if order == "newest":
        return [("createdAt", -1), ("_id", -1)]
    if order == "oldest":
        return [("createdAt", 1), ("_id", 1)]
    if order == "alphabetical":
        return [("name", 1), ("_id", 1)]
    return [("updatedAt", -1), ("_id", 1)]


async def study_list_chapter_names(
    app_state: Any, studies: list[Study]
) -> dict[str, tuple[str, ...]]:
    """Return the ordered chapter-name previews used by Study list cards.

    Lichess previews four chapter names per Study. Group them in MongoDB so list
    pages do not issue one chapter query per card and do not load chapter trees.
    """

    study_ids = [study.id for study in studies]
    if not study_ids:
        return {}

    pipeline = [
        {"$match": {"studyId": {"$in": study_ids}}},
        {"$sort": {"studyId": 1, "order": 1}},
        {"$group": {"_id": "$studyId", "names": {"$push": "$name"}}},
    ]
    cursor_or_awaitable = app_state.db.study_chapter.aggregate(pipeline)
    cursor = await cursor_or_awaitable if isawaitable(cursor_or_awaitable) else cursor_or_awaitable
    docs = await cursor.to_list(length=len(study_ids))

    previews: dict[str, tuple[str, ...]] = {}
    for doc in docs:
        study_id = doc.get("_id")
        raw_names = doc.get("names")
        if not isinstance(study_id, str) or not isinstance(raw_names, list):
            continue
        previews[study_id] = tuple(
            name for name in raw_names[:STUDY_PREVIEW_NB_CHAPTERS] if isinstance(name, str)
        )
    return previews


async def _studies_page(
    app_state: Any,
    query: dict[str, object],
    *,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    page = max(1, page)
    total = await app_state.db.study.count_documents(query)
    pages = max(1, (total + STUDY_LIST_PAGE_SIZE - 1) // STUDY_LIST_PAGE_SIZE)
    page = min(page, pages)
    skip = (page - 1) * STUDY_LIST_PAGE_SIZE
    cursor = (
        app_state.db.study.find(query)
        .sort(_study_list_sort(order))
        .skip(skip)
        .limit(STUDY_LIST_PAGE_SIZE)
    )
    studies = [Study.from_document(doc) async for doc in cursor]
    return {
        "studies": studies,
        "chapter_names": await study_list_chapter_names(app_state, studies),
        "order": order,
        "page": page,
        "pages": pages,
        "total": total,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < pages else None,
    }


async def owner_studies_page(
    app_state: Any,
    owner: str,
    *,
    visibility: StudyVisibility | Literal["private-or-unlisted"] | None = None,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    query: dict[str, object] = {"owner": owner}
    if visibility == "private-or-unlisted":
        query["visibility"] = {"$in": ["private", "unlisted"]}
    elif visibility is not None:
        query["visibility"] = visibility
    return await _studies_page(app_state, query, order=order, page=page)


async def contributed_studies_page(
    app_state: Any,
    username: str,
    *,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    # memberIds is a bounded indexed array maintained with the member map.
    # Like Lichess's member list, this includes read-only memberships as well
    # as contributors; excluding owned Studies avoids duplicating My studies.
    return await _studies_page(
        app_state,
        {
            "owner": {"$ne": username},
            "$or": [
                {"memberIds": username},
                {
                    "memberIds": {"$exists": False},
                    f"members.{username}": {"$exists": True},
                },
            ],
        },
        order=order,
        page=page,
    )


async def favorite_studies_page(
    app_state: Any,
    username: str,
    *,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    """Return Studies explicitly liked by ``username`` and still accessible.

    Lichess excludes owned Studies from this list because every new Study starts
    with the owner's like. Public and unlisted Studies remain link-accessible; a
    private favorite is listed only while the user is still a member.
    """

    return await _studies_page(
        app_state,
        {
            "$and": [
                {"owner": {"$ne": username}},
                {"likers": username},
                {
                    "$or": [
                        {"visibility": {"$in": ["public", "unlisted"]}},
                        _member_query(username),
                    ]
                },
            ]
        },
        order=order,
        page=page,
    )


async def topic_studies_page(
    app_state: Any,
    topic: str,
    *,
    viewer: str | None,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    """Return Studies with one exact topic that are discoverable to ``viewer``."""

    return await _studies_page(
        app_state,
        {"$and": [{"topics": topic}, _study_search_access_query(viewer)]},
        order=order,
        page=page,
    )


async def autocomplete_study_topics(
    app_state: Any,
    term: str,
    *,
    viewer: str | None,
    limit: int = 10,
) -> list[str]:
    """Suggest Study topics by prefix, preferring the viewer's own topics.

    This mirrors lichess' Study topic autocomplete behavior: personal topics come
    first, then public topics fill the remaining slots. Private/unlisted topics
    are never suggested to unrelated users.
    """

    clean = " ".join(str(term).split())
    if len(clean) < STUDY_TOPIC_MIN_LENGTH or len(clean) > STUDY_TOPIC_MAX_LENGTH:
        return []
    limit = max(1, min(limit, 20))
    folded = clean.casefold()
    suggestions: list[str] = []

    if viewer:
        for topic in await member_study_topics(app_state, viewer, limit=100):
            if topic.casefold().startswith(folded) and topic not in suggestions:
                suggestions.append(topic)
                if len(suggestions) >= limit:
                    return suggestions

    regex = {"$regex": f"^{re.escape(clean)}", "$options": "i"}
    pipeline = [
        {"$match": {"visibility": "public", "topics": regex}},
        {"$unwind": "$topics"},
        {"$match": {"topics": regex}},
        {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": limit * 2},
    ]
    cursor_or_awaitable = app_state.db.study.aggregate(pipeline)
    cursor = await cursor_or_awaitable if isawaitable(cursor_or_awaitable) else cursor_or_awaitable
    docs = await cursor.to_list(length=limit * 2)
    for doc in docs:
        topic = doc.get("_id")
        if isinstance(topic, str) and topic not in suggestions:
            suggestions.append(topic)
            if len(suggestions) >= limit:
                break
    return suggestions


async def popular_study_topics(app_state: Any, *, limit: int = 50) -> list[str]:
    """Return the most-used public Study topics without leaking private metadata."""

    pipeline = [
        {"$match": {"visibility": "public", "topics": {"$exists": True, "$ne": []}}},
        {"$unwind": "$topics"},
        {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": max(1, limit)},
    ]
    cursor_or_awaitable = app_state.db.study.aggregate(pipeline)
    cursor = await cursor_or_awaitable if isawaitable(cursor_or_awaitable) else cursor_or_awaitable
    docs = await cursor.to_list(length=max(1, limit))
    return [str(doc["_id"]) for doc in docs if isinstance(doc.get("_id"), str)]


async def member_study_topics(app_state: Any, username: str, *, limit: int = 12) -> list[str]:
    """Return recent distinct topics from Studies the user owns or belongs to.

    Lichess stores a separate personal topic-shortcut list. PyChess derives the
    shortcuts from the user's accessible Studies instead, which keeps the first
    topic implementation small while preserving the same useful navigation.
    """

    cursor = (
        app_state.db.study.find(
            {"$or": [{"owner": username}, _member_query(username)]},
            projection={"topics": 1, "updatedAt": 1},
        )
        .sort("updatedAt", -1)
        .limit(100)
    )
    topics: list[str] = []
    async for doc in cursor:
        raw_topics = doc.get("topics")
        if not isinstance(raw_topics, list):
            continue
        for raw_topic in raw_topics:
            if isinstance(raw_topic, str) and raw_topic not in topics:
                topics.append(raw_topic)
                if len(topics) >= limit:
                    return topics
    return topics


def _study_search_parts(value: object) -> tuple[str, tuple[str, ...], str | None, str | None, bool]:
    clean_query = " ".join(str(value or "").split())[:_STUDY_SEARCH_QUERY_MAX_LENGTH]
    owner: str | None = None
    member: str | None = None
    free_parts: list[str] = []
    for part in clean_query.split():
        key, separator, raw_value = part.partition(":")
        if separator and key.casefold() in {"owner", "member"}:
            if _STUDY_SEARCH_USERNAME_RE.fullmatch(raw_value):
                if key.casefold() == "owner":
                    owner = raw_value
                else:
                    member = raw_value
            else:
                free_parts.append(part)
        else:
            free_parts.append(part)

    free_query = " ".join(free_parts)
    tokens = study_search_query_tokens(free_query)
    query_too_short = bool(free_query and not tokens and owner is None and member is None)
    return clean_query, tokens, owner, member, query_too_short


def _member_query(username: str) -> dict[str, object]:
    # New Study documents keep the bounded memberIds array indexed. The safe
    # dotted-field fallback preserves membership discovery for pre-Phase-5 docs.
    return {
        "$or": [
            {"memberIds": username},
            {
                "memberIds": {"$exists": False},
                f"members.{username}": {"$exists": True},
            },
        ]
    }


def _study_search_access_query(viewer: str | None) -> dict[str, object]:
    # Unlisted Studies are link-viewable, but must not become discoverable merely
    # because somebody searches for their chapter text. Only public Studies and
    # the viewer's own/member Studies belong in search results.
    if viewer is None:
        return {"visibility": "public"}
    return {
        "$or": [
            {"visibility": "public"},
            {"owner": viewer},
            _member_query(viewer),
        ]
    }


async def study_search_page(
    app_state: Any,
    *,
    q: str,
    viewer: str | None,
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    """Search discoverable Studies using text plus Lichess-style owner/member filters."""

    clean_query, tokens, owner, member, query_too_short = _study_search_parts(q)
    if query_too_short:
        return {
            "studies": [],
            "q": clean_query,
            "order": order,
            "page": 1,
            "pages": 1,
            "total": 0,
            "prev_page": None,
            "next_page": None,
            "query_too_short": True,
        }

    clauses: list[dict[str, object]] = [_study_search_access_query(viewer)]
    if owner is not None:
        clauses.append({"owner": owner})
    if member is not None:
        clauses.append(_member_query(member))
    for token in tokens:
        clauses.append({"searchTokens": token})

    # Empty /study/search requests behave like All studies rather than exposing
    # every private membership to an accidental blank search.
    if not clean_query:
        result = await public_studies_page(app_state, order=order, page=page)
    else:
        result = await _studies_page(
            app_state,
            {"$and": clauses},
            order=order,
            page=page,
        )
    result["q"] = clean_query
    result["query_too_short"] = False
    result["owner_filter"] = owner
    result["member_filter"] = member
    return result


async def refresh_study_search_tokens(app_state: Any, study_id: str) -> None:
    """Rebuild the bounded denormalized search vocabulary for one Study."""

    study_doc = await app_state.db.study.find_one(
        {"_id": study_id}, projection={"name": 1, "owner": 1, "topics": 1}
    )
    if study_doc is None:
        return

    metadata: list[str] = []
    descriptions: list[str] = []
    cursor = app_state.db.study_chapter.find(
        {"studyId": study_id},
        projection={
            "name": 1,
            "variant": 1,
            "chess960": 1,
            "description": 1,
            "tags": 1,
            "order": 1,
        },
    ).sort("order", 1)
    async for chapter in cursor:
        metadata.append(str(chapter.get("name") or ""))
        metadata.append(str(chapter.get("variant") or ""))
        if chapter.get("chess960") is True:
            metadata.append("chess960")
        tags = chapter.get("tags")
        if isinstance(tags, dict):
            for tag_name, tag_value in tags.items():
                metadata.extend((str(tag_name), str(tag_value)))
        description = chapter.get("description")
        if isinstance(description, str) and description:
            descriptions.append(description)

    tokens = study_search_tokens(
        str(study_doc.get("name") or ""),
        str(study_doc.get("owner") or ""),
        *(str(topic) for topic in study_doc.get("topics", []) if isinstance(topic, str)),
        *metadata,
        *descriptions,
    )
    await app_state.db.study.update_one(
        {"_id": study_id},
        {"$set": {"searchTokens": list(tokens)}},
    )


async def public_studies_page(
    app_state: Any,
    *,
    q: str = "",
    order: StudyListOrder = "updated",
    page: int = 1,
) -> dict[str, object]:
    """Return one public Study discovery page, optionally filtered by indexed prefixes."""

    clean_query = " ".join(str(q or "").split())[:80]
    tokens = study_search_query_tokens(clean_query)
    query: dict[str, object] = {"visibility": "public"}
    if tokens:
        indexed_search: dict[str, object] = {
            "searchTokens": tokens[0] if len(tokens) == 1 else {"$all": list(tokens)}
        }
        # Phase 3 predates the derived searchTokens field. Keep already-created
        # public Studies searchable while new/renamed documents use the multikey
        # index. User text is escaped before it reaches MongoDB's regex engine.
        legacy_terms: list[dict[str, object]] = []
        for token in tokens:
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            legacy_terms.append(
                {"$or": [{"name": {"$regex": pattern}}, {"owner": {"$regex": pattern}}]}
            )
        query["$or"] = [
            indexed_search,
            {
                "$and": [
                    {"searchTokens": {"$exists": False}},
                    *legacy_terms,
                ]
            },
        ]
    elif clean_query:
        # Match Lichess's minimum useful query length without turning one- or
        # two-character searches into collection scans.
        return {
            "studies": [],
            "q": clean_query,
            "order": order,
            "page": 1,
            "pages": 1,
            "total": 0,
            "prev_page": None,
            "next_page": None,
            "query_too_short": True,
        }

    result = await _studies_page(app_state, query, order=order, page=page)
    result["q"] = clean_query
    result["query_too_short"] = False
    return result


def _clean_name(value: object, *, fallback: str, max_length: int) -> str:
    name = str(value or "").strip()
    if not name:
        return fallback
    return name[:max_length]


async def _ensure_chapter_size(chapter: StudyChapter) -> dict[str, object]:
    try:
        encoded = await encode_chapter(chapter, include_document=True)
    except Exception as exc:
        raise StudyStorageError("Study chapter could not be encoded") from exc
    if encoded.size > STUDY_CHAPTER_MAX_BSON_BYTES:
        raise StudyStorageError("Study chapter is too large")
    assert encoded.document is not None
    return encoded.document


async def studies_for_owner(app_state: Any, owner: str, *, limit: int = 100) -> list[Study]:
    cursor = app_state.db.study.find({"owner": owner}).sort("updatedAt", -1).limit(limit)
    return [Study.from_document(doc) async for doc in cursor]


def _owner_listing_filter(owner: str, viewer: str | None) -> dict[str, object]:
    # Unlisted Studies stay out of owner/profile listings. Owners still need a
    # complete self-view, matching the existing /study page and Lichess's
    # by-owner behavior for the signed-in owner.
    if viewer == owner:
        return {"owner": owner}
    return {"owner": owner, "visibility": "public"}


async def studies_for_owner_view(
    app_state: Any, owner: str, viewer: str | None, *, limit: int = 100
) -> list[Study]:
    cursor = (
        app_state.db.study.find(_owner_listing_filter(owner, viewer))
        .sort("updatedAt", -1)
        .limit(limit)
    )
    return [Study.from_document(doc) async for doc in cursor]


async def count_studies_for_owner_view(app_state: Any, owner: str, viewer: str | None) -> int:
    return await app_state.db.study.count_documents(_owner_listing_filter(owner, viewer))


async def studies_writable_by(
    app_state: Any,
    username: str,
    *,
    limit: int = 100,
) -> list[Study]:
    """Return Studies the user may write, including contributed Studies."""

    docs = (
        await app_state.db.study.find({"$or": [{"owner": username}, {"writeMembers": username}]})
        .sort("updatedAt", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    return [Study.from_document(doc) for doc in docs]


async def load_owned_study(app_state: Any, study_id: str, owner: str) -> Study | None:
    doc = await app_state.db.study.find_one({"_id": study_id, "owner": owner})
    return Study.from_document(doc) if doc is not None else None


async def load_study(app_state: Any, study_id: str) -> Study | None:
    doc = await app_state.db.study.find_one({"_id": study_id})
    return Study.from_document(doc) if doc is not None else None


async def set_study_like(
    app_state: Any,
    study: Study,
    username: str,
    liked: bool,
) -> tuple[bool, int, bool]:
    """Set one user's Study like and return state, count, and whether it changed."""

    update = {"$addToSet": {"likers": username}} if liked else {"$pull": {"likers": username}}
    result = await app_state.db.study.update_one({"_id": study.id}, update)
    doc = await app_state.db.study.find_one({"_id": study.id}, projection={"likers": 1})
    if doc is None:
        raise StudyStorageError("Study not found")
    raw_likers = doc.get("likers")
    likers = (
        tuple(dict.fromkeys(item for item in raw_likers if isinstance(item, str) and item))
        if isinstance(raw_likers, list)
        else ()
    )
    likes = len(likers)
    await app_state.db.study.update_one({"_id": study.id}, {"$set": {"likes": likes}})
    return username in likers, likes, bool(result.modified_count)


async def set_study_topics(
    app_state: Any,
    study_id: str,
    actor: str,
    topics: object,
) -> tuple[Study, bool]:
    """Replace one Study's discovery topics with optimistic metadata revision safety."""

    try:
        clean_topics = study_topics(topics)
    except (TypeError, ValueError) as exc:
        raise StudyStorageError(str(exc)) from exc
    if len(clean_topics) > STUDY_MAX_TOPICS:
        raise StudyStorageError(f"A Study can have at most {STUDY_MAX_TOPICS} topics")

    for _ in range(4):
        study = await load_study(app_state, study_id)
        if study is None:
            raise StudyStorageError("Study not found")
        if not can_write_study(study, actor):
            raise StudyStorageError("You cannot edit this Study")
        if study.topics == clean_topics:
            return study, False

        now = datetime.now(UTC)
        update: dict[str, object] = {
            "$set": {"updatedAt": now},
            "$inc": {"revision": 1},
        }
        if clean_topics:
            cast(dict[str, object], update["$set"])["topics"] = list(clean_topics)
        else:
            update["$unset"] = {"topics": ""}
        result = await app_state.db.study.update_one(
            {"_id": study.id, "revision": study.revision},
            update,
        )
        if result.matched_count == 1:
            updated = replace(
                study,
                topics=clean_topics,
                updated_at=now,
                revision=study.revision + 1,
            )
            await refresh_study_search_tokens(app_state, study.id)
            return updated, True

    raise StudyStorageError("Study topics changed concurrently; please retry")


async def _replace_study_members(
    app_state: Any,
    study: Study,
    members: dict[str, StudyMemberRole],
) -> Study | None:
    """CAS one member-map update against the Study metadata revision.

    Membership changes are rare, so replacing the bounded map keeps the Mongo shape
    simple and lets the existing revision protect the cap/invariants from concurrent
    owner requests without introducing a permanent in-memory lock per Study.
    """

    now = datetime.now(UTC)
    result = await app_state.db.study.update_one(
        {"_id": study.id, "revision": study.revision},
        {
            "$set": {
                "members": members,
                "memberIds": sorted(members),
                "writeMembers": sorted(
                    username for username, role in members.items() if role == "write"
                ),
                "updatedAt": now,
            },
            "$inc": {"revision": 1},
        },
    )
    if result.matched_count != 1:
        return None
    return replace(study, members=members, updated_at=now, revision=study.revision + 1)


async def add_study_member(
    app_state: Any,
    study_id: str,
    actor: str,
    username: str,
    role: object = "read",
) -> Study:
    clean_role = study_member_role(role)
    for _ in range(4):
        study = await load_study(app_state, study_id)
        if study is None:
            raise StudyStorageError("Study not found")
        if study.owner != actor:
            raise StudyStorageError("Only the Study owner can add members")
        if username == study.owner:
            raise StudyStorageError("The Study owner is already a member")
        members = dict(study.members)
        if username not in members and len(members) >= STUDY_MAX_MEMBERS:
            raise StudyStorageError(f"A Study can have at most {STUDY_MAX_MEMBERS} members")
        if members.get(username) == clean_role:
            return study
        members[username] = clean_role
        updated = await _replace_study_members(app_state, study, members)
        if updated is not None:
            return updated
    raise StudyStorageError("Study membership changed concurrently; please retry")


async def set_study_member_role(
    app_state: Any,
    study_id: str,
    actor: str,
    username: str,
    role: object,
) -> Study:
    clean_role = study_member_role(role)
    for _ in range(4):
        study = await load_study(app_state, study_id)
        if study is None:
            raise StudyStorageError("Study not found")
        if study.owner != actor:
            raise StudyStorageError("Only the Study owner can change member roles")
        if username == study.owner:
            raise StudyStorageError("The Study owner's role cannot be changed")
        if username not in study.members:
            raise StudyStorageError("Study member not found")
        if study.members[username] == clean_role:
            return study
        members = dict(study.members)
        members[username] = clean_role
        updated = await _replace_study_members(app_state, study, members)
        if updated is not None:
            return updated
    raise StudyStorageError("Study membership changed concurrently; please retry")


async def remove_study_member(
    app_state: Any,
    study_id: str,
    actor: str,
    username: str,
) -> Study:
    for _ in range(4):
        study = await load_study(app_state, study_id)
        if study is None:
            raise StudyStorageError("Study not found")
        if study.owner != actor:
            raise StudyStorageError("Only the Study owner can remove members")
        if username == study.owner:
            raise StudyStorageError("The Study owner cannot be removed")
        if username not in study.members:
            raise StudyStorageError("Study member not found")
        members = dict(study.members)
        del members[username]
        updated = await _replace_study_members(app_state, study, members)
        if updated is not None:
            return updated
    raise StudyStorageError("Study membership changed concurrently; please retry")


async def leave_study(app_state: Any, study_id: str, username: str) -> Study:
    for _ in range(4):
        study = await load_study(app_state, study_id)
        if study is None:
            raise StudyStorageError("Study not found")
        if username == study.owner:
            raise StudyStorageError("The Study owner cannot leave the Study")
        if username not in study.members:
            raise StudyStorageError("You are not a member of this Study")
        members = dict(study.members)
        del members[username]
        updated = await _replace_study_members(app_state, study, members)
        if updated is not None:
            return updated
    raise StudyStorageError("Study membership changed concurrently; please retry")


async def load_owned_chapter(
    app_state: Any,
    study_id: str,
    chapter_id: str,
    owner: str,
) -> StudyChapter | None:
    doc = await app_state.db.study_chapter.find_one(
        {"_id": chapter_id, "studyId": study_id, "owner": owner}
    )
    return StudyChapter.from_document(doc) if doc is not None else None


async def load_chapter(app_state: Any, study_id: str, chapter_id: str) -> StudyChapter | None:
    doc = await app_state.db.study_chapter.find_one({"_id": chapter_id, "studyId": study_id})
    return StudyChapter.from_document(doc) if doc is not None else None


def _chapter_preview_status(raw_tags: object) -> str | None:
    if not isinstance(raw_tags, Mapping):
        return None
    for raw_name, raw_value in raw_tags.items():
        if (
            not isinstance(raw_name, str)
            or raw_name.casefold() != "result"
            or not isinstance(raw_value, str)
        ):
            continue
        result = raw_value.strip()
        if result == "1/2-1/2":
            return "½-½"
        if result in {"1-0", "0-1", "½-½", "*"}:
            return result
    return None


async def chapter_previews(app_state: Any, study_id: str) -> list[dict[str, object]]:
    cursor = app_state.db.study_chapter.find(
        {"studyId": study_id},
        projection={
            "_id": 1,
            "name": 1,
            "order": 1,
            "orientation": 1,
            "mode": 1,
            "concealPly": 1,
            "description": 1,
            "tags": 1,
        },
    ).sort("order", 1)
    previews: list[dict[str, object]] = []
    async for doc in cursor:
        try:
            mode = study_chapter_mode(doc.get("mode", "normal"))
        except ValueError as exc:
            raise StudyStorageError("Invalid stored Study chapter mode") from exc
        preview: dict[str, object] = {
            "id": str(doc["_id"]),
            "name": str(doc["name"]),
            "order": int(doc["order"]),
            "orientation": str(doc.get("orientation") or "white"),
            "mode": mode,
            "descriptionPinned": bool(doc.get("description")),
        }
        status = _chapter_preview_status(doc.get("tags"))
        if status is not None:
            preview["status"] = status
        if mode == "conceal":
            raw_conceal_ply = doc.get("concealPly", 0)
            if (
                isinstance(raw_conceal_ply, bool)
                or not isinstance(raw_conceal_ply, int)
                or raw_conceal_ply < 0
            ):
                raise StudyStorageError("Invalid stored Study conceal boundary")
            preview["concealPly"] = raw_conceal_ply
        previews.append(preview)
    return previews


async def create_study_from_draft(
    app_state: Any,
    owner: str,
    draft: StudyChapterDraft,
    *,
    name: str | None = None,
    visibility: StudyVisibility = "private",
    settings: Mapping[str, object] | None = None,
) -> tuple[Study, StudyChapter]:
    study = await make_study(
        app_state.db.study,
        owner=owner,
        name=_clean_name(name, fallback=f"{owner}'s Study", max_length=STUDY_NAME_MAX_LENGTH),
        visibility=visibility,
        settings=settings,
        source=draft.source,
    )
    chapter = await make_chapter(
        app_state.db.study_chapter,
        study_id=study.id,
        owner=owner,
        variant=draft.variant,
        chess960=draft.chess960,
        initial_fen=draft.initial_fen,
        orientation=draft.orientation,
        variant_ini=draft.variant_ini,
        mode=draft.mode,
        conceal_ply=draft.conceal_ply,
        root=draft.root,
        source=draft.source,
        description=draft.description,
        tags=draft.tags,
        order=1,
        name=_clean_name(
            draft.name, fallback="Chapter 1", max_length=STUDY_CHAPTER_NAME_MAX_LENGTH
        ),
    )
    chapter_document = await _ensure_chapter_size(chapter)
    study = replace(study, current_chapter=chapter.id)
    await app_state.db.study.insert_one(study.to_document())
    try:
        await app_state.db.study_chapter.insert_one(chapter_document)
        await refresh_study_search_tokens(app_state, study.id)
    except Exception:
        await app_state.db.study.delete_one({"_id": study.id, "owner": owner})
        raise
    return study, chapter


async def create_study_from_drafts(
    app_state: Any,
    owner: str,
    drafts: list[StudyChapterDraft],
    *,
    name: str | None = None,
    visibility: StudyVisibility = "private",
    settings: Mapping[str, object] | None = None,
) -> tuple[Study, list[StudyChapter]]:
    if not drafts:
        raise StudyStorageError("PGN import contains no chapters")
    if len(drafts) > STUDY_MAX_CHAPTERS:
        raise StudyStorageError(f"A Study can have at most {STUDY_MAX_CHAPTERS} chapters")

    study, first = await create_study_from_draft(
        app_state,
        owner,
        drafts[0],
        name=name,
        visibility=visibility,
        settings=settings,
    )
    if len(drafts) == 1:
        return study, [first]

    try:
        rest = await add_chapters_from_drafts(app_state, study, drafts[1:])
    except Exception:
        # A new Study has no external references yet. Roll the first chapter and
        # Study metadata back as one creation unit when the remaining PGN chapters
        # cannot be persisted. add_chapters_from_drafts() already cleans its own
        # partial insert before propagating the failure.
        await app_state.db.study_chapter.delete_many({"studyId": study.id, "owner": owner})
        await app_state.db.study.delete_one({"_id": study.id, "owner": owner})
        raise
    return study, [first, *rest]


async def create_study_with_chapter(
    app_state: Any,
    owner: str,
    *,
    name: str | None = None,
    visibility: StudyVisibility = "private",
    settings: Mapping[str, object] | None = None,
) -> tuple[Study, StudyChapter]:
    return await create_study_from_draft(
        app_state,
        owner,
        StudyChapterDraft(
            variant="chess",
            initial_fen=FairyBoard.start_fen("chess"),
        ),
        name=name,
        visibility=visibility,
        settings=settings,
    )


async def clone_study(
    app_state: Any,
    source: Study,
    owner: str,
) -> tuple[Study, StudyChapter]:
    """Clone every chapter into a new private Study owned by ``owner``.

    The copy keeps Study/chapter content and settings, but receives fresh Study
    and chapter ids, fresh timestamps, reset revisions, and no inherited members.
    Like Lichess, the clone opens on its first chapter and records the source
    Study id for provenance.
    """

    now = datetime.now(UTC)
    cloned = await make_study(
        app_state.db.study,
        owner=owner,
        name=source.name,
        source=StudySource("study", source.id),
        now=now,
    )
    cloned = replace(cloned, settings=dict(source.settings), topics=source.topics)

    # Do not materialize every chapter at once. A chapter may be several MiB and
    # a maximal Study can contain dozens of them, which makes an eager clone an
    # avoidable OOM risk on small web dynos. MongoDB cursor batches are bounded
    # by the wire-protocol batch size; copying one decoded chapter at a time keeps
    # Python-side memory proportional to one chapter rather than the whole Study.
    cursor = app_state.db.study_chapter.find({"studyId": source.id}).sort("order", 1)
    first_chapter: StudyChapter | None = None
    chapter_count = 0
    try:
        async for doc in cursor:
            chapter_count += 1
            if chapter_count > STUDY_MAX_CHAPTERS:
                raise StudyStorageError(f"A Study can have at most {STUDY_MAX_CHAPTERS} chapters")
            original = StudyChapter.from_document(doc)
            if not study_chapter_mode_enabled(original.mode) or (
                original.root.has_gamebook and not study_chapter_mode_enabled("gamebook")
            ):
                raise StudyStorageError("Study contains a chapter mode that is not enabled")
            chapter = await make_chapter(
                app_state.db.study_chapter,
                study_id=cloned.id,
                owner=owner,
                variant=original.variant,
                initial_fen=original.initial_fen,
                orientation=original.orientation,
                order=original.order,
                name=original.name,
                chess960=original.chess960,
                variant_ini=original.variant_ini,
                mode=original.mode,
                conceal_ply=0 if original.mode == "conceal" else None,
                root=original.root,
                source=original.source,
                description=original.description,
                tags=original.tags,
                now=now,
            )
            chapter_document = await _ensure_chapter_size(chapter)
            await app_state.db.study_chapter.insert_one(chapter_document)
            if first_chapter is None:
                first_chapter = chapter

        if first_chapter is None:
            raise StudyStorageError("Study has no chapters to clone")

        cloned = replace(cloned, current_chapter=first_chapter.id)
        await app_state.db.study.insert_one(cloned.to_document())
        await refresh_study_search_tokens(app_state, cloned.id)
    except Exception:
        await app_state.db.study_chapter.delete_many({"studyId": cloned.id})
        await app_state.db.study.delete_one({"_id": cloned.id, "owner": owner})
        raise

    return cloned, first_chapter


async def add_chapter_from_draft(
    app_state: Any,
    study: Study,
    draft: StudyChapterDraft,
    *,
    activate_shared: bool = True,
) -> StudyChapter:
    count = await app_state.db.study_chapter.count_documents({"studyId": study.id})
    if count >= STUDY_MAX_CHAPTERS:
        raise StudyStorageError(f"A Study can have at most {STUDY_MAX_CHAPTERS} chapters")

    last = await app_state.db.study_chapter.find_one(
        {"studyId": study.id}, projection={"order": 1}, sort=[("order", -1)]
    )
    order = int(last["order"]) + 1 if last is not None else 1
    chapter = await make_chapter(
        app_state.db.study_chapter,
        study_id=study.id,
        owner=study.owner,
        variant=draft.variant,
        chess960=draft.chess960,
        initial_fen=draft.initial_fen,
        orientation=draft.orientation,
        variant_ini=draft.variant_ini,
        mode=draft.mode,
        conceal_ply=draft.conceal_ply,
        root=draft.root,
        source=draft.source,
        description=draft.description,
        tags=draft.tags,
        order=order,
        name=_clean_name(
            draft.name, fallback=f"Chapter {order}", max_length=STUDY_CHAPTER_NAME_MAX_LENGTH
        ),
    )
    chapter_document = await _ensure_chapter_size(chapter)
    await app_state.db.study_chapter.insert_one(chapter_document)
    now = datetime.now(UTC)
    study_update: dict[str, object] = {
        "$set": {"updatedAt": now},
        "$inc": {"revision": 1},
    }
    if activate_shared:
        cast_set = cast(dict[str, object], study_update["$set"])
        cast_set["currentChapter"] = chapter.id
        study_update["$unset"] = {"currentPath": ""}
    result = await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        study_update,
    )
    if result.matched_count != 1:
        await app_state.db.study_chapter.delete_one({"_id": chapter.id, "studyId": study.id})
        raise StudyStorageError("Study disappeared while adding chapter")
    await refresh_study_search_tokens(app_state, study.id)
    return chapter


async def add_chapters_from_drafts(
    app_state: Any,
    study: Study,
    drafts: list[StudyChapterDraft],
    *,
    activate_shared: bool = True,
) -> list[StudyChapter]:
    if not drafts:
        raise StudyStorageError("PGN import contains no chapters")

    count = await app_state.db.study_chapter.count_documents({"studyId": study.id})
    if count + len(drafts) > STUDY_MAX_CHAPTERS:
        remaining = max(0, STUDY_MAX_CHAPTERS - count)
        raise StudyStorageError(
            f"Study has room for {remaining} more chapter{'s' if remaining != 1 else ''}"
        )

    last = await app_state.db.study_chapter.find_one(
        {"studyId": study.id}, projection={"order": 1}, sort=[("order", -1)]
    )
    start_order = int(last["order"]) + 1 if last is not None else 1
    chapters: list[StudyChapter] = []
    documents: list[dict[str, object]] = []
    for offset, draft in enumerate(drafts):
        order = start_order + offset
        chapter = await make_chapter(
            app_state.db.study_chapter,
            study_id=study.id,
            owner=study.owner,
            variant=draft.variant,
            chess960=draft.chess960,
            initial_fen=draft.initial_fen,
            orientation=draft.orientation,
            variant_ini=draft.variant_ini,
            mode=draft.mode,
            conceal_ply=draft.conceal_ply,
            root=draft.root,
            source=draft.source,
            description=draft.description,
            tags=draft.tags,
            order=order,
            name=_clean_name(
                draft.name, fallback=f"Chapter {order}", max_length=STUDY_CHAPTER_NAME_MAX_LENGTH
            ),
        )
        chapter_document = await _ensure_chapter_size(chapter)
        chapters.append(chapter)
        documents.append(chapter_document)

    ids = [chapter.id for chapter in chapters]
    try:
        await app_state.db.study_chapter.insert_many(documents)
        now = datetime.now(UTC)
        study_update: dict[str, object] = {
            "$set": {"updatedAt": now},
            "$inc": {"revision": 1},
        }
        if activate_shared:
            cast_set = cast(dict[str, object], study_update["$set"])
            cast_set["currentChapter"] = chapters[-1].id
            study_update["$unset"] = {"currentPath": ""}
        result = await app_state.db.study.update_one(
            {"_id": study.id, "owner": study.owner},
            study_update,
        )
        if result.matched_count != 1:
            raise StudyStorageError("Study disappeared during PGN import")
    except Exception:
        await app_state.db.study_chapter.delete_many({"_id": {"$in": ids}, "studyId": study.id})
        raise
    await refresh_study_search_tokens(app_state, study.id)
    return chapters


async def add_chapter(
    app_state: Any,
    study: Study,
    source_chapter: StudyChapter,
    *,
    name: str | None = None,
) -> StudyChapter:
    if not study_chapter_mode_enabled(source_chapter.mode) or (
        source_chapter.root.has_gamebook and not study_chapter_mode_enabled("gamebook")
    ):
        raise StudyStorageError("Study chapter mode is not enabled")
    count = await app_state.db.study_chapter.count_documents({"studyId": study.id})
    if count >= STUDY_MAX_CHAPTERS:
        raise StudyStorageError(f"A Study can have at most {STUDY_MAX_CHAPTERS} chapters")

    last = await app_state.db.study_chapter.find_one(
        {"studyId": study.id}, projection={"order": 1}, sort=[("order", -1)]
    )
    order = int(last["order"]) + 1 if last is not None else 1
    chapter = await make_chapter(
        app_state.db.study_chapter,
        study_id=study.id,
        owner=study.owner,
        variant=source_chapter.variant,
        chess960=source_chapter.chess960,
        initial_fen=source_chapter.initial_fen,
        orientation=source_chapter.orientation,
        variant_ini=source_chapter.variant_ini,
        mode=source_chapter.mode,
        conceal_ply=0 if source_chapter.mode == "conceal" else None,
        order=order,
        name=_clean_name(
            name, fallback=f"Chapter {order}", max_length=STUDY_CHAPTER_NAME_MAX_LENGTH
        ),
    )
    await app_state.db.study_chapter.insert_one(chapter.to_document())
    now = datetime.now(UTC)
    result = await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {
            "$set": {"currentChapter": chapter.id, "updatedAt": now},
            "$unset": {"currentPath": ""},
            "$inc": {"revision": 1},
        },
    )
    if result.matched_count != 1:
        await app_state.db.study_chapter.delete_one({"_id": chapter.id, "studyId": study.id})
        raise StudyStorageError("Study disappeared while adding chapter")
    await refresh_study_search_tokens(app_state, study.id)
    return chapter


async def select_chapter(app_state: Any, study: Study, chapter: StudyChapter) -> None:
    if study.current_chapter == chapter.id:
        return
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {"$set": {"currentChapter": chapter.id}, "$inc": {"revision": 1}},
    )


async def set_shared_position(
    app_state: Any,
    study_id: str,
    username: str,
    chapter_id: str,
    path: str,
    *,
    expected_revision: int | None = None,
) -> StudySharedPositionResult:
    """Persist an authorized shared position and advance concealment when presented.

    The caller holds the Study sequencer while this runs and broadcasts the result.
    A concealed chapter advances only when the published path is a prefix of the
    preferred mainline; side variations and backward publication never increase the
    boundary. The boundary is root-relative, so custom-FEN move numbers are irrelevant.
    """

    study = await load_study(app_state, study_id)
    if study is None:
        raise StudyStorageError("Study not found")
    if not can_write_study(study, username):
        raise StudyStorageError("Study is read only")
    chapter = await load_chapter(app_state, study_id, chapter_id)
    if chapter is None:
        raise StudyStorageError("Study chapter not found")
    if path and chapter.root.node_at_path(path) is None:
        raise StudyStorageError("Study path not found")
    if expected_revision is not None and expected_revision != chapter.revision:
        raise StudyStorageError("Study chapter changed while publishing position")

    current_path = study.current_path or ""
    position_changed = study.current_chapter != chapter_id or current_path != path
    next_conceal_ply = chapter.conceal_ply
    conceal_changed = False
    if chapter.mode == "conceal":
        depth = preferred_mainline_depth_for_path(chapter.root, path)
        if depth is not None and depth > (chapter.conceal_ply or 0):
            if expected_revision is None:
                raise StudyStorageError("Conceal reveal publication requires a chapter revision")
            next_conceal_ply = depth
            conceal_changed = True

    if not position_changed and not conceal_changed:
        return StudySharedPositionResult(
            study=study,
            changed=False,
            chapter_revision=chapter.revision,
            conceal_ply=chapter.conceal_ply,
        )

    next_revision = chapter.revision
    if conceal_changed:
        next_revision += 1
        chapter_update = await app_state.db.study_chapter.update_one(
            {
                "_id": chapter.id,
                "studyId": study.id,
                "revision": chapter.revision,
                "mode": "conceal",
            },
            {
                "$set": {"concealPly": next_conceal_ply},
                "$inc": {"revision": 1},
            },
        )
        if chapter_update.matched_count != 1:
            raise StudyStorageError("Study chapter changed while publishing position")

    update: dict[str, object] = {"$set": {"currentChapter": chapter_id}}
    if path:
        cast_set = update["$set"]
        assert isinstance(cast_set, dict)
        cast_set["currentPath"] = path
    else:
        update["$unset"] = {"currentPath": ""}
    study_update = await app_state.db.study.update_one({"_id": study_id}, update)
    if study_update.matched_count != 1:
        raise StudyStorageError("Study disappeared while publishing position")

    return StudySharedPositionResult(
        study=replace(study, current_chapter=chapter_id, current_path=path or None),
        changed=True,
        chapter_revision=next_revision,
        conceal_ply=next_conceal_ply,
        conceal_changed=conceal_changed,
    )


async def reset_concealment(
    app_state: Any,
    study_id: str,
    username: str,
    chapter_id: str,
    expected_revision: int,
) -> StudySharedPositionResult:
    """Hide a concealed chapter again and reset its shared presentation to root."""

    study = await load_study(app_state, study_id)
    if study is None:
        raise StudyStorageError("Study not found")
    if not can_write_study(study, username):
        raise StudyStorageError("Study is read only")
    chapter = await load_chapter(app_state, study_id, chapter_id)
    if chapter is None:
        raise StudyStorageError("Study chapter not found")
    if chapter.mode != "conceal":
        raise StudyStorageError("Study chapter is not concealed")
    if expected_revision != chapter.revision:
        raise StudyStorageError("Study chapter changed while resetting concealment")

    current_path = study.current_path or ""
    position_changed = study.current_chapter != chapter_id or bool(current_path)
    conceal_changed = (chapter.conceal_ply or 0) != 0
    if not position_changed and not conceal_changed:
        return StudySharedPositionResult(
            study=study,
            changed=False,
            chapter_revision=chapter.revision,
            conceal_ply=0,
        )

    next_revision = chapter.revision
    if conceal_changed:
        next_revision += 1
        chapter_update = await app_state.db.study_chapter.update_one(
            {
                "_id": chapter.id,
                "studyId": study.id,
                "revision": chapter.revision,
                "mode": "conceal",
            },
            {
                "$set": {"concealPly": 0},
                "$inc": {"revision": 1},
            },
        )
        if chapter_update.matched_count != 1:
            raise StudyStorageError("Study chapter changed while resetting concealment")

    study_update = await app_state.db.study.update_one(
        {"_id": study.id},
        {"$set": {"currentChapter": chapter.id}, "$unset": {"currentPath": ""}},
    )
    if study_update.matched_count != 1:
        raise StudyStorageError("Study disappeared while resetting concealment")
    return StudySharedPositionResult(
        study=replace(study, current_chapter=chapter.id, current_path=None),
        changed=True,
        chapter_revision=next_revision,
        conceal_ply=0,
        conceal_changed=conceal_changed,
    )


async def rename_study(app_state: Any, study: Study, name: object) -> str:
    clean = _clean_name(name, fallback=study.name, max_length=STUDY_NAME_MAX_LENGTH)
    now = datetime.now(UTC)
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {
            "$set": {
                "name": clean,
                "updatedAt": now,
            },
            "$inc": {"revision": 1},
        },
    )
    await refresh_study_search_tokens(app_state, study.id)
    return clean


async def set_study_visibility(
    app_state: Any,
    study: Study,
    visibility: object,
) -> StudyVisibility:
    clean = study_visibility(visibility)
    if clean == study.visibility:
        return clean
    now = datetime.now(UTC)
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {"$set": {"visibility": clean, "updatedAt": now}, "$inc": {"revision": 1}},
    )
    return clean


async def set_study_feature_settings(
    app_state: Any,
    study: Study,
    values: Mapping[str, object],
) -> dict[str, object]:
    """Persist the known per-feature audience settings while preserving extensions."""

    settings = dict(study.settings)
    for feature in STUDY_FEATURE_KEYS:
        if feature in values:
            try:
                settings[feature] = study_user_selection(values[feature])
            except ValueError as exc:
                raise StudyStorageError(f"Invalid Study {feature} permission") from exc

    if settings == dict(study.settings):
        return settings

    now = datetime.now(UTC)
    result = await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {"$set": {"settings": settings, "updatedAt": now}, "$inc": {"revision": 1}},
    )
    if result.matched_count != 1:
        raise StudyStorageError("Study disappeared while updating permissions")
    return settings


async def rename_chapter(app_state: Any, chapter: StudyChapter, name: object) -> str:
    clean, _ = await edit_chapter_metadata(
        app_state,
        chapter,
        name=name,
        orientation=chapter.orientation,
    )
    return clean


async def edit_chapter_metadata(
    app_state: Any,
    chapter: StudyChapter,
    *,
    name: object,
    orientation: object,
    pinned_description: object | None = None,
    mode: object | None = None,
    conceal_ply: object | None = None,
) -> tuple[str, StudyOrientation]:
    clean_name = _clean_name(name, fallback=chapter.name, max_length=STUDY_CHAPTER_NAME_MAX_LENGTH)
    clean_orientation = str(orientation or chapter.orientation).lower()
    if clean_orientation not in ("white", "black"):
        raise StudyStorageError("Invalid Study chapter orientation")
    typed_orientation = cast(StudyOrientation, clean_orientation)

    try:
        next_mode = chapter.mode if mode is None else study_chapter_mode(mode)
    except ValueError as exc:
        raise StudyStorageError("Invalid Study chapter mode") from exc

    if next_mode != chapter.mode and not study_chapter_mode_enabled(next_mode):
        raise StudyStorageError("Study chapter mode is not enabled")

    if next_mode == "conceal":
        if conceal_ply is None or conceal_ply == "":
            next_conceal_ply = chapter.conceal_ply if chapter.mode == "conceal" else 0
        else:
            try:
                next_conceal_ply = int(conceal_ply)
            except (TypeError, ValueError) as exc:
                raise StudyStorageError("Invalid Study conceal boundary") from exc
            if isinstance(conceal_ply, bool) or str(next_conceal_ply) != str(conceal_ply).strip():
                raise StudyStorageError("Invalid Study conceal boundary")
        mainline_depth = len(chapter.root.preferred_mainline())
        if next_conceal_ply < 0 or next_conceal_ply > mainline_depth:
            raise StudyStorageError(
                f"Study conceal boundary must be between 0 and {mainline_depth}"
            )
    else:
        if conceal_ply not in (None, ""):
            raise StudyStorageError("Study conceal boundary is only valid in conceal mode")
        next_conceal_ply = None

    next_description = chapter.description
    if pinned_description is not None:
        enabled = str(pinned_description or "").strip() == "1"
        next_description = chapter.description or "-" if enabled else ""

    metadata_changed = clean_name != chapter.name or typed_orientation != chapter.orientation
    description_changed = next_description != chapter.description
    teaching_changed = next_mode != chapter.mode or next_conceal_ply != chapter.conceal_ply
    if not metadata_changed and not description_changed and not teaching_changed:
        return clean_name, typed_orientation

    now = datetime.now(UTC)
    set_fields: dict[str, object] = {
        "name": clean_name,
        "orientation": typed_orientation,
        "mode": next_mode,
        "updatedAt": now,
    }
    update: dict[str, object] = {"$set": set_fields}
    unset_fields: dict[str, object] = {}
    if description_changed:
        if next_description:
            set_fields["description"] = next_description
        else:
            unset_fields["description"] = ""
    if next_mode == "conceal":
        set_fields["concealPly"] = next_conceal_ply
    elif chapter.conceal_ply is not None:
        unset_fields["concealPly"] = ""
    if unset_fields:
        update["$unset"] = unset_fields
    if description_changed or teaching_changed:
        update["$inc"] = {"revision": 1}

    await app_state.db.study_chapter.update_one(
        {"_id": chapter.id, "studyId": chapter.study_id, "owner": chapter.owner},
        update,
    )
    study_update: dict[str, object] = {
        "$set": {"updatedAt": now},
        "$inc": {"revision": 1},
    }
    if chapter.mode != "conceal" and next_mode == "conceal":
        # Enabling concealment starts a new shared presentation from the root.
        # Only reset the path when this chapter is currently being presented.
        current = await app_state.db.study.find_one(
            {"_id": chapter.study_id, "owner": chapter.owner},
            projection={"currentChapter": 1},
        )
        if current is not None and current.get("currentChapter") == chapter.id:
            study_update["$unset"] = {"currentPath": ""}
    await app_state.db.study.update_one(
        {"_id": chapter.study_id, "owner": chapter.owner},
        study_update,
    )
    await refresh_study_search_tokens(app_state, chapter.study_id)
    return clean_name, typed_orientation


def _without_chapter_annotations(tree: StudyTree) -> tuple[StudyTree, bool]:
    changed = (
        not tree.root_annotations.empty
        or not tree.root_gamebook.empty
        or any(
            not node.annotations.empty or not node.gamebook.empty for node in tree.nodes.values()
        )
    )
    if not changed:
        return tree, False
    nodes = {
        node_id: replace(node, annotations=StudyAnnotations(), gamebook=StudyGamebook())
        for node_id, node in tree.nodes.items()
    }
    return (
        StudyTree(
            nodes,
            root_annotations=StudyAnnotations(),
            root_gamebook=StudyGamebook(),
            root_eval_score=tree.root_eval_score,
            root_clocks=tree.root_clocks,
        ),
        True,
    )


def _without_chapter_variations(tree: StudyTree) -> tuple[StudyTree, bool]:
    nodes = {}
    parent_id: str | None = None
    while True:
        children = tree.children_of(parent_id)
        if not children:
            break
        node = children[0]
        nodes[node.id] = node
        parent_id = node.id
    if len(nodes) == len(tree.nodes):
        return tree, False
    return (
        StudyTree(
            nodes,
            root_annotations=tree.root_annotations,
            root_gamebook=tree.root_gamebook,
            root_eval_score=tree.root_eval_score,
            root_clocks=tree.root_clocks,
        ),
        True,
    )


def _existing_tree_path(tree: StudyTree, path: str) -> str:
    candidate = path
    while candidate and tree.node_at_path(candidate) is None:
        candidate = candidate.rpartition(".")[0]
    return candidate


async def clear_chapter_annotations(app_state: Any, study: Study, chapter: StudyChapter) -> bool:
    """Clear comments, shapes, NAGs and lesson instructions in a chapter.

    Lichess also clears the chapter's server-analysis record because that record
    can contain annotations derived from the old tree state. Keep node evals,
    which are separate from annotations.
    """

    root, annotations_changed = _without_chapter_annotations(chapter.root)
    changed = annotations_changed or chapter.server_eval is not None
    if not changed:
        return False

    candidate = replace(
        chapter,
        root=root,
        server_eval=None,
        revision=chapter.revision + 1,
        updated_at=datetime.now(UTC),
    )
    chapter_document = await _ensure_chapter_size(candidate)
    update: dict[str, object] = {
        "$set": {"root": chapter_document["root"], "updatedAt": candidate.updated_at},
        "$inc": {"revision": 1},
    }
    if chapter.server_eval is not None:
        update["$unset"] = {"serverEval": ""}
    await app_state.db.study_chapter.update_one(
        {"_id": chapter.id, "studyId": study.id, "owner": study.owner},
        update,
    )
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        {"$set": {"updatedAt": candidate.updated_at}, "$inc": {"revision": 1}},
    )

    from study.analysis import drop_study_analysis_work

    drop_study_analysis_work(app_state, study.id, chapter.id)
    return True


async def clear_chapter_variations(app_state: Any, study: Study, chapter: StudyChapter) -> bool:
    """Keep only each position's first ordered child recursively."""

    root, changed = _without_chapter_variations(chapter.root)
    if not changed:
        return False

    now = datetime.now(UTC)
    next_conceal_ply = reconciled_conceal_ply(chapter.root, root, chapter.conceal_ply)
    candidate = replace(
        chapter,
        root=root,
        conceal_ply=next_conceal_ply,
        revision=chapter.revision + 1,
        updated_at=now,
    )
    chapter_document = await _ensure_chapter_size(candidate)
    set_fields: dict[str, object] = {"root": chapter_document["root"], "updatedAt": now}
    if next_conceal_ply != chapter.conceal_ply:
        set_fields["concealPly"] = next_conceal_ply
    await app_state.db.study_chapter.update_one(
        {"_id": chapter.id, "studyId": study.id, "owner": study.owner},
        {
            "$set": set_fields,
            "$inc": {"revision": 1},
        },
    )

    study_update: dict[str, object] = {
        "$set": {"updatedAt": now},
        "$inc": {"revision": 1},
    }
    if study.current_chapter == chapter.id and study.current_path:
        repaired_path = _existing_tree_path(root, study.current_path)
        if repaired_path != study.current_path:
            set_fields = cast(dict[str, object], study_update["$set"])
            if repaired_path:
                set_fields["currentPath"] = repaired_path
            else:
                study_update["$unset"] = {"currentPath": ""}
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        study_update,
    )
    return True


async def delete_chapter(app_state: Any, study: Study, chapter: StudyChapter) -> str:
    docs = (
        await app_state.db.study_chapter.find(
            {"studyId": study.id}, projection={"_id": 1, "order": 1}
        )
        .sort("order", 1)
        .to_list(length=STUDY_MAX_CHAPTERS + 1)
    )
    if len(docs) <= 1:
        raise StudyStorageError("A Study must keep at least one chapter")

    await app_state.db.study_chapter.delete_one(
        {"_id": chapter.id, "studyId": study.id, "owner": study.owner}
    )
    from study.analysis import drop_study_analysis_work

    drop_study_analysis_work(app_state, study.id, chapter.id)
    deleted_index = next(index for index, doc in enumerate(docs) if str(doc["_id"]) == chapter.id)
    remaining = [doc for doc in docs if str(doc["_id"]) != chapter.id]
    for order, doc in enumerate(remaining, start=1):
        if int(doc["order"]) != order:
            await app_state.db.study_chapter.update_one(
                {"_id": doc["_id"]}, {"$set": {"order": order}}
            )

    if study.current_chapter == chapter.id or not study.current_chapter:
        adjacent_index = min(deleted_index, len(remaining) - 1)
        next_chapter_id = str(remaining[adjacent_index]["_id"])
    else:
        next_chapter_id = study.current_chapter
    now = datetime.now(UTC)
    update: dict[str, object] = {
        "$set": {"currentChapter": next_chapter_id, "updatedAt": now},
        "$inc": {"revision": 1},
    }
    if study.current_chapter == chapter.id or not study.current_chapter:
        update["$unset"] = {"currentPath": ""}
    await app_state.db.study.update_one(
        {"_id": study.id, "owner": study.owner},
        update,
    )
    await refresh_study_search_tokens(app_state, study.id)
    return next_chapter_id


async def delete_study(app_state: Any, study: Study) -> None:
    from study.analysis import drop_study_analysis_works_for_study

    drop_study_analysis_works_for_study(app_state, study.id)
    await app_state.db.study_chapter.delete_many({"studyId": study.id, "owner": study.owner})
    await app_state.db.study.delete_one({"_id": study.id, "owner": study.owner})
