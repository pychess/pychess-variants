from __future__ import annotations

from hashlib import sha256

from bson import BSON

from study.document import encode_chapter
from study.models import Study, StudyChapter


async def chapter_snapshot_token(chapter: StudyChapter) -> str:
    """Opaque fingerprint for one persisted Study chapter snapshot.

    Chapter ``revision`` intentionally tracks collaborative mutations, while
    Fishnet/server-analysis updates can also change the stored tree. Hash the
    complete persisted chapter document so HTTP snapshots can be verified
    against the websocket stream without relying on revision semantics alone.
    """

    encoded = await encode_chapter(chapter, snapshot=True)
    assert encoded.snapshot_token is not None
    return encoded.snapshot_token


def study_snapshot_token(study: Study, chapters: list[dict[str, object]]) -> str:
    """Fingerprint Study-wide state installed from an HTTP Study snapshot.

    Chapter content has its own token.  This token covers the persisted Study
    document plus the ordered lightweight chapter previews that the client also
    replaces during chapter navigation.  Derived viewer capabilities are a
    deterministic function of this Study document and the connected user, so a
    membership/settings change also invalidates the room snapshot.
    """

    return sha256(
        BSON.encode(
            {
                "study": study.to_document(),
                "chapters": chapters,
            }
        )
    ).hexdigest()[:32]
