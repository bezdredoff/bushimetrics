"""Date-aware market-source audit; catalog build time is NOT price observation time.

Weiss Cardmarket EUR values are daily *price guides*, not completed sales.
TCGCSV market USD values are provider guide prices, not completed sales.
For both currencies, lack of an upstream price publication date means "undated",
even when the HTTP cache was downloaded today.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from market_provenance import OUTDATED_AFTER_DAYS, observation_age_days


def freshness_status(published_at, *, today=None):
    age = observation_age_days(published_at, today)
    if age is None:
        return "undated" if not published_at else "invalid-or-future-date"
    return "fresh" if age <= OUTDATED_AFTER_DAYS else "stale"


def eur_evidence(guide_date, retrieved_at=None, *, today=None):
    age = observation_age_days(guide_date, today)
    return {
        "marketEUREvidenceStatus": "Cardmarket-price-guide-not-completed-sales",
        "marketEURAgeDays": age,
        "marketEURStale": age is None or age > OUTDATED_AFTER_DAYS,
        "marketEURDateStatus": freshness_status(guide_date, today=today),
        # A retrieval timestamp is useful for debugging, but is NOT used as price age.
        "cardmarketRetrievedAt": retrieved_at,
    }


def source_group(card, currency):
    if currency == "EUR":
        return "Cardmarket price guide"
    source = str(card.get("priceSource") or "").lower()
    if "palworld prices" in source:
        return "Palworld Prices completed-sale sample"
    if "tcgcsv" in source:
        return "TCGCSV / TCGplayer price guide"
    if "tcg api" in source:
        return "TCG API / TCGplayer"
    if card.get("marketEvidenceStatus") == "linked-manual-observation":
        return "Linked manual observation (sale not established)"
    return "Other/undetermined USD provider"


def audit_market_freshness(cards, *, generated_at=None, today=None):
    """Aggregate measured/unknown publication dates, *not* source fetching dates.

    Each currency is audited separately. A single printing can appear in both
    panels; this is not a count of unique physical cards with price coverage.
    """
    result = {
        "schemaVersion": 1,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "staleAfterDays": OUTDATED_AFTER_DAYS,
        "currencies": {},
        "providers": [],
        "notes": [
            "Price guide observations are not completed sales.",
            "A successful API fetch today is not proof of a fresh source observation.",
            "Source timestamps missing or in the future are not silently replaced by catalog build time.",
            "A card with EUR and USD prices contributes to both currency totals.",
            "Source sample confidence and calendar age are independent factors.",
        ],
    }
    provider_groups = defaultdict(lambda: defaultdict(int))
    for currency in ("USD", "EUR"):
        counts = {k: 0 for k in ("priced", "fresh", "stale", "undated", "invalid-or-future-date")}
        for card in cards:
            if card.get("availability") != "released":
                continue
            value = card.get("market") if currency == "USD" else card.get("marketEUR")
            if not isinstance(value, (float, int)) or isinstance(value, bool) or value <= 0:
                continue
            counts["priced"] += 1
            asof = card.get("marketAsOf") if currency == "USD" else card.get("cardmarketAsOf")
            status = freshness_status(asof, today=today)
            counts[status] += 1
            provider = source_group(card, currency)
            group = provider_groups[(currency, provider)]
            group["priced"] += 1
            group[status] += 1
        assert sum(counts[k] for k in ("fresh", "stale", "undated", "invalid-or-future-date")) == counts["priced"]
        result["currencies"][currency] = counts
    for (currency, source), counts in sorted(provider_groups.items()):
        result["providers"].append({"currency": currency, "name": source, **dict(counts)})
    return result
