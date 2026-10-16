# Research evidence requirements

Quantitative functions are implemented in scripts/market_evidence.py. Curated observations live in data/research_observations.json and are evaluated with python scripts/evaluate_market_evidence.py. An empty register is intentional: no unverified sales or pull odds are fabricated.

Every record requires id, game, set, and a per-metric observations object. Every numerical observation must be tied to its source, date, exact physical printing/edition, geography and currency as applicable. Do not combine EUR and USD or first editions and reprints.

| Metric | Required evidence | If missing |
| --- | --- | --- |
| CEC | Observed carton price, empirical card-specific pull probability, at least 30 sampled cartons, source | Unavailable |
| Demand Pressure | Verified completed sales, inventory, window and source | Unavailable |
| Historical HYPE | Current pressure and at least 30 historical matched-cohort pressures, source | Unavailable |
| Rip EV | Complete outcome probability distribution, sold prices, sealed cost | Unavailable |
| Grading EV | Grade probabilities, graded net sold prices and grading cost | Unavailable |
| Franchise Health | Comparable historical franchise/player retention and validated weighting | Unavailable pending calibration |

The current marketHeatPercentile is cross-sectional, NOT historical HYPE. Current Investment Quality is a heuristic with versioned manual prior assumptions, NOT a trained price forecast. CEC estimates scarcity pressure, NOT expected sale price. The engine refuses the unverified assumption that hits are uniformly distributed across all cards in a rarity.

Source research: https://ws-tcg.com/cardlist/search/ (JP card identities, not sold prices), https://en.ws-tcg.com/products/ (EN product specifications), https://en.palworld-official-cardgame.com/ (official product and edition news), https://palworldtcg.gg/pulltracker (community observations, not official odds). Licensing, exact printing matching and proof of completed sales are required before importing third-party market prices.

Remaining: independently verified listing/sold inventory and history; carton breaks; verified edition identifiers; grading cohorts; franchise activity/retention; cross-rarity Pal/human and signature premiums; trained weights and prospective backtesting; browser E2E acceptance tests. New raw evidence must be reviewed before inclusion in the production catalog.

The published `data/research_status.json` is initially empty and explicitly reports no evaluated printing-level research observations. The card viewer renders per-metric unavailable reasons; the separate catalog price layer is unaffected. After curating and reviewing observations, run `python scripts/evaluate_market_evidence.py` and commit the validated status report. The report is not automatically promoted from unsourced market records.

## Manual price quarantine and independent age checks

The current manually entered USD quote file contains **8 price indications with no per-card independent evidence URL** (as of the 2026-10-16 audit). Their values remain visible only as separately marked *unverified research indications*; they are not included as observed market prices or fitted peer-price samples. The legacy seed prices follow the same rule. A dated URL-backed override can be included as a **source-linked observation** but is not automatically a confirmed completed sale.

When a vetted override replaces an automated provider, the original provider's sales counts, listing inventory and source link are **not inherited**. Source metadata must always travel atomically with its price.

USD observation freshness is computed from `marketAsOf` (currently **older than 14 days** or undated is labeled stale) even if a provider flag says `stale=false`. Freshness and completed-sale sample confidence are separate dimensions. The market source audit appears in `data/market-source-audit.json` and in the Sources tab after the next catalog refresh.

External verified sources may still be unavailable; adding a guessed price or linking only to BushiMetrics' own JSON does not constitute independently verified evidence.

## Japanese upstream printing-identity audit

The JP importer preserves its existing first-encountered collector-code policy while producing `data/jp-identity-audit.json` from the Akenaide source checkout on every data refresh. The report accounts for parsed, missing-code, malformed and duplicate source JSON files, and samples conflicting card metadata (rarity, name, set, artwork) under the same code. This explicitly exposes previously silent deduplication.

A conflicting image or rarity does **not** prove a distinct physical print or a missing product entry. Inspect official Bushiroad print records and any official reprint announcements before splitting catalog identities. No estimate of missing cards should be derived solely by subtracting the current public site result count from our local indexed printings.

The Coverage page exposes the generated audit when available. Before the next source refresh it reports the audit as pending rather than displaying invented counts.

## English Weiss source integrity audit

The English importer now writes `data/en-identity-audit.json` after reading the GachaWiki set source files. Every eligible English card row is accounted for as a unique code, duplicate code, missing code or invalid row. The report samples differing rarity, artwork, title, set and variant metadata under repeated collector codes.

The current first-by-code policy (except preferring a later available image) is preserved until physical-printing differences are independently verified. Audit counts are available in Coverage after the scheduled data refresh, and their internal arithmetic is checked in CI.

These checks establish source-import consistency, **not full official-market catalog completeness** or verified artwork reachability.
