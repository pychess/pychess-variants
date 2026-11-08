"""Validation and rendering of uploaded catalogue SVG assets."""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast
from urllib.parse import unquote

from aiohttp import web

from . import models, validation


def _catalogued_piece_set_is_directional(doc: Mapping[str, Any]) -> bool:
    """Whether custom pieces must keep pointing toward the opponent."""
    if bool(doc.get("pieceSetDirectional", False)):
        return True
    client_variant = validation._catalogued_client_variant_name(doc)
    if client_variant in models.CATALOGUED_DIRECTIONAL_PIECE_BASE_VARIANTS:
        return True
    return (
        validation._catalogued_piece_family_override(doc)
        in models.CATALOGUED_DIRECTIONAL_PIECE_FAMILIES
    )


PIECE_SET_FILENAME_RE = re.compile(r"^([wb])(\+?)([A-Za-z])\.svg$")


XML_DECL_RE = re.compile(r"^\ufeff?\s*<\?xml\s+[^?]*\?>", re.IGNORECASE)


SVG_DOCTYPE_RE = re.compile(
    r"^\s*<!DOCTYPE\s+svg\s+"
    r'(?:PUBLIC\s+"[^"]*"\s+"[^"]*"|SYSTEM\s+"[^"]*")\s*>',
    re.IGNORECASE,
)


XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


SAFE_SVG_TAGS = frozenset(
    {
        "svg",
        "defs",
        "g",
        "pattern",
        "linearGradient",
        "radialGradient",
        "stop",
        "filter",
        "feGaussianBlur",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "title",
        "desc",
    }
)


SAFE_SVG_ATTRS = frozenset(
    {
        "xmlns",
        "version",
        "id",
        "viewBox",
        "width",
        "height",
        "patternUnits",
        "patternContentUnits",
        "patternTransform",
        "gradientUnits",
        "gradientTransform",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "fx",
        "fy",
        "r",
        "rx",
        "ry",
        "offset",
        "d",
        "points",
        "fill",
        "stroke",
        "stop-color",
        "stop-opacity",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "fill-rule",
        "clip-rule",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "filter",
        "stdDeviation",
        "transform",
        "transform-origin",
        "href",
        "aria-label",
        "role",
    }
)


SAFE_SVG_STYLE_ATTRS = frozenset(
    {
        "fill",
        "stroke",
        "stop-color",
        "stop-opacity",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "fill-rule",
        "clip-rule",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "filter",
        "transform",
        "transform-origin",
    }
)


SAFE_SVG_VALUE_RE = re.compile(r"^[#%,.0-9A-Za-z_() +\-/:]*$")


# Several bundled piece sets use editor-generated numeric IDs such as ``id="0"``.
# They are safe here because references are still restricted to same-document
# fragments containing only this narrow character set.
SAFE_SVG_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:-]*$")


SAFE_SVG_LOCAL_REF_RE = re.compile(r"^url\(#[A-Za-z0-9_][A-Za-z0-9_.:-]*\)$")


SAFE_SVG_FRAGMENT_REF_RE = re.compile(r"^#[A-Za-z0-9_][A-Za-z0-9_.:-]*$")


def _local_xml_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[1]
    return name


def _svg_value_is_unsafe(value: str, *, allow_local_ref: bool = False) -> bool:
    lowered = value.casefold()
    if "javascript:" in lowered or "data:" in lowered:
        return True
    if "url(" not in lowered:
        return False
    return not (allow_local_ref and SAFE_SVG_LOCAL_REF_RE.fullmatch(value) is not None)


def _svg_value_is_supported(attribute: str, value: str) -> bool:
    # Accessible names commonly contain non-ASCII text (for example, the kanji
    # printed on shogi pieces). ElementTree escapes the value when serializing,
    # so it is safe to preserve after the unsafe-reference check above.
    return attribute == "aria-label" or SAFE_SVG_VALUE_RE.fullmatch(value) is not None


def _parse_safe_svg_style(style: str, filename: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for chunk in style.split(";"):
        declaration = chunk.strip()
        if not declaration:
            continue
        name, separator, value = declaration.partition(":")
        if not separator:
            raise web.HTTPBadRequest(text=f"{filename} contains malformed SVG style declarations.")
        prop = name.strip().casefold()
        if prop not in SAFE_SVG_STYLE_ATTRS:
            continue
        cleaned_value = value.strip()
        allow_local_ref_value = prop in {"fill", "stroke", "filter"}
        if _svg_value_is_unsafe(cleaned_value, allow_local_ref=allow_local_ref_value):
            raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG attribute values.")
        if not SAFE_SVG_VALUE_RE.fullmatch(cleaned_value):
            raise web.HTTPBadRequest(text=f"{filename} contains unsupported SVG attribute values.")
        parsed[prop] = cleaned_value
    return parsed


def _prune_unsupported_svg_children(element: ET.Element) -> None:
    for child in list(element):
        if not isinstance(child.tag, str):
            element.remove(child)
            continue
        tag = _local_xml_name(child.tag)
        if tag not in SAFE_SVG_TAGS:
            element.remove(child)
            continue
        child.tag = tag
        _prune_unsupported_svg_children(child)


def _canonical_piece_set_filename(filename: str) -> str | None:
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    filename = unquote(filename)
    filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    match = PIECE_SET_FILENAME_RE.fullmatch(filename)
    if match is None:
        return None
    color, promoted, letter = match.groups()
    return f"{color}{promoted}{letter.upper()}.svg"


def _catalogued_piece_set_filenames(doc: Mapping[str, Any], colors: tuple[str, ...]) -> list[str]:
    roles = {str(role).lower() for role in doc.get("pieces", []) if str(role).isalpha()}
    promotion_type = str(
        doc.get("promotionType") or validation.catalogued_promotion_type(str(doc.get("ini") or ""))
    ).casefold()
    promoted_roles = (
        {str(role).lower() for role in doc.get("promotionRoles", []) if str(role).isalpha()}
        if promotion_type == "shogi"
        else set()
    )
    filenames: list[str] = []
    for color in colors:
        for role in sorted(roles):
            filenames.append(f"{color}{role.upper()}.svg")
        for role in sorted(promoted_roles):
            filenames.append(f"{color}+{role.upper()}.svg")
    return filenames


def _catalogued_piece_set_required_filenames(doc: Mapping[str, Any]) -> list[str]:
    return _catalogued_piece_set_filenames(doc, ("w", "b"))


def _catalogued_piece_set_single_color_filenames(doc: Mapping[str, Any], color: str) -> list[str]:
    return _catalogued_piece_set_filenames(doc, (color,))


def _catalogued_piece_set_required_filenames_text(doc: Mapping[str, Any]) -> str:
    return ", ".join(_catalogued_piece_set_required_filenames(doc))


def _catalogued_piece_set_storage_key(filename_or_key: str) -> str:
    # MongoDB field names with dots are awkward and can fail on older server /
    # driver combinations. Store wP.svg as wP and w+P.svg as w+P, but accept
    # the old dotted keys when reading in case any test data was already saved.
    key = filename_or_key
    key = key.removesuffix(".svg")
    return key


def _catalogued_piece_set_required_keys(doc: Mapping[str, Any]) -> set[str]:
    return {
        _catalogued_piece_set_storage_key(filename)
        for filename in _catalogued_piece_set_required_filenames(doc)
    }


def _catalogued_piece_set_single_color_keys(doc: Mapping[str, Any], color: str) -> set[str]:
    return {
        _catalogued_piece_set_storage_key(filename)
        for filename in _catalogued_piece_set_single_color_filenames(doc, color)
    }


def _catalogued_piece_set_mode_for_keys(doc: Mapping[str, Any], keys: set[str]) -> str | None:
    if keys == _catalogued_piece_set_required_keys(doc):
        return "paired"
    if not _catalogued_piece_set_is_directional(doc):
        return None
    for color in ("w", "b"):
        if keys == _catalogued_piece_set_single_color_keys(doc, color):
            return f"canonical-{color}"
    return None


def _catalogued_piece_set_public_filename(key: str) -> str:
    return key if key.endswith(".svg") else f"{key}.svg"


def _piece_set_revision(doc: Mapping[str, Any]) -> str:
    updated_at = doc.get("pieceSetUpdatedAt")
    if isinstance(updated_at, datetime):
        return str(int(updated_at.timestamp()))
    return re.sub(r"\W+", "", str(updated_at or "0")) or "0"


def _board_svg_revision(doc: Mapping[str, Any]) -> str:
    updated_at = doc.get("boardSvgUpdatedAt")
    if isinstance(updated_at, datetime):
        return str(int(updated_at.timestamp()))
    return re.sub(r"\W+", "", str(updated_at or "0")) or "0"


def _sanitize_catalogued_svg(
    raw: bytes,
    filename: str,
    max_bytes: int,
) -> str:
    if not raw:
        raise web.HTTPBadRequest(text=f"{filename} is empty.")
    if len(raw) > max_bytes:
        raise web.HTTPBadRequest(
            text=(f"{filename} is too large. The SVG must be at most {max_bytes // 1024} KiB.")
        )

    try:
        text = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid UTF-8 SVG file.") from exc
    xml_decl = XML_DECL_RE.match(text)
    if xml_decl is not None:
        text = text[xml_decl.end() :].lstrip()

    # Many editor-exported SVG files include the legacy SVG 1.1 external DTD.
    # It does not carry image data, and keeping it only makes otherwise safe
    # piece sets fail. Strip only the simple external SVG doctype form; any
    # internal subset / entity declaration is still rejected by the check below.
    svg_doctype = SVG_DOCTYPE_RE.match(text)
    if svg_doctype is not None:
        text = text[svg_doctype.end() :].lstrip()

    text = XML_COMMENT_RE.sub("", text)
    lowered = text.casefold()
    if "<!" in text or "<?" in text:
        raise web.HTTPBadRequest(
            text=(
                f"{filename} contains unsupported doctypes, entity declarations, "
                "or processing instructions."
            )
        )
    if any(token in lowered for token in ("<script", "foreignobject", "javascript:", "data:")):
        raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG content.")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid UTF-8 SVG file.") from exc

    if _local_xml_name(root.tag) != "svg":
        raise web.HTTPBadRequest(text=f"{filename} must contain one <svg> root element.")

    root.tag = "svg"
    _prune_unsupported_svg_children(root)

    for element in root.iter():
        if not isinstance(element.tag, str):
            raise web.HTTPBadRequest(text=f"{filename} contains unsupported SVG nodes.")
        if element.tag not in SAFE_SVG_TAGS:
            raise web.HTTPBadRequest(
                text=f"{filename} contains unsupported <{element.tag}> SVG elements."
            )

        clean_attrs: dict[str, str] = {}
        for attr, raw_value in list(element.attrib.items()):
            local_attr = _local_xml_name(attr)
            value = raw_value.strip()
            if local_attr == "style":
                clean_attrs.update(_parse_safe_svg_style(value, filename))
                continue
            if local_attr.startswith("on"):
                continue
            if local_attr in {"src", "class"}:
                continue
            if local_attr not in SAFE_SVG_ATTRS:
                continue
            if local_attr == "id" and not SAFE_SVG_ID_RE.fullmatch(value):
                continue
            if local_attr == "href":
                if not SAFE_SVG_FRAGMENT_REF_RE.fullmatch(value):
                    continue
                clean_attrs[local_attr] = value
                continue
            allow_local_ref_value = local_attr in {"fill", "stroke", "filter"}
            if _svg_value_is_unsafe(value, allow_local_ref=allow_local_ref_value):
                raise web.HTTPBadRequest(text=f"{filename} contains unsafe SVG attribute values.")
            if not _svg_value_is_supported(local_attr, value):
                raise web.HTTPBadRequest(
                    text=f"{filename} contains unsupported SVG attribute values."
                )
            clean_attrs[local_attr] = value

        element.attrib.clear()
        element.attrib.update(clean_attrs)

    root.attrib["xmlns"] = "http://www.w3.org/2000/svg"
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _sanitize_catalogued_piece_svg(raw: bytes, filename: str) -> str:
    return _sanitize_catalogued_svg(raw, filename, models.MAX_CATALOGUED_PIECE_SVG_BYTES)


def _parse_svg_view_box_size(svg: str, filename: str) -> tuple[float, float]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise web.HTTPBadRequest(text=f"{filename} is not a valid SVG file.") from exc

    raw_view_box = str(root.attrib.get("viewBox") or "").strip()
    if not raw_view_box:
        raise web.HTTPBadRequest(text=f"{filename} must define a viewBox.")

    parts = [part for part in re.split(r"[\s,]+", raw_view_box) if part]
    if len(parts) != 4:
        raise web.HTTPBadRequest(text=f"{filename} has an invalid viewBox.")

    try:
        _min_x, _min_y, width, height = (float(part) for part in parts)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=f"{filename} has an invalid viewBox.") from exc

    if width <= 0 or height <= 0:
        raise web.HTTPBadRequest(text=f"{filename} viewBox must have positive width and height.")
    return width, height


def _sanitize_catalogued_board_svg(raw: bytes, filename: str, width: int, height: int) -> str:
    # Files and ranks describe the logical grid. The SVG viewBox describes the
    # intended physical board shape, including rectangular cells on regional
    # boards such as shogi. The generated board CSS applies that shape at render time.
    del width, height
    sanitized = _sanitize_catalogued_svg(raw, filename, models.MAX_CATALOGUED_BOARD_SVG_BYTES)
    _parse_svg_view_box_size(sanitized, filename)
    return sanitized


def _catalogued_piece_css_selector(
    variant_name: str, key: str, *, image_layer: bool = False
) -> str:
    # key format is wP, bP, w+P, b+P. Accept *.svg legacy keys too.
    key = _catalogued_piece_set_storage_key(key)
    color = "white" if key[0] == "w" else "black"
    promoted = key[1] == "+"
    letter = key[2 if promoted else 1].lower()
    role_class = f"p{letter}-piece" if promoted else f"{letter}-piece"
    style_class = f".piece-style-catalogued-{variant_name}-custom"
    piece_suffix = "::before" if image_layer else ""
    return (
        f"{style_class} piece.{role_class}.{color}{piece_suffix}, "
        f"label.piece.catalogued-custom-preview{style_class}.{role_class}.{color}"
    )


def _catalogued_piece_set_css(
    variant_name: str,
    piece_set: Mapping[str, Any],
    *,
    directional: bool = False,
) -> str:
    lines: list[str] = []
    stored_keys = {_catalogued_piece_set_storage_key(str(key)) for key in piece_set}
    stored_colors = {key[0] for key in stored_keys if key and key[0] in {"w", "b"}}
    canonical_color = next(iter(stored_colors)) if directional and len(stored_colors) == 1 else None
    if directional:
        style_class = f".piece-style-catalogued-{variant_name}-custom"
        lines.append(
            f"{style_class} piece::before "
            '{content:"";display:block;width:100%;height:100%;pointer-events:none;}'
        )
    for key in sorted(piece_set):
        item = piece_set[key]
        svg = str(item.get("svg") if isinstance(item, Mapping) else "")
        if not svg:
            continue
        data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        selectors = [_catalogued_piece_css_selector(variant_name, key, image_layer=directional)]
        if canonical_color is not None:
            stored_key = _catalogued_piece_set_storage_key(str(key))
            other_color = "b" if canonical_color == "w" else "w"
            selectors.append(
                _catalogued_piece_css_selector(
                    variant_name,
                    other_color + stored_key[1:],
                    image_layer=True,
                )
            )
        lines.append(
            f"{', '.join(selectors)} "
            "{background-position:center;background-size:contain;background-repeat:no-repeat;background-image:"
            f'url("data:image/svg+xml;base64,{data}");}}'
        )
    if directional:
        # chessgroundx owns the piece element's transform for positioning and
        # animation. Rotate only its image layer so that translation is left
        # untouched.
        if canonical_color == "w":
            lines.append(f"{style_class} piece.enemy::before {{transform:rotate(180deg);}}")
        elif canonical_color == "b":
            lines.append(f"{style_class} piece.ally::before {{transform:rotate(180deg);}}")
        else:
            lines.append(
                f"{style_class} piece.white.enemy::before, "
                f"{style_class} piece.black.ally::before "
                "{transform:rotate(180deg);}"
            )
    return "\n".join(lines) + "\n"


def _catalogued_disguised_piece_css(variant_name: str) -> str:
    style_class = f".piece-style-catalogued-{variant_name}-disguised"
    preview_class = f"label.piece.catalogued-disguised-preview{style_class}.white"
    white_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<circle cx="256" cy="256" r="170" fill="#fff" stroke="#000" stroke-width="20"/>'
        "</svg>"
    )
    black_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<circle cx="256" cy="256" r="170" fill="#000" stroke="#000" stroke-width="20"/>'
        "</svg>"
    )
    white_data = base64.b64encode(white_svg.encode("utf-8")).decode("ascii")
    black_data = base64.b64encode(black_svg.encode("utf-8")).decode("ascii")
    return (
        "\n".join(
            (
                f'{style_class} piece.white, {preview_class} {{background-image:url("data:image/svg+xml;base64,{white_data}");background-position:center;background-size:contain;background-repeat:no-repeat;}}',
                f'{style_class} piece.black {{background-image:url("data:image/svg+xml;base64,{black_data}");background-position:center;background-size:contain;background-repeat:no-repeat;}}',
            )
        )
        + "\n"
    )


def _catalogued_board_svg_css(variant_name: str, board_svg: Mapping[str, Any]) -> str:
    svg = str(board_svg.get("svg") or "")
    view_box_width, view_box_height = _parse_svg_view_box_size(svg, "board.svg")
    padding_bottom = view_box_height * 100 / view_box_width

    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    image = f'url("data:image/svg+xml;base64,{encoded}")'
    scope = f'[data-board-variant="{variant_name}"]'
    # Keep uploaded artwork available for its settings thumbnail while a user
    # selects a built-in theme on the actual board.
    custom_scope = f"{scope}:not(.board-style-builtin)"
    wrapper_selector = f"{custom_scope}.cg-wrap, {custom_scope} .cg-wrap"
    selector = f"{custom_scope} cg-board"
    preview_selector = f"{scope}.catalogued-board-preview-surface"
    settings_preview_selector = (
        f'label.board.catalogued-custom-board-preview[data-board-variant="{variant_name}"]'
    )
    return (
        f"{wrapper_selector} {{\n"
        f"  padding-bottom: {padding_bottom:.8f}% !important;\n"
        "}\n"
        f"{selector}, {preview_selector}, {settings_preview_selector} {{\n"
        f"  background-image: {image} !important;\n"
        "  background-size: 100% 100% !important;\n"
        "  background-repeat: no-repeat !important;\n"
        "  background-position: center center !important;\n"
        "}\n"
        f"{preview_selector}, {settings_preview_selector} {{\n"
        f"  aspect-ratio: {view_box_width:g} / {view_box_height:g} !important;\n"
        "}\n"
    )


def _has_complete_piece_set(doc: Mapping[str, Any]) -> bool:
    piece_set = doc.get("pieceSet")
    if not isinstance(piece_set, Mapping):
        return False
    keys = {_catalogued_piece_set_storage_key(str(key)) for key in piece_set}
    return _catalogued_piece_set_mode_for_keys(doc, keys) is not None


def _copy_catalogued_uploaded_assets(
    target_doc: models.CataloguedVariantDocument, source_doc: Mapping[str, Any]
) -> None:
    """Keep user uploads even when changed metadata makes them temporarily unusable."""
    piece_set = source_doc.get("pieceSet")
    if isinstance(piece_set, Mapping):
        target_doc["pieceSet"] = cast(
            dict[str, models.CataloguedVariantPieceSetSvg], dict(piece_set)
        )
        updated_at = source_doc.get("pieceSetUpdatedAt")
        if isinstance(updated_at, datetime):
            target_doc["pieceSetUpdatedAt"] = updated_at

    board_svg = source_doc.get("boardSvg")
    if isinstance(board_svg, Mapping) and board_svg.get("svg"):
        target_doc["boardSvg"] = cast(models.CataloguedVariantBoardSvg, dict(board_svg))
        updated_at = source_doc.get("boardSvgUpdatedAt")
        if isinstance(updated_at, datetime):
            target_doc["boardSvgUpdatedAt"] = updated_at


def _has_board_svg(doc: Mapping[str, Any]) -> bool:
    board_svg = doc.get("boardSvg")
    return isinstance(board_svg, Mapping) and bool(board_svg.get("svg"))
