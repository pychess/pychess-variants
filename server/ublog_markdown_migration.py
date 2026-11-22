"""One-time conversion of legacy blog HTML into strict Markdown.

This module only transforms content; database migration is handled separately.
Original HTML decoration (alignment, colors and layout) is intentionally discarded.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

_TAG = re.compile(
    r"<\s*/?\s*(?:img|iframe|p|div|br|a|b|strong|em|i|h[1-6])\b[^>]*>", re.IGNORECASE | re.DOTALL
)
_DIMENSION_MAX = 2048


class _Tag(HTMLParser):
    def __init__(self, raw: str):
        super().__init__(convert_charrefs=True)
        self.name = ""
        self.attrs_map: dict[str, str] = {}
        self.closing = raw.lstrip().startswith("</")
        self.feed(raw)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.name = tag.lower()
        self.attrs_map = {key.lower(): value or "" for key, value in attrs}

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        self.name = tag.lower()


def _dimensions(attrs: dict[str, str]) -> str:
    pairs = []
    for key in ("width", "height"):
        raw = attrs.get(key, "")
        if raw.isascii() and raw.isdecimal() and 0 < int(raw) <= _DIMENSION_MAX:
            pairs.append(f"{key}={int(raw)}")
    return "{" + " ".join(pairs) + "}" if pairs else ""


def _embed_link(src: str) -> str:
    parsed = urlparse(src)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    host = parsed.hostname.lower()
    if host in ("youtube.com", "www.youtube.com", "www.youtube-nocookie.com"):
        if parsed.path.startswith("/embed/"):
            video_id = parsed.path.removeprefix("/embed/")
        elif parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            return ""
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return f"https://www.youtube.com/watch?v={video_id}"
    if host in ("lichess.org", "www.lichess.org"):
        match = re.fullmatch(
            r"/study/(?:embed/)?([A-Za-z0-9]{8}(?:/[A-Za-z0-9]{8})?)/?", parsed.path
        )
        if match:
            return "https://lichess.org/study/" + match.group(1)
    return ""


def convert_legacy_blog_markdown(source: str) -> str:
    """Convert known legacy HTML; leave unknown HTML to be escaped by the renderer."""

    def replace(match: re.Match[str]) -> str:
        node = _Tag(match.group())
        tag = node.name
        attrs = node.attrs_map
        closing = node.closing
        if tag == "img" and not closing:
            src = attrs.get("src", "")
            if not src or any(c in src for c in "\r\n<>\x00"):
                return ""
            # Markdown syntax escaping. The renderer still applies its URL allowlist.
            src = src.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
            alt = attrs.get("alt", "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            return f"![{alt}]({src}){_dimensions(attrs)}"
        if tag == "iframe":
            return "\n\n" + _embed_link(attrs.get("src", "")) + "\n\n" if not closing else ""
        if tag == "br":
            return "  \n"
        if tag in ("p", "div"):
            return "\n\n"
        if tag in ("b", "strong"):
            return "**"
        if tag in ("i", "em"):
            return "*"
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            return "\n\n" if closing else "\n\n" + "#" * int(tag[1]) + " "
        if tag == "a":
            if closing:
                return "]"  # opening tag replaced separately in link-aware pass below
            return ""
        return match.group()

    # Handle HTML links as complete elements to avoid leaking unmatched Markdown brackets.
    def replace_link(match: re.Match[str]) -> str:
        opening, body = match.group(1), match.group(2)
        node = _Tag(opening)
        href = node.attrs_map.get("href", "")
        if not href or any(c in href for c in "\r\n<>\x00"):
            return html.unescape(body)
        label = html.unescape(body).replace("[", "\\[").replace("]", "\\]")
        return f"[{label}]({href.replace(' ', '%20').replace('(', '%28').replace(')', '%29')})"

    source = re.sub(
        r"(<a\b[^>]*>)(.*?)</a\s*>", replace_link, source, flags=re.IGNORECASE | re.DOTALL
    )
    converted = _TAG.sub(replace, source)
    converted = re.sub(r"\n{3,}", "\n\n", converted)
    return converted.strip() + "\n" if converted.strip() else ""
