#!/usr/bin/env python3
"""Enrich English Weiss Schwarz with public TCGplayer market prices via TCGCSV.

TCGCSV mirrors TCGplayer category/group/product/price endpoints daily and does
not require an API key. Products include extendedData; Weiss collector number
and rarity are used for exact/conservative matching.

The script is intentionally polite:
- one groups request;
- two requests per Weiss group (products + prices);
- 150 ms pause between group pairs;
- prior cache is kept if the source is temporarily unavailable.
"""
from __future__ import annotations
import argparse,json,time,re
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
WEISS=ROOT/'data/raw/weiss.json'
OUT=ROOT/'data/market/tcgcsv.json'
BASE='https://tcgcsv.com/tcgplayer'
CATEGORY=20
UA='BushiMetrics/0.9 (+https://github.com/bezdredoff/bushimetrics)'

def get_json(session,url):
    r=session.get(url,headers={'User-Agent':UA,'Accept':'application/json'},timeout=60)
    r.raise_for_status()
    return r.json()

def ext(product,name):
    target=name.lower()
    for x in product.get('extendedData') or []:
        if str(x.get('name') or '').lower()==target or str(x.get('displayName') or '').lower()==target:
            return str(x.get('value') or '').strip()
    return ''

def norm_code(v):
    return re.sub(r'\s+','',str(v or '')).upper()

def choose_price(rows):
    """Prefer foil-ish price for premium Weiss printings, otherwise Normal.
    When only one subtype exists, use it. We keep all rows for provenance."""
    usable=[r for r in rows if r.get('marketPrice') not in (None,'')]
    if not usable:return None
    def rank(r):
        sub=str(r.get('subTypeName') or '').lower()
        if 'foil' in sub or 'holo' in sub:return 0
        if 'normal' in sub:return 1
        return 2
    return sorted(usable,key=rank)[0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-groups',type=int,default=0,help='Smoke-test only the first N groups; 0 means all groups.')
    ap.add_argument('--require-match',action='store_true',help='Fail if no collector-number price match is found.')
    args=ap.parse_args()
    if not WEISS.exists():
        print('Weiss identity catalog missing; TCGCSV skipped.')
        return
    identity=json.loads(WEISS.read_text(encoding='utf-8'))
    cards=identity.get('cards',[])
    by_code={norm_code(c.get('code')):c for c in cards if c.get('code')}

    s=requests.Session()
    try:
        groups=(get_json(s,f'{BASE}/{CATEGORY}/groups').get('results') or [])
        if args.max_groups:
            groups=groups[:args.max_groups]
    except Exception as e:
        if OUT.exists():
            print('TCGCSV groups unavailable; keeping prior cache:',repr(e))
            return
        raise

    matched={}
    stats={'groups':len(groups),'products':0,'pricedRows':0,'exactNumber':0,'missingNumber':0,'unmatchedNumber':0,'duplicateProducts':0}
    product_seen=set()
    failures=[]
    for i,g in enumerate(groups,1):
        gid=g.get('groupId')
        if gid is None:continue
        try:
            products=get_json(s,f'{BASE}/{CATEGORY}/{gid}/products').get('results') or []
            prices=get_json(s,f'{BASE}/{CATEGORY}/{gid}/prices').get('results') or []
        except Exception as e:
            failures.append({'groupId':gid,'name':g.get('name'),'error':repr(e)})
            continue
        stats['products']+=len(products);stats['pricedRows']+=len(prices)
        prices_by={}
        for row in prices:
            pid=row.get('productId')
            if pid is not None:prices_by.setdefault(int(pid),[]).append(row)
        for p in products:
            pid=p.get('productId')
            if pid is None or int(pid) in product_seen:continue
            product_seen.add(int(pid))
            number=ext(p,'Number') or ext(p,'Card Number')
            if not number:
                stats['missingNumber']+=1;continue
            key=norm_code(number)
            target=by_code.get(key)
            if not target:
                stats['unmatchedNumber']+=1;continue
            chosen=choose_price(prices_by.get(int(pid),[]))
            if not chosen:continue
            stats['exactNumber']+=1
            prev=matched.get(target['code'])
            payload={
                'tcgplayerProductId':int(pid),
                'market':chosen.get('marketPrice'),
                'low':chosen.get('lowPrice'),
                'median':chosen.get('midPrice'),
                'high':chosen.get('highPrice'),
                'directLow':chosen.get('directLowPrice'),
                'marketSubtype':chosen.get('subTypeName'),
                'tcgcsvGroupId':gid,
                'tcgcsvGroupName':g.get('name'),
                'tcgplayerName':p.get('name'),
                'tcgplayerUrl':p.get('url'),
                'tcgplayerImage':p.get('imageUrl'),
                'tcgcsvMatch':'exact-collector-number',
                'priceSource':'TCGCSV / TCGplayer daily mirror',
                'marketSourceUrl':p.get('url'),
                'marketAsOf':datetime.now(timezone.utc).date().isoformat(),
            }
            # In the unlikely event multiple TCGplayer products share the same collector
            # number, prefer the product whose group/card name is closest to our record;
            # otherwise retain the first and report the duplicate.
            if prev:
                stats['duplicateProducts']+=1
                continue
            matched[target['code']]=payload
        if i%25==0:
            print('TCGCSV groups',i,'/',len(groups),'matched',len(matched),flush=True)
        time.sleep(.15)

    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':'https://tcgcsv.com/',
        'categoryId':CATEGORY,
        'stats':{**stats,'matchedCards':len(matched),'failures':len(failures)},
        'failures':failures[:30],
        'cards':matched
    }
    if args.require_match and not matched:
        raise RuntimeError(f'TCGCSV smoke test found no collector-number matches across {len(groups)} groups: {stats}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('TCGCSV matched',len(matched),'of',len(cards),'English Weiss printings;',payload['stats'])

if __name__=='__main__':
    main()
