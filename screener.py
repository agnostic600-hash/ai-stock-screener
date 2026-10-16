"""Transparentné finančné heuristiky. Chýbajúce údaje nikdy nenahrádzame nulou."""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


METRICS = {
    'price': 'Cena', 'pe': 'P/E', 'forward_pe': 'Forward P/E', 'peg': 'PEG',
    'revenue_growth': 'Rast tržieb', 'eps': 'EPS', 'earnings_growth': 'Rast zisku',
    'gross_margin': 'Hrubá marža', 'operating_margin': 'Prevádzková marža',
    'profit_margin': 'Čistá marža', 'fcf': 'Voľný cash flow', 'debt_equity': 'Dlh / vlastné imanie',
    'current_ratio': 'Bežná likvidita', 'roic': 'ROIC',
}
PERCENT = {'revenue_growth', 'earnings_growth', 'gross_margin', 'operating_margin', 'profit_margin', 'roic'}


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def tickers(text):
    result = list(dict.fromkeys(x.upper() for x in re.split(r'[,;\s]+', text.strip()) if x))
    if len(result) > 20:
        raise ValueError('Zadajte najviac 20 tickerov naraz.')
    if any(not re.fullmatch(r'[A-Z0-9][A-Z0-9.^=\-]{0,19}', x) for x in result):
        raise ValueError('Ticker obsahuje nepovolené znaky.')
    return result


@dataclass
class Stock:
    ticker: str
    name: str = ''
    currency: str = ''
    financial_currency: str = ''
    sector: str = 'N/A'
    metrics: dict = field(default_factory=dict)
    history: object = None
    warnings: list = field(default_factory=list)
    source: str = 'Yahoo Finance'
    fetched: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fiscal_date: str = 'N/A'


def ramp(value, low, high, reverse=False):
    value = number(value)
    if value is None:
        return None
    score = max(0, min(100, (value-low)/(high-low)*100))
    return 100-score if reverse else score


def positive_multiple(value, low, high):
    value = number(value)
    return ramp(value, low, high, True) if value is not None and value > 0 else None


def evaluate(stock):
    m = stock.metrics
    groups = {
        'Podhodnotenie': [positive_multiple(m.get('pe'), 10, 40), positive_multiple(m.get('forward_pe'), 10, 35), positive_multiple(m.get('peg'), .5, 3)],
        'Moat – finančné indikátory': [ramp(m.get('gross_margin'), .1, .6), ramp(m.get('operating_margin'), 0, .3), ramp(m.get('roic'), 0, .25)],
        'Finančná stabilita': [(ramp(m.get('debt_equity'), 0, 2, True) if number(m.get('debt_equity')) is not None and m['debt_equity'] >= 0 else None), ramp(m.get('current_ratio'), .5, 2), None if m.get('fcf') is None else (100 if m['fcf'] > 0 else 0)],
        'Rastový potenciál': [ramp(m.get('revenue_growth'), 0, .3), ramp(m.get('earnings_growth'), 0, .3)],
    }
    scores = {k: round(sum(v for v in vs if v is not None)/sum(v is not None for v in vs), 1) if any(v is not None for v in vs) else None for k, vs in groups.items()}
    available = sum(v is not None for vs in groups.values() for v in vs)
    coverage = round(100*available/11)
    # Všetky štyri dimenzie a aspoň 7 indikátorov sú podmienkou porovnateľného skóre.
    total = round(sum(scores.values())/4, 1) if available >= 7 and all(v is not None for v in scores.values()) else None
    return scores, total, coverage


def scenario(stock, years):
    """Podmienený rast EPS; nejde o predikciu ceny ani o analytický konsenzus."""
    eps, growth = stock.metrics.get('eps'), stock.metrics.get('earnings_growth')
    if eps is None or eps <= 0 or growth is None or growth <= -1:
        return None
    return eps*(1+growth)**years
