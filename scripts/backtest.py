#!/usr/bin/env python3
"""Walk-forward evaluator. It never trains on future snapshots."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SNAP=ROOT/'data/snapshots'
def main():
    files=sorted(SNAP.glob('catalog-*.json'));print('snapshots',len(files))
    if len(files)<31:
        print('Need at least 31 daily snapshots for first 30d walk-forward evaluation.');return
    bydate=[]
    for p in files:
        d=json.loads(p.read_text());bydate.append({c['id']:c for c in d.get('cards',[])})
    for h in [30,90,180]:
        if len(bydate)<=h:print(h,'days: insufficient');continue
        errors=[]
        for i in range(len(bydate)-h):
            a,b=bydate[i],bydate[i+h]
            for cid,c in a.items():
                if cid not in b or not c.get('market') or not b[cid].get('market') or not c.get('fair'):continue
                pred=c['fair']/c['market']-1;actual=b[cid]['market']/c['market']-1;errors.append(abs(pred-actual))
        print(h,'days observations',len(errors),'MAE',round(sum(errors)/len(errors),4) if errors else None)
if __name__=='__main__':main()
