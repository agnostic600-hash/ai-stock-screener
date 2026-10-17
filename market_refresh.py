"""Independent refresh queues: fundamentals share their original daily budget; prices do not reload SEC/info."""
import time
from datetime import datetime,timezone,timedelta
from data import load_prices
from market_store import parsed,utcnow
import discovery


def refresh_prices(store,listings,limit=10,loader=load_prices,min_interval=3):
    done=0;hits=0;attempted=0;errors=[];stopped=None
    catalog=store.catalog()
    floor=datetime.min.replace(tzinfo=timezone.utc)
    listings=sorted(listings,key=lambda r:(bool(catalog.get(('prices',r['symbol']),(None,{}))[0] and catalog[('prices',r['symbol'])][0].profile.get('technical_computed')),parsed(catalog.get(('prices',r['symbol']),(None,{}))[1].get('retrieved_at')) or floor))
    for listing in listings:
        symbol=listing['symbol'];old,meta=catalog.get(('prices',symbol),(None,{}));fund,_=catalog.get(('fundamentals',symbol),(None,{}))
        downloaded=parsed(meta.get('technical_retrieved_at') or meta.get('retrieved_at'))
        if old and old.profile.get('technical_computed') and downloaded and utcnow()-downloaded<timedelta(hours=12):hits+=1;continue
        if attempted>=limit:break
        with discovery._GATE:
            key='price-budget:'+datetime.now(timezone.utc).date().isoformat();used=store.cache.get(key) or 0
            if used>=100 or store.cache.get('cooldown:v1'):stopped='Cenový denný rozpočet alebo prestávka poskytovateľa.';break
            time.sleep(max(0,min_interval-(time.monotonic()-discovery._LAST_START)));discovery._LAST_START=time.monotonic()
            store.cache.put(key,used+1,48*3600);attempted+=1
            try:
                price=loader(symbol)
                if price.ticker!=symbol:raise ValueError('Mismatched symbol')
                if fund:price.currency=fund.currency
                if not store.save_prices(price):raise ValueError('Invalid/older prices')
                split=parsed(price.profile.get('last_split_at'))
                if fund and split and split>parsed(fund.fetched):
                    _,fm=store.get('fundamentals',symbol);fm['corporate_action_pending']=True;store.save('fundamentals',fund,fm)
                done+=1
            except Exception as exc:
                from providers import error_reason
                reason=error_reason(exc);errors.append(symbol+': '+reason);store.error('prices',symbol,reason)
                if '429' in reason or '401/403' in reason:
                    store.cache.put('cooldown:v1',{'reason':'price API rejected'},900);stopped=reason;break
    return {'updated':done,'cache_hits':hits,'attempted':attempted,'errors':errors,'stopped':stopped}


def due_fundamentals(store,listings):
    from market_store import fundamental_status
    catalog=store.catalog()
    return [r for r in listings if ('fundamentals',r['symbol']) in catalog and not fundamental_status(catalog[('fundamentals',r['symbol'])][1])[0] and (not parsed(catalog[('fundamentals',r['symbol'])][1].get('last_attempt_at')) or utcnow()-parsed(catalog[('fundamentals',r['symbol'])][1]['last_attempt_at'])>timedelta(minutes=15))]
