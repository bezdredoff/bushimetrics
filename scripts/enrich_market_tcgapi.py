#!/usr/bin/env python3
"""Incrementally enrich Weiss premium cards with TCG API / TCGPlayer market data.

Requires TCGAPI_KEY. Without it the script exits successfully and leaves the
catalog usable. A daily request budget lets even the free tier fill the cache
progressively instead of blocking a refresh.
"""
from __future__ import annotations
import json,math,os,re,time
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

SOURCE_RARITY_ALIASES={
    'SPECIALRARE':'SP','SUPERSPECIALRARE':'SSP','SECRET RARE':'SEC',
    'SECRETRARE':'SEC','SUPERRARE':'SR','TRIPLERARE':'RRR',
    'SUPERSECRETRARE':'SSS','OVERFRAMERARE':'OFR',
}
PREMIUM_PRINTING_TYPES={'FOIL','HOLOFOIL'}


def normalized_code(value):
    return re.sub(r'\s+','',str(value or '')).upper()


def normalized_rarity(value):
    raw=re.sub(r'[\s_-]+','',str(value or '')).upper()
    return SOURCE_RARITY_ALIASES.get(raw,raw)


def positive_price(value):
    try:
        amount=float(value)
        return amount if math.isfinite(amount) and amount>0 else None
    except (ValueError,TypeError,OverflowError):
        return None


def exact_identity(candidate,code,rarity):
    """Printed number AND explicit premium rarity must match target."""
    if not isinstance(candidate,dict) or candidate.get('id') is None:
        return False
    slug=candidate.get('game_slug') or candidate.get('game_name')
    if slug and str(slug).lower().strip() not in (
        'weiss-schwarz','weiss schwarz','weiss'
    ):
        return False
    ids=[candidate.get(k) for k in ('number','card_number','cardNumber','code')]
    if not any(normalized_code(n)==normalized_code(code) for n in ids):
        return False
    source_rarity=normalized_rarity(candidate.get('rarity'))
    if not source_rarity or source_rarity!=normalized_rarity(rarity):
        return False
    return True


def pick_candidate(payload,code,rarity=None):
    """A fuzzy title/subcode match can never price a different signed parallel.

    If two different provider IDs assert the same printed code/rarity, leave
    the identity unresolved. The input search response ordering is irrelevant.
    """
    matches={}
    for candidate in flatten(payload):
        if not exact_identity(candidate,code,rarity):
            continue
        identifier=str(candidate['id'])
        if identifier in matches:
            continue
        matches[identifier]=candidate
    return next(iter(matches.values())) if len(matches)==1 else None


def price_row(payload,card_id=None,rarity=None,today=None):
    """Require exactly one dated foil price of the selected premium product."""
    from market_provenance import observation_age_days,OUTDATED_AFTER_DAYS
    if normalized_rarity(rarity) not in PREMIUM:
        return None
    rows={}
    for item in flatten(payload):
        if not isinstance(item,dict):
            continue
        value=item.get('market_price')
        if value is None:value=item.get('marketPrice')
        amount=positive_price(value)
        if amount is None:
            continue
        printing=str(item.get('printing') or '').strip().upper()
        if printing not in PREMIUM_PRINTING_TYPES:
            continue
        pid=item.get('card_id')
        if pid is not None and str(pid)!=str(card_id):
            continue
        asof=item.get('market_price_as_of') or item.get('marketPriceAsOf')
        age=observation_age_days(asof,today=today)
        if age is None or age>OUTDATED_AFTER_DAYS:
            continue
        # Deduplicate repeated JSON copies of exactly the same provider quote.
        key=(str(card_id),printing,round(amount,6),str(asof))
        rows[key]=item
    return next(iter(rows.values())) if len(rows)==1 else None


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
        if old and old.get('checkedAt') and old.get('marketIdentityStatus')=='exact-code-rarity-foil-dated':
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
            cand=pick_candidate(payload,code,c.get('rarity'))
            row=price_row(cand,card_id=cand.get('id'),
                          rarity=c.get('rarity')) if cand else None
            if not row and cand and used<budget:
                pp=get_json(s,f"{BASE}/cards/{cand['id']}/prices",key)
                used+=1
                row=price_row(pp,card_id=cand['id'],rarity=c.get('rarity'))
            rec={
                'checkedAt':now.isoformat(),
                'found':bool(cand),
                'targetCode':code,
                'targetRarity':c.get('rarity'),
            }
            if cand:
                rec['tcgapiCardId']=cand.get('id')
                rec['tcgplayerId']=cand.get('tcgplayer_id') or cand.get('tcgplayerId')
            if row:
                rec.update({
                    'market':positive_price(
                        row.get('market_price') if row.get('market_price') is not None
                        else row.get('marketPrice')
                    ),
                    'low':row.get('low_price'),
                    'median':row.get('median_price'),
                    'change24h':row.get('price_change_24h'),
                    'change7d':row.get('price_change_7d'),
                    'change30d':row.get('price_change_30d'),
                    'marketAsOf':row.get('market_price_as_of') or row.get('marketPriceAsOf'),
                    'salesVolume':row.get('sales_volume'),
                    'avgSalesPrice':row.get('avg_sales_price'),
                    'printing':row.get('printing'),
                    'tcgapiIdentityStatus':'exact-code-rarity-foil-dated',
                    'marketIdentityStatus':'exact-code-rarity-foil-dated',
                    'marketSourceUrl':cand.get('tcgplayer_url'),
                    'priceSource':'TCG API / TCGPlayer price guide'
                })
            else:
                rec['marketIdentityStatus']='unverified-or-undated-no-market'
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
    cache['identityAudit']={
        'status':'exact-code-rarity-foil-dated',
        'pricedValidated':sum(
            1 for rec in cardcache.values()
            if isinstance(rec,dict) and rec.get('marketIdentityStatus')==
              'exact-code-rarity-foil-dated' and positive_price(rec.get('market'))
        ),
        'unverifiedRows':sum(
            1 for rec in cardcache.values()
            if not isinstance(rec,dict) or rec.get('marketIdentityStatus')!=
              'exact-code-rarity-foil-dated'
        ),
        'notes':(
            'TCG API is optional and requires valid source API licensing. '
            'Fuzzy titles and undated or different foil printings never '
            'override independently observed USD guide prices.'
        ),
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(cache,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('market enrichment cards checked',done,'requests',used,'cached',len(cardcache))

if __name__=='__main__':main()
