import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from snapshot_metrics import capture

class SnapshotImmutabilityTests(unittest.TestCase):
    def test_second_run_cannot_rewrite_training_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'data').mkdir()
            path=root/'data/catalog.json'
            path.write_text(json.dumps({'modelVersion':'v1','cards':[
                {'id':'released','availability':'released','marketEUR':20,'fairEUR':22},
                {'id':'unpriced','availability':'released'},
                {'id':'future','availability':'announced','market':400}
            ]}),encoding='utf-8')
            self.assertTrue(capture(root,'2026-10-16'))
            snap=root/'data/snapshots/market-2026-10-16.json'
            original=snap.read_bytes()
            result=json.loads(original)
            self.assertEqual(list(result['cards']),['released'])
            self.assertEqual(result['cards']['released']['marketEUR'],20)
            path.write_text(json.dumps({'modelVersion':'v2','cards':[
                {'id':'released','availability':'released','marketEUR':999,'fairEUR':1000}
            ]}),encoding='utf-8')
            self.assertFalse(capture(root,'2026-10-16'))
            self.assertEqual(snap.read_bytes(),original)
            self.assertTrue(capture(root,'2026-10-17'))
            next_snapshot=json.loads((root/'data/snapshots/market-2026-10-17.json').read_text())
            self.assertEqual(next_snapshot['cards']['released']['marketEUR'],999)

if __name__=='__main__':unittest.main()
