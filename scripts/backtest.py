#!/usr/bin/env python3
"""Calendar-day holdout reports by the originating forecast model version.

Real observation dates and saved *start-day* prediction versions are immutable.
Future observed guide prices may come from a newer model run, but the forecast
is ALWAYS attributed to its own saved model version and currency.

A small handful of backtest matches never receives a publishable accuracy score.
Cardmarket/TCGCSV guides are not verified completed-sale returns.
"""
import json
from collections import Counter
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


def source_publication_date(value):
    """Parse an upstream provider date; never use a snapshot or fetch date."""
    if not isinstance(value,str) or len(value)<10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def stable_price_identity(row, currency):
    """Only the same source-backed physical product can be compared later.

    A collector code alone does NOT prove the same edition/subtype was quoted.
    Cardmarket title-only normal prices and a sole surprising TCGCSV subtype
    remain useful indicative guide quotes in the viewer, but are not trusted
    for a published model-accuracy statistic.
    """
    if currency=='EUR':
        method=str(row.get('cardmarketMatch') or '')
        pid=row.get('cardmarketProductId')
        if not method.startswith('verified-collector-number') or pid is None:
            return None
        if row.get('priceSourceEUR')!='Cardmarket public daily price guide':
            return None
        return ('cardmarket',str(pid))
    # A completed-sale sample is also only a provider estimate; there is
    # no guarantee that its underlying sale set changed on each API refresh.
    if (row.get('marketEvidenceStatus')=='completed-sale-sample'
            and str(row.get('priceSource') or '').startswith('Palworld Prices')
            and row.get('marketKind') in ('bare','thin')
            and row.get('palworldPricesCardId') is not None
            and isinstance(row.get('salesInBasis'),(int,float))
            and not isinstance(row.get('salesInBasis'),bool)
            and row['salesInBasis']>0
            and row.get('marketSourceUrl')):
        return ('palworldprices',str(row['palworldPricesCardId']))
    if (row.get('tcgcsvMatch')=='exact-collector-number'
            and str(row.get('priceSource') or '').startswith('TCGCSV')
            and row.get('tcgplayerProductId') is not None
            and row.get('marketSubtypeSelection') in
                ('preferred-normal','preferred-foil')):
        return ('tcgcsv',str(row['tcgplayerProductId']),
                row['marketSubtypeSelection'])
    return None


def outcome_exclusion(start,end,market_key,fair_key,start_day,end_day,horizon):
    """Return a machine-readable reason, or None for a defensible guide pair.

    A fresh *download* or a later snapshot containing an old guide is never
    an independent future observation. This check is intentionally stricter
    than the old numeric-only evaluate() helper preserved for raw test tools.
    """
    if not valid_row(start,end,market_key,fair_key):
        return 'invalid-or-missing-numeric-price-or-forecast'
    currency='EUR' if market_key=='marketEUR' else 'USD'
    first=stable_price_identity(start,currency)
    last=stable_price_identity(end,currency)
    if first is None or last is None:
        return 'missing-verified-physical-source-identity'
    if first!=last:
        return 'changed-price-provider-or-physical-printing'
    date_key='cardmarketAsOf' if currency=='EUR' else 'marketAsOf'
    first_date=source_publication_date(start.get(date_key))
    last_date=source_publication_date(end.get(date_key))
    if first_date is None or last_date is None:
        return 'undated-provider-observation'
    # A source date published after the capture cannot have been observed
    # without hindsight, even if the numeric price happens to be plausible.
    if first_date>start_day or last_date>end_day:
        return 'future-dated-source-observation'
    if start.get('marketStale' if currency=='USD' else 'marketEURStale'):
        return 'provider-explicitly-marked-stale'
    if end.get('marketStale' if currency=='USD' else 'marketEURStale'):
        return 'provider-explicitly-marked-stale'
    if (start_day-first_date).days>14 or (end_day-last_date).days>14:
        return 'stale-or-repeated-provider-observation'
    if last_date<=first_date or last_date<start_day+timedelta(days=horizon):
        return 'no-new-price-observation-after-horizon'
    return None


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
            yield start_day,snapshots[start_day],future,snapshots[future]


def calendar_pairs(snapshots,horizon,tolerance_days=3):
    """Legacy two-card-map interface used by earlier contract tests."""
    for _,start,_,end in dated_calendar_pairs(snapshots,horizon,tolerance_days):
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
            group=[(start_day,start,end_day,end)
                   for start_day,start,end_day,end in dates
                   if versions.get(start_day,'unknown-legacy')==model]
            metrics={}
            for currency,market_key,fair_key in (
                ('EUR','marketEUR','fairEUR'),('USD','market','fair')
            ):
                accepted=[]
                excluded=Counter()
                valid_dates=0
                for start_day,start,end_day,end in group:
                    first={}
                    future={}
                    for cid,current in start.items():
                        later=end.get(cid)
                        if later is None:
                            excluded['missing-future-card-printing']+=1
                            continue
                        reason=outcome_exclusion(
                            current,later,market_key,fair_key,
                            start_day,end_day,horizon
                        )
                        if reason is not None:
                            excluded[reason]+=1
                            continue
                        first[cid]=current
                        future[cid]=later
                    if first:
                        valid_dates+=1
                        accepted.append((first,future))
                observed=evaluate(accepted,market_key,fair_key)
                metric_common={
                    'observations':observed['observations'],
                    'eligibleStartDates':valid_dates,
                    'excludedComparisons':sum(excluded.values()),
                    'exclusionReasons':dict(sorted(excluded.items())),
                }
                if (valid_dates<min_start_days or
                        observed['observations']<min_observations):
                    metrics[currency]={
                        **metric_common,'status':'pending',
                        'mae':None,'directional':None,
                        'reason':(
                            f'Need >= {min_start_days} independently dated '
                            f'and source-qualified start snapshots and >= '
                            f'{min_observations} matched provider updates '
                            f'with stable physical printing identity'
                        ),
                    }
                else:
                    metrics[currency]={
                        **metric_common,'status':'exploratory-guide-price-backtest',
                        'mae':observed['mae'],
                        'directional':observed['directional'],
                        'reason':(
                            'Dated source-matched provider estimates, not '
                            'realized investment returns or completed-sale prices'
                        ),
                    }
            by_model.append({
                'modelVersion':model,
                'candidateDatePairs':len(group),
                'currencies':metrics,
            })
        reports.append({'horizonDays':horizon,'byModel':by_model})
    days=sorted(snapshots)
    return {
        'schemaVersion':2,
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
            'A captured copy of an older provider quote is not a fresh price observation.',
            'Both source dates must be present, within 14 days of their snapshots, non-future, and the later one must pass the requested calendar horizon.',
            'Both quotes must identify the same independently qualified provider product/physical printing.',
            'Legacy snapshots without the source identity/date remain immutable but are ineligible for future model-accuracy scoring.',
            'At least three independently dated start snapshots and 30 matched observations are required before exploratory scores appear.',
            'EUR and USD never mix; guide-price and rolling-sale estimates are not realized investment returns.',
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
