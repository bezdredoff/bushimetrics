import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from market_evidence import cec, demand_pressure, recommended_window, hype, rip_ev, grading_ev, franchise_health


class EvidenceModelTests(unittest.TestCase):
    def test_cec_requires_provenance_and_real_probability(self):
        self.assertIsNone(cec(carton_price=1100, currency='EUR', probability_of_target=.2, sample_cartons=300)['value'])
        self.assertIsNone(cec(carton_price=1100, currency='EUR', rarity_hits_per_carton=2,
                              cards_in_rarity=10, sample_cartons=300, source='case breaks')['value'])
        measured = cec(carton_price=1100, currency='EUR', probability_of_target=.2,
                       sample_cartons=300, source='verified cases')
        self.assertEqual(measured['value'], 5500)
        self.assertEqual(measured['confidence'], 'high')
        self.assertEqual(measured['expectedCartons'], 5)

    def test_demand_pressure_and_liquidity_windows(self):
        self.assertEqual(recommended_window(40), 14)
        self.assertEqual(recommended_window(15), 30)
        self.assertEqual(recommended_window(5), 60)
        self.assertEqual(recommended_window(1), 90)
        self.assertIsNone(demand_pressure(completed_sales=1,available_inventory=0,window_days=90,source='sales')['value'])
        observed = demand_pressure(completed_sales=2,available_inventory=40,window_days=90,source='sales')
        self.assertEqual(observed['value'], .05)
        self.assertEqual(observed['confidence'], 'low')

    def test_hype_needs_historical_baseline(self):
        self.assertIsNone(hype(.1, [.02]*29, 'SP 500+', 'observations')['value'])
        result = hype(.1, [.02]*30, 'SP 500+', 'observations')
        self.assertEqual(result['value'], 100)
        self.assertEqual(result['ratioToBaseline'], 5)

    def test_rip_ev_requires_complete_distribution(self):
        a=[{'probability': .5,'soldPrice':20,'currency':'EUR'},
           {'probability': .5,'soldPrice':4,'currency':'EUR'}]
        self.assertEqual(rip_ev(a, 10, 'EUR', 'sales')['value'], 12)
        self.assertEqual(rip_ev(a, 10, 'EUR', 'sales')['netBeforeFees'], 2)
        self.assertIsNone(rip_ev(a[:1],10,'EUR','sales')['value'])
        self.assertIsNone(rip_ev([dict(a[0], currency='USD'),a[1]],10,'EUR','sales')['value'])

    def test_grading_cost_and_unknown_franchise(self):
        a=[{'probability': .8, 'netSoldPrice': 100, 'currency':'EUR'},
           {'probability': .2, 'netSoldPrice': 200, 'currency':'EUR'}]
        self.assertEqual(grading_ev(a, 30,'EUR','grade sales')['value'],90)
        self.assertIsNone(franchise_health({'activity':[1,2]},'source')['value'])


if __name__=='__main__':
    unittest.main()
