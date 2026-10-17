"""Real durable discovery run. Repeated invocations resume the same universe pass."""
import argparse
import json
import os
from discovery import universe, top20
from discovery_cache import Cache
from discovery_campaign import Campaigns,scan_campaign
from discovery_audit import audit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=10);parser.add_argument('--output',default='discovery-result.json');parser.add_argument('--new-pass',action='store_true')
    args=parser.parse_args()
    cache=Cache(os.getenv('DISCOVERY_CACHE_PATH','.cache/discovery.sqlite3'))
    campaigns=Campaigns(cache);current=campaigns.current()
    if current is None or args.new_pass:
        listing,hit=universe(cache);campaigns.start(listing,new=args.new_pass);current=campaigns.current()
    batch=scan_campaign(campaigns,current['id'],args.limit,progress=lambda n,total:print(f'{n}/{total}',flush=True))
    rows=campaigns.rows(current['id']);listing=current['universe'];report=audit(rows,listing['listings'])
    result={'campaign_id':current['id'],'progress':campaigns.counts(current['id']),'last_batch':{k:v for k,v in batch.items() if k!='rows'},'audit':report,'rows':rows,'top20':top20(rows),'universe_fetched_at':listing['fetched_at'],'universe_file_times':listing['file_times']}
    with open(args.output,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','top20','audit')},ensure_ascii=False))
    print(f"TOP {len(result['top20'])} from {report['analyzed']} financial analyses / {report['attempted']} attempts / {report['ranked_at_fetch']} rankable at fetch")

if __name__=='__main__':main()
