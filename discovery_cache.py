"""JSON-only SQLite cache, reusable across UI sessions. No pickle or credentials."""
import json
import os
import math
import sqlite3
import time
from pathlib import Path
from dataclasses import asdict
import pandas as pd
from screener import Stock

class Cache:
    def __init__(self,path,database_url=None):
        self.database_url=database_url or os.getenv('DISCOVERY_DATABASE_URL')
        self.path=Path(path)
        if not self.database_url:self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)')
    def connect(self):
        if self.database_url:
            from storage_postgres import PostgresConnection
            return PostgresConnection(self.database_url)
        return sqlite3.connect(self.path,timeout=15)
    @property
    def storage_kind(self):return 'external-postgresql' if self.database_url else 'local-sqlite'
    def get(self,key,now=None):
        now=time.time() if now is None else now
        with self.connect() as db:row=db.execute('SELECT value, expires FROM cache WHERE key=?',(key,)).fetchone()
        if not row or row[1]<=now:return None
        try:return json.loads(row[0])
        except (ValueError,TypeError):return None
    def put(self,key,value,ttl,now=None):
        now=time.time() if now is None else now
        text=json.dumps(value,allow_nan=False)
        with self.connect() as db:db.execute('INSERT INTO cache(key,value,expires) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,expires=excluded.expires',(key,text,now+ttl))


def pack(stock):
    result=asdict(stock)
    for key in ('history','volume_history'):
        series=getattr(stock,key)
        result[key]=[(str(d),float(v)) for d,v in series.dropna().items() if math.isfinite(float(v))] if series is not None else None
    return result


def unpack(payload):
    payload=dict(payload)
    histories={key:payload.pop(key,None) for key in ('history','volume_history')}
    stock=Stock(**payload)
    for key,history in histories.items():
        if history:setattr(stock,key,pd.Series([v for _,v in history],index=pd.to_datetime([d for d,_ in history],utc=True),name=stock.ticker))
    return stock
