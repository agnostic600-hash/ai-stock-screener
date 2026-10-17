"""Permanent fundamental and daily-price snapshots. No TTL deletion of good data."""
import json
from datetime import datetime,timezone,timedelta
from discovery_cache import pack,unpack
from screener import Stock,number


def utcnow():return datetime.now(timezone.utc)

def parsed(value):
    try:
        dt=datetime.fromisoformat(value)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError,TypeError):return None


def epoch(value):
    try:return datetime.fromtimestamp(float(value),timezone.utc)
    except (ValueError,TypeError,OverflowError,OSError):return None


def fundamental_status(meta,now=None):
    now=now or utcnow();downloaded=parsed(meta.get('retrieved_at'));period=parsed(meta.get('period_end'))
    if not downloaded or not period:return False,'Chýbajúci dátum výkazu/stiahnutia'
    if not meta.get('identity_verified'):return False,'Neoverená identita'
    if period>downloaded:return False,'Obdobie výkazu je po dátume stiahnutia'
    if period>now or (now-period).days>550:return False,'Nepoužiteľné obdobie výkazu (>550 dní alebo budúce)'
    if meta.get('corporate_action_pending'):return False,'Zistený split po stiahnutí EPS; nutná obnova'
    if meta.get('report_pending'):return False,'Zistené novšie podanie SEC; obnova čaká'
    publication=parsed(meta.get('published_at'))
    if publication and (publication>now+timedelta(days=1) or publication>downloaded+timedelta(days=1)):return False,'Budúci dátum zverejnenia'
    expiry=parsed(meta.get('valid_until'))
    if not expiry or now>=expiry:return False,'Uplynula platnosť fundamentov / termín výsledkov'
    if downloaded>now:return False,'Budúci dátum stiahnutia'
    return True,'Platné podľa politiky; nie garancia oneskorenia poskytovateľa'


class MarketStore:
    def __init__(self,cache):
        self.cache=cache
        with cache.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS market_snapshots (kind TEXT NOT NULL,symbol TEXT NOT NULL,payload TEXT NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(kind,symbol))')
    def get(self,kind,symbol):
        with self.cache.connect() as db:row=db.execute('SELECT payload,metadata FROM market_snapshots WHERE kind=? AND symbol=?',(kind,symbol)).fetchone()
        return (unpack(json.loads(row[0])),json.loads(row[1])) if row else (None,{})
    def catalog(self):
        with self.cache.connect() as db:rows=db.execute("SELECT kind,symbol,payload,metadata FROM market_snapshots WHERE kind IN ('fundamentals','prices')").fetchall()
        return {(kind,symbol):(unpack(json.loads(payload)),json.loads(meta)) for kind,symbol,payload,meta in rows}
    def save(self,kind,stock,metadata):
        with self.cache.connect() as db:db.execute('INSERT INTO market_snapshots(kind,symbol,payload,metadata) VALUES (?,?,?,?) ON CONFLICT(kind,symbol) DO UPDATE SET payload=excluded.payload,metadata=excluded.metadata',(kind,stock.ticker,json.dumps(pack(stock),allow_nan=False),json.dumps(metadata,allow_nan=False)))
    def save_fundamentals(self,stock,now=None):
        now=now or utcnow()
        if not stock.identity_verified or not any(v is not None for v in stock.resilience_inputs.values()):return False
        period=parsed(stock.resilience_period);downloaded=parsed(stock.fetched)
        if not period or not downloaded or period>now or period>downloaded or downloaded>now:return False
        old,oldmeta=self.get('fundamentals',stock.ticker)
        if old and old.resilience_period!='N/A' and (stock.resilience_period=='N/A' or stock.resilience_period<old.resilience_period):return False
        expiry=(parsed(stock.fetched) or now)+timedelta(days=90)
        expected=parsed(stock.next_report_at)
        if expected and expected>now:expiry=min(expiry,expected+timedelta(days=2))
        meta={'period_end':stock.resilience_period,'published_at':stock.financial_published_at or None,'publication_kind':'SEC filing date; not earnings-release timestamp' if stock.financial_published_at else 'N/A',
              'retrieved_at':stock.fetched,'valid_until':expiry.isoformat(),'expected_report_at':stock.next_report_at or None,'identity_verified':stock.identity_verified,'sec_cik':stock.sec_cik or None,
              'last_report_checked_at':oldmeta.get('last_report_checked_at'),'latest_report_at':oldmeta.get('latest_report_at'),'latest_report_key':oldmeta.get('latest_report_key'),'report_pending':False,'last_error':None}
        # Strip daily bars from the fundamental record.
        snapshot=unpack(pack(stock));snapshot.history=None;snapshot.volume_history=None
        self.save('fundamentals',snapshot,meta)
        if stock.history is not None:self.save_prices(stock)
        # Reuse an actual quote already returned by get_info, with its own provider time.
        price=number(stock.metrics.get('price'));stamp=number(stock.profile.get('regularMarketTime'))
        if price is not None and price>0 and epoch(stamp) is not None:
            quote=Stock(stock.ticker,currency=stock.currency,fetched=stock.fetched,metrics={'price':price},profile={'price_asof':epoch(stamp).isoformat()})
            existing,_=self.get('prices',stock.ticker)
            if existing is None:self.save_prices(quote)
        return True
    def save_prices(self,stock):
        history=stock.history is not None and not stock.history.dropna().empty
        if history:
            h=stock.history.dropna().sort_index();asof=h.index[-1].isoformat();price=number(h.iloc[-1])
        else:asof=stock.profile.get('price_asof');price=number(stock.metrics.get('price'))
        if price is None or price<=0 or not parsed(asof) or parsed(asof)>utcnow()+timedelta(hours=1):return False
        asof=parsed(asof).isoformat()
        old,meta=self.get('prices',stock.ticker)
        from discovery import swing_signal
        signal,_=swing_signal(stock.history,stock.volume_history)
        if old and parsed(meta.get('price_asof')) and parsed(asof)<parsed(meta['price_asof']):
            if not history:return False
            # A daily bar's timestamp is the bar date, not the later trade timestamp.
            # Preserve the newer quote while updating independently dated technicals.
            previous=parsed(old.profile.get('technical_asof'))
            if previous and parsed(asof)<previous:return False
            old.profile.update({'technical_computed':True,'swing_signal':signal if stock.currency=='USD' else None,'technical_asof':asof})
            meta.update({'technical_asof':asof,'technical_retrieved_at':stock.fetched,'last_error':None})
            self.save('prices',old,meta);return True
        profile={'price_asof':asof,'swing_signal':signal if stock.currency=='USD' else None,'technical_computed':history,'technical_asof':asof if history else None}
        price_snapshot=Stock(stock.ticker,currency=stock.currency,fetched=stock.fetched,metrics={'price':price},profile=profile,source=stock.source)
        self.save('prices',price_snapshot,{'price_asof':asof,'retrieved_at':stock.fetched,'source':stock.source,'technical_asof':asof if history else None,'technical_retrieved_at':stock.fetched if history else None,'last_split_at':stock.profile.get('last_split_at'),'last_error':None})
        return True
    def error(self,kind,symbol,message):
        stock,meta=self.get(kind,symbol)
        if stock:
            meta['last_error']=message;meta['last_attempt_at']=utcnow().isoformat();self.save(kind,stock,meta)
    def observe_filings(self,events,checked_at=None):
        checked_at=checked_at or utcnow().isoformat();updates=0
        with self.cache.connect() as db:rows=db.execute("SELECT symbol,payload,metadata FROM market_snapshots WHERE kind='fundamentals'").fetchall()
        writes=[]
        for symbol,payload,text in rows:
            meta=json.loads(text);cik=str(meta.get('sec_cik') or '').lstrip('0');event=events.get(cik)
            if not cik:continue
            meta['last_report_checked_at']=checked_at
            if event and (not meta.get('latest_report_at') or event['published_at']>=meta['latest_report_at']):
                downloaded=parsed(meta.get('retrieved_at'));eventdate=parsed(event['published_at'])
                if event['key']!=meta.get('latest_report_key') and eventdate and downloaded and eventdate.date()>=downloaded.date():meta['report_pending']=True;updates+=1
                meta['latest_report_key']=event['key'];meta['latest_report_at']=event['published_at']
            writes.append((json.dumps(meta),symbol))
        with self.cache.connect() as db:db.executemany("UPDATE market_snapshots SET metadata=? WHERE kind='fundamentals' AND symbol=?",writes)
        return updates
