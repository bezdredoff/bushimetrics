#!/usr/bin/env python3
"""No-look-ahead walk-forward evaluation over compact daily snapshots."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SNAP=ROOT/'data/snapshots'
def main():
    files=sorted(SNAP.glob('market-*.json'))
    print('market snapshots',len(files))
    if len(files)<31:
        print('Need >=31 daily market snapshots for the first 30d evaluation.'); return
    maps=[json.loads(p.read_text(encoding='utf-8')).get('cards',{}) for p in files]
    for h in (30,90,180):
        if len(maps)<=h:
            print(h,'days: insufficient'); continue
        errors=[]; directional=[]
        for i in range(len(maps)-h):
            a,b=maps[i],maps[i+h]
            for cid,c in a.items():
                nxt=b.get(cid)
                if not nxt or not c.get('market') or not c.get('fair') or not nxt.get('market'): continue
                pred=c['fair']/c['market']-1
                actual=nxt['market']/c['market']-1
                errors.append(abs(pred-actual))
                directional.append((pred>=0)==(actual>=0))
        print(h,'days observations',len(errors),'MAE',round(sum(errors)/len(errors),4) if errors else None,
              'directional',round(sum(directional)/len(directional),4) if directional else None)
if __name__=='__main__':main()
