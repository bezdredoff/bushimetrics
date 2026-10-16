#!/usr/bin/env python3
"""Collect Japanese Weiss Schwarz printings from Akenaide/wsoffdata.

Only analytics/identity fields are retained; rules/flavour text are intentionally
not copied into BushiMetrics. Artwork stays as official ws-tcg.com URLs.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/weiss-jp.json'
TYPE_MAP={'CH':'Character','EV':'Event','CX':'Climax'}

def compact(raw,path):
    code=str(raw.get('cardcode') or '').strip()
    if not code:return None
    set_id='/'.join(path.parts[-3:-1]) if len(path.parts)>=3 else str(raw.get('set') or '')
    return {
      'game':'weiss','language':'JP',
      'name':str(raw.get('jpName') or raw.get('name') or code).strip(),
      'set':str(raw.get('setName') or set_id).strip(),
      'setId':set_id,
      'code':code,
      'rarity':str(raw.get('rarity') or '').strip() or None,
      'cardType':TYPE_MAP.get(str(raw.get('cardType') or '').upper(),raw.get('cardType')),
      'color':str(raw.get('colour') or '').title() or None,
      'image':raw.get('imageURL'),
      'identitySource':f'https://github.com/Akenaide/wsoffdata/blob/master/{set_id}/{path.name}',
      'catalogSource':'Akenaide/wsoffdata / official ws-tcg.com artwork',
      'availability':'released',
      'market':None,'priceSource':None
    }

def write_if_changed(payload):
    if OUT.exists():
        try:
            old=json.loads(OUT.read_text(encoding='utf-8'))
            if old.get('cards')==payload.get('cards'):
                print('JP Weiss unchanged',len(payload['cards']));return
        except Exception:pass
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('saved JP Weiss',len(payload['cards']))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',default=str(ROOT/'external/wsoffdata'))
    args=ap.parse_args();src=Path(args.source_dir)
    if not src.exists():raise SystemExit(f'Missing JP Weiss source: {src}')
    cards=[];seen=set();files=sorted(src.glob('*/*/*.json'))
    for i,p in enumerate(files,1):
        try:raw=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print('WARN',p,e);continue
        c=compact(raw,p)
        if not c or c['code'] in seen:continue
        seen.add(c['code']);cards.append(c)
        if i%10000==0:print('JP files',i,'unique',len(cards),flush=True)
    if len(cards)<50000:raise RuntimeError(f'JP Weiss catalog unexpectedly small: {len(cards)}')
    cards.sort(key=lambda c:(c.get('setId') or '',c.get('code') or ''))
    write_if_changed({'source':'https://github.com/Akenaide/wsoffdata','sourceFiles':len(files),'cards':cards})

if __name__=='__main__':main()
