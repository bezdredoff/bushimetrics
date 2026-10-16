#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; RAW=DATA/'raw'; MARKET=DATA/'market'

RARITY={
 'SSS':100,'SIR':99,'SEC+':98,'SEC':96,'SSP':94,'AGR':92,'OFR':89,
 'TSP':88,'SP':86,'TSR':82,'OSR':78,'RRR+':76,'SR':62,'RRR':58,
 'PR+':56,'PR':54,'RR+':48,'RR':42,'R':28,'U':18,'C':10,'TD':12,
 'CR':12,'CC':8,'N':8
}
PREMIUM={'SSS','SIR','SEC+','SEC','SSP','AGR','OFR','TSP','SP','TSR','OSR','RRR+','SR'}

def read(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return default

def clamp(x,a=0,b=100):return max(a,min(b,x))

def stable(c):
    raw='|'.join(str(c.get(k) or '') for k in ('game','code','rarity','edition','treatment','availability'))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def prior_for(c,set_priors,game_priors):
    # Specific set prior wins over game prior.
    key=(c.get('set') or '').lower()
    found=next((v for k,v in set_priors.items() if k.lower() in key),None)
    return found or game_priors.get(c.get('game'),{})

def apply_market(c,tcgapi,manual_market,seed_market):
    code=str(c.get('code') or '')
    # Priority: explicit validated override > API cache > legacy seed.
    src=None
    if code in seed_market: src=seed_market[code]
    api=tcgapi.get(code)
    if api and api.get('market') is not None: src={**(src or {}),**api}
    if code in manual_market: src={**(src or {}),**manual_market[code]}
    if not src:return c
    mapping={
      'market':'market','low':'marketLow','median':'marketMedian',
      'change24h':'change24h','change7d':'change7d','change30d':'change30d',
      'marketAsOf':'marketAsOf','salesVolume':'salesVolume','avgSalesPrice':'avgSalesPrice',
      'priceSource':'priceSource','printing':'marketPrinting','confidence':'marketConfidence'
    }
    for a,b in mapping.items():
        if src.get(a) is not None:c[b]=src[a]
    return c

def scarcity_for(c,evidence,rr):
    for e in evidence:
        if e.get('game')!=c.get('game'):continue
        if str(e.get('rarity') or '').upper()!=str(c.get('rarity') or '').upper():continue
        target=str(e.get('set') or '').lower()
        cardset=str(c.get('set') or '').lower()
        code=str(c.get('code') or '').lower()
        if target and target not in cardset and not code.startswith(target.lower()):continue
        packs=float(e.get('packsPerHit') or 0)
        if packs>0:
            empirical=clamp(30+30*math.log10(packs))
            blended=round(rr*.35+empirical*.65)
            return blended,{k:e.get(k) for k in ('packsPerHit','samplePacks','confidence','evidenceType','source','asOf')}
    return rr,None

def score(c,set_priors,game_priors,scarcity_evidence):
    rr=RARITY.get(str(c.get('rarity') or '').upper(),30)
    scarcity_score,scarcity_note=scarcity_for(c,scarcity_evidence,rr)
    market=float(c.get('market') or 0)
    d7=c.get('change7d');d30=c.get('change30d')
    momentum=clamp(50+(float(d7 or 0)*1.6)+(float(d30 or 0)*.45))
    p=prior_for(c,set_priors,game_priors)
    ip=float(p.get('ip',55));reprint=float(p.get('reprint',55));historical=float(p.get('historical',50))
    treatment=float(c.get('treatmentScore') or (82 if rr>=86 else 55 if rr>=62 else 30))
    liquidity=clamp(35+math.log10(max(market,1))*10 if market else 25)
    edition_bonus=float(c.get('editionScore') or 50)
    investment=clamp(round(
        scarcity_score*.24 + ip*.20 + reprint*.13 + historical*.11 + treatment*.10 +
        liquidity*.07 + momentum*.10 + edition_bonus*.05
    ))
    fair=market*(1+(investment-58)/300+(momentum-50)/650) if market else None
    if c.get('availability')!='released': fair=None
    confidence=c.get('marketConfidence')
    if not confidence:
        confidence='High' if market and c.get('change30d') is not None and rr>=70 else ('Medium' if market else 'Low')
    c.update({
        'rarityRank':rr,'scarcityScore':scarcity_score,'scarcityEvidence':scarcity_note,
        'isPremium':str(c.get('rarity') or '').upper() in PREMIUM,
        'momentum':round(momentum),'investment':round(investment),
        'fair':round(fair,2) if fair else None,'confidence':confidence,
        'modelFactors':{
            'scarcity':round(scarcity_score),'ipStrength':round(ip),'reprintDurability':round(reprint),
            'historicalSignificance':round(historical),'treatment':round(treatment),
            'liquidity':round(liquidity),'editionDurability':round(edition_bonus)
        },
        'modelStatus':'heuristic-v0.4'
    })
    return c

def main():
    seed=read(DATA/'seed.json',{'cards':[]})
    wi=read(RAW/'weiss.json',{'cards':[]})
    pa=read(RAW/'palworld.json',{'cards':[]})
    manual=read(DATA/'manual_overrides.json',{})
    printing=read(DATA/'printing_overrides.json',{'cards':{}}).get('cards',{})
    market_overrides=read(DATA/'market_overrides.json',{'cards':{}}).get('cards',{})
    tcgapi=read(MARKET/'tcgapi.json',{'cards':{}}).get('cards',{})
    cardmarket_file=read(MARKET/'cardmarket.json',{'cards':{}})
    cardmarket=cardmarket_file.get('cards',{})
    cardmarket_asof=cardmarket_file.get('cardmarketCreatedAt') or cardmarket_file.get('generatedAt')
    set_priors=manual.get('setPriors',{}); game_priors=manual.get('gamePriors',{})
    scarcity_evidence=read(DATA/'scarcity.json',{'evidence':[]}).get('evidence',[])

    seeds=seed.get('cards',[])
    seed_market={str(x.get('code') or ''):{k:v for k,v in x.items() if k in (
        'market','change7d','change30d','change1y','priceSource','confidence'
    )} for x in seeds if x.get('code')}

    weiss_raw=wi.get('cards') or [c for c in seeds if c.get('game')=='weiss']
    pal_raw=pa.get('cards') or [c for c in seeds if c.get('game')=='palworld']
    announced=pa.get('announcedCards') or []
    raw=[*weiss_raw,*pal_raw,*announced]

    out=[];seen=set()
    for c0 in raw:
        c=dict(c0)
        code=str(c.get('code') or '').strip()
        if not code:continue
        game=c.get('game') or ('palworld' if code.upper().startswith(('EBP','ETD','ESS','EPR','ESOUL')) else 'weiss')
        c['game']=game
        c['availability']=c.get('availability') or 'released'

        # Versioned physical-printing metadata can override generic catalog data.
        ov=printing.get(code)
        if ov:
            for k,v in ov.items():
                if v is not None:c[k]=v

        apply_market(c,tcgapi,market_overrides,seed_market)
        cm=cardmarket.get(code)
        if cm:
            for k,v in cm.items():
                if v is not None:c[k]=v
            c['cardmarketAsOf']=cardmarket_asof
        c['priceSource']=c.get('priceSource') or ('Cardmarket EUR' if c.get('marketEUR') is not None else 'Market enrichment pending')
        c['id']=stable(c)
        if c['id'] in seen:continue
        seen.add(c['id'])
        out.append(score(c,set_priors,game_priors,scarcity_evidence))

    out.sort(key=lambda c:(c['game'],c.get('availability')!='released',c.get('set') or '',c.get('code') or ''))

    groups=defaultdict(list)
    for c in out:
        groups[(c['game'],c.get('set') or 'Unknown')].append(c)
    set_rows=[]
    for (game,name),cards in groups.items():
        released=[c for c in cards if c.get('availability')=='released']
        priced=[c for c in released if c.get('market')]
        priced_eur=[c for c in released if c.get('marketEUR') is not None]
        priced_any=[c for c in released if c.get('market') or c.get('marketEUR') is not None]
        premiums=[c for c in released if c.get('isPremium')]
        set_rows.append({
            'game':game,'name':name,'total':len(cards),'released':len(released),
            'announced':len(cards)-len(released),'premium':len(premiums),'priced':len(priced),
            'pricedEUR':len(priced_eur),'pricedAny':len(priced_any),
            'imageCoverage':round(sum(bool(c.get('image')) for c in cards)/len(cards)*100,1),
            'priceCoverage':round(len(priced_any)/len(released)*100,1) if released else 0,
            'priceCoverageUSD':round(len(priced)/len(released)*100,1) if released else 0,
            'priceCoverageEUR':round(len(priced_eur)/len(released)*100,1) if released else 0,
            'avgInvestment':round(sum(c.get('investment',0) for c in released)/len(released),1) if released else None,
            'topMarket':max((float(c.get('market') or 0) for c in priced),default=0) or None
        })
    set_rows.sort(key=lambda x:(x['game'],x['name']))

    counts={
        'total':len(out),
        'released':sum(c.get('availability')=='released' for c in out),
        'announced':sum(c.get('availability')!='released' for c in out),
        'weiss':sum(c['game']=='weiss' for c in out),
        'palworld':sum(c['game']=='palworld' for c in out),
        'priced':sum(bool(c.get('market')) for c in out),
        'pricedEUR':sum(c.get('marketEUR') is not None for c in out),
        'pricedAny':sum(bool(c.get('market')) or c.get('marketEUR') is not None for c in out),
        'imaged':sum(bool(c.get('image')) for c in out),
        'premium':sum(bool(c.get('isPremium')) for c in out),
        'sets':len(set_rows)
    }
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'modelVersion':'0.4-heuristic',
        'counts':counts,
        'sets':set_rows,
        'cards':out
    }
    DATA.mkdir(exist_ok=True)
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(counts)

if __name__=='__main__':main()
