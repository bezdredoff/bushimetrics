"""Provenance boundaries for market observations used by BushiMetrics.

An unlinked, manually entered price is a research indication, NOT a verified
sale or guide price. It must never silently overwrite the price and evidence
metadata of a different provider. Keep source age separate from sample confidence.
"""
from datetime import date, datetime, timezone
from urllib.parse import urlparse

OUTDATED_AFTER_DAYS = 14


def external_evidence_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme == "https" and bool(parsed.netloc) and not (
            parsed.netloc.lower() in ("github.com", "www.github.com")
            and "/bezdredoff/bushimetrics" in parsed.path.lower()
        )
    except (ValueError, AttributeError):
        return False


def observation_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def observation_age_days(value, today=None):
    observed = observation_date(value)
    if observed is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    age = (today - observed).days
    return age if age >= 0 else None


def choose_usd_market(code, provider_prices, palworld_prices,
                      manual_overrides, seed_prices):
    """Return one atomic source record and a separate unsourced indication.

    No mixing of sale samples/source URLs from one supplier with a market price
    from another supplier. Unlinked manual/seed prices remain outside market.
    """
    chosen = None
    for candidate in (palworld_prices.get(code), provider_prices.get(code)):
        if candidate and candidate.get("market") is not None:
            chosen = dict(candidate)
    indication = {}
    manual = manual_overrides.get(code) or {}
    if manual.get("market") is not None:
        as_of = manual.get("marketAsOf") or manual.get("asOf")
        source = manual.get("marketSourceUrl")
        if external_evidence_url(source) and observation_date(as_of):
            # This entire row replaces the previous provider. Do not inherit
            # its completed-sale count, ask inventory, or market source URL.
            chosen = dict(manual)
            chosen["marketAsOf"] = as_of
            chosen["marketEvidenceStatus"] = "linked-manual-observation"
        else:
            indication = {
                "unverifiedMarketIndicationUSD": manual["market"],
                "unverifiedMarketIndicationSource": manual.get("priceSource") or "Manual snapshot",
                "unverifiedMarketIndicationReason": (
                    "Independent evidence URL and dated per-printing observation required"
                ),
            }
    if chosen is None and not indication:
        seed = seed_prices.get(code) or {}
        if seed.get("market") is not None:
            indication = {
                "unverifiedMarketIndicationUSD": seed["market"],
                "unverifiedMarketIndicationSource": seed.get("priceSource") or "Legacy seed",
                "unverifiedMarketIndicationReason": "Legacy seed lacks a dated independent sale or guide source",
            }
    return chosen, indication


def describe_usd_evidence(source, today=None):
    if not source or source.get("market") is None:
        return {}
    source_url = source.get("marketSourceUrl")
    status = source.get("marketEvidenceStatus")
    if not status:
        if (external_evidence_url(source_url)
                and source.get("marketKind") in ("bare", "thin")
                and isinstance(source.get("salesInBasis"), (int, float))
                and source["salesInBasis"] > 0):
            status = "completed-sale-sample"
        elif external_evidence_url(source_url):
            status = "market-price-guide-or-provider-estimate"
        else:
            status = "provider-price-without-direct-evidence-link"
    age = observation_age_days(source.get("marketAsOf"), today)
    return {
        "marketEvidenceStatus": status,
        "marketObservationAgeDays": age,
        "marketStale": bool(source.get("marketStale")) or age is None or age > OUTDATED_AFTER_DAYS,
    }


def audit_manual_prices(overrides):
    linked = []
    missing = []
    for code, row in sorted(overrides.items()):
        if row.get("market") is None:
            continue
        if (external_evidence_url(row.get("marketSourceUrl"))
                and observation_date(row.get("marketAsOf") or row.get("asOf"))):
            linked.append(code)
        else:
            missing.append(code)
    return {
        "manualPriced": len(linked) + len(missing),
        "linkedDated": len(linked),
        "indicationOnly": len(missing),
        "indicationOnlyCodes": missing,
        "notice": "Unlinked prices are research indications, excluded from observed market and peer-model prices.",
    }
