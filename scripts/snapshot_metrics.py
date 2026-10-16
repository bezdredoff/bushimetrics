#!/usr/bin/env python3
"""Persist a compact immutable daily market/model snapshot."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
today=datetime.now(timezone.utc).date().isoformat()
cards={}
for c in catalog.get('cards',[]):
    if c.get('availability')!='released': continue
    if c.get('market') is None and c.get('fair') is None: continue
    cards[c['id']]={k:c.get(k) for k in ('market','fair','investment','momentum','confidence','demandPressure','marketHeatPercentile','characterPremiumIndex') if c.get(k) is not None}
out={'date':today,'modelVersion':catalog.get('modelVersion'),'cards':cards}
p=ROOT/'data/snapshots'/f'market-{today}.json';p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
print('snapshot',today,'cards',len(cards))
