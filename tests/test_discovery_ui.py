from pathlib import Path
from streamlit.testing.v1 import AppTest
from discovery_cache import Cache
from discovery import scan
from test_discovery import stock, listing

ROOT=Path(__file__).resolve().parents[1]

def test_discovery_view_does_not_load_network_on_render(monkeypatch):
    monkeypatch.setattr('discovery_ui.universe',lambda cache: (_ for _ in ()).throw(AssertionError('network not requested')))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    app.radio[0].set_value('Market Discovery').run()
    assert not app.exception
    assert 'Market Discovery' in app.header[0].value
    assert not app.dataframe


def test_discovery_batch_ui_and_single_stock_mode_preserved(monkeypatch,tmp_path):
    cache=Cache(tmp_path/'cache.sqlite')
    monkeypatch.setattr('discovery_ui.Cache',lambda path:cache)
    monkeypatch.setattr('discovery_ui.universe',lambda c:({'listings':[listing('AAA'),listing('BBB')],'fetched_at':'2026-10-17T00:00:00+00:00','file_times':{'test':'fixture'}},False))
    monkeypatch.setattr('discovery_ui.scan',lambda listings,cache,limit,excluded,progress,offset=0:scan(listings,cache,limit,excluded,loader=stock,progress=progress,min_interval=0,offset=offset))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    app.radio[0].set_value('Market Discovery').run()
    app.button(key='discovery_run').click().run()
    assert not app.exception
    assert [m.value for m in app.metric]==['2','2','2','2']
    assert len(app.dataframe[0].value)==2
    app.checkbox(key='discovery_swing').check().run()
    assert not app.exception
    assert any('zatiaľ nie je akcia' in item.value for item in app.info)
    app.radio[0].set_value('Analýza jednotlivých akcií').run()
    assert not app.exception
    assert app.text_area[0].value=='AAPL, MSFT, ASML.AS, SAP.DE'
