import os
import pandas as pd
import plotly.express as px
import streamlit as st
from data import load_stock
from resilience import evaluate_resilience, stress_24m
from screener import METRICS, PERCENT, evaluate, scenario, tickers

st.set_page_config(page_title='AI Stock Screener', page_icon='📈', layout='wide')
st.title('📈 AI Stock Screener')
st.caption('Americké a európske akcie • transparentná fundamentálna analýza')
st.info('Skóre je pravidlový analytický model, nie výstup generatívnej AI ani investičné odporúčanie. Údaje môžu byť oneskorené. N/A znamená chýbajúci alebo nepoužiteľný údaj.')


def secret_key():
    key = os.getenv('ALPHAVANTAGE_API_KEY', '')
    if key:
        return key
    try:
        return st.secrets.get('ALPHAVANTAGE_API_KEY', '')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''


@st.cache_data(ttl=300, max_entries=100, show_spinner=False)
def cached_stock(symbol, provider, api_key):
    return load_stock(symbol, api_key, provider)


with st.sidebar:
    st.header('Výber akcií')
    raw = st.text_area('Tickery oddelené čiarkou', 'AAPL, MSFT, ASML.AS, SAP.DE')
    st.caption('USA: AAPL, MSFT • Amsterdam: ASML.AS • Frankfurt: SAP.DE • Paríž: MC.PA • Londýn: SHEL.L. Alpha Vantage môže používať odlišné symboly a má obmedzené európske pokrytie.')
    provider = st.selectbox('Zdroj fundamentov', ['Yahoo Finance', 'Alpha Vantage'])
    if provider == 'Alpha Vantage':
        st.caption('Kľúč nastavte ako ALPHAVANTAGE_API_KEY v prostredí alebo Streamlit secrets. Bezplatné API má prísne denné limity.')
    run = st.button('Analyzovať akcie', type='primary')
    if st.button('Vymazať vyrovnávaciu pamäť'):
        cached_stock.clear()
        st.session_state.pop('stocks', None)
        st.rerun()

if run:
    try:
        symbols = tickers(raw)
        if not symbols:
            st.warning('Zadajte aspoň jeden ticker.')
        else:
            key = secret_key() if provider == 'Alpha Vantage' else ''
            if provider == 'Alpha Vantage' and not key:
                st.error('Chýba ALPHAVANTAGE_API_KEY. Nastavte ho bezpečne v prostredí alebo v secrets.')
            else:
                with st.spinner('Načítavam finančné údaje…'):
                    st.session_state.stocks = [cached_stock(s, provider, key) for s in symbols]
    except ValueError as exc:
        st.error(str(exc))

stocks = st.session_state.get('stocks', [])
if not stocks:
    st.write('Zadajte tickery a stlačte **Analyzovať akcie**. Aplikácia nepoužíva vymyslené ani ukážkové finančné údaje.')
else:
    for stock in stocks:
        for warning in stock.warnings:
            st.warning(f'{stock.ticker}: {warning}')
    rows = []
    for s in stocks:
        dimensions, score, coverage = evaluate(s)
        rows.append({'Ticker': s.ticker, 'Spoločnosť': s.name or s.ticker, 'Sektor': s.sector, 'Mena ceny': s.currency or 'N/A', 'Mena výkazov': s.financial_currency or 'N/A', 'Skóre': score, 'Pokrytie (%)': coverage, **dimensions, **{label:s.metrics.get(k) for k,label in METRICS.items()}})
    df = pd.DataFrame(rows)
    st.subheader('Screener a filtre')
    c1, c2, c3 = st.columns(3)
    minimum = c1.slider('Minimálne skóre', 0, 100, 0)
    coverage_min = c2.slider('Minimálne pokrytie (%)', 0, 100, 0)
    include_na = c3.checkbox('Zahrnúť akcie bez skóre', True)
    sectors = st.multiselect('Sektory (prázdny výber = všetky)', sorted(df['Sektor'].unique()))
    f1, f2, f3 = st.columns(3)
    max_pe = f1.number_input('Maximálne kladné P/E (0 = bez filtra)', min_value=0.0, value=0.0)
    min_growth = f2.number_input('Minimálny rast tržieb (%)', value=0.0)
    growth_filter = f3.checkbox('Použiť filter rastu tržieb')
    mask = ((df['Skóre'] >= minimum) | (df['Skóre'].isna() & include_na)) & (df['Pokrytie (%)'] >= coverage_min)
    if sectors:
        mask &= df['Sektor'].isin(sectors)
    if max_pe:
        mask &= (df['P/E'] > 0) & (df['P/E'] <= max_pe)
    if growth_filter:
        mask &= df['Rast tržieb'] >= min_growth/100
    filtered = df[mask].sort_values('Skóre', ascending=False, na_position='last')
    display = filtered.copy()
    for key in PERCENT:
        display[METRICS[key]] = display[METRICS[key]] * 100
        display.rename(columns={METRICS[key]:METRICS[key]+' (%)'}, inplace=True)
    st.dataframe(display.style.format(precision=2, na_rep='N/A'), hide_index=True, use_container_width=True)
    st.download_button('Stiahnuť výsledky CSV', display.to_csv(index=False, na_rep='N/A').encode('utf-8-sig'), 'akcie.csv', 'text/csv')
    st.subheader('Najzaujímavejšie akcie podľa modelu')
    ranked = filtered.dropna(subset=['Skóre']).head(5)
    if ranked.empty:
        st.info('Žiadna akcia nemá dostatok údajov alebo nespĺňa filtre.')
    else:
        st.dataframe(ranked[['Ticker', 'Spoločnosť', 'Skóre', 'Pokrytie (%)']], hide_index=True)
        st.caption('Poradie platí iba pre zadané akcie a aktuálne filtre. Nejde o výber z celého trhu.')
    comparison, detail, methodology = st.tabs(['Porovnanie a grafy', 'Detail a výhľad', 'Metodika a obmedzenia'])
    with comparison:
        selected = st.multiselect('Porovnávané akcie', [s.ticker for s in stocks], default=[s.ticker for s in stocks][:4])
        sub = df[df.Ticker.isin(selected)]
        dimensions = list(evaluate(stocks[0])[0])
        if not sub.empty:
            chart = sub[['Ticker'] + dimensions].melt(id_vars='Ticker', value_vars=dimensions, var_name='Oblasť', value_name='Skóre')
            st.plotly_chart(px.bar(chart.dropna(), x='Oblasť', y='Skóre', color='Ticker', barmode='group', range_y=[0,100]), use_container_width=True)
        histories = []
        for s in stocks:
            if s.ticker in selected and s.history is not None:
                h = s.history.dropna()
                if not h.empty and h.iloc[0] > 0:
                    h.index = pd.to_datetime(h.index, utc=True).normalize()
                    histories.append((h/h.iloc[0]*100).rename(s.ticker))
        if histories:
            prices = pd.concat(histories, axis=1).sort_index()
            prices.index.name = 'Dátum'
            long = prices.reset_index().melt(id_vars='Dátum', var_name='Ticker', value_name='Index ceny')
            st.plotly_chart(px.line(long, x='Dátum', y='Index ceny', color='Ticker', title='Upravená cena za rok (prvý dostupný deň = 100)'), use_container_width=True)
            st.caption('Každá akcia začína vlastným prvým dostupným dňom. Ceny sú upravené poskytovateľom; index nezohľadňuje menové riziko investora.')
        else:
            st.info('Pre vybrané akcie nie je dostupná cenová história.')
    with detail:
        chosen = st.selectbox('Detail akcie', [s.ticker for s in stocks])
        s = next(s for s in stocks if s.ticker == chosen)
        st.write(f'**{s.name or s.ticker}** • {s.sector}')
        st.caption(f'Zdroj: {s.source} • Načítané (UTC): {s.fetched} • Dátum výkazov/obdobia: {s.fiscal_date}')
        st.write('Mena ceny: **'+(s.currency or 'N/A')+'**; mena finančných výkazov a EPS: **'+(s.financial_currency or 'N/A')+'**. Čiastky FCF sú v základných jednotkách meny výkazov.')
        if s.provenance:
            st.dataframe(pd.DataFrame([{'Ukazovateľ': METRICS.get(k,k), 'Zdroj a obdobie': v} for k,v in s.provenance.items()]), hide_index=True)
        st.subheader('Financial Resilience Score (0–100)')
        st.caption('Ročné vstupy k '+s.resilience_period+'; mena '+(s.resilience_currency or 'N/A')+'. Horizont stresu: 24 mesiacov od dátumu súvahy, nie od dneška. Riedenie = zmena ročného váženého zriedeného počtu akcií; nejde o bodový počet akcií. EBITDA SEC je aproximácia prevádzkový zisk + D&A.')
        resilience_parts, resilience_score, confidence = evaluate_resilience(s.resilience_inputs)
        r1, r2 = st.columns(2)
        r1.metric('Financial Resilience Score', 'N/A' if resilience_score is None else f'{resilience_score:.1f} / 100')
        r2.metric('Istota – pokrytie váh', f'{confidence} %')
        if s.resilience_provenance:
            st.dataframe(pd.DataFrame([{'Vstup':k,'Hodnota':s.resilience_inputs.get(k),'Pôvod a obdobie':v} for k,v in s.resilience_provenance.items()]).style.format({'Hodnota':'{:.4f}'},na_rep='N/A'),hide_index=True)
        st.caption('Predbežné skóre pri neúplných dátach. Istota meria dostupnosť údajov, nie pravdepodobnosť prežitia. Chýbajúce kategórie sa nenahrádzajú nulou; dostupné váhy sa normalizujú.')
        labels = {'fcf':'FCF · 25 %','debt':'Zadlženie · 20 %','growth_margins':'Rast a marže · 20 %','valuation':'Valuácia · 15 %','dilution':'Riedenie akcií · 10 %','ai_capex':'AI capex expozícia · 10 %'}
        st.dataframe(pd.DataFrame([{'Kategória':labels[k], 'Skóre':v} for k,v in resilience_parts.items()]).style.format({'Skóre':'{:.1f}'}, na_rep='N/A'), hide_index=True)
        stress = stress_24m(s.resilience_inputs)
        st.subheader('Stresový scenár: tržby −20 %, horizont 24 mesiacov')
        if stress['status'] == 'N/A':
            st.info('Financovanie 24 mesiacov: N/A. Chýbajú alebo sú neplatné vstupy: '+', '.join(stress['missing']))
        else:
            st.write('Pokryté' if stress['status']=='covered' else 'Deficit financovania')
            st.json(stress)
        st.caption('Vyžaduje ročné tržby, FCF a hrubú maržu za rovnaké obdobie, hotovosť a dlh splatný do 24 mesiacov v rovnakej mene. Stratený hrubý zisk znižuje FCF; fixné náklady, capex a pracovný kapitál sú konštantné. Bez refinancovania. Koncová hotovosť negarantuje priebežnú likviditu. Riedenie, AI capex ani splatnosti dlhu sa neodhadujú.')
        st.subheader('Podmienený výhľad na 3 až 5 rokov')
        st.write('Scenár mechanicky zachováva posledný dostupný medziročný rast zisku a násobí ním dnešné EPS. Nie je to prognóza ceny ani odhad budúceho výnosu. Rast sa môže výrazne zmeniť.')
        projections = [{'Horizont':f'{year} rokov', 'Scenárové EPS':scenario(s, year)} for year in (3,4,5)]
        st.dataframe(pd.DataFrame(projections).style.format({'Scenárové EPS':'{:.2f}'}, na_rep='N/A'), hide_index=True)
        st.caption('Pri nekladnom EPS, chýbajúcom raste alebo raste ≤ −100 % sa scenár nevypočíta. Pre vysoké krátkodobé tempo môže byť extrapolácia nereálna.')
    with methodology:
        st.markdown('''
Skóre používa lineárne ohraničené stupnice 0–100:

- **Podhodnotenie:** P/E 10–40, forward P/E 10–35, PEG 0,5–3; nižšie kladné hodnoty sú lepšie. Nulové a záporné násobky sú N/A pre skórovanie.
- **Moat – finančné indikátory:** hrubá marža 10–60 %, prevádzková marža 0–30 %, ROIC 0–25 %. Finančné ukazovatele samy nepotvrdzujú konkurenčnú výhodu.
- **Finančná stabilita:** dlh/vlastné imanie 0–2 (nižšie je lepšie), bežná likvidita 0,5–2, kladný FCF = 100, nekladný = 0.
- **Rastový potenciál:** medziročný rast tržieb a zisku 0–30 %. Krátkodobý rast nie je spoľahlivá predikcia na 3–5 rokov.

V každej oblasti sa priemerujú iba dostupné indikátory. Celkové skóre je rovnomerný priemer štyroch oblastí, iba ak existuje aspoň 7 z 11 indikátorov a každá oblasť má údaj. Pokrytie ukazuje podiel použiteľných indikátorov. Rozdielne pokrytie znižuje porovnateľnosť.

**ROIC** = prevádzkový zisk × (1 − daň/zisk pred zdanením) / priemerný ročný (dlh + vlastné imanie − hotovosť). Požadujú sa dve ročné súvahy, kladný kapitál a použiteľná efektívna daň 0–100 %. Inak N/A. Ostatné ukazovatele sú priamo od poskytovateľa; rast je medziročný, marže a EPS spravidla TTM, forward P/E a PEG sú odhady poskytovateľa. Ich obdobia sa môžu líšiť.

Yahoo udáva dlh/vlastné imanie v percentách; aplikácia ho mení na pomer. Záporné vlastné imanie nie je známkou stability: nekladný pomer dlhu sa pri záporných hodnotách zo skórovania vylučuje. Banky, poisťovne a REIT vyžadujú odlišné modely. Absolútny FCF neporovnávajte medzi menami alebo rôzne veľkými firmami.

Alpha Vantage OVERVIEW neposkytuje všetky požadované ukazovatele; neznáme marže, FCF, zadlženie a ROIC zostávajú N/A. Európske pokrytie a symboly závisia od poskytovateľa. Pri limite alebo chybe API aplikácia zobrazí upozornenie. Údaje sa ukladajú do vyrovnávacej pamäte na 5 minút. API kľúč sa nezobrazuje ani nezapisuje do repozitára.
''')

