from pathlib import Path
from streamlit.testing.v1 import AppTest
from discovery_cache import Cache
from discovery import scan
from discovery_campaign import scan_campaign
from test_discovery import stock, listing

ROOT=Path(__file__).resolve().parents[1]

def test_discovery_view_does_not_load_network_on_render(monkeypatch,tmp_path):
    monkeypatch.setattr('discovery_ui.Cache',lambda path:Cache(tmp_path/'cache.sqlite'))
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
    monkeypatch.setattr('discovery_ui.scan_campaign',lambda campaigns,ident,limit,progress:scan_campaign(campaigns,ident,limit,progress,scanner=lambda listings,cache,limit:scan(listings,cache,limit,loader=stock,min_interval=0)))
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


def test_resume_after_new_apptest_session_and_denominator_caption(monkeypatch,tmp_path):
    cache=Cache(tmp_path/'cache.sqlite')
    from discovery_campaign import Campaigns
    from discovery import analyze
    campaigns=Campaigns(cache)
    listings=[listing('AAA'),listing('BBB')]
    ident=campaigns.start({'listings':listings,'fetched_at':'fixture','file_times':{}})
    claim=campaigns.claim(ident)
    campaigns.finish(ident,claim,analyze(stock(claim['symbol']),claim['listing']))
    monkeypatch.setattr('discovery_ui.Cache',lambda path:cache)
    monkeypatch.setattr('discovery_ui.universe',lambda c:(_ for _ in ()).throw(AssertionError('must resume snapshot')))
    monkeypatch.setattr('discovery_ui.scan_campaign',lambda campaigns,ident,limit,progress:scan_campaign(campaigns,ident,limit,progress,scanner=lambda listings,cache,limit:scan(listings,cache,limit,loader=stock,min_interval=0)))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    app.radio[0].set_value('Market Discovery').run()
    assert [m.value for m in app.metric]==['2','1','1','1']
    assert any('TOP 1 z 1 finančných analýz (1 pokusov)' in h.value for h in app.subheader)
    app.button(key='discovery_run').click().run()
    assert not app.exception
    assert [m.value for m in app.metric]==['2','2','2','2']
