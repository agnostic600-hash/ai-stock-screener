"""One-time SQLite -> configured PostgreSQL migration into an EMPTY target.
Stop all discovery/refresh workers first. No DSN on command line or in output.
"""
import argparse
import os
import sqlite3
from pathlib import Path
from discovery_cache import Cache
from discovery_campaign import Campaigns
from market_store import MarketStore

TABLES=('cache','campaigns','campaign_items','market_snapshots')


def migrate(source,target,apply=False):
    Campaigns(target);MarketStore(target)
    src=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True)
    src.execute('BEGIN')
    contents={}
    try:
        for table in TABLES:
            columns=[row[1] for row in src.execute('PRAGMA table_info('+table+')').fetchall()]
            expected={'cache':['key','value','expires'],'campaigns':['id','created','universe_json'],'campaign_items':['campaign','ordinal','symbol','listing','state','owner','lease','result'],'market_snapshots':['kind','symbol','payload','metadata']}
            if columns and columns!=expected[table]:raise ValueError('Unsupported source schema: '+table)
            if columns:contents[table]=(columns,src.execute('SELECT * FROM '+table).fetchall())
    finally:src.close()
    report={table:len(rows) for table,(_,rows) in contents.items()}
    if not apply:return report
    with target.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if any(db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in TABLES):raise ValueError('Target must be empty; migration will not overwrite existing data.')
        for table,(columns,rows) in contents.items():
            if table=='campaign_items':
                changed=[]
                for row in rows:
                    record=dict(zip(columns,row))
                    if record.get('state')=='running':record.update(state='pending',owner=None,lease=None)
                    changed.append(tuple(record[k] for k in columns))
                rows=changed
            sql='INSERT INTO '+table+'('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')'
            db.executemany(sql,rows)
        if target.storage_kind=='external-postgresql':db.execute("SELECT setval(pg_get_serial_sequence('campaigns','id'),GREATEST(COALESCE(MAX(id),1),1),COUNT(*)>0) FROM campaigns")
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source_sqlite');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    url=os.getenv('DISCOVERY_DATABASE_URL')
    if not url:raise ValueError('Set target DISCOVERY_DATABASE_URL as a server environment secret.')
    target=Cache('.unused-local-target',database_url=url)
    print(migrate(os.path.abspath(args.source_sqlite),target,args.apply))

if __name__=='__main__':main()
