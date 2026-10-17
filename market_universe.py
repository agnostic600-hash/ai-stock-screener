"""NASDAQ Trader directories; no fixed pick list. NYSE is exchange code N only."""
import csv
import io
import re
from datetime import datetime, timezone
import requests
from providers import DataError, error_reason

BASE='https://www.nasdaqtrader.com/dynamic/SymDir/'
EXCLUDED=re.compile(r'\b(preferred|preference|warrants?|rights?|units?|notes?|debentures?|bonds?|fund|etn)\b',re.I)


def parse_directory(text, source):
    reader=csv.DictReader(io.StringIO(text),delimiter='|')
    symbol_key='Symbol' if source=='nasdaqlisted.txt' else 'ACT Symbol'
    required={symbol_key,'Security Name','ETF','Test Issue'}
    if source=='otherlisted.txt':required.add('Exchange')
    if not required.issubset(reader.fieldnames or []):raise DataError('Neplatná schéma NASDAQ Trader.')
    listings=[]; stamp=None
    for row in reader:
        symbol=row.get(symbol_key,'') or ''
        if symbol.startswith('File Creation Time:'):
            stamp=symbol.split(':',1)[1].strip(); continue
        if row.get('Test Issue')!='N' or row.get('ETF')!='N':continue
        if source=='otherlisted.txt' and row.get('Exchange')!='N':continue
        name=row.get('Security Name') or ''
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,19}',symbol) or EXCLUDED.search(name):continue
        if row.get('NextShares')=='Y':continue
        listings.append({'symbol':symbol.replace('.','-'),'listing_symbol':symbol,'name':name,
                         'exchange':'NASDAQ' if source=='nasdaqlisted.txt' else 'NYSE'})
    if not listings or stamp is None:raise DataError('NASDAQ Trader súbor je prázdny, neúplný alebo bez časovej päčiatky.')
    return listings,stamp


def fetch_universe(get=requests.get):
    listings=[];timestamps={}
    for source in ('nasdaqlisted.txt','otherlisted.txt'):
        try:
            response=get(BASE+source,timeout=20);response.raise_for_status()
            rows,stamp=parse_directory(response.text,source)
            listings.extend(rows);timestamps[source]=stamp
        except requests.RequestException as exc:raise DataError('NASDAQ Trader: '+error_reason(exc)) from None
    unique={row['symbol']:row for row in listings}
    return {'listings':sorted(unique.values(),key=lambda r:r['symbol']),
            'fetched_at':datetime.now(timezone.utc).isoformat(),'file_times':timestamps,
            'source':BASE,'scope':'NASDAQ + NYSE (N), ETF/test/non-common name exclusions; ADRs allowed'}
