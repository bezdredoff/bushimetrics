"""BushiMetrics data-contract and browser-artwork regression checks.

Run: python -m unittest discover -s tests -p 'test_*.py'
Uses only the Python standard library; never contacts image hosts or price APIs.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CatalogContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = json.loads((ROOT / 'data/web/bootstrap.json').read_text(encoding='utf-8'))
        cls.manifest = json.loads((ROOT / 'data/web/manifest.json').read_text(encoding='utf-8'))
        cls.jp_meta = json.loads((ROOT / 'data/catalog-weiss-jp-meta.json').read_text(encoding='utf-8'))
        cls.app = (ROOT / 'assets/app.js').read_text(encoding='utf-8')
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')

    def test_catalog_counts_match_manifest(self):
        sets = self.manifest['sets']
        self.assertTrue(sets)
        self.assertEqual(len({x['key'] for x in sets}), len(sets))
        self.assertEqual(sum(x['total'] for x in sets if x['language'] == 'JP'), self.jp_meta['counts']['total'])
        self.assertEqual(sum(x['total'] for x in sets if x['language'] == 'EN'), self.bootstrap['counts']['total'])

    def test_no_invented_jp_market_coverage(self):
        jp = [x for x in self.manifest['sets'] if x['language'] == 'JP']
        self.assertTrue(jp)
        self.assertEqual(self.jp_meta['counts']['pricedAny'], 0)
        self.assertTrue(all(x['priced'] == 0 and x['priceCoverage'] == 0 for x in jp))

    def test_coverage_never_exceeds_total(self):
        for entry in self.manifest['sets']:
            with self.subTest(entry=entry['key']):
                self.assertGreaterEqual(entry['total'], entry['priced'])
                self.assertGreaterEqual(entry['total'], entry['imaged'])
                self.assertTrue(0 <= entry['priceCoverage'] <= 100)
                self.assertTrue(0 <= entry['imageCoverage'] <= 100)

    def test_bootstrap_has_cards_and_set_links(self):
        keys = {x['key'] for x in self.manifest['sets']}
        cards = self.bootstrap['cards']
        self.assertGreater(len(cards), 200)
        self.assertTrue(all(c.get('i') and c.get('k') in keys for c in cards))

    def test_official_image_fallback_is_not_bypassed(self):
        # Previous regression: eagerly changing every URL to /cardlist/ broke artwork.
        self.assertIn("img.dataset.artFallback = 'cardlist'", self.app)
        self.assertIn("img.dataset.artFallback = 'relay'", self.app)
        self.assertIn("'/wordpress/wp-content/images/cardlist/'", self.app)
        self.assertLess(self.app.index("img.dataset.artFallback = 'cardlist'"),
                        self.app.index("img.dataset.artFallback = 'relay'"))
        self.assertNotIn('preferredArtwork(c.image)', self.app)

    def test_app_bundle_and_required_panels_exist(self):
        self.assertIn('assets/app.js?v=', self.html)
        for name in ('renderMarket', 'renderCoverage', 'renderSets', 'renderPortfolio',
                     'renderCompare', 'renderBacktest', 'renderSources', 'renderCardHistory'):
            with self.subTest(name=name):
                self.assertIn('function ' + name, self.app)
        self.assertIn('search-jp.json', self.app)


if __name__ == '__main__':
    unittest.main()
