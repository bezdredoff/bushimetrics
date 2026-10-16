# BushiMetrics

A data-driven collectible card research dashboard for **Weiss Schwarz** and **Palworld Official Card Game**, inspired by the analytical *method* behind Collectrics rather than its branding or proprietary code.

## What it does

- Full catalog ingestion instead of a hand-maintained shortlist.
- Full English Weiss printing catalog (base + SR/SP/SSP/SEC+/promos) from Trading Card Dex set pages, with preview images derived from card detail slugs.
- Full current Palworld printing catalog from Trading Card Dex, cross-checkable against the official Palworld card list.
- Market enrichment is a separate layer; missing market prices remain missing rather than being inferred from retailer asks.
- Clear separation between **observed market**, **store ask**, and **model fair value**.
- Searchable/paginated Card Explorer designed for 30k+ printings.
- Full-screen preview with wheel/button zoom, keyboard navigation and thumbnail strip.
- Browser-local watchlist and three-card comparison.
- Fair Value Gap, Momentum, Investment Quality and Confidence research signals.
- Immutable daily snapshots and a no-look-ahead backtest scaffold.
- Automatic refresh through GitHub Actions and optional GitHub Pages deployment.

## Current source scale

The collectors discover current set pages automatically and ingest every printing shown on those set pages. This includes parallel collector rarities rather than only unique gameplay cards. New sets flow in without editing the frontend.

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
python scripts/build_catalog.py
```

The collectors use public pages at a deliberately low request rate. They do not bypass authentication, CAPTCHAs, paywalls or rate limits. Review source-site terms before increasing frequency.

## Data model

- `data/catalog.json` — browser-ready merged catalog.
- `data/raw/weiss.json` — full Weiss observed market catalog.
- `data/raw/palworld.json` — full official Palworld catalog.
- `data/manual_overrides.json` — explicit versioned priors; subjectivity is visible.
- `data/history.json` — validated historical set-level checks.
- `data/snapshots/` — immutable dated catalog snapshots used by walk-forward evaluation.

## Model boundaries

`market`, historical changes and source metadata are observed data where available. `fair`, `momentum` and `investment` are research/model outputs. The v0.3 fair-value model is intentionally conservative and labelled heuristic until enough snapshots exist to fit and validate a past-only log-price model.

A real 30/90/180-day scorecard starts only when those horizons can be measured from snapshots without look-ahead bias.
