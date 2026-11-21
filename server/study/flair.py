import json
from functools import cache
from pathlib import Path

from variants import ServerVariants

_VARIANT_ICONS = {variant.server_name: variant.icon for variant in ServerVariants}


@cache
def _emoji_flairs() -> frozenset[str]:
    path = Path(__file__).resolve().parents[2] / "static" / "study-flair" / "emoji.json"
    groups = json.loads(path.read_text(encoding="utf-8"))["groups"]
    return frozenset(emoji for group in groups.values() for emoji, _ in group)


def study_flair(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        kind, _, key = value.partition(":")
        if kind == "variant" and key in _VARIANT_ICONS:
            return value
        if kind == "emoji" and key in _emoji_flairs():
            return value
    raise ValueError("Invalid Study flair")


def study_flair_icon(flair: str) -> str:
    kind, _, key = flair.partition(":")
    if kind == "variant":
        return _VARIANT_ICONS.get(key, "")
    return key if kind == "emoji" else ""
