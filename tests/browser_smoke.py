"""Real Chromium smoke tests for the static GitHub Pages app.

Run after pip install playwright && python -m playwright install chromium:
python tests/browser_smoke.py
"""
import contextlib
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
            page.locator("#marketCards").locator(".metric-card, .metric, .stat-card").first.wait_for(timeout=45000) if page.locator("#marketCards .metric-card, #marketCards .metric, #marketCards .stat-card").count() else page.wait_for_function("document.querySelector('#globalStatus').textContent !== 'loading…'",timeout=45000)
            assert "Failed to load" not in page.locator("#catalogStatus").inner_text()
            page.locator('[data-tab="cards"]').click()
            page.locator("#cardGrid .card-tile").first.wait_for(timeout=60000)
            card=page.locator("#cardGrid .card-tile").first
            card.click()
            page.locator("#viewer.open").wait_for(timeout=10000)
            assert page.locator("#viewerName").inner_text().strip()
            assert page.locator("#viewerBadges").inner_text().strip()
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
            page.locator('[data-tab="compare"]').click()
            assert page.locator("#compareGrid").inner_text().strip()
            page.locator('[data-tab="sources"]').click()
            assert "Research model availability" in page.locator("#sourcesContent").inner_text()
            assert not errors, "Browser JavaScript errors: "+"; ".join(errors[:6])
            browser.close()
        print("Chromium acceptance smoke passed")
    finally:
        server.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):server.wait(timeout=5)


if __name__=="__main__":main()
