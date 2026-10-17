#!/usr/bin/env python3
"""Build lazy per-card price-history shards from immutable market snapshots.

History is partitioned by the first hexadecimal character of the stable card id.
The browser only downloads one shard when a card preview is opened. Each shard
keeps at most the latest 180 daily observations per card.
"""
from __future__ import annotations
import json,shutil
from collections import defaultdict
from pathlib import Path
from backtest import stable_price_identity

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/snapshots'
OUT=ROOT/'data/history-shards'
MAX_DAYS=180

def main():
    files=sorted(SNAP.glob('market-*.json'))[-MAX_DAYS:]
    by_card=defaultdict(list)
    for p in files:
        try:d=json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print('WARN',p,e);continue
        date=d.get('date') or p.stem.replace('market-','')
        for cid,row in (d.get('cards') or {}).items():
            point={'d':date}
            for src,dst in [('market','u'),('fair','fu'),('marketEUR','e'),('fairEUR','fe')]:
                if row.get(src) is not None:point[dst]=row[src]
            # Keep provider publication dates distinct from the file capture day.
            # Legacy snapshots legitimately have no dates and no qualified IDs.
            if row.get('market') is not None:
                if row.get('marketAsOf'):
                    point['ua']=str(row['marketAsOf'])[:10]
                if stable_price_identity(row,'USD'):
                    point['uv']=1
            if row.get('marketEUR') is not None:
                if row.get('cardmarketAsOf'):
                    point['ea']=str(row['cardmarketAsOf'])[:10]
                if stable_price_identity(row,'EUR'):
                    point['ev']=1
            if len(point)>1:by_card[cid].append(point)
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir(parents=True,exist_ok=True)
    shards={h:{} for h in '0123456789abcdef'}
    for cid,points in by_card.items():
        shards.get(cid[0].lower(),shards['0'])[cid]=points
    counts={}
    for h,data in shards.items():
        (OUT/f'{h}.json').write_text(json.dumps({'cards':data},separators=(',',':')),encoding='utf-8')
        counts[h]=len(data)
    meta={'snapshots':len(files),'cards':len(by_card),'maxDays':MAX_DAYS,'shards':counts}
    (OUT/'meta.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
    print('history shards',meta)

if __name__=='__main__':main()
