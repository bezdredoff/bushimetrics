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


def scan_source(files, max_examples=100, verified_variants=None):
    """Keep separately VERIFIED rarity variants, audit all duplicate codes.

    No generalized splitting by image or rarity: only explicit externally
    corroborated code/rarity combinations can create a new printing.
    """
    verified_variants=verified_variants or {}
    chosen={}
    first_by_code={}
    duplicate_codes=set()
    conflict_codes=set()
    verified_conflicts=set()
    unresolved_conflicts=set()
    examples=[]
    bad_examples=[]
    parsed=0
    missing=0
    invalid=0
    duplicate_files=0
    discarded_files=0
    verified_variant_rows=0
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
        rarity=str(card.get('rarity') or '').upper()
        approved=verified_variants.get(code) or {}
        allowed=set(approved.get('rarities') or [])
        if allowed and rarity not in allowed:
            raise ValueError(
                f'Unexpected rarity {rarity} for verified code {code}; review upstream identity'
            )
        existing=first_by_code.get(code)
        if existing is not None:
            duplicate_files+=1
            duplicate_codes.add(code)
            different=[key for key in COMPARE_FIELDS if existing.get(key)!=card.get(key)]
            if different:
                conflict_codes.add(code)
                independently_verified=(
                    bool(allowed) and rarity!=str(existing.get('rarity') or '').upper()
                    and rarity in allowed
                    and str(existing.get('rarity') or '').upper() in allowed
                )
                if independently_verified:
                    verified_conflicts.add(code)
                else:
                    unresolved_conflicts.add(code)
                if len(examples)<max_examples:
                    examples.append({
                        'code':code,
                        'differingFields':different,
                        'resolution':'verified separate printing' if independently_verified else 'requires review',
                        'first':{key:existing.get(key) for key in (*COMPARE_FIELDS,'sourceFile')},
                        'candidate':{key:card.get(key) for key in (*COMPARE_FIELDS,'sourceFile')}
                    })
        else:
            first_by_code[code]=card
        identity=(code,rarity) if allowed else (code,None)
        if identity in chosen:
            discarded_files+=1
        else:
            if existing is not None and allowed:
                verified_variant_rows+=1
            chosen[identity]=card
        if i%10000==0:
            print('JP files',i,'distinct printings',len(chosen),flush=True)

    audit={
        'source':'https://github.com/Akenaide/wsoffdata',
        'sourceFiles':i if 'i' in locals() else 0,
        'parsedFiles':parsed,
        'invalidFiles':invalid,
        'missingCardCodeFiles':missing,
        'uniqueCollectorCodes':len(first_by_code),
        'uniquePrintingsByCode':len(chosen),
        'duplicateCodeFiles':duplicate_files,
        'discardedDuplicateFiles':discarded_files,
        'verifiedVariantRows':verified_variant_rows,
        'duplicateCodeGroups':len(duplicate_codes),
        'conflictingCodeGroups':len(conflict_codes),
        'verifiedConflictCodeGroups':len(verified_conflicts),
        'unresolvedConflictingCodeGroups':len(unresolved_conflicts),
        'conflictExamples':examples,
        'invalidExamples':bad_examples,
        'notes':[
            'Only explicitly source-verified rarities can share a collector code as distinct physical printings.',
            'All other conflicts remain unresolved for manual review, not automatically split.',
            'This source audit does not certify completeness against the live official Bushiroad catalog.'
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
        'duplicateCodeGroups','conflictingCodeGroups','verifiedVariantRows','unresolvedConflictingCodeGroups'
    )},flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',default=str(ROOT/'external/wsoffdata'))
    args=ap.parse_args();src=Path(args.source_dir)
    if not src.exists():raise SystemExit(f'Missing JP Weiss source: {src}')
    files=sorted(src.glob('*/*/*.json'))
    verified=json.loads((ROOT/'data/verified-jp-variants.json').read_text(encoding='utf-8'))
    if verified.get('schemaVersion')!=1:raise RuntimeError('Invalid JP verified variant schema')
    cards,audit=scan_source(files,verified_variants=verified.get('byCode',{}))
    if len(cards)<50000:
        raise RuntimeError(f'JP Weiss catalog unexpectedly small: {len(cards)}')
    cards.sort(key=lambda c:(c.get('setId') or '',c.get('code') or ''))
    write_if_changed({'source':'https://github.com/Akenaide/wsoffdata',
                      'sourceFiles':len(files),'cards':cards})
    write_audit_if_changed(audit)

if __name__=='__main__':main()
