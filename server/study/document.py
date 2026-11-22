from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from struct import pack

from bson import BSON

from study.models import StudyChapter
from study.tree import STUDY_TREE_ROOT_KEY

_NODE_BATCH_SIZE = 32


@dataclass(frozen=True, slots=True)
class EncodedChapter:
    document: dict[str, object] | None
    size: int
    snapshot_token: str | None


async def encode_chapter(
    chapter: StudyChapter, *, include_document: bool = False, snapshot: bool = False
) -> EncodedChapter:
    """Size/hash canonical BSON in bounded batches, optionally keeping the document.

    A flat tree is a BSON subdocument. Batch encodings contribute their elements
    without their four-byte length and final NUL; the enclosing lengths are added
    once. This preserves the bytes (including field order) of BSON.encode on the
    complete chapter, without requiring one large synchronous tree conversion.
    """
    root: dict[str, object] = {}
    document = chapter.to_document(root_document=root)
    before_root: dict[str, object] = {}
    after_root: dict[str, object] = {}
    target = before_root
    for key, value in document.items():
        if key == "root":
            target = after_root
        else:
            target[key] = value
    prefix = BSON.encode(before_root)[4:-1]
    suffix = BSON.encode(after_root)[4:-1]
    root_size = 5
    root_parts: list[memoryview] = []
    batch: dict[str, object] = {STUDY_TREE_ROOT_KEY: chapter.root.root_to_document()}

    def flush() -> None:
        nonlocal root_size
        encoded = BSON.encode(batch)
        root_size += len(encoded) - 5
        if snapshot:
            root_parts.append(memoryview(encoded)[4:-1])
        if include_document:
            root.update(batch)
        batch.clear()

    for index, (node_id, node) in enumerate(chapter.root.nodes.items(), start=1):
        batch[node_id] = node.to_document()
        if index % _NODE_BATCH_SIZE == 0:
            flush()
            await asyncio.sleep(0)
    if batch:
        flush()

    # Outer framing (5 bytes), root type/key (6 bytes), and the complete root BSON.
    size = 5 + len(prefix) + 6 + root_size + len(suffix)
    token = None
    if snapshot:
        digest = sha256(pack("<i", size) + prefix + b"\x03root\x00" + pack("<i", root_size))
        for part in root_parts:
            digest.update(part)
            await asyncio.sleep(0)
        digest.update(b"\x00" + suffix + b"\x00")
        token = digest.hexdigest()[:32]
    return EncodedChapter(
        document=document if include_document else None, size=size, snapshot_token=token
    )
