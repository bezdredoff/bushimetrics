"""TCGCSV USD guides must choose Normal/Foil for the identified rarity.

Fixture-only tests, no external TCGplayer calls.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich_market_tcgcsv import choose_price,finalize_candidates,subtype_kind


def row(subtype,price):
    return {'subTypeName':subtype,'marketPrice':price,'lowPrice':price}


class TcgcsvSubtypeIntegrityTests(unittest.TestCase):
    def test_common_rare_double_rare_choose_normal_not_foil(self):
        prices=[row('Foil',300),row('Normal',12)]
        for rarity in ('C','U','R','RR','TD','PR'):
            with self.subTest(rarity=rarity):
                selected,reason=choose_price(prices,rarity)
                self.assertEqual(selected['marketPrice'],12)
                self.assertEqual(reason,'preferred-normal')

    def test_premium_sp_ssp_sr_choose_foil(self):
        prices=[row('Normal',11),row('Holofoil',199)]
        for rarity in ('SP','SSP','SR','SEC','OFR','RRR'):
            with self.subTest(rarity=rarity):
                selected,reason=choose_price(prices,rarity)
                self.assertEqual(selected['marketPrice'],199)
                self.assertEqual(reason,'preferred-foil')

    def test_only_exact_code_subtype_kept_but_treatment_marked_unverified(self):
        regular,rbasis=choose_price([row('Foil',50)],'C')
        premium,pbasis=choose_price([row('Normal',8)],'SP')
        self.assertEqual(regular['marketPrice'],50)
        self.assertEqual(premium['marketPrice'],8)
        self.assertEqual(rbasis,'single-opposite-subtype-unverified-treatment')
        self.assertEqual(pbasis,'single-opposite-subtype-unverified-treatment')

    def test_unspecified_subtype_may_be_used_only_if_sole_price(self):
        chosen,why=choose_price([row('Unspecified',33)],'R')
        self.assertEqual(chosen['marketPrice'],33)
        self.assertEqual(why,'single-unspecified-subtype')
        self.assertEqual(choose_price([row('',10),row('Unspecified',30)],'R'),
                         (None,'ambiguous-unverified-subtypes'))

    def test_duplicate_same_kind_not_chosen_by_input_order(self):
        prices=[row('Normal',5),row('Normal',50),row('Foil',99)]
        self.assertEqual(choose_price(prices,'R'),(None,'ambiguous-normal-rows'))
        self.assertEqual(choose_price(list(reversed(prices)),'R'),
                         (None,'ambiguous-normal-rows'))

    def test_nonfinite_zero_or_missing_market_price_is_not_market(self):
        prices=[row('Normal',0),row('Normal',float('nan')),
                row('Normal',float('inf')),row('Foil',12)]
        selected,reason=choose_price(prices,'R')
        self.assertEqual(selected['marketPrice'],12)
        self.assertEqual(reason,'single-opposite-subtype-unverified-treatment')
        self.assertEqual(choose_price([row('Normal','')],'R'),(None,'missing-price'))

    def test_collector_code_collision_quarantines_both_product_ids(self):
        incoming={
            'FOO/001':{123:{'market':20},456:{'market':50}},
            'BAR/001':{789:{'market':15}},
        }
        kept,groups,duplicates,examples=finalize_candidates(incoming)
        self.assertEqual(kept,{'BAR/001':{'market':15}})
        self.assertEqual(groups,1)
        self.assertEqual(duplicates,1)
        self.assertEqual(examples,[{'collectorCode':'FOO/001',
                                    'productIds':[123,456]}])
        reverse={k:dict(reversed(list(v.items()))) for k,v in incoming.items()}
        self.assertEqual(finalize_candidates(reverse),finalize_candidates(incoming))

    def test_subtype_names_are_interpreted_case_insensitively(self):
        self.assertEqual(subtype_kind(row('Reverse HOLO',19)),'foil')
        self.assertEqual(subtype_kind(row('Regular',19)),'normal')
        self.assertEqual(subtype_kind(row(None,19)),'unknown')


if __name__=='__main__':
    unittest.main()
