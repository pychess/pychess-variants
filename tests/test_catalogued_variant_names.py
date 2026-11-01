import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import test_logger
from aiohttp import web
from catalogued.variants import (
    ensure_catalogued_display_name_available,
    ensure_catalogued_variant_name_available,
    extract_variant_name,
    normalize_catalogued_display_name,
    replace_variant_section_name,
)

test_logger.init_test_logger()


class CataloguedVariantNameTestCase(unittest.TestCase):
    def test_extract_variant_name_accepts_hyphenated_fsf_alias(self) -> None:
        self.assertEqual("fsf-tencubed", extract_variant_name("[fsf-tencubed:tencubed]\n"))

    def test_replace_variant_section_name_preserves_parent_template(self) -> None:
        self.assertEqual(
            "[fsf-tencubed:tencubed]\n",
            replace_variant_section_name("[old_name:tencubed]\n", "fsf-tencubed"),
        )

    def test_rejects_name_that_does_not_start_with_lowercase_letter(self) -> None:
        with self.assertRaises(web.HTTPBadRequest):
            extract_variant_name("[-fsf-tencubed:tencubed]\n")

    def test_normalizes_repeated_display_name_separators(self) -> None:
        self.assertEqual(
            "Really-Fun_Name",
            normalize_catalogued_display_name("  Really---  Fun___Name  "),
        )
        self.assertEqual("A_B", normalize_catalogued_display_name("A_-_-_B"))

    def test_empty_display_name_uses_the_existing_fallback(self) -> None:
        self.assertEqual("", normalize_catalogued_display_name("   "))

    def test_accepts_natural_unicode_display_name_letters(self) -> None:
        for display_name in ("Misère Chess", "São Paulo Chess", "Шахматы 960"):
            with self.subTest(display_name=display_name):
                self.assertEqual(display_name, normalize_catalogued_display_name(display_name))

    def test_normalizes_compatibility_styled_display_name_characters(self) -> None:
        self.assertEqual("Chess 4", normalize_catalogued_display_name("𝗖𝗵𝗲𝘀𝘀 ４"))

    def test_accepts_meaningful_plain_text_punctuation(self) -> None:
        for display_name in (
            "Decimal Shogi (Will Be Archived)",
            "Guarded 0.5",
            "Hoppel-poppel++",
            "Trench Chess/Trench-house",
        ):
            with self.subTest(display_name=display_name):
                self.assertEqual(display_name, normalize_catalogued_display_name(display_name))

    def test_rejects_emoji_symbols_and_decorative_combining_marks(self) -> None:
        for display_name in ("Emoji 🎉 Chess", "Heart ♥ Chess", "C̸hess"):
            with (
                self.subTest(display_name=display_name),
                self.assertRaises(web.HTTPBadRequest),
            ):
                normalize_catalogued_display_name(display_name)

    def test_rejects_display_name_with_separator_at_an_edge(self) -> None:
        for display_name in ("-Chess", "Chess_", "---"):
            with (
                self.subTest(display_name=display_name),
                self.assertRaises(web.HTTPBadRequest),
            ):
                normalize_catalogued_display_name(display_name)

    def test_rejects_display_name_over_fifty_characters(self) -> None:
        with self.assertRaises(web.HTTPBadRequest):
            normalize_catalogued_display_name("A" * 51)

    def test_rejects_first_class_site_variant_display_names(self) -> None:
        for display_name in ("Chess", "CHESS", "King of the Hill", "𝗖𝗵𝗲𝘀𝘀"):
            with (
                self.subTest(display_name=display_name),
                self.assertRaises(web.HTTPConflict),
            ):
                ensure_catalogued_display_name_available(
                    normalize_catalogued_display_name(display_name),
                    variant_name="myvariant",
                )

    def test_rejects_active_fsf_catalogue_display_names(self) -> None:
        for display_name in ("Shatar", "shatar", "Courier Chess", "Janus Chess"):
            with (
                self.subTest(display_name=display_name),
                self.assertRaises(web.HTTPConflict),
            ):
                ensure_catalogued_display_name_available(
                    normalize_catalogued_display_name(display_name),
                    variant_name="myvariant",
                )

    def test_allows_distinct_derivative_display_names(self) -> None:
        for display_name in (
            "Shatar Custom",
            "Shatar Modified",
            "My Shatar",
            "Chess with Camels",
        ):
            with self.subTest(display_name=display_name):
                ensure_catalogued_display_name_available(
                    normalize_catalogued_display_name(display_name),
                    variant_name="myvariant",
                )

    def test_does_not_reserve_fsf_candidate_display_names(self) -> None:
        ensure_catalogued_display_name_available(
            normalize_catalogued_display_name("Chigorin Chess"),
            variant_name="myvariant",
        )

    def test_grandfathers_unchanged_legacy_collision_on_metadata_edit(self) -> None:
        ensure_catalogued_display_name_available(
            "Shatar",
            variant_name="shatar_custom",
            current_display_name="Shatar",
            current_variant_name="shatar_custom",
        )

    def test_legacy_collision_must_be_fixed_when_variant_is_renamed(self) -> None:
        with self.assertRaises(web.HTTPConflict):
            ensure_catalogued_display_name_available(
                "Shatar",
                variant_name="shatar_custom_v2",
                current_display_name="Shatar",
                current_variant_name="shatar_custom",
            )


class CataloguedVariantNameAvailabilityTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_previously_used_internal_name(self) -> None:
        active_collection = SimpleNamespace(find_one=AsyncMock(return_value=None))
        name_collection = SimpleNamespace(find_one=AsyncMock(return_value={"_id": "retiredname"}))
        app_state = SimpleNamespace(
            catalogued_variants={},
            db={
                "catalogued_variant": active_collection,
                "catalogued_variant_name": name_collection,
            },
        )

        with self.assertRaises(web.HTTPConflict) as exc:
            await ensure_catalogued_variant_name_available(app_state, "retiredname")

        self.assertIn("used previously", exc.exception.text)
        active_collection.find_one.assert_awaited_once()
        name_collection.find_one.assert_awaited_once()
