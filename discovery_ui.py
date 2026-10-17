"""Streamlit discovery view; explicit run button, no automatic network on render."""
import os
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from discovery_cache import Cache
from discovery import universe, top20, ranked_rows
from discovery_campaign import Campaigns, scan_campaign
from discovery_audit import audit, coverage_estimate
from providers import DataError


def render_discovery():
    st.header('Market Discovery Engine · NASDAQ / NYSE')
    st.caption('Reálne zdroje: NASDAQ Trader → Yahoo Finance + SEC EDGAR. TOP 20 je iba zo spracovanej vzorky, nie z celého trhu. Žiadne simulované výsledky.')
    st.info('Výber je stabilné SHA-256 poradie tickerov, nezávislé od investičných metrík. Trvalý priechod celého univerza pokračuje aj po reštarte relácie. Dávka najviac 100; nový úplný priechod je možný až po pokuse o každý symbol.')
    try:
        cache=Cache(Path(os.getenv('DISCOVERY_CACHE_PATH','.cache/discovery.sqlite3')))
        campaigns=Campaigns(cache)
        current=campaigns.current()
    except (OSError,sqlite3.Error) as exc:
        st.error('Úložisko priechodu nie je dostupné: '+str(exc));return
    st.caption('Postup je uložený mimo relácie prehliadača. Hosting musí mať trvalý disk; po strate alebo vymazaní serverového úložiska sa história priechodu nezachová.')
    size=st.select_slider('Veľkosť ďalšej dávky',options=[5,10,20,50,100],value=10,key='discovery_batch')
    if st.button('Vyhľadať príležitosti / ďalšia dávka',type='primary',key='discovery_run'):
        try:
            if current is None:
                listing,hit=universe(cache)
                campaigns.start(listing)
                current=campaigns.current()
            bar=st.progress(0,text='Pokračujem v trvalom priechode…')
            with st.spinner('Načítavam reálne dáta; prvá dávka môže trvať niekoľko minút…'):
                result=scan_campaign(campaigns,current['id'],size,
                    progress=lambda n,total:bar.progress(n/total,text=f'Spracované {n}/{total} v tejto dávke'))
            st.session_state['discovery_last']=result
        except (DataError,OSError,ValueError,sqlite3.Error) as exc:st.error('Discovery sa nepodarilo dokončiť: '+str(exc))
    if st.button('Nový úplný priechod (iba po dokončení univerza)',key='discovery_reset'):
        if current and campaigns.counts(current['id'])['done']<campaigns.counts(current['id'])['total']:
            st.warning('Priechod ešte nie je hotový. Ďalšia dávka pokračuje bez opakovania dokončených symbolov.')
        else:
            try:
                listing,hit=universe(cache)
                campaigns.start(listing,new=True)
                st.session_state.pop('discovery_last',None)
                current=campaigns.current()
            except (DataError,OSError,ValueError,sqlite3.Error) as exc:st.error(str(exc))
    if current is None:
        st.write('Spustite dávku. Bez úspešného načítania zdrojov nezobrazujeme žiadne výsledky.');return
    listings=current['universe']
    rows=campaigns.rows(current['id'])
    counts=campaigns.counts(current['id'])
    report=audit(rows,listings['listings'])
    last=st.session_state.get('discovery_last',{})
    if last.get('stopped'):st.warning(last['stopped'])
    analyzed=report['analyzed']
    a,b,c,d=st.columns(4)
    a.metric('Akcie v snímke univerza',counts['total'])
    b.metric('Unikátne spracované pokusy',report['attempted'])
    c.metric('Overená identita + finančný údaj',analyzed)
    d.metric('Zoraditeľné pri načítaní',report['ranked_at_fetch'])
    st.progress(counts['done']/counts['total'] if counts['total'] else 0,text=f"Trvalý priechod #{current['id']}: {counts['done']}/{counts['total']} hotových, {counts['running']} rezervovaných, {counts['pending']} čaká")
    st.caption(f"Zoznam načítaný UTC: {listings['fetched_at']} · časy súborov NASDAQ Trader: {listings['file_times']}. Snímka je počas priechodu zmrazená; zmeny listingov sa preberú pri ďalšom úplnom priechode.")
    st.caption(f"Posledná dávka: {last.get('attempted',0)} pokusov, {last.get('network_loads',0)} volaní analyzátora (nie HTTP požiadaviek), {last.get('cache_hits',0)} z cache. Ukončenie UTC: {last.get('completed_at','N/A')}. Dokončené pokusy vrátane neúspechov sa v tomto priechode neopakujú; expirácia cache ich nemaže.")
    theme=st.selectbox('Tematický filter',['Všetky','AI infraštruktúra','Robotika'],key='discovery_theme')
    undervalued=st.checkbox('Podhodnotený rast (pravidlový filter)',key='discovery_undervalued')
    swing=st.checkbox('Swing (trend, pullback, objem)',key='discovery_swing')
    min_coverage=st.slider('Minimálne pokrytie resilience (%)',0,100,70,key='discovery_coverage')
    chosen=top20(rows,theme,undervalued,swing,min_coverage)
    current_count=len(ranked_rows(rows,min_coverage=min_coverage))
    filtered_count=len(ranked_rows(rows,theme,undervalued,swing,min_coverage))
    st.subheader(f'TOP {len(chosen)} z {analyzed} finančných analýz ({len(rows)} pokusov)')
    st.caption(f"{report['ranked_at_fetch']} akcií bolo zoraditeľných pri načítaní; aktuálne zoraditeľných pri danom pokrytí a limite 48 hodín je {current_count}, po filtroch {filtered_count}. Úplné univerzum má {counts['total']} symbolov. Nejde o TOP celého trhu ani o jednotnú trhovú snímku.")
    st.warning('Dátové skreslenie: výber tickerov je nezávislý od dostupnosti dát, ale poradie zvýhodňuje firmy s úplnejšími výkazmi. Nezaradená firma nie je automaticky horšia investícia. N/A nenahrádzame nulou ani odhadom.')
    columns={'symbol':'Ticker','name':'Spoločnosť','exchange':'Burza','score':'Discovery skóre','resilience':'Odolnosť','coverage':'Pokrytie %','growth':'Rast tržieb','forward_pe':'Forward P/E','fcf_margin':'FCF marža','net_debt_ebitda':'Čistý dlh/EBITDA','annual_period':'Ročné obdobie','annual_age_days':'Vek výkazov (dni)','fetched_at':'Načítané UTC','price_date':'Posledná cena UTC'}
    if chosen:
        df=pd.DataFrame([{**{columns[k]:r.get(k) for k in columns},'Finančné analýzy v priechode':analyzed,'Pokusy v priechode':len(rows),'Zoraditeľné pri načítaní':report['ranked_at_fetch'],'Univerzum':counts['total'],'Aktuálne zoraditeľné':current_count,'Po filtroch':filtered_count} for r in chosen])
        st.dataframe(df.style.format(precision=3,na_rep='N/A'),hide_index=True)
        st.download_button('Stiahnuť TOP výsledky CSV',df.to_csv(index=False,na_rep='N/A').encode('utf-8-sig'),'discovery-top.csv','text/csv')
    else:st.info('V spracovanej vzorke zatiaľ nie je akcia s dostatkom dát, ktorá spĺňa filtre. Nejde o záver o celom trhu.')
    with st.expander('Reprezentatívnosť, dostupnosť dát a čas pokrytia',expanded=True):
        st.write(f"Z {analyzed} finančných analýz bolo {report['excluded_analyzed']} nezoraditeľných; ďalších {report['without_financials']} pokusov nemalo overenú identitu s finančným vstupom.")
        if report['overlapping_reasons']:
            st.dataframe(pd.DataFrame([{'Dôvod (môže sa prekrývať)':k,'Počet finančných analýz':v} for k,v in report['overlapping_reasons'].items()]),hide_index=True)
        if report['primary_reasons']:
            st.caption('Prvý blokujúci dôvod je iba technická priorita, nie jediná príčina. Tieto počty sa sčítajú na počet nezoraditeľných finančných analýz.')
            st.dataframe(pd.DataFrame([{'Prvý blokujúci dôvod':k,'Počet':v} for k,v in report['primary_reasons'].items()]),hide_index=True)
        if report['groups']:
            st.dataframe(pd.DataFrame(report['groups']).rename(columns={'dimension':'Dimenzia','group':'Skupina','universe':'Univerzum (iba burza)','attempted':'Pokusy','analyzed':'Finančné analýzy','ranked':'Zoraditeľné pri načítaní','rank_rate':'Miera zaradenia','sample_share':'Podiel vo vzorke','universe_share':'Podiel v univerze'}).style.format(precision=3,na_rep='N/A'),hide_index=True)
        st.caption('Porovnávame burzu, sektor, dostupnú kapitalizáciu a zdroj. Sektor/kapitalizácia nie sú známe pre celé univerzum, preto nedokazujeme reprezentatívnosť týchto skupín. N/A skupiny ostávajú viditeľné. Rozdielne miery zaradenia ukazujú dátové skreslenie, nie príčinu alebo investičnú výkonnosť.')
        estimate=coverage_estimate(counts['total'],counts['done'])
        full_estimate=coverage_estimate(counts['total'])
        st.write(f"Zostáva {estimate['remaining']} symbolov. Pri rozpočte 100 nových analýz denne: približne {estimate['daily_budgets']} denných rozpočtov od nuly pre zvyšok (cache môže pomôcť). Celých {counts['total']} symbolov potrebuje {full_estimate['daily_budgets']} denných rozpočtov; prakticky približne {full_estimate['daily_budgets']/7:.1f} týždňa pri každodennom spúšťaní, pri limitoch alebo vynechaných dňoch viac.")
        st.caption(f"Odhad aktívnej práce pri 5–20 sekundách na analyzátor je pre celé univerzum približne {full_estimate['active_hours_5_to_20s'][0]:.1f}–{full_estimate['active_hours_5_to_20s'][1]:.1f} hodín rozložených do dní; samotný interval 3 s dáva iba teoretickú dolnú hranicu {full_estimate['throttle_floor_hours']:.1f} hodiny. Jedna analýza môže vyvolať viac HTTP požiadaviek. Nie je to SLA ani horná hranica latencie. Bez plánovača musí obsluha spúšťať dávky; denný rozpočet nie je časová garancia. Priechod znamená pokus o každý symbol, nie úspešné fundamenty pre každý symbol.")
    if rows:
        with st.expander('Všetky pokusy, chýbajúce údaje a pôvod'):
            st.dataframe(pd.DataFrame([{'Ticker':r['symbol'],'Identita overená':r['identity_verified'],'Skóre':r['score'],'Dôvod nezaradenia':'; '.join(r.get('rank_exclusions',[])),'Načítané UTC':r['fetched_at'],'Ročné obdobie':r['annual_period'],'Chýbajúce vstupy':', '.join(r['missing']),'AI infraštruktúra':r['themes']['AI infraštruktúra'],'Robotika':r['themes']['Robotika'],'Swing':r['swing'],'Upozornenia':' | '.join(r['warnings'])} for r in rows]).style.format(na_rep='N/A'),hide_index=True)
            symbol=st.selectbox('Pôvod údajov pre akciu',[r['symbol'] for r in rows],key='discovery_detail')
            row=next(r for r in rows if r['symbol']==symbol)
            st.json({'source':row['source'],'provenance':row['provenance'],'currency':row['currency']})
    with st.expander('Metodika, výber vzorky a limity'):
        st.write('Discovery skóre je priemer piatich oblastí s váhou 20 %: rast/marže, valuácia, FCF, zadlženie a Financial Resilience Score. Prvé štyri oblasti používajú rovnaké normalizácie ako modul odolnosti; prekrytie metrík je zámerné. Vyžadujú sa všetky štyri primárne oblasti, overená identita, aspoň 70 % pokrytie odolnosti a ročné výkazy nie staršie než 550 dní. Neúplné dáta nemajú discovery skóre; nulový výsledok nie je náhradou za N/A.')
        st.write('AI infraštruktúra a robotika sú orientačné kľúčové slová v reálnom opise podnikania/odvetvia Yahoo, nie potvrdenie podielu AI tržieb. Bez opisu je téma N/A. Podhodnotený rast: rast tržieb ≥15 %, 0<forward P/E≤25 a FCF marža>0; nejde o výpočet férovej ceny. Swing: cena a 20-dňový priemer nad 50-dňovým, päťdňový pullback 0 až −8 %, posledný objem ≥1,2×20-dňový priemer, priemerný dolárový objem ≥1 mil. USD. Potrebuje 55 platných cien, objem a poslednú cenu nie staršiu ako 7 dní. Nie je to obchodný signál ani garantovaný výnos.')
        st.write('NASDAQ Trader vylučuje ETF a testovacie symboly; názvové pravidlá obmedzujú warranty/preferred/units/dlhové/fondové nástroje. Nie je to dokonalý klasifikátor. ADR sú zahrnuté; dve triedy jednej firmy sa počítajú ako dve akcie. Výsledky Yahoo môžu byť oneskorené; SEC má obmedzené US-GAAP pokrytie. Denný rozpočet je 100 nových volaní analyzátora na procesnú cache (UTC), nie 100 HTTP požiadaviek. Trvalý register dokončených symbolov prežije reštart prehliadača aj expiráciu cache; nový úplný priechod sa začne až po spracovaní všetkých symbolov. Cache trvá 24 hodín (neúspechy 15 minút), prestávka pri limite 15 minút. Nerobíme náhradu zlyhaných zdrojov simulovanými dátami.')
