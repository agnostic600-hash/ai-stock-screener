"""Independent resilience model; fractions, aligned annual amounts and currency required."""
import math

WEIGHTS = {'fcf':25, 'debt':20, 'growth_margins':20, 'valuation':15, 'dilution':10, 'ai_capex':10}

def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None

def evaluate_resilience(metrics):
    def component(keys, fn):
        return max(0, min(100, fn())) if all(number(metrics.get(k)) is not None for k in keys) else None
    m = metrics
    exposure = number(m.get('ai_capex_exposure'))
    parts = {
        'fcf':component(['fcf_margin'], lambda:50+250*m['fcf_margin']),
        'debt':component(['net_debt_ebitda'], lambda:100-25*max(0,m['net_debt_ebitda'])),
        'growth_margins':component(['revenue_growth','operating_margin'], lambda:50+150*m['revenue_growth']+100*m['operating_margin']),
        'valuation':component(['forward_pe'], lambda:110-2*m['forward_pe'] if m['forward_pe']>0 else 0),
        'dilution':component(['share_dilution'], lambda:100-1000*max(0,m['share_dilution'])),
        'ai_capex':100*(1-exposure) if exposure is not None and 0<=exposure<=1 else None,
    }
    coverage = sum(WEIGHTS[k] for k,v in parts.items() if v is not None)
    score = round(sum(v*WEIGHTS[k] for k,v in parts.items() if v is not None)/coverage,1) if coverage else None
    return parts, score, coverage

def stress_24m(m):
    required = ('annual_revenue','annual_fcf','annual_gross_margin','cash','debt_due_24m')
    missing = [k for k in required if number(m.get(k)) is None]
    if missing:
        return {'status':'N/A', 'missing':missing}
    if m['annual_revenue']<=0 or m['cash']<0 or m['debt_due_24m']<0 or not 0<=m['annual_gross_margin']<=1:
        return {'status':'N/A', 'missing':['invalid inputs']}
    fcf = m['annual_fcf']-.2*m['annual_revenue']*m['annual_gross_margin']
    cash = m['cash']+2*fcf-m['debt_due_24m']
    return {'status':'covered' if cash>=0 else 'shortfall','annual_stressed_fcf':fcf,'ending_cash':cash,'funding_gap':max(0,-cash),'missing':[]}
