import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backtest import calendar_pairs, evaluate, load_snapshots


class CalendarBacktestTests(unittest.TestCase):
    def test_snapshot_index_is_not_elapsed_days(self):
        start=date(2026,1,1)
        snapshots={start+timedelta(days=n*2):{'one':{'marketEUR':100,'fairEUR':120}}
                   for n in range(31)}
        # 31 entries spanning 60 days do not imply a 30-step=30-day horizon.
        pairs=list(calendar_pairs(snapshots,30,tolerance_days=0))
        self.assertEqual(len(pairs),16)
        self.assertEqual(len(list(calendar_pairs(snapshots,90))),0)

    def test_future_must_not_precede_horizon(self):
        start=date(2026,1,1)
        data={start:{'one':{'market':100,'fair':110}},
              start+timedelta(days=29):{'one':{'market':102}},
              start+timedelta(days=31):{'one':{'market':103}}}
        pairs=list(calendar_pairs(data,30))
        self.assertEqual(len(pairs),1)
        self.assertEqual(evaluate(pairs,'market','fair')['observations'],1)
        self.assertEqual(evaluate(pairs,'marketEUR','fairEUR')['observations'],0)

    def test_true_gap_stays_pending(self):
        data={date(2026,1,1):{},date(2026,3,1):{}}
        self.assertEqual(list(calendar_pairs(data,30)),[])

    def test_snapshot_date_filename_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'market-2026-01-01.json').write_text(json.dumps(
                {'date':'2026-01-02','cards':{}}),encoding='utf-8')
            with self.assertRaises(ValueError):
                load_snapshots(Path(tmp))

    def test_never_scores_missing_or_nonpositive_prices(self):
        x=[({'a':{'market':100,'fair':120},'b':{'market':0,'fair':100}},
            {'a':{'market':110},'b':{'market':90}})]
        result=evaluate(x,'market','fair')
        self.assertEqual(result['observations'],1)
        self.assertEqual(result['mae'],0.1)


if __name__=='__main__':
    unittest.main()
