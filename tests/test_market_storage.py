from datetime import datetime,timezone,timedelta
import pandas as pd
from discovery_cache import Cache
from market_store import MarketStore,fundamental_status
from discovery_campaign import Campaigns
from discovery import analyze,top20
from market_refresh import refresh_prices
from test_discovery import stock,listing


def test_fundamentals_survive_54_days_when_policy_valid_and_prices_are_new(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));s=stock();now=datetime.now(timezone.utc)
    s.resilience_period=(now-timedelta(days=100)).date().isoformat()
    s.fetched=(now-timedelta(days=54)).isoformat();s.profile['regularMarketTime']=(now-timedelta(days=54)).timestamp()
    assert store.save_fundamentals(s)
    fundamental,meta=store.get('fundamentals',s.ticker)
    assert fundamental_status(meta)[0]
    quote=stock();quote.profile={'price_asof':now.isoformat()};quote.metrics={'price':120}
    assert store.save_prices(quote)
    p,pm=store.get('prices',s.ticker);row=analyze(fundamental,listing(),meta,p,pm)
    assert row['forward_pe']==6 and len(top20([row]))==1
    assert row['fetched_at']==s.fetched and row['price_retrieved_at']!=s.fetched
    assert fundamental.profile['forwardEps']==20


def test_expiry_known_filing_and_missing_publication_are_distinct(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));s=stock();s.sec_cik='0000001234'
    store.save_fundamentals(s);f,m=store.get('fundamentals',s.ticker)
    assert m['published_at'] is None and fundamental_status(m)[0]
    assert not fundamental_status(m,datetime.now(timezone.utc)+timedelta(days=91))[0]
    day=datetime.now(timezone.utc).date().isoformat()
    store.observe_filings({'1234':{'published_at':day,'key':'edgar/data/1234/new','form':'10-Q'}})
    f,m=store.get('fundamentals',s.ticker)
    assert m['report_pending'] and not fundamental_status(m)[0]
    assert f.resilience_inputs['fcf_margin']==.2
    store.save_fundamentals(stock());assert fundamental_status(store.get('fundamentals',s.ticker)[1])[0]


def test_expected_report_shortens_validity(tmp_path):
    s=stock();s.next_report_at=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()
    store=MarketStore(Cache(tmp_path/'db'));store.save_fundamentals(s)
    meta=store.get('fundamentals',s.ticker)[1]
    assert not fundamental_status(meta,datetime.now(timezone.utc)+timedelta(days=8))[0]


def test_price_outage_preserves_last_good_without_refreshing_fundamentals(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));s=stock();store.save_fundamentals(s)
    original=store.get('fundamentals',s.ticker)[1]['retrieved_at']
    old=store.get('prices',s.ticker)[1].copy()
    def fail(symbol):raise TimeoutError('provider private error')
    status=refresh_prices(store,[listing()],loader=fail,min_interval=0)
    assert status['updated']==0 and status['errors']
    assert store.get('fundamentals',s.ticker)[1]['retrieved_at']==original
    assert store.get('prices',s.ticker)[1]['price_asof']==old['price_asof']
    assert store.get('prices',s.ticker)[1]['last_error']


def test_old_prices_do_not_expire_valid_fundamentals(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));s=stock();store.save_fundamentals(s)
    p,pm=store.get('prices',s.ticker);pm['price_asof']=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
    f,fm=store.get('fundamentals',s.ticker);row=analyze(f,listing(),fm,p,pm)
    assert row['fundamental_valid'] and not row['price_valid'] and row['score'] is None


def test_restart_and_cache_expiry_do_not_delete_snapshots_or_campaign(tmp_path):
    cache=Cache(tmp_path/'db');store=MarketStore(cache);store.save_fundamentals(stock())
    campaigns=Campaigns(cache);ident=campaigns.start({'listings':[listing()],'fetched_at':'fixture','file_times':{}})
    claim=campaigns.claim(ident);f,m=store.get('fundamentals','UNIT');p,pm=store.get('prices','UNIT')
    campaigns.finish(ident,claim,analyze(f,listing(),m,p,pm))
    cache.put('old',1,1,now=1)
    resumed=Campaigns(Cache(tmp_path/'db'))
    assert resumed.counts(ident)['done']==1
    assert resumed.rows(ident)[0]['fundamental_valid']
    assert MarketStore(Cache(tmp_path/'db')).get('fundamentals','UNIT')[0] is not None


def test_price_queue_advances_past_recent_quotes(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'))
    for symbol in ('AAA','BBB'):store.save_fundamentals(stock(symbol))
    calls=[]
    def load(symbol):
        calls.append(symbol);p=stock(symbol)
        p.history=pd.Series(range(100,160),index=pd.date_range(end=datetime.now(timezone.utc),periods=60))
        p.volume_history=p.history*10000;return p
    refresh_prices(store,[listing('AAA'),listing('BBB')],limit=1,loader=load,min_interval=0)
    refresh_prices(store,[listing('AAA'),listing('BBB')],limit=1,loader=load,min_interval=0)
    assert len(set(calls))==2


def test_no_forward_eps_never_fabricates_repriced_valuation(tmp_path):
    s=stock();s.profile.pop('forwardEps');s.profile['regularMarketTime']=(datetime.now(timezone.utc)-timedelta(days=20)).timestamp()
    store=MarketStore(Cache(tmp_path/'db'));store.save_fundamentals(s)
    quote=stock();quote.profile={'price_asof':datetime.now(timezone.utc).isoformat()};store.save_prices(quote)
    f,m=store.get('fundamentals','UNIT');p,pm=store.get('prices','UNIT');row=analyze(f,listing(),m,p,pm)
    assert row['forward_pe'] is None and row['score'] is None


def test_bulk_price_file_joins_known_identity_currency_and_dates(tmp_path):
    from bulk_prices import import_prices
    store=MarketStore(Cache(tmp_path/'db'));store.save_fundamentals(stock())
    path=tmp_path/'licensed.csv';now=datetime.now(timezone.utc).isoformat()
    path.write_text('symbol,price,price_asof,currency\nUNIT,123,'+now+',USD\nOTHER,12,'+now+',USD\nUNIT,10,'+now+',EUR\n')
    result=import_prices(store,path,{'UNIT'})
    assert result['accepted']==1 and result['rejected']==2
    assert store.get('prices','UNIT')[0].metrics['price']==123
    assert store.get('prices','UNIT')[0].profile['swing_signal'] is None


def test_fundamental_outage_never_marks_old_snapshot_as_refreshed(tmp_path):
    from discovery import scan
    cache=Cache(tmp_path/'db');store=MarketStore(cache);s=stock();store.save_fundamentals(s)
    old,m=store.get('fundamentals','UNIT');m['valid_until']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();store.save('fundamentals',old,m)
    def fail(symbol):raise TimeoutError('upstream unavailable')
    result=scan([listing()],cache,1,loader=fail,min_interval=0)
    preserved,meta=store.get('fundamentals','UNIT')
    assert preserved.fetched==old.fetched and meta['retrieved_at']==old.fetched
    assert meta['last_error'] and result['rows'][0]['score'] is None
    assert preserved.resilience_inputs['fcf_margin']==.2


def test_price_only_loader_does_not_fetch_info_or_sec(monkeypatch):
    from data import load_prices
    class Asset:
        def get_info(self):raise AssertionError('No fundamental request allowed')
        def history(self,**kwargs):return pd.DataFrame({'Close':[100.,101.],'Volume':[1000.,1100.]},index=pd.date_range(end=datetime.now(timezone.utc),periods=2))
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    assert load_prices('UNIT').history.iloc[-1]==101


def test_fundamental_loader_skips_explicit_price_history(monkeypatch):
    from data import load_fundamentals
    from test_resilience_data import frames
    inc,flow,bal=frames()
    class Asset:
        income_stmt=inc;cashflow=flow;balance_sheet=bal
        def get_info(self):return {'symbol':'UNIT','financialCurrency':'USD'}
        def history(self,**kwargs):raise AssertionError('No price-history request allowed')
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    result=load_fundamentals('UNIT')
    assert result.history is None and result.resilience_inputs['annual_fcf']==40


def test_daily_bar_can_update_technicals_without_rewinding_newer_quote(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));s=stock();store.save_fundamentals(s)
    quote,original=store.get('prices','UNIT')
    day=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    bars=stock();bars.history=pd.Series(range(100,160),index=pd.date_range(end=day,periods=60));bars.volume_history=bars.history*10000
    assert store.save_prices(bars)
    retained,meta=store.get('prices','UNIT')
    assert meta['price_asof']==original['price_asof']
    assert retained.metrics['price']==quote.metrics['price']
    assert meta['technical_asof']==day.isoformat() and retained.profile['technical_computed']


def test_future_price_cannot_replace_last_successful_quote(tmp_path):
    store=MarketStore(Cache(tmp_path/'db'));store.save_fundamentals(stock())
    old=store.get('prices','UNIT')[1].copy()
    quote=stock();quote.profile={'price_asof':(datetime.now(timezone.utc)+timedelta(days=20)).isoformat()}
    assert not store.save_prices(quote)
    assert store.get('prices','UNIT')[1]['price_asof']==old['price_asof']


def test_migration_preserves_snapshots_progress_and_refuses_overwrite(tmp_path):
    import pytest
    from migrate_storage import migrate
    source=Cache(tmp_path/'source.sqlite');store=MarketStore(source);store.save_fundamentals(stock())
    campaigns=Campaigns(source);ident=campaigns.start({'listings':[listing('AAA'),listing('BBB')],'fetched_at':'fixture','file_times':{}})
    claim=campaigns.claim(ident);campaigns.finish(ident,claim,{'symbol':claim['symbol']})
    other=campaigns.claim(ident)
    target=Cache(tmp_path/'target.sqlite');report=migrate(source.path,target,apply=True)
    assert report['market_snapshots']>=1
    resumed=Campaigns(target)
    assert resumed.counts(ident)['done']==1 and resumed.counts(ident)['pending']==1
    assert MarketStore(target).get('fundamentals','UNIT')[0].identity_verified
    with pytest.raises(ValueError):migrate(source.path,target,apply=True)
