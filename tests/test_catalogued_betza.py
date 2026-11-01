from __future__ import annotations

import unittest
from unittest.mock import patch

import catalogued.betza as catalogued_betza
from catalogued.betza import catalogued_betza_diagrams, catalogued_betza_pieces


class CataloguedBetzaDiagramTestCase(unittest.TestCase):
    def setUp(self) -> None:
        catalogued_betza._cached_betza_svg.cache_clear()
        catalogued_betza._cached_piece_diagram_definitions.cache_clear()
        catalogued_betza._cached_catalogued_betza_diagrams.cache_clear()

    def test_custom_piece_diagrams_are_generated_from_betza_definitions(self):
        diagrams = catalogued_betza_diagrams(
            {
                "ini": """
                [testvariant:chess]
                customPiece1 = n:N
                customPiece2 = a:BN
                """,
                "width": 8,
                "height": 8,
            }
        )

        self.assertEqual([diagram["piece"] for diagram in diagrams], ["n", "a"])
        self.assertEqual([diagram["betza"] for diagram in diagrams], ["N", "BN"])
        self.assertIn("<svg", diagrams[0]["svg"])
        self.assertIn("Custom piece 1", diagrams[0]["title"])

    def test_documentation_ini_generates_diagrams_without_runtime_ini(self):
        diagrams = catalogued_betza_diagrams(
            {
                "ini": "",
                "rulesIni": """
                [documented:shogi]
                customPiece1 = n:fRffN
                customPiece2 = g:WfFbR
                """,
                "width": 7,
                "height": 9,
            }
        )

        self.assertEqual([diagram["piece"] for diagram in diagrams], ["n", "g"])
        self.assertEqual([diagram["betza"] for diagram in diagrams], ["fRffN", "WfFbR"])

    def test_explicit_piece_name_replaces_custom_piece_fallback(self):
        diagrams = catalogued_betza_diagrams(
            {
                "ini": """
                [namedpiece:chess]
                customPiece1 = z:WAD
                """,
                "pieceNames": {"z": "Zebra"},
            }
        )

        self.assertEqual(diagrams[0]["title"], "Zebra (Z) movement")

    def test_custom_king_with_betza_is_rendered_but_bare_king_is_ignored(self):
        with_custom_king = catalogued_betza_diagrams(
            {
                "ini": """
                [royaltest:chess]
                king = k:KN
                """,
            }
        )
        bare_king = catalogued_betza_diagrams(
            {
                "ini": """
                [normalking:chess]
                king = k
                """,
            }
        )

        self.assertEqual(len(with_custom_king), 1)
        self.assertEqual(with_custom_king[0]["piece"], "k")
        self.assertEqual(with_custom_king[0]["betza"], "KN")
        self.assertEqual(bare_king, [])

    def test_resolved_piece_map_includes_fsf_builtin_betza(self):
        pieces = catalogued_betza_pieces(
            {
                "name": "janus",
                "fsfBuiltinVariant": "janus",
                "baseVariant": "",
                "clientVariant": "capablanca",
                "ini": "",
                "pieces": ["p", "n", "b", "r", "q", "k", "j"],
            }
        )

        self.assertEqual(pieces, {"j": "BN"})

    def test_shatar_bishop_premove_override_is_not_a_rule_diagram(self):
        doc = {
            "name": "shatar",
            "fsfBuiltinVariant": "shatar",
            "baseVariant": "",
            "clientVariant": "shatranj",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "k", "j"],
        }

        self.assertEqual(catalogued_betza_pieces(doc), {"b": "B", "j": "RF"})
        self.assertEqual(
            [(diagram["piece"], diagram["betza"]) for diagram in catalogued_betza_diagrams(doc)],
            [("j", "RF")],
        )

    def test_courier_normal_bishop_does_not_inherit_shatranj_alfil(self):
        doc = {
            "name": "courier",
            "fsfBuiltinVariant": "courier",
            "baseVariant": "",
            "clientVariant": "shatranj",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "k", "e", "f", "m", "w"],
        }

        self.assertEqual(
            catalogued_betza_pieces(doc),
            {"b": "B", "e": "A", "f": "F", "m": "K", "w": "W"},
        )
        self.assertNotIn("b", {diagram["piece"] for diagram in catalogued_betza_diagrams(doc)})

    def test_paradigm_dragon_bishop_uses_fsf_movement(self):
        doc = {
            "name": "paradigm",
            "fsfBuiltinVariant": "paradigm",
            "baseVariant": "",
            "clientVariant": "chess",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "q", "k"],
        }

        self.assertEqual(catalogued_betza_pieces(doc), {"b": "BnN"})
        self.assertEqual(
            [(diagram["piece"], diagram["betza"]) for diagram in catalogued_betza_diagrams(doc)],
            [("b", "BnN")],
        )

    def test_petrified_inherits_sideways_pawn_and_replaces_king_with_commoner(self):
        doc = {
            "name": "petrified",
            "fsfBuiltinVariant": "petrified",
            "baseVariant": "pawnsideways",
            "clientVariant": "chess",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "q", "k"],
        }

        self.assertEqual(
            catalogued_betza_pieces(doc),
            {"k": "K", "p": "fsmWfceFifmnD"},
        )

    def test_newer_fsf_builtin_piece_definitions_are_available(self):
        gustav = catalogued_betza_pieces(
            {
                "name": "gustav3",
                "fsfBuiltinVariant": "gustav3",
                "baseVariant": "",
                "ini": "",
                "pieces": ["p", "n", "b", "r", "q", "k", "a"],
            }
        )
        omicron = catalogued_betza_pieces(
            {
                "name": "omicron",
                "fsfBuiltinVariant": "omicron",
                "baseVariant": "",
                "ini": "",
                "pieces": ["p", "n", "b", "r", "q", "k", "c", "w"],
            }
        )

        self.assertEqual(gustav, {"a": "QN"})
        self.assertEqual(omicron, {"c": "DAW", "w": "CF"})

    def test_builtin_pawn_premove_overrides_are_not_rule_diagrams(self):
        raazuvaa = {
            "name": "raazuvaa",
            "fsfBuiltinVariant": "raazuvaa",
            "baseVariant": "",
            "clientVariant": "chess",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "q", "k"],
        }
        torpedo = {
            "name": "torpedo",
            "fsfBuiltinVariant": "torpedo",
            "baseVariant": "",
            "clientVariant": "chess",
            "ini": "",
            "pieces": ["p", "n", "b", "r", "q", "k"],
        }

        self.assertEqual(catalogued_betza_pieces(raazuvaa), {"p": "fmWfceF"})
        self.assertEqual(catalogued_betza_pieces(torpedo), {"p": "fmWfceFfmnD"})
        self.assertEqual(catalogued_betza_diagrams(raazuvaa), [])
        self.assertEqual(catalogued_betza_diagrams(torpedo), [])

    def test_custom_piece_overrides_inherited_fsf_builtin_betza(self):
        pieces = catalogued_betza_pieces(
            {
                "name": "custom-janus",
                "baseVariant": "janus",
                "ini": "[custom-janus:janus]\ncustomPiece1 = j:W",
                "pieces": ["p", "n", "b", "r", "q", "k", "j"],
            }
        )

        self.assertEqual(pieces, {"j": "W"})

    def test_custom_piece_diagram_list_is_cached_by_ini_and_preview_size(self):
        doc = {
            "ini": """
            [cachetest:chess]
            customPiece1 = a:BN
            """,
            "width": 8,
            "height": 8,
        }

        with patch(
            "catalogued.betza._custom_piece_definitions",
            wraps=catalogued_betza._custom_piece_definitions,
        ) as definitions:
            first = catalogued_betza_diagrams(doc)
            second = catalogued_betza_diagrams(dict(doc))

        self.assertEqual(first, second)
        self.assertEqual(definitions.call_count, 1)


if __name__ == "__main__":
    unittest.main()
