import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import test_logger
from aiohttp import web
from catalogued.variants import (
    _canonical_piece_set_filename,
    _catalogued_board_svg_css,
    _catalogued_disguised_piece_css,
    _catalogued_piece_set_css,
    _catalogued_piece_set_is_directional,
    _catalogued_piece_set_required_filenames,
    _check_ini_with_pyffish_child,
    _copy_catalogued_uploaded_assets,
    _has_complete_piece_set,
    _read_bool_metadata,
    _sanitize_catalogued_board_svg,
    _sanitize_catalogued_piece_svg,
    register_catalogued_variant_doc,
    validate_catalogued_ini,
)

test_logger.init_test_logger()


class CataloguedVariantPieceSvgSanitizerTestCase(unittest.TestCase):
    def test_canonical_filename_accepts_percent_encoded_plus(self) -> None:
        self.assertEqual("w+O.svg", _canonical_piece_set_filename("w%2BO.svg"))
        self.assertEqual("b+O.svg", _canonical_piece_set_filename("b%2bO.svg"))

    def test_accepts_leading_xml_declaration(self) -> None:
        svg = b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="45" height="45">
  <path d="M 1 1 L 10 10" fill="#000"/>
</svg>
"""

        sanitized = _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertNotIn("<?xml", sanitized)
        self.assertIn("<svg", sanitized)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', sanitized)

    def test_strips_comments_metadata_and_unsafe_attrs_but_keeps_safe_style(self) -> None:
        svg = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <!-- editor note -->
  <metadata><foo /></metadata>
  <defs>
    <pattern id="p1" width="10" height="10" patternUnits="userSpaceOnUse">
      <path style="fill:#000;stroke:#fff;stroke-width:2;display:inline" d="M 0 0 L 10 10" />
    </pattern>
  </defs>
  <g inkscape:label="Layer 1" style="display:inline">
    <path class="piece" id="piece-1" fill="url(#p1)" d="M 0 0 L 10 10" />
  </g>
</svg>
"""

        sanitized = _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertNotIn("<!--", sanitized)
        self.assertNotIn("metadata", sanitized)
        self.assertNotIn("class=", sanitized)
        self.assertNotIn("display:inline", sanitized)
        self.assertIn('id="p1"', sanitized)
        self.assertIn('id="piece-1"', sanitized)
        self.assertIn('fill="url(#p1)"', sanitized)
        self.assertIn('fill="#000"', sanitized)
        self.assertIn('stroke="#fff"', sanitized)
        self.assertIn('stroke-width="2"', sanitized)
        self.assertIn('d="M 0 0 L 10 10"', sanitized)

    def test_accepts_safe_local_gradient_and_filter_references(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <defs>
    <linearGradient id="g1">
      <stop style="stop-color:#000000;stop-opacity:1" offset="0" />
      <stop style="stop-color:#000000;stop-opacity:0" offset="1" />
    </linearGradient>
    <radialGradient xlink:href="#g1" id="rg1" cx="22" cy="22" fx="22" fy="22" r="20" gradientUnits="userSpaceOnUse" />
    <filter id="blur1" x="-1" y="-1" width="3" height="3">
      <feGaussianBlur stdDeviation="2" />
    </filter>
  </defs>
  <ellipse style="fill:#e7c870;stroke:url(#rg1);filter:url(#blur1)" cx="23" cy="26" rx="22" ry="22" />
</svg>"""

        sanitized = _sanitize_catalogued_piece_svg(svg, "wQ.svg")

        self.assertIn("<linearGradient", sanitized)
        self.assertIn("<radialGradient", sanitized)
        self.assertIn('href="#g1"', sanitized)
        self.assertIn("<filter", sanitized)
        self.assertIn("<feGaussianBlur", sanitized)
        self.assertIn('stop-color="#000000"', sanitized)
        self.assertIn('stop-opacity="1"', sanitized)
        self.assertIn('stroke="url(#rg1)"', sanitized)
        self.assertIn('filter="url(#blur1)"', sanitized)

    def test_accepts_digit_prefixed_local_references(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <defs>
    <linearGradient id="0">
      <stop stop-color="#fff" offset="0" />
    </linearGradient>
    <radialGradient id="1a" xlink:href="#0" />
  </defs>
  <path fill="url(#1a)" d="M 0 0 L 10 10" />
</svg>"""

        sanitized = _sanitize_catalogued_piece_svg(svg, "wR.svg")

        self.assertIn('id="0"', sanitized)
        self.assertIn('id="1a"', sanitized)
        self.assertIn('href="#0"', sanitized)
        self.assertIn('fill="url(#1a)"', sanitized)

    def test_accepts_unicode_aria_label(self) -> None:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 34">
  <path d="M 0 0 L 10 10" aria-label="金" />
</svg>""".encode()

        sanitized = _sanitize_catalogued_piece_svg(svg, "b+B.svg")

        self.assertIn('aria-label="金"', sanitized)

    def test_rejects_non_utf8_file_as_bad_request(self) -> None:
        png = b"\x89PNG\r\n\x1a\n"

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_piece_svg(png, "wP.svg")

        self.assertEqual("wP.svg is not a valid UTF-8 SVG file.", exc.exception.text)

    def test_unicode_remains_unsupported_in_geometry_attributes(self) -> None:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="三" height="34">
  <path d="M 0 0 L 10 10" />
</svg>""".encode()

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertIn("unsupported SVG attribute values", exc.exception.text)

    def test_rejects_external_filter_reference(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg">
  <ellipse style="filter:url(http://example.invalid/filter.svg#blur1)" cx="23" cy="26" rx="22" ry="22" />
</svg>"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_piece_svg(svg, "wQ.svg")

        self.assertIn("unsafe SVG attribute values", exc.exception.text)

    def test_strips_legacy_external_svg_doctype(self) -> None:
        svg = b"""<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
 "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" width="45" height="45">
  <path d="M 1 1 L 10 10" fill="#000"/>
</svg>
"""

        sanitized = _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertNotIn("<!DOCTYPE", sanitized)
        self.assertIn("<svg", sanitized)
        self.assertIn('d="M 1 1 L 10 10"', sanitized)

    def test_rejects_doctype_with_internal_subset(self) -> None:
        svg = b"""<!DOCTYPE svg [<!ENTITY bad SYSTEM "file:///etc/passwd">]>
<svg xmlns="http://www.w3.org/2000/svg" width="45" height="45">&bad;</svg>
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertIn("unsupported doctypes", exc.exception.text)

    def test_rejects_non_xml_processing_instruction(self) -> None:
        svg = b"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet href="evil.css"?>
<svg xmlns="http://www.w3.org/2000/svg" width="45" height="45"></svg>
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_piece_svg(svg, "wP.svg")

        self.assertIn("processing instructions", exc.exception.text)

    def test_catalogued_disguised_css_contains_board_and_preview_selectors(self) -> None:
        css = _catalogued_disguised_piece_css("wildebeest")

        self.assertIn(".piece-style-catalogued-wildebeest-disguised piece.white", css)
        self.assertIn(".piece-style-catalogued-wildebeest-disguised piece.black", css)
        self.assertIn(
            "label.piece.catalogued-disguised-preview.piece-style-catalogued-wildebeest-disguised.white",
            css,
        )

    def test_directional_piece_css_rotates_reversed_player_images(self) -> None:
        css = _catalogued_piece_set_css(
            "yarishogi",
            {
                "wP": {"svg": '<svg xmlns="http://www.w3.org/2000/svg" />'},
                "bP": {"svg": '<svg xmlns="http://www.w3.org/2000/svg" />'},
            },
            directional=True,
        )

        self.assertIn(
            ".piece-style-catalogued-yarishogi-custom piece::before "
            '{content:"";display:block;width:100%;height:100%;pointer-events:none;}',
            css,
        )
        self.assertIn("piece.p-piece.white::before", css)
        self.assertIn("piece.p-piece.black::before", css)
        self.assertIn(
            ".piece-style-catalogued-yarishogi-custom piece.white.enemy::before, "
            ".piece-style-catalogued-yarishogi-custom piece.black.ally::before "
            "{transform:rotate(180deg);}",
            css,
        )

    def test_directional_white_canonical_css_shares_images_and_rotates_enemy(self) -> None:
        css = _catalogued_piece_set_css(
            "canonicalshogi",
            {"wP": {"svg": '<svg xmlns="http://www.w3.org/2000/svg" />'}},
            directional=True,
        )

        self.assertIn("piece.p-piece.white::before", css)
        self.assertIn("piece.p-piece.black::before", css)
        self.assertIn(
            ".piece-style-catalogued-canonicalshogi-custom piece.enemy::before "
            "{transform:rotate(180deg);}",
            css,
        )
        self.assertNotIn("piece.white.enemy::before", css)

    def test_directional_black_canonical_css_shares_images_and_rotates_ally(self) -> None:
        css = _catalogued_piece_set_css(
            "canonicalshogi",
            {"bP": {"svg": '<svg xmlns="http://www.w3.org/2000/svg" />'}},
            directional=True,
        )

        self.assertIn("piece.p-piece.white::before", css)
        self.assertIn("piece.p-piece.black::before", css)
        self.assertIn(
            ".piece-style-catalogued-canonicalshogi-custom piece.ally::before "
            "{transform:rotate(180deg);}",
            css,
        )
        self.assertNotIn("piece.black.ally::before", css)

    def test_regular_piece_css_does_not_rotate_player_images(self) -> None:
        css = _catalogued_piece_set_css(
            "wildebeest",
            {"wP": {"svg": '<svg xmlns="http://www.w3.org/2000/svg" />'}},
        )

        self.assertNotIn("rotate:", css)

    def test_shogi_base_marks_custom_piece_set_as_directional(self) -> None:
        self.assertTrue(_catalogued_piece_set_is_directional({"baseVariant": "shogi"}))
        self.assertTrue(_catalogued_piece_set_is_directional({"baseVariant": "minishogi"}))

    def test_client_variant_controls_directional_piece_fallback(self) -> None:
        self.assertTrue(
            _catalogued_piece_set_is_directional({"baseVariant": "", "clientVariant": "shogi"})
        )
        self.assertFalse(
            _catalogued_piece_set_is_directional({"baseVariant": "shogi", "clientVariant": "chess"})
        )

    def test_directional_piece_family_override_marks_custom_set(self) -> None:
        self.assertTrue(
            _catalogued_piece_set_is_directional(
                {"baseVariant": "chess", "pieceFamilyOverride": "tori"}
            )
        )

    def test_directional_checkbox_marks_standalone_custom_set(self) -> None:
        self.assertTrue(
            _catalogued_piece_set_is_directional(
                {
                    "baseVariant": "",
                    "pieceSetDirectional": True,
                }
            )
        )

    def test_directional_checkbox_does_not_disable_inherited_rotation(self) -> None:
        self.assertTrue(
            _catalogued_piece_set_is_directional(
                {
                    "baseVariant": "shogi",
                    "pieceSetDirectional": False,
                }
            )
        )

    def test_shogi_promotion_alone_does_not_mark_custom_set_as_directional(self) -> None:
        self.assertFalse(
            _catalogued_piece_set_is_directional({"baseVariant": "chess", "promotionType": "shogi"})
        )


class CataloguedVariantBoardSvgTestCase(unittest.TestCase):
    def test_accepts_board_svg_matching_variant_aspect_ratio(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 800">
  <rect x="0" y="0" width="1000" height="800" fill="#f0d9b5"/>
  <rect x="0" y="0" width="100" height="800" fill="#cc0000" opacity="0.25"/>
</svg>"""

        sanitized = _sanitize_catalogued_board_svg(svg, "board.svg", 10, 8)

        self.assertIn('viewBox="0 0 1000 800"', sanitized)
        self.assertIn('fill="#cc0000"', sanitized)

    def test_accepts_board_svg_with_internal_pattern_fill(self) -> None:
        svg = b"""<svg viewBox="0 0 800 800" xmlns="http://www.w3.org/2000/svg">
  <pattern id="a" height="100" patternUnits="userSpaceOnUse" width="100">
    <path d="m0 0h100v100h-100z" fill="#efd783" stroke="#000" stroke-width="2"/>
  </pattern>
  <path d="m0 0h800v800h-800z" fill="url(#a)"/>
</svg>"""

        sanitized = _sanitize_catalogued_board_svg(svg, "makruk.svg", 8, 8)

        self.assertIn("<pattern", sanitized)
        self.assertIn('id="a"', sanitized)
        self.assertIn('fill="url(#a)"', sanitized)

    def test_rejects_board_svg_without_view_box(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="800">
  <rect x="0" y="0" width="1000" height="800" fill="#f0d9b5"/>
</svg>"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _sanitize_catalogued_board_svg(svg, "board.svg", 10, 8)

        self.assertIn("viewBox", exc.exception.text)

    def test_accepts_board_svg_with_independent_view_box_aspect_ratio(self) -> None:
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 1200">
  <rect x="0" y="0" width="1100" height="1200" fill="#fdd775"/>
</svg>"""

        sanitized = _sanitize_catalogued_board_svg(svg, "shogi-board.svg", 10, 10)

        self.assertIn('viewBox="0 0 1100 1200"', sanitized)
        self.assertIn('fill="#fdd775"', sanitized)

    def test_board_css_uses_view_box_for_board_and_piece_geometry(self) -> None:
        css = _catalogued_board_svg_css(
            "shosushogi",
            {"svg": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 1200" />')},
        )

        self.assertIn('[data-board-variant="shosushogi"] cg-board', css)
        self.assertIn('[data-board-variant="shosushogi"].cg-wrap', css)
        self.assertIn('[data-board-variant="shosushogi"] .cg-wrap', css)
        self.assertIn("padding-bottom: 109.09090909% !important", css)
        self.assertIn('[data-board-variant="shosushogi"].catalogued-board-preview-surface', css)
        self.assertIn(
            'label.board.catalogued-custom-board-preview[data-board-variant="shosushogi"]',
            css,
        )
        self.assertIn("aspect-ratio: 1100 / 1200 !important", css)
        self.assertIn('background-image: url("data:image/svg+xml;base64,', css)


class CataloguedVariantStartFenValidationTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_child_checker_rejects_start_fen_without_side_to_move(self) -> None:
        output = '{"ok": true, "startFen": "8/8/8/8/8/8/8/8"}\n'

        with (
            patch(
                "catalogued.variants._run_process",
                new=AsyncMock(return_value=(0, output)),
            ),
            self.assertRaises(web.HTTPBadRequest) as exc,
        ):
            await _check_ini_with_pyffish_child(
                "[missingturn:placement]\nstartFen = 8/8/8/8/8/8/8/8\n",
                "missingturn",
            )

        self.assertIn("side to move", exc.exception.text)

    def test_register_rejects_stored_variant_without_side_to_move(self) -> None:
        app_state = SimpleNamespace(catalogued_variants={})
        doc = {
            "name": "missingturn",
            "ini": "[missingturn:placement]",
            "startFen": "8/8/8/8/8/8/8/8",
        }

        with self.assertRaises(web.HTTPBadRequest) as exc:
            register_catalogued_variant_doc(app_state, doc, load_config=False)

        self.assertIn("side to move", exc.exception.text)
        self.assertNotIn("missingturn", app_state.catalogued_variants)


class CataloguedVariantPieceMetadataTestCase(unittest.TestCase):
    def test_directional_checkbox_metadata_parses_boolean_values(self) -> None:
        self.assertTrue(
            _read_bool_metadata(
                {"pieceSetDirectional": True},
                "pieceSetDirectional",
                "piece_set_directional",
            )
        )
        self.assertFalse(
            _read_bool_metadata(
                {"piece_set_directional": "off"},
                "pieceSetDirectional",
                "piece_set_directional",
            )
        )
        self.assertIsNone(_read_bool_metadata({}, "pieceSetDirectional", "piece_set_directional"))

    def test_directional_checkbox_metadata_rejects_invalid_value(self) -> None:
        with self.assertRaises(web.HTTPBadRequest):
            _read_bool_metadata(
                {"pieceSetDirectional": "sometimes"},
                "pieceSetDirectional",
                "piece_set_directional",
            )

    def test_directional_piece_set_accepts_complete_single_color_or_paired_modes(
        self,
    ) -> None:
        directional_doc: Any = {
            "baseVariant": "",
            "pieceSetDirectional": True,
            "pieces": ["k", "p"],
            "promotionType": "shogi",
            "promotionRoles": ["p"],
        }
        white = {
            "wK": {"svg": "<svg />"},
            "wP": {"svg": "<svg />"},
            "w+P": {"svg": "<svg />"},
        }
        black = {
            "bK": {"svg": "<svg />"},
            "bP": {"svg": "<svg />"},
            "b+P": {"svg": "<svg />"},
        }

        self.assertTrue(_has_complete_piece_set({**directional_doc, "pieceSet": white}))
        self.assertTrue(_has_complete_piece_set({**directional_doc, "pieceSet": black}))
        self.assertTrue(
            _has_complete_piece_set({**directional_doc, "pieceSet": {**white, **black}})
        )

    def test_directional_piece_set_rejects_partial_or_mixed_single_color_modes(
        self,
    ) -> None:
        directional_doc: Any = {
            "baseVariant": "",
            "pieceSetDirectional": True,
            "pieces": ["k", "p"],
            "promotionType": "shogi",
            "promotionRoles": ["p"],
        }

        self.assertFalse(
            _has_complete_piece_set(
                {
                    **directional_doc,
                    "pieceSet": {
                        "wK": {"svg": "<svg />"},
                        "wP": {"svg": "<svg />"},
                    },
                }
            )
        )
        self.assertFalse(
            _has_complete_piece_set(
                {
                    **directional_doc,
                    "pieceSet": {
                        "wK": {"svg": "<svg />"},
                        "wP": {"svg": "<svg />"},
                        "b+P": {"svg": "<svg />"},
                    },
                }
            )
        )

    def test_non_directional_piece_set_still_requires_paired_mode(self) -> None:
        regular_doc: Any = {
            "baseVariant": "chess",
            "pieces": ["k", "p"],
            "promotionType": "regular",
            "promotionRoles": ["p"],
            "pieceSet": {
                "wK": {"svg": "<svg />"},
                "wP": {"svg": "<svg />"},
            },
        }

        self.assertFalse(_has_complete_piece_set(regular_doc))

    def test_validate_ini_uses_pychess_pieces_metadata_for_promoted_svgs(self) -> None:
        ini = """[metapromo:chess]
# pychessPieces = k,q,r,+r,p,+p
"""

        with (
            patch("catalogued.variants.sf.load_variant_config"),
            patch(
                "catalogued.variants.sf.start_fen",
                return_value="r3k2r/8/8/8/8/8/8/4K2P w - - 0 1",
            ),
        ):
            validated = validate_catalogued_ini(ini)

        self.assertEqual(validated.pieces, ["k", "r", "p", "q"])
        self.assertEqual(validated.promotion_type, "shogi")
        self.assertEqual(validated.promotion_roles, ["r", "p"])
        self.assertEqual(validated.promotion_order, ["+", ""])
        self.assertTrue(validated.show_promoted)
        self.assertIn(
            "w+P.svg",
            _catalogued_piece_set_required_filenames(
                {
                    "pieces": validated.pieces,
                    "promotionType": validated.promotion_type,
                    "promotionRoles": validated.promotion_roles,
                }
            ),
        )

    def test_validate_ini_rejects_start_fen_without_side_to_move(self) -> None:
        ini = """[missingturn:placement]
startFen = 8/8/8/8/8/8/8/8
"""

        with (
            patch("catalogued.variants.sf.load_variant_config"),
            patch(
                "catalogued.variants.sf.start_fen",
                return_value="8/8/8/8/8/8/8/8",
            ),
            self.assertRaises(web.HTTPBadRequest) as exc,
        ):
            validate_catalogued_ini(ini)

        self.assertIn("side to move", exc.exception.text)
        self.assertIn("'w' or 'b'", exc.exception.text)

    def test_regular_promotion_roles_do_not_require_promoted_svgs(self) -> None:
        self.assertEqual(
            [
                "wA.svg",
                "wB.svg",
                "wC.svg",
                "wK.svg",
                "wM.svg",
                "wN.svg",
                "wP.svg",
                "wQ.svg",
                "wR.svg",
                "wW.svg",
                "bA.svg",
                "bB.svg",
                "bC.svg",
                "bK.svg",
                "bM.svg",
                "bN.svg",
                "bP.svg",
                "bQ.svg",
                "bR.svg",
                "bW.svg",
            ],
            _catalogued_piece_set_required_filenames(
                {
                    "pieces": ["k", "q", "r", "b", "n", "p", "a", "m", "c", "w"],
                    "promotionType": "regular",
                    "promotionRoles": ["p"],
                }
            ),
        )

    def test_existing_piece_set_is_preserved_when_metadata_adds_required_svgs(self) -> None:
        updated_doc: Any = {
            "_id": "metapromo",
            "name": "metapromo",
            "displayName": "metapromo",
            "description": "",
            "author": "alice",
            "ini": "[metapromo:chess]\n# pychessPieces = k,p,+p",
            "baseVariant": "chess",
            "enabled": True,
            "archived": False,
            "startFen": "4k3/8/8/8/8/8/8/4K2P w - - 0 1",
            "width": 8,
            "height": 8,
            "pieces": ["k", "p"],
            "kingRoles": ["k"],
            "pocketRoles": [],
            "captureToHand": False,
            "promotionType": "shogi",
            "promotionRoles": ["p"],
            "promotionOrder": ["+", ""],
            "showPromoted": True,
            "rulesGate": False,
            "rulesPass": False,
            "legalMovesNeedHistory": False,
            "nFoldIsDraw": False,
            "showCheckCounters": False,
            "category": "other",
            "visibility": "private",
            "gameCount": 0,
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        }
        old_complete_before_metadata: Any = {
            "pieceSet": {
                "wK": {"svg": "<svg />", "size": 7},
                "bK": {"svg": "<svg />", "size": 7},
                "wP": {"svg": "<svg />", "size": 7},
                "bP": {"svg": "<svg />", "size": 7},
            },
            "pieceSetUpdatedAt": datetime.now(UTC),
            "boardSvg": {"svg": "<svg />", "size": 7},
            "boardSvgUpdatedAt": datetime.now(UTC),
        }

        _copy_catalogued_uploaded_assets(updated_doc, old_complete_before_metadata)

        self.assertIn("pieceSet", updated_doc)
        self.assertFalse(_has_complete_piece_set(updated_doc))
        self.assertEqual(updated_doc["boardSvg"], old_complete_before_metadata["boardSvg"])
        self.assertEqual(
            updated_doc["boardSvgUpdatedAt"], old_complete_before_metadata["boardSvgUpdatedAt"]
        )

    def test_existing_piece_set_is_preserved_when_it_matches_new_metadata_requirements(
        self,
    ) -> None:
        updated_doc: Any = {
            "_id": "metapromo",
            "name": "metapromo",
            "displayName": "metapromo",
            "description": "",
            "author": "alice",
            "ini": "[metapromo:chess]\n# pychessPieces = k,p,+p",
            "baseVariant": "chess",
            "enabled": True,
            "archived": False,
            "startFen": "4k3/8/8/8/8/8/8/4K2P w - - 0 1",
            "width": 8,
            "height": 8,
            "pieces": ["k", "p"],
            "kingRoles": ["k"],
            "pocketRoles": [],
            "captureToHand": False,
            "promotionType": "shogi",
            "promotionRoles": ["p"],
            "promotionOrder": ["+", ""],
            "showPromoted": True,
            "rulesGate": False,
            "rulesPass": False,
            "legalMovesNeedHistory": False,
            "nFoldIsDraw": False,
            "showCheckCounters": False,
            "category": "other",
            "visibility": "private",
            "gameCount": 0,
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        }
        matching_piece_set: Any = {
            "pieceSet": {
                "wK": {"svg": "<svg />", "size": 7},
                "bK": {"svg": "<svg />", "size": 7},
                "wP": {"svg": "<svg />", "size": 7},
                "bP": {"svg": "<svg />", "size": 7},
                "w+P": {"svg": "<svg />", "size": 7},
                "b+P": {"svg": "<svg />", "size": 7},
            },
            "pieceSetUpdatedAt": datetime.now(UTC),
        }

        _copy_catalogued_uploaded_assets(updated_doc, matching_piece_set)

        self.assertIn("pieceSet", updated_doc)
        self.assertIn("w+P", updated_doc["pieceSet"])
        self.assertTrue(_has_complete_piece_set(updated_doc))
