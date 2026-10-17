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


## Financial Resilience Score (návrh rozšírenia)
Samostatný modul `resilience.py` používa váhy FCF 25 %, zadlženie 20 %, rast a marže 20 %, valuácia 15 %, riedenie 10 %, závislosť od AI capexu 10 %. Dostupné kategórie sa normalizujú; istota je súčet dostupných váh. N/A nikdy nie je nula. Stupnice (ohraničené 0–100): FCF 50 + 250 × marža; dlh 100 − 25 × kladný čistý dlh/EBITDA; rast/marže 50 + 150 × rast tržieb + 100 × prevádzková marža; valuácia 110 − 2 × forward P/E (nekladný násobok = 0); riedenie 100 − 1000 × kladný rast počtu akcií; AI capex 100 × (1 − overený podiel expozície).

Súčasní provideri nedodávajú všetky vstupy. Modul preto používa len dostupné položky `revenue_growth`, `operating_margin`, `forward_pe`; ostatné zostávajú N/A, kým sa nedoplnia overené `fcf_margin`, `net_debt_ebitda`, `share_dilution`, `ai_capex_exposure`. Neodvodzuje FCF maržu miešaním ročných SEC a TTM Yahoo údajov. Súčasné čiastkové skóre má maximálne 35 % pokrytie.

Stresový model vyžaduje `annual_revenue`, `annual_fcf`, `annual_gross_margin` za rovnaké ročné obdobie a v rovnakej mene, `cash` a `debt_due_24m`. Pokles tržieb o 20 % trvá dva roky; stratený hrubý zisk znižuje FCF, fixné náklady, capex a pracovný kapitál sa nemenia, bez nového financovania. Koncová hotovosť = hotovosť + 2 × stresované FCF − splatný dlh. Bez kompletných vstupov je výsledok N/A; provider ich zatiaľ nedodáva. Kladný výsledok negarantuje priebežnú likviditu.

Yahoo odpoveď s iným symbolom sa odmietne a využije sa existujúca SEC záloha. COHR nemá osobitné vymyslené hodnoty. Pri zlyhaní Yahoo sa overený názov doplní zo SEC. Živé načítanie COHR a celý Streamlit test suite treba overiť v prostredí s nainštalovanými requirements; čistý model sa overí cez `python -m unittest discover -s tests -p test_resilience.py`.
