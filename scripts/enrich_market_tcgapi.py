#!/usr/bin/env python3
"""Incrementally enrich Weiss premium cards with TCG API / TCGPlayer market data.

Requires TCGAPI_KEY. Without it the script exits successfully and leaves the
catalog usable. A daily request budget lets even the free tier fill the cache
progressively instead of blocking a refresh.
"""
from __future__ import annotations
import json,os,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import quote
import requests

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/weiss.json'
OUT=ROOT/'data/market/tcgapi.json'
BASE='https://api.tcgapi.dev/v1'
PREMIUM={'SP','SSP','SEC','SEC+','SIR','AGR','OFR','RRR+','SR'}
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

def read(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default

def flatten(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from flatten(v)
    elif isinstance(x,list):
        for v in x: yield from flatten(v)

def pick_candidate(payload, code):
    code_l=code.lower()
    candidates=[]
    for d in flatten(payload):
        if not isinstance(d,dict):continue
        hay=' '.join(str(d.get(k) or '') for k in ('number','card_number','cardNumber','name','product_name','code')).lower()
        if code_l in hay:
            candidates.append(d)
    if not candidates:return None
    exact=[]
    for d in candidates:
        vals=[str(d.get(k) or '').lower() for k in ('number','card_number','cardNumber','code')]
        if code_l in vals: exact.append(d)
    return (exact or candidates)[0]

def price_row(payload):
    rows=[]
    for d in flatten(payload):
        if not isinstance(d,dict):continue
        if any(k in d for k in ('market_price','marketPrice','low_price','price_change_7d')):
            rows.append(d)
    if not rows:return None
    rows.sort(key=lambda d:(str(d.get('printing') or '').lower() not in ('foil','holofoil'), -(float(d.get('market_price') or d.get('marketPrice') or 0))))
    return rows[0]

def get_json(session,url,key):
    r=session.get(url,headers={'User-Agent':UA,'X-API-Key':key},timeout=30)
    if r.status_code==429:raise RuntimeError('RATE_LIMIT')
    r.raise_for_status();return r.json()

def main():
    key=os.environ.get('TCGAPI_KEY','').strip()
    if not key:
        print('TCGAPI_KEY not set; market enrichment skipped cleanly.')
        return
    budget=max(1,int(os.environ.get('TCGAPI_DAILY_REQUEST_BUDGET','80')))
    source=read(RAW,{'cards':[]})
    cache=read(OUT,{'cards':{},'cursor':0})
    cardcache=cache.setdefault('cards',{})
    premium=[c for c in source.get('cards',[]) if str(c.get('rarity') or '').upper() in PREMIUM]
    premium.sort(key=lambda c:(c.get('set') or '',c.get('code') or ''))
    if not premium:
        print('No premium Weiss cards found.')
        return
    now=datetime.now(timezone.utc)
    stale_before=now-timedelta(days=2)
    todo=[]
    for c in premium:
        old=cardcache.get(c['code'])
        fresh=False
        if old and old.get('checkedAt'):
            try:fresh=datetime.fromisoformat(old['checkedAt'].replace('Z','+00:00'))>=stale_before
            except:pass
        if not fresh:todo.append(c)
    cursor=int(cache.get('cursor') or 0)
    if todo: todo=todo[cursor%len(todo):]+todo[:cursor%len(todo)]
    s=requests.Session();used=0;done=0
    for c in todo:
        if used>=budget:break
        code=c['code']
        try:
            q=quote(code,safe='')
            payload=get_json(s,f'{BASE}/search?q={q}&game=weiss-schwarz',key);used+=1
            cand=pick_candidate(payload,code)
            row=price_row(cand) if cand else None
            if not row and cand and cand.get('id') is not None and used<budget:
                pp=get_json(s,f"{BASE}/cards/{cand['id']}/prices",key);used+=1;row=price_row(pp)
            rec={'checkedAt':now.isoformat(),'found':bool(cand)}
            if cand:
                rec['tcgapiCardId']=cand.get('id')
                rec['tcgplayerId']=cand.get('tcgplayer_id') or cand.get('tcgplayerId')
            if row:
                rec.update({
                    'market':row.get('market_price') if row.get('market_price') is not None else row.get('marketPrice'),
                    'low':row.get('low_price'),
                    'median':row.get('median_price'),
                    'change24h':row.get('price_change_24h'),
                    'change7d':row.get('price_change_7d'),
                    'change30d':row.get('price_change_30d'),
                    'marketAsOf':row.get('market_price_as_of'),
                    'salesVolume':row.get('sales_volume'),
                    'avgSalesPrice':row.get('avg_sales_price'),
                    'printing':row.get('printing'),
                    'priceSource':'TCG API / TCGPlayer'
                })
            cardcache[code]=rec;done+=1
            time.sleep(.08)
        except RuntimeError as e:
            if str(e)=='RATE_LIMIT':
                print('TCG API daily rate limit reached.');break
            print('WARN',code,e)
        except Exception as e:
            cardcache[code]={'checkedAt':now.isoformat(),'error':str(e)[:250]}
            print('WARN',code,e)
    cache['generatedAt']=now.isoformat();cache['cursor']=(cursor+done)%max(1,len(todo) or 1);cache['requestsUsed']=used
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(cache,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('market enrichment cards checked',done,'requests',used,'cached',len(cardcache))

if __name__=='__main__':main()
