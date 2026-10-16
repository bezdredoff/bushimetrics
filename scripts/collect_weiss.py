#!/usr/bin/env python3
"""Collect the full TCGRate Weiss Schwarz market catalog.
Discovers set URLs from the Weiss index, then follows pagination on every set page.
"""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/raw/weiss.json'
BASE='https://tcgrate.com'; INDEX=BASE+'/weiss-schwarz/'; YEARS=BASE+'/weiss-schwarz/years/'
UA='BushiMetrics/0.3 public research collector (+https://github.com/bezdredoff/bushimetrics)'
RESERVED={'years','sets','rarity','releases','sealed','prices','top-cards','movers'}
RARITIES={'SEC+','SEC','SSP','SP','OFR','AGR','SIR','RRR+','RRR','SR','PR','RR','R','U','C','TD','CR','CC','N','PER','XR'}

def money(t):
    m=re.search(r'\$([0-9,]+(?:\.\d+)?)',t or ''); return float(m.group(1).replace(',','')) if m else None

def percents(t): return [float(x) for x in re.findall(r'([+-]?\d+(?:\.\d+)?)%',(t or '').replace('−','-'))]

def discover_sets(session):
    urls={}
    for source in (INDEX,YEARS):
        r=session.get(source,headers={'User-Agent':UA},timeout=30); r.raise_for_status(); s=BeautifulSoup(r.text,'html.parser')
        for a in s.find_all('a',href=True):
            u=urljoin(BASE,a['href']); p=urlparse(u).path.strip('/').split('/')
            if len(p)==2 and p[0]=='weiss-schwarz' and p[1] not in RESERVED:
                name=a.get_text(' ',strip=True)
                if name and len(name)>2: urls[u]=name
    return urls

def next_page(soup,current):
    for a in soup.find_all('a',href=True):
        t=a.get_text(' ',strip=True).lower()
        if t.startswith('next'): return urljoin(current,a['href'])
    return None

def parse_row(tr,set_name,set_url):
    txt=' '.join(tr.stripped_strings)
    if '$' not in txt:return None
    code_m=re.search(r'#?([A-Z0-9]+/[A-Z0-9]+-E?[A-Z0-9+\-]+)',txt)
    if not code_m:return None
    code=code_m.group(1)
    rarity=None
    tail=txt[txt.find(code)+len(code):]
    for r in sorted(RARITIES,key=len,reverse=True):
        if re.search(rf'(^|\s|\)){re.escape(r)}($|\s|\()',tail): rarity=r; break
    a=tr.find('a',href=True); name=a.get_text(' ',strip=True) if a else txt.split('·')[0].strip()
    price=money(txt); ps=percents(txt)
    source=urljoin(BASE,a['href']) if a else set_url
    return {'game':'weiss','name':name,'set':set_name,'code':code,'rarity':rarity,'market':price,'change7d':ps[0] if ps else None,'change30d':ps[1] if len(ps)>1 else None,'source':source,'setUrl':set_url}

def parse_cards(html,set_name,set_url):
    s=BeautifulSoup(html,'html.parser'); out=[]
    for tr in s.select('table tr'):
        c=parse_row(tr,set_name,set_url)
        if c:out.append(c)
    if not out:
        for a in s.find_all('a',href=True):
            block=a.parent.get_text(' ',strip=True) if a.parent else a.get_text(' ',strip=True)
            if '$' not in block:continue
            m=re.search(r'#?([A-Z0-9]+/[A-Z0-9]+-E?[A-Z0-9+\-]+)',block)
            if not m:continue
            code=m.group(1); rarity=None
            for rr in sorted(RARITIES,key=len,reverse=True):
                if re.search(rf'\b{re.escape(rr)}\b',block): rarity=rr;break
            out.append({'game':'weiss','name':a.get_text(' ',strip=True),'set':set_name,'code':code,'rarity':rarity,'market':money(block),'change7d':(percents(block)+[None])[0],'source':urljoin(BASE,a['href']),'setUrl':set_url})
    return out,s

def collect_set(session,url,set_name):
    seen=set(); cards=[]; page=url
    while page and page not in seen:
        seen.add(page); time.sleep(.18); r=session.get(page,headers={'User-Agent':UA},timeout=30); r.raise_for_status(); chunk,s=parse_cards(r.text,set_name,url); cards+=chunk; page=next_page(s,r.url)
    uniq={}
    for c in cards:uniq[(c['code'],c['name'])]=c
    return list(uniq.values())

def main():
    s=requests.Session(); sets=discover_sets(s); print('Weiss sets discovered:',len(sets)); allcards=[]
    for i,(u,n) in enumerate(sets.items(),1):
        try:
            cs=collect_set(s,u,n); allcards+=cs; print(f'{i}/{len(sets)} {n}: {len(cs)}')
        except Exception as e: print('WARN',n,u,e)
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'source':INDEX,'sets':len(sets),'cards':allcards}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); print('saved',OUT,len(allcards))
if __name__=='__main__':main()
