#!/usr/bin/env python3
"""Write the *first* daily market snapshot immutably.

A same-day rerun must not rewrite historical training inputs with fresher
prices or changed model predictions. Both EUR and USD stay separate.
"""
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIELDS=('market','fair','marketEUR','fairEUR','investment','momentum',
        'confidence','fairValueConfidence','demandPressure',
        'marketHeatPercentile','characterPremiumIndex')


def capture(root=ROOT, day=None):
    root=Path(root)
    catalog=json.loads((root/'data/catalog.json').read_text(encoding='utf-8'))
    day=day or datetime.now(timezone.utc).date().isoformat()
    cards={}
    for card in catalog.get('cards',[]):
        if card.get('availability')!='released':
            continue
        if card.get('market') is None and card.get('marketEUR') is None:
            continue
        cards[card['id']]={key:card[key] for key in FIELDS if card.get(key) is not None}
    out={'date':day,'modelVersion':catalog.get('modelVersion'),'cards':cards}
    path=root/'data/snapshots'/f'market-{day}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        # Exclusive create prevents accidental price/history revisions and races.
        with path.open('x',encoding='utf-8') as stream:
            json.dump(out,stream,separators=(',',':'))
    except FileExistsError:
        print('snapshot exists, preserved unchanged:',day,path)
        return False
    usd=sum(x.get('market') is not None for x in cards.values())
    eur=sum(x.get('marketEUR') is not None for x in cards.values())
    print('snapshot created:',day,'cards',len(cards),'USD',usd,'EUR',eur)
    return True


if __name__=='__main__':
    capture()
