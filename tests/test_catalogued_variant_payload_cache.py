"""The anonymous HTML catalogue is shared, bounded, and invalidated on writes."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from catalogued.variants import (
    invalidate_public_catalogued_variants_json,
    public_catalogued_variants_json,
)


class PublicCataloguedVariantsPayloadCacheTestCase(unittest.TestCase):
    def test_reuses_payload_until_the_catalogue_changes(self):
        app_state = SimpleNamespace(catalogued_variants={})
        with patch(
            "catalogued.variants.catalogued_variants_for_client",
            return_value=[{"name": "sample"}],
        ) as builder:
            payload = public_catalogued_variants_json(app_state)
            self.assertEqual(payload, public_catalogued_variants_json(app_state))
            self.assertEqual(builder.call_count, 1)

            # Direct catalogue additions (including tests) invalidate by size.
            app_state.catalogued_variants["sample"] = {"visibility": "private"}
            self.assertEqual(payload, public_catalogued_variants_json(app_state))
            self.assertEqual(builder.call_count, 2)

            # Writers explicitly invalidate same-size document updates.
            invalidate_public_catalogued_variants_json(app_state)
            self.assertEqual(payload, public_catalogued_variants_json(app_state))
            self.assertEqual(builder.call_count, 3)
