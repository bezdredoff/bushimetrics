"""Unit tests for hosted Pages freshness and build identity; no internet requests."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tests"))
from hosted_pages_smoke import app_ref, clean_base, published_probe


class HostedPagesContracts(unittest.TestCase):
    def setUp(self):
        self.base="https://bezdredoff.github.io/bushimetrics/"
        self.html='<html><head><title>BushiMetrics</title></head><body><script src="assets/app.js?v=build49"></script></body></html>'
        self.bootstrap={"generatedAt":"2026-10-17T12:00:00+00:00",
                        "counts":{"total":31272},"jpCounts":{"total":63675}}

    def fetcher(self, html=None, data=None):
        def get(url):
            if "index.html" in url:
                return html if html is not None else self.html
            return json.dumps(data if data is not None else self.bootstrap)
        return get

    def test_match_current_index_and_data(self):
        report=published_probe(self.base,self.html,self.bootstrap,get=self.fetcher())
        self.assertEqual(report["failures"],[])
        self.assertEqual(report["deployedBundle"],"assets/app.js?v=build49")

    def test_old_pages_branch_is_reported(self):
        old=self.html.replace("assets/app.js?v=build49","assets/app.js")
        report=published_probe(self.base,self.html,self.bootstrap,get=self.fetcher(html=old))
        self.assertFalse(all(row["ok"] for row in report["checks"]))
        self.assertIn("old branch",report["failures"][0])

    def test_older_bootstrap_and_missing_jp(self):
        old={**self.bootstrap,"generatedAt":"2026-10-16T09:00:00+00:00",
             "jpCounts":{"total":63673}}
        result=published_probe(self.base,self.html,self.bootstrap,get=self.fetcher(data=old))
        self.assertEqual(len(result["failures"]),2)
        self.assertIn("JP catalog count",result["failures"][0])

    def test_unreachable_or_corrupted_pages_is_failure(self):
        result=published_probe(self.base,self.html,self.bootstrap,
            get=lambda url: (_ for _ in ()).throw(OSError("connection refused")))
        self.assertEqual(len(result["failures"]),1)
        self.assertIn("connection refused",result["failures"][0])

    def test_url_and_bundle_normalization(self):
        self.assertEqual(clean_base(self.base.rstrip("/")),self.base)
        self.assertEqual(app_ref(self.html),"assets/app.js?v=build49")
        self.assertIsNone(app_ref("<script src='unrelated.js'>"))
        with self.assertRaises(ValueError):
            clean_base("http://bezdredoff.github.io/bushimetrics")


if __name__=="__main__":
    unittest.main()
