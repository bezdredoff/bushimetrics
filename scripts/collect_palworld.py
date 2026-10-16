#!/usr/bin/env python3
"""Build the current Palworld OCG printing catalog from a GitHub-hosted
official-card mirror plus versioned BushiMetrics overrides for newly-released
printings not yet present upstream.

Current released-catalog target is versioned in data/palworld-current-overrides.json.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/palworld.json'
OVERRIDES=ROOT/'data/palworld-current-overrides.json'
BASE_URL='https://raw.githubusercontent.com/dragogodev/cgs/master/Palworld/AllCards.json'
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

def from_upstream(raw):
    return {
        'game':'palworld',
        'name':raw.get('name') or raw.get('id'),
        'set':raw.get('set') or 'Palworld',
        'code':raw.get('id'),
        'rarity':raw.get('rare'),
        'cardType':raw.get('card_kind'),
        'subtype':raw.get('card_kind_sub'),
        'color':raw.get('color'),
        'image':raw.get('image'),
        'parallel':raw.get('parallel') == 'Yes',
        'identitySource':'https://github.com/dragogodev/cgs/blob/master/Palworld/AllCards.json',
        'catalogSource':'dragogodev/cgs mirror of official Palworld card data',
        'market':None,
        'priceSource':None,
        'availability':'released',
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--upstream-url',default=BASE_URL)
    args=ap.parse_args()
    r=requests.get(args.upstream_url,headers={'User-Agent':UA},timeout=40)
    r.raise_for_status()
    upstream=r.json()
    if not isinstance(upstream,list):
        raise RuntimeError('Unexpected Palworld upstream schema')
    by_code={c['code']:c for c in (from_upstream(x) for x in upstream) if c.get('code')}
    o=json.loads(OVERRIDES.read_text(encoding='utf-8'))
    for c in o.get('releasedCards',[]):
        by_code[c['code']]={**by_code.get(c['code'],{}),**c,'game':'palworld','availability':'released'}
    expected=int(o.get('expectedReleasedCount',0))
    cards=sorted(by_code.values(),key=lambda c:c['code'])
    if expected and len(cards)!=expected:
        raise RuntimeError(f'Palworld released catalog mismatch: got {len(cards)}, expected {expected}')
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':args.upstream_url,
        'expectedReleasedCount':expected,
        'cards':cards,
        'announcedCards':o.get('announcedCards',[])
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved Palworld released',len(cards),'announced',len(payload['announcedCards']),flush=True)

if __name__=='__main__': main()
