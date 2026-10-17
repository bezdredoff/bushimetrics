"""Provider physical printings are distinct even for matching printed rarities.

Palworld Prices API documents pal-BP01-001 as a different physical source
identity from pal-BP01-001-RR, OSR and SSP. These tests use synthetic records.
They do not substitute made-up observations into the published catalog.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich_market_palworldprices import (
    target_code, target_identity, map_sale_rows, positive_price,
)
from market_provenance import choose_usd_market,is_completed_sale_sample,describe_usd_evidence


KNOWN={'EBP01-001','EBP01-001OSR','EBP01-001SSP','EBP01-002',
       'ETD02-001','ESOUL-001'}


def source(code='BP01-001',variant=None,*,median=15,card_id=None,kind='bare'):
    source_id='pal-'+code+('-'+variant if variant else '')
    return {
        'code':code,'variant':variant,'rarity':variant or 'RR',
        'cardId':card_id or source_id,
        'pageUrl':'https://palworldprices.com/cards/ebp01/001-example/',
        'headline':{
            'kind':kind,'medianUsd':median,'confidence':'HIGH',
            'salesInBasis':18,'salesInWindow':18,
            'basisWindow':'30d','method':'recency-weighted median',
        },
    }


class PalworldPhysicalIdentityTests(unittest.TestCase):
    def test_base_and_premium_have_distinct_exact_target_codes(self):
        cases=[
            (None,'EBP01-001'),('OSR','EBP01-001OSR'),
            ('SSP','EBP01-001SSP'),
        ]
        for variant,expected in cases:
            with self.subTest(variant=variant):
                code,method=target_identity(source(variant=variant),KNOWN)
                self.assertEqual(code,expected)
                self.assertIn('exact-printing',method)

    def test_explicit_rr_never_falls_back_to_same_rarity_base(self):
        row=source(variant='RR',median=999)
        code,reason=target_identity(row,KNOWN)
        self.assertIsNone(code)
        self.assertEqual(reason,'explicit-variant-absent-from-catalog')
        rows=[source(median=10),row]
        mapped,stats=map_sale_rows(rows,KNOWN,
                                   asof='2026-10-17',stale=False)
        self.assertEqual(mapped['EBP01-001']['market'],10)
        self.assertEqual(stats['rejectionReasons']
                         ['explicit-variant-absent-from-catalog'],1)
        self.assertEqual(stats['matched'],1)

    def test_variant_card_id_disagreement_is_quarantined(self):
        mismatched=source(variant='OSR',card_id='pal-BP01-001-SSP',median=850)
        code,reason=target_identity(mismatched,KNOWN)
        self.assertIsNone(code)
        self.assertEqual(reason,'source-cardid-variant-disagreement')

    def test_unknown_explicit_suffix_or_bad_source_identifier_is_not_base(self):
        row=source(variant='ALT',median=600)
        self.assertIsNone(target_code(row,KNOWN))
        self.assertEqual(target_identity(source(card_id=''),KNOWN)[0],'EBP01-001')
        missing=source()
        missing.pop('cardId')
        self.assertEqual(target_identity(missing,KNOWN)[1],
                         'missing-source-printing-id')
        unknown=source()
        unknown['variant']='R/SSP'
        self.assertEqual(target_identity(unknown,KNOWN)[1],
                         'invalid-source-variant')

    def test_japanese_source_code_normalizes_only_to_known_english_printing(self):
        self.assertEqual(target_identity(source(code='TD02-001'),KNOWN)[0],
                         'ETD02-001')
        self.assertEqual(target_identity(source(code='SOUL-001'),KNOWN)[0],
                         'ESOUL-001')
        self.assertEqual(target_identity(source(code='BP01-099'),KNOWN)[1],
                         'base-printing-absent-from-catalog')

    def test_two_source_rows_claiming_one_code_never_choose_higher_price(self):
        first=source(median=5)
        second=source(median=500)
        mapped,stats=map_sale_rows([first,second],KNOWN,asof='2026-10-17')
        self.assertNotIn('EBP01-001',mapped)
        self.assertEqual(stats['duplicateTargets'],1)
        self.assertEqual(stats['collisionCodeGroups'],1)
        self.assertEqual(stats['rejectionReasons']['colliding-source-printing-rows'],2)
        backward,_=map_sale_rows([second,first],KNOWN,asof='2026-10-17')
        self.assertEqual(backward,mapped)

    def test_none_and_asks_never_turn_into_sold_market_price(self):
        row=source(kind='none',median=None)
        row['asks']={'n':10,'lowUsd':600}
        mapped,stats=map_sale_rows([row],KNOWN,asof='2026-10-17')
        self.assertIsNone(mapped['EBP01-001'].get('market'))
        self.assertEqual(mapped['EBP01-001']['marketAskLow'],600)
        self.assertEqual(stats['priced'],0)

    def test_thin_price_retains_source_qualifier(self):
        row=source(kind='thin',median=20)
        row['headline']['qualifier']='Thin confirmed sample'
        mapped,stats=map_sale_rows([row],KNOWN,asof='2026-09-17',stale=True)
        record=mapped['EBP01-001']
        self.assertEqual(record['marketQualifier'],'Thin confirmed sample')
        self.assertTrue(record['marketStale'])
        self.assertEqual(record['palworldMatch'],'exact-printing-cardid-base')
        self.assertEqual(record['marketAsOf'],'2026-09-17')
        self.assertEqual(stats['priced'],1)

    def test_invalid_nonfinite_or_negative_market_not_imputed(self):
        self.assertIsNone(positive_price(float('nan')))
        self.assertIsNone(positive_price(float('inf')))
        self.assertIsNone(positive_price(-3))
        mapped,_=map_sale_rows([source(median=-42)],KNOWN,asof='2026-10-17')
        self.assertNotIn('market',mapped['EBP01-001'])


class UsdSourcePriorityTests(unittest.TestCase):
    def setUp(self):
        mapped,_=map_sale_rows([source(median=150)],KNOWN,asof='2026-10-16')
        self.sale=mapped['EBP01-001']
        self.guide={
            'market':200,'priceSource':'TCGCSV / TCGplayer daily mirror',
            'marketAsOf':None,'marketSubtype':'Foil',
        }

    def test_completed_sale_cannot_be_overwritten_by_guide(self):
        selected,_=choose_usd_market('EBP01-001',
            {'EBP01-001':self.guide},{'EBP01-001':self.sale},{},{})
        self.assertEqual(selected['market'],150)
        self.assertEqual(selected['palworldPricesCardId'],'pal-BP01-001')
        self.assertEqual(selected['marketSelectionReason'],
                         'completed-sales-preferred-over-provider-guide')
        self.assertEqual(selected['marketEvidenceStatus'] if 'marketEvidenceStatus' in selected else
                         describe_usd_evidence(selected)['marketEvidenceStatus'],
                         'completed-sale-sample')

    def test_when_sales_are_unpriced_a_provider_guide_can_be_used(self):
        row=dict(self.sale)
        row.pop('market')
        selected,_=choose_usd_market('EBP01-001',
            {'EBP01-001':self.guide},{'EBP01-001':row},{},{})
        self.assertEqual(selected['market'],200)
        self.assertNotIn('palworldPricesCardId',selected)

    def test_untrusted_sale_like_url_does_not_earn_completed_sale_status(self):
        fake=dict(self.sale,marketSourceUrl='https://example.org/sale',
                  palworldPricesCardId='invented')
        self.assertFalse(is_completed_sale_sample(fake))
        chosen,_=choose_usd_market('EBP01-001',
            {'EBP01-001':self.guide},{'EBP01-001':fake},{},{})
        self.assertEqual(chosen['market'],200)
        self.assertNotEqual(describe_usd_evidence(fake)['marketEvidenceStatus'],
                            'completed-sale-sample')

    def test_explicit_linked_manual_override_still_remains_atomic(self):
        manual={'EBP01-001':{
            'market':199,'marketSourceUrl':'https://example.org/sale/123',
            'marketAsOf':'2026-10-16','priceSource':'individually sourced',
        }}
        chosen,_=choose_usd_market('EBP01-001',
            {'EBP01-001':self.guide},{'EBP01-001':self.sale},manual,{})
        self.assertEqual(chosen['market'],199)
        self.assertNotIn('salesInBasis',chosen)
        self.assertEqual(chosen['marketSelectionReason'],
                         'explicit-linked-manual-override')


if __name__=='__main__':
    unittest.main()
