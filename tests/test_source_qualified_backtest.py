"""The backtest must never mistake daily re-downloads for new price evidence.

Every fixture contains a claimed source publication date and a provider product
identifier. Legacy and provisional guide entries must not be silently promoted.
No internet or user market data is necessary for these unit contracts.
"""
import sys
import unittest
from datetime import date,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from backtest import (
    build_report, outcome_exclusion, source_publication_date,
    stable_price_identity
)


def eur_row(day, *, pid=123,method='verified-collector-number-rarity',
            quoted=90):
    return {
        'marketEUR':quoted, 'fairEUR':120,
        'cardmarketProductId':pid, 'cardmarketMatch':method,
        'priceSourceEUR':'Cardmarket public daily price guide',
        'cardmarketAsOf':day.isoformat(),
    }


def usd_row(day, *, card_id=456,quoted=40):
    return {
        'market':quoted, 'fair':50,
        'marketEvidenceStatus':'completed-sale-sample',
        'priceSource':'Palworld Prices — completed-sale median',
        'marketKind':'bare',
        'palworldPricesCardId':card_id,
        'marketSourceUrl':f'https://palworldprices.com/cards/{card_id}',
        'salesInBasis':12,
        'marketAsOf':day.isoformat(),
    }


def report_for(start,end, currency='EUR'):
    first=date(2026,1,1)
    second=first+timedelta(days=30)
    snaps={
        first:{f'printing-{i}':start for i in range(40)},
        second:{f'printing-{i}':end for i in range(40)},
    }
    versions={first:'v0.8',second:'v0.9'}
    report=build_report(snaps,versions)
    currency_info=report['horizons'][0]['byModel'][0]['currencies'][currency]
    return currency_info


class SourcePublicationBacktestTests(unittest.TestCase):
    def setUp(self):
        self.start=date(2026,1,1)
        self.end=date(2026,1,31)

    def test_different_source_publication_dates_qualify_when_same_physical_id(self):
        initial=eur_row(self.start)
        future=eur_row(self.end,quoted=130)
        self.assertIsNone(outcome_exclusion(initial,future,'marketEUR','fairEUR',
                                            self.start,self.end,30))
        info=report_for(initial,future)
        self.assertEqual(info['status'],'pending')  # one independent start date
        self.assertEqual(info['observations'],40)
        self.assertEqual(info['eligibleStartDates'],1)
        self.assertEqual(info['exclusionReasons'],{})

    def test_replayed_guide_is_not_a_new_market_observation(self):
        initial=eur_row(self.start)
        stale=eur_row(self.start,quoted=130)  # different number, same underlying guide
        info=report_for(initial,stale)
        self.assertEqual(info['observations'],0)
        self.assertEqual(info['status'],'pending')
        self.assertIsNone(info['mae'])
        self.assertEqual(info['exclusionReasons']['stale-or-repeated-provider-observation'],40)

    def test_undated_tcgcsv_price_is_not_historical_evidence(self):
        initial={'market':40,'fair':50,
                 'priceSource':'TCGCSV / TCGplayer daily mirror',
                 'tcgcsvMatch':'exact-collector-number',
                 'tcgplayerProductId':99,'marketSubtypeSelection':'preferred-normal',
                 'marketRetrievedAt':'2026-01-01T03:00:00Z'}
        later=dict(initial,market=61,marketRetrievedAt='2026-01-31T03:00:00Z')
        info=report_for(initial,later,currency='USD')
        self.assertEqual(info['observations'],0)
        self.assertEqual(info['exclusionReasons']['undated-provider-observation'],40)

    def test_provisional_title_only_eur_never_counts_as_verified_printing(self):
        initial=eur_row(self.start,method='unique-normal-name-unverified-source-treatment')
        future=eur_row(self.end,method='unique-normal-name-unverified-source-treatment')
        info=report_for(initial,future)
        self.assertEqual(info['observations'],0)
        self.assertEqual(info['exclusionReasons']['missing-verified-physical-source-identity'],40)

    def test_changed_product_id_is_not_same_price_series(self):
        info=report_for(eur_row(self.start,pid=123),eur_row(self.end,pid=456))
        self.assertEqual(info['observations'],0)
        self.assertEqual(info['exclusionReasons']['changed-price-provider-or-physical-printing'],40)

    def test_future_source_date_not_available_at_initial_capture(self):
        wrong=eur_row(self.end)
        info=report_for(wrong,eur_row(self.end))
        self.assertEqual(info['observations'],0)
        self.assertEqual(info['exclusionReasons']['future-dated-source-observation'],40)

    def test_not_yet_reached_actual_horizon(self):
        start=eur_row(self.start)
        future=eur_row(self.start+timedelta(days=29))
        self.assertEqual(outcome_exclusion(start,future,'marketEUR','fairEUR',
                                          self.start,self.end,30),
                         'no-new-price-observation-after-horizon')

    def test_qualifying_completed_sale_estimate_is_still_exploratory(self):
        start=usd_row(self.start)
        end=usd_row(self.end,quoted=42)
        self.assertIsNone(outcome_exclusion(start,end,'market','fair',
                                            self.start,self.end,30))
        qualified=report_for(start,end,currency='USD')
        self.assertEqual(qualified['observations'],40)
        self.assertIsNone(qualified['mae'])
        self.assertEqual(qualified['status'],'pending')

    def test_legacy_v1_snapshots_with_just_prices_are_ineligible(self):
        start={'marketEUR':100,'fairEUR':115}
        end={'marketEUR':110}
        info=report_for(start,end)
        self.assertEqual(info['observations'],0)
        self.assertIsNone(info['mae'])
        self.assertEqual(info['exclusionReasons']['missing-verified-physical-source-identity'],40)

    def test_date_parser_is_never_the_file_capture_timestamp(self):
        self.assertEqual(source_publication_date('2026-01-01T07:12:00+0200'),
                         self.start)
        self.assertIsNone(source_publication_date(None))
        self.assertIsNone(source_publication_date('2026-22-99'))

    def test_provider_identity_rejects_unspecified_vendor_subtype(self):
        card=usd_row(self.start)
        self.assertEqual(stable_price_identity(card,'USD'),
                         ('palworldprices','456'))
        card={'market':40,'fair':50,
              'tcgcsvMatch':'exact-collector-number',
              'tcgplayerProductId':2,
              'marketSubtypeSelection':'single-opposite-subtype-unverified-treatment',
              'priceSource':'TCGCSV / TCGplayer daily mirror'}
        self.assertIsNone(stable_price_identity(card,'USD'))


if __name__=='__main__':
    unittest.main()
