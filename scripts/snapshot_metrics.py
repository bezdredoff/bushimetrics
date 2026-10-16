#!/usr/bin/env python3
"""Persist a compact immutable daily market/model snapshot.

Both Cardmarket EUR and USD sold/TCGPlayer layers are kept. A card enters the
snapshot if either currency has an observed market value. This matters because
most English Weiss coverage currently comes from Cardmarket EUR while Palworld
is mostly USD sold-price evidence.
"""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
today=datetime.now(timezone.utc).date().isoformat()
cards={}
fields=(
    'market','fair','marketEUR','fairEUR',
    'investment','momentum','confidence','fairValueConfidence',
    'demandPressure','marketHeatPercentile','characterPremiumIndex'
)
for c in catalog.get('cards',[]):
    if c.get('availability')!='released':
        continue
    if c.get('market') is None and c.get('marketEUR') is None:
        continue
    cards[c['id']]={k:c.get(k) for k in fields if c.get(k) is not None}
out={'date':today,'modelVersion':catalog.get('modelVersion'),'cards':cards}
p=ROOT/'data/snapshots'/f'market-{today}.json'
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
usd=sum(1 for c in cards.values() if c.get('market') is not None)
eur=sum(1 for c in cards.values() if c.get('marketEUR') is not None)
print('snapshot',today,'cards',len(cards),'USD',usd,'EUR',eur)
