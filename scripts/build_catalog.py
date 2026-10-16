#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';RAW=DATA/'raw'
RARITY={'SSS':100,'SIR':99,'SEC+':98,'SEC':96,'SSP':94,'AGR':92,'OFR':89,'TSP':88,'SP':86,'TSR':82,'OSR':78,'RRR+':76,'SR':62,'RRR':58,'PR':54,'RR':42,'R':28,'U':18,'C':10,'TD':12}
def read(p,default):
    try:return json.loads(Path(p).read_text(encoding='utf-8'))
    except:return default
def clamp(x,a=0,b=100):return max(a,min(b,x))
def stable(game,code,name):return hashlib.sha1(f'{game}|{code}|{name}'.encode()).hexdigest()[:14]
def score(c,priors):
    rr=RARITY.get(c.get('rarity'),30);market=float(c.get('market') or 0);d7=c.get('change7d');d30=c.get('change30d')
    momentum=clamp(50+(float(d7 or 0)*1.6)+(float(d30 or 0)*.45))
    key=(c.get('set') or '').lower(); p=next((v for k,v in priors.items() if k.lower() in key),{})
    ip=float(p.get('ip',55));reprint=float(p.get('reprint',55));historical=float(p.get('historical',50));liquidity=clamp(35+math.log10(max(market,1))*10 if market else 30)
    investment=clamp(round(rr*.30+ip*.22+reprint*.16+historical*.12+liquidity*.08+momentum*.12))
    fair=market*(1+(investment-58)/300+(momentum-50)/650) if market else None
    conf='High' if market and c.get('change30d') is not None and rr>=70 else ('Medium' if market else 'Low')
    c.update({'rarityRank':rr,'momentum':round(momentum),'investment':round(investment),'fair':round(fair,2) if fair else None,'confidence':conf,'modelStatus':'heuristic-v0.3'})
    return c
def main():
    seed=read(DATA/'seed.json',{'cards':[]});wi=read(RAW/'weiss.json',{'cards':[]});pa=read(RAW/'palworld.json',{'cards':[]});imgs=read(RAW/'weiss-images.json',{'cards':{}}).get('cards',{});manual=read(DATA/'manual_overrides.json',{});priors=manual.get('setPriors',{})
    raw=[]
    if wi.get('cards'):raw+=wi['cards']
    if pa.get('cards'):raw+=pa['cards']
    if not raw:raw=seed.get('cards',[])
    seed_by={(x.get('game'),x.get('code')):x for x in seed.get('cards',[])};out=[]
    for c0 in raw:
        c=dict(c0); game=c.get('game') or ('palworld' if str(c.get('code','')).startswith(('EBP','ETD','ESS','EPR')) else 'weiss');c['game']=game
        old=seed_by.get((game,c.get('code')),{})
        for k in ['market','change7d','change30d','change1y','image','ask','identitySource','priceSource','asOf','treatment','edition']:
            if c.get(k) is None and old.get(k) is not None:c[k]=old[k]
        if game=='weiss' and c.get('code') in imgs:c.update({k:v for k,v in imgs[c['code']].items() if v is not None})
        c['id']=stable(game,c.get('code'),c.get('name'));c['priceSource']=c.get('priceSource') or ('TCGRate / TCGplayer' if game=='weiss' else 'Official catalog (price pending)')
        out.append(score(c,priors))
    out.sort(key=lambda c:(c['game'],c.get('set') or '',c.get('code') or '',c.get('name') or ''))
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'modelVersion':'0.3-heuristic','counts':{'total':len(out),'weiss':sum(x['game']=='weiss' for x in out),'palworld':sum(x['game']=='palworld' for x in out),'priced':sum(bool(x.get('market')) for x in out),'imaged':sum(bool(x.get('image')) for x in out)},'cards':out}
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print(payload['counts'])
if __name__=='__main__':main()
