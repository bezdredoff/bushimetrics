"""Cardmarket must not misattribute product/rarity prices to other printings.

Pure-fixture tests: no network access and no external card data are required.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich_market_cardmarket import (
    match_cardmarket, norm, normalized_code, product_identity
)


def catalog():
    return [
        {'code':'AA/W01-001','name':'A Hero','rarity':'SP','set':'Alpha Adventure'},
        {'code':'AA/W01-002','name':'A Hero','rarity':'RR','set':'Alpha Adventure'},
        {'code':'BB/W01-001','name':'A Hero','rarity':'SP','set':'Beta Adventure'},
        {'code':'CC/W01-003','name':'Unique Girl','rarity':'R','set':'Gamma Town'},
        {'code':'DD/W01-001','name':'Another One','rarity':'R','set':'Delta Story'},
    ]


def product(pid,name,*,number=None,rarity=None,expansion=None):
    return {'idProduct':pid,'name':name,'number':number,
            'rarity':rarity,'expansionName':expansion}


def price(pid,amount=10.0):
    return {'idProduct':pid,'trend':amount,'low':amount-1,
            'avg7':amount+2}


class CardmarketPhysicalMatchTests(unittest.TestCase):
    def test_explicit_unknown_code_never_falls_back_to_unique_name(self):
        matched,audit=match_cardmarket(catalog(),
            [product(1,'Unique Girl',number='XX/W01-003',
                     rarity='Rare',expansion='Gamma Town')],[price(1)])
        self.assertEqual(matched,{})
        self.assertEqual(audit['explicitNumberNotFound'],1)

    def test_explicit_rarity_conflict_quarantined(self):
        matched,audit=match_cardmarket(catalog(),
            [product(1,'A Hero',number='AA/W01-001',
                     rarity='Double Rare',expansion='Alpha Adventure')],
            [price(1,200)])
        self.assertEqual(matched,{})
        self.assertEqual(audit['explicitRarityConflict'],1)
        self.assertNotIn('AA/W01-001',matched)

    def test_exact_collector_id_accepted_with_matching_rarity(self):
        matched,audit=match_cardmarket(catalog(),
            [product(9,'Card title differs',number=' AA/W01-001 ',
                     rarity='Special Rare',expansion='Alpha Adventure')],
            [price(9,250)])
        self.assertEqual(matched['AA/W01-001']['marketEUR'],250)
        self.assertEqual(matched['AA/W01-001']['cardmarketMatch'],
                         'verified-collector-number-rarity')
        self.assertEqual(audit['matchedCards'],1)

    def test_source_constraints_are_not_ignored_in_name_fallback(self):
        inputs=[
            product(1,'A Hero',rarity='Special Rare',expansion='Alpha Adventure'),
            product(2,'Unique Girl',rarity='Rare',expansion='Beta Adventure'),
            product(3,'Unique Girl',rarity='Double Rare',expansion='Gamma Town'),
            product(4,'Unique Girl',rarity='Rare',expansion='Gamma Town'),
            product(5,'A Hero',rarity='Special Rare',expansion='Totally Different'),
        ]
        matched,audit=match_cardmarket(catalog(),inputs,[price(i) for i in range(1,6)])
        self.assertEqual(set(matched),{'AA/W01-001','CC/W01-003'})
        self.assertEqual(audit['matchedCards'],2)
        self.assertEqual(audit['unmatchedProducts'],3)

    def test_name_only_without_expansion_or_rarity_is_not_enough(self):
        matched,audit=match_cardmarket(catalog(),[
            product(1,'Unique Girl'),product(2,'A Hero')
        ],[price(1),price(2)])
        self.assertEqual(matched,{})
        self.assertEqual(audit['insufficientIdentity'],2)

    def test_collision_quarantines_all_products_regardless_of_order(self):
        inputs=[
            product(1,'A Hero',number='AA/W01-001',rarity='SP'),
            product(2,'A Hero',rarity='SP',expansion='Alpha Adventure'),
            product(3,'Another One',number='DD/W01-001',rarity='Rare')
        ]
        prices=[price(1,120),price(2,999),price(3,24)]
        first,audit=match_cardmarket(catalog(),inputs,prices)
        second,reversed_audit=match_cardmarket(catalog(),list(reversed(inputs)),prices)
        self.assertEqual(first,second)
        self.assertEqual(set(first),{'DD/W01-001'})
        self.assertEqual(first['DD/W01-001']['marketEUR'],24)
        self.assertEqual(audit['collisionCodeGroups'],1)
        self.assertEqual(audit['collisionProducts'],2)
        self.assertEqual(audit['collisionExamples'][0]['productIds'],[1,2])
        self.assertEqual(reversed_audit['collisionCodeGroups'],1)

    def test_same_vendor_product_id_twice_not_a_physical_collision(self):
        twice=product(8,'Another One',number='DD/W01-001',rarity='Rare')
        matched,audit=match_cardmarket(catalog(),[twice,twice],[price(8)])
        self.assertEqual(len(matched),1)
        self.assertEqual(audit['duplicateSourceRows'],1)
        self.assertEqual(audit['collisionCodeGroups'],0)

    def test_ambiguous_catalog_code_is_not_assumed_to_be_one_printing(self):
        cards=catalog()
        cards.append(dict(cards[0],rarity='SEC'))
        matched,audit=match_cardmarket(cards,
            [product(1,'A Hero',number='AA/W01-001',rarity='Special Rare')],
            [price(1)])
        self.assertEqual(matched,{})
        self.assertEqual(audit['explicitNumberAmbiguous'],1)

    def test_ambiguous_name_and_rarity_without_set_stay_unpriced(self):
        matched,audit=match_cardmarket(catalog(),
            [product(1,'A Hero',rarity='SP')],[price(1)])
        self.assertEqual(matched,{})
        self.assertEqual(audit['ambiguousProducts'],1)

    def test_missing_or_nonpositive_trend_not_a_price(self):
        matched,audit=match_cardmarket(catalog(),
            [product(1,'Another One',number='DD/W01-001')],
            [price(1,0)])
        self.assertFalse(matched)
        self.assertEqual(audit['invalidPriceRows'],1)
        self.assertFalse(norm(None))
        self.assertEqual(normalized_code(' aa/w01-001 '),'AA/W01-001')


if __name__=='__main__':
    unittest.main()
