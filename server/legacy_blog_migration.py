from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legacy_blog_catalog import legacy_blogs
from ublog import slugify_title

OFFICIAL_TAGS = {"Announcement", "Tournament"}
DATE_FORMATS = ("%Y-%m-%d", "%Y.%m.%d")
GITHUB_STATIC_PREFIX = "https://github.com/pychess/pychess-variants/blob/master/static/"
BREAK_TAG_RE = re.compile(r"^<\s*/?\s*br\s*/?\s*>$", re.IGNORECASE)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
IMG_SRC_RE = re.compile(r"""<img[^>]+src=['"]([^'"]+)['"][^>]*>""", re.IGNORECASE)


def parse_legacy_date(raw: str) -> datetime:
    value = str(raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {raw!r}")


def stable_post_id(legacy_id: str) -> str:
    return "L" + hashlib.sha1(legacy_id.encode("utf-8")).hexdigest()[:7]


def markdown_path(legacy_id: str) -> Path:
    base = Path(__file__).resolve().parent.parent
    primary = base / "static" / "blogs" / f"{legacy_id.replace('_', ' ')}.md"
    if primary.exists():
        return primary

    legacy_tokens = legacy_id.replace("_", " ").lower()
    for path in (base / "static" / "blogs").glob("*.md"):
        if path.stem.lower() == legacy_tokens:
            return path
    raise FileNotFoundError(f"Missing markdown for legacy blog {legacy_id!r}")


def normalize_github_static_urls(markdown: str) -> str:
    return markdown.replace(GITHUB_STATIC_PREFIX, "/static/")


def normalize_linebreaks(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "" or BREAK_TAG_RE.fullmatch(stripped):
            index += 1
            continue
        break
    return index


def div_delta(line: str) -> int:
    return line.lower().count("<div") - line.lower().count("</div>")


def remove_meta_headline(lines: list[str], start: int) -> int:
    index = start
    if index >= len(lines) or 'class="meta-headline"' not in lines[index].replace("'", '"'):
        return start

    depth = 0
    while index < len(lines):
        depth += div_delta(lines[index])
        index += 1
        if depth <= 0:
            break
    return index


def remove_leading_title(lines: list[str], start: int) -> int:
    index = start
    if index >= len(lines):
        return start
    if "<h1" not in lines[index].lower():
        return start
    while index < len(lines):
        if "</h1>" in lines[index].lower():
            return index + 1
        index += 1
    return index


def remove_leading_center_image_before_title(lines: list[str], start: int) -> int:
    index = start
    if index >= len(lines):
        return start
    if "<p" not in lines[index].lower() or "align=" not in lines[index].lower():
        return start
    end = index + 1
    while end < len(lines) and "</p>" not in lines[end].lower():
        end += 1
    if end < len(lines):
        end += 1
    probe = normalize_linebreaks(lines, end)
    if probe < len(lines) and "<h1" in lines[probe].lower():
        return end
    return start


def image_path_matches(url: str, legacy_image: str) -> bool:
    normalized = url.strip().replace("/blob/master", "")
    image_token = legacy_image.strip().lstrip("/")
    return image_token != "" and image_token in normalized


def remove_duplicate_hero(lines: list[str], legacy_image: str) -> list[str]:
    if legacy_image == "":
        return lines
    index = normalize_linebreaks(lines, 0)
    if index >= len(lines):
        return lines

    line = lines[index].strip()
    md_match = MARKDOWN_IMAGE_RE.search(line)
    if md_match and image_path_matches(md_match.group(1), legacy_image):
        return lines[:index] + lines[index + 1 :]

    if "<p" in line.lower() and "align=" in line.lower():
        end = index + 1
        block = [lines[index]]
        while end < len(lines):
            block.append(lines[end])
            if "</p>" in lines[end].lower():
                break
            end += 1
        block_text = "\n".join(block)
        img_match = IMG_SRC_RE.search(block_text)
        if img_match and image_path_matches(img_match.group(1), legacy_image):
            return lines[:index] + lines[min(end + 1, len(lines)) :]

    return lines


def strip_legacy_preamble(markdown: str, legacy_image: str) -> str:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = normalize_linebreaks(lines, 0)
    index = remove_leading_center_image_before_title(lines, index)
    index = normalize_linebreaks(lines, index)
    index = remove_leading_title(lines, index)
    index = normalize_linebreaks(lines, index)
    next_index = remove_meta_headline(lines, index)
    if next_index != index:
        index = next_index
        index = normalize_linebreaks(lines, index)
    body_lines = lines[index:]
    body_lines = remove_duplicate_hero(body_lines, legacy_image)
    return "\n".join(body_lines).strip()


def normalize_topics(tags: list[str], category: Any) -> list[str]:
    topics = [tag.lower() for tag in tags if isinstance(tag, str) and tag.strip() != ""]
    if isinstance(category, str) and category not in topics:
        topics.append(category)
    elif isinstance(category, list):
        for item in category:
            if isinstance(item, str) and item not in topics:
                topics.append(item)
    return topics[:5]


def to_ublog_doc(
    legacy: dict[str, Any], author_policy: str, strip_preamble: bool
) -> dict[str, Any]:
    legacy_id = str(legacy["_id"])
    md = markdown_path(legacy_id).read_text(encoding="utf-8")
    tags = [str(tag) for tag in legacy.get("tags", []) if isinstance(tag, str)]
    official = any(tag in OFFICIAL_TAGS for tag in tags)
    author = str(legacy.get("author") or "")
    if author_policy == "official-as-pychess" and official:
        author = "Pychess"

    published = parse_legacy_date(str(legacy.get("date") or ""))
    intro = str(legacy.get("intro") or legacy.get("subtitle") or "")
    image_alt = str(legacy.get("imageAlt") or legacy.get("alt") or "")
    image = str(legacy.get("image") or "")
    category = legacy.get("category", "all")
    markdown = normalize_github_static_urls(md)
    if strip_preamble:
        markdown = strip_legacy_preamble(markdown, image)

    return {
        "_id": stable_post_id(legacy_id),
        "legacyBlogId": legacy_id,
        "source": "legacy_static",
        "author": author,
        "slug": slugify_title(str(legacy.get("title") or "")),
        "title": str(legacy.get("title") or ""),
        "intro": intro,
        "subtitle": intro,
        "markdown": markdown,
        "topics": normalize_topics(tags, category),
        "tags": tags,
        "category": category,
        "blogType": "site" if official else "community",
        "isOfficial": official,
        "language": "en",
        "image": image,
        "imageAlt": image_alt,
        "imageCredit": "",
        "live": True,
        "discuss": False,
        "sticky": False,
        "views": 0,
        "likes": [],
        "createdAt": published,
        "updatedAt": published,
        "publishedAt": published,
    }


def build_legacy_ublog_docs(
    author_policy: str = "keep",
    strip_preamble: bool = True,
    from_id: str = "",
    limit: int = 0,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    started = from_id == ""
    for legacy in legacy_blogs():
        legacy_id = str(legacy.get("_id") or "")
        if not started:
            if legacy_id == from_id:
                started = True
            else:
                continue
        docs.append(to_ublog_doc(legacy, author_policy, strip_preamble))
    if limit > 0:
        docs = docs[:limit]
    return docs
