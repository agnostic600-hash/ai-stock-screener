"""Actual PostgreSQL integration, enabled by CI service URL; not a mocked database."""
import os
import uuid
import pytest
from discovery_cache import Cache
from discovery_campaign import Campaigns
from market_store import MarketStore
from test_discovery import stock,listing


@pytest.fixture
def pg(tmp_path):
    url=os.getenv('TEST_DATABASE_URL')
    if not url:pytest.skip('PostgreSQL service not configured in this environment')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    schema='test_'+uuid.uuid4().hex
    with psycopg.connect(url,autocommit=True) as connection:connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    dsn=make_conninfo(url,options='-c search_path='+schema)
    yield Cache(tmp_path/'not-used.sqlite',database_url=dsn)
    with psycopg.connect(url,autocommit=True) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_real_pg_cache_and_snapshots_survive_new_client(pg):
    assert pg.storage_kind=='external-postgresql'
    pg.put('test',{'v':2},10,now=100)
    assert pg.get('test',now=109)=={'v':2}
    assert pg.get('test',now=110) is None
    MarketStore(pg).save_fundamentals(stock())
    reconnect=Cache(pg.path,database_url=pg.database_url)
    assert MarketStore(reconnect).get('fundamentals','UNIT')[0].identity_verified
    assert not pg.path.exists()


def test_real_pg_claims_upserts_and_restart(pg):
    campaigns=Campaigns(pg);ident=campaigns.start({'listings':[listing('AAA'),listing('BBB')],'fetched_at':'fixture','file_times':{}})
    claim=campaigns.claim(ident);another=Campaigns(Cache(pg.path,database_url=pg.database_url))
    b=another.claim(ident)
    assert b['symbol']!=claim['symbol']
    campaigns.finish(ident,claim,{'symbol':claim['symbol']})
    assert another.counts(ident)['done']==1
    another.release(ident,b)
    assert another.counts(ident)['pending']==1


def test_real_pg_migration_and_next_campaign_sequence(pg,tmp_path):
    from migrate_storage import migrate
    source=Cache(tmp_path/'source.sqlite');campaigns=Campaigns(source)
    ident=campaigns.start({'listings':[listing()],'fetched_at':'fixture','file_times':{}})
    claim=campaigns.claim(ident);campaigns.finish(ident,claim,{'symbol':claim['symbol']})
    MarketStore(source).save_fundamentals(stock())
    migrate(source.path,pg,apply=True)
    restored=Campaigns(pg)
    assert restored.counts(ident)['done']==1
    new=restored.start({'listings':[listing()],'fetched_at':'fixture','file_times':{}},new=True)
    assert new>ident
