#!/usr/bin/env python3
"""Best-effort EUR market enrichment from Cardmarket's public daily downloads.

Cardmarket publishes per-game product catalogs and price guides without API
credentials. Weiss Schwarz is Cardmarket game id 10.

Important: Cardmarket stopped adding NEW Weiss singles in 2026, so this is a
partial European market layer, never the master card catalog.

Matching is deliberately conservative:
1) collector number, if the published product row exposes one;
2) unique (normalized card name, rarity, expansion) among our Weiss catalog;
3) unique (normalized card name, expansion);
4) unique (normalized card name, rarity);
5) unique normalized name only.

Cardmarket's public export includes expansionName. Using it resolves many false
ambiguities where the same card title exists in multiple Weiss products.

Ambiguous rows are skipped rather than attached to the wrong printing.
"""
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
import requests

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

def main():
    if not WEISS.exists():
        print('Weiss catalog missing; Cardmarket enrichment skipped.')
        return
    source=json.loads(WEISS.read_text(encoding='utf-8'))
    cards=source.get('cards',[])
    by_code={str(c.get('code') or '').upper():c for c in cards if c.get('code')}
    by_name={}
    by_name_rarity={}
    by_name_set={}
    by_name_rarity_set={}
    for c in cards:
        n=norm(c.get('name')); r=str(c.get('rarity') or '').upper(); st=set_norm(c.get('set'))
        if not n:continue
        by_name.setdefault(n,[]).append(c)
        by_name_rarity.setdefault((n,r),[]).append(c)
        if st:
            by_name_set.setdefault((n,st),[]).append(c)
            by_name_rarity_set.setdefault((n,r,st),[]).append(c)

    def expansion_candidates(name, rarity, expansion):
        """Conservative fallback when set strings differ only by light naming boilerplate."""
        if not expansion:return []
        pool=by_name_rarity.get((name,rarity),[]) if rarity else by_name.get(name,[])
        out=[]
        for c in pool:
            st=set_norm(c.get('set'))
            if not st:continue
            if st==expansion or st in expansion or expansion in st:
                out.append(c)
        return out

    session=requests.Session()
    try:
        products_file=get_json(session,PRODUCTS_URL)
        prices_file=get_json(session,PRICES_URL)
    except Exception as e:
        if OUT.exists():
            print('Cardmarket download failed; keeping prior cache:',e)
            return
        print('Cardmarket unavailable and no prior cache:',e)
        return

    products=products_file.get('products') or []
    guides=prices_file.get('priceGuides') or []
    by_product={int(g.get('idProduct')):g for g in guides if g.get('idProduct') is not None}

    matched={}; ambiguous=0; no_price=0; no_match=0
    methods={}; ambiguous_examples=[]
    for p in products:
        pid=p.get('idProduct')
        if pid is None:continue
        guide=by_product.get(int(pid))
        if not guide:
            no_price+=1;continue
        n,r,number,expansion=product_identity(p)
        candidate=None;method=None
        if number and number.upper() in by_code:
            candidate=by_code[number.upper()];method='collector-number'
        elif r and expansion and len(by_name_rarity_set.get((n,r,expansion),[]))==1:
            candidate=by_name_rarity_set[(n,r,expansion)][0];method='unique-name-rarity-expansion'
        elif expansion and len(by_name_set.get((n,expansion),[]))==1:
            candidate=by_name_set[(n,expansion)][0];method='unique-name-expansion'
        else:
            ex=expansion_candidates(n,r,expansion)
            if len(ex)==1:
                candidate=ex[0];method='compatible-expansion'
            elif r and len(by_name_rarity.get((n,r),[]))==1:
                candidate=by_name_rarity[(n,r)][0];method='unique-name-rarity'
            elif len(by_name.get(n,[]))==1:
                candidate=by_name[n][0];method='unique-name'
            else:
                if n in by_name:
                    ambiguous+=1
                    if len(ambiguous_examples)<30:
                        ambiguous_examples.append({'product':p.get('name'),'rarity':p.get('rarity'),'expansion':p.get('expansionName'),'number':number,'catalogCandidates':len(by_name.get(n,[]))})
                else:no_match+=1
                continue

        def val(*keys):
            for k in keys:
                if guide.get(k) not in (None,''):return guide.get(k)
            return None
        methods[method]=methods.get(method,0)+1
        matched[candidate['code']]={
            'cardmarketProductId':int(pid),
            'marketEUR':val('trend'),
            'marketEURLow':val('low'),
            'marketEURAvg':val('avg'),
            'marketEURAvg1':val('avg1'),
            'marketEURAvg7':val('avg7'),
            'marketEURAvg30':val('avg30'),
            'cardmarketMatch':method,
            'cardmarketProductName':p.get('name'),
            'cardmarketCategory':p.get('categoryName'),
            'cardmarketExpansionId':p.get('idExpansion'),
            'cardmarketExpansionName':p.get('expansionName')
        }

    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'cardmarketCreatedAt':prices_file.get('createdAt'),
        'productsCreatedAt':products_file.get('createdAt'),
        'source':{'products':PRODUCTS_URL,'prices':PRICES_URL,'gameId':10},
        'stats':{
            'catalogCards':len(cards),'publishedProducts':len(products),'priceRows':len(guides),
            'matchedCards':len(matched),'ambiguousProducts':ambiguous,
            'productsWithoutPrice':no_price,'unmatchedProducts':no_match,
            'matchMethods':methods,'ambiguousExamples':ambiguous_examples
        },
        'cards':matched
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Cardmarket matched',len(matched),'of',len(cards),'Weiss cards;',payload['stats'])

if __name__=='__main__':main()
