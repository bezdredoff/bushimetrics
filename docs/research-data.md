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
