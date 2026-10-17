"""Real Chromium smoke tests for the static GitHub Pages app.

Run after pip install playwright && python -m playwright install chromium:
python tests/browser_smoke.py
"""
import contextlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    server=subprocess.Popen([sys.executable,"-m","http.server",str(port),"--bind","127.0.0.1"],
                            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for i in range(60):
            try:
                with urlopen(f"http://127.0.0.1:{port}/",timeout=1) as response:
                    if response.status==200:break
            except Exception:time.sleep(.2)
        else:raise RuntimeError("Development web server did not start")
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
            page=browser.new_page(viewport={"width":1280,"height":900})
            errors=[]
            page.on("pageerror",lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}/",wait_until="domcontentloaded")
            # Wait for the *actual catalog*, not a status string changed by a failed request.
            page.wait_for_function(
                "() => document.querySelector('#catalogStatus').textContent.includes('loaded printings')",
                timeout=60000)
            assert "Failed to load" not in page.locator("#catalogStatus").inner_text()
            page.locator('[data-tab="cards"]').click()
            page.locator("#cardGrid .card-tile").first.wait_for(timeout=60000)
            card=page.locator("#cardGrid .card-tile").first
            card.click()
            page.locator("#viewer.open").wait_for(timeout=10000)
            assert page.locator("#viewerName").inner_text().strip()
            assert page.locator("#viewerBadges").inner_text().strip()
            stats=page.locator("#viewerStats").inner_text()
            assert "Carton Equivalent Cost" in stats
            assert "Historical HYPE" in stats
            assert "No verified observation" in stats
            page.locator("#watchBtn").click()
            assert page.locator("#watchBtn").inner_text()=="Watching"
            page.locator("#compareBtn").click()
            assert page.locator("#compareBtn").inner_text()=="In compare"
            page.locator("#portfolioQty").fill("2")
            page.locator("#portfolioCost").fill("10")
            page.locator("#savePortfolioBtn").click()
            assert page.locator("#portfolioCount").inner_text().strip() != "0"
            page.keyboard.press("Escape")
            page.locator('[data-tab="portfolio"]').click()
            assert page.locator("#portfolioTable").inner_text().strip()
            with page.expect_download() as portfolio_download:
                page.locator("#portfolioExportBtn").click()
            portfolio_backup=json.loads(Path(portfolio_download.value.path()).read_text(encoding="utf-8"))
            assert portfolio_backup["version"] == 1
            assert list(portfolio_backup["portfolio"].values())[0]["qty"] == 2
            page.locator('[data-tab="compare"]').click()
            assert page.locator("#compareGrid").inner_text().strip()
            page.locator('[data-tab="coverage"]').click()
            assert "Japanese source identity audit" in page.locator("#coverage").inner_text()
            assert page.locator("#jpIdentityAudit").inner_text().strip()
            assert "English source identity audit" in page.locator("#coverage").inner_text()
            assert page.locator("#enIdentityAudit").inner_text().strip()
            page.locator('[data-tab="backtest"]').click()
            backtest_text=page.locator("#backtestContent").inner_text()
            assert "Versioned 30 / 90 / 180-day holdouts" in backtest_text
            assert "Previous unsourced example values have been withheld" in backtest_text
            assert "No predictive accuracy has been established" in backtest_text or "pending" in backtest_text.lower()
            page.locator('[data-tab="sources"]').click()
            assert "Research model availability" in page.locator("#sourcesContent").inner_text()
            assert "Market source audit" in page.locator("#sourcesContent").inner_text()
            assert "Cardmarket printing identity audit" in page.locator("#sourcesContent").inner_text()
            assert "TCGplayer Normal / Foil audit" in page.locator("#sourcesContent").inner_text()
            assert "Palworld physical printing and completed sales" in page.locator("#sourcesContent").inner_text()
            assert "Optional premium Weiss TCG API source validation" in page.locator("#sourcesContent").inner_text()
            assert ("Exact source printings" in page.locator("#sourcesContent").inner_text() or
                    "Exact Palworld source-variant identity audit pending" in page.locator("#sourcesContent").inner_text())
            assert "Source subtype verification pending" in page.locator("#sourcesContent").inner_text() or "Quarantined duplicate product numbers" in page.locator("#sourcesContent").inner_text()
            assert "Mapping verification pending" in page.locator("#sourcesContent").inner_text() or "Quarantined code collisions" in page.locator("#sourcesContent").inner_text()
            assert "Market price-source freshness" in page.locator("#sourcesContent").inner_text()
            assert "Price guides are not completed sales" in page.locator("#sourcesContent").inner_text()
            assert "Missing independent source or card-level date" in page.locator("#sourcesContent").inner_text()
            # Card explorer pagination, CSV export and local backup round-trip.
            page.locator('[data-tab="cards"]').click()
            page.wait_for_function(
                "() => !document.querySelector('#catalogStatus').textContent.includes('bootstrap visible')",
                timeout=90000)
            page.locator("#resetFiltersBtn").click()
            page.locator("#pageSizeSelect").select_option("120")
            assert page.locator("#cardGrid .card-tile").count() == 120
            first_card=page.locator("#cardGrid .card-tile").first.get_attribute("data-id")
            page.locator("#nextPage").click()
            assert page.locator("#pageJump").input_value() == "2"
            assert page.locator("#cardGrid .card-tile").first.get_attribute("data-id") != first_card
            page.locator("#pageJump").fill("3")
            page.locator("#pageJump").press("Tab")
            assert page.locator("#pageJump").input_value() == "3"
            page.locator("#search").fill("SFN/S108-E074SSP")
            page.wait_for_function(
                "() => document.querySelector('#cardGrid .card-tile') && document.querySelector('#cardGrid .card-tile').textContent.includes('SFN/S108-E074SSP')",
                timeout=15000)
            with page.expect_download() as csv_download:
                page.locator("#exportFilteredBtn").click()
            csv=Path(csv_download.value.path()).read_text(encoding="utf-8-sig")
            assert "SFN/S108-E074SSP" in csv and "marketUSD" in csv

            with page.expect_download() as local_download:
                page.locator("#exportLocalBtn").click()
            backup=json.loads(Path(local_download.value.path()).read_text(encoding="utf-8"))
            assert backup["version"] == 1
            assert len(backup["watch"]) == 1
            assert len(backup["compare"]) == 1
            assert list(backup["portfolio"].values())[0]["qty"] == 2
            keys=["bm-watch","bm-compare","bm-portfolio"]
            stored_before=page.evaluate("(keys) => keys.map(key => localStorage.getItem(key))",keys)
            card_id=next(iter(backup["portfolio"]))
            bad={"version":1,"watch":[],"portfolio":{
                card_id:{"qty":"not-an-integer","cost":10,"currency":"EUR"}
            }}
            page.locator("#importLocalFile").set_input_files({
                "name":"invalid-backup.json","mimeType":"application/json",
                "buffer":json.dumps(bad).encode("utf-8")})
            page.wait_for_function(
                "() => document.querySelector('#toast').textContent.includes('Import rejected')",
                timeout=10000)
            assert page.evaluate("(keys) => keys.map(key => localStorage.getItem(key))",keys)==stored_before
            page.locator("#importLocalFile").set_input_files({
                "name":"empty-backup.json","mimeType":"application/json",
                "buffer":json.dumps({"version":1,"watch":[],"compare":[],"portfolio":{}}).encode("utf-8")})
            page.wait_for_function(
                "() => document.querySelector('#portfolioCount').textContent.trim()==='0'",
                timeout=10000)
            page.locator("#importLocalFile").set_input_files({
                "name":"restored-backup.json","mimeType":"application/json",
                "buffer":json.dumps(backup).encode("utf-8")})
            page.wait_for_function(
                "() => document.querySelector('#portfolioCount').textContent.trim()==='2'",
                timeout=10000)
            assert json.loads(page.evaluate("() => localStorage.getItem('bm-portfolio')"))==backup["portfolio"]
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "() => document.querySelector('#catalogStatus').textContent.includes('loaded printings')",
                timeout=60000)
            assert page.locator("#portfolioCount").inner_text().strip() == "2"
            page.locator('[data-tab="cards"]').click()
            # The full Japanese index must load on demand, rather than being claimed by metadata alone.
            page.locator('[data-tab="cards"]').click()
            page.locator('[data-preset="jp-weiss"]').click()
            page.wait_for_function(
                "() => document.querySelector('#catalogStatus').textContent.includes('JP loaded')",
                timeout=90000)
            page.locator("#cardGrid .card-tile").first.wait_for(timeout=45000)
            assert "JP" in page.locator("#catalogStatus").inner_text()
            page.locator("#search").fill("GZL/SE33-12")
            page.wait_for_function(
                "() => [...document.querySelectorAll('#cardGrid .card-tile')].filter(el => el.textContent.includes('GZL/SE33-12')).length === 2",
                timeout=20000)
            variants=page.locator("#cardGrid .card-tile")
            assert variants.count()==2
            assert {"RR","SEC"} <= set(
                badge.inner_text() for badge in page.locator("#cardGrid .card-tile .badge").all())
            variants.filter(has_text="SEC").first.click()
            page.locator("#viewer.open").wait_for(timeout=10000)
            assert "GZL/SE33-12" in page.locator("#viewerMeta").inner_text()
            assert "SEC" in page.locator("#viewerMeta").inner_text()

            # Simulate final image failure without relying on official/CDN uptime.
            # The reusable viewer <img> must remain mounted for the next card.
            previous_meta=page.locator("#viewerMeta").inner_text()
            page.route("https://bushimetrics-art-test.invalid/**",
                       lambda route: route.fulfill(status=404,body="missing"))
            page.evaluate("""() => {
                const img=document.querySelector('#viewerImage');
                const placeholder=document.querySelector('#viewerPlaceholder');
                img.dataset.artFallback='';
                img.style.display='block';
                placeholder.classList.add('hidden');
                img.src='https://bushimetrics-art-test.invalid/intentional-404.png';
            }""")
            page.wait_for_function(
                "() => document.querySelector('#viewerImage')?.style.display === 'none' && !document.querySelector('#viewerPlaceholder').classList.contains('hidden')",
                timeout=15000)
            assert page.locator("#viewerImage").count()==1
            page.locator("#viewerNext").click()
            assert page.locator("#viewerImage").count()==1
            assert page.locator("#viewerMeta").inner_text()!=previous_meta
            assert not errors, "Browser JavaScript errors: "+"; ".join(errors[:6])
            browser.close()
        print("Chromium acceptance smoke passed")
    finally:
        server.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):server.wait(timeout=5)


if __name__=="__main__":main()
