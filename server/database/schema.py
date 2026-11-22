from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from const import GAME_CATEGORIES, NOTIFY_EXPIRE_WEEKS

IndexKey = tuple[tuple[str, int | str], ...]
CreateOption = tuple[str, Any]

TIMELINE_RETENTION_SECONDS = 14 * 24 * 60 * 60
TEAM_UPDATE_RETENTION_SECONDS = 90 * 24 * 60 * 60


class StartupPolicy(Enum):
    """How a populated production database should handle a missing index."""

    BLOCKING = "blocking"
    AFTER_STARTUP = "after_startup"
    MANUAL = "manual"


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    create_options: tuple[CreateOption, ...] = ()
    fallback_to_default_options: bool = False

    def pymongo_options(self) -> dict[str, Any]:
        return dict(self.create_options)


@dataclass(frozen=True)
class IndexSpec:
    collection: str
    name: str
    key: IndexKey
    unique: bool = False
    sparse: bool = False
    expire_after_seconds: int | None = None
    partial_filter: dict[str, Any] | None = None
    startup_policy: StartupPolicy = StartupPolicy.BLOCKING

    def pymongo_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"name": self.name}
        if self.unique:
            options["unique"] = True
        if self.sparse:
            options["sparse"] = True
        if self.expire_after_seconds is not None:
            options["expireAfterSeconds"] = self.expire_after_seconds
        if self.partial_filter is not None:
            options["partialFilterExpression"] = self.partial_filter
        return options


def _default_index_name(key: IndexKey) -> str:
    return "_".join(f"{field}_{direction}" for field, direction in key)


def _index(
    collection: str,
    *key: tuple[str, int | str],
    name: str | None = None,
    unique: bool = False,
    sparse: bool = False,
    expire_after_seconds: int | None = None,
    partial_filter: dict[str, Any] | None = None,
    startup_policy: StartupPolicy = StartupPolicy.BLOCKING,
) -> IndexSpec:
    index_key = tuple(key)
    return IndexSpec(
        collection=collection,
        name=name or _default_index_name(index_key),
        key=index_key,
        unique=unique,
        sparse=sparse,
        expire_after_seconds=expire_after_seconds,
        partial_filter=partial_filter,
        startup_policy=startup_policy,
    )


# These are the collections required by the current application. Startup uses
# this catalog to create every missing collection before feature initialization.
COLLECTIONS = (
    CollectionSpec("account_reopen_token"),
    CollectionSpec("autopairing"),
    CollectionSpec("bot_token"),
    CollectionSpec("external_engine"),
    CollectionSpec("catalogued_variant"),
    CollectionSpec("catalogued_variant_name"),
    CollectionSpec("cheat_report"),
    CollectionSpec("config"),
    CollectionSpec("crosstable"),
    CollectionSpec(
        "dailypuzzle",
        create_options=(
            ("capped", True),
            ("size", 50000),
            ("max", 365 * len(GAME_CATEGORIES)),
        ),
        fallback_to_default_options=True,
    ),
    CollectionSpec("fishnet"),
    CollectionSpec("forum_categ"),
    CollectionSpec("forum_post"),
    CollectionSpec("forum_topic"),
    CollectionSpec("game"),
    CollectionSpec("highscore"),
    CollectionSpec("inbox_msg"),
    CollectionSpec("inbox_thread"),
    CollectionSpec("mod_log"),
    CollectionSpec("notify"),
    CollectionSpec("puzzle"),
    CollectionSpec("practice"),
    CollectionSpec("push_subscription"),
    CollectionSpec("relation"),
    CollectionSpec("security_ban_signal"),
    CollectionSpec("seek"),
    CollectionSpec("simul"),
    CollectionSpec("simul_chat"),
    CollectionSpec("stats"),
    CollectionSpec("stats_humans"),
    CollectionSpec("study"),
    CollectionSpec("study_chapter"),
    CollectionSpec("team"),
    CollectionSpec("team_member"),
    CollectionSpec("team_request"),
    CollectionSpec("team_update"),
    CollectionSpec("timeline_entry"),
    CollectionSpec("timeline_unsub"),
    CollectionSpec("tournament"),
    CollectionSpec("tournament_arrangement"),
    CollectionSpec("tournament_chat"),
    CollectionSpec("tournament_pairing"),
    CollectionSpec("tournament_player"),
    CollectionSpec("ublog_post"),
    CollectionSpec("ublog_post2"),
    CollectionSpec("user"),
    CollectionSpec("user_report"),
    CollectionSpec("video"),
)


# Production exports can still contain these retired collections. They are
# recognized for audit/reporting purposes but must not be created in a fresh
# database.
LEGACY_OPTIONAL_COLLECTIONS = (
    CollectionSpec("blog"),
    CollectionSpec("lobbychat"),
)


# This is the single source of truth for indexes managed by application startup
# and the schema utility.
INDEXES = (
    # Tournament and social infrastructure.
    _index("tournament_chat", ("tid", 1)),
    _index("tournament_chat", ("user", 1)),
    _index("simul_chat", ("sid", 1)),
    _index("simul_chat", ("user", 1)),
    _index("tournament", ("startsAt", 1)),
    _index("tournament", ("status", 1)),
    _index("tournament", ("teamId", 1)),
    _index("tournament", ("createdBy", 1)),
    _index("tournament", ("winner", 1)),
    _index("tournament", ("profilePointsPending", 1), sparse=True),
    _index("tournament_player", ("tid", 1)),
    _index("tournament_player", ("uid", 1)),
    _index("tournament_pairing", ("tid", 1)),
    _index("tournament_pairing", ("u", 1)),
    _index("tournament_arrangement", ("tid", 1)),
    _index("tournament_arrangement", ("u", 1)),
    _index("tournament_arrangement", ("ch", 1)),
    _index("relation", ("u1", 1), ("r", 1), name="u1_r"),
    _index("relation", ("u2", 1), ("r", 1), name="u2_r"),
    _index("timeline_entry", ("users", 1), ("date", -1), name="users_date"),
    _index("timeline_entry", ("type", 1), ("date", -1), name="type_date"),
    _index("timeline_entry", ("data.actor", 1), sparse=True),
    _index(
        "timeline_entry",
        ("date", 1),
        name="date_ttl",
        expire_after_seconds=TIMELINE_RETENTION_SECONDS,
    ),
    _index(
        "timeline_unsub",
        ("user", 1),
        ("channel", 1),
        name="user_channel",
        unique=True,
    ),
    # The large game collection. New scan-heavy indexes are built explicitly,
    # while the tournament-effect recovery index is delayed until after boot.
    _index("game", ("us", 1)),
    _index("game", ("r", 1)),
    _index("game", ("v", 1)),
    _index("game", ("y", 1)),
    _index("game", ("by", 1)),
    _index("game", ("c", 1)),
    _index("game", ("tid", 1)),
    _index("game", ("sid", 1), sparse=True, startup_policy=StartupPolicy.MANUAL),
    _index("game", ("aid", 1), sparse=True, startup_policy=StartupPolicy.MANUAL),
    _index(
        "game",
        ("d", -1),
        ("_id", -1),
        name="d_id_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("v", 1),
        ("d", -1),
        ("_id", -1),
        name="v_d_id_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("us", 1),
        ("d", -1),
        name="us_d_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("us", 1),
        ("s", 1),
        ("d", -1),
        name="us_s_d_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("us.0", 1),
        ("d", -1),
        name="us0_d_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("us.1", 1),
        ("d", -1),
        name="us1_d_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("us.0", 1),
        ("us.1", 1),
        ("d", -1),
        name="us0_us1_d_desc",
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "game",
        ("fx", 1),
        sparse=True,
        startup_policy=StartupPolicy.AFTER_STARTUP,
    ),
    # Studies. Owner/member/write-member indexes support personal list and contributor lookups.
    # Keep private/unlisted documents out of the separate public-discovery indexes.
    _index("study", ("owner", 1), ("updatedAt", -1), name="owner_updatedAt"),
    _index("study", ("owner", 1), ("createdAt", 1), ("_id", 1), name="owner_createdAt"),
    _index("study", ("owner", 1), ("name", 1), ("_id", 1), name="owner_name"),
    _index("study", ("writeMembers", 1), ("updatedAt", -1), name="writeMembers_updatedAt"),
    _index("study", ("memberIds", 1), ("updatedAt", -1), name="memberIds_updatedAt"),
    _index(
        "study",
        ("memberIds", 1),
        ("createdAt", 1),
        ("_id", 1),
        name="memberIds_createdAt",
    ),
    _index("study", ("memberIds", 1), ("name", 1), ("_id", 1), name="memberIds_name"),
    _index("study", ("likers", 1), ("updatedAt", -1), name="likers_updatedAt"),
    _index(
        "study",
        ("updatedAt", -1),
        ("_id", 1),
        name="public_updatedAt",
        partial_filter={"visibility": "public"},
    ),
    _index(
        "study",
        ("createdAt", 1),
        ("_id", 1),
        name="public_createdAt",
        partial_filter={"visibility": "public"},
    ),
    _index(
        "study",
        ("name", 1),
        ("_id", 1),
        name="public_name",
        partial_filter={"visibility": "public"},
    ),
    _index(
        "study",
        ("searchTokens", 1),
        ("updatedAt", -1),
        ("_id", 1),
        name="searchTokens_updatedAt",
    ),
    _index(
        "study",
        ("topics", 1),
        ("updatedAt", -1),
        ("_id", 1),
        name="topics_updatedAt",
    ),
    _index("study_chapter", ("studyId", 1), ("order", 1), name="studyId_order"),
    # Notifications, inboxes, teams, forums, and moderation.
    _index("notify", ("notifies", 1)),
    # createdAt is a BSON date even in legacy documents, unlike expireAt strings.
    _index(
        "notify",
        ("createdAt", 1),
        expire_after_seconds=int(NOTIFY_EXPIRE_WEEKS.total_seconds()),
    ),
    _index("notify", ("content.arr", 1), sparse=True),
    _index("push_subscription", ("user", 1)),
    _index(
        "push_subscription",
        ("user", 1),
        ("endpoint", 1),
        name="push_user_endpoint",
        unique=True,
    ),
    _index("inbox_thread", ("users", 1)),
    _index("inbox_msg", ("tid", 1), ("createdAt", 1)),
    _index("inbox_msg", ("from", 1)),
    _index("team", ("enabled", 1), ("memberCount", -1), ("createdAt", -1)),
    _index("team", ("createdBy", 1), ("createdAt", -1)),
    _index("team_member", ("team", 1)),
    _index("team_member", ("user", 1)),
    _index("team_member", ("user", 1), ("permissions", 1)),
    _index("team_update", ("team", 1), ("createdAt", -1)),
    _index("team_update", ("sender", 1)),
    _index(
        "team_update",
        ("createdAt", 1),
        name="team_update_ttl",
        expire_after_seconds=TEAM_UPDATE_RETENTION_SECONDS,
    ),
    _index("team_request", ("team", 1), ("declined", 1), ("createdAt", 1)),
    _index("team_request", ("team", 1), ("declined", 1), ("processedAt", -1)),
    _index("team_request", ("user", 1)),
    _index("forum_categ", ("order", 1)),
    _index("forum_topic", ("categId", 1), ("sticky", -1), ("updatedAt", -1)),
    _index(
        "forum_topic",
        ("categId", 1),
        ("slug", 1),
        name="forum_topic_categ_slug",
        unique=True,
    ),
    _index("forum_topic", ("user", 1)),
    _index("forum_post", ("topicId", 1), ("createdAt", 1)),
    _index("forum_post", ("categId", 1), ("createdAt", -1)),
    _index("forum_post", ("user", 1)),
    _index("forum_post", ("text", "text")),
    _index("user_report", ("createdAt", 1)),
    _index("user_report", ("status", 1)),
    _index("user_report", ("reporter", 1)),
    _index("mod_log", ("createdAt", 1)),
    _index("mod_log", ("user", 1)),
    _index("seek", ("expireAt", 1), expire_after_seconds=0),
    _index("seek", ("user", 1)),
    _index("seek", ("rrArrangementId", 1), sparse=True),
    _index("bot_token", ("user", 1)),
    _index("external_engine", ("user", 1)),
    _index("external_engine", ("expiresAt", 1), expire_after_seconds=0),
    _index("account_reopen_token", ("username", 1)),
    _index("security_ban_signal", ("expireAt", 1), expire_after_seconds=0),
    # User-generated blogs and account lookup.
    _index("ublog_post", ("author", 1), ("live", 1), ("publishedAt", -1)),
    _index("ublog_post", ("live", 1), ("sticky", -1), ("publishedAt", -1)),
    _index("ublog_post", ("live", 1), ("blogType", 1), ("publishedAt", -1)),
    _index("ublog_post", ("legacyBlogId", 1)),
    _index("ublog_post", ("topics", 1)),
    _index("ublog_post2", ("author", 1), ("live", 1), ("publishedAt", -1)),
    _index("ublog_post2", ("live", 1), ("sticky", -1), ("publishedAt", -1)),
    _index("ublog_post2", ("live", 1), ("blogType", 1), ("publishedAt", -1)),
    _index("ublog_post2", ("legacyBlogId", 1)),
    _index("ublog_post2", ("topics", 1)),
    _index("config", ("name", 1)),
    # These support manual investigation scripts rather than server queries.
    _index("cheat_report", ("createdAt", 1), startup_policy=StartupPolicy.MANUAL),
    _index("cheat_report", ("gameId", 1), startup_policy=StartupPolicy.MANUAL),
    _index("cheat_report", ("suspect", 1), startup_policy=StartupPolicy.MANUAL),
    _index(
        "user",
        ("oauth_provider", 1),
        ("oauth_id", 1),
        startup_policy=StartupPolicy.MANUAL,
    ),
    _index(
        "user",
        ("username_lower", 1),
        name="username_lower",
        partial_filter={"username_lower": {"$type": "string"}},
        startup_policy=StartupPolicy.MANUAL,
    ),
    # Simul and catalogued-variant queries.
    _index("simul", ("status", 1)),
    _index("simul", ("createdAt", 1)),
    _index("simul", ("hostSeenAt", 1)),
    _index("simul", ("players.user", 1)),
    _index("simul", ("pendingPlayers.user", 1)),
    _index(
        "simul",
        ("status", 1),
        ("featurable", 1),
        ("hostSeenAt", -1),
        ("createdAt", -1),
        name="status_featurable_hostSeenAt_createdAt",
    ),
    _index(
        "simul",
        ("status", 1),
        ("featurable", 1),
        ("endsAt", -1),
        name="status_featurable_endsAt",
    ),
    _index(
        "simul",
        ("createdBy", 1),
        ("status", 1),
        ("createdAt", -1),
        name="createdBy_status_createdAt",
    ),
    _index("catalogued_variant", ("enabled", 1)),
    _index("catalogued_variant", ("archived", 1)),
    _index("catalogued_variant", ("author", 1)),
    _index("catalogued_variant", ("visibility", 1)),
    _index("catalogued_variant", ("createdAt", 1)),
    _index("catalogued_variant", ("source", 1)),
)


LEGACY_OPTIONAL_INDEXES = (_index("lobbychat", ("user", 1)),)

# Exact historical definitions that can be removed safely before auditing the
# current schema.
OBSOLETE_INDEXES = (
    # Notifications now expire by their BSON createdAt date, not expireAt strings.
    _index("notify", ("expireAt", 1), expire_after_seconds=0),
    # Study search uses one full index for both public and member-visible searches.
    _index(
        "study",
        ("searchTokens", 1),
        ("updatedAt", -1),
        ("_id", 1),
        name="public_searchTokens_updatedAt",
        partial_filter={"visibility": "public"},
    ),
)

ALL_KNOWN_COLLECTIONS = COLLECTIONS + LEGACY_OPTIONAL_COLLECTIONS
ALL_KNOWN_INDEXES = INDEXES + LEGACY_OPTIONAL_INDEXES
COLLECTIONS_BY_NAME = {spec.name: spec for spec in COLLECTIONS}
INDEXES_BY_COLLECTION = {
    collection_name: tuple(spec for spec in INDEXES if spec.collection == collection_name)
    for collection_name in COLLECTIONS_BY_NAME
}
