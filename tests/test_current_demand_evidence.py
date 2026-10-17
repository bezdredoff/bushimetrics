"""Current market heat and model liquidity cannot rely on stale copied quotes.

Only dated sales and independently stamped fresh ask inventory can support
cross-sectional pressure. Synthetic fixtures never become market observations.
"""
import copy
import sys
import unittest
from datetime import date,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_catalog import (
    attach_market_pressure,observed_activity_inputs,score,
    audit_current_demand,
)

TODAY=date(2026,10,17)


def card(code='EBP01-001',sales=12,asks=6,sold_on=TODAY,ask_on=TODAY):
    return {
        'id':code,'code':code,'game':'palworld','language':'EN',
        'set':'EBP01','name':'Imaginary fixture Pal','rarity':'RR',
        'availability':'released',
        'market':20.0,'marketKind':'bare',
        'marketConfidence':'HIGH','marketStale':False,
        'priceSource':'Palworld Prices — completed-sale median',
        'palworldPricesCardId':'pal-BP01-001',
        'marketSourceUrl':'https://palworldprices.com/cards/ebp01/001-imaginary/',
        'marketAsOf':sold_on.isoformat() if sold_on else None,
        'marketAskAsOf':ask_on.isoformat() if ask_on else None,
        'marketBasisWindow':'30d','salesInBasis':sales,
        'salesInWindow':sales,'marketAskCount':asks,
    }


class CurrentMarketEvidenceTests(unittest.TestCase):
    def test_fresh_dated_sales_and_asks_support_activity(self):
        c=card()
        self.assertEqual(observed_activity_inputs(c,TODAY),
                         ((12.0,6.0),'qualified-current-sales-and-asks'))
        attach_market_pressure([c],TODAY)
        self.assertAlmostEqual(c['demandPressure'],66.7)
        self.assertIsNone(c['marketHeatPercentile'])
        self.assertEqual(c['demandPressureStatus'],
                         'qualified-insufficient-heat-cohort')
        score(c,{}, {},[])
        self.assertEqual(c['liquidityEvidenceStatus'],
                         'fresh-dated-sales-and-inventory')
        self.assertGreater(c['modelFactors']['liquidity'],25)

    def test_stale_quote_must_not_claim_current_pressure_or_liquidity(self):
        c=card(sold_on=TODAY-timedelta(days=30),ask_on=TODAY)
        attach_market_pressure([c],TODAY)
        self.assertIsNone(c['demandPressure'])
        self.assertIsNone(c['marketHeatPercentile'])
        self.assertEqual(c['demandPressureStatus'],'stale-or-undated-sales')
        score(c,{}, {},[])
        self.assertEqual(c['modelFactors']['liquidity'],25)
        self.assertEqual(c['liquidityEvidenceStatus'],
                         'neutral-prior-no-current-activity')
        self.assertEqual(c['momentum'],50)

    def test_provider_explicit_stale_overrides_young_capture(self):
        c=card()
        c['marketStale']=True
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'stale-or-undated-sales')

    def test_undated_asks_are_not_fresh_inventory(self):
        c=card(ask_on=None)
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'undated-or-future-ask-inventory')
        attach_market_pressure([c],TODAY)
        self.assertIsNone(c['demandPressure'])
        self.assertNotIn('demandPressureSales',c)

    def test_incompatible_inventory_and_sale_dates_do_not_coexist(self):
        c=card(sold_on=TODAY,ask_on=TODAY-timedelta(days=10))
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'sales-and-asks-not-contemporaneous')

    def test_stale_inventory_does_not_count_even_for_fresh_sales(self):
        c=card(ask_on=TODAY-timedelta(days=20))
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'stale-ask-inventory')

    def test_future_asks_are_not_current_observations(self):
        c=card(ask_on=TODAY+timedelta(days=1))
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'undated-or-future-ask-inventory')

    def test_no_source_sale_sample_cannot_use_previously_copied_counts(self):
        c=card(sales=500,asks=1)
        c['priceSource']='TCGCSV / TCGplayer price guide'
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'no-attributed-completed-sale-sample')

    def test_zero_live_listings_cannot_generate_fake_hottest_market(self):
        c=card(sales=100,asks=0)
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'zero-sales-or-available-asks')
        attach_market_pressure([c],TODAY)
        self.assertIsNone(c['marketHeatPercentile'])

    def test_counts_nonfinite_and_unknown_sales_window_fail_closed(self):
        for sales,asks in ((float('nan'),4),(5,float('inf')),(-4,6),(True,5)):
            c=card(sales=sales,asks=asks)
            with self.subTest(sales=sales,asks=asks):
                self.assertIn(observed_activity_inputs(c,TODAY)[1],
                              ('missing-or-invalid-sales-asks',
                               'zero-sales-or-available-asks'))
        c=card()
        c['marketBasisWindow']='unknown'
        self.assertEqual(observed_activity_inputs(c,TODAY)[1],
                         'unknown-sales-window')

    def test_heat_midrank_ties_are_identical_regardless_of_card_order(self):
        cards=[
            card(code=f'EBP01-{i:03d}',sales=10,asks=10) for i in range(12)
        ]
        attach_market_pressure(cards,TODAY)
        first={c['id']:(c['marketHeatPercentile'],c['marketHeatLabel'])
               for c in cards}
        self.assertEqual({x[0] for x in first.values()},{50})
        self.assertEqual({x[1] for x in first.values()},{'Neutral'})
        attach_market_pressure(list(reversed(cards)),TODAY)
        self.assertEqual(first,{c['id']:(c['marketHeatPercentile'],
                                        c['marketHeatLabel']) for c in cards})

    def test_unrelated_stale_records_cannot_change_qualified_heat_ranks(self):
        valid=[card(code=f'EBP01-{i:03d}',sales=i+2,asks=5) for i in range(10)]
        attach_market_pressure(valid,TODAY)
        reference={c['id']:c['marketHeatPercentile'] for c in valid}
        stale=[card(code=f'ES-OLD-{i}',sales=99999,asks=1,
                    sold_on=TODAY-timedelta(days=45)) for i in range(500)]
        attach_market_pressure(stale+valid,TODAY)
        self.assertEqual(reference,{c['id']:c['marketHeatPercentile']
                                    for c in valid})
        self.assertTrue(all(c['marketHeatPercentile'] is None for c in stale))

    def test_repeated_recomputation_clears_previously_assigned_heat(self):
        cards=[card(code=f'TD01-{i:03d}') for i in range(15)]
        attach_market_pressure(cards,TODAY)
        self.assertIsNotNone(cards[0]['marketHeatPercentile'])
        for c in cards:
            c['marketAskAsOf']=None
        attach_market_pressure(cards,TODAY)
        self.assertTrue(all(c.get('marketHeatPercentile') is None for c in cards))
        self.assertTrue(all('demandPressureAsks' not in c for c in cards))

    def test_stale_sale_counts_cannot_boost_investment_liquidity(self):
        stale=card(sales=9000,asks=9000,
                   sold_on=TODAY-timedelta(days=30),ask_on=TODAY)
        low=card(sales=1,asks=1,
                 sold_on=TODAY-timedelta(days=30),ask_on=TODAY)
        for c in (stale,low):
            attach_market_pressure([c],TODAY)
            score(c,{}, {},[])
        self.assertEqual(stale['investment'],low['investment'])
        self.assertEqual(stale['modelFactors']['liquidity'],25)
        self.assertEqual(stale['momentumEvidenceStatus'],
                         'neutral-prior-no-current-independent-movement')

    def test_explicit_status_audit_cannot_invent_market_heat(self):
        a=card(ask_on=None)
        b=card(sold_on=TODAY-timedelta(days=30))
        attach_market_pressure([a,b],TODAY)
        audit=audit_current_demand([a,b],generated_at='2026-10-17T17:00:00Z')
        self.assertEqual(audit['eligibleDemandRatios'],0)
        self.assertEqual(audit['eligibleCrossSectionalHeat'],0)
        self.assertEqual(audit['exclusionReasons']['undated-or-future-ask-inventory'],1)
        self.assertEqual(audit['exclusionReasons']['stale-or-undated-sales'],1)


if __name__=='__main__':
    unittest.main()
