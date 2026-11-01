from __future__ import annotations

import unittest

from aiohttp import web
from catalogued.variants import _client_doc, parse_catalogued_piece_names


class CataloguedVariantPieceNamesTestCase(unittest.TestCase):
    def test_parses_and_normalizes_piece_names(self) -> None:
        self.assertEqual(
            {
                "p": "Soldier",
                "z": "Zebra",
                "c": "Flying Camel",
                "y": "Yōkai",
            },
            parse_catalogued_piece_names(" P : Soldier, z:Zebra, c:  Flying   Camel , y:Yōkai "),
        )

    def test_accepts_structured_piece_name_mapping(self) -> None:
        self.assertEqual(
            {"r": "Chariot", "n": "Night Rider"},
            parse_catalogued_piece_names({"R": "Chariot", "n": "Night Rider"}),
        )

    def test_rejects_invalid_piece_name_syntax(self) -> None:
        invalid_values = (
            "zebra",
            "zz:Zebra",
            "z:Zebra, Z:Striped Horse",
            "z:Zebra:Horse",
            "z:---",
            {"z": 42},
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(web.HTTPBadRequest):
                parse_catalogued_piece_names(value)

    def test_piece_names_are_included_in_editable_client_metadata(self) -> None:
        client_doc = _client_doc(
            {
                "name": "namedpieces",
                "displayName": "Named Pieces",
                "description": "",
                "pieceNames": {"z": "Zebra"},
                "ini": "[namedpieces:chess]\ncustomPiece1 = z:WAD",
                "startFen": "4k3/8/8/8/8/8/4Z3/4K3 w - - 0 1",
                "width": 8,
                "height": 8,
                "pieces": ["k", "z"],
            }
        )

        self.assertEqual(client_doc["pieceNames"], {"z": "Zebra"})


if __name__ == "__main__":
    unittest.main()
