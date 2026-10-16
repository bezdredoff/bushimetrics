#!/usr/bin/env python3
"""Collect every card currently published in the official Palworld OCG card list."""
from __future__ import annotations
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/raw/palworld.json'
BASE='https://en.palworld-official-cardgame.com'; LIST=BASE+'/cardlist/searchresults'
UA='BushiMetrics/0.3 public research collector (+https://github.com/bezdredoff/bushimetrics)'

def detail(session,url,delay=.12):
    time.sleep(delay); r=session.get(url,headers={'User-Agent':UA},timeout=30); r.raise_for_status(); s=BeautifulSoup(r.text,'html.parser')
    title=s.find('h1') or s.find('h2'); name=title.get_text(' ',strip=True) if title else None
    page='\n'.join(x.strip() for x in s.stripped_strings)
    def rx(label):
        m=re.search(rf'{re.escape(label)}\s*\n([^\n]+)',page,re.I); return m.group(1).strip() if m else None
    code=rx('Card Number'); rarity=rx('Rarity'); color=rx('Color'); ctype=rx('Card Types'); subtype=rx('Subtype')
    img=None
    for im in s.find_all('img'):
        alt=(im.get('alt') or '').strip(); src=im.get('src') or im.get('data-src')
        if src and name and (alt==name or name.lower() in alt.lower()): img=urljoin(BASE,src); break
    if not img:
        for im in s.find_all('img'):
            src=im.get('src') or im.get('data-src') or ''
            if src and ('card' in src.lower() or '/upload/' in src.lower()): img=urljoin(BASE,src); break
    set_name=None; release=None
    m=re.search(r'Card Set\s*\n\s*(\d{4}\.\d{2}\.\d{2})\s*\n([^\n]+)',page,re.I)
    if m: release=m.group(1).replace('.','-'); set_name=m.group(2).strip()
    return {'game':'palworld','name':name,'code':code,'rarity':rarity,'color':color,'cardType':ctype,'subtype':subtype,'set':set_name,'releaseDate':release,'image':img,'officialUrl':url}

def main():
    s=requests.Session(); r=s.get(LIST,headers={'User-Agent':UA},timeout=30); r.raise_for_status(); soup=BeautifulSoup(r.text,'html.parser')
    links=list(dict.fromkeys(urljoin(BASE,a.get('href')) for a in soup.select('a[href*="/cardlist/detail?id="]')))
    print('Palworld detail pages:',len(links)); cards=[]
    for i,u in enumerate(links,1):
        try:
            c=detail(s,u)
            if c.get('code'): cards.append(c)
        except Exception as e: print('WARN',u,e)
        if i%50==0: print(i,'/',len(links))
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'source':LIST,'cards':cards}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); print('saved',OUT,len(cards))
if __name__=='__main__':main()
