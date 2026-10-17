# PR #1 validation — 2026-10-17

## Full automated suite (synthetic contracts)
Python 3.12 clean virtual environment using committed requirements. Full `python -m pytest -q` passes **56 tests** including Streamlit AppTest, original screener/provider/SEC regressions, and annual resilience mapping contracts. Added tests cover annual alignment, missing currency, capex sign, missing/negative debt, explicit zero borrowings, missing second-year maturities, quarter/instant rejection for annual flows, prior-year share alignment, issuer mismatch, provider failure, newer-bundle replacement, end-to-end SEC-to-score/stress, and N/A UI. Fixtures are synthetic and are not current company facts.

## Actual Streamlit startup
The Streamlit server started; local `/` and `/_stcore/health` returned HTTP 200. AppTest exercises rendered UI logic. No graphical browser or real mobile layout inspection was performed.

## Separate live COHR observation (no mocks)
A separate subprocess invoked `load_stock('COHR')` outside pytest. Both Yahoo Finance and SEC EDGAR responded. Identity: Coherent Corp.; annual end 2026-06-30, USD. FCF margin, net debt/EBITDA, revenue growth, operating margin, forward P/E and weighted diluted-share growth were populated with per-field provenance. Observed resilience score 51.9/100, coverage 90%; AI-capex dependence remained N/A. The model lacked a fully supported `debt_due_24m`, so financing status remained N/A. A second Yahoo annual statement check found the same revenue/cash and slightly different FCF than SEC, demonstrating why provider provenance remains visible. Sources are not independently audited and the probe does not guarantee ongoing access or cover every issuer.

## Scope and remaining limits
All implemented standard-field mappings are wired. Missing proprietary AI-capex exposure and company-specific/narrative debt-maturity disclosures remain N/A by design. No total-debt substitution, fabricated maturity or zero-fill. See README for accounting proxies, annual-source dates, US-GAAP/European coverage, and stress assumptions. Historical annual cash is not current liquidity. The stress outcome covers debt principal plus short-term borrowings, not every lease, commitment or intra-period timing requirement.

The stable provider-neutral schema and pure scoring functions are separate from the Streamlit ticker input. Future all-market discovery is intentionally outside this PR. Existing PR #1 only; no merge performed. The bounded change is suitable for merge once the full hosted CI checks for its latest commit pass; it does not promise complete data for every company.
