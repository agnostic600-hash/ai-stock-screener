"""Durable universe traversal, independent of expiring financial cache or UI session."""
import json
import time
import uuid
from discovery import candidates, scan, now_iso


class Campaigns:
    def __init__(self,cache):
        self.cache=cache
        with cache.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS campaigns (id INTEGER PRIMARY KEY, created TEXT NOT NULL, universe_json TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS campaign_items (campaign INTEGER NOT NULL, ordinal INTEGER NOT NULL, symbol TEXT NOT NULL, listing TEXT NOT NULL, state TEXT NOT NULL DEFAULT \'pending\', owner TEXT, lease REAL, result TEXT, PRIMARY KEY(campaign,symbol))')
    def current(self):
        with self.cache.connect() as db:row=db.execute('SELECT id,created,universe_json FROM campaigns ORDER BY id DESC LIMIT 1').fetchone()
        return {'id':row[0],'created':row[1],'universe':json.loads(row[2])} if row else None
    def start(self,universe,new=False):
        with self.cache.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id FROM campaigns ORDER BY id DESC LIMIT 1').fetchone()
            if row:
                remaining=db.execute("SELECT count(*) FROM campaign_items WHERE campaign=? AND state!='done'",(row[0],)).fetchone()[0]
                if not new:return row[0]
                if remaining:raise ValueError('Nový priechod nemožno začať, kým sa neskončí existujúci.')
            cursor=db.execute('INSERT INTO campaigns(created,universe_json) VALUES (?,?)',(now_iso(),json.dumps(universe,allow_nan=False)))
            ident=cursor.lastrowid
            ordered={r['symbol']:r for r in candidates(universe['listings'])}
            db.executemany('INSERT INTO campaign_items(campaign,ordinal,symbol,listing) VALUES (?,?,?,?)',[(ident,i,s,json.dumps(r)) for i,(s,r) in enumerate(ordered.items())])
            return ident
    def claim(self,ident,now=None,lease_seconds=900):
        now=time.time() if now is None else now
        owner=uuid.uuid4().hex
        with self.cache.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT symbol,listing FROM campaign_items WHERE campaign=? AND (state='pending' OR (state='running' AND lease<=?)) ORDER BY ordinal LIMIT 1",(ident,now)).fetchone()
            if not row:return None
            db.execute("UPDATE campaign_items SET state='running',owner=?,lease=? WHERE campaign=? AND symbol=?",(owner,now+lease_seconds,ident,row[0]))
        return {'symbol':row[0],'listing':json.loads(row[1]),'owner':owner}
    def release(self,ident,claim):
        with self.cache.connect() as db:db.execute("UPDATE campaign_items SET state='pending',owner=NULL,lease=NULL WHERE campaign=? AND symbol=? AND owner=? AND state='running'",(ident,claim['symbol'],claim['owner']))
    def finish(self,ident,claim,row):
        if row['symbol']!=claim['symbol']:raise ValueError('Výsledok nezodpovedá rezervovanému symbolu.')
        with self.cache.connect() as db:
            changed=db.execute("UPDATE campaign_items SET state='done',result=?,lease=NULL WHERE campaign=? AND symbol=? AND owner=? AND state='running'",(json.dumps(row,allow_nan=False),ident,claim['symbol'],claim['owner'])).rowcount
        if changed!=1:raise ValueError('Rezervácia expirovala alebo bola spracovaná iným pracovníkom.')
    def rows(self,ident):
        with self.cache.connect() as db:rows=db.execute("SELECT result FROM campaign_items WHERE campaign=? AND state='done' ORDER BY ordinal",(ident,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def counts(self,ident):
        with self.cache.connect() as db:rows=db.execute('SELECT state,count(*) FROM campaign_items WHERE campaign=? GROUP BY state',(ident,)).fetchall()
        counts={'pending':0,'running':0,'done':0};counts.update(dict(rows));counts['total']=sum(counts.values())
        return counts


def scan_campaign(campaigns,ident,limit=10,progress=None,scanner=scan):
    if not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Dávka musí obsahovať 1–100 symbolov.')
    combined={'rows':[],'attempted':0,'network_loads':0,'cache_hits':0,'analyzed':0,'ranked':0,'stopped':None}
    for _ in range(limit):
        claim=campaigns.claim(ident)
        if claim is None:break
        try:
            result=scanner([claim['listing']],campaigns.cache,1)
            if not result['rows']:
                campaigns.release(ident,claim);combined['stopped']=result.get('stopped');break
            campaigns.finish(ident,claim,result['rows'][0])
        except Exception:
            campaigns.release(ident,claim);raise
        combined['rows'].extend(result['rows'])
        for key in ('attempted','network_loads','cache_hits','analyzed','ranked'):combined[key]+=result[key]
        if progress:progress(combined['attempted'],limit)
        if result.get('stopped'):
            combined['stopped']=result['stopped'];break
    combined['completed_at']=now_iso()
    return combined
