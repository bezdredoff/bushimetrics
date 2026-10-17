"""Optional TCG API premium price guides must be exact, dated, and foil matched.

These fixtures are synthetic and do not request an API key or publish prices.
Source endpoint shapes follow https://tcgapi.dev/api/search/ and /api/cards/.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich_market_tcgapi import pick_candidate,price_row,exact_identity
from market_provenance import combine_usd_guide_sources

CODE='SFN/S108-E074SSP'
TARGET_RARITY='SSP'
TODAY=date(2026,10,17)


def card(identifier=101,code=CODE,rarity='Super Special Rare',name='A hero'):
    return {'id':identifier,'name':name,'number':code,'rarity':rarity,
            'game_slug':'weiss-schwarz','tcgplayer_id':927021}


def quoted(card_id=101,price=125,printing='Foil',asof='2026-10-16'):
    return {'card_id':card_id,'printing':printing,'market_price':price,
            'market_price_as_of':asof,'sales_volume':None}


class TcgApiPremiumIdentityTests(unittest.TestCase):
    def test_search_requires_exact_number_not_substring_in_title(self):
        payload={'data':[
            card(1,code='SFN/S108-E074',name=CODE),
            card(2,code='SFN/S108-E074SSP copy',name=CODE)
        ]}
        self.assertIsNone(pick_candidate(payload,CODE,TARGET_RARITY))
        self.assertFalse(exact_identity(payload['data'][0],CODE,TARGET_RARITY))

    def test_matches_full_code_and_rarity_even_when_fuzzy_result_first(self):
        results={'data':[
            card(1,code='SFN/S108-E074',name=CODE),
            card(2,code=CODE,rarity='SSP')
        ]}
        found=pick_candidate(results,CODE,TARGET_RARITY)
        self.assertEqual(found['id'],2)

    def test_duplicate_verified_catalog_id_candidates_refused(self):
        payload={'data':[card(101),card(102)]}
        self.assertIsNone(pick_candidate(payload,CODE,TARGET_RARITY))

    def test_rejects_same_code_different_rarity_and_foreign_game(self):
        wrong={'data':[card(101,rarity='Special Rare'),
                       dict(card(102),game_slug='pokemon')]}
        self.assertIsNone(pick_candidate(wrong,CODE,TARGET_RARITY))

    def test_selects_unique_foil_with_actual_price_publication_date(self):
        data={'data':[quoted(printing='Normal',price=10),
                      quoted(printing='Holofoil',price=250)]}
        selected=price_row(data,card_id=101,rarity=TARGET_RARITY,today=TODAY)
        self.assertEqual(selected['market_price'],250)
        self.assertEqual(selected['printing'],'Holofoil')

    def test_rejects_normal_only_or_undated_premium_prices(self):
        self.assertIsNone(price_row({'data':[quoted(printing='Normal')]},
                                    card_id=101,rarity=TARGET_RARITY,today=TODAY))
        self.assertIsNone(price_row({'data':[quoted(asof=None)]},
                                    card_id=101,rarity=TARGET_RARITY,today=TODAY))

    def test_rejects_future_or_stale_or_other_product_price(self):
        for candidate in (quoted(asof='2026-10-18'),
                          quoted(asof='2026-09-01'),quoted(card_id=102)):
            with self.subTest(candidate=candidate):
                self.assertIsNone(price_row({'data':[candidate]},
                               card_id=101,rarity=TARGET_RARITY,today=TODAY))

    def test_refuses_arbitrary_highest_or_first_foil_quote(self):
        first=quoted(price=25)
        second=quoted(price=250)
        self.assertIsNone(price_row({'data':[first,second]},
                          card_id=101,rarity=TARGET_RARITY,today=TODAY))
        self.assertIsNone(price_row({'data':[second,first]},
                          card_id=101,rarity=TARGET_RARITY,today=TODAY))

    def test_duplicate_same_quote_does_not_create_fake_ambiguity(self):
        r=quoted(price=99)
        chosen=price_row({'data':[r,dict(r)]},card_id=101,
                         rarity=TARGET_RARITY,today=TODAY)
        self.assertEqual(chosen['market_price'],99)

    def test_old_unqualified_cache_never_overwrites_baseline(self):
        baseline={CODE:{'market':35,'priceSource':'TCGCSV'}}
        legacy={CODE:{'market':900,'priceSource':'TCG API / TCGPlayer',
                      'marketAsOf':'2026-10-16'}}
        chosen,audit=combine_usd_guide_sources(baseline,legacy,today=TODAY)
        self.assertEqual(chosen[CODE]['market'],35)
        self.assertEqual(audit['tcgapiQualifiedSelections'],0)
        self.assertEqual(
            audit['tcgapiRejectedReasons']['unverified-source-card-or-physical-treatment'],1)

    def test_qualified_fresh_premium_guide_can_override_tcgcsv(self):
        baseline={CODE:{'market':35,'priceSource':'TCGCSV'}}
        verified={CODE:{
            'market':125,'priceSource':'TCG API / TCGPlayer price guide',
            'marketIdentityStatus':'exact-code-rarity-foil-dated',
            'targetCode':CODE,'targetRarity':'SSP',
            'marketAsOf':'2026-10-16','printing':'Foil',
        }}
        chosen,audit=combine_usd_guide_sources(baseline,verified,today=TODAY)
        self.assertEqual(chosen[CODE]['market'],125)
        self.assertEqual(audit['tcgapiQualifiedSelections'],1)
        self.assertEqual(chosen[CODE]['marketAsOf'],'2026-10-16')

    def test_stale_or_future_prices_cannot_overwrite_other_guide(self):
        base={CODE:{'market':35}}
        for asof in ('2026-09-01','2026-10-18',None):
            with self.subTest(asof=asof):
                provider={CODE:{
                    'market':199,'marketIdentityStatus':'exact-code-rarity-foil-dated',
                    'targetCode':CODE,'marketAsOf':asof,
                }}
                chosen,audit=combine_usd_guide_sources(base,provider,today=TODAY)
                self.assertEqual(chosen[CODE]['market'],35)
                self.assertEqual(audit['tcgapiQualifiedSelections'],0)

    def test_foreign_printing_target_code_is_rejected(self):
        base={CODE:{'market':35}}
        provider={CODE:{
            'market':199,'marketIdentityStatus':'exact-code-rarity-foil-dated',
            'targetCode':'SFN/S108-E073SSP','marketAsOf':'2026-10-16',
        }}
        chosen,_=combine_usd_guide_sources(base,provider,today=TODAY)
        self.assertEqual(chosen[CODE]['market'],35)


if __name__=='__main__':
    unittest.main()
