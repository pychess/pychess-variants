import unittest

from aiohttp import web
from catalogued_variants import (
    _clean_board_family_override,
    _ensure_board_family_dimensions,
    _read_board_family_override,
)


class CataloguedVariantBoardFamilyOverrideTestCase(unittest.TestCase):
    def test_auto_detect_values_clear_board_family_override(self):
        for value in (None, "", "auto", "Auto-detect", "autodetect"):
            with self.subTest(value=value):
                self.assertEqual(_clean_board_family_override(value), "")

    def test_explicit_empty_modern_field_clears_legacy_override(self):
        self.assertEqual(
            _read_board_family_override(
                {"boardFamilyOverride": "", "board_family_override": "makruk8x8"}
            ),
            "",
        )

    def test_legacy_board_family_override_is_accepted(self):
        self.assertEqual(
            _read_board_family_override({"board_family_override": "shogi9x9"}),
            "shogi9x9",
        )

    def test_unknown_board_family_override_is_rejected(self):
        with self.assertRaises(web.HTTPBadRequest):
            _clean_board_family_override("catalogued8x8")

    def test_board_family_dimensions_must_match_variant(self):
        with self.assertRaises(web.HTTPBadRequest):
            _ensure_board_family_dimensions("xiangqi9x10", 8, 8)

    def test_matching_board_family_dimensions_are_accepted(self):
        _ensure_board_family_dimensions("makruk8x8", 8, 8)
        _ensure_board_family_dimensions("shogi7x9", 7, 9)
        _ensure_board_family_dimensions("shogi6x6", 6, 6)
