# PR #2 representativeness review — 2026-10-17

Historical evidence. The later `STORAGE_AND_FRESHNESS.md` supersedes the combined cache / 48h fundamental expiry architecture described below.

## Selection
The first sample was the first 100 of the stable SHA-256(`discovery-v1:` + symbol) permutation of the 5,370-symbol NASDAQ Trader snapshot. It was not alphabetical, handpicked, investment-filtered or formally randomized. Data availability is not an input to selection. This order is reproducible, not a guarantee of a representative market sample.

## Historical real-data sample audit (not a new live run)
Recomputed from the saved real result JSON from the earlier 2026-10-17 live validation. No provider fixtures or substituted financial values were used. Sector labels were supplemented where available from the same real cached Stock records; old payloads do not contain market cap, so size groups remain N/A. This is a historical audit, not a new claim of 100 fresh network analyses.

100 attempted securities → 90 verified identity + at least one required financial input → 46 rankable at fetch. The remaining 10 attempts lacked verified usable financial analysis. Among the 90 analyses, 44 were unranked.

Overlapping blocking categories within these 44:

| Category | Count |
| --- | ---: |
| Debt component unavailable / unusable | 40 |
| Growth/margins component unavailable / unusable | 14 |
| FCF component unavailable / unusable | 11 |
| Valuation component unavailable / unusable | 7 |
| Annual period missing/future/older than 550 days | 2 |
| Resilience coverage below 70% | 24 |

These counts must not be added: a company can fail several conditions. First-blocking technical reason counts sum to 44: debt 20, growth/margins 13, valuation 6, FCF 3, annual period 2. Priority is code order, not a causal attribution. Unusable debt can reflect missing raw inputs or nonpositive EBITDA; this report does not prove every underlying reason.

## Availability/model eligibility bias

| Exchange | Universe | Sample attempts | Financial analyses | Rankable | Rankable / attempts |
| --- | ---: | ---: | ---: | ---: | ---: |
| NASDAQ | 3,406 | 59 | 50 | 18 | 30.5% |
| NYSE | 1,964 | 41 | 40 | 28 | 68.3% |

NASDAQ is 63.4% of the listing snapshot and 59% of the sample; NYSE is 36.6% / 41%. This describes the one deterministic sample; no statistical confidence interval or random-sampling inference is claimed. Rankability is substantially different, which is evidence against calling the final ranking data-neutral. It is not evidence of superior NYSE investment performance or proof that exchange alone causes missing data.

The sample contained 14 Financial Services securities and none was rankable; Technology 8/15, Healthcare 5/16, Industrials 10/16 were rankable. Generic EBITDA/FCF/forward-PE models and accounting coverage are not equally suitable across sectors. Full universe sector and market-cap distributions are unknown. We cannot rule out size/sector availability bias; the UI explicitly warns about it, retains incomplete candidates and exposes group coverage rather than inventing comparable scores.

## Fixes
- Durable per-snapshot traversal replaces browser-only offsets. Completed attempts (including failures) are not repeated on cache expiry/restart. Quota-blocked unattempted symbols remain pending. Full new pass is blocked until completion. Concurrent claims use transactions; crash recovery uses a 15min lease. Same persistent database is required.
- TOP and CSV include attempted/financial/rankable/current/filter denominators. Historical data fetched over 48h ago is excluded from current TOP, while its audit remains.
- UI reports all and primary blocking reasons and exchange/sector/known-size/source eligibility rates; unknown groups are not discarded.
- Old pre-ledger results are not silently presented as newly persisted campaign work. The local real-cache campaign validation resumed 14 cached attempts then stopped at the first expired payload because the daily network budget was already exhausted; it did not skip that pending symbol or fabricate further progress.

## Time and scope
At 100 new analyzers/day, a cold 5,370-symbol pass requires 54 daily budgets. Assume daily manual runs: roughly eight weeks minimum as a planning figure; blocked sources/skipped days can extend it. Active processing at illustrative 5–20s per company is ~7.5–30h, not a bound. One analyzer invokes multiple HTTP requests. Completed attempts do not mean complete usable fundamentals. The 48h current-TOP window means a 54-day pass cannot be called a synchronized whole-market ranking.

## Validation
81 automated tests including original tests and Streamlit AppTest passed before final documentation changes. Added contracts for full traversal across restart, frozen snapshots, no partial reset, disjoint leases/crash recovery, budget stops, failed-attempt fairness, data-independent selection, measured missing-data bias, stale-TOP exclusion and persistent UI denominators. Tests use synthetic contracts, not live provider evidence. Separately, the actual UI rendered the persisted real-cache campaign with counters 5,370 / 14 / 14 / 9 and the explicit TOP 9 of 14 heading, with no new provider calls and no exceptions. No graphical mobile browser QA.

Existing branch/PR #2 only. No merge performed.
