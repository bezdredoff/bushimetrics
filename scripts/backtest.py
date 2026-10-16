#!/usr/bin/env python3
"""No-look-ahead walk-forward evaluation over compact daily snapshots.

EUR and USD are evaluated independently so FX movement never contaminates a
card-price prediction. A card can contribute to one or both currency tracks.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/snapshots'

def evaluate(maps,h,market_key,fair_key):
    errors=[]; directional=[]
    for i in range(len(maps)-h):
        a,b=maps[i],maps[i+h]
        for cid,c in a.items():
            nxt=b.get(cid)
            if not nxt: continue
            start=c.get(market_key); fair=c.get(fair_key); end=nxt.get(market_key)
            if start in (None,0) or fair in (None,0) or end in (None,0): continue
            pred=fair/start-1
            actual=end/start-1
            errors.append(abs(pred-actual))
            directional.append((pred>=0)==(actual>=0))
    return {
        'observations':len(errors),
        'mae':round(sum(errors)/len(errors),4) if errors else None,
        'directional':round(sum(directional)/len(directional),4) if directional else None
    }

def main():
    files=sorted(SNAP.glob('market-*.json'))
    print('market snapshots',len(files))
    if len(files)<31:
        print('Need >=31 daily market snapshots for the first 30d evaluation.')
        return
    maps=[json.loads(p.read_text(encoding='utf-8')).get('cards',{}) for p in files]
    for h in (30,90,180):
        if len(maps)<=h:
            print(h,'days: insufficient'); continue
        eur=evaluate(maps,h,'marketEUR','fairEUR')
        usd=evaluate(maps,h,'market','fair')
        print(h,'days','EUR',eur,'USD',usd)

if __name__=='__main__':
    main()
