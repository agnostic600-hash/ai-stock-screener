import pytest
from discovery_campaign import Campaigns,scan_campaign
from discovery_cache import Cache
from discovery import scan
from discovery_audit import audit,coverage_estimate
from test_discovery import listing,stock


def universe():return {'listings':[listing(s) for s in ('AAA','BBB','CCC','DDD','EEE')],'fetched_at':'fixture','file_times':{}}

def scanner(listings,cache,limit):return scan(listings,cache,limit,loader=stock,min_interval=0)


def test_durable_full_traversal_without_repeating_first_batch(tmp_path):
    cache=Cache(tmp_path/'db.sqlite');campaign=Campaigns(cache);ident=campaign.start(universe())
    first=scan_campaign(campaign,ident,2,scanner=scanner)
    # Simulate a new browser and process object, with no session-state offset.
    resumed=Campaigns(Cache(tmp_path/'db.sqlite'))
    assert resumed.start(universe())==ident
    second=scan_campaign(resumed,ident,2,scanner=scanner)
    third=scan_campaign(resumed,ident,2,scanner=scanner)
    symbols=[r['symbol'] for part in (first,second,third) for r in part['rows']]
    assert len(symbols)==len(set(symbols))==5
    assert resumed.counts(ident)['done']==5
    assert scan_campaign(resumed,ident,2,scanner=scanner)['attempted']==0
    assert resumed.start(universe(),new=True)!=ident


def test_cannot_reset_partial_sweep_or_change_frozen_snapshot(tmp_path):
    c=Campaigns(Cache(tmp_path/'db'));ident=c.start(universe())
    with pytest.raises(ValueError):c.start(universe(),new=True)
    c.start({'listings':[listing('NEW')]})
    assert c.current()['universe']==universe()
    assert c.counts(ident)['total']==5


def test_claims_do_not_overlap_and_crash_lease_is_recoverable(tmp_path):
    c=Campaigns(Cache(tmp_path/'db'));ident=c.start(universe())
    a=c.claim(ident,now=100,lease_seconds=10);b=c.claim(ident,now=100,lease_seconds=10)
    assert a['symbol']!=b['symbol']
    recovered=c.claim(ident,now=111)
    assert recovered['symbol']==a['symbol'] and recovered['owner']!=a['owner']
    with pytest.raises(ValueError):c.finish(ident,a,{'symbol':a['symbol']})
    c.finish(ident,recovered,{'symbol':recovered['symbol']})
    assert c.counts(ident)['done']==1


def test_quota_stop_does_not_skip_unattempted_symbol(tmp_path):
    c=Campaigns(Cache(tmp_path/'db'));ident=c.start(universe());claimed=[]
    def blocked(listings,cache,limit):claimed.append(listings[0]['symbol']);return {'rows':[],'stopped':'budget'}
    assert scan_campaign(c,ident,2,scanner=blocked)['attempted']==0
    assert c.counts(ident)['pending']==5
    result=scan_campaign(c,ident,1,scanner=scanner)
    assert result['rows'][0]['symbol']==claimed[0]


def test_failed_attempt_is_done_without_retry_bias(tmp_path):
    c=Campaigns(Cache(tmp_path/'db'));ident=c.start(universe())
    def broken(symbol):raise RuntimeError('source failed')
    failure=lambda listings,cache,limit:scan(listings,cache,limit,loader=broken,min_interval=0)
    result=scan_campaign(c,ident,1,scanner=failure)
    assert result['analyzed']==0 and c.counts(ident)['done']==1
    after=scan_campaign(c,ident,1,scanner=scanner)
    assert after['rows'][0]['symbol']!=result['rows'][0]['symbol']


def test_availability_bias_is_measured_not_imputed():
    from discovery import analyze
    a=analyze(stock('AAA'),listing('AAA'))
    s=stock('BBB');s.resilience_inputs.pop('fcf_margin')
    b=analyze(s,listing('BBB'));b['exchange']='NYSE'
    report=audit([a,b],[listing('AAA'),{**listing('BBB'),'exchange':'NYSE'}])
    assert report['analyzed']==2 and report['ranked_at_fetch']==1
    assert report['overlapping_reasons']['N/A: fcf']==1
    assert sum(report['primary_reasons'].values())==1
    rates={r['group']:r['rank_rate'] for r in report['groups'] if r['dimension']=='exchange'}
    assert rates=={'NASDAQ':1,'NYSE':0}
    assert b['score'] is None


def test_realistic_budget_estimate():
    result=coverage_estimate(5370)
    assert result['daily_budgets']==54
    assert result['active_hours_5_to_20s'][0]>7
    assert coverage_estimate(5370,done=100)['daily_budgets']==53


def test_selection_ignores_financial_availability():
    from discovery import candidates
    first=universe()['listings']
    second=[{**r,'coverage':0,'score':None} for r in reversed(first)]
    assert [r['symbol'] for r in candidates(first)]==[r['symbol'] for r in candidates(second)]


def test_old_financial_snapshots_are_not_ranked_as_current():
    from discovery import analyze,top20
    from datetime import datetime,timedelta,timezone
    row=analyze(stock(),listing())
    row['fetched_at']=(datetime.now(timezone.utc)-timedelta(hours=49)).isoformat()
    assert row['score'] is not None  # Historical eligibility remains auditable.
    assert top20([row])==[]
