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
      'sourceFile':f'{set_id}/{path.name}',
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

AUDIT=ROOT/'data/jp-identity-audit.json'
COMPARE_FIELDS=('name','set','setId','rarity','cardType','image')


def scan_source(files, max_examples=100):
    """Preserve current first-encountered policy; report everything it discards.

    Different image, set or rarity for one collector number is a *possible*
    identity conflict, not proof that a distinct physical card exists.
    """
    chosen={}
    duplicate_codes=set()
    conflict_codes=set()
    examples=[]
    bad_examples=[]
    parsed=0
    missing=0
    invalid=0
    duplicate_files=0
    for i,path in enumerate(files,1):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw,dict):
                raise ValueError('card JSON must be an object')
            card=compact(raw,path)
            parsed+=1
        except (ValueError,TypeError,OSError,AttributeError) as exc:
            invalid+=1
            if len(bad_examples)<20:
                bad_examples.append({'file':str(path),'error':str(exc)[:200]})
            continue
        if not card:
            missing+=1
            continue
        code=card['code']
        existing=chosen.get(code)
        if existing is not None:
            duplicate_files+=1
            duplicate_codes.add(code)
            different=[key for key in COMPARE_FIELDS if existing.get(key)!=card.get(key)]
            if different:
                conflict_codes.add(code)
                if len(examples)<max_examples:
                    examples.append({
                        'code':code,
                        'differingFields':different,
                        'kept':{key:existing.get(key) for key in (*COMPARE_FIELDS,'sourceFile')},
                        'discarded':{key:card.get(key) for key in (*COMPARE_FIELDS,'sourceFile')}
                    })
        else:
            chosen[code]=card
        if i%10000==0:
            print('JP files',i,'unique',len(chosen),flush=True)

    audit={
        'source':'https://github.com/Akenaide/wsoffdata',
        'sourceFiles':i if 'i' in locals() else 0,
        'parsedFiles':parsed,
        'invalidFiles':invalid,
        'missingCardCodeFiles':missing,
        'uniquePrintingsByCode':len(chosen),
        'duplicateCodeFiles':duplicate_files,
        'duplicateCodeGroups':len(duplicate_codes),
        'conflictingCodeGroups':len(conflict_codes),
        'conflictExamples':examples,
        'invalidExamples':bad_examples,
        'notes':[
            'A repeated collector code is not automatically a second verified physical printing.',
            'Different rarity, name, set or artwork for the same code requires source-level and physical verification.',
            'This audit compares the upstream GitHub data with itself; it does not certify completeness against the live Bushiroad website.'
        ]
    }
    return list(chosen.values()),audit


def write_audit_if_changed(payload):
    AUDIT.parent.mkdir(parents=True,exist_ok=True)
    if AUDIT.exists():
        try:
            if json.loads(AUDIT.read_text(encoding='utf-8'))==payload:
                print('JP identity audit unchanged')
                return
        except (ValueError,OSError):
            pass
    AUDIT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('JP identity audit', {key:payload[key] for key in (
        'sourceFiles','uniquePrintingsByCode','duplicateCodeFiles',
        'duplicateCodeGroups','conflictingCodeGroups'
    )},flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',default=str(ROOT/'external/wsoffdata'))
    args=ap.parse_args();src=Path(args.source_dir)
    if not src.exists():raise SystemExit(f'Missing JP Weiss source: {src}')
    files=sorted(src.glob('*/*/*.json'))
    cards,audit=scan_source(files)
    if len(cards)<50000:
        raise RuntimeError(f'JP Weiss catalog unexpectedly small: {len(cards)}')
    cards.sort(key=lambda c:(c.get('setId') or '',c.get('code') or ''))
    write_if_changed({'source':'https://github.com/Akenaide/wsoffdata',
                      'sourceFiles':len(files),'cards':cards})
    write_audit_if_changed(audit)

if __name__=='__main__':main()
