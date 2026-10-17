"""Operator import of a real licensed price file; no demo rows or invented dates."""
import csv
import math
from datetime import datetime,timezone
from pathlib import Path
from screener import Stock
from market_store import parsed
from discovery_cache import unpack


def import_prices(store,path,allowed_symbols):
    allowed=set(allowed_symbols);accepted=0;rejected=0;seen=set()
    source='Operator price CSV: '+Path(path).name
    if Path(path).stat().st_size>100*1024*1024:raise ValueError('Price file too large')
    catalog=store.catalog()
    with open(path,encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        if not {'symbol','price','price_asof','currency'}.issubset(reader.fieldnames or []):raise ValueError('Expected symbol,price,price_asof,currency columns')
        for row in reader:
            symbol=row['symbol'];fund,meta=catalog.get(('fundamentals',symbol),(None,{}))
            stamp=parsed(row['price_asof'])
            try:price=float(row['price'])
            except (TypeError,ValueError):price=None
            if symbol in seen or symbol not in allowed or not fund or not fund.identity_verified or not fund.currency or row['currency']!=fund.currency or price is None or not math.isfinite(price) or price<=0 or stamp is None or not -3600<=(datetime.now(timezone.utc)-stamp).total_seconds()<=7*86400:
                rejected+=1;continue
            seen.add(symbol)
            quote=Stock(symbol,currency=row['currency'],metrics={'price':price},profile={'price_asof':row['price_asof']},source=source)
            if store.save_prices(quote):accepted+=1
            else:rejected+=1
    return {'accepted':accepted,'rejected':rejected,'source':source,'technical_indicators':'N/A without historical OHLCV','independent_vendor_validation':False}
