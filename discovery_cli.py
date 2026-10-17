"""Real discovery run, no fixtures. python discovery_cli.py --limit 10"""
import argparse
import json
import os
from discovery import universe, scan, top20
from discovery_cache import Cache


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=10);parser.add_argument('--output',default='discovery-result.json');parser.add_argument('--offset',type=int,default=0)
    args=parser.parse_args()
    cache=Cache(os.getenv('DISCOVERY_CACHE_PATH','.cache/discovery.sqlite3'))
    listing,hit=universe(cache)
    result=scan(listing['listings'],cache,args.limit,offset=args.offset,progress=lambda n,total:print(f'{n}/{total}',flush=True))
    result['universe_count']=len(listing['listings']);result['universe_fetched_at']=listing['fetched_at'];result['universe_file_times']=listing['file_times']
    result['top20']=top20(result['rows'])
    with open(args.output,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','top20')},ensure_ascii=False))
    print('TOP rows:',len(result['top20']))

if __name__=='__main__':main()
