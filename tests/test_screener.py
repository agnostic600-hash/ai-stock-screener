import pandas as pd
import pytest
from screener import Stock, evaluate, number, tickers, scenario
from data import compute_roic, load_stock


def test_missing_data_has_no_score():
    dimensions, total, coverage = evaluate(Stock('NONE'))
    assert total is None and coverage == 0
    assert all(v is None for v in dimensions.values())


def test_score_and_negative_equity():
    s = Stock('GOOD', metrics=dict(pe=10, forward_pe=10, peg=.5, gross_margin=.6, operating_margin=.3, roic=.25, debt_equity=0, current_ratio=2, fcf=1, revenue_growth=.3, earnings_growth=.3))
    assert evaluate(s)[1:] == (100, 100)
    s.metrics['debt_equity'] = -1
    assert evaluate(s)[2] == 91
    s.metrics.update(pe=-10, forward_pe=0, peg=None)
    assert evaluate(s)[1] is None


def test_partial_score_threshold():
    s = Stock('PART', metrics=dict(pe=20, gross_margin=.3, current_ratio=1, revenue_growth=.1))
    assert evaluate(s)[1] is None


@pytest.mark.parametrize('value', [None, 'None', 'NaN', float('inf'), '-Infinity', ''])
def test_invalid_numbers(value):
    assert number(value) is None


def test_ticker_validation():
    assert tickers(' aapl, SAP.DE; asml.as AAPL ') == ['AAPL', 'SAP.DE', 'ASML.AS']
    with pytest.raises(ValueError):
        tickers('../secret')
    with pytest.raises(ValueError):
        tickers(','.join(f'A{i}' for i in range(21)))


def test_scenario():
    s = Stock('X', metrics={'eps':2, 'earnings_growth':.1})
    assert scenario(s, 3) == pytest.approx(2.662)
    s.metrics['eps'] = -1
    assert scenario(s, 5) is None


def test_roic_requires_complete_aligned_annual_statements():
    dates = pd.to_datetime(['2025-12-31', '2024-12-31'])
    income = pd.DataFrame({dates[0]:[100,20,100]}, index=['Operating Income','Tax Provision','Pretax Income'])
    balance = pd.DataFrame({d:[100,400,100] for d in dates}, index=['Total Debt','Stockholders Equity','Cash And Cash Equivalents'])
    assert compute_roic(income, balance)[0] == pytest.approx(.2)
    assert compute_roic(income, balance.drop(index='Total Debt'))[0] is None
    assert compute_roic(income, balance[[dates[0]]])[0] is None
    income.loc['Pretax Income'] = -1
    assert compute_roic(income, balance)[0] is None


def test_provider_error_is_safe(monkeypatch):
    class Broken:
        def __init__(self, symbol): pass
        def get_info(self): raise RuntimeError('private detail')
        def history(self, **kwargs): raise RuntimeError('private detail')
    monkeypatch.setattr('data.yf.Ticker', Broken)
    stock = load_stock('BAD')
    assert stock.metrics == {} and len(stock.warnings) >= 3
    assert 'private detail' not in str(stock)


def test_alpha_vantage_limit_and_key_not_leaked(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'Information':'API limit'}
    monkeypatch.setattr('data.requests.get', lambda *args, **kwargs: Response())
    monkeypatch.setattr('data.yf.Ticker', lambda symbol: type('T', (), {'history':lambda self, **kw:pd.DataFrame()})())
    stock = load_stock('AAPL', 'test-secret', 'Alpha Vantage')
    assert stock.warnings and evaluate(stock)[1] is None
    assert 'test-secret' not in str(stock)


def test_yahoo_mapping(monkeypatch):
    class Asset:
        income_stmt = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        def get_info(self):
            return {'longName':'Test', 'currentPrice':12, 'debtToEquity':150, 'financialCurrency':'EUR', 'revenueGrowth':0}
        def history(self, **kwargs): return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker', lambda symbol: Asset())
    s = load_stock('TEST.DE')
    assert s.metrics['debt_equity'] == 1.5
    assert s.metrics['revenue_growth'] == 0
    assert s.metrics['pe'] is None
