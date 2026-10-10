import unittest

from aiohttp import web
from catalogued_variants import _clean_piece_family_override, _read_piece_family_override


class CataloguedVariantPieceFamilyOverrideTestCase(unittest.TestCase):
    def test_auto_detect_values_clear_piece_family_override(self):
        for value in ("", " ", "auto", "Auto", "auto-detect", "Auto-Detect", "autodetect"):
            with self.subTest(value=value):
                self.assertEqual(_clean_piece_family_override(value), "")

    def test_explicit_empty_modern_payload_does_not_fall_back_to_stale_legacy_value(self):
        self.assertEqual(
            _read_piece_family_override(
                {"pieceFamilyOverride": "", "piece_family_override": "threekings"}
            ),
            "",
        )

    def test_legacy_payload_is_still_accepted_when_modern_key_is_absent(self):
        self.assertEqual(
            _read_piece_family_override({"piece_family_override": "standard"}), "standard"
        )

    def test_site_piece_family_overrides_are_accepted(self):
        for family in ("perfect", "courier", "centaur", "opulent"):
            with self.subTest(family=family):
                self.assertEqual(_clean_piece_family_override(family), family)

    def test_unknown_piece_family_override_is_rejected(self):
        with self.assertRaises(web.HTTPBadRequest):
            _clean_piece_family_override("threekings")


if __name__ == "__main__":
    unittest.main()
