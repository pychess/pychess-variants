from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import catalogued.rules as catalogued_rules
from catalogued.rules import catalogued_rule_summary


class CataloguedRuleSummaryCacheTestCase(TestCase):
    def setUp(self) -> None:
        catalogued_rules._cached_catalogued_rule_summary.cache_clear()

    def test_rule_summary_reuses_cache_for_same_definition_and_context(self) -> None:
        doc = {
            "ini": """
            [cachetest:chess]
            connectN = 5
            """,
            "width": 9,
            "height": 9,
            "pieces": ["p", "k"],
        }

        with patch(
            "catalogued.rules.parse_catalogued_ini", wraps=catalogued_rules.parse_catalogued_ini
        ) as parse:
            first = catalogued_rule_summary(doc)
            second = catalogued_rule_summary(dict(doc))

        self.assertIs(first, second)
        self.assertEqual(parse.call_count, 1)

    def test_rule_summary_uses_documentation_ini_before_runtime_ini(self) -> None:
        doc = {
            "ini": "",
            "rulesIni": """
            [documented:shogi]
            customPiece1 = n:fRffN
            pieceDrops = true
            """,
            "pieces": ["p", "n", "k"],
            "pocketRoles": ["p", "n"],
        }

        summary = catalogued_rule_summary(doc)

        self.assertIn("`shogi`", summary["intro"][0])
        section_titles = [section["title"] for section in summary["sections"]]
        self.assertIn("Pieces and movement", section_titles)
        self.assertIn("Drops and hands", section_titles)

    def test_rule_summary_cache_key_includes_document_context(self) -> None:
        doc = {
            "ini": """
            [cachetest:chess]
            connectN = 5
            """,
            "width": 9,
            "height": 9,
        }
        wider_doc = {**doc, "width": 10}

        with patch(
            "catalogued.rules.parse_catalogued_ini", wraps=catalogued_rules.parse_catalogued_ini
        ) as parse:
            first = catalogued_rule_summary(doc)
            second = catalogued_rule_summary(wider_doc)

        self.assertIsNot(first, second)
        self.assertEqual(parse.call_count, 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
