#!/usr/bin/env python3
"""Bounded, independent sampled artwork-health audit for Japanese Weiss.

Never changes image URLs or claims that nonempty URL fields are verified images.
Uses at most N set-shard samples per run (default 16) with one limited-range
image fetch per candidate; no bulk scan of ~64k remote assets.

Run offline: python scripts/audit_jp_artwork.py --offline --output /tmp/jp-artwork.json
Run bounded: python scripts/audit_jp_artwork.py --samples 16 --output /tmp/jp-artwork.json
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data/web/manifest.json"
IMAGE_MAGIC = (
    b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff",
    b"GIF87a", b"GIF89a",
)


def choose_samples(manifest, root=ROOT, limit=16):
    sets = sorted((s for s in manifest.get("sets", []) if
                   s.get("language") == "JP" and s.get("path")),
                  key=lambda s: (s.get("key", ""), s.get("name", "")))
    if limit < 1 or limit > 40:
        raise ValueError("Remote sample limit must be 1..40")
    if not sets:
        raise ValueError("No Japanese sets in current manifest")
    selected = []
    n = min(limit, len(sets))
    for index in range(n):
        meta = sets[(index * len(sets)) // n]
        location = (Path(root) / meta["path"]).resolve()
        if not location.is_relative_to(Path(root).resolve()):
            raise ValueError("Unsafe shard path")
        payload = json.loads(location.read_text(encoding="utf-8"))
        rows = payload.get("cards", [])
        cards = [c for c in rows if c.get("im") and c.get("c")]
        if not cards:
            continue
        card = cards[len(cards)//2]
        selected.append({
            "set": meta.get("name"),
            "printingId": card.get("id") or card.get("i"),
            "code": card["c"],
            "rarity": card.get("r"),
            "originalUrl": card["im"],
        })
    return selected, len(sets)


def candidates(url):
    """Mirror the current *order* of official JP image fallback requests."""
    try:
        parts = parse.urlsplit(url)
    except ValueError:
        return []
    if parts.scheme not in ("https", "http") or parts.hostname not in (
        "ws-tcg.com", "www.ws-tcg.com"
    ):
        return []
    base = "/wordpress/wp-content/images/"
    modern = base + "cardlist/"
    result = [("original", url)]
    if base in parts.path and modern not in parts.path:
        modern_url = url.replace(base, modern, 1)
        result.append(("cardlist", modern_url))
        relay_target = modern_url
    else:
        relay_target = url
    relay = "https://images.weserv.nl/?url=" + parse.quote(relay_target, safe="")
    result.append(("relay", relay))
    return result


def looks_like_image(prefix):
    return any(prefix.startswith(signature) for signature in IMAGE_MAGIC) or (
        prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
    )


def inspect_url(url, *, timeout=8):
    """Read at most 32 bytes; a successful HTTP page is not necessarily art."""
    headers = {
        "User-Agent": "BushiMetricsArtworkAudit/1.0 (+https://github.com/bezdredoff/bushimetrics; limited sampling)",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5",
        "Range": "bytes=0-63",
    }
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as reply:
            prefix = reply.read(32)
            kind = reply.headers.get("Content-Type", "").split(";", 1)[0]
            status = reply.status
        return {
            "ok": bool(looks_like_image(prefix)),
            "httpStatus": status,
            "mime": kind,
            "reason": "image-signature-valid" if looks_like_image(prefix) else "non-image-payload",
        }
    except error.HTTPError as exc:
        return {"ok": False, "httpStatus": exc.code, "reason": "http-error"}
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"ok": False, "httpStatus": None, "reason": "network-or-timeout",
                "detail": str(exc)[:140]}


def audit_card(card, checker=inspect_url, delay=0):
    links = candidates(card["originalUrl"])
    if not links:
        return {**card, "status": "unverified-unsupported-url",
                "workingVariant": None, "checks": []}
    checks = []
    for variant, url in links:
        evidence = checker(url)
        checks.append({"variant": variant, **evidence})
        if evidence.get("ok"):
            return {**card, "status": "confirmed-in-sample",
                    "workingVariant": variant, "checks": checks}
        if delay:
            time.sleep(delay)
    blocked = any(check.get("httpStatus") in (401, 403, 429) or
                  check.get("reason") == "network-or-timeout" for check in checks)
    return {**card, "status": "blocked-or-unverifiable" if blocked else "sample-failed",
            "workingVariant": None, "checks": checks}


def run(manifest, root=ROOT, limit=16, offline=False, checker=inspect_url):
    selected, total_sets = choose_samples(manifest, root, limit)
    rows = ([
        {**card, "status": "not-probed-offline",
         "workingVariant": None, "checks": []} for card in selected
    ] if offline else [
        audit_card(card, checker=checker, delay=0.15) for card in selected
    ])
    counts = {status: sum(row["status"] == status for row in rows) for status in (
        "confirmed-in-sample", "blocked-or-unverifiable",
        "sample-failed", "unverified-unsupported-url", "not-probed-offline"
    )}
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "JP Weiss set-stratified remote URL sample only",
        "totalJPSetGroups": total_sets,
        "sampleCount": len(rows),
        "summary": counts,
        "observations": rows,
        "limitations": [
            "Sampled image requests never prove all catalog artwork is available.",
            "A GitHub Actions HTTP 403/timeout may reflect hotlink controls rather than a missing image.",
            "A successful sampled byte signature verifies that response only at the time of request.",
            "Existing app.js image URLs and fallback order are unchanged.",
            "No purchase prices, official printing status or resale data are inferred from artwork.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/jp-artwork-health.json")
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = run(manifest, root=ROOT, limit=args.samples, offline=args.offline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("JP artwork sampled", result["sampleCount"], "of", result["totalJPSetGroups"],
          "sets:", result["summary"])
    print("Source:", args.output)


if __name__ == "__main__":
    main()
