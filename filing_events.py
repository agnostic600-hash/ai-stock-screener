"""One SEC daily master index can signal new 10-K/10-Q filings for many CIKs."""
from datetime import datetime,timedelta,timezone,date
import requests
from secdata import headers
from providers import DataError,error_reason


def parse_index(text):
    if not any('CIK|Company Name|Form Type|Date Filed|'+name in text for name in ('Filename','File Name')):raise DataError('SEC index nemá očakávanú schému.')
    events={}
    for line in text.splitlines():
        parts=line.split('|')
        if len(parts)!=5:continue
        cik,_,form,filed,path=[v.strip() for v in parts]
        if not cik.isdigit() or form not in ('10-K','10-Q','10-K/A','10-Q/A'):continue
        try:filed=(datetime.strptime(filed,'%Y%m%d').date().isoformat() if len(filed)==8 else date.fromisoformat(filed).isoformat())
        except ValueError:continue
        if not path.startswith('edgar/data/'+str(int(cik))+'/'):continue
        key=str(int(cik));event={'published_at':filed,'key':path,'form':form}
        if key not in events or (filed,path)>(events[key]['published_at'],events[key]['key']):events[key]=event
    return events


def check_filings(store,day=None,get=requests.get):
    day=day or (datetime.now(timezone.utc).date()-timedelta(days=1))
    while day.weekday()>4:day-=timedelta(days=1)
    key='filing-index:'+day.isoformat()
    error=store.cache.get(key+':error')
    if error:raise DataError(error)
    events=store.cache.get(key)
    if events is None:
        quarter=(day.month-1)//3+1
        url=f'https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/master.{day:%Y%m%d}.idx'
        try:
            response=get(url,headers=headers(),timeout=20);response.raise_for_status();events=parse_index(response.text)
        except DataError as exc:
            store.cache.put(key+':error',str(exc),3600);raise
        except requests.RequestException as exc:
            reason='SEC index: '+error_reason(exc);store.cache.put(key+':error',reason,3600);raise DataError(reason) from None
        store.cache.put(key,events,86400)
    changed=store.observe_filings(events)
    return {'date':day.isoformat(),'filings':len(events),'invalidated':changed}
