import pytest
from filing_events import parse_index,check_filings
from discovery_cache import Cache
from market_store import MarketStore
from providers import DataError


def test_index_requires_schema_and_cik_path_identity():
    text='CIK|Company Name|Form Type|Date Filed|Filename\n1234|Issuer|10-Q|2026-10-16|edgar/data/1234/filing.txt\n4321|Other|10-Q|2026-10-16|edgar/data/1234/wrong.txt'
    assert list(parse_index(text))==['1234']
    with pytest.raises(DataError):parse_index('<html>blocked</html>')


def test_index_outage_is_not_reported_as_successful_empty_feed(tmp_path):
    import requests
    store=MarketStore(Cache(tmp_path/'db'))
    def fail(*args,**kwargs):raise requests.Timeout('private URL')
    with pytest.raises(DataError):check_filings(store,get=fail)


def test_sec_actual_file_name_header_and_compact_date_contract():
    # Format observed in actual SEC master.20261016.idx; values here remain synthetic.
    text='CIK|Company Name|Form Type|Date Filed|File Name\n1234|Issuer|10-Q|20261016|edgar/data/1234/report.txt'
    assert parse_index(text)['1234']['published_at']=='2026-10-16'
