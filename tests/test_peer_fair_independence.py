"""Peer Fair Value must not depend on the target's own observed price.

Historical backtests are invalid if the feature engineering stage lets the
target price enter other subject observations' rarity normalization. Tests
cover both a live priced printing and a card with no own source price.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_catalog import attach_character_premium, attach_peer_fair_value


def fixture(target_eur=40.0, target_usd=None):
    rows=[]
    for idx,(subject,eur) in enumerate([
        ('Alice',target_eur),('Alice',42),('Alice',45),('Alice',47),
        ('Bob',30),('Bob',33),('Bob',36),('Bob',39),('Bob',34),('Bob',31)
    ]):
        price={'marketEUR':eur} if eur is not None else {}
        if idx==0 and target_usd is not None:
            price['market']=target_usd
        rows.append({
            'id':f'printing-{idx}','code':f'TST/EN-{idx:03}',
            'game':'weiss','set':'Fixture Set','rarity':'SP',
            'name':f'Quote, {subject}','cardType':'Character',
            'availability':'released', **price,
        })
    attach_character_premium(rows)
    attach_peer_fair_value(rows)
    return rows


class PeerFairLeaveOneOutTests(unittest.TestCase):
    def test_changing_own_eur_price_never_changes_own_fair_estimate(self):
        original=fixture(target_eur=40)[0]
        changed=fixture(target_eur=4000)[0]
        for key in ('peerFairEUR','fairValuePeerMedian','fairValuePeerCount',
                    'fairValueSubjectRatio','fairValueSubjectObservations',
                    'fairValueConfidence','fairValueDataBasis'):
            with self.subTest(key=key):
                self.assertEqual(original.get(key),changed.get(key))
        self.assertGreater(original['peerFairEUR'],0)
        self.assertEqual(original['fairValueMethod'],
                         'target-independent rarity peer × subject premium')
        self.assertEqual(original['fairValueConfidenceBasis'],
                         'peer sample size, not predictive accuracy')

    def test_target_can_be_unpriced_without_changing_peer_forecast(self):
        with_price=fixture(target_eur=40)[0]
        without_price=fixture(target_eur=None)[0]
        self.assertEqual(with_price['peerFairEUR'],without_price['peerFairEUR'])
        self.assertEqual(without_price['fairValueCurrency'],'EUR')

    def test_changing_target_usd_does_not_affect_eur_model(self):
        first=fixture(target_eur=40,target_usd=10)[0]
        second=fixture(target_eur=40,target_usd=999999)[0]
        self.assertEqual(first['peerFairEUR'],second['peerFairEUR'])
        self.assertNotIn('peerFairUSD',first)

    def test_unseen_subject_never_gets_fabricated_subject_premium(self):
        cards=fixture(40)
        cards[0]['name']='Unique character, Nobody'
        for c in cards:
            for key in ('_marketPeerRatio','_marketPeerMedian','_marketPeerCount',
                        'peerFairEUR','peerFairUSD','fairValueSubjectRatio'):
                c.pop(key,None)
        attach_character_premium(cards)
        attach_peer_fair_value(cards)
        self.assertIsNone(cards[0].get('peerFairEUR'))
        self.assertEqual(cards[0]['fairValueConfidence'],'None')

    def test_unreleased_printing_gets_no_peer_fair_value(self):
        cards=fixture(40)
        cards[0]['availability']='announced'
        for card in cards:
            for field in ('_marketPeerRatio','_marketPeerMedian','_marketPeerCount',
                          'peerFairEUR','peerFairUSD','fairValueSubjectRatio'):
                card.pop(field,None)
        attach_character_premium(cards)
        attach_peer_fair_value(cards)
        self.assertIsNone(cards[0].get('peerFairEUR'))
        self.assertEqual(cards[0]['fairValueConfidence'],'None')


if __name__=='__main__':
    unittest.main()
