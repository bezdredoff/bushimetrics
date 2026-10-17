#!/usr/bin/env python3
"""Build set-sharded browser payloads for GitHub Pages.

Research data stays in data/catalog.json and data/catalog-weiss-jp.json.
The browser gets:
  data/web/bootstrap.json          tiny first paint with real cards
  data/web/manifest.json           set metadata + set file paths
  data/web/search-en.json          lightweight global EN search/sort index
  data/web/search-jp.json          lightweight JP index, loaded only on demand
  data/web/sets/<lang>/<set>.json  one payload per set

This keeps the UI responsive and makes each set independently cacheable/debuggable.
"""
from __future__ import annotations
import hashlib,json,re,shutil
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; OUT=DATA/'web'; SETS=OUT/'sets'

SEARCH_FIELDS={
    'id':'i','game':'g','language':'l','availability':'a','name':'n','set':'s',
    'code':'c','rarity':'r','marketEUR':'me','market':'mu','fairEUR':'fe','fair':'fu',
    'investment':'iq','momentum':'mo','isPremium':'p','rarityRank':'rr',
    'marketHeatPercentile':'hp','characterPremiumIndex':'cp',
    'characterPremiumObservations':'co','marketKind':'mk','marketConfidence':'mc',
    'marketEvidenceStatus':'es','marketObservationAgeDays':'ea',
    'marketIdentityStatus':'ms','tcgapiCardId':'ti',
    'palworldMatch':'pm','palworldPricesCardId':'pi',
    'palworldSourceVariant':'pv','marketSelectionReason':'mr',
    'marketStale':'st','unverifiedMarketIndicationUSD':'ui',
    'marketAsOf':'ma','cardmarketAsOf':'ca',
    'marketEURAgeDays':'eg','marketEURStale':'et',
    'marketEURDateStatus':'ed','cardmarketMatch':'cm',
    'confidence':'cf','fairValueConfidence':'fc','change7d':'d7','change30d':'d30',
    'demandPressure':'dp','cardType':'ct','color':'cl'
}
BOOT_EXTRA={'image':'im','priceSource':'ps','priceSourceEUR':'pe','marketSourceUrl':'su','marketRetrievedAt':'mt'}

def slug(s):
    base=re.sub(r'[^a-z0-9]+','-',str(s or 'set').lower()).strip('-')[:72] or 'set'
    h=hashlib.sha1(str(s or '').encode()).hexdigest()[:8]
    return f'{base}-{h}'

def compact(row,extra=False,set_key=None):
    out={'k':set_key} if set_key else {}
    for src,dst in SEARCH_FIELDS.items():
        v=row.get(src)
        if v is not None and v!='':out[dst]=v
    if extra:
        for src,dst in BOOT_EXTRA.items():
            v=row.get(src)
            if v is not None and v!='':out[dst]=v
    return out

def jp_search(row,set_key):
    out={'i':row.get('id'),'g':'weiss','l':'JP','a':'released','k':set_key,
         'n':row.get('n'),'s':row.get('s'),'c':row.get('c'),'r':row.get('r'),
         'iq':row.get('iq'),'rr':row.get('rr')}
    if row.get('p'):out['p']=1
    return {k:v for k,v in out.items() if v is not None and v!=''}

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

def main():
    full=json.loads((DATA/'catalog.json').read_text(encoding='utf-8'))
    cards=full.get('cards') or []
    jp=json.loads((DATA/'catalog-weiss-jp.json').read_text(encoding='utf-8')) if (DATA/'catalog-weiss-jp.json').exists() else {'cards':[],'counts':{}}
    jp_meta=json.loads((DATA/'catalog-weiss-jp-meta.json').read_text(encoding='utf-8')) if (DATA/'catalog-weiss-jp-meta.json').exists() else {'sets':[],'counts':{}}

    if OUT.exists():shutil.rmtree(OUT)
    SETS.mkdir(parents=True,exist_ok=True)

    manifest=[]; en_index=[]; jp_index=[]; en_groups=defaultdict(list); jp_groups=defaultdict(list)

    for c in cards:
        lang=c.get('language') or 'EN'
        if lang!='EN':continue
        name=c.get('set') or 'Unknown'
        key=f"{c.get('game') or 'unknown'}-en-{slug(name)}"
        en_groups[key].append(c)

    for key,rows in en_groups.items():
        game=rows[0].get('game') or 'weiss'; name=rows[0].get('set') or 'Unknown'
        rel=f"sets/en/{key}.json"
        write(OUT/rel,{'key':key,'game':game,'language':'EN','name':name,'cards':rows})
        for c in rows:en_index.append(compact(c,set_key=key))
        manifest.append({
            'key':key,'game':game,'language':'EN','name':name,'path':f'data/web/{rel}',
            'total':len(rows),'released':sum((x.get('availability') or 'released')=='released' for x in rows),
            'announced':sum((x.get('availability') or 'released')!='released' for x in rows),
            'premium':sum(bool(x.get('isPremium')) for x in rows),
            'imaged':sum(bool(x.get('image')) for x in rows),
            'priced':sum(x.get('market') is not None or x.get('marketEUR') is not None for x in rows),
            'imageCoverage':round(sum(bool(x.get('image')) for x in rows)/max(1,len(rows))*100,1),
            'priceCoverage':round(sum(x.get('market') is not None or x.get('marketEUR') is not None for x in rows)/max(1,len(rows))*100,1),
            'avgInvestment':round(sum(float(x.get('investment') or 0) for x in rows)/max(1,len(rows)),1)
        })

    for row in jp.get('cards') or []:
        name=row.get('s') or row.get('si') or 'Unknown'
        key=f"weiss-jp-{slug(name)}"
        jp_groups[key].append(row)

    for key,rows in jp_groups.items():
        name=rows[0].get('s') or rows[0].get('si') or 'Unknown'
        rel=f"sets/jp/{key}.json"
        write(OUT/rel,{'key':key,'game':'weiss','language':'JP','name':name,'cards':rows,'compactJP':True})
        for row in rows:jp_index.append(jp_search(row,key))
        manifest.append({
            'key':key,'game':'weiss','language':'JP','name':name,'path':f'data/web/{rel}',
            'total':len(rows),'released':len(rows),'announced':0,
            'premium':sum(bool(x.get('p')) for x in rows),'imaged':sum(bool(x.get('im')) for x in rows),'priced':0,
            'imageCoverage':round(sum(bool(x.get('im')) for x in rows)/max(1,len(rows))*100,1),
            'priceCoverage':0,
            'avgInvestment':round(sum(float(x.get('iq') or 0) for x in rows)/max(1,len(rows)),1)
        })

    en_index.sort(key=lambda x:(x.get('g',''),x.get('s',''),x.get('c',''),x.get('r','')))
    jp_index.sort(key=lambda x:(x.get('s',''),x.get('c',''),x.get('r','')))
    manifest.sort(key=lambda x:(x['game'],x['language'],x['name']))

    common={'generatedAt':full.get('generatedAt'),'modelVersion':full.get('modelVersion'),
            'counts':full.get('counts') or {},'jpCounts':jp.get('counts') or {}}
    write(OUT/'manifest.json',{**common,'sets':manifest})
    write(OUT/'search-en.json',{**common,'cards':en_index})
    write(OUT/'search-jp.json',{'generatedAt':full.get('generatedAt'),'counts':jp.get('counts') or {},'cards':jp_index})

    # Tiny first paint: all current Palworld + top EN Weiss conviction.
    en_weiss=[c for c in cards if c.get('game')=='weiss' and (c.get('language') or 'EN')=='EN' and (c.get('availability') or 'released')=='released']
    en_weiss.sort(key=lambda c:(-int(c.get('investment') or 0),-int(c.get('rarityRank') or 0),str(c.get('name') or '')))
    pal=[c for c in cards if c.get('game')=='palworld' and (c.get('language') or 'EN')=='EN']
    by_set={x['key']:x for x in manifest}
    def key_for(c):
        return f"{c.get('game') or 'unknown'}-en-{slug(c.get('set') or 'Unknown')}"
    boot=[compact(c,extra=True,set_key=key_for(c)) for c in [*en_weiss[:240],*pal]]
    write(OUT/'bootstrap.json',{**common,'bootstrap':True,'sets':manifest,'cards':boot})

    set_files=list((SETS/'en').glob('*.json'))+list((SETS/'jp').glob('*.json'))
    sizes=[p.stat().st_size for p in set_files]
    meta={
        'legacyBytes':(DATA/'catalog.json').stat().st_size,
        'bootstrapBytes':(OUT/'bootstrap.json').stat().st_size,
        'searchENBytes':(OUT/'search-en.json').stat().st_size,
        'searchJPBytes':(OUT/'search-jp.json').stat().st_size,
        'searchENCards':len(en_index),'searchJPCards':len(jp_index),
        'sets':len(manifest),'setFileMaxBytes':max(sizes,default=0),
        'setFilesEN':len(en_groups),'setFilesJP':len(jp_groups)
    }
    write(OUT/'meta.json',meta)
    print('web catalog',meta)

    if meta['bootstrapBytes']>2_000_000:raise RuntimeError('Bootstrap payload too large')
    if meta['searchENBytes']>12_000_000:raise RuntimeError('EN search index too large')
    if meta['searchJPBytes']>16_000_000:raise RuntimeError('JP search index too large')
    if meta['setFileMaxBytes']>6_000_000:raise RuntimeError('A set payload is too large')
    if meta['searchENCards']<30000:raise RuntimeError('EN search index unexpectedly small')
    if meta['searchJPCards']<50000:raise RuntimeError('JP search index unexpectedly small')

if __name__=='__main__':main()
