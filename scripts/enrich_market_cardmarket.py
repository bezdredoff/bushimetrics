#!/usr/bin/env python3
"""Best-effort EUR market enrichment from Cardmarket's public daily downloads.

Cardmarket publishes per-game product catalogs and price guides without API
credentials. Weiss Schwarz is Cardmarket game id 10.

Important: Cardmarket stopped adding NEW Weiss singles in 2026, so this is a
partial European market layer, never the master card catalog.

Matching is deliberately evidence-gated:
1) exact collector number (never fall back if an explicit number disagrees);
2) unique name with all supplied rarity and set constraints;
3) quarantine ambiguous products and collisions instead of overwriting values.
Unannotated name-only guides are allowed only for globally unique, ordinary (non-premium) printings and remain explicitly labeled source-treatment-unverified.

Cardmarket's public export includes expansionName. Using it resolves many false
ambiguities where the same card title exists in multiple Weiss products.

Ambiguous rows are skipped rather than attached to the wrong printing.
"""
from __future__ import annotations
import json,math,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WEISS=ROOT/'data/raw/weiss.json'
OUT=ROOT/'data/market/cardmarket.json'
PRODUCTS_URL='https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_10.json'
PRICES_URL='https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_10.json'
UA='BushiMetrics/0.4 (+https://github.com/bezdredoff/bushimetrics)'

RARITY_WORDS={
 'common':'C','uncommon':'U','rare':'R','double rare':'RR','triple rare':'RRR',
 'super rare':'SR','special rare':'SP','special':'SP','super special rare':'SSP',
 'super special':'SSP','secret rare':'SEC','secret':'SEC','over frame rare':'OFR',
}
VERSION_RE=re.compile(r'\s*\(V\.\d+(?:\s*-\s*([^)]*))?\)\s*',re.I)
PARENS_RARITY_RE=re.compile(r'\s*\(([^()]*(?:rare|special|secret|foil|signed)[^()]*)\)\s*$',re.I)

def norm(s):
    s=unicodedata.normalize('NFKC',str(s or '')).lower()
    s=s.replace('“','"').replace('”','"').replace('’',"'").replace('–','-').replace('—','-')
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(s.split())

def canon_rarity(value):
    v=norm(value)
    if not v:return None
    for name,code in sorted(RARITY_WORDS.items(),key=lambda kv:len(kv[0]),reverse=True):
        if name in v:return code
    raw=str(value).strip().upper()
    return raw if raw in {'C','U','R','RR','RRR','SR','SP','SSP','SEC','SEC+','OFR','PR'} else None

def set_norm(value):
    s=norm(value)
    # Remove packaging/product boilerplate but keep franchise/volume semantics.
    s=re.sub(r'\b(booster pack|trial deck\+?|trial deck|extra booster|premium booster|weiss schwarz)\b',' ',s)
    return ' '.join(s.split())

def product_identity(p):
    raw=str(p.get('name') or '')
    rarity=canon_rarity(p.get('rarity'))
    versions=VERSION_RE.findall(raw)
    if versions:
        for v in versions:
            rarity=rarity or canon_rarity(v)
        raw=VERSION_RE.sub(' ',raw)
    m=PARENS_RARITY_RE.search(raw)
    if m:
        rarity=rarity or canon_rarity(m.group(1)); raw=raw[:m.start()]
    number=str(p.get('number') or p.get('collectorNumber') or '').strip()
    expansion=str(p.get('expansionName') or p.get('expansion') or '').strip()
    return norm(raw),rarity,number,set_norm(expansion)

def get_json(session,url):
    r=session.get(url,headers={'User-Agent':UA},timeout=180)
    r.raise_for_status()
    return r.json()

def normalized_code(value):
    """Do not conflate two physical products merely by a similar name."""
    return re.sub(r'\s+', '', str(value or '')).upper()


def positive_price(value):
    try:
        number=float(value)
        return math.isfinite(number) and number>0
    except (TypeError,ValueError,OverflowError):
        return False


def compatible_expansion(card, expansion):
    name=set_norm(card.get('set'))
    # Very short/shared fragments are insufficient to identify a product.
    return bool(name and expansion and (
        name==expansion or
        (min(len(name),len(expansion))>=6 and (
            name in expansion or expansion in name
        ))
    ))


def match_cardmarket(cards, products, guides, *, max_examples=40):
    """Map price guides only to unambiguous physical printings.

    * A specified collector number is authoritative: if absent from our
      catalog, or if specified rarity disagrees, NEVER retry name matching.
    * Name fallback must respect every rarity and expansion constraint that
      the source actually supplies.
    * Multiple distinct Cardmarket product IDs for one catalog code are
      quarantined, not overwritten by source enumeration order.
    """
    by_code=defaultdict(list)
    by_name=defaultdict(list)
    for card in cards:
        if card.get('code'):
            by_code[normalized_code(card['code'])].append(card)
        name=norm(card.get('name'))
        if name:
            by_name[name].append(card)

    by_product={}
    for row in guides:
        try:
            pid=int(row['idProduct'])
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
        by_product[pid]=row

    accepted=defaultdict(dict)
    stats={
        'catalogCards':len(cards),
        'publishedProducts':len(products),
        'priceRows':len(guides),
        'productsWithoutPrice':0,
        'invalidPriceRows':0,
        'explicitNumberNotFound':0,
        'explicitNumberAmbiguous':0,
        'explicitRarityConflict':0,
        'insufficientIdentity':0,
        'unmatchedProducts':0,
        'ambiguousProducts':0,
        'duplicateSourceRows':0,
        'candidateProducts':0,
        'collisionCodeGroups':0,
        'collisionProducts':0,
        'collisionExamples':[],
        'rejectionExamples':[],
    }
    seen_products=set()

    def reject(reason, product, number, rarity, expansion):
        stats[reason]+=1
        if len(stats['rejectionExamples'])<max_examples:
            stats['rejectionExamples'].append({
                'reason':reason,
                'cardmarketProductId':product.get('idProduct'),
                'name':product.get('name'),
                'number':number,
                'rarity':rarity,
                'expansion':expansion,
            })

    for product in products:
        try:
            pid=int(product['idProduct'])
        except (KeyError,TypeError,ValueError,OverflowError):
            stats['unmatchedProducts']+=1
            continue
        if pid in seen_products:
            stats['duplicateSourceRows']+=1
            continue
        seen_products.add(pid)
        guide=by_product.get(pid)
        if guide is None:
            stats['productsWithoutPrice']+=1
            continue
        if not positive_price(guide.get('trend')):
            stats['invalidPriceRows']+=1
            continue

        name,rarity,number,expansion=product_identity(product)
        candidate=None
        method=None
        if number:
            matches=by_code.get(normalized_code(number),[])
            if not matches:
                reject('explicitNumberNotFound',product,number,rarity,expansion)
                continue
            if len(matches)!=1:
                reject('explicitNumberAmbiguous',product,number,rarity,expansion)
                continue
            candidate=matches[0]
            if rarity is not None and str(candidate.get('rarity') or '').upper()!=rarity:
                reject('explicitRarityConflict',product,number,rarity,expansion)
                continue
            method='verified-collector-number'+('-rarity' if rarity else '')
        else:
            if not name:
                reject('insufficientIdentity',product,number,rarity,expansion)
                continue
            matches=by_name.get(name,[])
            if not rarity and not expansion:
                # Cardmarket's real public Weiss product export generally omits
                # ALL of code, rarity and expansion. A globally unique normal
                # printing is a usable *indicative guide* only; refuse premium
                # cards, known V.2 parallels and merchandising foil/signed tags.
                base={'C','U','R','RR','CC','CR','N','TD'}
                raw_name=str(product.get('name') or '')
                suspect=bool(VERSION_RE.search(raw_name)) or bool(
                    re.search(r'\b(foil|signed|serialized|parallel|alt[ -]?art)\b',
                              raw_name,re.I)
                )
                if len(matches)!=1 or str(matches[0].get('rarity') or '').upper() not in base or suspect:
                    reject('insufficientIdentity',product,number,rarity,expansion)
                    continue
                candidate=matches[0]
                method='unique-normal-name-unverified-source-treatment'
            else:
                if rarity:
                    matches=[card for card in matches if str(card.get('rarity') or '').upper()==rarity]
                if expansion:
                    matches=[card for card in matches if compatible_expansion(card,expansion)]
                if not matches:
                    reject('unmatchedProducts',product,number,rarity,expansion)
                    continue
                if len(matches)>1:
                    reject('ambiguousProducts',product,number,rarity,expansion)
                    continue
                candidate=matches[0]
                method=('unique-name'+('-rarity' if rarity else '')+
                        ('-compatible-expansion' if expansion else ''))
        if not candidate:
            raise AssertionError('Internal matching error: no candidate')
        code=candidate['code']
        def val(*keys):
            for key in keys:
                if guide.get(key) not in (None,''):
                    return guide[key]
            return None
        accepted[code][pid]={
            'cardmarketProductId':pid,
            'marketEUR':val('trend'),
            'marketEURLow':val('low'),
            'marketEURAvg':val('avg'),
            'marketEURAvg1':val('avg1'),
            'marketEURAvg7':val('avg7'),
            'marketEURAvg30':val('avg30'),
            'cardmarketMatch':method,
            'cardmarketProductName':product.get('name'),
            'cardmarketCategory':product.get('categoryName'),
            'cardmarketExpansionId':product.get('idExpansion'),
            'cardmarketExpansionName':product.get('expansionName'),
        }
        stats['candidateProducts']+=1

    matched={}
    methods=defaultdict(int)
    for code,variants in sorted(accepted.items()):
        if len(variants)>1:
            stats['collisionCodeGroups']+=1
            stats['collisionProducts']+=len(variants)
            if len(stats['collisionExamples'])<max_examples:
                stats['collisionExamples'].append({
                    'collectorCode':code,
                    'productIds':sorted(variants),
                    'matchMethods':[variants[pid]['cardmarketMatch']
                                    for pid in sorted(variants)],
                })
            continue
        chosen=next(iter(variants.values()))
        matched[code]=chosen
        methods[chosen['cardmarketMatch']]+=1

    stats['matchedCards']=len(matched)
    stats['matchMethods']=dict(sorted(methods.items()))
    stats['rejectedProductRows']=sum(
        stats[key] for key in (
            'explicitNumberNotFound','explicitNumberAmbiguous',
            'explicitRarityConflict','insufficientIdentity',
            'unmatchedProducts','ambiguousProducts',
        )
    )
    stats['notes']=[
        'A Cardmarket trend value is a price guide, not a verified completed sale.',
        'Explicit collector numbers that do not match this catalog never fall back to title.',
        'Rarity and expansion constraints are not silently discarded on name fallback.',
        'When Cardmarket omits all code/rarity/set fields, unique normal printing title is indicative only; rare treatments and multiple printings are excluded.',
        'All distinct product collisions for one collector code are quarantined.',
        'Absent entries have unknown price; neither zero nor a substitute asking price.',
    ]
    return matched,stats


def main():
    if not WEISS.exists():
        print('Weiss catalog missing; Cardmarket enrichment skipped.')
        return
    source=json.loads(WEISS.read_text(encoding='utf-8'))
    cards=source.get('cards',[])
    import requests
    session=requests.Session()
    try:
        products_file=get_json(session,PRODUCTS_URL)
        prices_file=get_json(session,PRICES_URL)
    except Exception as exc:
        if OUT.exists():
            print('Cardmarket download failed; keeping prior cache:',exc)
            return
        print('Cardmarket unavailable and no prior cache:',exc)
        return

    products=products_file.get('products') or []
    guides=prices_file.get('priceGuides') or []
    matched,stats=match_cardmarket(cards,products,guides)
    # Prevent a changed provider format from wiping the established EUR market
    # on the next scheduled refresh. The explicit audit examples explain drops.
    minimum=max(100,int(len(cards)*0.02))
    if len(matched)<minimum:
        raise RuntimeError(
            f'Cardmarket matched only {len(matched)} of {len(cards)} cards '
            f'(min {minimum} to publish). Investigate source/matcher and '
            f'leave existing cached market file unchanged. '
            f'Matched={len(matched)}, unique title restrictions and collisions require review.'
        )
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'cardmarketCreatedAt':prices_file.get('createdAt'),
        'productsCreatedAt':products_file.get('createdAt'),
        'source':{'products':PRODUCTS_URL,'prices':PRICES_URL,'gameId':10},
        'stats':stats,
        'cards':matched,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Cardmarket unambiguous matches',len(matched),'of',len(cards),
          'Weiss cards; collision groups',stats['collisionCodeGroups'],
          'rejected rows',stats['rejectedProductRows'])


if __name__=='__main__':
    main()
