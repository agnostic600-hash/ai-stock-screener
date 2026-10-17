# AI Stock Screener

Webová aplikácia v Pythone a Streamlite so slovenským rozhraním pre americké a európske akcie. Obsahuje fundamentálny screener, filtre, porovnanie, cenové grafy, export CSV a poradie zadaných akcií podľa transparentného skóre 0–100. Názov AI označuje analytický produkt; hodnotenie je deterministický pravidlový model, nepoužíva LLM.

## Lokálne spustenie

Vyžaduje Python 3.11 alebo 3.12 a internet pre finančné dáta.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Zadajte napríklad `AAPL, MSFT, ASML.AS, SAP.DE, MC.PA, SHEL.L`. Aplikácia načítava dáta až po kliknutí na **Analyzovať akcie**, najviac 20 tickerov. Yahoo Finance funguje bez kľúča, ale dostupnosť a limity nie sú garantované. Poskytovateľ môže vrátiť oneskorené alebo neúplné údaje. Žiadne dáta sa nevymýšľajú: neznáme položky sú N/A.

## API a bezpečnosť

Voliteľne zvoľte **Alpha Vantage** pre fundamenty. Vytvorte si kľúč na https://www.alphavantage.co/support/#api-key a nastavte premennú prostredia `ALPHAVANTAGE_API_KEY` pomocou správcu tajomstiev svojho prostredia. Alternatívne vytvorte lokálny ignorovaný súbor `.streamlit/secrets.toml`:

```toml
ALPHAVANTAGE_API_KEY = "SEM_PATRÍ_VÁŠ_KĽÚČ"
```

Skutočný kľúč nikdy necommitujte. Aplikácia ho nežiada vo webovom formulári, nezobrazuje ani neloguje. Cache je serverová, spoločná pre relácie, s platnosťou 5 minút; kľúč je súčasťou jej hashovaného identifikátora. Používajte kľúč správcu nasadenia. Pri chybe API sa nezobrazuje surová odpoveď ani URL s kľúčom.

Alpha Vantage má podľa plánu prísne limity a odlišné symboly; OVERVIEW nemusí podporovať požadovanú európsku akciu. Poskytuje iba časť fundamentov. FCF, ROIC a ďalšie nepodporované ukazovatele zostávajú N/A; aplikácia ich potichu nemieša s druhým poskytovateľom. Cenový graf pochádza z Yahoo Finance. Pri neúplných dátach nemusí existovať celkové skóre.

Sieť potrebuje HTTPS na `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`, `guce.yahoo.com` a voliteľne `www.alphavantage.co`; inštalácia potrebuje PyPI. V obmedzenom cloude musia byť povolené príslušné domény. Dostupnosť sa overuje skutočným načítaním, nie prítomnosťou kľúča.

## Metodika a limity

Aplikácia zobrazuje P/E, forward P/E, PEG, medziročný rast tržieb a zisku, EPS, hrubú, prevádzkovú a čistú maržu, voľný cash flow, dlh/vlastné imanie, bežnú likviditu a ROIC. Percentá sa zobrazujú v percentuálnych bodoch; FCF a EPS v mene výkazov, cena v mene kotácie (pri britských tituloch môže ísť o GBp). Meny sa neprepočítavajú.

Skóre používa štyri rovnako vážené oblasti. V oblasti sa priemerujú dostupné indikátory; celkové skóre vyžaduje aspoň 7 z 11 indikátorov a zastúpenie všetkých štyroch oblastí. Pokrytie je vždy viditeľné.

| Oblasť | Stupnica od horšieho po lepšie |
| --- | --- |
| Podhodnotenie | P/E 40→10, forward P/E 35→10, PEG 3→0,5; iba kladné násobky |
| Indikátory moat | Hrubá marža 10→60 %, prevádzková marža 0→30 %, ROIC 0→25 % |
| Stabilita | Dlh/vlastné imanie 2→0 (záporné N/A), likvidita 0,5→2, FCF kladný 100 / nekladný 0 |
| Rast | Rast tržieb a zisku 0→30 % |

Stupnice sú lineárne, ohraničené na 0–100 a nie sú kalibrované na konkrétne odvetvie. ROIC je NOPAT delený priemerným ročným kapitálom (dlh + vlastné imanie − hotovosť). Počíta sa len pri úplných, časovo zladených výkazoch a použiteľnej efektívnej daňovej sadzbe; inak N/A. Poskytovatelia môžu používať iné definície. Údaje TTM, ročné výkazy a analytické odhady sa môžu vzťahovať k odlišným obdobiam. Čas načítania nie je časom poslednej aktualizácie poskytovateľa.

Moat je len finančný indikátor, nie potvrdenie konkurenčnej výhody. Scenár EPS na 3–5 rokov mechanicky udržiava posledný medziročný rast zisku: EPS × (1 + rast)^roky. Nie je to prognóza ani cieľová cena. Banky, poisťovne a REIT potrebujú osobitné modely. Poradie je iba v rámci zadaných tickerov, nejde o celý investičný trh. Nejde o investičné odporúčanie. Rešpektujte licenčné podmienky Yahoo Finance a Alpha Vantage pred verejným alebo komerčným použitím.

## Testy

```bash
python -m pytest -q
```

Testy pokrývajú skórovanie, chýbajúce hodnoty, záporné násobky a vlastné imanie, ROIC, tickery, scenáre, chyby API, normalizáciu údajov a Streamlit rozhranie. API je v testoch nahradené kontrolovanými odpoveďami; testy nepotrebujú internet ani kľúč. Živé dáta overte samostatne analýzou platného tickera.

## Streamlit Community Cloud

1. Uložte tento projekt do GitHub repozitára.
2. Na https://share.streamlit.io vytvorte aplikáciu z repozitára, vyberte vetvu a hlavný súbor `app.py`.
3. V rozšírených nastaveniach zvoľte Python 3.12. Závislosti sa nainštalujú z `requirements.txt`.
4. Voliteľný kľúč vložte v nastaveniach aplikácie do **Secrets** v TOML formáte uvedenom vyššie. Nenahrávajte lokálny secrets súbor do GitHubu.
5. Spustite analýzu tickera a skontrolujte zdroj, upozornenia, pokrytie a graf. Limity API alebo blokovanie Yahoo sa môžu líšiť od lokálneho prostredia.

Nastavenie témy a bezobslužného servera je v `.streamlit/config.toml`. Nepotrebujete databázu ani ďalšiu službu. Nasadenie vyžaduje prístup k vášmu GitHubu a účtu Streamlit; samotné vytvorenie súborov aplikáciu nepublikuje.


## Diagnostika načítania a bezplatná záloha SEC EDGAR

Predvolená cesta je Yahoo Finance cez aktualizovaný yfinance 1.7.0. Chyba fundamentov sama osebe neznamená chybný ticker: COHR je symbol Coherent Corp. na NYSE, SAP.DE je Yahoo symbol pre Frankfurt a ASML.AS pre Amsterdam. Symboly sa automaticky neprepisujú na inú burzu. Triedy US akcií (napr. BRK.B) sa iba pri hľadaní v SEC normalizujú na BRK-B. Yahoo suffixy nie sú univerzálne symboly pre ostatné API.

Aplikácia rozlišuje proxy/sieťové blokovanie, HTTP 429, HTTP 401/403, HTTP 404, timeout, TLS a neúplnú odpoveď. Ak yfinance chybu interne potlačí a vráti iba prázdnu odpoveď, aplikácia nedokáže spätne určiť HTTP stav a uvedie neúplnú odpoveď. Neoznačuje firmu za neexistujúcu iba preto, že poskytovateľ zlyhal. Nezobrazuje surové výnimky, URL s kľúčmi ani obsah chybovej odpovede.

Pri chýbajúcich Yahoo fundamentoch sa automaticky skúsi **SEC EDGAR**, oficiálny zdroj bez API kľúča: register tickerov a Company Facts. SEC nezávisle overí ticker a CIK, potom doplní iba chýbajúce údaje. Podporované sú ročné US-GAAP údaje v USD z 10-K/10-K/A: EPS, marže, rast ročných tržieb/zisku, FCF (prevádzkový cash flow − kapitálové výdavky) a bežná likvidita. Výpočty vyžadujú zladené obdobia; chýbajúce položky nenahrádza nula. Pri nekladnom minuloročnom zisku sa percentuálny rast zisku nevypočíta. Aktuálna cena, P/E, forward P/E, PEG, dlh/vlastné imanie a ROIC zo SEC sa nedopočítavajú. Záloha nie je garantovaným zdrojom pre európske firmy ani IFRS/20-F.

**Ročné údaje SEC nie sú TTM ani odhady.** Pri každom použitom údaji je v detaile jeho zdroj a pri SEC aj koniec obdobia. Existujúce údaje Yahoo sa neprepisujú; ak Yahoo uvádza inú menu výkazov než USD, SEC USD údaje sa nemiešajú. Výsledné skóre môže obsahovať odlišné obdobia, na čo aplikácia upozorňuje. Pri výpadku oboch zdrojov zostáva N/A aj s dôvodom. Cache má platnosť 5 minút, aby dočasný výpadok nezostal pol hodiny; možno ju ručne vymazať.

SEC vyžaduje identifikovaný User-Agent podľa https://www.sec.gov/about/developer-resources. Voliteľne nastavte **SEC_USER_AGENT** napríklad na názov aplikácie a kontaktný e-mail prevádzkovateľa, iba v prostredí v prostredí. Nejde o API kľúč. Bez nastavenia sa používa názov aplikácie a verejná adresa projektu. SEC môže automatické požiadavky aj napriek tomu obmedziť. Požiadavky sú na proces serializované, začínajú najviac 4-krát za sekundu. HTTP 429/5xx sa opakuje maximálne raz pri krátkom Retry-After, bez nekonečného skúšania; dlhý Retry-After sa neobchádza.

V sieťovej politike povoľte navyše **www.sec.gov** a **data.sec.gov**. Na Streamlit Community Cloud povoľte odchádzajúce HTTPS, aktualizujte závislosti/reštartujte aplikáciu a skúste COHR; zobrazte detail zdrojov a diagnostiku. Lokálne overenie v spravovanom cloude narazilo na proxy 403 pre Yahoo aj SEC. To nie je dôkaz, že COHR nie je platný, ani potvrdenie rovnakého problému na vašom Streamlit hostingu. Automatické testy používajú výhradne označené syntetické odpovede; živú dostupnosť SEC v blokovanom prostredí nemožno potvrdiť.


## Financial Resilience Score
`python -m pytest -q` runs the full suite, including Streamlit AppTest. The pure scorer in `resilience.py` consumes a provider-neutral `Stock.resilience_inputs` schema, populated by `resilience_data.py` / `data.py`. Input keys are stable and missing values are explicit None. The loader accepts one symbol; it has no UI or universe-discovery dependency. A future market-universe service can feed the same loader and scorer without changing the model. No all-market scanning is implemented in this PR.

Weights: FCF 25%, debt 20%, growth/margins 20%, valuation 15%, dilution 10%, AI-capex dependence 10%. Available categories are normalized; confidence measures available weight, not probability. No missing category contributes zero. Category ramps, bounded 0–100: FCF 50+250×margin; debt 100−25×positive net debt/EBITDA; growth/margins 50+150×revenue growth+100×operating margin; valuation 110−2×forward P/E (nonpositive multiple=0); dilution 100−1000×positive share growth; AI exposure 100×(1−verified exposure).

### Sources and alignment
- Yahoo annual income, cash-flow and balance frames must share fiscal year end and have a reporting currency. FCF = operating cash flow + negative capex, with invalid capex sign rejected. FCF margin, operating margin, net debt/EBITDA, prior-year revenue growth and weighted diluted-share growth are derived from annual statements, not from mixed TTM summary fields.
- Yahoo fundamentals must return the requested symbol before they can supply resilience inputs. SEC registry matches exact normalized ticker and validates returned CIK. Existing SEC fallback and other screener features remain.
- SEC accepts 10-K/10-K/A US-GAAP annual USD flows, matching revenue start/end; instant balances and maturity disclosures must match year end. FCF = OCF − nonnegative capex. Debt needs explicit noncurrent/current or aggregate long-term debt plus explicit short-term borrowings; absence is not zero. EBITDA proxy = operating income + explicit combined D&A. Dilution uses aligned prior-year weighted diluted shares.
- For a newer annual bundle, old inputs are discarded. Same-year-end USD bundles can supplement with independently derived ratios and per-field provenance. A non-USD Yahoo issuer is not blended with SEC USD. No FX conversion or TTM/annual blending. Yahoo forward P/E is separately labeled as a current provider estimate.
- The UI shows source, annual end, currency and every available input. Data from Yahoo is provider-normalized; the same year end is not an independent guarantee against provider accounting restatements.

### Stress and unavoidable N/A
20% revenue loss persists for two years; lost gross profit reduces annual FCF. Fixed costs, capex and working capital remain constant. End cash = initial cash + 2×stressed FCF − debt due within 24 months, without refinancing. This is a historical balance-sheet-date scenario, not 24 months from today. Positive end cash does not guarantee interim liquidity; dividends, buybacks, new M&A, tax changes and interest resets are not separately forecast.

The SEC debt-due mapping requires explicit next-12-month principal maturities, year-two principal maturities and short-term borrowings. Missing any component means N/A; it never substitutes all debt or twice current debt. Custom extensions and untagged narrative maturity tables are unsupported. The maturity model covers disclosed borrowings, not every future lease/contractual commitment.

AI-capex revenue exposure is not a standardized Yahoo/SEC field; it remains N/A without a separate verified disclosure. Weighted diluted-share growth is a dilution proxy affected by convertible instruments and EPS dilution rules; it is not a direct measurement of share issuance. Nonpositive EBITDA cannot yield net-debt/EBITDA. SEC IFRS/20-F and many European issuers are unsupported by this US-GAAP annual parser; Yahoo may supply annual figures instead. Missing provider values, mismatched identity/periods and missing currency fail closed. Period age is shown, not silently rolled forward. No live-source availability or independent financial audit is guaranteed.

See `VALIDATION.md` for separate synthetic tests, server checks and live COHR observations.

## FÁZA 2 — Market Discovery MVP
Select **Market Discovery** in the sidebar; individual-stock analysis stays in its original mode. Click **Vyhľadať príležitosti / ďalšia dávka**; no ticker entry is needed. Default batch 10, configurable up to 100. Further batches resume a durable SQLite universe pass; 100 is the maximum batch size, not a traversal limit. **Nový úplný priechod** is allowed only after every snapshot symbol has a completed attempt. Browser state and expiring quote cache do not control traversal progress. This is user-triggered discovery, not a continuously running background scheduler.

### Real data sources
- NASDAQ Trader Symbol Directory: `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt` and `https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt`. Both must parse with their expected pipe-delimited schema and file-creation footer. Only NASDAQ plus NYSE exchange code N; excludes ETF/test/NextShares and preferred/warrant/right/unit/debt/fund terms in names. ADRs are allowed; name classification is imperfect and two share classes count as two securities. No seed ticker list or manufactured results.
- Existing Yahoo/SEC loader supplies real annual fundamentals, company identity, description/industry and adjusted daily close/volume. SEC exact ticker/CIK checks remain; a missing or mismatching Yahoo symbol cannot supply profile or resilience statement inputs. Yahoo non-equity quote types cannot enter the ranking. Directory membership does not guarantee a security has all required fundamentals.
- `market_universe.py` owns universe ingestion; `discovery.py` owns sample selection, ranking and filters; provider-neutral `Stock` remains shared with the original analysis. Universe discovery does not require changing the scorer or data provider. A paid bulk data adapter or scheduler can replace the bounded loader loop later.

### Ranking and filters
All scores are documented heuristics computed from source metrics, not generative AI or synthetic company values. Discovery score is the equally weighted average of growth/margins, valuation, FCF, debt and Financial Resilience Score. The first four use existing resilience component scales; reusing them inside the resilience score deliberately increases their effective influence. Every primary component must exist, identity must be verified, resilience coverage must be ≥70%, annual end must be known, not in the future and no older than 550 days. Otherwise discovery score is N/A and the security is shown among attempts, not assigned zero or silently replaced by a different company. The UI lists exclusion reasons and missing fields. TOP 20 contains at most 20 **eligible analyzed securities**, after filters; it is never called a scan of the entire market.

Selection order is SHA-256(`discovery-v1:` + symbol), fixed for a frozen universe snapshot in each durable pass. It is deterministic and independent of scores, without market-cap or liquidity preselection; it can contain small/illiquid or sector-specific businesses unsuitable for generic ratios. This MVP is a sample, not a representative performance study or a marketwide best-picks claim.

Filters:
- AI infrastructure / robotics: case-insensitive keyword matches in verified Yahoo industry/business description. Displayed as heuristic themes, not proven AI revenue exposure; no description means N/A. Full keyword rules are in `discovery.py`.
- Undervalued growth: annual revenue growth ≥15%, 0<forward P/E≤25, FCF margin>0. This does not calculate fair value.
- Swing: adjusted close and 20-close average above 50-close average, five-close return between −8% and 0%, last volume ≥1.2×20-day volume, average dollar volume ≥USD 1m. Requires 55 positive closes, 20 aligned volumes, USD price currency and latest price ≤7 days old. No missing volumes or prices are invented; this is not a trading recommendation.

### Counts, cache and quotas
`Cache` stores only JSON in SQLite at `DISCOVERY_CACHE_PATH` (default `.cache/discovery.sqlite3`, ignored by Git). Directory and usable stock payload TTL: 24 h; unusable attempts: 15 min. Cached payloads retain original fetched time, fiscal end, missing inputs and per-field provenance; cache hits do not masquerade as a new fetch. Price history retains the last trading date. A new full pass does not wipe cache, network budget or prior-pass audit records. Cache storage is deployment-local; use a persistent writable volume to retain it across restarts. Do not place secrets in it.

One process-wide gate serializes discovery network analyses and spaces their starts by at least 3 seconds. There is a persisted budget of 100 **new analyzer invocations** per UTC day per cache, not 100 HTTP requests: one analyzer may make multiple Yahoo/SEC requests. Existing SEC limiter remains at max 4 request starts/s. On a freshly encountered 429 or 401/403 warning, stop the batch and persist a 15-minute cooldown. Cached older warnings do not repeatedly extend it. Cache hits still work during cooldown/budget exhaustion. Yahoo does not offer a guaranteed public quota/SLA; these are conservative controls, not a promise of free marketwide coverage. Multiple processes/replicas with separate locks/caches need a centralized distributed limiter before scaling. No retry loop bypasses provider blocks.

Counters distinguish frozen directory size, durable completed attempts in the pass, identity+at-least-one-financial-input analyses, rankable securities, and per-batch network analyzer calls/cache hits. Failed or partial results remain visible. Source file-creation strings and fetched UTC timestamps are both displayed. Financial payloads older than 48h do not enter current TOP ranking; historical scores and exclusion audits remain available. A 54-day pass is not a synchronized market snapshot. Start the next full pass only when the current pass is finished; no silent refresh retries completed tickers ahead of pending ones.

### Run and validate
```
python -m pip install -r requirements.txt
streamlit run app.py
python discovery_cli.py --limit 10 --output discovery-result.json
python discovery_cli.py --limit 10 --output discovery-result.json  # resumes durable progress
python discovery_cli.py --limit 10 --new-pass --output discovery-result.json  # only after full completion
python -m pytest -q
```
CLI is an actual network/cache run, never fixtures; its output path is ignored by Git by default. Tests inject synthetic provider responses and are explicitly not live-data evidence. Live run observations are recorded separately in `DISCOVERY_VALIDATION.md`. No secret/API key is needed for these public sources. Do not promise complete live fundamentals, FCF, maturity or AI-capex coverage; original N/A and accounting/stress limitations still apply.


### Representativeness and durable traversal (PR #2 review)
The SHA-256 order is a deterministic, data-independent permutation. It is neither alphabetical nor an investment screen, and is not a formally randomized probability sample. Do not infer marketwide representativeness from its first 100 records. No ticker is replaced just because its analysis fails or cannot be scored.

`discovery_campaign.py` persists an immutable listing snapshot and pending/running/done state per symbol, separately from the expiring cache. SQLite immediate transactions prevent overlapping reservations. Results are committed once per reservation owner. A crashed worker's 15-minute lease can be recovered; failed completed attempts remain done and auditable. A quota stop before an attempt releases the reservation, so the next batch resumes that symbol. Completed symbols are not revisited until every symbol has an attempt and the user starts a new full pass. This survives browser/server restarts **if the same SQLite file persists**; ephemeral disk loss or deleting the database loses that guarantee. Directory additions/removals are deferred to the next snapshot. This is a single-shared-SQLite deployment mechanism, not a distributed scheduler or exactly-once HTTP guarantee after crashes.

TOP headings and CSV exports include total financial analyses, attempts, rankable-at-fetch securities, currently eligible (48h) securities and filter-matching count, plus universe size. All-pass results can be old: completed attempts do not imply recent or successful financial coverage. Current TOP excludes fetched payloads older than 48h and annual periods older than 550 days, so it intentionally cannot masquerade as a fresh whole-market TOP after a long sweep.

`discovery_audit.py` reports overlapping and first-blocking reasons, plus attempted/analyzed/rankable counts by exchange, sector, available market-cap bucket and source. Exchange population shares are available from the listing snapshot. Sector/size population distributions are not known without fetching those fundamentals, so no population-level sector/size representativeness or causal fairness claim is made. Unknown groups stay N/A. Missing-data eligibility does favor companies with complete standard financial statements and forward estimates; N/A is never assigned zero, but unranked firms are not necessarily worse investments. Nonpositive EBITDA and sector-inapplicable metrics can also cause N/A; aggregated exclusion categories alone cannot distinguish every accounting cause. Generic EBITDA/FCF models are especially unsuitable for some banks/financial firms.

Cold coverage of 5,370 symbols at 100 new analyzer calls per UTC day requires 54 daily budgets (about eight weeks with daily triggering; longer with skipped days, provider blocks or retries). Cache can reduce calls; active work at an illustrative 5–20s/company is about 7.5–30h spread over those days, not an upper bound or SLA. The 3s start-spacing floor alone is about 4.5h and is not a realistic elapsed-time promise. The engine remains user-triggered. Current whole-market daily coverage would require a licensed bulk-data source and scheduler/distributed quota management, not a larger displayed counter.

See `REPRESENTATIVENESS_REVIEW.md` for the historical 100-attempt sample audit, distinct from new network observations.
