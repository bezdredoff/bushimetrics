# BushiMetrics

A data-driven collectible card research dashboard for **Weiss Schwarz** and **Palworld Official Card Game**, inspired by the analytical *method* behind Collectrics rather than its branding or proprietary code.

## What it does

- Full catalog ingestion instead of a hand-maintained shortlist.
- Weiss market layer from TCGRate / TCGplayer-style market data.
- Palworld identity, rarity, rules metadata and images from the official card list.
- Optional TCG Republic image/store-ask enrichment for premium Weiss printings.
- Clear separation between **observed market**, **store ask**, and **model fair value**.
- Searchable/paginated Card Explorer designed for 30k+ printings.
- Full-screen preview with wheel/button zoom, keyboard navigation and thumbnail strip.
- Browser-local watchlist and three-card comparison.
- Fair Value Gap, Momentum, Investment Quality and Confidence research signals.
- Immutable daily snapshots and a no-look-ahead backtest scaffold.
- Automatic refresh through GitHub Actions and optional GitHub Pages deployment.

## Current source scale

TCGRate currently reports roughly 31k Weiss Schwarz printings across 177 sets; the official Palworld card list is imported in full on each refresh. New releases are discovered automatically.

## Run locally

```bash
python -m http.server 8080
```

Open `http://localhost:8080`.

## Refresh data

```bash
python -m pip install -r requirements.txt
python scripts/collect_weiss.py
python scripts/collect_palworld.py
python scripts/enrich_weiss_images.py --limit 800
python scripts/build_catalog.py
```

The collectors use public pages at a deliberately low request rate. They do not bypass authentication, CAPTCHAs, paywalls or rate limits. Review source-site terms before increasing frequency.

## Data model

- `data/catalog.json` — browser-ready merged catalog.
- `data/raw/weiss.json` — full Weiss observed market catalog.
- `data/raw/palworld.json` — full official Palworld catalog.
- `data/raw/weiss-images.json` — optional premium image/store-ask enrichment.
- `data/manual_overrides.json` — explicit versioned priors; subjectivity is visible.
- `data/history.json` — validated historical set-level checks.
- `data/snapshots/` — immutable dated catalog snapshots used by walk-forward evaluation.

## Model boundaries

`market`, historical changes and source metadata are observed data where available. `fair`, `momentum` and `investment` are research/model outputs. The v0.3 fair-value model is intentionally conservative and labelled heuristic until enough snapshots exist to fit and validate a past-only log-price model.

A real 30/90/180-day scorecard starts only when those horizons can be measured from snapshots without look-ahead bias.
