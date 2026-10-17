"""Coverage/bias diagnostics, never an imputation or replacement ranking."""
import math
from collections import Counter
from datetime import datetime,timezone


def has_financials(row):
    if 'has_financial_inputs' in row:return row['has_financial_inputs']
    return row['identity_verified'] and any(row.get(k) is not None for k in ('growth','forward_pe','fcf_margin','net_debt_ebitda'))


def recent(row,now=None,hours=None):
    """Fundamental validity and separately dated market valuation, not 48h age."""
    from market_store import parsed,fundamental_status
    now=now or datetime.now(timezone.utc)
    metadata={'retrieved_at':row.get('fetched_at'),'period_end':row.get('annual_period'),'valid_until':row.get('fundamental_valid_until'),'identity_verified':row.get('identity_verified'),'report_pending':row.get('report_pending',False)}
    if not fundamental_status(metadata,now)[0]:return False
    for key in ('price_asof','valuation_asof'):
        timestamp=parsed(row.get(key))
        if not timestamp or not -3600<=(now-timestamp).total_seconds()<=7*86400:return False
    return True


def audit(rows,listings=()):
    analyzed=[r for r in rows if has_financials(r)]
    excluded=[r for r in analyzed if r['score'] is None]
    reasons=Counter(reason for r in excluded for reason in r.get('rank_exclusions',[]))
    primary=Counter((r.get('rank_exclusions') or ['Neurčené'])[0] for r in excluded)
    groups=[]
    for field in ('exchange','sector','size_band','source'):
        values=sorted({r.get(field) or 'N/A' for r in rows})
        for value in values:
            subset=[r for r in rows if (r.get(field) or 'N/A')==value]
            n=len(subset);ranked=sum(r['score'] is not None for r in subset)
            pop=sum(r['exchange']==value for r in listings) if field=='exchange' else None
            groups.append({'dimension':field,'group':value,'universe':pop,'attempted':n,'analyzed':sum(has_financials(r) for r in subset),'ranked':ranked,'rank_rate':ranked/n if n else None,'sample_share':n/len(rows) if rows else None,'universe_share':pop/len(listings) if pop is not None and listings else None})
    return {'covered_fundamentals':sum(r.get('fundamental_valid') is True for r in rows),'comparable':sum(r['score'] is not None and recent(r) for r in rows),'attempted':len(rows),'analyzed':len(analyzed),'ranked_at_fetch':sum(r['score'] is not None for r in rows),'excluded_analyzed':len(excluded),'without_financials':len(rows)-len(analyzed),'overlapping_reasons':dict(reasons),'primary_reasons':dict(primary),'groups':groups}


def coverage_estimate(total,done=0,daily_budget=100):
    if daily_budget<=0:raise ValueError('daily_budget must be positive')
    remaining=max(0,total-done)
    return {'remaining':remaining,'daily_budget':daily_budget,'daily_budgets':math.ceil(remaining/daily_budget),'throttle_floor_hours':max(0,remaining-1)*3/3600,'active_hours_5_to_20s':(remaining*5/3600,remaining*20/3600)}
