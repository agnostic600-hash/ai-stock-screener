"""Bounded sequential discovery. Selection is independent of company scores."""
import hashlib
import math
import threading
import time
from datetime import datetime, timezone
from data import load_fundamentals
from discovery_cache import pack, unpack
from market_universe import fetch_universe
from resilience import evaluate_resilience
from resilience_data import INPUT_KEYS
from discovery_audit import recent,has_financials
from market_store import MarketStore,fundamental_status,parsed,utcnow,epoch
from datetime import timedelta

_GATE=threading.Lock()
_LAST_START=0.0
THEMES={'AI infraštruktúra':('semiconductor','data center','data centre','networking','optical networking','power management','cooling','accelerated computing'),
        'Robotika':('robotics','robotic','industrial automation','machine vision','motion control')}


def now_iso():return datetime.now(timezone.utc).isoformat()

def universe(cache):
    result=cache.get('universe:v1')
    if result:return result,True
    result=fetch_universe();cache.put('universe:v1',result,24*3600);return result,False


def candidates(listings):
    # Deterministic sample order, not alphabetical or handpicked winners.
    return sorted(listings,key=lambda r:hashlib.sha256(('discovery-v1:'+r['symbol']).encode()).hexdigest())


def swing_signal(history,volume=None,now=None):
    if history is None:return None,None
    h=history.dropna().sort_index()
    h=h[~h.index.duplicated(keep='last')]
    if h.empty:return None,None
    latest=pd_time(h.index[-1]);current=datetime.now(timezone.utc) if now is None else now
    if len(h)<55 or (h<=0).any() or not h.map(math.isfinite).all() or volume is None:return None,latest.isoformat()
    if not -86400<=(current-latest).total_seconds()<=7*86400:return None,latest.isoformat()
    volume=volume[~volume.index.duplicated(keep='last')]
    aligned=volume.reindex(h.index)
    if aligned.iloc[-20:].isna().any():return None,latest.isoformat()
    v=aligned.dropna()
    if len(v)<20 or v.index[-1]!=h.index[-1] or (v<0).any() or not v.map(math.isfinite).all() or float(v.iloc[-20:].mean())<=0:return None,latest.isoformat()
    # Trend + pullback + above-average volume and basic liquidity.
    ma20=float(h.iloc[-20:].mean());ma50=float(h.iloc[-50:].mean());price=float(h.iloc[-1]);ret5=price/float(h.iloc[-6])-1
    return bool(price>ma50 and ma20>ma50 and -.08<=ret5<=0 and float(v.iloc[-1])>=1.2*float(v.iloc[-20:].mean()) and float((h.reindex(v.index)*v).iloc[-20:].mean())>=1_000_000),latest.isoformat()


def pd_time(value):
    import pandas as pd
    value=pd.Timestamp(value)
    return value.tz_localize('UTC').to_pydatetime() if value.tzinfo is None else value.tz_convert('UTC').to_pydatetime()


def analyze(stock,listing,fund_meta=None,price_stock=None,price_meta=None):
    now=utcnow()
    if fund_meta is None:
        downloaded=parsed(stock.fetched)
        fund_meta={'period_end':stock.resilience_period,'retrieved_at':stock.fetched,'valid_until':(downloaded+timedelta(days=90)).isoformat() if downloaded else None,'identity_verified':stock.identity_verified}
    valid_fund,fund_reason=fundamental_status(fund_meta,now)
    price_stock=price_stock or stock
    if price_meta is None:
        asof=price_stock.profile.get('price_asof')
        stamp=price_stock.profile.get('regularMarketTime')
        if not asof and epoch(stamp):asof=epoch(stamp).isoformat()
        if price_stock.history is not None and not price_stock.history.dropna().empty:asof=price_stock.history.dropna().sort_index().index[-1].isoformat()
        price_meta={'price_asof':asof,'retrieved_at':price_stock.fetched}
    price_asof=parsed(price_meta.get('price_asof'))
    valid_price=price_asof is not None and -3600<=(now-price_asof).total_seconds()<=7*86400
    effective=dict(stock.resilience_inputs)
    price=price_stock.metrics.get('price')
    if price_stock.history is not None and not price_stock.history.dropna().empty:price=float(price_stock.history.dropna().sort_index().iloc[-1])
    eps=stock.profile.get('forwardEps');valuation_asof=None
    effective_provenance=dict(stock.resilience_provenance)
    if valid_price and isinstance(eps,(int,float)) and math.isfinite(eps) and eps>0 and isinstance(price,(int,float)) and price>0 and stock.currency and stock.currency==stock.financial_currency:
        effective['forward_pe']=price/eps;valuation_asof=price_meta['price_asof']
        effective_provenance['forward_pe']='Price as of '+str(valuation_asof)+' / Yahoo forward EPS retrieved '+stock.fetched+'; matching currencies'
    else:
        stamp=stock.profile.get('regularMarketTime')
        original=epoch(stamp)
        if valid_price and original and -3600<=(now-original).total_seconds()<=7*86400:
            valuation_asof=original.isoformat()
        else:effective['forward_pe']=None
    parts,resilience,coverage=evaluate_resilience(effective)
    keys=('growth_margins','valuation','fcf','debt')
    try:
        annual_age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(stock.resilience_period).date()).days
    except (ValueError,TypeError):annual_age=None
    fresh_annual=annual_age is not None and 0<=annual_age<=550
    quote_type=stock.profile.get('quoteType')
    equity=quote_type in (None,'EQUITY')
    complete=valid_fund and valid_price and valuation_asof is not None and equity and fresh_annual and stock.identity_verified and coverage>=70 and all(parts[k] is not None for k in keys)
    # 20% each: growth/margins, valuation, FCF, debt, resilience. Explicit overlap.
    score=round((sum(parts[k] for k in keys)+resilience)/5,1) if complete else None
    exclusions=[]
    if not valid_fund:exclusions.append(fund_reason)
    if not valid_price:exclusions.append('Chýbajúca alebo stará cena (>7 dní)')
    if valuation_asof is None:exclusions.append('Valuácia N/A: chýba aktuálne forward EPS / použiteľné P/E')
    if not stock.identity_verified:exclusions.append('Neoverená identita')
    if not equity:exclusions.append('Typ nástroja nie je EQUITY')
    if not fresh_annual:exclusions.append('Chýbajúce/budúce/staršie než 550 dní ročné obdobie')
    exclusions.extend('N/A: '+k for k in keys if parts[k] is None)
    if coverage<70:exclusions.append('Pokrytie odolnosti pod 70 %')
    profile=getattr(stock,'profile',{})
    text=' '.join(str(profile.get(k) or '') for k in ('industry','longBusinessSummary')).lower()
    theme={name:(any(word in text for word in words) if text.strip() else None) for name,words in THEMES.items()}
    m=effective
    growth=m.get('revenue_growth');pe=m.get('forward_pe');fcf=m.get('fcf_margin')
    undervalued=(growth>=.15 and 0<pe<=25 and fcf>0) if all(v is not None for v in (growth,pe,fcf)) else None
    swing,price_date=swing_signal(price_stock.history,price_stock.volume_history)
    if price_stock.profile.get('technical_computed'):
        technical_date=parsed(price_stock.profile.get('technical_asof'))
        swing=price_stock.profile.get('swing_signal') if valid_price and technical_date and -3600<=(now-technical_date).total_seconds()<=7*86400 else None
    if stock.currency != 'USD':swing=None
    cap=profile.get('marketCap') if stock.currency=='USD' else None
    size_band='N/A'
    if isinstance(cap,(int,float)) and math.isfinite(cap) and cap>0:
        size_band='micro <300m USD' if cap<300e6 else 'small 300m–2b USD' if cap<2e9 else 'mid 2–10b USD' if cap<10e9 else 'large ≥10b USD'
    return {'has_financial_inputs':stock.identity_verified and any(stock.resilience_inputs.get(k) is not None for k in ('revenue_growth','forward_pe','fcf_margin','net_debt_ebitda')),'sector':stock.sector if profile else 'N/A','size_band':size_band,'market_cap':cap,'symbol':stock.ticker,'name':stock.name or listing['name'],'exchange':listing['exchange'],
            'identity_verified':stock.identity_verified,'rank_exclusions':exclusions,'score':score,'resilience':resilience,'coverage':coverage,
            'growth':growth,'forward_pe':pe,'fcf_margin':fcf,'net_debt_ebitda':m.get('net_debt_ebitda'),
            'themes':theme,'undervalued_growth':undervalued,'swing':swing,'price_date':price_date,
            'fundamental_valid':valid_fund,'fundamental_valid_until':fund_meta.get('valid_until'),'report_pending':fund_meta.get('report_pending',False),'published_at':fund_meta.get('published_at'),'last_report_checked_at':fund_meta.get('last_report_checked_at'),'fundamental_error':fund_meta.get('last_error'),'price_error':price_meta.get('last_error'),'price_source':price_meta.get('source'),'technical_asof':price_meta.get('technical_asof'),'technical_retrieved_at':price_meta.get('technical_retrieved_at'),'price_asof':price_meta.get('price_asof'),'price_retrieved_at':price_meta.get('retrieved_at'),'valuation_asof':valuation_asof,'price_valid':valid_price,'fetched_at':stock.fetched,'annual_period':stock.resilience_period,'annual_age_days':annual_age,'fresh_annual':fresh_annual,'currency':stock.resilience_currency,
            'missing':[k for k in INPUT_KEYS if m.get(k) is None], 'warnings':stock.warnings,
            'provenance':effective_provenance,'source':stock.source}


def scan(listings,cache,limit=10,excluded=(),loader=load_fundamentals,progress=None,min_interval=3,offset=0):
    global _LAST_START
    if not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Dávka musí obsahovať 1–100 spoločností.')
    ordered=candidates(listings)
    offset=offset%len(ordered) if ordered else 0
    ordered=ordered[offset:]+ordered[:offset]
    selected=[r for r in ordered if r['symbol'] not in set(excluded)][:limit]
    rows=[];attempted=0;cache_hits=0;network_loads=0;stopped=None
    for listing in selected:
        loaded_network=False
        key='stock:v1:'+listing['symbol']
        store=MarketStore(cache)
        stock,meta=store.get('fundamentals',listing['symbol'])
        if stock is None:
            legacy=cache.get(key)
            if legacy is not None:
                legacy_stock=unpack(legacy)
                store.save_fundamentals(legacy_stock)
                stock,meta=store.get('fundamentals',listing['symbol'])
        if stock is not None and fundamental_status(meta)[0]:
            cache_hits+=1
        else:
            with _GATE:
                if cache.get('cooldown:v1'):
                    stopped='Aktívna 15-minútová prestávka po limite poskytovateľa.';break
                budget_key='network-budget:'+datetime.now(timezone.utc).date().isoformat()
                used=cache.get(budget_key) or 0
                if used>=100:
                    stopped='Denný limit 100 nových sieťových analýz bol dosiahnutý (UTC); uložené fundamenty ostávajú zachované.';break
                time.sleep(max(0,min_interval-(time.monotonic()-_LAST_START)))
                _LAST_START=time.monotonic();network_loads+=1;loaded_network=True
                cache.put(budget_key,used+1,48*3600)
                try:fresh=loader(listing['symbol'])
                except Exception:
                    from screener import Stock
                    fresh=Stock(listing['symbol'],warnings=['Fundamentálne API zlyhalo; staré dáta neboli prepísané.'])
                if store.save_fundamentals(fresh):stock,meta=store.get('fundamentals',listing['symbol'])
                elif stock is not None:
                    store.error('fundamentals',listing['symbol'],'Obnova zlyhala; posledný úspešný snapshot je zachovaný.')
                    stock,meta=store.get('fundamentals',listing['symbol'])
                    stock.warnings+=fresh.warnings
                else:stock=fresh;meta={}
        price_stock,price_meta=store.get('prices',listing['symbol'])
        attempted+=1
        row=analyze(stock,listing,meta,price_stock,price_meta or None);rows.append(row)
        if progress:progress(attempted,len(selected))
        limited=any('429' in w or '401/403' in w for w in stock.warnings)
        if limited and loaded_network:
            cache.put('cooldown:v1',{'reason':'provider limit/access rejection','at':now_iso()},15*60)
            stopped='Zdroj vrátil limit alebo odmietol prístup; ďalšie sieťové analýzy sa zastavili na 15 minút.';break
    return {'rows':rows,'attempted':attempted,'cache_hits':cache_hits,'network_loads':network_loads,
            'analyzed':sum(has_financials(r) for r in rows),
            'ranked':sum(r['score'] is not None for r in rows),'stopped':stopped,'completed_at':now_iso()}


def ranked_rows(rows,theme='Všetky',undervalued=False,swing=False,min_coverage=70):
    result=[r for r in rows if r['score'] is not None and recent(r) and r['coverage']>=min_coverage
            and (theme=='Všetky' or r['themes'].get(theme) is True)
            and (not undervalued or r['undervalued_growth'] is True)
            and (not swing or r['swing'] is True)]
    return sorted(result,key=lambda r:(-r['score'],r['symbol']))


def top20(rows,theme='Všetky',undervalued=False,swing=False,min_coverage=70):
    return ranked_rows(rows,theme,undervalued,swing,min_coverage)[:20]
