#!/usr/bin/env python3
"""Calendar-day holdout reports by the originating forecast model version.

Real observation dates and saved *start-day* prediction versions are immutable.
Future observed guide prices may come from a newer model run, but the forecast
is ALWAYS attributed to its own saved model version and currency.

A small handful of backtest matches never receives a publishable accuracy score.
Cardmarket/TCGCSV guides are not verified completed-sale returns.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/snapshots'
OUTPUT=ROOT/'data/backtest-status.json'
HORIZONS=(30,90,180)
MIN_START_DAYS=3
MIN_OBSERVATIONS=30


def valid_row(current,later,market_key,fair_key):
    values=(current.get(market_key),current.get(fair_key),later.get(market_key))
    return all(isinstance(v,(int,float)) and not isinstance(v,bool) and
               v>0 and v!=float('inf') and v!=float('-inf') and v==v
               for v in values)


def evaluate(pairs,market_key,fair_key):
    errors,directional=[],[]
    for start,end in pairs:
        for cid,current in start.items():
            later=end.get(cid)
            if not later or not valid_row(current,later,market_key,fair_key):
                continue
            price,fair,future=(current[market_key],
                               current[fair_key],later[market_key])
            predicted,realized=fair/price-1,future/price-1
            errors.append(abs(predicted-realized))
            directional.append((predicted>=0)==(realized>=0))
    return {'observations':len(errors),
            'mae':round(sum(errors)/len(errors),4) if errors else None,
            'directional':round(sum(directional)/len(directional),4) if errors else None}


def dated_calendar_pairs(snapshots,horizon,tolerance_days=3):
    """Yield start date and the first eligible date *after* horizon."""
    days=sorted(snapshots)
    for start_day in days:
        earliest=start_day+timedelta(days=horizon)
        latest=earliest+timedelta(days=tolerance_days)
        future=next((d for d in days if earliest<=d<=latest),None)
        if future is not None:
            yield start_day,snapshots[start_day],snapshots[future]


def calendar_pairs(snapshots,horizon,tolerance_days=3):
    """Legacy two-card-map interface used by earlier contract tests."""
    for _,start,end in dated_calendar_pairs(snapshots,horizon,tolerance_days):
        yield start,end


def load_snapshots(folder,versions=None):
    """Read immutable observations and optionally their source model version."""
    snapshots={}
    for path in sorted(folder.glob('market-*.json')):
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
            day=date.fromisoformat(payload['date'])
        except (KeyError,TypeError,ValueError,json.JSONDecodeError) as exc:
            raise ValueError(f'Invalid dated snapshot {path}: {exc}') from exc
        if day.isoformat() not in path.name:
            raise ValueError(f'Snapshot filename/date mismatch: {path.name} vs {day}')
        if day in snapshots:
            raise ValueError(f'Duplicate dated snapshot: {day}')
        cards=payload.get('cards')
        if not isinstance(cards,dict):
            raise ValueError(f'Invalid card map: {path}')
        snapshots[day]=cards
        if versions is not None:
            versions[day]=str(payload.get('modelVersion') or 'unknown-legacy')
    return snapshots


def build_report(snapshots,versions,*,generated_at=None,
                 min_start_days=MIN_START_DAYS,
                 min_observations=MIN_OBSERVATIONS):
    models=sorted(set(versions.values()))
    reports=[]
    for horizon in HORIZONS:
        dates=list(dated_calendar_pairs(snapshots,horizon))
        by_model=[]
        for model in models:
            group=[(start,end) for day,start,end in dates
                   if versions.get(day,'unknown-legacy')==model]
            metrics={}
            for currency,market_key,fair_key in (
                ('EUR','marketEUR','fairEUR'),('USD','market','fair')
            ):
                valid_dates=sum(any(valid_row(c,end[cid],market_key,fair_key)
                                    for cid,c in start.items() if cid in end)
                                for start,end in group)
                observed=evaluate(group,market_key,fair_key)
                if len(group)<min_start_days or valid_dates<min_start_days or (
                    observed['observations']<min_observations
                ):
                    metrics[currency]={
                        'status':'pending','observations':observed['observations'],
                        'eligibleStartDates':valid_dates,
                        'mae':None,'directional':None,
                        'reason':(
                            f'Need >= {min_start_days} distinct independent dated start snapshots '
                            f'and >= {min_observations} matched forecast/outcome observations'
                        ),
                    }
                else:
                    metrics[currency]={
                        **observed,'status':'exploratory-guide-price-backtest',
                        'eligibleStartDates':valid_dates,
                        'reason':'Price-guide changes are not independently proven sale returns',
                    }
            by_model.append({
                'modelVersion':model,
                'candidateDatePairs':len(group),
                'currencies':metrics,
            })
        reports.append({'horizonDays':horizon,'byModel':by_model})
    days=sorted(snapshots)
    return {
        'schemaVersion':1,
        'generatedAt':generated_at or datetime.now(timezone.utc).isoformat(),
        'snapshots':len(days),
        'earliestSnapshot':days[0].isoformat() if days else None,
        'latestSnapshot':days[-1].isoformat() if days else None,
        'modelVersions':models,
        'horizons':reports,
        'notes':[
            'Results are isolated by the originating snapshot modelVersion.',
            'No future snapshot before the requested calendar horizon is used.',
            'A changed modelVersion never rewrites past forecast snapshots.',
            'At least three different start dates and 30 matched observations are required before any exploratory score appears.',
            'EUR and USD never mix; guide price changes are not verified completed sales or realizable investment returns.',
        ],
    }


def main():
    versions={}
    snapshots=load_snapshots(SNAP,versions=versions)
    report=build_report(snapshots,versions)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Version-aware backtest',report['snapshots'],'snapshots',
          report['modelVersions'])
    for horizon in report['horizons']:
        for model in horizon['byModel']:
            print(horizon['horizonDays'],'calendar days',model['modelVersion'],
                  {cc:(info['status'],info['observations'])
                   for cc,info in model['currencies'].items()})
    if not snapshots:
        print('Pending: no dated market snapshots have been captured yet')
    return snapshots


if __name__=='__main__':
    main()
