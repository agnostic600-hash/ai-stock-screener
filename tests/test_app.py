from pathlib import Path
from streamlit.testing.v1 import AppTest
import pandas as pd
from screener import Stock


def test_initial_screen():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
    assert not app.exception
    assert app.title[0].value == '📈 AI Stock Screener'


def test_results_filters_and_detail():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
    app.session_state['stocks'] = [Stock('TEST', name='Testovacia firma', metrics=dict(pe=15, forward_pe=12, peg=1, gross_margin=.5, operating_margin=.2, roic=.15, debt_equity=.5, current_ratio=1.5, fcf=100, revenue_growth=.1, earnings_growth=.1), history=pd.Series([10,11], index=pd.date_range('2025-01-01', periods=2)), currency='EUR', financial_currency='EUR')]
    app.run()
    assert not app.exception
    assert len(app.dataframe) >= 3
    app.slider[0].set_value(100).run()
    assert not app.exception
    assert app.dataframe[0].value.empty


def test_all_missing_results_do_not_crash():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
    app.session_state['stocks'] = [Stock('MISSING')]
    app.run()
    assert not app.exception


def test_analyze_button_loads_provider(monkeypatch):
    calls = []
    def fake_load(symbol, api_key='', provider='Yahoo Finance'):
        calls.append((symbol, provider))
        return Stock(symbol, name='Overená testovacia firma')
    monkeypatch.setattr('data.load_stock', fake_load)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
    app.text_area[0].set_value('UNIT.DE')
    app.button[0].click().run()
    assert not app.exception
    assert calls == [('UNIT.DE', 'Yahoo Finance')]
    assert app.dataframe[0].value.iloc[0]['Ticker'] == 'UNIT.DE'


def test_invalid_ticker_shows_error():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
    app.text_area[0].set_value('../invalid')
    app.button[0].click().run()
    assert not app.exception
    assert app.error


def test_fallback_results_are_visible_in_ui(monkeypatch):
    class Asset:
        def get_info(self): raise type('YFRateLimitError',(Exception,),{})()
        def history(self,**kw): return pd.DataFrame()
    monkeypatch.setattr('data.yf.Ticker',lambda symbol:Asset())
    monkeypatch.setattr('data.load_sec',lambda symbol:('Testovacia firma',{'eps':2},'2025-06-30'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
    app.text_area[0].set_value('FALLBACK')
    app.button[0].click().run()
    assert not app.exception
    assert app.dataframe[0].value.iloc[0]['EPS']==2
    assert any('SEC' in w.value for w in app.warning)
    assert any('429' in w.value for w in app.warning)
    assert any('2025-06-30' in str(table.value) for table in app.dataframe)


def test_resilience_panel_missing_data_is_explicit():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
    app.session_state['stocks'] = [Stock('COHR')]
    app.run()
    assert not app.exception
    assert app.metric[0].value == 'N/A'
    assert app.metric[1].value == '0 %'
    assert any('Financovanie 24 mesiacov: N/A' in item.value for item in app.info)


def test_resilience_panel_complete_inputs_and_shortfall():
    # Synthetic UI fixture; not a live COHR statement.
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
    app.session_state['stocks'] = [Stock('UNIT', metrics=dict(
        fcf_margin=.2, net_debt_ebitda=0, revenue_growth=.2, operating_margin=.2,
        forward_pe=5, share_dilution=0, ai_capex_exposure=0,
        annual_revenue=1000, annual_fcf=50, annual_gross_margin=.5, cash=120, debt_due_24m=50))]
    app.run()
    assert not app.exception
    assert app.metric[0].value == '100.0 / 100'
    assert app.metric[1].value == '100 %'
    assert any('Deficit financovania' in item.value for item in app.markdown)
    assert len(app.json) == 1
