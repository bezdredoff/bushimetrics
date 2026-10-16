#!/usr/bin/env python3
"""Calendar-day, out-of-time walk-forward validation for observed prices.

Do not interpret file index offsets as elapsed days. A prediction is evaluated
only when an observation exists in the requested future calendar-day window.
EUR and USD are scored independently; snapshots never backfill earlier dates.
"""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / 'data/snapshots'
HORIZONS = (30, 90, 180)

def evaluate(pairs, market_key, fair_key):
    errors, directional = [], []
    for start, end in pairs:
        for cid, current in start.items():
            later = end.get(cid)
            if not later:
                continue
            price, fair, future = (current.get(market_key),
                                   current.get(fair_key), later.get(market_key))
            if any(not isinstance(v, (int,float)) or v <= 0 for v in (price, fair, future)):
                continue
            pred, realized = fair/price-1, future/price-1
            errors.append(abs(pred-realized))
            directional.append((pred >= 0) == (realized >= 0))
    return {'observations': len(errors),
            'mae': round(sum(errors)/len(errors),4) if errors else None,
            'directional': round(sum(directional)/len(directional),4) if errors else None}


def calendar_pairs(snapshots, horizon, tolerance_days=3):
    """Use snapshots within [horizon, horizon+tolerance] calendar days.

    No snapshot preceding the horizon is used; each initial day contributes at
    most one future comparison for a given horizon.
    """
    days = sorted(snapshots)
    for start_day in days:
        target = start_day + timedelta(days=horizon)
        future = next((d for d in days if target <= d <= target+timedelta(days=tolerance_days)), None)
        if future is not None:
            yield snapshots[start_day], snapshots[future]


def load_snapshots(folder):
    snapshots = {}
    for path in sorted(folder.glob('market-*.json')):
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
            day=date.fromisoformat(payload['date'])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            raise ValueError(f'Invalid dated snapshot {path}: {e}') from e
        if day.isoformat() not in path.name:
            raise ValueError(f'Snapshot filename/date mismatch: {path.name} vs {day}')
        if day in snapshots:
            raise ValueError(f'Duplicate dated snapshot: {day}')
        cards=payload.get('cards')
        if not isinstance(cards,dict):
            raise ValueError(f'Invalid card map: {path}')
        snapshots[day]=cards
    return snapshots


def main():
    snapshots=load_snapshots(SNAP)
    print('distinct dated market snapshots',len(snapshots))
    for h in HORIZONS:
        pairs=list(calendar_pairs(snapshots,h))
        eur=evaluate(pairs,'marketEUR','fairEUR')
        usd=evaluate(pairs,'market','fair')
        print(f'{h} calendar days ({len(pairs)} dated pairs): EUR {eur}; USD {usd}')
        if not pairs:
            print(f'{h}d pending — insufficient future-dated observations')
    return snapshots

if __name__=='__main__':
    main()
