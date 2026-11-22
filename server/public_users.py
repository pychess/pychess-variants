from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import MINYEAR, UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING

from const import ANON_PREFIX, BLOCK, MAX_USER_BLOCK
from glicko2.glicko2 import sparse_perf_map
from typing_defs import BotEngineInfo, PerfMap, RelationDocument, UserCount, UserDocument
from user_stats import normalize_user_count
from variants import RATED_VARIANTS

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User


PUBLIC_PROFILE_CACHE_TTL_SECONDS = 60.0
PUBLIC_TITLE_CACHE_TTL_SECONDS = 300.0
PUBLIC_PATRON_CACHE_TTL_SECONDS = 300.0
PUBLIC_CACHE_CLEANUP_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True)
class PublicProfile:
    username: str
    title: str
    bot: bool
    enabled: bool
    patron: bool
    created_at: datetime
    count: UserCount
    perfs: PerfMap
    blocked: frozenset[str]
    pm_friends_only: bool
    oauth_id: str
    oauth_provider: str
    tournament_points: int | float = 0
    forum_posts: int = 0
    variant_count: int = 0
    bot_engine: BotEngineInfo | None = None


class PublicUsers:
    def __init__(self, app_state: PychessGlobalAppState) -> None:
        self.app_state = app_state
        self._profiles: dict[str, tuple[float, PublicProfile | None]] = {}
        self._titles: dict[str, tuple[float, str | None]] = {}
        self._patrons: dict[str, tuple[float, bool]] = {}
        self._last_cleanup = 0.0

    def _cleanup_if_needed(self) -> None:
        now = monotonic()
        if now - self._last_cleanup < PUBLIC_CACHE_CLEANUP_INTERVAL_SECONDS:
            return

        for cache in (self._profiles, self._titles, self._patrons):
            for key, (expires_at, _) in tuple(cache.items()):
                if expires_at <= now:
                    del cache[key]

        self._last_cleanup = now

    def _live_user(self, username: str) -> User | None:
        return self.app_state.users.data.get(username)

    @staticmethod
    def _profile_from_live_user(user: User) -> PublicProfile:
        return PublicProfile(
            username=user.username,
            title=user.title,
            bot=user.bot,
            enabled=user.enabled,
            patron=user.patron,
            created_at=user.created_at,
            count=normalize_user_count(user.count),
            perfs=user.perfs,
            blocked=frozenset(user.blocked),
            pm_friends_only=user.pm_friends_only,
            oauth_id=user.oauth_id,
            oauth_provider=user.oauth_provider,
            tournament_points=user.tournament_points,
            forum_posts=user.forum_posts,
            variant_count=user.variant_count,
            bot_engine=user.bot_engine if user.bot else None,
        )

    @staticmethod
    def _profile_from_doc(
        username: str,
        doc: UserDocument,
        blocked: frozenset[str],
    ) -> PublicProfile:
        title = doc.get("title") or ""
        return PublicProfile(
            username=username,
            title=title,
            bot=title == "BOT",
            enabled=doc.get("enabled", True),
            patron=doc.get("patron", False),
            created_at=doc.get("createdAt", datetime(MINYEAR, 1, 1, tzinfo=UTC)),
            count=normalize_user_count(doc.get("count")),
            perfs=sparse_perf_map(RATED_VARIANTS, doc.get("perfs")),
            blocked=blocked,
            pm_friends_only=doc.get("pmf", False),
            oauth_id=doc.get("oauth_id") or "",
            oauth_provider=doc.get("oauth_provider") or "",
            tournament_points=doc.get("tournamentPoints", 0),
            forum_posts=doc.get("forumPosts", 0),
            variant_count=doc.get("variantCount", 0),
            bot_engine=doc.get("botEngine") if title == "BOT" else None,
        )

    @staticmethod
    def _anon_profile(username: str) -> PublicProfile:
        return PublicProfile(
            username=username,
            title="",
            bot=False,
            enabled=True,
            patron=False,
            created_at=datetime(MINYEAR, 1, 1, tzinfo=UTC),
            count=normalize_user_count(None),
            perfs={},
            blocked=frozenset(),
            pm_friends_only=False,
            oauth_id="",
            oauth_provider="",
        )

    def invalidate(self, username: str) -> None:
        """Drop cached public data after an account attribute changes."""
        self._profiles.pop(username, None)
        self._titles.pop(username, None)
        self._patrons.pop(username, None)

    async def get_profile(
        self,
        username: str,
        *,
        cache: bool = True,
        include_blocked: bool = True,
    ) -> PublicProfile | None:
        live_user = self._live_user(username)
        if live_user is not None:
            return self._profile_from_live_user(live_user)

        if cache:
            self._cleanup_if_needed()
            cached = self._profiles.get(username)
            now = monotonic()
            if cached is not None and cached[0] > now:
                return cached[1]
        else:
            now = monotonic()

        if username.startswith(ANON_PREFIX):
            profile = self._anon_profile(username)
            if cache:
                self._profiles[username] = (now + PUBLIC_PROFILE_CACHE_TTL_SECONDS, profile)
                self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, "")
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)
            return profile

        if self.app_state.db is None:
            if cache:
                self._profiles[username] = (now + PUBLIC_PROFILE_CACHE_TTL_SECONDS, None)
            return None

        doc: UserDocument | None = await self.app_state.db.user.find_one({"_id": username})
        if doc is None:
            if cache:
                self._profiles[username] = (now + PUBLIC_PROFILE_CACHE_TTL_SECONDS, None)
                self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, None)
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)
            return None

        blocked: frozenset[str] = frozenset()
        if include_blocked:
            cursor = self.app_state.db.relation.find(
                {"u1": username, "r": BLOCK}, projection={"_id": 0, "u2": 1}
            )
            docs: list[RelationDocument] = await cursor.to_list(MAX_USER_BLOCK)
            blocked = frozenset(relation["u2"] for relation in docs)

        profile = self._profile_from_doc(
            username=username,
            doc=doc,
            blocked=blocked,
        )
        if cache:
            self._profiles[username] = (now + PUBLIC_PROFILE_CACHE_TTL_SECONDS, profile)
            self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, profile.title)
            self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, profile.patron)
        return profile

    async def get_patrons(self, usernames: Iterable[str]) -> set[str]:
        """Return patron usernames using live/cache data plus at most one Mongo query."""
        self._cleanup_if_needed()
        now = monotonic()
        unique_usernames = tuple(dict.fromkeys(username for username in usernames if username))
        patrons: set[str] = set()
        missing: list[str] = []

        for username in unique_usernames:
            live_user = self._live_user(username)
            if live_user is not None:
                if live_user.patron:
                    patrons.add(username)
                continue

            cached_profile = self._profiles.get(username)
            if cached_profile is not None and cached_profile[0] > now:
                patron = cached_profile[1] is not None and cached_profile[1].patron
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, patron)
                if patron:
                    patrons.add(username)
                continue

            cached_patron = self._patrons.get(username)
            if cached_patron is not None and cached_patron[0] > now:
                if cached_patron[1]:
                    patrons.add(username)
                continue

            if username.startswith(ANON_PREFIX):
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)
                continue

            missing.append(username)

        if len(missing) == 0 or self.app_state.db is None:
            return patrons

        docs = await self.app_state.db.user.find(
            {"_id": {"$in": missing}, "patron": True},
            projection={"_id": 1},
        ).to_list(None)
        found = {doc["_id"] for doc in docs}
        patrons.update(found)
        for username in missing:
            self._patrons[username] = (
                now + PUBLIC_PATRON_CACHE_TTL_SECONDS,
                username in found,
            )
        return patrons

    async def get_titles_and_patrons(
        self, usernames: Iterable[str]
    ) -> tuple[dict[str, str], set[str]]:
        """Resolve titles and patron flags together with at most one Mongo query."""
        self._cleanup_if_needed()
        now = monotonic()
        unique_usernames = tuple(dict.fromkeys(username for username in usernames if username))
        titles: dict[str, str] = {}
        patrons: set[str] = set()
        missing: list[str] = []

        for username in unique_usernames:
            live_user = self._live_user(username)
            if live_user is not None:
                titles[username] = live_user.title
                if live_user.patron:
                    patrons.add(username)
                continue

            if username.startswith(ANON_PREFIX):
                titles[username] = ""
                self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, "")
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)
                continue

            cached_profile = self._profiles.get(username)
            if cached_profile is not None and cached_profile[0] > now:
                profile = cached_profile[1]
                if profile is not None:
                    titles[username] = profile.title
                    if profile.patron:
                        patrons.add(username)
                    self._titles[username] = (
                        now + PUBLIC_TITLE_CACHE_TTL_SECONDS,
                        profile.title,
                    )
                    self._patrons[username] = (
                        now + PUBLIC_PATRON_CACHE_TTL_SECONDS,
                        profile.patron,
                    )
                continue

            cached_title = self._titles.get(username)
            title_known = cached_title is not None and cached_title[0] > now
            if title_known and cached_title is not None and cached_title[1] is not None:
                titles[username] = cached_title[1]

            cached_patron = self._patrons.get(username)
            patron_known = cached_patron is not None and cached_patron[0] > now
            if patron_known and cached_patron is not None and cached_patron[1]:
                patrons.add(username)

            if title_known and patron_known:
                continue

            missing.append(username)

        if len(missing) == 0 or self.app_state.db is None:
            return titles, patrons

        docs = await self.app_state.db.user.find(
            {"_id": {"$in": missing}},
            projection={"_id": 1, "title": 1, "patron": 1},
        ).to_list(None)
        found = {doc["_id"]: doc for doc in docs}
        for username in missing:
            doc = found.get(username)
            title = (doc.get("title") or "") if doc is not None else None
            patron = bool(doc is not None and doc.get("patron", False))
            self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, title)
            self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, patron)
            if title is not None:
                titles[username] = title
            if patron:
                patrons.add(username)

        return titles, patrons

    async def get_titles(self, usernames: Iterable[str]) -> dict[str, str]:
        self._cleanup_if_needed()
        now = monotonic()
        unique_usernames = tuple(dict.fromkeys(username for username in usernames if username))
        titles: dict[str, str] = {}
        missing: list[str] = []

        for username in unique_usernames:
            live_user = self._live_user(username)
            if live_user is not None:
                titles[username] = live_user.title
                continue

            if username.startswith(ANON_PREFIX):
                titles[username] = ""
                self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, "")
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)
                continue

            cached = self._titles.get(username)
            if cached is not None and cached[0] > now:
                if cached[1] is not None:
                    titles[username] = cached[1]
                continue

            missing.append(username)

        if len(missing) == 0 or self.app_state.db is None:
            return titles

        docs = await self.app_state.db.user.find(
            {"_id": {"$in": missing}},
            projection={"_id": 1, "title": 1},
        ).to_list(None)
        found: dict[str, str] = {}
        for doc in docs:
            username = doc["_id"]
            title = doc.get("title") or ""
            found[username] = title
            self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, title)

        for username in missing:
            if username in found:
                titles[username] = found[username]
            else:
                self._titles[username] = (now + PUBLIC_TITLE_CACHE_TTL_SECONDS, None)
                self._patrons[username] = (now + PUBLIC_PATRON_CACHE_TTL_SECONDS, False)

        return titles
