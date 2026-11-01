from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web
from catalogued.promotions import _BUILTIN_PROMOTIONS, _site_definitions
from catalogued.variants import (
    _check_ini_with_pyffish_child,
    _ensure_catalogued_rules_supported,
    validate_catalogued_ini,
)


class PromotionChainingTestCase(unittest.TestCase):
    def test_rejects_chains_cycles_and_self_promotions(self) -> None:
        for mapping in (
            "p:g g:r r:d",
            "r:d g:r p:g",
            "p:g g:p",
            "p:p",
            "p:g g:g",
            # The reported variant also has several independent promotions.
            "g:r p:g s:m v:w c:i x:l o:q t:a b:h r:d",
        ):
            with self.subTest(mapping=mapping), self.assertRaises(web.HTTPBadRequest) as exc:
                _ensure_catalogued_rules_supported(
                    f"[promotiontest:chess]\npromotedPieceType={mapping}"
                )
            self.assertEqual(exc.exception.text, "Promotion chaining is not supported by FSF.")

    def test_accepts_independent_shared_and_disabled_targets(self) -> None:
        for mapping in ("", "-", "p:g s:g b:h r:d", "p:g g:-", "g:- p:g", "p:g g:r g:-"):
            with self.subTest(mapping=mapping):
                _ensure_catalogued_rules_supported(
                    f"[promotiontest:chess]\npromotedPieceType={mapping}"
                )

    def test_ignores_comments_and_uses_last_option_value(self) -> None:
        _ensure_catalogued_rules_supported(
            "[promotiontest:chess]\n"
            "# promotedPieceType=p:g g:r\n"
            "; promotedPieceType=p:g g:r\n"
            "promotedPieceType=p:g g:r\n"
            "promotedPieceType=p:g # g:r is only a comment\n"
        )

    def test_rejects_inherited_builtin_and_site_chains(self) -> None:
        for base, options in (
            ("shogi", "promotedPieceType=g:r"),
            ("minishogi", "promotedPieceType=g:r"),
            ("shogi", "gold=x\npromotedPieceType=x:r"),
            ("shogi", "rook=x\npromotedPieceType=p:x"),
            ("shogun", "promotedPieceType=g:a"),
            ("gorogoroplus", "promotedPieceType=g:r"),
        ):
            with self.subTest(base=base, options=options), self.assertRaises(web.HTTPBadRequest):
                _ensure_catalogued_rules_supported(f"[promotiontest:{base}]\n{options}")

    def test_can_disable_inherited_promotions_to_avoid_a_chain(self) -> None:
        _ensure_catalogued_rules_supported(
            "[promotiontest:shogi]\npromotedPieceType=p:- s:- l:- n:- r:- g:r"
        )

    def test_builtin_and_site_mappings_remain_supported(self) -> None:
        # Only exercise this new guard: some site variants use other rules that
        # the community-variant validator deliberately excludes.
        from catalogued.promotions import ensure_no_promotion_chaining

        for name in _BUILTIN_PROMOTIONS.keys() | _site_definitions().keys():
            with self.subTest(name=name):
                ensure_no_promotion_chaining(f"[promotiontest:{name}]\n")

    def test_rejects_before_registering_rules_in_pyffish(self) -> None:
        with patch("catalogued.variants.sf.load_variant_config") as load_config:
            with self.assertRaises(web.HTTPBadRequest):
                validate_catalogued_ini("[promotiontest:chess]\npromotedPieceType=p:g g:r")
            load_config.assert_not_called()


class PromotionChainingChildTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_before_starting_engine_validation(self) -> None:
        with patch("catalogued.variants._run_process", new_callable=AsyncMock) as run_process:
            with self.assertRaises(web.HTTPBadRequest) as exc:
                await _check_ini_with_pyffish_child(
                    "[promotiontest:shogi]\npromotedPieceType=g:r", "promotiontest"
                )
            self.assertEqual(exc.exception.text, "Promotion chaining is not supported by FSF.")
            run_process.assert_not_awaited()
