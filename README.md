# BushiMetrics

A data-driven collectible-card research dashboard for **Weiss Schwarz** and **Palworld Official Card Game**, inspired by the analytical method behind Collectrics rather than its branding or proprietary implementation.

The product goal is simple: separate **what a card is**, **what the market is actually doing**, and **what the model thinks**.

## Current product

### Full catalog
- English Weiss Schwarz master catalog from the MIT-licensed GachaWiki dataset.
- Premium printings such as SR / SP / SSP / SEC / SEC+ are distinct objects when the source exposes distinct collector numbers.
- Current Palworld released catalog is pinned to **276 printings as of 2026-10-16**.
- Announced future Palworld promos are stored separately and never counted as released inventory.
- Card preview URLs come from official/art-source metadata and are lazy-loaded in the browser.

### Explorer
- Search by name, set, collector number, rarity, type or color.
- Game, set, rarity, release-status, premium-only and priced-only filters.
- Grid and table views.
- 60-card pagination so a 20k–30k+ catalog remains responsive.
- Full-screen viewer with wheel/button zoom, keyboard left/right navigation, thumbnail strip and shareable `#card=` deep links.

### Research
- Observed market price is separate from Model Fair Value.
- Market data can be enriched incrementally through TCG API with `TCGAPI_KEY`.
- Missing market data remains missing; retailer asks are never silently substituted.
- Investment Quality exposes the component scores used by the heuristic.
- Palworld BP01 uses sourced community pull-rate evidence where available rather than relying only on rarity labels.
- Set Explorer summarizes premium density, artwork URL presence (not verified reachability), price coverage and average Investment Quality.

### Personal tools
Everything below is browser-local; no account or server storage is required:
- Watchlist.
- Four-card comparison.
- Portfolio quantity and average cost basis.
- Known market value and unrealized P/L where observed prices exist.
- Import/export of local data as JSON.

### Validation
- Compact immutable daily market/model snapshots.
- 30 / 90 / 180-day walk-forward evaluation.
- No future data is used in a historical prediction.
- Until enough real time elapses, the site reports the backtest as pending rather than manufacturing an accuracy number.

## Architecture

```text
GachaWiki/ws-cards ───────┐
                           ├── collect_weiss.py ──┐
dragogodev/cgs ───────────┤                       │
Palworld overrides ───────┴── collect_palworld.py├── build_catalog.py ── data/catalog.json ── GitHub Pages
                                                   │
TCG API cache ── enrich_market_tcgapi.py ─────────┤
validated market_overrides.json ──────────────────┤
scarcity.json / priors / edition overrides ───────┘

data/catalog.json ── snapshot_metrics.py ── data/snapshots/market-YYYY-MM-DD.json
                                              └── backtest.py
```

## Hosted site, integrity checks and measured limitations (2026-10-17)

- Live dashboard: https://bezdredoff.github.io/bushimetrics/
- [Hosted Pages acceptance CI](https://github.com/bezdredoff/bushimetrics/actions/workflows/hosted-pages-smoke.yml) checks deployed HTML bundle/version, EN+Palworld and JP counts and source generation date against `main`, then runs desktop/mobile Chromium (PR #50). **The published site was verified on October 17, 2026.**
- [Sampled JP artwork audit](https://github.com/bezdredoff/bushimetrics/actions/workflows/jp-artwork-health.yml) probes up to 16 Japanese-set sample cards each week, distinguishes valid bytes from 403/hotlink blocks, and uploads a JSON report. An initial PR run verified **8 of 8** sampled images; this is **not** proof that all 63,675 images work (PR #51).
- [Data methodology and provenance](docs/research-data.md) explains why manually entered quotes, expired USD observations and Cardmarket price guides must be distinguished from completed sales.
- [Market freshness report](data/market-freshness-audit.json) shows dated versus undated prices separately for USD/EUR. On 2026-10-17, USD: 2,303 records (253 stale, 2,050 without a confirmed observation date); EUR: 8,097 dated guide records. `fresh` for EUR means guide publication date, **not** sale activity.
- Japanese prices from independently verified sales remain unavailable in the current dataset; the research engines return missing-data reasons rather than imaginary results.
- Follow remaining work in [Issue #31](https://github.com/bezdredoff/bushimetrics/issues/31).

## Automatic refresh

GitHub Actions:
- sparse-checks out only `src/data/ws-cards` from GachaWiki;
- checks out the Palworld mirror from GitHub;
- rebuilds both full catalogs;
- optionally spends a bounded TCG API request budget;
- validates catalog scale / Palworld exact released count / image coverage / ID uniqueness;
- stores a compact market snapshot;
- commits changed generated data back to `main`.

The catalog does **not** depend on anti-bot-protected websites.

## Optional TCG API price enrichment

TCG API currently covers English Weiss Schwarz / TCGPlayer marketplace pricing. Add a repository secret:

```text
TCGAPI_KEY
```

The workflow defaults to an 80-request daily budget. The cache fills progressively, prioritizing premium cards that are stale or missing. The site works without this key; only price coverage is lower.

## Local development

```bash
python -m pip install -r requirements.txt

# external sources, same layout CI expects
git clone --filter=blob:none --sparse https://github.com/GachaWiki/gacha-wiki external/gacha-wiki
git -C external/gacha-wiki sparse-checkout set --no-cone src/data/ws-cards

git clone --filter=blob:none --sparse https://github.com/dragogodev/cgs external/cgs
git -C external/cgs sparse-checkout set --no-cone Palworld/AllCards.json

python scripts/collect_weiss.py
python scripts/collect_palworld.py
python scripts/enrich_market_tcgapi.py   # cleanly skips if TCGAPI_KEY is absent
python scripts/build_catalog.py
python scripts/snapshot_metrics.py

python -m http.server 8080
```

Open <http://localhost:8080>.

## Data files

- `data/catalog.json` — generated analytical EN/Palworld catalog + set summaries; `data/web/` contains the lightweight browser indices and per-set shards.
- `data/raw/weiss.json` — generated full Weiss printing identity layer.
- `data/raw/palworld.json` — generated released Palworld + announced promos.
- `data/market/tcgapi.json` — incremental market cache, when configured.
- `data/market_overrides.json` — manually researched USD indications; the eight current unlinked records are **not** included in observed-market prices or peer training.
- `data/scarcity.json` — pull-rate/case evidence with sample size, confidence and source.
- `data/manual_overrides.json` — versioned game/set priors.
- `data/printing_overrides.json` — verified physical edition/treatment corrections only.
- `data/palworld-current-overrides.json` — current official-release supplement and announced future promos.
- `data/history.json` — historical set-level validation notes.
- `data/snapshots/` — compact walk-forward market snapshots.

## Investment heuristic + peer Fair Value v0.8

Current Investment Quality weights:

| Factor | Weight |
| --- | ---: |
| Structural scarcity | 24% |
| IP / character strength | 20% |
| Reprint durability | 13% |
| Historical significance | 11% |
| Treatment premium | 10% |
| Momentum | 10% |
| Liquidity | 7% |
| Edition durability | 5% |

This is intentionally a transparent heuristic. It is **not** labelled a fitted predictive model until accumulated snapshots permit a real walk-forward calibration.

Fair Value v0.8 excludes the target card's own market price **both directly and indirectly through the subject-premium peers**. It is a cross-sectional peer estimate, not a trained investment-return forecast. Its High/Medium/Low confidence labels refer only to **sample sizes**, not proven predictive accuracy, liquidity or verified completed sales. The interface only compares Fair Value to a target market price where that target has an observed price.

## Important collector-data rule

A collector number is not always enough to distinguish a physical investment object. If a Bushiroad reprint changes a gold/silver stamp or Palworld edition mark without changing the logical card identity, BushiMetrics only splits those editions after the physical difference is verified. It does not invent First Edition labels from a card number alone.

## Source attribution

- GachaWiki card-data repository: MIT License, copyright GachaWiki.
- Bushiroad / Weiss Schwarz card images and marks belong to their respective rights holders.
- Palworld Official Card Game card images and marks belong to Pocketpair / Bushiroad and their respective rights holders.
- BushiMetrics is an independent research project and is not affiliated with or endorsed by Bushiroad, Pocketpair, TCGPlayer or TCG API.

## Language architecture

English Weiss + Palworld load initially. The Japanese Weiss catalog is generated separately and lazy-loaded by the browser only when JP/All is requested. This keeps initial Pages payload reasonable while retaining the full JP printing catalog.

## Public-data availability audit (2026-10-17)

**Do not treat a missing observation as zero, a retailer asking price as a completed sale, or an unverified image URL as a working image.** The model's Investment Quality score is a heuristic, not an observed price or validated investment return.

| Dataset | Available now | Missing / limitation | Status |
| --- | --- | --- | --- |
| Weiss Schwarz EN identity | 30,983 printings in generated catalog | May lag new releases and unusual variants | Available, refresh-dependent |
| Weiss Schwarz JP identity | 63,675 printings in generated catalog | Official Japanese site currently reports 66,067 search results; definitions and update timing may differ | Partial / reconcile |
| Palworld | 276 released and 13 announced printings in generated catalog | Announced items must not be counted as released | Available as-of date |
| EN + Palworld market observations | 10,190 of 31,272 printings with price in at least one currency | 21,082 without price observations | Partial |
| JP market observations | 0 of 63,675 with verified market price in generated metadata | No public, reproducible price dataset integrated | **Not available in current dataset** |
| Historical price series | Sharded snapshots when observations exist | Insufficient history for many printings | Partial / pending |
| Images | URL metadata exists for most records | JP source URLs may be stale; successful image load not independently validated | Partial |
| Predictive backtest | Walk-forward framework exists | Needs sufficient time-stamped independent observations | Pending, no fabricated accuracy |

Public references: [official Japanese card list](https://ws-tcg.com/cardlist/search/), [official product list](https://ws-tcg.com/products/), [official PR cards](https://ws-tcg.com/cardlist/card_pr/). Third-party databases can help reconcile identities, but their prices/images are **not** ingested without verifiable provenance, reuse permission, and correct printing-level matching.

### Acceptance checks still required

- [x] Real Chromium checks for published GitHub Pages on desktop and mobile, including lazy JP browsing and matching the shipped catalog/bundle to `main` (PR #50). Local smoke additionally tests watchlist, compare, portfolio and backup import/export. This is not an exhaustive visual/manual QA pass.
- [ ] Reconcile JP catalog against official printings, including rarity/parallel variants and release status.
- [ ] Add per-card data freshness, provenance, and verified/unavailable flags for prices and artwork.
- [ ] Validate each image URL rather than equating non-empty URL with an image.
- [ ] Add public-market-source connectors only where access, licensing, and matching are verified.
- [ ] Calibrate model and backtest only when sufficient historical observations exist.
