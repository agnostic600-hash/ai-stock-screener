"""Streamlit discovery view; explicit run button, no automatic network on render."""
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from discovery_cache import Cache
from discovery import universe, scan, top20
from providers import DataError


def render_discovery():
    st.header('Market Discovery Engine · NASDAQ / NYSE')
    st.caption('Reálne zdroje: NASDAQ Trader → Yahoo Finance + SEC EDGAR. TOP 20 je iba zo spracovanej vzorky, nie z celého trhu. Žiadne simulované výsledky.')
    st.info('MVP spracúva maximálne 100 automaticky vybraných akcií v jednom pracovnom cykle. Dávky sú sekvenčné, s cache 24 h a prestávkou po limite. Vzorka je deterministická podľa hash tickera; nie podľa veľkosti firmy ani investičnej atraktivity.')
    size=st.select_slider('Veľkosť ďalšej dávky',options=[5,10,20,50,100],value=10,key='discovery_batch')
    if st.button('Vyhľadať príležitosti / ďalšia dávka',type='primary',key='discovery_run'):
        try:
            cache=Cache(Path(os.getenv('DISCOVERY_CACHE_PATH','.cache/discovery.sqlite3')))
            listing,hit=universe(cache)
            previous=st.session_state.get('discovery_rows',{})
            # A new directory snapshot prunes delisted securities from this session.
            allowed={r['symbol'] for r in listing['listings']}
            previous={k:v for k,v in previous.items() if k in allowed}
            remaining=max(0,100-len(previous))
            if remaining:
                bar=st.progress(0,text='Automatický výber akcií…')
                with st.spinner('Načítavam reálne dáta; prvá dávka môže trvať niekoľko minút…'):
                    result=scan(listing['listings'],cache,min(size,remaining),excluded=previous,offset=st.session_state.get('discovery_offset',0),
                        progress=lambda n,total:bar.progress(n/total,text=f'Spracované {n}/{total} v tejto dávke'))
                previous.update({r['symbol']:r for r in result['rows']})
                st.session_state['discovery_rows']=previous
                st.session_state['discovery_last']=result
            else:st.info('Dosiahli ste limit 100 akcií v tomto cykle. Nový cyklus využije platnú cache.')
            st.session_state['discovery_universe']=listing
            st.session_state['discovery_universe_cached']=hit
        except (DataError,OSError,ValueError) as exc:st.error('Discovery sa nepodarilo dokončiť: '+str(exc))
    if st.button('Nový cyklus / ďalšia vzorka (zachovať cache)',key='discovery_reset'):
        st.session_state['discovery_offset']=st.session_state.get('discovery_offset',0)+len(st.session_state.get('discovery_rows',{}))
        for key in ('discovery_rows','discovery_last','discovery_universe','discovery_universe_cached'):st.session_state.pop(key,None)
        st.rerun()
    listings=st.session_state.get('discovery_universe')
    rows=list(st.session_state.get('discovery_rows',{}).values())
    if not listings:
        st.write('Spustite dávku. Bez úspešného načítania zdrojov nezobrazujeme žiadne výsledky.');return
    last=st.session_state.get('discovery_last',{})
    if last.get('stopped'):st.warning(last['stopped'])
    analyzed=sum(r['identity_verified'] and any(r[k] is not None for k in ('growth','forward_pe','fcf_margin','net_debt_ebitda')) for r in rows)
    a,b,c,d=st.columns(4)
    a.metric('Akcie v aktuálnom zozname',len(listings['listings']))
    b.metric('Unikátne spracované pokusy',len(rows))
    c.metric('Overená identita + finančný údaj',analyzed)
    d.metric('Dostatok dát na poradie',sum(r['score'] is not None for r in rows))
    st.caption(f"Zoznam načítaný UTC: {listings['fetched_at']} · časy súborov NASDAQ Trader (ako uvádza zdroj): {listings['file_times']} · cache zoznamu: {st.session_state.get('discovery_universe_cached',False)}")
    st.caption(f"Posledná dávka: {last.get('attempted',0)} spracovaných, {last.get('network_loads',0)} volaní analyzátora (nie počet HTTP požiadaviek), {last.get('cache_hits',0)} z cache. Ukončenie UTC: {last.get('completed_at','N/A')}. Štatistika cyklu sa počíta z unikátnych tickerov, nie opakovaných kliknutí.")
    theme=st.selectbox('Tematický filter',['Všetky','AI infraštruktúra','Robotika'],key='discovery_theme')
    undervalued=st.checkbox('Podhodnotený rast (pravidlový filter)',key='discovery_undervalued')
    swing=st.checkbox('Swing (trend, pullback, objem)',key='discovery_swing')
    min_coverage=st.slider('Minimálne pokrytie resilience (%)',0,100,70,key='discovery_coverage')
    chosen=top20(rows,theme,undervalued,swing,min_coverage)
    st.subheader(f'TOP {len(chosen)} zo spracovanej vzorky')
    columns={'symbol':'Ticker','name':'Spoločnosť','exchange':'Burza','score':'Discovery skóre','resilience':'Odolnosť','coverage':'Pokrytie %','growth':'Rast tržieb','forward_pe':'Forward P/E','fcf_margin':'FCF marža','net_debt_ebitda':'Čistý dlh/EBITDA','annual_period':'Ročné obdobie','annual_age_days':'Vek výkazov (dni)','fetched_at':'Načítané UTC','price_date':'Posledná cena UTC'}
    if chosen:
        df=pd.DataFrame([{columns[k]:r.get(k) for k in columns} for r in chosen])
        st.dataframe(df.style.format(precision=3,na_rep='N/A'),hide_index=True)
        st.download_button('Stiahnuť TOP výsledky CSV',df.to_csv(index=False,na_rep='N/A').encode('utf-8-sig'),'discovery-top.csv','text/csv')
    else:st.info('V spracovanej vzorke zatiaľ nie je akcia s dostatkom dát, ktorá spĺňa filtre. Nejde o záver o celom trhu.')
    if rows:
        with st.expander('Všetky pokusy, chýbajúce údaje a pôvod'):
            st.dataframe(pd.DataFrame([{'Ticker':r['symbol'],'Identita overená':r['identity_verified'],'Skóre':r['score'],'Dôvod nezaradenia':'; '.join(r.get('rank_exclusions',[])),'Načítané UTC':r['fetched_at'],'Ročné obdobie':r['annual_period'],'Chýbajúce vstupy':', '.join(r['missing']),'AI infraštruktúra':r['themes']['AI infraštruktúra'],'Robotika':r['themes']['Robotika'],'Swing':r['swing'],'Upozornenia':' | '.join(r['warnings'])} for r in rows]).style.format(na_rep='N/A'),hide_index=True)
            symbol=st.selectbox('Pôvod údajov pre akciu',[r['symbol'] for r in rows],key='discovery_detail')
            row=next(r for r in rows if r['symbol']==symbol)
            st.json({'source':row['source'],'provenance':row['provenance'],'currency':row['currency']})
    with st.expander('Metodika, výber vzorky a limity'):
        st.write('Discovery skóre je priemer piatich oblastí s váhou 20 %: rast/marže, valuácia, FCF, zadlženie a Financial Resilience Score. Prvé štyri oblasti používajú rovnaké normalizácie ako modul odolnosti; prekrytie metrík je zámerné. Vyžadujú sa všetky štyri primárne oblasti, overená identita, aspoň 70 % pokrytie odolnosti a ročné výkazy nie staršie než 550 dní. Neúplné dáta nemajú discovery skóre; nulový výsledok nie je náhradou za N/A.')
        st.write('AI infraštruktúra a robotika sú orientačné kľúčové slová v reálnom opise podnikania/odvetvia Yahoo, nie potvrdenie podielu AI tržieb. Bez opisu je téma N/A. Podhodnotený rast: rast tržieb ≥15 %, 0<forward P/E≤25 a FCF marža>0; nejde o výpočet férovej ceny. Swing: cena a 20-dňový priemer nad 50-dňovým, päťdňový pullback 0 až −8 %, posledný objem ≥1,2×20-dňový priemer, priemerný dolárový objem ≥1 mil. USD. Potrebuje 55 platných cien, objem a poslednú cenu nie staršiu ako 7 dní. Nie je to obchodný signál ani garantovaný výnos.')
        st.write('NASDAQ Trader vylučuje ETF a testovacie symboly; názvové pravidlá obmedzujú warranty/preferred/units/dlhové/fondové nástroje. Nie je to dokonalý klasifikátor. ADR sú zahrnuté; dve triedy jednej firmy sa počítajú ako dve akcie. Výsledky Yahoo môžu byť oneskorené; SEC má obmedzené US-GAAP pokrytie. Denný rozpočet je 100 nových volaní analyzátora na procesnú cache (UTC), nie 100 HTTP požiadaviek. Nový cyklus posunie výber ďalej v zozname; nezmaže cache ani rozpočet. Cache trvá 24 hodín (neúspechy 15 minút), prestávka pri limite 15 minút. Nerobíme náhradu zlyhaných zdrojov simulovanými dátami.')
