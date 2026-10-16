"""Regression tests for atomic market sources and unsourced quote quarantine."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from market_provenance import (
    audit_manual_prices, choose_usd_market, describe_usd_evidence,
    external_evidence_url, observation_age_days
)
from build_catalog import apply_market


class MarketProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.provider = {
            "market": 50.0,
            "priceSource": "Completed sales",
            "marketSourceUrl": "https://palworldprices.com/cards/test",
            "marketAsOf": "2026-09-17T22:30:01Z",
            "marketKind": "bare",
            "salesInBasis": 42,
            "marketAskCount": 10,
            "marketConfidence": "HIGH",
        }

    def test_unlinked_manual_quote_never_overwrites_provider_market(self):
        manual = {"C-001": {"market": 999, "priceSource": "manual",
                            "confidence": "High"}}
        src, indication = choose_usd_market(
            "C-001", {}, {"C-001": self.provider}, manual, {}
        )
        self.assertEqual(src["market"], 50)
        self.assertEqual(src["salesInBasis"], 42)
        self.assertEqual(indication["unverifiedMarketIndicationUSD"], 999)
        self.assertEqual(
            audit_manual_prices(manual)["indicationOnlyCodes"], ["C-001"]
        )

    def test_indication_without_provider_is_not_market(self):
        card = {"code": "X", "game": "weiss"}
        apply_market(card, {}, {}, {"X": {"market": 800}}, {})
        self.assertNotIn("market", card)
        self.assertEqual(card["unverifiedMarketIndicationUSD"], 800)

    def test_legacy_seed_only_is_not_market(self):
        card = {"code": "X", "game": "weiss"}
        apply_market(card, {}, {}, {}, {"X": {"market": 444}})
        self.assertNotIn("market", card)
        self.assertEqual(card["unverifiedMarketIndicationUSD"], 444)

    def test_linked_dated_manual_never_inherits_provider_sales_samples(self):
        manual = {"X": {"market": 81, "marketSourceUrl": "https://example.org/sale/1",
                        "marketAsOf": "2026-10-15", "priceSource": "linked market"}}
        card = {"code": "X", "game": "weiss"}
        apply_market(card, {"X": self.provider}, {}, manual, {})
        self.assertEqual(card["market"], 81)
        self.assertEqual(card["marketSourceUrl"], "https://example.org/sale/1")
        self.assertEqual(card["marketEvidenceStatus"], "linked-manual-observation")
        self.assertNotIn("salesInBasis", card)
        self.assertNotIn("marketAskCount", card)
        self.assertNotIn("marketKind", card)

    def test_independent_source_and_per_card_date_both_required(self):
        self.assertFalse(external_evidence_url(
            "https://github.com/bezdredoff/bushimetrics/blob/main/data/market_overrides.json"
        ))
        self.assertFalse(external_evidence_url("javascript:alert(1)"))
        src, indication = choose_usd_market(
            "X", {}, {}, {"X": {"market": 101, "marketAsOf": "2026-10-16"}}, {}
        )
        self.assertIsNone(src)
        self.assertEqual(indication["unverifiedMarketIndicationUSD"], 101)

    def test_source_age_is_not_conflated_with_sample_confidence(self):
        day = date(2026, 10, 16)
        self.assertEqual(observation_age_days(self.provider["marketAsOf"], day), 29)
        facts = describe_usd_evidence(self.provider, day)
        self.assertEqual(facts["marketEvidenceStatus"], "completed-sale-sample")
        self.assertEqual(facts["marketObservationAgeDays"], 29)
        self.assertTrue(facts["marketStale"])
        self.assertEqual(self.provider["marketConfidence"], "HIGH")
        self.assertFalse(describe_usd_evidence(dict(self.provider, marketAsOf="2026-10-15"), day)["marketStale"])

    def test_undated_provider_is_marked_stale_not_assumed_fresh(self):
        facts = describe_usd_evidence({"market": 50, "priceSource": "price guide"})
        self.assertEqual(facts["marketEvidenceStatus"], "provider-price-without-direct-evidence-link")
        self.assertIsNone(facts["marketObservationAgeDays"])
        self.assertTrue(facts["marketStale"])


if __name__ == "__main__":
    unittest.main()
