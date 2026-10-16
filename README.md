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
- Set Explorer summarizes premium density, image coverage, price coverage and average Investment Quality.

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

- `data/catalog.json` — generated browser catalog + set summaries.
- `data/raw/weiss.json` — generated full Weiss printing identity layer.
- `data/raw/palworld.json` — generated released Palworld + announced promos.
- `data/market/tcgapi.json` — incremental market cache, when configured.
- `data/market_overrides.json` — explicit validated market observations.
- `data/scarcity.json` — pull-rate/case evidence with sample size, confidence and source.
- `data/manual_overrides.json` — versioned game/set priors.
- `data/printing_overrides.json` — verified physical edition/treatment corrections only.
- `data/palworld-current-overrides.json` — current official-release supplement and announced future promos.
- `data/history.json` — historical set-level validation notes.
- `data/snapshots/` — compact walk-forward market snapshots.

## Model v0.4

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

Fair Value is only generated when an observed market price exists.

## Important collector-data rule

A collector number is not always enough to distinguish a physical investment object. If a Bushiroad reprint changes a gold/silver stamp or Palworld edition mark without changing the logical card identity, BushiMetrics only splits those editions after the physical difference is verified. It does not invent First Edition labels from a card number alone.

## Source attribution

- GachaWiki card-data repository: MIT License, copyright GachaWiki.
- Bushiroad / Weiss Schwarz card images and marks belong to their respective rights holders.
- Palworld Official Card Game card images and marks belong to Pocketpair / Bushiroad and their respective rights holders.
- BushiMetrics is an independent research project and is not affiliated with or endorsed by Bushiroad, Pocketpair, TCGPlayer or TCG API.

## Language architecture

English Weiss + Palworld load initially. The Japanese Weiss catalog is generated separately and lazy-loaded by the browser only when JP/All is requested. This keeps initial Pages payload reasonable while retaining the full JP printing catalog.
