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

def median(values):
    a=sorted(float(x) for x in values if x is not None and float(x)>0)
    if not a:return None
    n=len(a);m=n//2
    return a[m] if n%2 else (a[m-1]+a[m])/2

def observed_basis(c):
    # Never compare USD and EUR inside the same peer group.
    if c.get('marketEUR') is not None and float(c.get('marketEUR') or 0)>0:
        return float(c['marketEUR']),'EUR'
    if c.get('market') is not None and float(c.get('market') or 0)>0:
        return float(c['market']),'USD'
    return None,None

def attach_character_premium(cards):
    """Estimate collector/character premium relative to same-set, same-rarity peers.

    For each priced printing, compute price / median price of its rarity in that set
    and currency. Then aggregate those ratios across printings sharing the exact
    card/character name. This controls for rarity before estimating desirability.
    """
    peers=defaultdict(list)
    for c in cards:
        if c.get('availability')!='released':continue
        value,currency=observed_basis(c)
        rarity=str(c.get('rarity') or '').upper()
        if value and rarity:
            peers[(c.get('game'),c.get('set') or '',rarity,currency)].append(value)
    peer_medians={k:median(v) for k,v in peers.items() if len(v)>=3}

    families=defaultdict(list)
    for c in cards:
        value,currency=observed_basis(c)
        rarity=str(c.get('rarity') or '').upper()
        pmed=peer_medians.get((c.get('game'),c.get('set') or '',rarity,currency))
        if value and pmed:
            ratio=value/pmed
            # Winsorize thin-market extremes before family aggregation.
            ratio=max(.20,min(5.0,ratio))
            families[(c.get('game'),c.get('set') or '',str(c.get('name') or '').strip().lower())].append(ratio)

    for c in cards:
        key=(c.get('game'),c.get('set') or '',str(c.get('name') or '').strip().lower())
        ratios=families.get(key,[])
        ratio=median(ratios)
        n=len(ratios)
        if ratio is None:
            c['characterPremiumIndex']=None
            c['characterPremiumScore']=50
            c['characterPremiumObservations']=0
            c['characterPremiumConfidence']='None'
            continue
        idx=round(ratio*100)
        # 1.0 peer-relative = neutral score 50; 2x = 85; 0.5x = 15.
        score=clamp(50+35*math.log(ratio,2))
        c['characterPremiumIndex']=idx
        c['characterPremiumScore']=round(score)
        c['characterPremiumObservations']=n
        c['characterPremiumConfidence']='High' if n>=4 else ('Medium' if n>=2 else 'Low')
    return cards

def attach_market_pressure(cards):
    """Attach a current absorption proxy where completed-sales + fresh-ask data exist.

    This is deliberately NOT called historical HYPE. HYPE needs an own-card time
    baseline and will only be derived after enough daily snapshots accumulate.
    """
    measured=[]
    for c in cards:
        sales=c.get('salesInWindow')
        if sales is None:sales=c.get('salesInBasis')
        asks=c.get('marketAskCount')
        try:sales=float(sales) if sales is not None else None
        except:sales=None
        try:asks=float(asks) if asks is not None else None
        except:asks=None
        if sales is None or asks is None or sales+asks<=0:
            c['demandPressure']=None
            c['marketHeatPercentile']=None
            continue
        pressure=100*sales/(sales+asks)
        c['demandPressure']=round(pressure,1)
        c['demandPressureSales']=int(sales)
        c['demandPressureAsks']=int(asks)
        measured.append((pressure,c))
    if measured:
        ordered=sorted(measured,key=lambda x:x[0])
        n=len(ordered)
        for i,(pressure,c) in enumerate(ordered):
            # Mid-rank percentile; cross-sectional, not historical.
            c['marketHeatPercentile']=round(100*(i+.5)/n)
            c['marketHeatLabel']=('Hot' if c['marketHeatPercentile']>=80 else
                                  'Warm' if c['marketHeatPercentile']>=60 else
                                  'Neutral' if c['marketHeatPercentile']>=40 else
                                  'Cool' if c['marketHeatPercentile']>=20 else 'Cold')
    return cards

def stable(c):
    raw='|'.join(str(c.get(k) or '') for k in ('game','code','rarity','edition','treatment','availability'))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def prior_for(c,set_priors,game_priors):
    # Specific set prior wins over game prior.
    key=(c.get('set') or '').lower()
    found=next((v for k,v in set_priors.items() if k.lower() in key),None)
    return found or game_priors.get(c.get('game'),{})

def apply_market(c,tcgapi,palworldprices,manual_market,seed_market):
    code=str(c.get('code') or '')
    # Priority: explicit validated override > API cache > legacy seed.
    src=None
    if code in seed_market: src=seed_market[code]
    pwp=palworldprices.get(code)
    if pwp: src={**(src or {}),**pwp}
    api=tcgapi.get(code)
    if api and api.get('market') is not None: src={**(src or {}),**api}
    if code in manual_market: src={**(src or {}),**manual_market[code]}
    if not src:return c
    mapping={
      'market':'market','low':'marketLow','median':'marketMedian',
      'change24h':'change24h','change7d':'change7d','change30d':'change30d',
      'marketAsOf':'marketAsOf','salesVolume':'salesVolume','avgSalesPrice':'avgSalesPrice',
      'priceSource':'priceSource','printing':'marketPrinting','confidence':'marketConfidence',
      'marketKind':'marketKind','marketConfidence':'marketConfidence','marketQualifier':'marketQualifier',
      'marketSourceUrl':'marketSourceUrl','marketBasisWindow':'marketBasisWindow','marketEstimator':'marketEstimator',
      'marketMethod':'marketMethod','salesInBasis':'salesInBasis','salesInWindow':'salesInWindow',
      'marketAskCount':'marketAskCount','marketAskLow':'marketAskLow','marketAskMedian':'marketAskMedian',
      'marketAskSpreadPct':'marketAskSpreadPct','marketAskAsOf':'marketAskAsOf','marketStale':'marketStale',
      'palworldPricesCardId':'palworldPricesCardId'
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
    market_eur=float(c.get('marketEUR') or 0)
    d7=c.get('change7d');d30=c.get('change30d')
    momentum=clamp(50+(float(d7 or 0)*1.6)+(float(d30 or 0)*.45))
    p=prior_for(c,set_priors,game_priors)
    ip=float(p.get('ip',55));character=float(c.get('characterPremiumScore') or 50);reprint=float(p.get('reprint',55));historical=float(p.get('historical',50))
    treatment=float(c.get('treatmentScore') or (82 if rr>=86 else 55 if rr>=62 else 30))
    sold_n=float(c.get('salesInBasis') or 0)
    ask_n=float(c.get('marketAskCount') or 0)
    if sold_n:
        liquidity=clamp(28+18*math.log10(1+sold_n)+6*math.log10(1+ask_n))
    else:
        liquidity=clamp(35+math.log10(max(market,1))*10 if market else 25)
    edition_bonus=float(c.get('editionScore') or 50)
    investment=clamp(round(
        scarcity_score*.24 + ip*.10 + character*.10 + reprint*.13 + historical*.11 + treatment*.10 +
        liquidity*.07 + momentum*.10 + edition_bonus*.05
    ))
    fair_multiplier=1+(investment-58)/300+(momentum-50)/650
    fair=market*fair_multiplier if market else None
    fair_eur=market_eur*fair_multiplier if market_eur else None
    if c.get('availability')!='released':
        fair=None; fair_eur=None
    confidence=c.get('marketConfidence')
    if not confidence:
        confidence='High' if market and c.get('change30d') is not None and rr>=70 else ('Medium' if market else 'Low')
    c.update({
        'rarityRank':rr,'scarcityScore':scarcity_score,'scarcityEvidence':scarcity_note,
        'isPremium':str(c.get('rarity') or '').upper() in PREMIUM,
        'momentum':round(momentum),'investment':round(investment),
        'fair':round(fair,2) if fair else None,
        'fairEUR':round(fair_eur,2) if fair_eur else None,'confidence':confidence,
        'modelFactors':{
            'scarcity':round(scarcity_score),'ipStrength':round(ip),'characterPremium':round(character),'reprintDurability':round(reprint),
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
    palworldprices_file=read(MARKET/'palworldprices.json',{'cards':{}})
    palworldprices=palworldprices_file.get('cards',{})
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

        apply_market(c,tcgapi,palworldprices,market_overrides,seed_market)
        cm=cardmarket.get(code)
        if cm:
            for k,v in cm.items():
                if v is not None:c[k]=v
            c['cardmarketAsOf']=cardmarket_asof
            c['priceSourceEUR']='Cardmarket public daily price guide'
        c['priceSource']=c.get('priceSource') or 'Market enrichment pending'
        c['id']=stable(c)
        if c['id'] in seen:continue
        seen.add(c['id'])
        out.append(c)

    attach_character_premium(out)
    attach_market_pressure(out)
    out=[score(c,set_priors,game_priors,scarcity_evidence) for c in out]

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
        'modelVersion':'0.6-demand-pressure',
        'counts':counts,
        'sets':set_rows,
        'cards':out
    }
    DATA.mkdir(exist_ok=True)
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(counts)

if __name__=='__main__':main()
