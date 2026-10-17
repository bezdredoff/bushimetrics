#!/usr/bin/env python3
"""Enrich released Palworld printings from Palworld Prices' free bulk API.

Contract followed from https://palworldprices.com/docs/api/:
- completed-sale estimates only become `market`
- thin samples remain explicitly LOW / approximate
- asks are stored separately and never substituted for sold prices
- unpriced cards remain unpriced
- attribution + pageUrl are preserved per printing
"""
from __future__ import annotations
import json,math,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/palworld.json'
OUT=ROOT/'data/market/palworldprices.json'
URL='https://palworldprices.com/api/v1/cards.json'
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

# Source cardId is the physical printing key. BP01-001 (base, rarity RR)
# and BP01-001-RR (explicit RR variant) are DIFFERENT collectibles even
# though their printed collector number and rarity can be identical.
def normalize_base(code):
    code=str(code or '').strip().upper()
    if code.startswith(('BP','TD','SOUL')):
        return 'E'+code
    return code


def target_identity(row,known):
    """Return exact English collector code OR a machine-readable rejection.

    Never fall back from an explicit variant to the base collector number.
    The API's stable cardId must agree with its code and variant fields.
    """
    if not isinstance(row,dict):
        return None,'invalid-source-row'
    source_code=str(row.get('code') or '').strip().upper()
    source_id=str(row.get('cardId') or '').strip()
    if not re.fullmatch(r'[A-Z0-9]+-[0-9A-Z]+',source_code):
        return None,'invalid-source-collector-code'
    if not source_id:
        return None,'missing-source-printing-id'
    raw_variant=row.get('variant')
    variant='' if raw_variant is None else str(raw_variant).strip().upper()
    if variant and not re.fullmatch(r'[A-Z0-9+]+',variant):
        return None,'invalid-source-variant'
    expected_id='pal-'+source_code+('-'+variant if variant else '')
    if source_id.upper()!=expected_id.upper():
        return None,'source-cardid-variant-disagreement'
    base=normalize_base(source_code)
    target=base+variant if variant else base
    if target not in known:
        return None,'explicit-variant-absent-from-catalog' if variant else 'base-printing-absent-from-catalog'
    return target,'exact-printing-cardid'+('-variant' if variant else '-base')


def target_code(row,known):
    """Compatibility helper, never an approximate fallback."""
    return target_identity(row,known)[0]


def positive_price(value):
    try:
        price=float(value)
        return price if math.isfinite(price) and price>0 else None
    except (ValueError,TypeError,OverflowError):
        return None


def map_sale_rows(rows,known,*,asof=None,stale=False,max_examples=30):
    """Map a complete provider feed atomically, isolating ambiguous identities."""
    candidates=defaultdict(list)
    excluded=Counter()
    examples=[]
    for row in rows:
        code,method=target_identity(row,known)
        if code is None:
            excluded[method]+=1
            if len(examples)<max_examples:
                examples.append({
                    'reason':method,'sourceCardId':row.get('cardId') if isinstance(row,dict) else None,
                    'collectorCode':row.get('code') if isinstance(row,dict) else None,
                    'sourceVariant':row.get('variant') if isinstance(row,dict) else None,
                })
            continue
        headline=row.get('headline') or {}
        kind=headline.get('kind') or 'none'
        rec={
            'marketKind':kind,
            'marketConfidence':headline.get('confidence') or row.get('confidence') or 'NONE',
            'marketAsOf':asof,
            'marketStale':bool(stale),
            'marketSourceUrl':row.get('pageUrl'),
            'priceSource':'Palworld Prices — completed-sale median',
            'palworldPricesCardId':row.get('cardId'),
            'palworldSourceVariant':row.get('variant'),
            'palworldMatch':method,
            'marketBasisWindow':headline.get('basisWindow'),
            'marketEstimator':headline.get('estimator'),
            'marketMethod':headline.get('method'),
            'salesInBasis':headline.get('salesInBasis'),
            'salesInWindow':headline.get('salesInWindow'),
        }
        median=positive_price(headline.get('medianUsd'))
        if kind in ('bare','thin') and median is not None:
            rec['market']=median
        elif kind in ('bare','thin'):
            excluded['priced-headline-without-positive-median']+=1
        if kind=='thin':
            rec['marketQualifier']=headline.get('qualifier') or (
                'Thin sample (1–3 completed sales) — approximate only.'
            )
        asks=row.get('asks') or {}
        if isinstance(asks,dict) and asks:
            rec.update({
                'marketAskCount':asks.get('n'),
                'marketAskLow':asks.get('lowUsd'),
                'marketAskMedian':asks.get('medianAskUsd'),
                'marketAskSpreadPct':asks.get('spreadPct'),
                'marketAskAsOf':asks.get('asOf'),
            })
        candidates[code].append(rec)

    matched={}
    collision_examples=[]
    collision_count=0
    for code,records in sorted(candidates.items()):
        if len(records)>1:
            collision_count+=1
            excluded['colliding-source-printing-rows']+=len(records)
            if len(collision_examples)<max_examples:
                collision_examples.append({
                    'collectorCode':code,
                    'sourceCardIds':sorted(str(r['palworldPricesCardId']) for r in records),
                })
            continue
        matched[code]=records[0]
    priced=sum(rec.get('market') is not None for rec in matched.values())
    stats={
        'apiCards':len(rows),
        'matched':len(matched),
        'priced':priced,
        'skipped':sum(excluded.values()),
        'duplicateTargets':collision_count,
        'collisionCodeGroups':collision_count,
        'rejectionReasons':dict(sorted(excluded.items())),
        'rejectionExamples':examples,
        'collisionExamples':collision_examples,
        'identityMethod':'exact-source-cardId-and-explicit-variant',
        'notes':[
            'An explicit RR/OSR/SSP/SP or other variant never inherits the base printing price.',
            'Distinct source physical printings and duplicate target rows are quarantined.',
            'Only bare/thin positive sale medians become observed USD market prices.',
            'Provider stale status and source publication date are preserved separately from download time.',
        ],
    }
    return matched,stats


def main():
    if not RAW.exists():
        print('Palworld catalog missing; sold-price enrichment skipped.')
        return
    source=json.loads(RAW.read_text(encoding='utf-8'))
    known={str(c.get('code') or '').upper() for c in source.get('cards',[]) if c.get('code')}

    import requests
    s=requests.Session()
    try:
        r=s.get(URL,headers={'User-Agent':UA,'Accept':'application/json'},timeout=60)
        r.raise_for_status()
        payload=r.json()
    except Exception as e:
        if OUT.exists():
            print('Palworld Prices unavailable; keeping prior cache:',e)
            return
        print('Palworld Prices unavailable and no cache:',e)
        return

    rows=payload.get('cards') or []
    if not isinstance(rows,list):
        raise RuntimeError('Palworld Prices feed has no valid cards array; old cache unchanged')
    matched,stats=map_sale_rows(rows,known,asof=payload.get('asOf'),
                               stale=bool(payload.get('stale')))
    # A provider schema change must not silently wipe a whole observed-sale
    # market. We still report *which* rows failed, without overwriting cache.
    if len(matched)<max(100,int(len(known)*.65)):
        raise RuntimeError(
            'Palworld Prices identity-mapping coverage unexpectedly low: '
            f'{len(matched)} of {len(known)} catalog printings; '
            f'rejection reasons: {stats["rejectionReasons"]}. '
            'Previously published cache preserved.'
        )
    out={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'asOf':payload.get('asOf'),'stale':bool(payload.get('stale')),
        'source':URL,
        'attribution':payload.get('attribution') or
            'Data: Palworld Prices (palworldprices.com) — completed-sale prices with confidence tiers',
        'stats':stats,
        'cards':matched,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),
                   encoding='utf-8')
    print('Palworld Prices exact printings',len(matched),'of',len(known),
          'with completed-sale median',stats['priced'],
          'rejected',stats['rejectionReasons'])

if __name__=='__main__':main()
