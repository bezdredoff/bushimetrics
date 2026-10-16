#!/usr/bin/env python3
"""Build the current Palworld OCG printing catalog from a GitHub-hosted
official-card mirror plus versioned BushiMetrics overrides for newly released
printings not yet present upstream.

CI uses a local checkout of dragogodev/cgs, so catalog refreshes are GitHub-native
and do not depend on anti-bot-protected websites.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/palworld.json'
OVERRIDES=ROOT/'data/palworld-current-overrides.json'
DEFAULT_LOCAL=ROOT/'external/cgs/Palworld/AllCards.json'
BASE_URL='https://raw.githubusercontent.com/dragogodev/cgs/master/Palworld/AllCards.json'
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

def from_upstream(raw):
    return {
        'game':'palworld','language':'EN',
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

def load_upstream(local_path,url):
    p=Path(local_path)
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8')), f'file://{p}'
    r=requests.get(url,headers={'User-Agent':UA},timeout=40)
    r.raise_for_status()
    return r.json(),url

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-file',default=str(DEFAULT_LOCAL))
    ap.add_argument('--upstream-url',default=BASE_URL)
    args=ap.parse_args()
    upstream,source=load_upstream(args.source_file,args.upstream_url)
    if not isinstance(upstream,list):
        raise RuntimeError('Unexpected Palworld upstream schema')
    by_code={c['code']:c for c in (from_upstream(x) for x in upstream) if c.get('code')}
    o=json.loads(OVERRIDES.read_text(encoding='utf-8'))
    for c in o.get('releasedCards',[]):
        by_code[c['code']]={**by_code.get(c['code'],{}),**c,'game':'palworld','language':c.get('language') or 'EN','availability':'released'}
    expected=int(o.get('expectedReleasedCount',0))
    cards=sorted(by_code.values(),key=lambda c:c['code'])
    if expected and len(cards)!=expected:
        raise RuntimeError(f'Palworld released catalog mismatch: got {len(cards)}, expected {expected}')
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':source,
        'expectedReleasedCount':expected,
        'cards':cards,
        'announcedCards':o.get('announcedCards',[])
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved Palworld released',len(cards),'announced',len(payload['announcedCards']),flush=True)

if __name__=='__main__': main()
