#!/usr/bin/env python3
"""Collect every English Weiss Schwarz printing from Trading Card Dex set pages.

Why this source: set pages expose base cards *and* parallel printings (SR/SP/SSP/SEC+,
promos, etc.) and each detail slug maps deterministically to a card image URL.
Market price enrichment is intentionally separate.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/weiss.json'
BASE='https://weissschwarz.tradingcarddex.com'
SETS=BASE+'/sets'
UA='BushiMetrics/0.3 (+https://github.com/bezdredoff/bushimetrics)'

CODE_RE=re.compile(r'([A-Za-z0-9]+/[A-Za-z0-9]+-[A-Za-z0-9]+)')
RARITY_RE=re.compile(r'^\s*([A-Z][A-Z0-9+]{0,7})\b')

def get(session,url):
    r=session.get(url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.9'},timeout=40)
    r.raise_for_status()
    return r

def discover_sets(session):
    soup=BeautifulSoup(get(session,SETS).text,'html.parser')
    out=[]
    for a in soup.find_all('a',href=True):
        u=urljoin(BASE,a['href'])
        if '/sets/' not in u or not urlparse(u).path.endswith('-card-list'):
            continue
        name=a.get_text(' ',strip=True)
        if name and (u,name) not in out: out.append((u,name))
    return out

def parse_set(session,url,set_name):
    soup=BeautifulSoup(get(session,url).text,'html.parser')
    cards=[]
    for a in soup.find_all('a',href=True):
        href=urljoin(BASE,a['href'])
        path=urlparse(href).path
        if '/database/' not in path or not path.endswith('-details'):
            continue
        txt=a.get_text(' ',strip=True)
        m=CODE_RE.search(txt)
        if not m: continue
        code=m.group(1)
        name=txt[:m.start()].strip(' ·-')
        tail=txt[m.end():].strip()
        rm=RARITY_RE.search(tail)
        rarity=rm.group(1) if rm else None
        slug=path.rsplit('/',1)[-1][:-len('-details')]
        image=f'{BASE}/images/CARDDEX/WEISSSCHWARZ/{slug}-card.jpg'
        treatment=None
        tm=re.search(r'\((SP|SSP|SEC\+?|SR|RRR\+?|OFR|SIR|AGR|PR\+?|Foil|Gold Stamp|Silver Stamp)[^)]*\)',name,re.I)
        if tm: treatment=tm.group(1)
        cards.append({
            'game':'weiss','name':name,'set':set_name,'code':code,'rarity':rarity,
            'image':image,'identitySource':href,'source':url,'treatment':treatment,
            'market':None,'priceSource':None
        })
    uniq={}
    for c in cards:
        uniq[(c['code'],c.get('rarity'),c.get('name'),c.get('identitySource'))]=c
    return list(uniq.values())

def main():
    s=requests.Session()
    sets=discover_sets(s)
    print('Weiss sets discovered:',len(sets),flush=True)
    allcards=[]
    for i,(url,name) in enumerate(sets,1):
        try:
            time.sleep(.12)
            cs=parse_set(s,url,name)
            allcards.extend(cs)
            print(f'{i}/{len(sets)} {name}: {len(cs)}',flush=True)
        except Exception as e:
            print('WARN',name,url,repr(e),flush=True)
    if len(allcards)<5000:
        raise RuntimeError(f'Weiss catalog unexpectedly small: {len(allcards)} printings')
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'source':SETS,'sets':len(sets),'cards':allcards}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved',OUT,len(allcards),flush=True)

if __name__=='__main__': main()
