"""Real durable discovery run. Repeated invocations resume the same universe pass."""
import argparse
import json
import os
from discovery import universe, top20
from discovery_cache import Cache
from discovery_campaign import Campaigns,scan_campaign
from discovery_audit import audit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=10);parser.add_argument('--output',default='discovery-result.json');parser.add_argument('--new-pass',action='store_true');parser.add_argument('--prices-only',action='store_true');parser.add_argument('--refresh-fundamentals',action='store_true');parser.add_argument('--price-file');parser.add_argument('--check-filings',action='store_true')
    args=parser.parse_args()
    cache=Cache(os.getenv('DISCOVERY_CACHE_PATH','.cache/discovery.sqlite3'))
    campaigns=Campaigns(cache);current=campaigns.current()
    if current is None or args.new_pass:
        listing,hit=universe(cache);campaigns.start(listing,new=args.new_pass);current=campaigns.current()
    from market_store import MarketStore
    from market_refresh import refresh_prices,due_fundamentals
    from discovery import scan
    store=MarketStore(cache)
    if args.check_filings:
        from filing_events import check_filings
        print(check_filings(store))
    if args.price_file:
        from bulk_prices import import_prices
        print(import_prices(store,args.price_file,[r['symbol'] for r in current['universe']['listings']]))
    covered={r['symbol'] for r in campaigns.rows(current['id'])}
    covered_listings=[r for r in current['universe']['listings'] if r['symbol'] in covered]
    if args.prices_only:
        status=refresh_prices(store,covered_listings,limit=args.limit)
        batch={'attempted':status['attempted'],'prices':status}
    elif args.refresh_fundamentals:
        due=due_fundamentals(store,covered_listings)
        batch=scan(due,cache,args.limit) if due else {'attempted':0}
    elif args.price_file:
        batch={'attempted':0}
    else:
        batch=scan_campaign(campaigns,current['id'],args.limit,progress=lambda n,total:print(f'{n}/{total}',flush=True))
    rows=campaigns.rows(current['id']);listing=current['universe'];report=audit(rows,listing['listings'])
    result={'campaign_id':current['id'],'progress':campaigns.counts(current['id']),'last_batch':{k:v for k,v in batch.items() if k!='rows'},'audit':report,'rows':rows,'top20':top20(rows),'universe_fetched_at':listing['fetched_at'],'universe_file_times':listing['file_times']}
    with open(args.output,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','top20','audit')},ensure_ascii=False))
    print(f"TOP {len(result['top20'])} from {report['analyzed']} financial analyses / {report['attempted']} attempts / {report['covered_fundamentals']} valid fundamental snapshots / {report['comparable']} currently comparable")

if __name__=='__main__':main()
