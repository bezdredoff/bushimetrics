#!/usr/bin/env python3
"""Verify the *deployed* GitHub Pages site, not just local http.server.

Checks that Pages serves the app bundle and data at least as recent as the
checked-out main catalog. Then tests Chromium on desktop and mobile, with
screenshots and a machine-readable report on failure.

Run:
  python tests/hosted_pages_smoke.py
  PAGES_BASE_URL=https://bezdredoff.github.io/bushimetrics/ python tests/hosted_pages_smoke.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_URL="https://bezdredoff.github.io/bushimetrics/"
USER_AGENT="BushiMetricsHostedSmoke/1.0 (+https://github.com/bezdredoff/bushimetrics)"
BROWSER_TIMEOUT=60000


def clean_base(url):
    parts=parse.urlsplit(url)
    if parts.scheme!="https" or not parts.netloc:
        raise ValueError("Hosted Pages URL must be a complete HTTPS origin")
    return parse.urlunsplit((parts.scheme,parts.netloc,parts.path.rstrip("/")+"/","",""))


def get_text(url, *, max_bytes=1_000_000):
    rq=request.Request(url,headers={
        "User-Agent":USER_AGENT,"Cache-Control":"no-cache",
        "Accept":"text/html,application/json;q=0.9,*/*;q=0.2"
    })
    with request.urlopen(rq,timeout=20) as response:
        if response.status!=200:
            raise ValueError(f"HTTP {response.status}: {url}")
        data=response.read(max_bytes+1)
        if len(data)>max_bytes:
            raise ValueError(f"Response exceeded {max_bytes} bytes: {url}")
        return data.decode("utf-8")


def app_ref(html):
    m=re.search(r'<script\s+src=["\']([^"\']*assets/app\.js(?:\?[^"\']*)?)["\']',html)
    return m.group(1) if m else None


def published_probe(base, expected_html, expected_bootstrap, get=get_text):
    """Don't equate a successful HTTP 200 with publication of the right build."""
    result={"base":base,"checks":[],"failures":[],"expectedBundle":app_ref(expected_html)}
    def check(name, ok, detail):
        result["checks"].append({"check":name,"ok":bool(ok),"detail":detail})
        if not ok:
            result["failures"].append(f"{name}: {detail}")
    try:
        published_html=get(parse.urljoin(base,"index.html")+"?bushi-pages-probe=1")
    except Exception as exc:
        check("published index reachable",False,str(exc))
        return result
    deployed_ref=app_ref(published_html)
    result["deployedBundle"]=deployed_ref
    check("published HTML identifies BushiMetrics",
          "<title>BushiMetrics</title>" in published_html,
          "index.html missing expected BushiMetrics title")
    check("current app bundle published",deployed_ref==result["expectedBundle"],
          f"deployed={deployed_ref!r}, expected={result['expectedBundle']!r}. "
          "Pages may be publishing an old branch instead of main.")
    try:
        payload=json.loads(get(parse.urljoin(base,"data/web/bootstrap.json")+"?bushi-pages-probe=1"))
    except Exception as exc:
        check("published catalog bootstrap reachable",False,str(exc))
        return result
    expected_count=int((expected_bootstrap.get("counts") or {}).get("total") or 0)
    deployed_count=int((payload.get("counts") or {}).get("total") or 0)
    expected_jp=int((expected_bootstrap.get("jpCounts") or {}).get("total") or 0)
    deployed_jp=int((payload.get("jpCounts") or {}).get("total") or 0)
    result["expected"]={"catalogCount":expected_count,"jpCount":expected_jp,
                        "generatedAt":expected_bootstrap.get("generatedAt")}
    result["deployed"]={"catalogCount":deployed_count,"jpCount":deployed_jp,
                        "generatedAt":payload.get("generatedAt")}
    check("published EN/Palworld catalog counts match",
          deployed_count==expected_count,
          f"deployed={deployed_count}, expected={expected_count}")
    check("published JP catalog count matches",
          deployed_jp==expected_jp,
          f"deployed={deployed_jp}, expected={expected_jp}")
    expected_date=expected_bootstrap.get("generatedAt")
    deployed_date=payload.get("generatedAt")
    check("published catalog generatedAt is not older than checkout",
          bool(deployed_date) and bool(expected_date) and deployed_date>=expected_date,
          f"deployed={deployed_date!r}, expected>={expected_date!r}")
    return result


def browser_check(base, output_dir):
    from playwright.sync_api import sync_playwright
    output=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        for label,viewport,mobile in (
            ("desktop",{"width":1365,"height":900},False),
            ("mobile",{"width":390,"height":844},True),
        ):
            ctx=browser.new_context(viewport=viewport,is_mobile=mobile,
                                    device_scale_factor=1,service_workers="block",
                                    accept_downloads=False)
            page=ctx.new_page()
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            try:
                page.goto(base+"?bushi-smoke="+str(int(time.time())),wait_until="domcontentloaded",
                          timeout=BROWSER_TIMEOUT)
                # catalogStatus is deliberately hidden by the app's CSS.
                # Waiting for visibility would time out on a correctly loaded page.
                page.wait_for_function(
                    "() => document.querySelector('#catalogStatus')?.textContent.includes('loaded printings')",
                    timeout=BROWSER_TIMEOUT)
                page.locator('[data-tab="cards"]').click(timeout=15000)
                page.locator("#cardGrid .card-tile").first.wait_for(timeout=BROWSER_TIMEOUT)
                count=page.locator("#cardGrid .card-tile").count()
                assert count>0,"No cards rendered"
                if not mobile:
                    page.locator('[data-preset="jp-weiss"]').click(timeout=15000)
                    page.wait_for_function(
                        "() => document.querySelector('#catalogStatus')?.textContent.includes('JP loaded')",
                        timeout=BROWSER_TIMEOUT)
                    page.locator("#search").fill("GZL/SE33-12")
                    page.wait_for_function(
                        "() => [...document.querySelectorAll('#cardGrid .card-tile')].filter(el => el.textContent.includes('GZL/SE33-12')).length === 2",
                        timeout=BROWSER_TIMEOUT)
                    page.locator("#cardGrid .card-tile").first.click()
                    page.locator("#viewer.open").wait_for(timeout=15000)
                    assert "GZL/SE33-12" in page.locator("#viewerMeta").inner_text()
                assert not errors,"JavaScript errors: "+"; ".join(errors[:5])
                output.append({"viewport":label,"ok":True,"cardsInFirstPage":count})
            except Exception as exc:
                output.append({"viewport":label,"ok":False,"reason":str(exc)[:700],
                               "jsErrors":errors[:5]})
                try:
                    page.screenshot(path=str(output_dir/f"hosted-{label}-failure.png"),full_page=True,
                                    timeout=5000)
                except Exception:
                    pass
            finally:
                ctx.close()
        browser.close()
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-url",default=os.environ.get("PAGES_BASE_URL",DEFAULT_URL))
    parser.add_argument("--output",type=Path,default=ROOT/"artifacts/hosted-pages-smoke.json")
    parser.add_argument("--skip-browser",action="store_true")
    args=parser.parse_args()
    output=args.output
    output.parent.mkdir(parents=True,exist_ok=True)
    report={"schemaVersion":1,"checkedAt":datetime.now(timezone.utc).isoformat(),
            "baseUrl":args.base_url,"passed":False,"probe":None,"browsers":[]}
    try:
        base=clean_base(args.base_url)
        expected_html=(ROOT/"index.html").read_text(encoding="utf-8")
        expected=json.loads((ROOT/"data/web/bootstrap.json").read_text(encoding="utf-8"))
        report["probe"]=published_probe(base,expected_html,expected)
        if not report["probe"]["failures"] and not args.skip_browser:
            report["browsers"]=browser_check(base,output.parent)
        report["passed"]=(not report["probe"]["failures"] and
                           all(x["ok"] for x in report["browsers"]))
        if args.skip_browser and not report["probe"]["failures"]:
            report["passed"]=True
    except Exception as exc:
        report["failure"]=str(exc)[:1200]
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=f"Hosted Pages acceptance: {'PASS' if report['passed'] else 'FAIL'}; {report['baseUrl']}"
    print(summary,flush=True)
    for bad in (report.get("probe") or {}).get("failures",[]):
        print("  Publication problem:",bad,flush=True)
    for tested in report["browsers"]:
        print(" ",tested["viewport"],"OK" if tested["ok"] else tested.get("reason"),flush=True)
    if report.get("failure"):
        print("  Error:",report["failure"],flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(f"### {summary}\n\n")
            for bad in (report.get("probe") or {}).get("failures",[]):
                f.write(f"- {bad}\n")
            for tested in report["browsers"]:
                f.write(f"- {tested['viewport']}: {'PASS' if tested['ok'] else 'FAIL'}\n")
    return 0 if report["passed"] else 1


if __name__=="__main__":
    sys.exit(main())
