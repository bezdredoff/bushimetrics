#!/usr/bin/env python3
"""Evaluate curated evidence without scraping, guessing or filling missing values."""
import json
from datetime import datetime, timezone
from pathlib import Path
from market_evidence import cec, demand_pressure, hype, rip_ev, grading_ev, franchise_health
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'data/research_observations.json'
OUTPUT=ROOT/'data/research_status.json'
METRICS={'cec':cec,'demandPressure':demand_pressure,'historicalHype':hype,'ripEV':rip_ev,'gradingEV':grading_ev,'franchiseHealth':franchise_health}

def evaluate(payload):
    output={'schemaVersion':1,'generatedAt':datetime.now(timezone.utc).isoformat(),
            'records':[],'notice':'Missing is not zero. Estimates are not guaranteed returns.'}
    for record in payload.get('records',[]):
        if not all(record.get(k) for k in ('id','game','set')):
            raise ValueError('id, game and set required for every record')
        observed=record.get('observations') or {}
        metrics={}
        for name, model in METRICS.items():
            args=observed.get(name)
            if args is None:
                metrics[name]={'value':None,'status':'unavailable','reason':'No verified public observations supplied'}
            elif not isinstance(args,dict):
                raise ValueError(f"{record['id']}: invalid {name} input")
            else:
                try:metrics[name]=model(**args)
                except (ValueError, TypeError) as e:raise ValueError(f"{record['id']}: {name}: {e}") from e
        output['records'].append({'id':record['id'],'game':record['game'],'set':record['set'],'metrics':metrics})
    output['summary']={'records':len(output['records']),
        'availableByMetric':{name:sum(row['metrics'][name].get('value') is not None for row in output['records']) for name in METRICS}}
    return output

def main():
    data=json.loads(INPUT.read_text(encoding='utf-8'))
    if data.get('schemaVersion')!=1 or not isinstance(data.get('records'),list):
        raise ValueError('schemaVersion=1 and records[] required')
    report=evaluate(data)
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['summary'])

if __name__=='__main__':main()
