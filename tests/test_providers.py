import pandas as pd
import pytest
import requests
from providers import DataError, error_reason, get_json
from secdata import parse_facts, load_sec, company_index
from data import load_stock


def facts_fixture():
    # Syntetické dáta patria iba do testov; nikdy sa nepoužívajú v aplikácii.
    tags = {'RevenueFromContractWithCustomerExcludingAssessedTax':(200,100),'NetIncomeLoss':(20,-10),'GrossProfit':(80,40),'OperatingIncomeLoss':(30,20),'NetCashProvidedByUsedInOperatingActivities':(50,40),'PaymentsToAcquirePropertyPlantAndEquipment':(10,10),'AssetsCurrent':(100,100),'LiabilitiesCurrent':(50,50),'EarningsPerShareDiluted':(2,1)}
    result={}
    for tag,values in tags.items():
        records=[]
        for year,value in zip((2025,2024),values):
            r={'end':f'{year}-06-30','filed':f'{year}-08-20','form':'10-K','val':value}
            if tag not in ('AssetsCurrent','LiabilitiesCurrent'):
                r['start']=f'{year-1}-07-01'
            records.append(r)
        unit='USD/shares' if tag=='EarningsPerShareDiluted' else 'USD'
        result[tag]={'units':{unit:records}}
    return {'cik':820318,'facts':{'us-gaap':result}}


def test_sec_annual_metrics_and_negative_growth_base():
    metrics,end=parse_facts(facts_fixture())
    assert end=='2025-06-30'
    assert metrics['revenue_growth']==1
    assert metrics['earnings_growth'] is None
    assert metrics['gross_margin']==.4
    assert metrics['fcf']==40
    assert metrics['eps']==2
    assert metrics['current_ratio']==2
    assert 'forward_pe' not in metrics


def test_sec_does_not_use_quarterly_or_missing_capex():
    payload=facts_fixture()
    tags=payload['facts']['us-gaap']
    del tags['PaymentsToAcquirePropertyPlantAndEquipment']
    tags['GrossProfit']['units']['USD'][0]['start']='2025-04-01'
    metrics,_=parse_facts(payload)
    assert metrics['fcf'] is None
    assert metrics['gross_margin'] is None


def test_sec_rejects_unsupported_currency():
    payload=facts_fixture()
    payload['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']={'EUR':[]}
    with pytest.raises(DataError,match='USD'):
        parse_facts(payload)


def test_cohr_registry_identity_and_invalid_symbol(monkeypatch):
    monkeypatch.setattr('secdata.company_index',lambda:{'0':{'ticker':'COHR','title':'Coherent Corp.','cik_str':820318}})
    urls=[]
    def get(url,**kwargs):
        urls.append(url)
        return facts_fixture()
    monkeypatch.setattr('secdata.get_json',get)
    assert load_sec('COHR')[0]=='Coherent Corp.'
    assert urls[0].endswith('CIK0000820318.json')
    with pytest.raises(DataError,match='nenašiel'):
        load_sec('COHR.DE')
    monkeypatch.setattr('secdata.get_json',lambda *args,**kwargs:{'cik':1})
    with pytest.raises(DataError,match='identitu'):
        load_sec('COHR')


@pytest.mark.parametrize('exc,expected',[(requests.exceptions.ProxyError('403 tunnel'),'proxy'),(requests.exceptions.Timeout('private secret'),'čas'),(type('YFRateLimitError',(Exception,),{})('private'),'429'),(Exception('Invalid Crumb secret'),'401/403')])
def test_error_classification_and_redaction(exc,expected):
    reason=error_reason(exc)
    assert expected in reason
    assert 'secret' not in reason and 'private' not in reason


def test_http_retry_is_bounded(monkeypatch):
    calls=[]
    class Response:
        status_code=429
        headers={'Retry-After':'1'}
        def raise_for_status(self):
            raise requests.HTTPError('private url?apikey=SECRET',response=self)
    monkeypatch.setattr('providers.requests.get',lambda *a,**kw: calls.append(kw) or Response())
    monkeypatch.setattr('providers.time.sleep',lambda seconds:None)
    with pytest.raises(DataError,match='429') as exc:
        get_json('https://www.sec.gov/example')
    assert len(calls)==2 and 'SECRET' not in str(exc.value)


def test_long_retry_after_is_not_retried(monkeypatch):
    calls=[]
    class Response:
        status_code=429
        headers={'Retry-After':'120'}
        def raise_for_status(self):
            raise requests.HTTPError(response=self)
    monkeypatch.setattr('providers.requests.get',lambda *a,**kw: calls.append(1) or Response())
    with pytest.raises(DataError): get_json('https://www.sec.gov/example')
    assert len(calls)==1


def test_yahoo_failure_falls_back_without_fabricating_price(monkeypatch):
    class Asset:
        def get_info(self): raise type('YFRateLimitError',(Exception,),{})()
        def history(self,**kwargs): return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    monkeypatch.setattr('data.load_sec',lambda s:('Coherent Corp.',{'eps':2,'fcf':40},'2025-06-30'))
    stock=load_stock('COHR')
    assert stock.metrics['eps']==2
    assert stock.metrics.get('price') is None
    assert stock.metrics.get('pe') is None
    assert 'SEC EDGAR' in stock.provenance['eps']
    assert any('429' in w for w in stock.warnings)


def test_partial_yahoo_values_are_not_overwritten(monkeypatch):
    class Asset:
        income_stmt=pd.DataFrame()
        balance_sheet=pd.DataFrame()
        def get_info(self): return {'longName':'Test','trailingEps':3,'financialCurrency':'USD'}
        def history(self,**kwargs): return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    monkeypatch.setattr('data.load_sec',lambda s:('Test',{'eps':2,'fcf':40},'2025-06-30'))
    stock=load_stock('COHR')
    assert stock.metrics['eps']==3 and stock.metrics['fcf']==40
    assert 'Yahoo' in stock.provenance['eps']
    assert '2025-06-30' in stock.provenance['fcf']


def test_curl_proxy_denial_is_not_misreported_as_bad_ticker():
    assert 'proxy' in error_reason(Exception('Failed to perform, curl: (7) CONNECT tunnel failed, response 403'))


def test_latest_revenue_tag_wins_over_obsolete_tag():
    payload=facts_fixture()
    tags=payload['facts']['us-gaap']
    tags['Revenues']=tags['RevenueFromContractWithCustomerExcludingAssessedTax']
    tags['RevenueFromContractWithCustomerExcludingAssessedTax']={'units':{'USD':[{'start':'2021-07-01','end':'2022-06-30','filed':'2022-08-20','form':'10-K','val':1}]}}
    metrics,end=parse_facts(payload)
    assert end=='2025-06-30' and metrics['gross_margin']==.4


def test_sec_usd_not_merged_with_other_reporting_currency(monkeypatch):
    class Asset:
        income_stmt=pd.DataFrame()
        balance_sheet=pd.DataFrame()
        def get_info(self): return {'longName':'Test','financialCurrency':'EUR'}
        def history(self,**kwargs): return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    monkeypatch.setattr('data.load_sec',lambda s:('Test',{'eps':2},'2025-06-30'))
    stock=load_stock('TEST')
    assert stock.metrics['eps'] is None
    assert any('nemiešajú' in w for w in stock.warnings)
