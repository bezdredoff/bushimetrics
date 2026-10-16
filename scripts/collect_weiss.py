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

AUDIT=ROOT/'data/en-identity-audit.json'
COMPARE_FIELDS=('name','set','setId','rarity','cardType','image','variant')


def scan_source_files(files, max_examples=100):
    """Audit silently discarded duplicate collector codes while preserving current output."""
    by_code={}
    duplicate_codes=set()
    conflict_codes=set()
    examples=[]
    invalid_examples=[]
    files_eligible=0
    files_other_language=0
    invalid_files=0
    rows=0
    rows_with_code=0
    missing_code_rows=0
    invalid_card_rows=0
    duplicate_rows=0
    for i,path in enumerate(files,1):
        try:
            source=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(source,dict) or not isinstance(source.get('cards'),list):
                raise ValueError('expected set JSON object with cards list')
        except (ValueError,TypeError,OSError) as exc:
            invalid_files+=1
            if len(invalid_examples)<20:
                invalid_examples.append({'file':path.name,'reason':str(exc)[:200]})
            continue
        if source.get('lang') not in (None,'en'):
            files_other_language+=1
            continue
        files_eligible+=1
        for raw in source['cards']:
            rows+=1
            if not isinstance(raw,dict):
                invalid_card_rows+=1
                continue
            try:
                card=normalize_card(source,raw,path)
            except (TypeError,AttributeError) as exc:
                invalid_card_rows+=1
                if len(invalid_examples)<20:
                    invalid_examples.append({'file':path.name,'reason':str(exc)[:200]})
                continue
            if card is None:
                missing_code_rows+=1
                continue
            rows_with_code+=1
            code=card['code']
            old=by_code.get(code)
            if old is not None:
                duplicate_rows+=1
                duplicate_codes.add(code)
                different=[key for key in COMPARE_FIELDS if old.get(key)!=card.get(key)]
                if different:
                    conflict_codes.add(code)
                    if len(examples)<max_examples:
                        examples.append({
                            'code':code,
                            'differingFields':different,
                            'kept':{key:old.get(key) for key in (*COMPARE_FIELDS,'identitySource')},
                            'candidate':{key:card.get(key) for key in (*COMPARE_FIELDS,'identitySource')}
                        })
            # Preserve pre-audit behavior: use the first row unless the next has artwork.
            if old is None or (not old.get('image') and card.get('image')):
                by_code[code]=card
        if i%100==0:
            print('parsed files',i,'cards',len(by_code),flush=True)

    audit={
        'source':'https://github.com/GachaWiki/gacha-wiki/tree/main/src/data/ws-cards',
        'sourceFiles':len(files),
        'englishSetFiles':files_eligible,
        'nonEnglishSetFiles':files_other_language,
        'invalidSetFiles':invalid_files,
        'cardRows':rows,
        'validCodeRows':rows_with_code,
        'missingCodeRows':missing_code_rows,
        'invalidCardRows':invalid_card_rows,
        'uniquePrintingsByCode':len(by_code),
        'duplicateCodeRows':duplicate_rows,
        'duplicateCodeGroups':len(duplicate_codes),
        'conflictingCodeGroups':len(conflict_codes),
        'conflictExamples':examples,
        'invalidExamples':invalid_examples,
        'notes':[
            'Conflicting source metadata is a review candidate, not proof of another physical printing.',
            'A source-file image mismatch may reflect only metadata quality.',
            'This report audits the imported open dataset, not full live official product coverage.'
        ]
    }
    return list(by_code.values()),audit


def write_audit_if_changed(audit):
    AUDIT.parent.mkdir(parents=True,exist_ok=True)
    if AUDIT.exists():
        try:
            if json.loads(AUDIT.read_text(encoding='utf-8'))==audit:
                print('EN identity audit unchanged')
                return
        except (ValueError,OSError):
            pass
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('EN identity audit',{key:audit[key] for key in (
        'sourceFiles','validCodeRows','uniquePrintingsByCode',
        'duplicateCodeRows','conflictingCodeGroups'
    )},flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',default=str(ROOT/'external/gacha-wiki/src/data/ws-cards'))
    args=ap.parse_args()
    src=Path(args.source_dir)
    if not src.exists():
        raise SystemExit(f'Missing Weiss source directory: {src}')
    files=sorted(src.glob('*.json'))
    cards,audit=scan_source_files(files)
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
    write_audit_if_changed(audit)

if __name__=='__main__': main()
