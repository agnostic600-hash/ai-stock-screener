"""Bounded sequential discovery. Selection is independent of company scores."""
import hashlib
import math
import threading
import time
from datetime import datetime, timezone
from data import load_stock
from discovery_cache import pack, unpack
from market_universe import fetch_universe
from resilience import evaluate_resilience
from resilience_data import INPUT_KEYS
from discovery_audit import recent

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


def analyze(stock,listing):
    parts,resilience,coverage=evaluate_resilience(stock.resilience_inputs)
    keys=('growth_margins','valuation','fcf','debt')
    try:
        annual_age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(stock.resilience_period).date()).days
    except (ValueError,TypeError):annual_age=None
    fresh_annual=annual_age is not None and 0<=annual_age<=550
    quote_type=stock.profile.get('quoteType')
    equity=quote_type in (None,'EQUITY')
    complete=equity and fresh_annual and stock.identity_verified and coverage>=70 and all(parts[k] is not None for k in keys)
    # 20% each: growth/margins, valuation, FCF, debt, resilience. Explicit overlap.
    score=round((sum(parts[k] for k in keys)+resilience)/5,1) if complete else None
    exclusions=[]
    if not stock.identity_verified:exclusions.append('Neoverená identita')
    if not equity:exclusions.append('Typ nástroja nie je EQUITY')
    if not fresh_annual:exclusions.append('Chýbajúce/budúce/staršie než 550 dní ročné obdobie')
    exclusions.extend('N/A: '+k for k in keys if parts[k] is None)
    if coverage<70:exclusions.append('Pokrytie odolnosti pod 70 %')
    profile=getattr(stock,'profile',{})
    text=' '.join(str(profile.get(k) or '') for k in ('industry','longBusinessSummary')).lower()
    theme={name:(any(word in text for word in words) if text.strip() else None) for name,words in THEMES.items()}
    m=stock.resilience_inputs
    growth=m.get('revenue_growth');pe=m.get('forward_pe');fcf=m.get('fcf_margin')
    undervalued=(growth>=.15 and 0<pe<=25 and fcf>0) if all(v is not None for v in (growth,pe,fcf)) else None
    swing,price_date=swing_signal(stock.history,stock.volume_history)
    if stock.currency != 'USD':swing=None
    cap=profile.get('marketCap') if stock.currency=='USD' else None
    size_band='N/A'
    if isinstance(cap,(int,float)) and math.isfinite(cap) and cap>0:
        size_band='micro <300m USD' if cap<300e6 else 'small 300m–2b USD' if cap<2e9 else 'mid 2–10b USD' if cap<10e9 else 'large ≥10b USD'
    return {'sector':stock.sector if profile else 'N/A','size_band':size_band,'market_cap':cap,'symbol':stock.ticker,'name':stock.name or listing['name'],'exchange':listing['exchange'],
            'identity_verified':stock.identity_verified,'rank_exclusions':exclusions,'score':score,'resilience':resilience,'coverage':coverage,
            'growth':growth,'forward_pe':pe,'fcf_margin':fcf,'net_debt_ebitda':m.get('net_debt_ebitda'),
            'themes':theme,'undervalued_growth':undervalued,'swing':swing,'price_date':price_date,
            'fetched_at':stock.fetched,'annual_period':stock.resilience_period,'annual_age_days':annual_age,'fresh_annual':fresh_annual,'currency':stock.resilience_currency,
            'missing':[k for k in INPUT_KEYS if m.get(k) is None], 'warnings':stock.warnings,
            'provenance':stock.resilience_provenance,'source':stock.source}


def scan(listings,cache,limit=10,excluded=(),loader=load_stock,progress=None,min_interval=3,offset=0):
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
        value=cache.get(key)
        if value is not None:
            stock=unpack(value);cache_hits+=1
        else:
            # Global process gate prevents concurrent discovery sessions from bursting providers.
            with _GATE:
                value=cache.get(key)  # Another session may have filled it while we waited.
                if value is not None:
                    stock=unpack(value);cache_hits+=1
                else:
                    if cache.get('cooldown:v1'):
                        stopped='Aktívna 15-minútová prestávka po limite poskytovateľa.';break
                    budget_key='network-budget:'+datetime.now(timezone.utc).date().isoformat()
                    used=cache.get(budget_key) or 0
                    if used>=100:
                        stopped='Denný limit 100 nových sieťových analýz bol dosiahnutý (UTC); cache ostáva dostupná.';break
                    time.sleep(max(0,min_interval-(time.monotonic()-_LAST_START)))
                    _LAST_START=time.monotonic();network_loads+=1;loaded_network=True
                    cache.put(budget_key,used+1,48*3600)
                    try:stock=loader(listing['symbol'])
                    except Exception:
                        from screener import Stock
                        stock=Stock(listing['symbol'],warnings=['Analýza zlyhala; údaje sú N/A.'])
                    usable=stock.identity_verified and any(v is not None for v in stock.resilience_inputs.values())
                    cache.put(key,pack(stock),24*3600 if usable else 15*60)
        attempted+=1
        row=analyze(stock,listing);rows.append(row)
        if progress:progress(attempted,len(selected))
        limited=any('429' in w or '401/403' in w for w in stock.warnings)
        if limited and loaded_network:
            cache.put('cooldown:v1',{'reason':'provider limit/access rejection','at':now_iso()},15*60)
            stopped='Zdroj vrátil limit alebo odmietol prístup; ďalšie sieťové analýzy sa zastavili na 15 minút.';break
    return {'rows':rows,'attempted':attempted,'cache_hits':cache_hits,'network_loads':network_loads,
            'analyzed':sum(r['identity_verified'] and any(r[k] is not None for k in ('growth','forward_pe','fcf_margin','net_debt_ebitda')) for r in rows),
            'ranked':sum(r['score'] is not None for r in rows),'stopped':stopped,'completed_at':now_iso()}


def ranked_rows(rows,theme='Všetky',undervalued=False,swing=False,min_coverage=70):
    result=[r for r in rows if r['score'] is not None and recent(r) and r['coverage']>=min_coverage
            and (theme=='Všetky' or r['themes'].get(theme) is True)
            and (not undervalued or r['undervalued_growth'] is True)
            and (not swing or r['swing'] is True)]
    return sorted(result,key=lambda r:(-r['score'],r['symbol']))


def top20(rows,theme='Všetky',undervalued=False,swing=False,min_coverage=70):
    return ranked_rows(rows,theme,undervalued,swing,min_coverage)[:20]
