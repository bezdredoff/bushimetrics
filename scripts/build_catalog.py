#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';RAW=DATA/'raw'
RARITY={'SSS':100,'SIR':99,'SEC+':98,'SEC':96,'SSP':94,'AGR':92,'OFR':89,'TSP':88,'SP':86,'TSR':82,'OSR':78,'RRR+':76,'SR':62,'RRR':58,'PR+':56,'PR':54,'RR+':48,'RR':42,'R':28,'U':18,'C':10,'TD':12,'CR':12,'CC':8,'N':8}

def read(p,default):
    try:return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:return default
def clamp(x,a=0,b=100):return max(a,min(b,x))
def stable(c):
    # Printing identity must include rarity/source because Weiss base and parallels often
    # share character/title roots while being distinct collector objects.
    raw='|'.join(str(c.get(k) or '') for k in ('game','code','rarity','treatment','edition','identitySource'))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def prior_for(c,priors,game_priors):
    if c.get('game') in game_priors:return game_priors[c['game']]
    key=(c.get('set') or '').lower()
    return next((v for k,v in priors.items() if k.lower() in key),{})

def score(c,priors,game_priors):
    rr=RARITY.get(str(c.get('rarity') or '').upper(),30)
    market=float(c.get('market') or 0)
    d7=c.get('change7d');d30=c.get('change30d')
    momentum=clamp(50+(float(d7 or 0)*1.6)+(float(d30 or 0)*.45))
    p=prior_for(c,priors,game_priors)
    ip=float(p.get('ip',55));reprint=float(p.get('reprint',55));historical=float(p.get('historical',50))
    liquidity=clamp(35+math.log10(max(market,1))*10 if market else 25)
    investment=clamp(round(rr*.30+ip*.22+reprint*.16+historical*.12+liquidity*.08+momentum*.12))
    fair=market*(1+(investment-58)/300+(momentum-50)/650) if market else None
    conf='High' if market and c.get('change30d') is not None and rr>=70 else ('Medium' if market else 'Low')
    c.update({'rarityRank':rr,'momentum':round(momentum),'investment':round(investment),
              'fair':round(fair,2) if fair else None,'confidence':conf,'modelStatus':'heuristic-v0.3'})
    return c

def seed_key(c):
    return (c.get('game'),str(c.get('code') or '').upper(),str(c.get('rarity') or '').upper())

def main():
    seed=read(DATA/'seed.json',{'cards':[]})
    wi=read(RAW/'weiss.json',{'cards':[]})
    pa=read(RAW/'palworld.json',{'cards':[]})
    imgs=read(RAW/'weiss-images.json',{'cards':{}}).get('cards',{})
    manual=read(DATA/'manual_overrides.json',{})
    priors=manual.get('setPriors',{});game_priors=manual.get('gamePriors',{})

    seeds=seed.get('cards',[])
    # Fall back *per game*, never for the entire catalog at once.
    weiss_raw=wi.get('cards') or [c for c in seeds if c.get('game')=='weiss']
    pal_raw=pa.get('cards') or [c for c in seeds if c.get('game')=='palworld']
    raw=[*weiss_raw,*pal_raw]

    seed_by={seed_key(x):x for x in seeds}
    out=[];seen=set()
    for c0 in raw:
        c=dict(c0)
        game=c.get('game') or ('palworld' if str(c.get('code','')).upper().startswith(('EBP','ETD','ESS','EPR','ESOUL')) else 'weiss')
        c['game']=game
        old=seed_by.get(seed_key(c),{})
        # Seed/snapshot values are fallback enrichment only; identity from current master wins.
        for k in ['market','change7d','change30d','change1y','ask','priceSource','asOf','edition']:
            if c.get(k) is None and old.get(k) is not None:c[k]=old[k]
        if not c.get('image') and old.get('image'):c['image']=old['image']
        if game=='weiss' and c.get('code') in imgs:
            for k,v in imgs[c['code']].items():
                if v is not None and (k!='image' or not c.get('image')):c[k]=v
        c['id']=stable(c)
        if c['id'] in seen:continue
        seen.add(c['id'])
        c['priceSource']=c.get('priceSource') or ('Market enrichment pending' if game=='weiss' else 'Market enrichment pending')
        out.append(score(c,priors,game_priors))
    out.sort(key=lambda c:(c['game'],c.get('set') or '',c.get('code') or '',c.get('rarity') or '',c.get('name') or ''))
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'modelVersion':'0.3-heuristic',
             'counts':{'total':len(out),'weiss':sum(x['game']=='weiss' for x in out),
                       'palworld':sum(x['game']=='palworld' for x in out),
                       'priced':sum(bool(x.get('market')) for x in out),
                       'imaged':sum(bool(x.get('image')) for x in out)},
             'cards':out}
    DATA.mkdir(exist_ok=True)
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(payload['counts'])

if __name__=='__main__':main()
