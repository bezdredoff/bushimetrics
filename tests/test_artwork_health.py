"""Bounded artwork-audit contracts. No external HTTP in unit tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_jp_artwork import (
    audit_card, candidates, choose_samples, looks_like_image, run
)


class ArtworkHealthContracts(unittest.TestCase):
    def test_legacy_url_preserves_order_and_relay_of_cardlist_retry(self):
        url="https://ws-tcg.com/wordpress/wp-content/images/p/py_s38/py_s38_001.png"
        variants=candidates(url)
        self.assertEqual([v for v,_ in variants], ["original","cardlist","relay"])
        self.assertEqual(variants[0][1], url)
        self.assertEqual(variants[1][1],
            "https://ws-tcg.com/wordpress/wp-content/images/cardlist/p/py_s38/py_s38_001.png")
        self.assertIn("images.weserv.nl/?url=", variants[2][1])
        self.assertIn("%2Fimages%2Fcardlist%2F", variants[2][1])
        self.assertEqual([v for v,_ in candidates(variants[1][1])], ["original","relay"])
        self.assertEqual(candidates("https://example.org/card.png"), [])

    def test_valid_magic_not_http_or_html_page(self):
        self.assertTrue(looks_like_image(b"\x89PNG\r\n\x1a\n" + b"0"*10))
        self.assertTrue(looks_like_image(b"\xff\xd8\xff" + b"0"*10))
        self.assertTrue(looks_like_image(b"RIFF\x10\x00\x00\x00WEBPxxxx"))
        self.assertFalse(looks_like_image(b"<html>200 OK but not an image</html>"))

    def test_fallback_hit_only_after_initial_failure(self):
        card={"originalUrl":
              "https://ws-tcg.com/wordpress/wp-content/images/d/dc_w01/test.png",
              "code":"D/01", "rarity":"R"}
        checked=[]
        def checker(url):
            checked.append(url)
            return {"ok":"/images/cardlist/" in url,
                    "httpStatus":200 if "/images/cardlist/" in url else 404,
                    "reason":"image-signature-valid" if "/images/cardlist/" in url else "http-error"}
        record=audit_card(card, checker=checker)
        self.assertEqual(record["workingVariant"],"cardlist")
        self.assertEqual(record["status"],"confirmed-in-sample")
        self.assertEqual(len(checked),2)
        self.assertEqual([c["variant"] for c in record["checks"]],["original","cardlist"])

    def test_ci_hotlink_denial_does_not_claim_asset_missing(self):
        card={"originalUrl":
              "https://ws-tcg.com/wordpress/wp-content/images/d/dc_w01/test.png"}
        result=audit_card(card,checker=lambda _:{"ok":False,"httpStatus":403,"reason":"http-error"})
        self.assertEqual(result["status"],"blocked-or-unverifiable")
        result=audit_card(card,checker=lambda _:{"ok":False,"httpStatus":404,"reason":"http-error"})
        self.assertEqual(result["status"],"sample-failed")

    def test_stratified_sample_and_offline_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sets=[]
            for n in range(4):
                rel=f"data/web/sets/jp/set-{n}.json"
                p=root/rel
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(json.dumps({"cards":[
                    {"id":f"printing-{n}", "c":f"CODE-{n}","r":"RR",
                     "im":"https://ws-tcg.com/wordpress/wp-content/images/z/test.png"}
                ]}),encoding="utf-8")
                sets.append({"key":f"set-{n}","language":"JP","path":rel,"name":f"Set {n}"})
            sets.append({"key":"en","language":"EN","path":"irrelevant"})
            cards,count=choose_samples({"sets":sets},root=root,limit=2)
            self.assertEqual(count,4)
            self.assertEqual([x["code"] for x in cards],["CODE-0","CODE-2"])
            result=run({"sets":sets},root=root,limit=2,offline=True)
            self.assertEqual(result["sampleCount"],2)
            self.assertEqual(result["summary"]["not-probed-offline"],2)
            self.assertEqual(result["summary"]["confirmed-in-sample"],0)


if __name__ == "__main__":
    unittest.main()
