from __future__ import annotations

import unittest

import test_logger
from aiohttp import web
from catalogued.validation import _ensure_catalogued_rules_supported

test_logger.init_test_logger()


class CataloguedVariantRuleGateTestCase(unittest.TestCase):
    def test_extinction_claim_is_allowed_for_server_adjudicated_endings(self) -> None:
        _ensure_catalogued_rules_supported(
            """
            [reformedcourier]
            extinctionValue = loss
            extinctionClaim = true
            extinctionPieceTypes = *
            extinctionPieceCount = 1
            extinctionOpponentPieceCount = 2
            """
        )

    def test_two_boards_stays_unsupported(self) -> None:
        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rules_supported(
                """
                [buglike]
                twoBoards = true
                """
            )

        self.assertIn("twoBoards", exc.exception.text)


if __name__ == "__main__":
    unittest.main()
