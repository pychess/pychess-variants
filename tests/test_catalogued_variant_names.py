import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from aiohttp import web
from catalogued.http import check_catalogued_variant_rules, upload_catalogued_variant
from catalogued.repository import ensure_catalogued_variant_name_available
from catalogued.validation import (
    ensure_catalogued_display_name_available,
    extract_variant_name,
    normalize_catalogued_display_name,
    replace_variant_section_name,
)
from mongomock_motor import AsyncMongoMockClient

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
        for display_name in (
            "Shatar",
            "shatar",
            "Courier Chess",
            "Janus Chess",
            "Chigorin Chess",
            "Sort-of-Almost Chess",
        ):
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
        candidates = {"candidatevariant": {"displayName": "Candidate Chess"}}
        with (
            patch("catalogued.builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS", {}),
            patch("catalogued.builtin_data.FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES", candidates),
        ):
            ensure_catalogued_display_name_available(
                normalize_catalogued_display_name("Candidate Chess"),
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
    def setUp(self) -> None:
        self.db = AsyncMongoMockClient().get_database("catalogued_name_test")
        self.app_state = SimpleNamespace(catalogued_variants={}, db=self.db)
        self.engine_variants = self.enterContext(
            patch("catalogued.repository.sf.variants", return_value=[])
        )
        self.name = "retiredname"
        self.ini = f"[{self.name}:chess]\nnFoldRule = 4\n"

    async def test_allows_deleted_name_after_engine_restart(self) -> None:
        reservation = {"_id": self.name, "author": "alice"}
        await self.db.catalogued_variant_name.insert_one(reservation)

        await ensure_catalogued_variant_name_available(self.app_state, self.name)

        # Checking availability neither consumes the history nor registers rules.
        self.assertEqual(
            await self.db.catalogued_variant_name.find_one({"_id": self.name}), reservation
        )

    async def test_rejects_deleted_name_still_loaded_in_engine(self) -> None:
        await self.db.catalogued_variant_name.insert_one({"_id": self.name})
        self.engine_variants.return_value = [self.name]

        with self.assertRaises(web.HTTPConflict) as exc:
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

        self.assertIn("until the server restarts", exc.exception.text)

    async def test_rejects_loaded_name_without_reservation(self) -> None:
        self.engine_variants.return_value = [self.name]

        with self.assertRaises(web.HTTPConflict) as exc:
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

        self.assertIn("still loaded", exc.exception.text)

    async def test_allows_fresh_name(self) -> None:
        await ensure_catalogued_variant_name_available(self.app_state, self.name)

    async def test_saved_games_prevent_reuse_even_after_restart(self) -> None:
        # Protect history even if the catalogue document and reservation are missing.
        await self.db.game.insert_one({"_id": "historical-game", "v": self.name})

        with self.assertRaises(web.HTTPConflict) as exc:
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

        self.assertIn("has saved games", exc.exception.text)

    async def test_existing_and_archived_documents_prevent_reuse(self) -> None:
        for archived in (False, True):
            with self.subTest(archived=archived):
                await self.db.catalogued_variant.replace_one(
                    {"_id": self.name},
                    {"_id": self.name, "author": "bob", "archived": archived},
                    upsert=True,
                )
                with self.assertRaises(web.HTTPConflict) as exc:
                    await ensure_catalogued_variant_name_available(self.app_state, self.name)
                self.assertIn("already exists", exc.exception.text)

    async def test_cached_catalogued_variant_prevents_reuse(self) -> None:
        self.app_state.catalogued_variants[self.name] = {"name": self.name}

        with self.assertRaises(web.HTTPConflict):
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

    async def test_registered_server_variant_prevents_reuse(self) -> None:
        with (
            patch.dict("catalogued.repository.CATALOGUED_VARIANTS", {self.name: object()}),
            self.assertRaises(web.HTTPConflict),
        ):
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

    async def test_builtin_names_remain_protected(self) -> None:
        for name in ("chess", "tencubed"):
            with self.subTest(name=name), self.assertRaises(web.HTTPConflict) as exc:
                await ensure_catalogued_variant_name_available(self.app_state, name)
            self.assertIn("built-in", exc.exception.text)

    async def test_unchanged_current_name_remains_available_for_metadata_edits(self) -> None:
        self.engine_variants.return_value = [self.name]
        self.app_state.catalogued_variants[self.name] = {"name": self.name}
        await self.db.game.insert_one({"_id": "historical-game", "v": self.name})

        await ensure_catalogued_variant_name_available(
            self.app_state, self.name, current_name=self.name
        )

    async def test_database_unavailable_prevents_reuse(self) -> None:
        self.app_state.db = None
        with self.assertRaises(web.HTTPServiceUnavailable):
            await ensure_catalogued_variant_name_available(self.app_state, self.name)

    def api_request(self) -> SimpleNamespace:
        self.enterContext(patch("catalogued.http.get_app_state", return_value=self.app_state))
        self.enterContext(
            patch("catalogued.http._current_human_username", AsyncMock(return_value="alice"))
        )
        return SimpleNamespace(app=object())

    async def test_rules_check_accepts_reusable_name_without_loading_it(self) -> None:
        await self.db.catalogued_variant_name.insert_one({"_id": self.name})
        request = self.api_request()
        with (
            patch("catalogued.http.read_json_data", AsyncMock(return_value={"ini": self.ini})),
            patch(
                "catalogued.validation.check_catalogued_ini_without_mutating_server",
                AsyncMock(return_value="checked-fen"),
            ) as child_check,
            patch("catalogued.validation.sf.load_variant_config") as load_config,
        ):
            response = await check_catalogued_variant_rules(request)

        self.assertEqual(
            json.loads(response.text),
            {"ok": True, "name": self.name, "startFen": "checked-fen"},
        )
        child_check.assert_awaited_once_with(self.ini.strip(), self.name)
        load_config.assert_not_called()

    async def test_rules_check_reports_restart_requirement_before_validation(self) -> None:
        await self.db.catalogued_variant_name.insert_one({"_id": self.name})
        self.engine_variants.return_value = [self.name]
        request = self.api_request()
        with (
            patch("catalogued.http.read_json_data", AsyncMock(return_value={"ini": self.ini})),
            patch(
                "catalogued.validation.check_catalogued_ini_without_mutating_server", AsyncMock()
            ) as child_check,
            self.assertRaises(web.HTTPConflict) as exc,
        ):
            await check_catalogued_variant_rules(request)

        self.assertIn("until the server restarts", exc.exception.text)
        child_check.assert_not_awaited()

    async def test_upload_rechecks_registry_after_child_validation(self) -> None:
        request = self.api_request()

        async def concurrent_registration(*_args):
            self.engine_variants.return_value = [self.name]

        with (
            patch(
                "catalogued.http._read_upload_payload",
                AsyncMock(return_value=(self.ini, "New rules", "", {}, False, "", "", "private")),
            ),
            patch("catalogued.repository._ensure_catalogued_variant_quota", AsyncMock()),
            patch(
                "catalogued.validation.check_catalogued_ini_without_mutating_server",
                AsyncMock(side_effect=concurrent_registration),
            ),
            patch("catalogued.validation.validate_catalogued_ini") as validate,
            self.assertRaises(web.HTTPConflict) as exc,
        ):
            await upload_catalogued_variant(request)

        self.assertIn("until the server restarts", exc.exception.text)
        validate.assert_not_called()
        self.assertIsNone(await self.db.catalogued_variant.find_one({"_id": self.name}))
