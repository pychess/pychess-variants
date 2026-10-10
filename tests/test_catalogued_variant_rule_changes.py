from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from aiohttp import web
from catalogued_variants import (
    _ensure_catalogued_rule_changes,
    check_catalogued_variant_rules,
    clone_catalogued_variant,
    update_catalogued_variant,
    upload_catalogued_variant,
)

test_logger.init_test_logger()

COSMETIC_INI = """[chinesechesscambulac:xiangqi]
# ignore this.
; startFen = ignored comment
# pychessPieces = k,r,n,b,a,c,p
variantTemplate = xiangqi
pieceToCharTable = RNBAKCP rnbakcp
pocketSize = 10
"""


class CataloguedVariantRuleChangesTestCase(unittest.TestCase):
    def test_rejects_empty_and_comment_only_aliases(self) -> None:
        for body in ("", "\n# ignore this.", "\n ; note = not a rule\n\n"):
            with self.subTest(body=body), self.assertRaises(web.HTTPBadRequest) as exc:
                _ensure_catalogued_rule_changes("[chinesechesscambulac:xiangqi]" + body)
            self.assertIn("already playable on PyChess as Xiangqi", exc.exception.text)

    def test_rejects_protocol_and_piece_metadata_only_alias(self) -> None:
        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rule_changes(COSMETIC_INI)
        self.assertEqual(
            "This variant is already playable on PyChess as Xiangqi.", exc.exception.text
        )

    def test_each_protocol_option_alone_does_not_count_as_a_rule(self) -> None:
        for option in ("variantTemplate = fairy", "pieceToCharTable = -", "pocketSize = 8"):
            with self.subTest(option=option), self.assertRaises(web.HTTPBadRequest):
                _ensure_catalogued_rule_changes(f"[cosmetic:chess]\n{option}\n")

    def test_rejects_alias_of_curated_playable_engine_variant(self) -> None:
        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rule_changes("[myshatar:shatar]\n# new board")
        self.assertIn("already playable on PyChess as Shatar", exc.exception.text)

    def test_accepts_gameplay_overrides_alongside_cosmetic_settings(self) -> None:
        for option in (
            "stalemateValue = draw",
            "customPiece1 = x:W",
            "startFen = 9/9/9/9/4k4/4K4/9/9/9/9 w - - 0 1",
        ):
            with self.subTest(option=option):
                _ensure_catalogued_rule_changes(COSMETIC_INI + option + "\n")

    def test_does_not_claim_unexposed_engine_variant_is_already_playable(self) -> None:
        _ensure_catalogued_rule_changes("[mychigorin:chigorin]\n# new catalogue entry")

    def test_allows_standalone_rule_definitions(self) -> None:
        _ensure_catalogued_rule_changes("[standalone]\ncustomPiece1 = x:W\n")


class CataloguedVariantRuleChangesApiTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.collection = SimpleNamespace(insert_one=AsyncMock(), update_one=AsyncMock())
        self.existing = {
            "name": "chinesechesscambulac",
            "ini": COSMETIC_INI,
            "author": "alice",
            "startFen": "9/9/9/9/4k4/4K4/9/9/9/9 w - - 0 1",
            "width": 9,
            "height": 10,
        }
        self.app_state = SimpleNamespace(
            catalogued_variants={"chinesechesscambulac": self.existing},
            db={"catalogued_variant": self.collection},
        )
        self.request = SimpleNamespace(app=object())
        self.json_body = {"ini": COSMETIC_INI}
        self.enterContext(patch("catalogued_variants.get_app_state", return_value=self.app_state))
        self.enterContext(
            patch("catalogued_variants._current_human_username", AsyncMock(return_value="alice"))
        )
        self.enterContext(
            patch("catalogued_variants.read_json_data", AsyncMock(return_value=self.json_body))
        )
        self.read_payload = self.enterContext(
            patch(
                "catalogued_variants._read_upload_payload",
                AsyncMock(
                    return_value=(COSMETIC_INI, "Chinese skin", "", "", False, "", "", "private")
                ),
            )
        )
        self.enterContext(
            patch(
                "catalogued_variants._load_owned_doc",
                AsyncMock(
                    return_value=(self.app_state, "alice", "chinesechesscambulac", self.existing)
                ),
            )
        )
        self.enterContext(
            patch("catalogued_variants._ensure_catalogued_variant_quota", AsyncMock())
        )
        self.enterContext(
            patch("catalogued_variants.ensure_catalogued_variant_name_available", AsyncMock())
        )
        self.child_check = self.enterContext(
            patch(
                "catalogued_variants.check_catalogued_ini_without_mutating_server",
                AsyncMock(return_value=self.existing["startFen"]),
            )
        )
        self.load_config = self.enterContext(patch("catalogued_variants.sf.load_variant_config"))

    def assert_no_registration_or_writes(self) -> None:
        self.child_check.assert_not_awaited()
        self.load_config.assert_not_called()
        self.collection.insert_one.assert_not_awaited()
        self.collection.update_one.assert_not_awaited()

    async def test_rules_check_rejects_cosmetic_definition(self) -> None:
        with self.assertRaises(web.HTTPBadRequest) as exc:
            await check_catalogued_variant_rules(self.request)
        self.assertIn("already playable on PyChess", exc.exception.text)
        self.assert_no_registration_or_writes()

    async def test_upload_rejects_before_registration_or_database_write(self) -> None:
        with self.assertRaises(web.HTTPBadRequest):
            await upload_catalogued_variant(self.request)
        self.assert_no_registration_or_writes()

    async def test_cloning_legacy_cosmetic_definition_is_rejected(self) -> None:
        with self.assertRaises(web.HTTPBadRequest):
            await clone_catalogued_variant(self.request)
        self.assert_no_registration_or_writes()

    async def test_rule_edit_cannot_turn_variant_into_cosmetic_alias(self) -> None:
        self.existing["ini"] = COSMETIC_INI + "stalemateValue = draw\n"
        self.read_payload.return_value = (
            COSMETIC_INI.replace("chinesechesscambulac", "newcosmetic"),
            "New skin",
            "",
            "",
            False,
            "",
            "",
            "private",
        )
        with self.assertRaises(web.HTTPBadRequest):
            await update_catalogued_variant(self.request)
        self.assert_no_registration_or_writes()

    async def test_unchanged_legacy_definition_can_still_be_checked(self) -> None:
        self.json_body["currentName"] = "chinesechesscambulac"
        response = await check_catalogued_variant_rules(self.request)
        self.assertEqual(json.loads(response.text)["ok"], True)
        self.child_check.assert_awaited_once()
        self.load_config.assert_not_called()

    async def test_legacy_metadata_edit_remains_allowed(self) -> None:
        async def return_updated(*_args, **kwargs):
            return kwargs["doc"]

        with (
            patch(
                "catalogued_variants._update_catalogued_variant_document",
                AsyncMock(side_effect=return_updated),
            ),
            patch("catalogued_variants.register_catalogued_variant_doc"),
            patch("catalogued_variants._game_count", AsyncMock(return_value=0)),
        ):
            response = await update_catalogued_variant(self.request)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text)["variant"]["displayName"], "Chinese skin")
        self.assert_no_registration_or_writes()


if __name__ == "__main__":
    unittest.main()
