#!/usr/bin/env python3
"""Build the lazy-loaded Japanese Weiss browser catalog."""
from __future__ import annotations
import hashlib,json
from collections import defaultdict
from pathlib import Path
from build_catalog import read,score,attach_character_premium,PREMIUM

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';RAW=DATA/'raw'
OUT=DATA/'catalog-weiss-jp.json';META=DATA/'catalog-weiss-jp-meta.json'

def stable_jp(c):
    raw='|'.join(['weiss','JP',str(c.get('code') or ''),str(c.get('rarity') or '')])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def write_if_changed(path,payload):
    if path.exists():
        try:
            old=json.loads(path.read_text(encoding='utf-8'))
            if old==payload:
                print(path.name,'unchanged');return
        except Exception:pass
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved',path.name)

def main():
    raw=read(RAW/'weiss-jp.json',{'cards':[]})
    cards=[dict(c) for c in raw.get('cards',[])]
    if len(cards)<50000:raise RuntimeError(f'JP input unexpectedly small: {len(cards)}')
    manual=read(DATA/'manual_overrides.json',{})
    set_priors=manual.get('setPriors',{});game_priors=manual.get('gamePriors',{})
    scarcity=read(DATA/'scarcity.json',{'evidence':[]}).get('evidence',[])
    for c in cards:
        c['game']='weiss';c['language']='JP';c['availability']='released';c['id']=stable_jp(c)
    attach_character_premium(cards)
    cards=[score(c,set_priors,game_priors,scarcity) for c in cards]
    cards.sort(key=lambda c:(c.get('setId') or '',c.get('code') or ''))

    groups=defaultdict(list)
    for c in cards:groups[c.get('set') or c.get('setId') or 'Unknown'].append(c)
    sets=[]
    for name,rows in groups.items():
        sets.append({
          'game':'weiss','language':'JP','name':name,'total':len(rows),'released':len(rows),'announced':0,
          'premium':sum(bool(c.get('isPremium')) for c in rows),
          'priced':0,'pricedEUR':0,'pricedAny':0,'imageCoverage':round(sum(bool(c.get('image')) for c in rows)/len(rows)*100,1),
          'priceCoverage':0,'priceCoverageUSD':0,'priceCoverageEUR':0,
          'avgInvestment':round(sum(c.get('investment',0) for c in rows)/len(rows),1) if rows else None,'topMarket':None
        })
    sets.sort(key=lambda x:x['name'])
    counts={
      'total':len(cards),'released':len(cards),'announced':0,'weiss':len(cards),'weissJP':len(cards),
      'priced':0,'pricedEUR':0,'pricedAny':0,'imaged':sum(bool(c.get('image')) for c in cards),
      'premium':sum(bool(c.get('isPremium')) for c in cards),'sets':len(sets)
    }
    catalog={'modelVersion':'0.7-peer-fair-value','language':'JP','counts':counts,'cards':cards}
    meta={'language':'JP','counts':counts,'sets':sets,'catalogUrl':'data/catalog-weiss-jp.json'}
    write_if_changed(OUT,catalog);write_if_changed(META,meta)
    print(counts)

if __name__=='__main__':main()
