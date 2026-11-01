from __future__ import annotations

import unittest

from catalogued.variants import _client_doc
from nnue_identity import canonicalize_fsf_ini_v1, fsf_ini_v1_fingerprint


class NnueIdentityTestCase(unittest.TestCase):
    def test_canonicalization_ignores_only_safe_formatting(self) -> None:
        left = """
            # comment
            [DragonFly : CHESS]
            maxFile = 7
            startFen = rbbknnr/ppppppp/7/7/7/PPPPPPP/RBBKNNR[]   w KQkq - 0 1
        """
        right = "[dragonfly:chess]\r\nmaxFile=7\r\nstartFen=rbbknnr/ppppppp/7/7/7/PPPPPPP/RBBKNNR[] w KQkq - 0 1\r\n"

        self.assertEqual(
            canonicalize_fsf_ini_v1(left),
            "[dragonfly:chess]\nmaxFile=7\nstartFen=rbbknnr/ppppppp/7/7/7/PPPPPPP/RBBKNNR[] w KQkq - 0 1\n",
        )
        self.assertEqual(fsf_ini_v1_fingerprint(left), fsf_ini_v1_fingerprint(right))

    def test_option_order_remains_part_of_identity(self) -> None:
        first = "[sample:chess]\nmaxFile=7\nmaxRank=7\n"
        second = "[sample:chess]\nmaxRank=7\nmaxFile=7\n"

        self.assertNotEqual(fsf_ini_v1_fingerprint(first), fsf_ini_v1_fingerprint(second))

    def test_user_catalogued_client_doc_includes_fingerprint(self) -> None:
        ini = "[sample:chess]\nmaxFile=7\n"
        client_doc = _client_doc(
            {
                "name": "sample",
                "displayName": "Sample",
                "ini": ini,
                "startFen": "7/7/7/7/7/7/K5k w - - 0 1",
                "width": 7,
                "height": 7,
                "pieces": ["k"],
                "source": "user",
            }
        )

        self.assertEqual(client_doc["nnueFingerprint"], fsf_ini_v1_fingerprint(ini))

    def test_custom_parent_keeps_udv_on_manual_nnue_path(self) -> None:
        client_doc = _client_doc(
            {
                "name": "child",
                "displayName": "Child",
                "ini": "[child:another-udv]\nmaxFile=7\n",
                "startFen": "7/7/7/7/7/7/K5k w - - 0 1",
                "width": 7,
                "height": 7,
                "pieces": ["k"],
                "source": "user",
            }
        )

        self.assertNotIn("nnueFingerprint", client_doc)

    def test_fsf_builtin_client_doc_does_not_need_udv_fingerprint(self) -> None:
        client_doc = _client_doc(
            {
                "name": "3check",
                "displayName": "Three-check",
                "ini": "[3check:chess]\n",
                "startFen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "width": 8,
                "height": 8,
                "pieces": ["p", "n", "b", "r", "q", "k"],
                "source": "fairy-stockfish-builtin",
            }
        )

        self.assertNotIn("nnueFingerprint", client_doc)


if __name__ == "__main__":
    unittest.main()
