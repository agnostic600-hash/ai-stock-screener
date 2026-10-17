"""Synthetic unit contracts, deliberately no live market calls."""
from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest
from screener import Stock
from providers import DataError
from market_universe import parse_directory
from discovery_cache import Cache, pack, unpack
from discovery import analyze, scan, top20, candidates, swing_signal


def listing(symbol='UNIT'):
    return {'symbol':symbol,'listing_symbol':symbol,'exchange':'NASDAQ','name':'Unit Test Common Stock'}


def stock(symbol='UNIT'):
    return Stock(symbol,identity_verified=True,name='Test',currency='USD',resilience_period=datetime.now(timezone.utc).date().isoformat(),
        resilience_inputs=dict(fcf_margin=.2,net_debt_ebitda=0,revenue_growth=.2,operating_margin=.2,forward_pe=5,share_dilution=0,ai_capex_exposure=None),
        profile={'industry':'Semiconductor equipment','longBusinessSummary':'industrial automation robotics','quoteType':'EQUITY'})


def test_directory_excludes_etf_tests_and_unsupported_names():
    text='Symbol|Security Name|Test Issue|ETF|NextShares\nGOOD|Good Common Stock|N|N|N\nETF|Exchange Fund|N|Y|N\nTEST|Test Common|Y|N|N\nBADW|Bad Warrants|N|N|N\nFile Creation Time: 10172026|x||||\n'
    rows,stamp=parse_directory(text,'nasdaqlisted.txt')
    assert [r['symbol'] for r in rows]==['GOOD']
    assert stamp=='10172026'


def test_other_directory_selects_nyse_n_and_normalizes_class():
    text='ACT Symbol|Security Name|Exchange|Test Issue|ETF\nBRK.B|Berkshire Common Stock|N|N|N\nARCA|Arca Common Stock|P|N|N\nAMEX|Amex Common|A|N|N\nFile Creation Time: now||||\n'
    rows,_=parse_directory(text,'otherlisted.txt')
    assert rows==[{'symbol':'BRK-B','listing_symbol':'BRK.B','exchange':'NYSE','name':'Berkshire Common Stock'}]


def test_invalid_or_truncated_directory_rejected():
    for text in ['<html>blocked</html>','Symbol|Security Name|Test Issue|ETF\nGOOD|Good|N|N\n']:
        with pytest.raises(DataError):parse_directory(text,'nasdaqlisted.txt')


def test_cache_expiry_and_stock_roundtrip(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite')
    cache.put('test',{'value':0},10,now=100)
    assert cache.get('test',now=109)=={'value':0}
    assert cache.get('test',now=110) is None
    s=stock();s.history=pd.Series([1.,2.],index=pd.date_range('2026-01-01',periods=2,tz='UTC'));s.volume_history=s.history*100
    restored=unpack(pack(s))
    pd.testing.assert_series_equal(restored.history,s.history.rename('UNIT'),check_freq=False)
    assert restored.identity_verified


def test_rank_requires_real_complete_inputs_and_recent_annual():
    s=stock();r=analyze(s,listing())
    assert r['score'] is not None and r['coverage']==90
    s.resilience_inputs.pop('fcf_margin')
    assert analyze(s,listing())['score'] is None
    assert 'fcf_margin' in analyze(s,listing())['missing']
    s=stock();s.resilience_period='2020-01-01'
    assert analyze(s,listing())['score'] is None
    s=stock();s.identity_verified=False
    assert analyze(s,listing())['score'] is None


def test_filters_and_top_twenty_are_from_analyzed_rows():
    rows=[analyze(stock(str(i)),listing(str(i))) for i in range(25)]
    assert len(top20(rows))==20
    assert len(top20(rows,theme='Robotika'))==20
    assert len(top20(rows,undervalued=True))==20
    assert not top20(rows,swing=True)
    s=stock();s.profile={}
    assert analyze(s,listing())['themes']['Robotika'] is None


def test_sequential_scan_counts_cache_and_exclusions(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite');calls=[]
    def load(symbol):calls.append(symbol);return stock(symbol)
    listings=[listing(s) for s in ['AAA','BBB','CCC']]
    first=scan(listings,cache,2,loader=load,min_interval=0)
    assert first['attempted']==2 and first['network_loads']==2 and first['analyzed']==2
    again=scan(listings,cache,2,loader=load,min_interval=0)
    assert again['cache_hits']==2 and again['network_loads']==0
    remaining=scan(listings,cache,2,excluded=calls,loader=load,min_interval=0)
    assert remaining['attempted']==1 and len(calls)==3
    assert candidates(listings)==candidates(list(reversed(listings)))


def test_limit_failure_and_cooldown_are_honest(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite');calls=[]
    def load(symbol):
        calls.append(symbol)
        return Stock(symbol,warnings=['Limit API (HTTP 429)'])
    r=scan([listing('AAA'),listing('BBB')],cache,2,loader=load,min_interval=0)
    assert len(calls)==1 and r['analyzed']==0 and r['ranked']==0 and r['stopped']
    r=scan([listing('CCC')],cache,1,loader=load,min_interval=0)
    assert r['attempted']==0 and r['network_loads']==0
    with pytest.raises(ValueError):scan([],cache,101,loader=load)


def test_swing_requires_fresh_history_and_volume():
    now=datetime.now(timezone.utc)
    dates=pd.date_range(end=now,periods=60)
    prices=pd.Series([100+i for i in range(55)]+[154,153,152,151,150],index=dates,dtype=float)
    volume=pd.Series([20000.]*59+[30000.],index=dates)
    assert swing_signal(prices,volume,now)[0] is True
    assert swing_signal(prices,None,now)[0] is None
    assert swing_signal(prices,volume,now+timedelta(days=8))[0] is None


def test_daily_network_budget_does_not_block_cache(tmp_path):
    from discovery import now_iso
    cache=Cache(tmp_path/'cache.sqlite')
    cache.put('network-budget:'+now_iso()[:10],100,1000)
    cache.put('stock:v1:AAA',pack(stock('AAA')),1000)
    r=scan([listing('AAA')],cache,1,loader=lambda s:pytest.fail('must not call network'),min_interval=0)
    assert r['cache_hits']==1
    r=scan([listing('BBB')],cache,1,loader=lambda s:pytest.fail('budget exhausted'),min_interval=0)
    assert r['attempted']==0 and r['stopped']


def test_offset_advances_to_next_universe_slice(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite');rows=[listing(s) for s in ('AAA','BBB','CCC')]
    first=scan(rows,cache,1,loader=stock,min_interval=0)
    second=scan(rows,cache,1,loader=stock,min_interval=0,offset=1)
    assert first['rows'][0]['symbol']!=second['rows'][0]['symbol']


def test_cached_limit_warning_does_not_restart_cooldown(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite')
    s=stock('AAA');s.warnings=['HTTP 429 during an older fetch']
    cache.put('stock:v1:AAA',pack(s),1000)
    r=scan([listing('AAA')],cache,1,loader=stock,min_interval=0)
    assert r['cache_hits']==1 and r['stopped'] is None
    assert cache.get('cooldown:v1') is None


def test_loader_exception_is_visible_as_failed_attempt(tmp_path):
    cache=Cache(tmp_path/'cache.sqlite')
    def broken(symbol):raise RuntimeError('provider failed')
    result=scan([listing()],cache,1,loader=broken,min_interval=0)
    assert result['attempted']==1 and result['analyzed']==0 and result['ranked']==0
    assert result['rows'][0]['score'] is None
    assert result['rows'][0]['missing'] and result['rows'][0]['rank_exclusions']
