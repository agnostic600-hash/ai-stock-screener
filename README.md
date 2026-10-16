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

Skutočný kľúč nikdy necommitujte. Aplikácia ho nežiada vo webovom formulári, nezobrazuje ani neloguje. Cache je serverová, spoločná pre relácie, s platnosťou 30 minút; kľúč je súčasťou jej hashovaného identifikátora. Používajte kľúč správcu nasadenia. Pri chybe API sa nezobrazuje surová odpoveď ani URL s kľúčom.

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
