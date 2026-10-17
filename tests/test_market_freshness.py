"""Market freshness never substitutes collection/fetch timestamps for provider dates."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from market_freshness import (
    audit_market_freshness, eur_evidence, freshness_status, source_group
)
from build_web_catalog import SEARCH_FIELDS, BOOT_EXTRA


class MarketFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,10,17)

    def test_date_states_and_fetched_eur_without_published_date(self):
        self.assertEqual(freshness_status('2026-10-16',today=self.day),'fresh')
        self.assertEqual(freshness_status('2026-09-17T12:00:00Z',today=self.day),'stale')
        self.assertEqual(freshness_status(None,today=self.day),'undated')
        self.assertEqual(freshness_status('2026-10-18',today=self.day),'invalid-or-future-date')
        facts=eur_evidence(None,'2026-10-17T12:00:00+00:00',today=self.day)
        self.assertIsNone(facts['marketEURAgeDays'])
        self.assertTrue(facts['marketEURStale'])
        self.assertEqual(facts['marketEURDateStatus'],'undated')
        self.assertEqual(facts['cardmarketRetrievedAt'],'2026-10-17T12:00:00+00:00')

    def test_age_is_measured_from_guide_date_only(self):
        facts=eur_evidence('2026-09-17T00:00:00Z','2026-10-17',today=self.day)
        self.assertEqual(facts['marketEURAgeDays'],30)
        self.assertTrue(facts['marketEURStale'])
        self.assertIn('not-completed-sales',facts['marketEUREvidenceStatus'])

    def test_distinct_currency_counts_and_providers(self):
        cards=[
            {'id':'a','availability':'released','market':17,'marketAsOf':'2026-09-17',
             'priceSource':'Palworld Prices — completed-sale median',
             'marketEUR':15,'cardmarketAsOf':'2026-10-16'},
            {'id':'b','availability':'released','market':100,'marketAsOf':None,
             'priceSource':'TCGCSV / TCGplayer daily mirror'},
            {'id':'c','availability':'released','marketEUR':22,
             'cardmarketAsOf':'2026-11-01'},
            {'id':'d','availability':'announced','market':200,'marketAsOf':'2026-10-16'},
            {'id':'e','availability':'released','market':None,'marketEUR':0}
        ]
        report=audit_market_freshness(cards,today=self.day,generated_at='2026-10-17T08:00:00Z')
        self.assertEqual(report['currencies']['USD'],{
            'priced':2,'fresh':0,'stale':1,'undated':1,'invalid-or-future-date':0
        })
        self.assertEqual(report['currencies']['EUR'],{
            'priced':2,'fresh':1,'stale':0,'undated':0,'invalid-or-future-date':1
        })
        self.assertEqual({p['name'] for p in report['providers']},{
            'Palworld Prices completed-sale sample','TCGCSV / TCGplayer price guide',
            'Cardmarket price guide'
        })
        self.assertEqual(report['generatedAt'],'2026-10-17T08:00:00Z')

    def test_full_browser_index_preserves_actual_price_provenance(self):
        for f in ('marketAsOf','cardmarketAsOf','marketEURAgeDays','marketEURStale',
                  'marketEURDateStatus','marketEvidenceStatus'):
            self.assertIn(f,SEARCH_FIELDS)
        for f in ('priceSource','priceSourceEUR','marketSourceUrl','marketRetrievedAt'):
            self.assertIn(f,BOOT_EXTRA)


if __name__=='__main__':
    unittest.main()
