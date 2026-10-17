# PR #1 validation — 2026-10-17

## Automated tests (synthetic fixtures)
Python 3.12, clean virtual environment installed from the committed requirements.txt. `python -m pytest -q`: **42 passed in 2.29s**. This includes the complete original suite, scoring, provider/SEC error and COHR identity regressions, Streamlit AppTest flows, and two new resilience UI tests (missing inputs and complete synthetic inputs with funding shortfall). Synthetic fixtures do not verify current financial facts.

No failing test required a production-code fix. Added regression coverage and a GitHub Actions workflow to run the complete suite on push/PR.

## Server startup
`python -m streamlit run app.py --server.port 8501 --server.address 127.0.0.1 --browser.gatherUsageStats false` started successfully. Local `/_stcore/health` and `/` returned HTTP 200. AppTest executes the actual Streamlit application; a graphical browser/mobile layout inspection was not performed.

## Separate live probe — not mocked
A separate Python subprocess called `data.load_stock('COHR')` without pytest, monkeypatching or fixtures, with a 45-second process deadline. It succeeded:
- Company: Coherent Corp.
- Source: Yahoo Finance + SEC EDGAR annual fallback.
- Reported fiscal date: 2026-06-30.
- Available metric keys: price, pe, forward_pe, revenue_growth, eps, earnings_growth, gross_margin, operating_margin, profit_margin, fcf, debt_equity, current_ratio, roic.
- SEC supplied annual earnings_growth; this remains explicitly distinguished from Yahoo TTM metrics via provenance.
- PEG remained N/A.

This establishes access and successful parsing at the time of this probe, not independent accuracy verification or a guarantee of ongoing provider availability. It does not verify every ticker.

## Merge recommendation
Keep PR #1 as draft / **not ready for full feature acceptance**. The code tested successfully, but provider mapping still only covers growth/margins and forward valuation for resilience (maximum 35% confidence). Verified FCF margin, net debt/EBITDA, dilution, AI-capex exposure and aligned 24-month stress inputs are not wired. Financing capacity correctly stays N/A. Do not present this draft as a completed resilience product. Complete and validate these data mappings before marking ready to merge. No merge was performed.
