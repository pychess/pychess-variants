from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from catalogued_variants import (
    CATALOGUED_CHESS_PROMOTION_ORDER,
    CATALOGUED_SOURCE_FSF_BUILTIN,
    FSF_CATALOGUED_BUILTIN_DESCRIPTION,
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES,
    FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS,
    _build_fsf_builtin_doc,
    _fsf_builtin_synced_fields,
    _remove_legacy_fsf_builtin_description_fields,
    ensure_fsf_catalogued_builtin_variants,
)


class FsfBuiltinMetadataTestCase(TestCase):
    def test_engine_and_client_variant_relationships_are_separate(self) -> None:
        expected = {
            "amazons": ("", "chess"),
            "atomar": ("nocheckatomic", "atomic"),
            "centaur": ("", "capablanca"),
            "chancellor": ("", "capablanca"),
            "codrus": ("giveaway", "antichess"),
            "courier": ("", "shatranj"),
            "georgian": ("amazon", "chess"),
            "giveaway": ("", "antichess"),
            "janus": ("", "capablanca"),
            "joust": ("", "chess"),
            "judkins": ("", "shogi"),
            "kinglet": ("extinction", "chess"),
            "losers": ("", "antichess"),
            "modern": ("", "capablanca"),
            "nocheckatomic": ("", "atomic"),
            "petrified": ("pawnsideways", "chess"),
            "shatar": ("", "shatranj"),
            "tencubed": ("", "grand"),
            "yarishogi": ("", "shogi"),
            "almost": ("", "chess"),
            "gustav3": ("", "chess"),
            "omicron": ("", "chess"),
            "paradigm": ("", "chess"),
            "troitzky": ("", "chess"),
        }

        for name, (base_variant, client_variant) in expected.items():
            with self.subTest(name=name):
                metadata = FSF_CATALOGUED_BUILTIN_VARIANTS[name]
                self.assertEqual(metadata["baseVariant"], base_variant)
                self.assertEqual(metadata["clientVariant"], client_variant)

    def test_candidate_relationships_do_not_invent_engine_parents(self) -> None:
        expected = {
            "chessgi": ("loop", "crazyhouse"),
            "euroshogi": ("", "shogi"),
            "gorogoro": ("", "shogi"),
            "mini": ("", "minishogi"),
            "okisakishogi": ("", "shogi"),
        }

        for name, (base_variant, client_variant) in expected.items():
            with self.subTest(name=name):
                metadata = FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES[name]
                self.assertEqual(metadata["baseVariant"], base_variant)
                self.assertEqual(metadata["clientVariant"], client_variant)

        self.assertEqual(
            FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES["micro"]["baseVariant"],
            "kyotoshogi",
        )
        self.assertNotIn("clientVariant", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES["micro"])
        self.assertEqual(FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES["normal"]["baseVariant"], "")
        self.assertEqual(
            FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES["normal"]["clientVariant"],
            "chess",
        )

    def test_amazons_is_seeded_with_arrowing_input(self) -> None:
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS["amazons"]
        self.assertTrue(metadata["rulesArrowing"])
        self.assertEqual(metadata["pieceFamilyOverride"], "amazons")
        doc = _build_fsf_builtin_doc("amazons", metadata)
        self.assertEqual(doc["pieceFamilyOverride"], "amazons")
        self.assertEqual(_fsf_builtin_synced_fields(doc)["pieceFamilyOverride"], "amazons")
        self.assertNotIn("amazons", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)

    def test_joust_is_seeded_with_past_walling_input(self) -> None:
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS["joust"]
        self.assertTrue(metadata["rulesArrowing"])
        self.assertNotIn("pieceFamilyOverride", metadata)
        doc = _build_fsf_builtin_doc("joust", metadata)
        self.assertTrue(doc["rulesArrowing"])
        self.assertTrue(_fsf_builtin_synced_fields(doc)["rulesArrowing"])
        self.assertNotIn("joust", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)

    def test_judkins_is_seeded_with_shogi_promotions_and_board(self) -> None:
        doc = _build_fsf_builtin_doc("judkins", FSF_CATALOGUED_BUILTIN_VARIANTS["judkins"])
        self.assertEqual((doc["width"], doc["height"]), (6, 6))
        self.assertEqual(doc["ini"], "")
        self.assertEqual(doc["boardFamilyOverride"], "shogi6x6")
        self.assertEqual(_fsf_builtin_synced_fields(doc)["boardFamilyOverride"], "shogi6x6")
        self.assertEqual(set(doc["pieces"]), {"p", "n", "s", "g", "b", "r", "k"})
        self.assertEqual(set(doc["pocketRoles"]), {"p", "n", "s", "g", "b", "r"})
        self.assertTrue(doc["captureToHand"])
        self.assertEqual(doc["promotionType"], "shogi")
        self.assertEqual(doc["promotionRoles"], ["p", "n", "s", "b", "r"])
        self.assertEqual(doc["promotionOrder"], ["+", ""])
        self.assertTrue(doc["legalMovesNeedHistory"])
        self.assertTrue(doc["nFoldIsDraw"])
        self.assertNotIn("judkins", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)

    def test_chigorin_is_not_seeded_until_side_specific_promotions_are_supported(self) -> None:
        self.assertNotIn("chigorin", FSF_CATALOGUED_BUILTIN_VARIANTS)
        self.assertIn("chigorin", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
        self.assertIn("chigorin", FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS)

    def test_premove_profile_can_be_narrower_than_general_client_profile(self) -> None:
        for name in ("omicron", "troitzky"):
            metadata = FSF_CATALOGUED_BUILTIN_VARIANTS[name]
            self.assertEqual(metadata["clientVariant"], "chess")
            self.assertEqual(metadata["premoveVariant"], "grand")

    def test_paradigm_is_seeded_with_dragon_bishop_promotions(self) -> None:
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS["paradigm"]
        self.assertEqual(metadata["pieceNames"], {"b": "Dragon Bishop"})
        self.assertEqual(metadata["promotionRoles"], ("p",))
        self.assertEqual(metadata["promotionOrder"], CATALOGUED_CHESS_PROMOTION_ORDER)
        self.assertNotIn("paradigm", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)

    def test_gustav_and_omicron_promotion_targets_include_fairy_pieces(self) -> None:
        gustav = FSF_CATALOGUED_BUILTIN_VARIANTS["gustav3"]
        self.assertEqual(gustav["promotionRoles"], ("p",))
        self.assertEqual(gustav["promotionOrder"], ("a", "q", "r", "b", "n"))

        omicron = FSF_CATALOGUED_BUILTIN_VARIANTS["omicron"]
        self.assertEqual(omicron["promotionRoles"], ("p",))
        self.assertEqual(omicron["promotionOrder"], ("w", "c", "q", "r", "b", "n"))


class FsfBuiltinDescriptionStorageTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_includes_retired_builtins_but_only_exact_default(self) -> None:
        collection = SimpleNamespace(
            update_many=AsyncMock(return_value=SimpleNamespace(modified_count=1))
        )

        await _remove_legacy_fsf_builtin_description_fields(collection)

        collection.update_many.assert_awaited_once_with(
            {
                "source": CATALOGUED_SOURCE_FSF_BUILTIN,
                "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
            },
            {"$unset": {"description": ""}},
        )

    async def test_startup_unsets_automatic_description(self) -> None:
        existing = {
            "_id": "yarishogi",
            "name": "yarishogi",
            "source": CATALOGUED_SOURCE_FSF_BUILTIN,
            "description": FSF_CATALOGUED_BUILTIN_DESCRIPTION,
        }
        collection = SimpleNamespace(
            find_one=AsyncMock(return_value=existing),
            update_one=AsyncMock(),
            update_many=AsyncMock(),
        )
        app_state = SimpleNamespace(db={"catalogued_variant": collection})
        rebuilt = {"name": "yarishogi", "references": []}

        with (
            patch(
                "catalogued_variants.FSF_CATALOGUED_BUILTIN_VARIANTS",
                {"yarishogi": {"description": FSF_CATALOGUED_BUILTIN_DESCRIPTION}},
            ),
            patch("catalogued_variants.FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS", frozenset()),
            patch("catalogued_variants.BUILTIN_FSF_VARIANT_NAMES", {"yarishogi"}),
            patch("catalogued_variants._build_fsf_builtin_doc", return_value=rebuilt),
        ):
            await ensure_fsf_catalogued_builtin_variants(app_state)

        update = collection.update_one.await_args.args[1]
        self.assertEqual(update["$unset"]["description"], "")

    async def test_startup_preserves_custom_description(self) -> None:
        existing = {
            "_id": "yarishogi",
            "name": "yarishogi",
            "source": CATALOGUED_SOURCE_FSF_BUILTIN,
            "description": "Custom administrator description",
        }
        collection = SimpleNamespace(
            find_one=AsyncMock(return_value=existing),
            update_one=AsyncMock(),
            update_many=AsyncMock(),
        )
        app_state = SimpleNamespace(db={"catalogued_variant": collection})
        rebuilt = {"name": "yarishogi", "references": []}

        with (
            patch(
                "catalogued_variants.FSF_CATALOGUED_BUILTIN_VARIANTS",
                {"yarishogi": {"description": FSF_CATALOGUED_BUILTIN_DESCRIPTION}},
            ),
            patch("catalogued_variants.FSF_CATALOGUED_RETIRED_BUILTIN_VARIANTS", frozenset()),
            patch("catalogued_variants.BUILTIN_FSF_VARIANT_NAMES", {"yarishogi"}),
            patch("catalogued_variants._build_fsf_builtin_doc", return_value=rebuilt),
        ):
            await ensure_fsf_catalogued_builtin_variants(app_state)

        update = collection.update_one.await_args.args[1]
        self.assertNotIn("description", update.get("$unset", {}))
