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
import json
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/palworld.json'
OUT=ROOT/'data/market/palworldprices.json'
URL='https://palworldprices.com/api/v1/cards.json'
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

PREMIUM_SUFFIXES={'OSR','SSP','SP','SR','TSP','TSR','SSS','S'}

def normalize_base(code):
    code=str(code or '').strip().upper()
    if code.startswith('BP'): return 'E'+code
    if code.startswith('TD'): return 'E'+code
    if code.startswith('SOUL'): return 'E'+code
    return code

def target_code(row, known):
    base=normalize_base(row.get('code'))
    variant=str(row.get('variant') or '').strip().upper()
    candidates=[]
    if variant in PREMIUM_SUFFIXES:
        candidates.append(base+variant)
    candidates.append(base)
    if variant and variant not in PREMIUM_SUFFIXES:
        candidates.append(base+variant)
    for c in candidates:
        if c in known:return c
    return None

def main():
    if not RAW.exists():
        print('Palworld catalog missing; sold-price enrichment skipped.')
        return
    source=json.loads(RAW.read_text(encoding='utf-8'))
    known={str(c.get('code') or '').upper() for c in source.get('cards',[]) if c.get('code')}

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

    asof=payload.get('asOf')
    stale=bool(payload.get('stale'))
    matched={}
    skipped=0
    duplicates=0
    for row in payload.get('cards') or []:
        code=target_code(row,known)
        if not code:
            skipped+=1; continue
        h=row.get('headline') or {}
        kind=h.get('kind') or 'none'
        rec={
            'marketKind':kind,
            'marketConfidence':h.get('confidence') or row.get('confidence') or 'NONE',
            'marketAsOf':asof,
            'marketStale':stale,
            'marketSourceUrl':row.get('pageUrl'),
            'priceSource':'Palworld Prices — completed-sale median',
            'palworldPricesCardId':row.get('cardId'),
            'marketBasisWindow':h.get('basisWindow'),
            'marketEstimator':h.get('estimator'),
            'marketMethod':h.get('method'),
            'salesInBasis':h.get('salesInBasis'),
            'salesInWindow':h.get('salesInWindow'),
        }
        if kind in ('bare','thin') and h.get('medianUsd') is not None:
            rec['market']=h.get('medianUsd')
        if kind=='thin':
            rec['marketQualifier']=h.get('qualifier') or 'Thin sample (1–3 completed sales) — approximate only.'
        asks=row.get('asks') or {}
        if asks:
            rec.update({
                'marketAskCount':asks.get('n'),
                'marketAskLow':asks.get('lowUsd'),
                'marketAskMedian':asks.get('medianAskUsd'),
                'marketAskSpreadPct':asks.get('spreadPct'),
                'marketAskAsOf':asks.get('asOf'),
            })
        # Prefer a priced or higher-confidence row if API contains multiple identities
        old=matched.get(code)
        if old:
            duplicates+=1
            rank={'HIGH':4,'MEDIUM':3,'LOW':2,'NONE':1}
            if rank.get(str(rec.get('marketConfidence')).upper(),0) <= rank.get(str(old.get('marketConfidence')).upper(),0):
                continue
        matched[code]=rec

    out={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'asOf':asof,'stale':stale,'source':URL,
        'attribution':payload.get('attribution') or 'Data: Palworld Prices (palworldprices.com) — completed-sale prices with confidence tiers',
        'stats':{'apiCards':len(payload.get('cards') or []),'matched':len(matched),'skipped':skipped,'duplicateTargets':duplicates},
        'cards':matched,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Palworld Prices matched',len(matched),'of',len(known),'released catalog codes;',out['stats'])

if __name__=='__main__':main()
