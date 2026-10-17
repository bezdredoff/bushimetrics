"""Provenance boundaries for market observations used by BushiMetrics.

An unlinked, manually entered price is a research indication, NOT a verified
sale or guide price. It must never silently overwrite the price and evidence
metadata of a different provider. Keep source age separate from sample confidence.
"""
import math
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


def positive_market(value):
    try:
        amount=float(value)
        return math.isfinite(amount) and amount>0 and not isinstance(value,bool)
    except (TypeError,ValueError,OverflowError):
        return False


def is_completed_sale_sample(row):
    """Require actual Palworld provider evidence, not source-like keywords."""
    if not isinstance(row,dict) or not positive_market(row.get('market')):
        return False
    url=urlparse(str(row.get('marketSourceUrl') or ''))
    return (
        str(row.get('priceSource') or '').startswith('Palworld Prices')
        and url.scheme=='https'
        and url.hostname in ('palworldprices.com','www.palworldprices.com')
        and bool(row.get('palworldPricesCardId'))
        and row.get('marketKind') in ('bare','thin')
        and isinstance(row.get('salesInBasis'),(int,float))
        and not isinstance(row.get('salesInBasis'),bool)
        and math.isfinite(row['salesInBasis'])
        and row['salesInBasis']>0
    )


def combine_usd_guide_sources(tcgcsv,tcgapi,today=None):
    """A speculative or stale optional quote must not replace public TCGCSV.

    The authenticated TCG API importer can produce a stronger identity
    match, but only after its exact collector number, rarity, premium foil
    and actual upstream price publication timestamp were independently checked.
    Old/pre-vetted cache rows are NOT silently upgraded to that status.
    """
    base={code:dict(row) for code,row in tcgcsv.items()
          if isinstance(row,dict) and positive_market(row.get('market'))}
    selected=0
    rejected={}
    for code,row in sorted(tcgapi.items()):
        reason=None
        if not isinstance(row,dict) or not positive_market(row.get('market')):
            reason='no-valid-price'
        elif (
            row.get('marketIdentityStatus')!='exact-code-rarity-foil-dated'
            or row.get('targetCode')!=code
            or str(row.get('targetRarity') or '').upper() not in (
                'SP','SSP','SEC','SEC+','SIR','AGR','OFR','RRR+','SR'
            )
            or str(row.get('printing') or '').lower() not in ('foil','holofoil')
            or row.get('tcgapiCardId') is None
            or not str(row.get('priceSource') or '').startswith('TCG API / TCGPlayer')
        ):
            reason='unverified-source-card-or-physical-treatment'
        elif observation_age_days(row.get('marketAsOf'),today) is None:
            reason='undated-or-future-source-guide'
        elif observation_age_days(row.get('marketAsOf'),today)>OUTDATED_AFTER_DAYS:
            reason='stale-source-guide'
        else:
            base[code]=dict(row)
            selected+=1
        if reason:
            rejected[reason]=rejected.get(reason,0)+1
    return base,{
        'schemaVersion':1,
        'tcgcsvGuideCandidates':len(tcgcsv),
        'tcgapiCacheRows':len(tcgapi),
        'tcgapiQualifiedSelections':selected,
        'tcgapiRejectedReasons':rejected,
        'notes':(
            'Only exact-card and rarity identified, dated premium Foil quotes '
            'from an authorized TCG API source may override TCGCSV. '
            'Price guides are not completed-sale observations.'
        ),
    }


def choose_usd_market(code, provider_prices, palworld_prices,
                      manual_overrides, seed_prices):
    """Return one atomic source record and a separate unsourced indication.

    No mixing of sale samples/source URLs from one supplier with a market price
    from another supplier. Unlinked manual/seed prices remain outside market.
    """
    pal=palworld_prices.get(code) or {}
    guide=provider_prices.get(code) or {}
    chosen=None
    if is_completed_sale_sample(pal):
        # Completed-sale samples are materially different evidence from a
        # market guide. Never let iteration order overwrite a real-sale
        # sample with a TCGplayer/TCGCSV price guide.
        chosen=dict(pal)
        chosen['marketSelectionReason']=(
            'completed-sales-preferred-over-provider-guide'
            if positive_market(guide.get('market')) else 'completed-sales'
        )
    elif positive_market(guide.get('market')):
        chosen=dict(guide)
        chosen['marketSelectionReason']='provider-price-guide-or-estimate'
    elif positive_market(pal.get('market')):
        chosen=dict(pal)
        chosen['marketSelectionReason']='unqualified-provider-price-no-sale-proof'
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
            chosen["marketSelectionReason"] = "explicit-linked-manual-override"
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
        if is_completed_sale_sample(source):
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
