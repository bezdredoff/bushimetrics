"""Evidence-gated BushiMetrics quantitative research models.

All unavailable outputs are None with explicit reasons. Inputs are *observations*,
never synthetic card prices. Currency/edition/cohort separation is mandatory.
No third-party scraping or fabricated probabilities are performed here.
"""
from __future__ import annotations
import math
from statistics import median


def unavailable(reason, **extra):
    return {"value": None, "status": "unavailable", "reason": reason, **extra}


def cec(carton_price=None, currency=None, rarity_hits_per_carton=None,
        cards_in_rarity=None, probability_of_target=None, sample_cartons=None,
        source=None):
    """Expected carton-equivalent acquisition cost, not predicted sale price."""
    if not source:
        return unavailable("Verified case-break source required")
    if currency not in ("EUR", "USD", "JPY"):
        return unavailable("Explicit currency required")
    if not isinstance(carton_price, (int, float)) or not math.isfinite(carton_price) or carton_price <= 0:
        return unavailable("Positive observed carton price required")
    if probability_of_target is None:
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0
                   for v in (rarity_hits_per_carton, cards_in_rarity)):
            return unavailable("Target-card pull probability or rarity hit distribution required")
        probability_of_target = rarity_hits_per_carton / cards_in_rarity
        # Unequal collation invalidates this inference unless verified.
        return unavailable("Uniform distribution across variants is unverified; provide observed target probability")
    if not isinstance(probability_of_target, (int, float)) or not math.isfinite(probability_of_target) or not 0 < probability_of_target <= 1:
        return unavailable("Probability must be between 0 and 1")
    if sample_cartons is None or sample_cartons < 30:
        return unavailable("Fewer than 30 verified cartons: insufficient evidence", sampleCartons=sample_cartons)
    return {"value": round(carton_price / probability_of_target, 2),
            "expectedCartons": round(1 / probability_of_target, 4),
            "currency": currency, "status": "estimated",
            "confidence": "medium" if sample_cartons < 300 else "high",
            "sampleCartons": sample_cartons, "source": source,
            "note": "Scarcity pressure proxy; not fair value or expected resale price"}


def demand_pressure(completed_sales=None, available_inventory=None, new_listings=None,
                    unique_sellers=None, window_days=None, source=None):
    if not source:
        return unavailable("Market observation source missing")
    if window_days not in (7, 14, 30, 60, 90):
        return unavailable("Liquidity-adjusted observation window required")
    if any(not isinstance(v, int) or v < 0 for v in (completed_sales, available_inventory)):
        return unavailable("Nonnegative observed sales and inventory required")
    if available_inventory == 0:
        return unavailable("Zero available inventory; ratio undefined")
    if completed_sales == 0:
        confidence = "low"
    else:
        confidence = "low" if completed_sales < 3 else ("medium" if completed_sales < 10 else "high")
    return {"value": round(completed_sales / available_inventory, 5),
            "status": "estimated", "windowDays": window_days,
            "completedSales": completed_sales, "availableInventory": available_inventory,
            "newListings": new_listings, "uniqueSellers": unique_sellers,
            "confidence": confidence, "source": source}


def recommended_window(monthly_completed_sales):
    if not isinstance(monthly_completed_sales, (int, float)) or monthly_completed_sales < 0:
        return None
    return 14 if monthly_completed_sales > 30 else 30 if monthly_completed_sales >= 10 else 60 if monthly_completed_sales >= 3 else 90


def hype(current_pressure=None, historical_peer_pressures=None, cohort=None, source=None):
    """Historical peer percentile; never a cross-sectional price-momentum percentile."""
    rows = historical_peer_pressures or []
    if not source or not cohort:
        return unavailable("Verified history source and peer cohort required")
    if not isinstance(current_pressure, (int, float)) or not math.isfinite(current_pressure) or current_pressure < 0:
        return unavailable("Observed current demand pressure required")
    valid = [x for x in rows if isinstance(x, (int, float)) and math.isfinite(x) and x >= 0]
    if len(valid) < 30:
        return unavailable("At least 30 independent historical peer observations required", observations=len(valid))
    baseline = median(valid)
    if baseline == 0:
        return unavailable("Historical median is zero; ratio undefined")
    ratio = current_pressure / baseline
    # Midrank percentile; historical peer group must be supplied externally.
    percentile = 100 * (sum(x < current_pressure for x in valid)
                        + .5 * sum(x == current_pressure for x in valid)) / len(valid)
    return {"value": round(percentile, 1), "ratioToBaseline": round(ratio, 4),
            "historicalMedian": round(baseline, 6), "observations": len(valid),
            "cohort": cohort, "source": source, "status": "estimated",
            "confidence": "medium" if len(valid) < 90 else "high"}


def rip_ev(outcomes, product_cost, currency, source=None):
    """Pre-fee raw opening EV. Missing pull probabilities or prices invalidate output."""
    if not source:
        return unavailable("Verified pull distribution and sold-price source required")
    if currency not in ("EUR", "USD", "JPY") or not isinstance(product_cost, (int, float)) or product_cost < 0:
        return unavailable("Valid sealed-product cost and currency required")
    if not outcomes:
        return unavailable("Card outcome distribution missing")
    total_probability = 0.
    ev = 0.
    for card in outcomes:
        probability = card.get("probability")
        price = card.get("soldPrice")
        if (not isinstance(probability, (int, float)) or not math.isfinite(probability)
                or not 0 <= probability <= 1 or not isinstance(price, (int, float))
                or not math.isfinite(price) or price < 0 or card.get("currency") != currency):
            return unavailable("Each outcome requires valid probability and sold price in same currency")
        total_probability += probability
        ev += probability * price
    if abs(total_probability - 1) > .0001:
        return unavailable("Pull probabilities must sum to 1; do not omit common outcomes",
                           probabilitySum=round(total_probability, 6))
    return {"value": round(ev, 2), "cost": round(product_cost, 2),
            "netBeforeFees": round(ev-product_cost, 2), "currency": currency,
            "status": "estimated", "source": source,
            "note": "Excludes grading, fees, taxes, liquidity and shipping; not realizable EV"}


def grading_ev(outcomes, grading_cost, currency, source=None):
    """Grading-adjusted EV only for complete observed grade distribution."""
    if not source or not outcomes:
        return unavailable("Observed grade probabilities and graded sold prices required")
    if currency not in ("EUR", "USD", "JPY") or not isinstance(grading_cost, (int, float)) or grading_cost < 0:
        return unavailable("Valid grading cost and currency required")
    probs = 0.
    total = 0.
    for outcome in outcomes:
        p, price = outcome.get("probability"), outcome.get("netSoldPrice")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in (p, price)) or outcome.get("currency") != currency:
            return unavailable("Every grade needs probability and net sold price in matching currency")
        probs += p
        total += p*price
    if abs(probs-1)>0.0001:
        return unavailable("Grade outcome probabilities must total 1")
    return {"value":round(total-grading_cost,2),"currency":currency,
            "status":"estimated","source":source,
            "note":"Net grade proceeds after grading cost; excludes acquisition unless already in netSoldPrice"}


def franchise_health(signals=None, source=None):
    """No arbitrary composite of unrelated player, sales and community metrics."""
    if not source or not signals:
        return unavailable("Comparable, dated franchise activity time series required")
    return unavailable("Franchise index requires validated normalization, weights and retention cohorts")
