#!/usr/bin/env python3
"""Build the complete English Weiss Schwarz printing catalog from GachaWiki's
MIT-licensed GitHub dataset.

Expected source checkout:
  external/gacha-wiki/src/data/ws-cards/*.json

Every premium parallel is its own row in the source (SP/SSP/SEC/SEC+/SR/etc.)
and carries an official Bushiroad image URL.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/weiss.json'

def normalize_card(set_meta, card, source_path):
    code=(card.get('num') or '').strip()
    if not code: return None
    return {
        'game':'weiss','language':'EN',
        'name':(card.get('name') or code).strip(),
        'set':set_meta.get('name') or set_meta.get('id') or source_path.stem,
        'setId':set_meta.get('id') or source_path.stem,
        'code':code,
        'rarity':(card.get('rarity') or '').strip() or None,
        'cardType':card.get('type'),
        'color':card.get('color'),
        'image':card.get('img'),
        'variant':card.get('variant'),
        'identitySource':f'https://github.com/GachaWiki/gacha-wiki/blob/main/src/data/ws-cards/{source_path.name}',
        'catalogSource':'GachaWiki / official Bushiroad image metadata',
        'market':None,
        'priceSource':None,
        'availability':'released',
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',default=str(ROOT/'external/gacha-wiki/src/data/ws-cards'))
    args=ap.parse_args()
    src=Path(args.source_dir)
    if not src.exists():
        raise SystemExit(f'Missing Weiss source directory: {src}')
    by_code={}
    files=sorted(src.glob('*.json'))
    for i,p in enumerate(files,1):
        try:
            d=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print('WARN parse',p.name,e,flush=True); continue
        if d.get('lang') not in (None,'en'):
            continue
        for raw in d.get('cards') or []:
            c=normalize_card(d,raw,p)
            if not c: continue
            old=by_code.get(c['code'])
            # Prefer records that have an official image and a specific set name.
            if old is None or (not old.get('image') and c.get('image')):
                by_code[c['code']]=c
        if i%100==0: print('parsed files',i,'cards',len(by_code),flush=True)
    cards=list(by_code.values())
    if len(cards)<10000:
        raise RuntimeError(f'Weiss catalog unexpectedly small: {len(cards)} unique printings')
    payload={
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':'https://github.com/GachaWiki/gacha-wiki/tree/main/src/data/ws-cards',
        'sourceFiles':len(files),
        'cards':cards
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved Weiss',len(cards),flush=True)

if __name__=='__main__': main()
