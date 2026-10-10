from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

import settings
from newid import new_id
from typing_defs import AnalysisStep

from study.annotations import canonical_description, canonical_tags
from study.constants import (
    STUDY_MAX_TOPICS,
    STUDY_SEARCH_MAX_TOKENS,
    STUDY_TOPIC_MAX_LENGTH,
    STUDY_TOPIC_MIN_LENGTH,
)
from study.tree import StudyTree

StudyVisibility = Literal["private", "unlisted", "public"]
StudyMemberRole = Literal["read", "write"]
StudySourceKind = Literal["scratch", "game", "study", "import"]
StudyOrientation = Literal["white", "black"]
StudyChapterMode = Literal["normal", "practice", "conceal", "gamebook"]
StudyUserSelection = Literal["nobody", "owner", "contributor", "member", "everyone"]

_VISIBILITIES = frozenset(("private", "unlisted", "public"))
_MEMBER_ROLES = frozenset(("read", "write"))
_SOURCE_KINDS = frozenset(("scratch", "game", "study", "import"))
_ORIENTATIONS = frozenset(("white", "black"))
STUDY_CHAPTER_MODES: tuple[StudyChapterMode, ...] = ("normal", "practice", "conceal", "gamebook")
STUDY_DEFAULT_ENABLED_CHAPTER_MODES: tuple[StudyChapterMode, ...] = (
    "normal",
    "practice",
    "gamebook",
)
_CHAPTER_MODES = frozenset(STUDY_CHAPTER_MODES)


def _configured_study_chapter_modes(
    raw: str | None, *, dev: bool = False
) -> tuple[StudyChapterMode, ...]:
    """Return the chapter modes authors may newly select on this deployment.

    DEV always exposes every schema-known mode so incomplete rollout gates do not
    block authoring, PGN import, or Practice content testing. Production keeps the
    staged entry gate: existing chapters remain readable even when a mode is not
    enabled for new data.
    """

    requested: set[str] | None = None
    if raw is not None and raw.strip():
        requested = {part.strip() for part in raw.split(",") if part.strip()}
        unknown = requested - _CHAPTER_MODES
        if unknown:
            values = ", ".join(sorted(unknown))
            raise RuntimeError(f"Unknown STUDY_ENABLED_CHAPTER_MODES value(s): {values}")

    if dev:
        return STUDY_CHAPTER_MODES
    if requested is None:
        return STUDY_DEFAULT_ENABLED_CHAPTER_MODES

    # Normal analysis is the schema baseline and the escape hatch from a disabled
    # training mode, so never allow an operator setting to remove it.
    requested.add("normal")
    return tuple(mode for mode in STUDY_CHAPTER_MODES if mode in requested)


STUDY_ENABLED_CHAPTER_MODES = _configured_study_chapter_modes(
    os.getenv("STUDY_ENABLED_CHAPTER_MODES"), dev=settings.DEV
)
_USER_SELECTIONS = frozenset(("nobody", "owner", "contributor", "member", "everyone"))


def study_visibility(value: object) -> StudyVisibility:
    if not isinstance(value, str) or value not in _VISIBILITIES:
        raise ValueError(f"Unknown Study visibility: {value!r}")
    return cast(StudyVisibility, value)


def study_member_role(value: object) -> StudyMemberRole:
    if not isinstance(value, str) or value not in _MEMBER_ROLES:
        raise ValueError(f"Unknown Study member role: {value!r}")
    return cast(StudyMemberRole, value)


def study_user_selection(value: object) -> StudyUserSelection:
    if not isinstance(value, str) or value not in _USER_SELECTIONS:
        raise ValueError(f"Unknown Study user selection: {value!r}")
    return cast(StudyUserSelection, value)


def study_chapter_mode(value: object) -> StudyChapterMode:
    if not isinstance(value, str) or value not in _CHAPTER_MODES:
        raise ValueError(f"Unknown Study chapter mode: {value!r}")
    return cast(StudyChapterMode, value)


def study_enabled_chapter_modes() -> tuple[StudyChapterMode, ...]:
    return STUDY_ENABLED_CHAPTER_MODES


def study_chapter_mode_enabled(mode: StudyChapterMode) -> bool:
    return mode in STUDY_ENABLED_CHAPTER_MODES


def study_conceal_ply(
    mode: StudyChapterMode,
    value: object,
    root: StudyTree,
) -> int | None:
    """Validate the stored conceal boundary as depth from the chapter root.

    Unlike Lichess's absolute FEN ply, PyChess stores the number of preferred
    mainline moves revealed from this chapter's own root. Existing documents that
    predate analysis modes have no boundary and remain normal chapters. A concealed
    chapter with no stored boundary starts fully hidden at root depth 0.
    """

    if mode != "conceal":
        if value is not None:
            raise ValueError("Study concealPly is only valid in conceal mode")
        return None
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Study concealPly must be a non-negative integer")
    mainline_depth = len(root.preferred_mainline())
    if value > mainline_depth:
        raise ValueError(
            f"Study concealPly {value} exceeds preferred mainline depth {mainline_depth}"
        )
    return value


def study_topic(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Study topic must be a string")
    clean = " ".join(value.split())
    if not STUDY_TOPIC_MIN_LENGTH <= len(clean) <= STUDY_TOPIC_MAX_LENGTH:
        raise ValueError(
            f"Study topics must be {STUDY_TOPIC_MIN_LENGTH}-{STUDY_TOPIC_MAX_LENGTH} characters"
        )
    return clean


def study_topics(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("Study topics must be a list")
    topics: list[str] = []
    for raw_topic in value:
        topic = study_topic(raw_topic)
        if topic not in topics:
            topics.append(topic)
        if len(topics) > STUDY_MAX_TOPICS:
            raise ValueError(f"A Study can have at most {STUDY_MAX_TOPICS} topics")
    return tuple(topics)


def _search_words(value: str) -> tuple[str, ...]:
    words: list[str] = []
    current: list[str] = []
    for char in value.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current.clear()
    if current:
        words.append("".join(current))
    return tuple(words)


def study_search_tokens(name: str, owner: str, *content: str) -> tuple[str, ...]:
    """Return bounded word-prefix tokens for Study discovery.

    The Study name and owner are always passed first so they retain priority if
    unusually large chapter metadata reaches the global token budget. Chapter
    names, variants, descriptions, and PGN tags are appended by the storage
    layer for richer discovery.
    """

    tokens: set[str] = set()
    for value in (name, owner, *content):
        for word in _search_words(value):
            if len(word) < 3:
                continue
            # Cap each individual prefix and the complete multikey array. Long
            # annotation text must never grow the Study index without bound.
            for length in range(3, min(len(word), 32) + 1):
                tokens.add(word[:length])
                if len(tokens) >= STUDY_SEARCH_MAX_TOKENS:
                    return tuple(sorted(tokens))
    return tuple(sorted(tokens))


def study_search_query_tokens(value: str) -> tuple[str, ...]:
    """Normalize a user query to the same searchable word-prefix vocabulary."""

    return tuple(dict.fromkeys(word[:32] for word in _search_words(value) if len(word) >= 3))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required_str(doc: Mapping[str, object], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Study document field {key!r} must be a non-empty string")
    return value


def _optional_str(doc: Mapping[str, object], key: str) -> str | None:
    value = doc.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Study document field {key!r} must be a string or null")
    return value or None


def _required_datetime(doc: Mapping[str, object], key: str) -> datetime:
    value = doc.get(key)
    if not isinstance(value, datetime):
        raise TypeError(f"Study document field {key!r} must be a datetime")
    return _utc(value)


def _nonnegative_int(doc: Mapping[str, object], key: str, *, default: int | None = None) -> int:
    value = doc.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Study document field {key!r} must be a non-negative integer")
    return value


def _positive_int(doc: Mapping[str, object], key: str) -> int:
    value = doc.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"Study document field {key!r} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class StudySource:
    kind: StudySourceKind = "scratch"
    source_id: str | None = None

    def encode(self) -> str:
        if self.kind in ("game", "study"):
            if not self.source_id:
                raise ValueError(f"Study source {self.kind!r} requires an id")
            return f"{self.kind} {self.source_id}"
        if self.source_id:
            raise ValueError(f"Study source {self.kind!r} does not accept an id")
        return self.kind

    @classmethod
    def decode(cls, value: object) -> StudySource:
        if not isinstance(value, str) or not value:
            raise ValueError("Study source must be a non-empty string")
        kind, separator, source_id = value.partition(" ")
        if kind not in _SOURCE_KINDS:
            raise ValueError(f"Unknown Study source kind: {kind!r}")
        typed_kind = cast(StudySourceKind, kind)
        if typed_kind in ("game", "study"):
            if not separator or not source_id:
                raise ValueError(f"Study source {typed_kind!r} requires an id")
            return cls(typed_kind, source_id)
        if separator:
            raise ValueError(f"Study source {typed_kind!r} does not accept an id")
        return cls(typed_kind)


@dataclass(frozen=True, slots=True)
class Study:
    id: str
    name: str
    owner: str
    members: Mapping[str, StudyMemberRole]
    created_at: datetime
    updated_at: datetime
    visibility: StudyVisibility = "private"
    source: StudySource = field(default_factory=StudySource)
    current_chapter: str | None = None
    current_path: str | None = None
    settings: Mapping[str, object] = field(default_factory=dict)
    revision: int = 0
    likers: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()

    @property
    def likes(self) -> int:
        return len(self.likers)

    def is_liked_by(self, username: str | None) -> bool:
        return bool(username) and username in self.likers

    def to_document(self) -> dict[str, object]:
        if self.owner not in self.members or self.members[self.owner] != "write":
            raise ValueError("Study owner must be a write member")
        if self.visibility not in _VISIBILITIES:
            raise ValueError(f"Unknown Study visibility: {self.visibility!r}")
        if self.revision < 0:
            raise ValueError("Study revision must be non-negative")
        if any(not username for username in self.likers) or len(set(self.likers)) != len(
            self.likers
        ):
            raise ValueError("Study likers must be unique non-empty usernames")
        canonical_topics = study_topics(self.topics)
        if canonical_topics != self.topics:
            raise ValueError("Study topics must be canonical and unique")

        doc: dict[str, object] = {
            "_id": self.id,
            "name": self.name,
            "owner": self.owner,
            "members": dict(self.members),
            "memberIds": sorted(self.members),
            "writeMembers": sorted(
                username for username, role in self.members.items() if role == "write"
            ),
            "visibility": self.visibility,
            "source": self.source.encode(),
            "createdAt": _utc(self.created_at),
            "updatedAt": _utc(self.updated_at),
            "revision": self.revision,
            "likers": list(self.likers),
            "likes": self.likes,
            "searchTokens": list(study_search_tokens(self.name, self.owner, *self.topics)),
        }
        if self.current_chapter is not None:
            doc["currentChapter"] = self.current_chapter
        if self.current_path is not None:
            doc["currentPath"] = self.current_path
        if self.settings:
            doc["settings"] = dict(self.settings)
        if self.topics:
            doc["topics"] = list(self.topics)
        return doc

    @classmethod
    def from_document(cls, doc: Mapping[str, object]) -> Study:
        owner = _required_str(doc, "owner")
        raw_members = doc.get("members")
        if not isinstance(raw_members, Mapping):
            raise TypeError("Study document field 'members' must be a mapping")
        members: dict[str, StudyMemberRole] = {}
        for username, role in raw_members.items():
            if not isinstance(username, str) or not username:
                raise ValueError("Study member usernames must be non-empty strings")
            if not isinstance(role, str) or role not in _MEMBER_ROLES:
                raise ValueError(f"Unknown Study member role for {username!r}: {role!r}")
            members[username] = cast(StudyMemberRole, role)
        if members.get(owner) != "write":
            raise ValueError("Study owner must be a write member")

        raw_visibility = study_visibility(doc.get("visibility", "private"))

        raw_settings = doc.get("settings", {})
        if not isinstance(raw_settings, Mapping):
            raise TypeError("Study document field 'settings' must be a mapping")

        raw_likers = doc.get("likers", [])
        if isinstance(raw_likers, list):
            likers_list: list[str] = []
            for username in raw_likers:
                if not isinstance(username, str) or not username:
                    raise ValueError("Study liker usernames must be non-empty strings")
                if username not in likers_list:
                    likers_list.append(username)
            likers = tuple(likers_list)
        else:
            raise TypeError("Study document field 'likers' must be a list")

        raw_topics = study_topics(doc.get("topics", []))

        return cls(
            id=_required_str(doc, "_id"),
            name=_required_str(doc, "name"),
            owner=owner,
            members=members,
            visibility=raw_visibility,
            source=StudySource.decode(doc.get("source", "scratch")),
            current_chapter=_optional_str(doc, "currentChapter"),
            current_path=_optional_str(doc, "currentPath"),
            settings={str(key): value for key, value in raw_settings.items()},
            created_at=_required_datetime(doc, "createdAt"),
            updated_at=_required_datetime(doc, "updatedAt"),
            revision=_nonnegative_int(doc, "revision", default=0),
            likers=likers,
            topics=raw_topics,
        )


@dataclass(frozen=True, slots=True)
class StudyServerEval:
    path: str
    done: bool
    requested_at: datetime
    analysis: tuple[AnalysisStep | None, ...] = ()

    def to_document(self) -> dict[str, object]:
        return {
            "path": self.path,
            "done": self.done,
            "requestedAt": _utc(self.requested_at),
            "analysis": [None if step is None else dict(step) for step in self.analysis],
        }

    def to_payload(self, *, pending: bool | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path,
            "done": self.done,
            "requestedAt": _utc(self.requested_at).isoformat(),
            "analysis": [None if step is None else dict(step) for step in self.analysis],
        }
        if pending is not None:
            payload["pending"] = pending
        return payload

    @classmethod
    def from_document(cls, doc: Mapping[str, object]) -> StudyServerEval:
        path = doc.get("path")
        if not isinstance(path, str):
            raise TypeError("Study serverEval field 'path' must be a string")
        done = doc.get("done")
        if not isinstance(done, bool):
            raise TypeError("Study serverEval field 'done' must be boolean")
        requested_at = _required_datetime(doc, "requestedAt")
        raw_analysis = doc.get("analysis", [])
        if not isinstance(raw_analysis, (list, tuple)):
            raise TypeError("Study serverEval field 'analysis' must be a list")

        analysis: list[AnalysisStep | None] = []
        for raw_step in raw_analysis:
            if raw_step is None:
                analysis.append(None)
                continue
            if not isinstance(raw_step, Mapping):
                raise TypeError("Study serverEval analysis entries must be mappings or null")
            step: AnalysisStep = {}
            raw_score = raw_step.get("s")
            if not isinstance(raw_score, Mapping):
                raise TypeError("Study serverEval analysis score must be a mapping")
            score: dict[str, int] = {}
            for key in ("cp", "mate"):
                value = raw_score.get(key)
                if value is not None:
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise TypeError(
                            f"Study serverEval analysis score {key!r} must be an integer"
                        )
                    score[key] = value
            if not score:
                raise ValueError("Study serverEval analysis score requires cp or mate")
            step["s"] = score
            depth = raw_step.get("d")
            if depth is not None:
                if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
                    raise ValueError("Study serverEval analysis depth must be non-negative")
                step["d"] = depth
            pv = raw_step.get("p")
            if pv is not None:
                if not isinstance(pv, str):
                    raise TypeError("Study serverEval analysis PV must be a string")
                step["p"] = pv
            analysis.append(step)
        return cls(path=path, done=done, requested_at=requested_at, analysis=tuple(analysis))


@dataclass(frozen=True, slots=True)
class StudyChapter:
    id: str
    study_id: str
    name: str
    order: int
    owner: str
    variant: str
    initial_fen: str
    orientation: StudyOrientation
    root: StudyTree
    created_at: datetime
    updated_at: datetime
    chess960: bool = False
    variant_ini: str | None = None
    mode: StudyChapterMode = "normal"
    conceal_ply: int | None = None
    source: StudySource = field(default_factory=StudySource)
    description: str = ""
    tags: Mapping[str, str] = field(default_factory=dict)
    server_eval: StudyServerEval | None = None
    revision: int = 0

    def to_document(self, *, root_document: dict[str, object] | None = None) -> dict[str, object]:
        if self.order < 1:
            raise ValueError("Study chapter order must be positive")
        if self.orientation not in _ORIENTATIONS:
            raise ValueError(f"Unknown Study chapter orientation: {self.orientation!r}")
        if self.revision < 0:
            raise ValueError("Study chapter revision must be non-negative")
        mode = study_chapter_mode(self.mode)
        conceal_ply = study_conceal_ply(mode, self.conceal_ply, self.root)
        description = canonical_description(self.description)
        tags = canonical_tags(self.tags)

        doc: dict[str, object] = {
            "_id": self.id,
            "studyId": self.study_id,
            "name": self.name,
            "order": self.order,
            "owner": self.owner,
            "variant": self.variant,
            "initialFen": self.initial_fen,
            "orientation": self.orientation,
            "mode": mode,
            "root": self.root.to_document() if root_document is None else root_document,
            "createdAt": _utc(self.created_at),
            "updatedAt": _utc(self.updated_at),
            "revision": self.revision,
        }
        if self.chess960:
            doc["chess960"] = True
        if self.variant_ini is not None:
            doc["variantIni"] = self.variant_ini
        if conceal_ply is not None:
            doc["concealPly"] = conceal_ply
        if self.source.kind != "scratch":
            doc["source"] = self.source.encode()
        if description:
            doc["description"] = description
        if tags:
            doc["tags"] = tags
        if self.server_eval is not None:
            doc["serverEval"] = self.server_eval.to_document()
        return doc

    @classmethod
    def from_document(cls, doc: Mapping[str, object]) -> StudyChapter:
        raw_orientation = doc.get("orientation")
        if not isinstance(raw_orientation, str) or raw_orientation not in _ORIENTATIONS:
            raise ValueError(f"Unknown Study chapter orientation: {raw_orientation!r}")
        raw_root = doc.get("root")
        if not isinstance(raw_root, Mapping):
            raise TypeError("Study chapter field 'root' must be a mapping")
        raw_chess960 = doc.get("chess960", False)
        if not isinstance(raw_chess960, bool):
            raise TypeError("Study chapter field 'chess960' must be boolean")
        raw_tags = doc.get("tags", {})
        raw_server_eval = doc.get("serverEval")
        if raw_server_eval is not None and not isinstance(raw_server_eval, Mapping):
            raise TypeError("Study chapter field 'serverEval' must be a mapping or null")
        root = StudyTree.from_document(raw_root)
        mode = study_chapter_mode(doc.get("mode", "normal"))
        conceal_ply = study_conceal_ply(mode, doc.get("concealPly"), root)

        return cls(
            id=_required_str(doc, "_id"),
            study_id=_required_str(doc, "studyId"),
            name=_required_str(doc, "name"),
            order=_positive_int(doc, "order"),
            owner=_required_str(doc, "owner"),
            variant=_required_str(doc, "variant"),
            initial_fen=_required_str(doc, "initialFen"),
            orientation=cast(StudyOrientation, raw_orientation),
            root=root,
            created_at=_required_datetime(doc, "createdAt"),
            updated_at=_required_datetime(doc, "updatedAt"),
            chess960=raw_chess960,
            variant_ini=_optional_str(doc, "variantIni"),
            mode=mode,
            conceal_ply=conceal_ply,
            source=StudySource.decode(doc.get("source", "scratch")),
            description=canonical_description(doc.get("description", "")),
            tags=canonical_tags(raw_tags),
            server_eval=(
                StudyServerEval.from_document(raw_server_eval)
                if isinstance(raw_server_eval, Mapping)
                else None
            ),
            revision=_nonnegative_int(doc, "revision", default=0),
        )


async def make_study(
    table: Any | None,
    *,
    owner: str,
    name: str | None = None,
    visibility: StudyVisibility = "private",
    settings: Mapping[str, object] | None = None,
    source: StudySource | None = None,
    now: datetime | None = None,
) -> Study:
    created_at = _utc(now or datetime.now(UTC))
    return Study(
        id=await new_id(table),
        name=name or f"{owner}'s Study",
        owner=owner,
        members={owner: "write"},
        visibility=visibility,
        settings={} if settings is None else dict(settings),
        source=source or StudySource(),
        created_at=created_at,
        updated_at=created_at,
        likers=(owner,),
    )


async def make_chapter(
    table: Any | None,
    *,
    study_id: str,
    owner: str,
    variant: str,
    initial_fen: str,
    orientation: StudyOrientation,
    order: int,
    name: str | None = None,
    chess960: bool = False,
    variant_ini: str | None = None,
    mode: StudyChapterMode = "normal",
    conceal_ply: int | None = None,
    root: StudyTree | None = None,
    source: StudySource | None = None,
    description: str = "",
    tags: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> StudyChapter:
    created_at = _utc(now or datetime.now(UTC))
    chapter_root = StudyTree() if root is None else root
    clean_mode = study_chapter_mode(mode)
    clean_conceal_ply = study_conceal_ply(clean_mode, conceal_ply, chapter_root)
    return StudyChapter(
        id=await new_id(table),
        study_id=study_id,
        name=name or f"Chapter {order}",
        order=order,
        owner=owner,
        variant=variant,
        chess960=chess960,
        initial_fen=initial_fen,
        orientation=orientation,
        variant_ini=variant_ini,
        mode=clean_mode,
        conceal_ply=clean_conceal_ply,
        root=chapter_root,
        source=source or StudySource(),
        description=description,
        tags={} if tags is None else dict(tags),
        created_at=created_at,
        updated_at=created_at,
    )
