#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math,re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from market_provenance import choose_usd_market, describe_usd_evidence, audit_manual_prices, combine_usd_guide_sources
from market_freshness import eur_evidence, audit_market_freshness

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

def collector_subject(c):
    """Best-effort collectible subject used only for market grouping."""
    name=str(c.get('name') or '').strip()
    if not name:return ''
    if c.get('game')=='palworld':
        for sep in (' – ',' - '):
            if sep in name:
                return name.split(sep,1)[0].strip()
        return name
    if str(c.get('cardType') or '').lower()=='character':
        if ',' in name:
            tail=name.rsplit(',',1)[1].strip()
            if tail:return tail
        m=re.match(r'^[“"][^”"]+[”"]\s*(.+)$',name)
        if m and m.group(1).strip():return m.group(1).strip()
    return name

def attach_character_premium(cards):
    """Describe subject demand after controlling for set, rarity and currency."""
    peers=defaultdict(list)
    for c in cards:
        c['collectorSubject']=collector_subject(c)
        if c.get('availability')!='released':continue
        value,currency=observed_basis(c)
        rarity=str(c.get('rarity') or '').upper()
        if value and rarity:
            peers[(c.get('game'),c.get('set') or '',rarity,currency)].append((c.get('id'),value))

    ratios_by_subject=defaultdict(list)
    for c in cards:
        value,currency=observed_basis(c)
        rarity=str(c.get('rarity') or '').upper()
        if not value or not rarity:continue
        rows=peers.get((c.get('game'),c.get('set') or '',rarity,currency),[])
        others=[v for cid,v in rows if cid!=c.get('id')]
        pmed=median(others)
        if pmed is None or len(others)<2:continue
        ratio=max(.20,min(5.0,value/pmed))
        c['_marketPeerRatio']=ratio
        c['_marketPeerCurrency']=currency
        c['_marketPeerMedian']=round(pmed,4)
        c['_marketPeerCount']=len(others)
        key=(c.get('game'),c.get('set') or '',c.get('collectorSubject') or '',currency)
        ratios_by_subject[key].append((c.get('id'),ratio))

    for c in cards:
        _,observed_currency=observed_basis(c)
        currency=observed_currency or ('EUR' if c.get('game')=='weiss' else 'USD')
        key=(c.get('game'),c.get('set') or '',c.get('collectorSubject') or '',currency)
        rows=ratios_by_subject.get(key,[])
        ratios=[ratio for _,ratio in rows]
        ratio=median(ratios)
        n=len(ratios)
        if ratio is None:
            c['characterPremiumIndex']=None
            c['characterPremiumScore']=50
            c['characterPremiumObservations']=0
            c['characterPremiumConfidence']='None'
            continue
        c['characterPremiumIndex']=round(ratio*100)
        c['characterPremiumScore']=round(clamp(50+35*math.log(ratio,2)))
        c['characterPremiumObservations']=n
        c['characterPremiumConfidence']='High' if n>=4 else ('Medium' if n>=2 else 'Low')
    return cards

def attach_peer_fair_value(cards):
    """Leave-target-out peer estimate, including every subject-ratio denominator.

    Previously the target was excluded from the *direct* rarity median but
    still entered the precomputed subject-ratio denominator of other cards
    in the same rarity cohort. This indirectly leaked the target's observed
    price into its own forecast and inflated retrospective skill.
    """
    peers=defaultdict(list)
    subject_rows=defaultdict(list)
    for c in cards:
        if c.get('availability')!='released':
            continue
        value,currency=observed_basis(c)
        rarity=str(c.get('rarity') or '').upper()
        if value is None or not currency or not rarity:
            continue
        cohort=(c.get('game'),c.get('set') or '',rarity,currency)
        peers[cohort].append((c.get('id'),value))
        # Keep source price for re-normalizing the *other* subject cards with
        # both target and subject card held out of the rarity baseline.
        subject=(c.get('game'),c.get('set') or '',
                 c.get('collectorSubject') or '',currency)
        subject_rows[subject].append((c.get('id'),rarity,value,
                                      c.get('_marketPeerRatio')))

    for c in cards:
        if c.get('availability')!='released':
            c['fairValueConfidence']='None'
            continue
        _,current_currency=observed_basis(c)
        candidate_currencies=[current_currency] if current_currency else (
            ['EUR','USD'] if c.get('game')=='weiss' else ['USD','EUR'])
        predicted=None
        for currency in candidate_currencies:
            if not currency:
                continue
            rarity=str(c.get('rarity') or '').upper()
            cohort=(c.get('game'),c.get('set') or '',rarity,currency)
            rows=peers.get(cohort,[])
            peer_values=[v for cid,v in rows if cid!=c.get('id')]
            peer_med=median(peer_values)
            if peer_med is None or len(peer_values)<3:
                continue
            subject=(c.get('game'),c.get('set') or '',
                     c.get('collectorSubject') or '',currency)
            family_ratios=[]
            for peer_id,peer_rarity,peer_price,existing_ratio in subject_rows.get(subject,[]):
                if peer_id==c.get('id'):
                    continue
                if peer_rarity==rarity:
                    # The other card's precomputed ratio used the target in its
                    # denominator. Recompute excluding BOTH card IDs, so the
                    # target price cannot change its own prediction indirectly.
                    independent=[v for cid,v in rows
                                 if cid!=c.get('id') and cid!=peer_id]
                    independent_med=median(independent)
                    if independent_med is None or len(independent)<2:
                        continue
                    ratio=max(.20,min(5.0,peer_price/independent_med))
                else:
                    # This peer uses a different rarity cohort; target never
                    # occurred in its precomputed denominator.
                    if existing_ratio is None:
                        continue
                    ratio=existing_ratio
                family_ratios.append(ratio)
            subject_ratio=median(family_ratios)
            if subject_ratio is None:
                continue
            predicted=peer_med*subject_ratio
            c['fairValueMethod']='target-independent rarity peer × subject premium'
            c['fairValueCurrency']=currency
            c['fairValuePeerMedian']=round(peer_med,2)
            c['fairValuePeerCount']=len(peer_values)
            c['fairValueSubjectRatio']=round(subject_ratio,3)
            c['fairValueSubjectObservations']=len(family_ratios)
            # These bands only describe sample sizes; they do NOT assert
            # prediction accuracy or reliable completed-sale observations.
            c['fairValueConfidenceBasis']='peer sample size, not predictive accuracy'
            c['fairValueDataBasis']=(
                'EUR provider price guides (not completed sales)'
                if currency=='EUR' else
                'USD mixed provider prices (sale provenance varies)'
            )
            if len(peer_values)>=8 and len(family_ratios)>=3:
                c['fairValueConfidence']='High'
            elif len(peer_values)>=4 and len(family_ratios)>=2:
                c['fairValueConfidence']='Medium'
            else:
                c['fairValueConfidence']='Low'
            if currency=='EUR':
                c['peerFairEUR']=round(predicted,2)
            else:
                c['peerFairUSD']=round(predicted,2)
            break
        if predicted is None:
            c['fairValueConfidence']='None'
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

def apply_market(c,price_sources,palworldprices,manual_market,seed_market):
    code=str(c.get('code') or '')
    source, indication = choose_usd_market(
        code, price_sources, palworldprices, manual_market, seed_market
    )
    c.update(indication)
    if source is None:
        return c
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
      'palworldPricesCardId':'palworldPricesCardId',
      'palworldSourceVariant':'palworldSourceVariant',
      'palworldMatch':'palworldMatch',
      'marketSelectionReason':'marketSelectionReason',
      'marketRetrievedAt':'marketRetrievedAt','checkedAt':'marketRetrievedAt',
      'marketSubtype':'marketSubtype','marketSubtypeSelection':'marketSubtypeSelection',
      'tcgcsvMatch':'tcgcsvMatch','tcgplayerProductId':'tcgplayerProductId'
    }
    for a,b in mapping.items():
        if source.get(a) is not None:
            c[b] = source[a]
    c.update(describe_usd_evidence(source))
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
    fair=c.get('peerFairUSD')
    fair_eur=c.get('peerFairEUR')
    if c.get('availability')!='released':
        fair=None; fair_eur=None
    confidence=c.get('marketConfidence')
    if not confidence:
        observed=bool(market or market_eur)
        confidence='High' if observed and c.get('change30d') is not None and rr>=70 else ('Medium' if observed else 'Low')
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
        'modelStatus':'peer-fair-v0.8-true-loo'
    })
    return c

def main():
    seed=read(DATA/'seed.json',{'cards':[]})
    wi=read(RAW/'weiss.json',{'cards':[]})
    pa=read(RAW/'palworld.json',{'cards':[]})
    manual=read(DATA/'manual_overrides.json',{})
    printing=read(DATA/'printing_overrides.json',{'cards':{}}).get('cards',{})
    market_file=read(DATA/'market_overrides.json',{'cards':{}})
    market_overrides=market_file.get('cards',{})
    tcgcsv_file=read(MARKET/'tcgcsv.json',{'cards':{}})
    tcgcsv=tcgcsv_file.get('cards',{})
    tcgapi_file=read(MARKET/'tcgapi.json',{'cards':{}})
    tcgapi=tcgapi_file.get('cards',{})
    # Optional authenticated data is NOT trusted by its mere presence in
    # the local cache. It must meet the exact printed-identity, foil, and
    # upstream publication-date gate before replacing a TCGCSV guide.
    usd_market,tcgapi_guide_audit=combine_usd_guide_sources(tcgcsv,tcgapi)
    tcgapi_guide_audit['status']=(
        'not-configured-no-price-cache' if not tcgapi else
        'source-qualified-selections' if tcgapi_guide_audit['tcgapiQualifiedSelections'] else
        'no-qualified-selections-or-legacy-cache'
    )
    tcgapi_guide_audit['cacheGeneratedAt']=tcgapi_file.get('generatedAt')
    palworldprices_file=read(MARKET/'palworldprices.json',{'cards':{}})
    palworldprices=palworldprices_file.get('cards',{})
    cardmarket_file=read(MARKET/'cardmarket.json',{'cards':{}})
    cardmarket=cardmarket_file.get('cards',{})
    # Only the provider's guide publication date can be treated as the date
    # of its market price. generatedAt is our cache-fetch time, not a price date.
    cardmarket_asof=cardmarket_file.get('cardmarketCreatedAt')
    cardmarket_retrieved_at=cardmarket_file.get('generatedAt')
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
        c['language']=c.get('language') or 'EN'
        c['availability']=c.get('availability') or 'released'

        # Versioned physical-printing metadata can override generic catalog data.
        ov=printing.get(code)
        if ov:
            for k,v in ov.items():
                if v is not None:c[k]=v

        apply_market(c,usd_market,palworldprices,market_overrides,seed_market)
        cm=cardmarket.get(code)
        if cm:
            for k,v in cm.items():
                if v is not None:c[k]=v
            if cm.get('marketEUR') is not None:
                c['cardmarketAsOf']=cardmarket_asof
                c['priceSourceEUR']='Cardmarket public daily price guide'
                c.update(eur_evidence(cardmarket_asof, cardmarket_retrieved_at))
        c['priceSource']=c.get('priceSource') or 'Market enrichment pending'
        c['id']=stable(c)
        if c['id'] in seen:continue
        seen.add(c['id'])
        out.append(c)

    attach_character_premium(out)
    attach_peer_fair_value(out)
    attach_market_pressure(out)
    out=[score(c,set_priors,game_priors,scarcity_evidence) for c in out]

    out.sort(key=lambda c:(c['game'],c.get('availability')!='released',c.get('set') or '',c.get('code') or ''))

    groups=defaultdict(list)
    for c in out:
        groups[(c['game'],c.get('language') or 'EN',c.get('set') or 'Unknown')].append(c)
    set_rows=[]
    for (game,language,name),cards in groups.items():
        released=[c for c in cards if c.get('availability')=='released']
        priced=[c for c in released if c.get('market')]
        priced_eur=[c for c in released if c.get('marketEUR') is not None]
        priced_any=[c for c in released if c.get('market') or c.get('marketEUR') is not None]
        premiums=[c for c in released if c.get('isPremium')]
        set_rows.append({
            'game':game,'language':language,'name':name,'total':len(cards),'released':len(released),
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
        'weissEN':sum(c['game']=='weiss' and c.get('language')=='EN' for c in out),
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
        'modelVersion':'0.8-peer-fair-true-leave-one-out',
        'counts':counts,
        'sets':set_rows,
        'cards':out
    }
    DATA.mkdir(exist_ok=True)
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    # Preserve data-source matching provenance separately from EUR price count.
    # A pre-fix cached file may still exist until the next network refresh;
    # in that case the UI must state that duplicate collisions were NOT checked.
    cm_stats=cardmarket_file.get('stats',{})
    cm_vetted='collisionCodeGroups' in cm_stats
    cm_rows=cardmarket_file.get('cards',{})
    cm_audit={
        'schemaVersion':1,
        'status':'vetted-identity-matching-v1' if cm_vetted else 'legacy-cache-unverified-mapping',
        'priceGuideCreatedAt':cardmarket_file.get('cardmarketCreatedAt'),
        'cacheRetrievedAt':cardmarket_file.get('generatedAt'),
        'matchedPrintings':len(cm_rows),
        'pricedPrintings':sum(
            isinstance(row,dict) and row.get('marketEUR') is not None
            and isinstance(row['marketEUR'],(int,float)) and row['marketEUR']>0
            for row in cm_rows.values()
        ),
        'sourceStats':cm_stats,
        'note':(
            'Explicit collector code and rarity mismatches are rejected; '
            'colliding product IDs are quarantined only after the new '
            'Cardmarket source matcher has successfully refreshed. '
            'Cached legacy records are NOT retroactively certified.'
        )
    }
    (DATA/'cardmarket-match-audit.json').write_text(
        json.dumps(cm_audit,ensure_ascii=False,indent=2),encoding='utf-8'
    )
    print('Cardmarket match audit',cm_audit['status'],
          'priced',cm_audit['pricedPrintings'],
          'collided groups',cm_stats.get('collisionCodeGroups','not checked'))
    tcg_stats=tcgcsv_file.get('stats',{})
    vetted='subtypeSelection' in tcg_stats and 'collisionCodeGroups' in tcg_stats
    tcg_audit={
        'schemaVersion':1,
        'status':'vetted-subtype-matching-v1' if vetted else 'legacy-cache-unverified-subtypes',
        'retrievedAt':tcgcsv_file.get('generatedAt'),
        'matchedPrintings':len(tcgcsv),
        'sourceStats':tcg_stats,
        'note':(
            'Normal and Foil selections require rarity-aware product subtype data. '
            'Only one unspecified subtype is provisional; conflicting vendor '
            'products for a collector number are excluded. Older cached records '
            'are not retroactively validated.'
        )
    }
    (DATA/'tcgcsv-subtype-audit.json').write_text(
        json.dumps(tcg_audit,indent=2,ensure_ascii=False),encoding='utf-8'
    )
    print('TCGCSV subtype integrity audit',tcg_audit['status'],
          'matched',tcg_audit['matchedPrintings'])
    palworld_source_stats=palworldprices_file.get('stats',{})
    palworld_audit={
        'schemaVersion':1,
        'status':(
            'exact-printing-cardid-v1'
            if palworld_source_stats.get('identityMethod')==
               'exact-source-cardId-and-explicit-variant'
            else 'legacy-provider-cache-not-variant-audited'
        ),
        'cacheRetrievedAt':palworldprices_file.get('generatedAt'),
        'priceSourceAsOf':palworldprices_file.get('asOf'),
        'sourceStale':palworldprices_file.get('stale'),
        'matchedPrintings':len(palworldprices),
        'pricedPrintings':sum(
            isinstance(v,dict) and isinstance(v.get('market'),(int,float))
            and v['market']>0
            for v in palworldprices.values()
        ),
        'sourceStats':palworld_source_stats,
        'notice':(
            'Palworld Prices completed-sale estimates are only assigned to '
            'printings with an exact API cardId/code/explicit variant match. '
            'Older provider caches cannot be retroactively certified.'
        ),
    }
    (DATA/'palworld-identity-audit.json').write_text(
        json.dumps(palworld_audit,ensure_ascii=False,indent=2),encoding='utf-8'
    )
    print('Palworld source-identity audit',palworld_audit['status'],
          'priced',palworld_audit['pricedPrintings'])
    (DATA/'tcgapi-identity-audit.json').write_text(
        json.dumps(tcgapi_guide_audit,indent=2,ensure_ascii=False),
        encoding='utf-8'
    )
    print('Optional TCG API premium identity audit',
          tcgapi_guide_audit['status'],
          tcgapi_guide_audit['tcgapiQualifiedSelections'])
    source_audit=audit_manual_prices(market_overrides)
    source_audit['generatedAt']=payload['generatedAt']
    (DATA/'market-source-audit.json').write_text(json.dumps(source_audit,indent=2),encoding='utf-8')
    freshness=audit_market_freshness(out, generated_at=payload['generatedAt'])
    (DATA/'market-freshness-audit.json').write_text(
        json.dumps(freshness,indent=2,ensure_ascii=False),encoding='utf-8'
    )
    print('market freshness audit',freshness['currencies'])
    print('market source audit',source_audit)
    print(counts)

if __name__=='__main__':main()
