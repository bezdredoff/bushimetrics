#!/usr/bin/env python3
"""Build a compact lazy-loaded Japanese Weiss browser catalog.

The browser payload intentionally uses short keys and omits repetitive/null model
fields. The frontend expands them on demand. This keeps ~63k JP printings well
below GitHub's 50 MB recommended single-file threshold.
"""
from __future__ import annotations
import hashlib,json
from collections import defaultdict
from pathlib import Path
from build_catalog import read,RARITY,PREMIUM,prior_for,clamp

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';RAW=DATA/'raw'
OUT=DATA/'catalog-weiss-jp.json';META=DATA/'catalog-weiss-jp-meta.json'

def stable_jp(c):
    raw='|'.join(['weiss','JP',str(c.get('code') or ''),str(c.get('rarity') or '')])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def generic_score(c,set_priors,game_priors):
    rr=RARITY.get(str(c.get('rarity') or '').upper(),30)
    p=prior_for(c,set_priors,game_priors)
    ip=float(p.get('ip',55));reprint=float(p.get('reprint',55));historical=float(p.get('historical',50))
    treatment=82 if rr>=86 else (55 if rr>=62 else 30)
    character=50;liquidity=25;momentum=50;edition=50
    iq=clamp(round(rr*.24+ip*.10+character*.10+reprint*.13+historical*.11+treatment*.10+liquidity*.07+momentum*.10+edition*.05))
    return rr,int(iq),str(c.get('rarity') or '').upper() in PREMIUM

def write_if_changed(path,payload):
    if path.exists():
        try:
            old=json.loads(path.read_text(encoding='utf-8'))
            if old==payload:
                print(path.name,'unchanged');return
        except Exception:pass
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved',path.name,'bytes',path.stat().st_size)

def main():
    raw=read(RAW/'weiss-jp.json',{'cards':[]});source=raw.get('cards',[])
    if len(source)<50000:raise RuntimeError(f'JP input unexpectedly small: {len(source)}')
    manual=read(DATA/'manual_overrides.json',{})
    set_priors=manual.get('setPriors',{});game_priors=manual.get('gamePriors',{})
    cards=[];groups=defaultdict(list)
    for c in source:
        rr,iq,is_premium=generic_score(c,set_priors,game_priors)
        row={
          'id':stable_jp(c),'n':c.get('name'),'s':c.get('set'),'si':c.get('setId'),
          'c':c.get('code'),'r':c.get('rarity'),'t':c.get('cardType'),'co':c.get('color'),
          'im':c.get('image'),'rr':rr,'iq':iq
        }
        if is_premium:row['p']=1
        if c.get('sourceFile'):row['sf']=c['sourceFile']
        cards.append(row);groups[c.get('set') or c.get('setId') or 'Unknown'].append((row,is_premium))
    cards.sort(key=lambda c:(c.get('si') or '',c.get('c') or ''))

    sets=[]
    for name,rows in groups.items():
        sets.append({
          'game':'weiss','language':'JP','name':name,'total':len(rows),'released':len(rows),'announced':0,
          'premium':sum(p for _,p in rows),'priced':0,'pricedEUR':0,'pricedAny':0,
          'imageCoverage':round(sum(bool(c.get('im')) for c,_ in rows)/len(rows)*100,1),
          'priceCoverage':0,'priceCoverageUSD':0,'priceCoverageEUR':0,
          'avgInvestment':round(sum(c.get('iq',0) for c,_ in rows)/len(rows),1) if rows else None,'topMarket':None
        })
    sets.sort(key=lambda x:x['name'])
    counts={
      'total':len(cards),'released':len(cards),'announced':0,'weiss':len(cards),'weissJP':len(cards),
      'priced':0,'pricedEUR':0,'pricedAny':0,'imaged':sum(bool(c.get('im')) for c in cards),
      'premium':sum(bool(c.get('p')) for c in cards),'sets':len(sets)
    }
    catalog={'v':1,'language':'JP','counts':counts,'cards':cards}
    meta={'language':'JP','counts':counts,'sets':sets,'catalogUrl':'data/catalog-weiss-jp.json'}
    write_if_changed(OUT,catalog);write_if_changed(META,meta)
    print(counts)

if __name__=='__main__':main()
