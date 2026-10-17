# Market Discovery MVP — validation 2026-10-17

## Automated contracts (not live financial facts)
Complete original and new suite: `python -m pytest -q` — **71 passed**, including Streamlit AppTest. New tests cover official directory schemas/exclusions, NYSE N selection/class symbols, malformed/truncated files, deterministic sampling/offset, cache expiry and history round-trip, real-metric eligibility/missing-data exclusion, stale annuals, thematic/value/swing filters, cache/attempt/network counters, budget/cooldown behavior, loader failures and both UI modes. Synthetic fixtures are explicitly confined to tests.

The Streamlit server started with root and health endpoints returning HTTP 200. No graphical mobile browser inspection was performed.

## Separate live runs — no provider fixtures
Both public NASDAQ Trader files returned HTTP 200. Parsed eligible universe: **5,370 securities**. Original file-creation strings: `1016202621:31` for both files (retained exactly as published; no invented source timezone). Universe fetched at 2026-10-17T19:16:44.901442+00:00.

Initial actual sample: 5 attempts, 5 identity+financial-input analyses, 2 rankable securities.

Expanded actual run: `python discovery_cli.py --limit 100`, completed 2026-10-17T19:22:29.602892+00:00:
- 100 unique sample attempts; 95 new analyzer calls plus 5 existing live-cache hits.
- 90 securities had verified identity and at least one required financial input.
- 46 had all primary ranking dimensions and sufficient coverage/current annuals.
- Exactly 20 eligible rows returned in TOP 20; the other 54 incomplete/stale/ineligible attempts were not assigned fabricated discovery scores.
- 13 sample rows matched the broad AI-infrastructure keyword rules and 4 robotics rules. These are description-based tags, not independently audited thematic revenue exposure.
- No rate-limit stop was triggered in this run. This does not establish a guaranteed provider quota or continuous availability.

Live payloads are stored only in the ignored local JSON/SQLite cache, not committed as a fixed result list. The initial live run occurred while the final budget/UI refinements were being completed; the final code was separately exercised against the same real cache and through the full test suite. The persisted daily budget was then set to account for the 100 actual unique analyzer loads already used during validation. No financial values were edited.

The final-code cache rerun produced 100 cache hits, 0 new analyzer calls, the same 90 analyzed / 46 rankable securities and 20 TOP rows. An actual Streamlit AppTest render using those live cached payloads (no provider mocking) displayed counters 5,370 / 100 / 90 / 46 and 20 TOP rows without exceptions. This is live-cache UI validation, distinct from both fresh-source access and synthetic UI tests.

## Limitations / review expectations
This is a bounded user-triggered MVP, not a complete daily scan of 5,370 securities or an always-on scheduler. Ranking is only within the analyzed sample. Missing fields are N/A, and all four primary dimensions are required for a discovery score. Cache TTL is 24h for usable results and 15min for failed attempts; network budget is 100 analyzer invocations per UTC day per cache/process, not 100 HTTP requests. One invocation may issue multiple Yahoo/SEC requests. Multi-replica deployment needs a distributed limiter and shared persistent cache before scaling.

Selection is reproducible hash order, not market-cap/liquidity preselection or a claim of representative market performance. New cycles rotate to another sample. Directory filters are heuristic beyond official ETF/test flags; ADRs and multiple share classes remain. Theme keywords can over/under-classify. Swing is a documented price/volume screen, not a backtested strategy. Annual data can be up to 550 days old and forward estimates come from the provider; fetched time is not fiscal freshness. Original resilience/stress/SEC coverage limitations remain. Sources are not independently audited and may fail or revise values.

New branch and PR only; no merge into main is authorized or performed.
