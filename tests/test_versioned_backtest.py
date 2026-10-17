"""Versioned walk-forward reports require real dates and independent observations."""
import json
import sys
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backtest import build_report,load_snapshots,valid_row


class VersionedBacktestTests(unittest.TestCase):
    def make(self,count=55):
        start=date(2026,1,1)
        snapshots={}
        versions={}
        for step in range(count):
            day=start+timedelta(days=step)
            snapshots[day]={
                f'item-{n}':{'marketEUR':100+step,
                             'fairEUR':125 if step<20 else 108,
                             'market':40+step,'fair':45}
                for n in range(35)
            }
            versions[day]='v0.7' if step<20 else 'v0.8'
        return snapshots,versions

    def test_forecast_remains_attributed_to_saved_original_version(self):
        snapshots,versions=self.make(55)
        report=build_report(snapshots,versions,generated_at='2026-10-17T00:00:00Z')
        h30=next(h for h in report['horizons'] if h['horizonDays']==30)
        by_version={m['modelVersion']:m for m in h30['byModel']}
        self.assertEqual(set(by_version),{'v0.7','v0.8'})
        self.assertEqual(by_version['v0.7']['candidateDatePairs'],20)
        self.assertEqual(by_version['v0.8']['candidateDatePairs'],5)
        self.assertEqual(by_version['v0.7']['currencies']['EUR']['status'],
                         'exploratory-guide-price-backtest')
        self.assertGreater(by_version['v0.7']['currencies']['EUR']['observations'],0)
        self.assertNotEqual(
            by_version['v0.7']['currencies']['EUR']['mae'],
            by_version['v0.8']['currencies']['EUR']['mae'])
        self.assertEqual(report['snapshots'],55)

    def test_scant_history_does_not_report_backtest_accuracy(self):
        snapshots,versions=self.make(31)
        report=build_report(snapshots,versions)
        for row in report['horizons']:
            for model in row['byModel']:
                for currency in ('EUR','USD'):
                    info=model['currencies'][currency]
                    self.assertEqual(info['status'],'pending')
                    self.assertIsNone(info['mae'])
                    self.assertIsNone(info['directional'])

    def test_validation_does_not_accept_nan_or_infinite_market_prices(self):
        c={'marketEUR':100,'fairEUR':float('nan')}
        self.assertFalse(valid_row(c,{'marketEUR':110},'marketEUR','fairEUR'))
        c['fairEUR']=float('inf')
        self.assertFalse(valid_row(c,{'marketEUR':110},'marketEUR','fairEUR'))
        c['fairEUR']=120
        self.assertTrue(valid_row(c,{'marketEUR':110},'marketEUR','fairEUR'))

    def test_reads_saved_model_version_without_rewriting_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'market-2026-01-01.json'
            row={'date':'2026-01-01','modelVersion':'v0.7',
                 'cards':{'print':{'marketEUR':20,'fairEUR':23}}}
            path.write_text(json.dumps(row),encoding='utf-8')
            original=path.read_bytes()
            versions={}
            found=load_snapshots(Path(tmp),versions)
            self.assertEqual(versions[date(2026,1,1)],'v0.7')
            self.assertEqual(found[date(2026,1,1)]['print']['marketEUR'],20)
            self.assertEqual(path.read_bytes(),original)

    def test_no_snapshots_has_no_invented_observations(self):
        report=build_report({}, {}, generated_at='2026-10-17T00:00:00Z')
        self.assertEqual(report['snapshots'],0)
        self.assertEqual(report['modelVersions'],[])
        self.assertTrue(all(not h['byModel'] for h in report['horizons']))


if __name__=='__main__':
    unittest.main()
