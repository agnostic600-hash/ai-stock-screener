"""Synthetic statement contracts only; not live financial facts."""
import pandas as pd
import pytest
from resilience_data import yahoo_annual
from secdata import parse_facts
from data import load_stock
from test_providers import facts_fixture


def frames():
    dates=pd.to_datetime(['2025-06-30','2024-06-30'])
    income=pd.DataFrame([[200,100],[80,40],[30,20],[50,30],[12,10]],index=['Total Revenue','Gross Profit','Operating Income','EBITDA','Diluted Average Shares'],columns=dates)
    flow=pd.DataFrame([[50,40],[-10,-10]],index=['Operating Cash Flow','Capital Expenditure'],columns=dates)
    balance=pd.DataFrame([[80,50],[100,80]],index=['Cash And Cash Equivalents','Total Debt'],columns=dates)
    return income,flow,balance


def test_yahoo_annual_aligned_ratios_and_zero_is_real():
    values,end=yahoo_annual(*frames(),'USD')
    assert end=='2025-06-30'
    assert values['annual_fcf']==40
    assert values['fcf_margin']==.2
    assert values['net_debt_ebitda']==.4
    assert values['share_dilution']==pytest.approx(.2)
    assert values['ai_capex_exposure'] is None
    assert values['debt_due_24m'] is None


def test_yahoo_mismatch_and_no_currency_fail_closed():
    income,flow,balance=frames()
    flow.columns=pd.to_datetime(['2023-06-30','2022-06-30'])
    assert yahoo_annual(income,flow,balance,'USD')==({},None)
    assert yahoo_annual(*frames(),'')==({},None)


def test_yahoo_missing_shares_and_wrong_capex_sign_are_not_zero():
    income,flow,balance=frames()
    income=income.drop('Diluted Average Shares')
    flow.loc['Capital Expenditure']=10
    values,_=yahoo_annual(income,flow,balance,'USD')
    assert values['share_dilution'] is None
    assert values['annual_fcf'] is None


def full_facts():
    p=facts_fixture();tags=p['facts']['us-gaap']
    for tag,value in [('CashAndCashEquivalentsAtCarryingValue',80),('LongTermDebtNoncurrent',80),('LongTermDebtCurrent',10),('ShortTermBorrowings',0),('LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths',10),('LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo',20)]:
        tags[tag]={'units':{'USD':[{'end':'2025-06-30','form':'10-K','filed':'2025-08-20','val':value}]}}
    for tag,unit,values in [('WeightedAverageNumberOfDilutedSharesOutstanding','shares',(12,10)),('DepreciationDepletionAndAmortization','USD',(20,10))]:
        tags[tag]={'units':{unit:[{'start':f'{y-1}-07-01','end':f'{y}-06-30','form':'10-K','filed':f'{y}-08-20','val':v} for y,v in zip((2025,2024),values)]}}
    return p


def test_sec_complete_bundle_and_explicit_zero_borrowings():
    m,end=parse_facts(full_facts());v=m['_resilience']
    assert v['fcf_margin']==.2
    assert v['net_debt_ebitda']==.2
    assert v['debt_due_24m']==30
    assert v['cash']==80
    assert v['share_dilution']==pytest.approx(.2)


def test_sec_missing_short_term_borrowings_does_not_assume_zero():
    p=full_facts();del p['facts']['us-gaap']['ShortTermBorrowings']
    v=parse_facts(p)[0]['_resilience']
    assert v['net_debt_ebitda'] is None
    assert v['debt_due_24m'] is None


def test_sec_missing_second_year_maturity_does_not_use_total_debt():
    p=full_facts();del p['facts']['us-gaap']['LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo']
    assert parse_facts(p)[0]['_resilience']['debt_due_24m'] is None


def test_sec_quarterly_capex_not_merged_with_annual_revenue():
    p=full_facts();p['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD'][0]['start']='2025-04-01'
    assert parse_facts(p)[0]['_resilience']['annual_fcf'] is None


def test_wrong_yahoo_identity_cannot_supply_resilience(monkeypatch):
    class Asset:
        def get_info(self):return {'symbol':'OTHER','forwardPE':5,'financialCurrency':'USD'}
        def history(self,**kwargs):return pd.DataFrame()
        @property
        def cashflow(self):raise AssertionError('must not access mismatched issuer statements')
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    stock=load_stock('COHR')
    assert all(v is None for v in stock.resilience_inputs.values())


def test_yahoo_bundle_is_preserved_when_sec_unavailable(monkeypatch):
    income,flow,balance=frames()
    class Asset:
        income_stmt=income
        cashflow=flow
        balance_sheet=balance
        def get_info(self):return {'symbol':'COHR','forwardPE':20,'financialCurrency':'USD'}
        def history(self,**kwargs):return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    stock=load_stock('COHR')
    assert stock.resilience_inputs['annual_fcf']==40
    assert stock.resilience_inputs['forward_pe']==20
    assert '2025-06-30' in stock.resilience_provenance['annual_fcf']


def test_sec_newer_bundle_replaces_old_yahoo_without_mixing(monkeypatch):
    income,flow,balance=frames()
    class Asset:
        income_stmt=income
        cashflow=flow
        balance_sheet=balance
        def get_info(self):return {'symbol':'COHR','forwardPE':20,'financialCurrency':'USD'}
        def history(self,**kwargs):return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    monkeypatch.setattr('data.load_sec',lambda s:('Issuer',{'_resilience':{'annual_revenue':300,'annual_fcf':None}},'2026-06-30'))
    stock=load_stock('COHR')
    assert stock.resilience_inputs.get('annual_fcf') is None
    assert stock.resilience_inputs['annual_revenue']==300
    assert stock.resilience_inputs['forward_pe']==20


def test_sec_flow_without_start_is_not_treated_as_annual():
    p=full_facts()
    del p['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][0]['start']
    assert parse_facts(p)[0]['_resilience']['annual_fcf'] is None


def test_dilution_previous_period_must_align_with_previous_revenue():
    p=full_facts()
    p['facts']['us-gaap']['WeightedAverageNumberOfDilutedSharesOutstanding']['units']['shares'][1]['start']='2023-07-02'
    assert parse_facts(p)[0]['_resilience']['share_dilution'] is None


def test_invalid_balance_and_share_counts_do_not_improve_score():
    income,flow,balance=frames()
    income.loc['Diluted Average Shares']=0
    balance.loc['Total Debt']=-1
    values,_=yahoo_annual(income,flow,balance,'USD')
    assert values['share_dilution'] is None
    assert values['net_debt_ebitda'] is None


def test_loader_sec_bundle_drives_scoring_and_stress(monkeypatch):
    from resilience import evaluate_resilience, stress_24m
    class Asset:
        def get_info(self):return {'symbol':'COHR','forwardPE':20,'financialCurrency':'USD'}
        def history(self,**kwargs):return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda s:Asset())
    m,end=parse_facts(full_facts())
    monkeypatch.setattr('data.load_sec',lambda s:('Coherent Corp.',m,end))
    stock=load_stock('COHR')
    assert evaluate_resilience(stock.resilience_inputs)[2]==90
    assert stress_24m(stock.resilience_inputs)['status']=='covered'
    assert stock.resilience_period=='2025-06-30'
    assert stock.resilience_currency=='USD'
    assert stock.resilience_inputs['ai_capex_exposure'] is None or 'ai_capex_exposure' not in stock.resilience_inputs
