#!/usr/bin/env python3
"""Build compact browser payloads from the full analytical catalog.

The full data/catalog.json remains the research source of truth. GitHub Pages
loads data/web/catalog-en.json instead, which keeps only fields required for
search/filter/grid/market dashboards. Full card records are split across 16
detail shards and loaded only when a preview is opened.
"""
from __future__ import annotations
import json, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
OUT=DATA/'web'
DETAIL=OUT/'details'

INDEX_FIELDS={
    'id':'i','game':'g','language':'l','availability':'a','name':'n','set':'s',
    'code':'c','rarity':'r','image':'im','marketEUR':'me','market':'mu',
    'fairEUR':'fe','fair':'fu','investment':'iq','momentum':'mo',
    'isPremium':'p','rarityRank':'rr','marketHeatPercentile':'hp',
    'marketHeatLabel':'hl','characterPremiumIndex':'cp',
    'characterPremiumObservations':'co','marketKind':'mk',
    'marketConfidence':'mc','confidence':'cf','fairValueConfidence':'fc',
    'change7d':'d7','change30d':'d30','demandPressure':'dp',
    'demandPressureSales':'ds','demandPressureAsks':'da',
    'priceSource':'ps','priceSourceEUR':'pe','marketAsOf':'ma',
    'cardmarketAsOf':'ca','cardType':'ct','color':'cl'
}

def compact_card(c):
    out={}
    for src,dst in INDEX_FIELDS.items():
        v=c.get(src)
        if v is not None and v != '':
            out[dst]=v
    return out

def main():
    full=json.loads((DATA/'catalog.json').read_text(encoding='utf-8'))
    cards=full.get('cards') or []
    # Initial browser payload intentionally excludes JP because that already has
    # its own compact lazy catalog.
    browser=[compact_card(c) for c in cards if (c.get('language') or 'EN')=='EN']

    if OUT.exists():
        # Keep nothing stale: all browser payloads are deterministic build output.
        shutil.rmtree(OUT)
    DETAIL.mkdir(parents=True,exist_ok=True)

    common={
        'generatedAt':full.get('generatedAt'),
        'modelVersion':full.get('modelVersion'),
        'counts':full.get('counts') or {},
        'sets':full.get('sets') or []
    }
    payload={**common,'cards':browser}
    (OUT/'catalog-en.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    # Tiny first-paint payload: all current Palworld + highest-conviction EN Weiss.
    # This is intentionally a visible subset only until catalog-en.json arrives.
    en_weiss=[c for c in cards if c.get('game')=='weiss' and (c.get('language') or 'EN')=='EN' and c.get('availability')=='released']
    en_weiss.sort(key=lambda c:(-int(c.get('investment') or 0),-int(c.get('rarityRank') or 0),str(c.get('name') or '')))
    pal=[c for c in cards if c.get('game')=='palworld' and (c.get('language') or 'EN')=='EN']
    bootstrap_cards=[compact_card(c) for c in [*en_weiss[:240],*pal]]
    (OUT/'bootstrap.json').write_text(json.dumps({**common,'bootstrap':True,'cards':bootstrap_cards},ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    shards={h:{} for h in '0123456789abcdef'}
    for c in cards:
        cid=str(c.get('id') or '')
        if not cid: continue
        h=cid[0].lower()
        if h not in shards: h='0'
        shards[h][cid]=c
    for h,rows in shards.items():
        (DETAIL/f'{h}.json').write_text(json.dumps({'cards':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    legacy=(DATA/'catalog.json').stat().st_size
    compact=(OUT/'catalog-en.json').stat().st_size
    shard_sizes={h:(DETAIL/f'{h}.json').stat().st_size for h in shards}
    meta={
        'legacyBytes':legacy,'compactBytes':compact,
        'compactCards':len(browser),'bootstrapCards':len(bootstrap_cards),'bootstrapBytes':(OUT/'bootstrap.json').stat().st_size,'detailCards':len(cards),
        'detailShardMaxBytes':max(shard_sizes.values()) if shard_sizes else 0,
        'detailShardBytes':shard_sizes
    }
    (OUT/'meta.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
    print('browser payload',meta)
    if compact >= legacy*.65:
        raise RuntimeError(f'Browser payload compression insufficient: {compact} vs {legacy}')
    if compact > 20_000_000:
        raise RuntimeError(f'Browser payload still too large: {compact}')
    if (OUT/'bootstrap.json').stat().st_size > 2_000_000:
        raise RuntimeError('Bootstrap payload too large')
    if max(shard_sizes.values(),default=0) > 8_000_000:
        raise RuntimeError('Detail shard too large')

if __name__=='__main__':
    main()
