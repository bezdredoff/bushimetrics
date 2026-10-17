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

## Verified Godzilla Japanese parallel printings (GZL/SE33)

The upstream Akenaide source includes two confirmed **RR versus SEC** collector variants sharing their normalized base codes: `GZL/SE33-12` (Godzilla Earth) and `GZL/SE33-23` (Vulture). The RR and SEC variants have different artwork/treatment and must be separate collectible printings. The original source JSON contains both but the old code-only deduplication discarded both SEC versions.

Documented external verification and permitted rarity pairs are stored in `data/verified-jp-variants.json`, including official/retailer URLs. The importer now retains **only those explicitly verified pairs** as distinct rarities. This adds two JP printings while preserving all existing identities and leaving other codes unchanged. No unrelated first-edition or reprint labels are inferred.

Retail **asking prices** used to verify that these distinct products exist are not converted into observed market prices or Fair Value. Confirmed printing identity does not imply verified completed-sale economics.

## Collector data backup acceptance (2026-10-17)

The local JSON exporter uses `version: 1` and includes watchlist IDs, at most four compare IDs, and portfolio positions with positive integer quantity, nonnegative finite numeric cost and explicit EUR/USD currency. Imports validate the complete backup first and reject invalid/unsupported payloads **without changing the existing local collection**. Unknown but syntactically valid printing IDs remain stored so lazily loaded JP records can resolve later.

The browser acceptance test now checks a real export/import round trip, rejects a malformed portfolio, checks persistence after reload, verifies CSV output and catalog pagination, and confirms both distinct Godzilla RR/SEC variants are searchable in Japanese Weiss.

No watchlist, portfolio or comparison data is uploaded to a server by this feature; only user-triggered downloads and local browser storage are used.

## Japanese artwork health: limited remote sample (2026-10-17)

`scripts/audit_jp_artwork.py` checks a **fixed, deterministic, spread-across-sets sample** from the published Japanese set shards. It does **not** change artwork URLs, use guessed rewrites, scrape entire image collections, or treat a nonempty image URL as proof of a working file.

- Local offline inspection: `python scripts/audit_jp_artwork.py --offline`.
- Limited remote inspection: `python scripts/audit_jp_artwork.py --samples 16` (maximum 40).
- A scheduled workflow `.github/workflows/jp-artwork-health.yml` runs weekly, also on initial merge; its result is a downloadable JSON Actions artifact retained for 14 days with the individual tested paths.
- It tries the same image URL, official `/images/cardlist/` alternative and (if needed) an image relay, in the existing app's order. The script only reads a few response bytes and checks known image signatures.
- It distinguishes `confirmed-in-sample`, `sample-failed`, and `blocked-or-unverifiable` (HTTP 403/429 or network timeouts). A CDN blocking GitHub runners is **not** evidence that a user's browser cannot load an image.
- Sampling status never implies all Japanese card artwork is verified. Confidence in the catalog remains limited by independent proof of each remote image; separate source identity and pricing audits remain in place.

[See sampled results in GitHub Actions](https://github.com/bezdredoff/bushimetrics/actions/workflows/jp-artwork-health.yml).

## Market data dates vs download timestamps — USD & EUR

The catalog differentiates three things that were previously conflated in some
data sources: **provider price publication date**, **local cache fetch time**,
and **sample confidence**. Fetching a provider file now does not make its market
observations recent.

- TCGCSV/TGCPlayer public market prices are price-guide figures, not
  independently verified completed sales. The daily fetch time is now
  `marketRetrievedAt`, **not** `marketAsOf`. When the mirror does not
  identify a price-observation date, the price remains available but explicitly
  **undated**.
- The Cardmarket public EUR guide uses the upstream
  `price_guide_10.json.createdAt` as `cardmarketAsOf`. If the provider does
  not supply an interpretable publication date, the catalog never substitutes
  its own `generatedAt`; it reports unknown source freshness.
- Palworld Prices' completed-sale sample dates continue to use the actual
  upstream `asOf`. Sample size, date age, and whether a price is a guide or
  completed-sale median are separate.
- Optional TCG API and linked manual USD observations retain their own
  provider-specific dates; missing or future/invalid dates are flagged.
- The catalog derives EUR `marketEURAgeDays`, `marketEURStale` and
  `marketEURDateStatus`; existing USD `marketObservationAgeDays` and
  `marketStale` remain independent. The current threshold is **older than
  14 days**. Unknown dates are *not* assumed fresh.
- The generated `data/market-freshness-audit.json` gives independent
  price-record totals for both currencies and each provider, grouped into
  recent, old, undated and invalid/future dates. **A printing priced in both
  EUR and USD is counted in each currency; totals are not distinct cards.**
- This summary is shown in Sources, with per-printing EUR information in the
  viewer. Where a source date is absent, the viewer explicitly says it cannot
  verify freshness. This does **not** change public prices or imply that
  older observations have no value.

Data freshness is not proof of trading liquidity, authentic completed-sales
provenance, validated grading results, or investment predictiveness.

## Peer Fair Value v0.8: independent target holdout

Previous code excluded the target market quote from the primary
same-set/same-rarity median, **but the target could still leak back** through
a second card's precomputed subject premium: that second card's relative
rarity median had itself been calculated using the target card's price.

v0.8 removes the held-out target from **every** same-rarity peer normalization
used in its own forecast. When computing the premium of a different subject
printing with the same rarity, both that peer and the held-out target are
excluded from the comparison baseline. Ratios from different rarity cohorts
are still safe because the held-out target was never in their denominators.
This is tested by increasing a target's EUR quote 100-fold: its own Fair
Value, peer median, subject premium and sample counts must remain identical.

Confidence thresholds still describe only the number of usable peer
observations and **do not indicate calibrated return prediction skill**.
EUR peers are Cardmarket guide estimates, not necessarily actual completed
sales; USD peer evidence varies by provider. Never interpret these estimates
as tradeable bids or guaranteed realizable proceeds. Existing immutable daily
snapshots retain their original model version; do not rewrite old forecasts
when methodology changes.

## Version-aware walk-forward research (v0.8, 2026-10-17)

Every immutable daily snapshot stores the model version that produced its
forecast. The new `scripts/backtest.py` preserves this identifier and
separately evaluates 30/90/180-calendar-day EUR and USD forecasts for each
originating version (v0.7, v0.8, etc.). A later market price observation can
close an earlier forecast even if model logic has changed since; the old model
is never retroactively re-fitted or overwritten.

Scores remain **pending** without at least 3 distinct source dates and 30
card-level matches per currency/model/horizon. Even when sufficient guide
prices accumulate, scores are marked **exploratory price-guide changes**, not
realized sales returns. There is no defensible investment model calibration
until independent dated completed sales, adequate cohorts and future holdouts
exist. The output `data/backtest-status.json` is published by the daily
refresh; the Backtest tab renders the status without combining versions.

Previous hard-coded historical indices for Frieren, NIKKE and Azur Lane
were missing independent source URLs and dated underlying observations. The
three rows were removed from the displayed Backtest examples rather than
claiming unverified index changes are factual. Verified set-level figures
can return once source URL, as-of date and comparable methodology are available.

## Cardmarket-to-physical-printing identity gate (2026-10-17)

Cardmarket's public Weiss Schwarz EUR export is a **price guide**, not a
source of independently verified completed sale prices. The collector-number
matcher in `scripts/enrich_market_cardmarket.py` is now fail-closed:

- Where Cardmarket publishes a collector number, it must identify **exactly
  one** known Weiss printing. An unknown number never falls back to matching
  a similar title. Any explicit rarity that conflicts with the identified
  printing rejects the price, even if the name matches.
- When the collector number is absent, name-based matching respects **every**
  rarity and product-expansion constraint supplied by Cardmarket. Where
  Cardmarket provides only a title (common in its public Weiss export),
  only a globally unique **ordinary/base printing** may receive an
  *indicative* guide price. Premium/signature, V.2, foil and signed titles
  require stronger physical metadata. These tentative title-only matches
  are explicitly marked `unique-normal-name-unverified-source-treatment`
  and are **not** verified physical treatment identities. Multiple matching
  cards are quarantined rather than arbitrarily chosen.
- Multiple distinct Cardmarket products mapping to the same BushiMetrics
  collector code **all remain unpriced** until their physical variants can be
  independently reviewed. Product ordering or higher asking prices do not
  decide which observation is used.
- Reports record matched product IDs, matching methods, rejected source rows
  and a limited list of collided source IDs. The generated
  `data/cardmarket-match-audit.json` marks older cached mappings as
  **legacy/unverified** until a complete fetch is processed by the new
  matcher. A cache date does not certify identity matching.
- The scheduled refresh refuses to publish a suspiciously small new EUR
  mapping result (less than 2% of the English Weiss catalog, minimum 100)
  rather than silently discarding almost all price coverage. The previous
  published catalog remains intact if this validation fails.

This conservatism may lower EUR price coverage. Such missing prices are
preferable to attaching a price guide from a different rarity, signed parallel
or physical treatment. It does not imply the underlying card is worthless.

## TCGCSV / TCGplayer USD subtype integrity

The TCGCSV mirror publishes market **price guides**, which do not establish a
completed-sale price. Different price rows under a single TCGplayer product may
refer to Normal versus Foil/Holofoil subtypes. A previous importer always
preferred Foil even for ordinary Common/Uncommon/Rare/Double Rare Weiss cards,
potentially overstating the price of the actual collectible.

The importer now selects the **Normal** subtype for non-premium source
printings and **Foil/Holofoil** for explicitly premium rarities (SP, SSP, SEC,
SR, OFR, RRR and related variants). If an exactly matched collector-number product has *only one*
subtype quote, it may still be retained even when the Normal/Foil designation
looks inconsistent with the card rarity, but it is explicitly labelled
`single-opposite-subtype-unverified-treatment`: the exact number is known,
not the supplier's treatment semantics. A single source row with no subtype
designation is separately provisional (`single-unspecified-subtype`).
Multiple possible rows for the preferred subtype are rejected rather than
chosen by source order.

If two different TCGplayer product IDs resolve to the same exact collector
number, *all those conflicting mappings* are quarantined until the exact
physical versions can be verified. They are not treated as one printing merely
because the text of the collector number matches.

The next full refresh generates `data/tcgcsv-subtype-audit.json` with
matched/duplicate/subtype-rejection counts. Earlier cached USD values keep a
legacy/unverified subtype marker until this refresh has completed. Missing
market values mean unknown, never zero or worthless. The sampling confidence
of separate Palworld Prices completed-sales observations is unaffected.

## Snapshot source-lineage and no-lookahead gate (2026-10-17)

The daily `data/snapshots/market-YYYY-MM-DD.json` files are **capture
snapshots**, not evidence of a trade, independently published price change, or
new sale. Snapshot schema v2 retains separate per-card fields for USD and EUR:
source publication dates (`marketAsOf`, `cardmarketAsOf`), provider identity
(`palworldPricesCardId`, `tcgplayerProductId`,
`cardmarketProductId`), subtype/match method, source labels, and the
underlying sale-sample basis where available. It continues to use exclusive
file creation; existing v0.7/v0.8 snapshots are NEVER rewritten.

`scripts/backtest.py` now publishes a schema-v2
`data/backtest-status.json` with exclusion counts/reasons per model,
currency and horizon. An exploratory 30/90/180-day comparison is only eligible
when BOTH source records:

- Have positive numeric quotes and an earlier positive prediction for the
  same card, **without crossing currencies**.
- Have independently date-stamped price-source publication dates, not just
  local download or snapshot times. Neither date can be future relative to
  its capture; source age is at most 14 days, and the later publication date
  must occur AFTER the entire requested calendar horizon.
- Refer to the **same separately traceable provider product/printing ID**.
  Cardmarket title-only matches, TCGCSV's provisional/unverified Normal-Foil
  choices, legacy records with no such identity, and provider switches
  are excluded rather than assigned a false numerical forecast accuracy.
- Are not explicitly marked stale by their own price provider.

An old cached price copied into a new daily snapshot therefore contributes
**zero qualifying future observations**. The metrics remain pending until
there are >=3 independent source-qualified forecast start dates and >=30
same-currency comparison records. Even at that threshold results describe
**exploratory movement in provider guide/rolling-sale estimates, not
verified profitable sales or net realizable returns**. Provider publication
dates for Palworld are not by themselves proof that fresh individual
completed sales entered the provider's rolling sample.

The browser's per-card history chart now explicitly labels saved daily
captures, distinct upstream price-publication dates and dates with sufficient
source identity. It does not show a percent *source-guide move* unless
multiple independently dated qualified readings exist. This avoids
conflating a flat re-downloaded quote with 30 days of new sales observations.

Tests use fabricated fixtures for legacy/undated quotes, repeated old prices,
future-dated source updates, changed product IDs, mismatched treatments,
and distinct valid publications. These synthetic tests validate guardrails;
they do NOT constitute market evidence.

## Exact Palworld printing identity and sold-price precedence (2026-10-17)

Palworld Prices publishes a **stable source `cardId`** plus separate
`code` and `variant` fields. Its documentation explicitly distinguishes
the unsuffixed `pal-BP01-001` base printing from a separately listed
`pal-BP01-001-RR` printing: both can have printed rarity RR but are
*different collectibles* with independent completed-sale prices. OSR,
SP and SSP likewise have different physical identities.

The importer now requires that all three source fields agree:
`cardId == pal-{code}[-{explicit variant}]`. An explicitly suffixed
variant must map to that **exact suffixed English printing**, never back
to `EBP01-001` if `EBP01-001RR` (or another suffix) does not exist in
our catalog. Unknown variants, contradictory source IDs and duplicates
are quarantined with machine-readable reasons and limited examples.

Only positive numerical `bare` or properly labelled `thin`
**completed-sale sample estimates** populate USD market prices.
Asking prices remain separate; provider publication date and stale flag
are preserved. The next refresh publishes
`data/palworld-identity-audit.json` with the unambiguous source
printing counts, priced observations and excluded source variants.
Older cache rows are explicitly *not* retroactively certified.

USD market source choice is also provenance-aware: a traceable Palworld
Prices completed-sale sample takes precedence over a TCGCSV or TCG API
**price guide** on the same exact collector code, even if both records
exist. That sample retains its actual age and confidence; the decision
does not imply it is fresh or investment-grade. A market guide can fill
a genuinely unpriced printing but cannot silently replace a measured
sold-price sample. An explicitly linked, dated manual override is still
separate and labelled as such rather than borrowing sales metadata.

Source documentation: https://palworldprices.com/docs/api/
Source attribution: Data: Palworld Prices (palworldprices.com).
The API's public terms permit reuse with attribution and a link;
we do not redistribute card images from this price API. Independent
ownership/printing audits for Japan and other external sources remain
separate tasks.

## Optional Weiss premium TCG API safety and provider licensing (2026-10-17)

The optional `scripts/enrich_market_tcgapi.py` is disabled without
`TCGAPI_KEY`. It previously accepted the first **partial or title-string
match** returned by search and could choose the highest Foil guide price
without checking which physical printing or date it represented.

The premium importer now requires a unique provider card with:
(1) exact complete collector code, (2) explicitly compatible premium rarity,
(3) the Weiss Schwarz game identity when provided, and (4) a unique
market-price row for its **Foil/Holofoil** treatment with a nonzero finite
guide amount and an actual `market_price_as_of` within 14 days. A
different provider product ID, different printing subtype, ambiguous
same-rarity results, future date, stale guide or missing source publication
date is unavailable rather than a plausible price.

The last-stage source merger separately verifies these fields. **Cached
records written by an older unverified importer can never replace TCGCSV**
merely by containing a numerical `market` price. New approved selections,
rejections and source cache date appear in
`data/tcgapi-identity-audit.json`; the user interface labels the
unavailable/optional state. No TCG API provider pricing is fetched or
claimed when an authenticated key is absent.

As publicly described at
https://tcgapi.dev/, the provider restricts Free, Hobby and Starter
tiers to personal/non-commercial use; Pro/Business list commercial licenses.
Any deployment using this optional source must satisfy the account's
licensing and attribution obligations. This implementation does **not**
enable an account, purchase a tier or claim permission to redistribute
restricted datasets. Cardmarket and TCGCSV remain separate price
**guides**, not independently verified completed sales.

These fixture tests secure data-processing contracts; **the live TCG API
premium importer has not been verified with a real authenticated key in
this PR**.
