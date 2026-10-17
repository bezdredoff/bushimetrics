"""Per-card chart shards label saved captures separately from source publications."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_history_shards as history


class HistoricalEvidenceShardTests(unittest.TestCase):
    def test_legacy_undated_and_dated_guides_are_visibly_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            snaps=root/'snapshots'
            output=root/'history'
            snaps.mkdir()
            before={'date':'2026-01-01','modelVersion':'v0.7',
                    'cards':{'a-card':{'marketEUR':20,'fairEUR':24}}}
            now={'date':'2026-02-01','modelVersion':'v0.8','cards':{
                'a-card':{'marketEUR':22,'fairEUR':25,
                          'cardmarketAsOf':'2026-02-01T00:15:00Z',
                          'cardmarketProductId':1002,
                          'cardmarketMatch':'verified-collector-number-rarity',
                          'priceSourceEUR':'Cardmarket public daily price guide'},
                'b-card':{'market':30,'fair':40,
                          'marketAsOf':'2026-02-01',
                          'tcgplayerProductId':1234,
                          'marketSubtypeSelection':
                              'single-opposite-subtype-unverified-treatment',
                          'tcgcsvMatch':'exact-collector-number',
                          'priceSource':'TCGCSV / TCGplayer daily mirror'}
            }}
            for payload in (before,now):
                (snaps/f"market-{payload['date']}.json").write_text(
                    json.dumps(payload),encoding='utf-8')
            with patch.object(history,'SNAP',snaps),patch.object(history,'OUT',output):
                history.main()
            shard=json.loads((output/'a.json').read_text(encoding='utf-8'))
            points=shard['cards']['a-card']
            self.assertEqual(len(points),2)
            self.assertNotIn('ea',points[0])
            self.assertNotIn('ev',points[0])
            self.assertEqual(points[1]['ea'],'2026-02-01')
            self.assertEqual(points[1]['ev'],1)
            tcg=json.loads((output/'b.json').read_text(encoding='utf-8'))
            self.assertEqual(tcg['cards']['b-card'][0]['ua'],'2026-02-01')
            self.assertNotIn('uv',tcg['cards']['b-card'][0])
            meta=json.loads((output/'meta.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['snapshots'],2)


if __name__=='__main__':
    unittest.main()
