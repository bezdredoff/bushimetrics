#!/usr/bin/env python3
"""Collect every current Palworld OCG printing from Trading Card Dex set pages.

The set pages include rarity variants and direct detail slugs. Images are derived from
those slugs, so we do not need one HTTP request per card.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/palworld.json'
BASE='https://palworld.tradingcarddex.com'
SETS=BASE+'/sets'
UA='BushiMetrics/0.3 (+https://github.com/bezdredoff/bushimetrics)'
CODE_RE=re.compile(r'\b(E?(?:BP|TD|PR|SOUL|SS|SLEEVE|PROMO)[A-Z0-9-]*\d[A-Z0-9+-]*)\b',re.I)
# Broad fallback covers forms such as EBP01-025SSP, ETD01-001, EPR-001, ESOUL-003.
FALLBACK_RE=re.compile(r'\b(E[A-Z]+[A-Z0-9]*-?[A-Z0-9]+)\b')
RARITY_RE=re.compile(r'^\s*([A-Z][A-Z0-9+]{0,7})\b')

def get(session,url):
    r=session.get(url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.9'},timeout=40)
    r.raise_for_status(); return r

def discover_sets(session):
    soup=BeautifulSoup(get(session,SETS).text,'html.parser');out=[]
    for a in soup.find_all('a',href=True):
        u=urljoin(BASE,a['href'])
        if '/sets/' not in u or not urlparse(u).path.endswith('-card-list'): continue
        n=a.get_text(' ',strip=True)
        if n and (u,n) not in out:out.append((u,n))
    return out

def parse_set(session,url,set_name):
    soup=BeautifulSoup(get(session,url).text,'html.parser');cards=[]
    for a in soup.find_all('a',href=True):
        href=urljoin(BASE,a['href']);path=urlparse(href).path
        if '/database/' not in path or not path.endswith('-details'):continue
        txt=a.get_text(' ',strip=True)
        m=CODE_RE.search(txt) or FALLBACK_RE.search(txt)
        if not m:continue
        code=m.group(1).upper();name=txt[:m.start()].strip(' ·-');tail=txt[m.end():].strip()
        rm=RARITY_RE.search(tail);rarity=rm.group(1) if rm else None
        slug=path.rsplit('/',1)[-1][:-len('-details')]
        image=f'{BASE}/images/CARDDEX/PALWORLD/{slug}-card.jpg'
        cards.append({'game':'palworld','name':name,'set':set_name,'code':code,'rarity':rarity,
                      'image':image,'identitySource':href,'source':url,'market':None,'priceSource':None})
    uniq={}
    for c in cards:uniq[(c['code'],c.get('rarity'),c.get('identitySource'))]=c
    return list(uniq.values())

def main():
    s=requests.Session();sets=discover_sets(s);print('Palworld sets discovered:',len(sets),flush=True);cards=[]
    for i,(u,n) in enumerate(sets,1):
        try:
            time.sleep(.12);cs=parse_set(s,u,n);cards.extend(cs);print(f'{i}/{len(sets)} {n}: {len(cs)}',flush=True)
        except Exception as e:print('WARN',n,u,repr(e),flush=True)
    if len(cards)<150:raise RuntimeError(f'Palworld catalog unexpectedly small: {len(cards)} printings')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'generatedAt':datetime.now(timezone.utc).isoformat(),'source':SETS,'sets':len(sets),'cards':cards},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved',OUT,len(cards),flush=True)

if __name__=='__main__':main()
