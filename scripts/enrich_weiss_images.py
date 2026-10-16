#!/usr/bin/env python3
"""Best-effort image enrichment for investment-relevant Weiss printings."""
from __future__ import annotations
import argparse,json,re,time
from pathlib import Path
from urllib.parse import quote,urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'data/raw/weiss.json'; OUT=ROOT/'data/raw/weiss-images.json'
BASE='https://tcgrepublic.com'; UA='BushiMetrics/0.3 public research collector'
PREMIUM={'SP','SSP','SEC','SEC+','OFR','AGR','SIR','RRR+','SSS'}
def price(t):
    m=re.search(r'\$([0-9,]+(?:\.\d+)?)',t or '');return float(m.group(1).replace(',','')) if m else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=600);args=ap.parse_args()
    d=json.loads(RAW.read_text());cards=[c for c in d['cards'] if c.get('rarity') in PREMIUM][:args.limit];s=requests.Session()
    existing={}
    if OUT.exists():
        try: existing=json.loads(OUT.read_text()).get('cards',{})
        except: pass
    out=dict(existing)
    for i,c in enumerate(cards,1):
        if c['code'] in out and out[c['code']].get('image'): continue
        q=quote(c['code']);url=f'{BASE}/search?keyword={q}'
        try:
            time.sleep(.3);r=s.get(url,headers={'User-Agent':UA},timeout=30);r.raise_for_status();soup=BeautifulSoup(r.text,'html.parser');link=None
            for a in soup.find_all('a',href=True):
                if '/product/product_page_' in a['href'] and (c['code'].replace('-E','-') in a.get_text(' ',strip=True) or c['code'].split('-E')[0] in a.get_text(' ',strip=True)):
                    link=urljoin(BASE,a['href']);break
            if not link:continue
            time.sleep(.2);rr=s.get(link,headers={'User-Agent':UA},timeout=30);rr.raise_for_status();sp=BeautifulSoup(rr.text,'html.parser');img=None
            for im in sp.find_all('img'):
                src=im.get('src') or im.get('data-src') or ''
                if '/media/binary/' in src:img=urljoin(BASE,src);break
            out[c['code']]={'image':img,'ask':price(sp.get_text(' ',strip=True)),'identitySource':link}
        except Exception as e: print('WARN',c['code'],e)
        if i%50==0:print(i,'/',len(cards))
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'cards':out},ensure_ascii=False,indent=2),encoding='utf-8');print('saved',len(out))
if __name__=='__main__':main()
