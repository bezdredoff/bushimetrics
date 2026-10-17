#!/usr/bin/env python3
"""Enrich English Weiss Schwarz with public TCGplayer market prices via TCGCSV.

TCGCSV mirrors TCGplayer category/group/product/price endpoints daily and does
not require an API key. Products include extendedData; Weiss collector number
and rarity are used to choose the correct Normal vs Foil price subtype.

The script is intentionally polite:
- one groups request;
- two requests per Weiss group (products + prices);
- 150 ms pause between group pairs;
- prior cache is kept if the source is temporarily unavailable.
"""
from __future__ import annotations
import argparse,json,time,re,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

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

PREMIUM_RARITIES={'RRR','RRR+','SR','SP','SSP','SEC','SEC+','OFR',
                  'TSP','SIR','AGR','OSR','TSR','SSS'}


def subtype_kind(row):
    text=str(row.get('subTypeName') or '').lower()
    if 'foil' in text or 'holo' in text:
        return 'foil'
    if 'normal' in text or 'regular' in text:
        return 'normal'
    return 'unknown'


def choose_price(rows, rarity):
    """Select only an identifiable TCGplayer price subtype for the rarity.

    The old code ranked Foil first for every printing, including ordinary
    Common/Uncommon/Rare/Double-Rare cards, inflating their market price.
    Return (row, reason), preserving explicit uncertainty for unknown or
    contradictory provider subtype metadata.
    """
    good=[]
    for row in rows:
        value=row.get('marketPrice')
        try:
            number=float(value)
        except (ValueError,TypeError,OverflowError):
            continue
        if not math.isfinite(number) or number<=0:
            continue
        good.append(row)
    if not good:
        return None,'missing-price'

    expected='foil' if str(rarity or '').upper() in PREMIUM_RARITIES else 'normal'
    preferred=[row for row in good if subtype_kind(row)==expected]
    if len(preferred)==1:
        return preferred[0],'preferred-'+expected
    if len(preferred)>1:
        return None,'ambiguous-'+expected+'-rows'

    # Unknown subtype can be accepted only when it is the sole quoted price.
    # Never substitute a foil-only quote for a known regular printing or vice versa.
    if len(good)==1 and subtype_kind(good[0])=='unknown':
        return good[0],'single-unspecified-subtype'
    if len(good)==1:
        return None,'opposite-only-subtype'
    return None,'ambiguous-unverified-subtypes'


def finalize_candidates(candidates, max_examples=30):
    """No arbitrary first-product winner for one collector number."""
    matched={}
    examples=[]
    collisions=0
    duplicate_products=0
    for code,rows in sorted(candidates.items()):
        if len(rows)>1:
            collisions+=1
            duplicate_products+=len(rows)-1
            if len(examples)<max_examples:
                examples.append({'collectorCode':code,
                                 'productIds':sorted(rows)})
            continue
        matched[code]=next(iter(rows.values()))
    return matched,collisions,duplicate_products,examples


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

    import requests
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

    candidates=defaultdict(dict)
    stats={'groups':len(groups),'products':0,'pricedRows':0,'exactNumber':0,
           'missingNumber':0,'unmatchedNumber':0,'duplicateProducts':0,
           'subtypeRejections':{},'subtypeSelection':{},'collisionCodeGroups':0,
           'collisionExamples':[]}
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
            chosen,basis=choose_price(prices_by.get(int(pid),[]),target.get('rarity'))
            if not chosen:
                rejected=stats['subtypeRejections']
                rejected[basis]=rejected.get(basis,0)+1
                continue
            stats['exactNumber']+=1
            stats['subtypeSelection'][basis]=stats['subtypeSelection'].get(basis,0)+1
            payload={
                'tcgplayerProductId':int(pid),
                'market':chosen.get('marketPrice'),
                'low':chosen.get('lowPrice'),
                'median':chosen.get('midPrice'),
                'high':chosen.get('highPrice'),
                'directLow':chosen.get('directLowPrice'),
                'marketSubtype':chosen.get('subTypeName'),
                'marketSubtypeSelection':basis,
                'tcgcsvGroupId':gid,
                'tcgcsvGroupName':g.get('name'),
                'tcgplayerName':p.get('name'),
                'tcgplayerUrl':p.get('url'),
                'tcgplayerImage':p.get('imageUrl'),
                'tcgcsvMatch':'exact-collector-number',
                'priceSource':'TCGCSV / TCGplayer daily mirror',
                'marketSourceUrl':p.get('url'),
                # A download timestamp is not the date the underlying market
                # price was observed. TCGCSV's row has no proven price date.
                'marketRetrievedAt':datetime.now(timezone.utc).isoformat(),
            }
            candidates[target['code']][int(pid)]=payload
        if i%25==0:
            print('TCGCSV groups',i,'/',len(groups),
                  'candidate printing codes',len(candidates),flush=True)
        time.sleep(.15)

    matched,collisions,duplicates,examples=finalize_candidates(candidates)
    stats['collisionCodeGroups']=collisions
    stats['duplicateProducts']=duplicates
    stats['collisionExamples']=examples

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
