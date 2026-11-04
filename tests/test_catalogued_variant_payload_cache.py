"""The anonymous HTML catalogue is shared, bounded, and invalidated on writes."""

import unittest
from json import loads
from types import SimpleNamespace
from unittest.mock import patch

from catalogued.models import CATALOGUED_AI_FAILURE_LIMIT
from catalogued.repository import (
    clear_catalogued_variant_ai_failures,
    record_catalogued_variant_ai_failure,
)
from catalogued.variants import (
    catalogued_variants_for_client,
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


class CataloguedAiQuarantinePayloadCacheTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_quarantine_and_recovery_refresh_anonymous_payload(self):
        doc = {
            "name": "sample",
            "visibility": "public",
            "enabled": True,
            "ini": "",
            "startFen": "8/8/8/8/8/8/8/8 w - - 0 1",
            "width": 8,
            "height": 8,
            "pieces": ["k"],
        }
        app_state = SimpleNamespace(catalogued_variants={"sample": doc}, db=None)

        def client_doc():
            return loads(public_catalogued_variants_json(app_state))[0]

        initial = client_doc()
        self.assertNotIn("aiDisabled", initial)

        for _ in range(CATALOGUED_AI_FAILURE_LIMIT - 1):
            self.assertFalse(
                await record_catalogued_variant_ai_failure(app_state, "sample", "timeout")
            )
        # A failure below the threshold does not affect client-visible metadata.
        self.assertEqual(client_doc(), initial)

        self.assertTrue(await record_catalogued_variant_ai_failure(app_state, "sample", "timeout"))
        quarantined = client_doc()
        self.assertTrue(quarantined["aiDisabled"])
        self.assertEqual(quarantined["aiDisabledReason"], "timeout")
        self.assertIn("aiDisabledUntil", quarantined)

        await clear_catalogued_variant_ai_failures(app_state, "sample")
        recovered = client_doc()
        self.assertNotIn("aiDisabled", recovered)
        self.assertNotIn("aiDisabledUntil", recovered)
        self.assertEqual(recovered, initial)


class SelectedCataloguedVariantsTestCase(unittest.TestCase):
    def test_names_prevent_unneeded_document_construction(self):
        app_state = SimpleNamespace(
            catalogued_variants={
                "selected": {"name": "selected", "displayName": "Selected"},
                "unneeded": {"name": "unneeded", "displayName": "Unneeded"},
            }
        )
        with (
            patch("catalogued.variants.documents._can_preload_catalogued_doc", return_value=True),
            patch(
                "catalogued.variants.documents._client_doc",
                side_effect=lambda doc, **_: {"name": doc["name"]},
            ) as builder,
        ):
            self.assertEqual(
                catalogued_variants_for_client(app_state, names={"selected"}),
                [{"name": "selected"}],
            )
            self.assertEqual(builder.call_count, 1)
            self.assertEqual(
                catalogued_variants_for_client(app_state, names=set()),
                [],
            )
            self.assertEqual(builder.call_count, 1)
