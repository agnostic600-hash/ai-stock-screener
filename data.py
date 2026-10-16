"""Dáta Yahoo Finance, voliteľne fundamenty Alpha Vantage."""
import requests
import pandas as pd
import yfinance as yf
from screener import Stock, number


def statement_value(frame, row, column):
    if frame is None or frame.empty or row not in frame.index or column not in frame.columns:
        return None
    return number(frame.loc[row, column])


def compute_roic(income, balance):
    """NOPAT / priemerný investovaný kapitál, len pri úplných ročných výkazoch."""
    if income.empty or balance.empty:
        return None, 'N/A'
    dates = sorted(set(income.columns) & set(balance.columns), reverse=True)
    if not dates:
        return None, 'N/A'
    date = dates[0]
    previous = [d for d in balance.columns if 300 <= (date-d).days <= 430]
    if not previous:
        return None, str(date.date())
    ebit = statement_value(income, 'Operating Income', date)
    tax = statement_value(income, 'Tax Provision', date)
    pretax = statement_value(income, 'Pretax Income', date)
    capital = []
    for d in (date, max(previous)):
        vals = [statement_value(balance, row, d) for row in ('Total Debt', 'Stockholders Equity', 'Cash And Cash Equivalents')]
        if any(v is None for v in vals):
            return None, str(date.date())
        capital.append(vals[0]+vals[1]-vals[2])
    if ebit is None or tax is None or pretax is None or pretax <= 0 or not 0 <= tax/pretax <= 1 or min(capital) <= 0:
        return None, str(date.date())
    return ebit*(1-tax/pretax)/(sum(capital)/2), str(date.date())


def load_stock(symbol, api_key='', provider='Yahoo Finance'):
    stock = Stock(symbol)
    asset = yf.Ticker(symbol)
    if provider == 'Yahoo Finance':
        try:
            info = asset.get_info()
            if not info or not any(info.get(k) is not None for k in ('regularMarketPrice', 'currentPrice', 'longName')):
                stock.warnings.append('Fundamentálne údaje nie sú dostupné; overte ticker.')
            stock.name = info.get('longName') or info.get('shortName') or symbol
            stock.currency = info.get('currency', '')
            stock.financial_currency = info.get('financialCurrency', '')
            stock.sector = info.get('sector') or 'N/A'
            mapping = {'price':'currentPrice', 'pe':'trailingPE', 'forward_pe':'forwardPE', 'peg':'trailingPegRatio', 'revenue_growth':'revenueGrowth', 'eps':'trailingEps', 'earnings_growth':'earningsGrowth', 'gross_margin':'grossMargins', 'operating_margin':'operatingMargins', 'profit_margin':'profitMargins', 'fcf':'freeCashflow', 'debt_equity':'debtToEquity', 'current_ratio':'currentRatio'}
            stock.metrics = {k:number(info.get(v)) for k,v in mapping.items()}
            if stock.metrics['price'] is None:
                stock.metrics['price'] = number(info.get('regularMarketPrice'))
            if stock.metrics['debt_equity'] is not None:
                stock.metrics['debt_equity'] /= 100
            try:
                stock.metrics['roic'], stock.fiscal_date = compute_roic(asset.income_stmt, asset.balance_sheet)
            except Exception:
                stock.warnings.append('Ročné výkazy pre ROIC nie sú dostupné.')
        except Exception:
            stock.warnings.append('Yahoo Finance neposkytlo fundamenty. Skontrolujte sieť, ticker alebo limit API.')
    else:
        stock.source = 'Alpha Vantage (fundamenty), Yahoo Finance (graf)'
        if not api_key:
            stock.warnings.append('Chýba ALPHAVANTAGE_API_KEY v prostredí alebo Streamlit secrets.')
        else:
            try:
                response = requests.get('https://www.alphavantage.co/query', params={'function':'OVERVIEW','symbol':symbol,'apikey':api_key}, timeout=20)
                response.raise_for_status()
                info = response.json()
                if not info.get('Symbol'):
                    stock.warnings.append('Alpha Vantage nevrátilo firmu: neplatný ticker, limit API alebo nedostupné pokrytie.')
                stock.name = info.get('Name', symbol)
                stock.currency = stock.financial_currency = info.get('Currency', '')
                stock.sector = info.get('Sector') or 'N/A'
                stock.fiscal_date = info.get('LatestQuarter') or 'N/A'
                mapping = {'pe':'PERatio','forward_pe':'ForwardPE','peg':'PEGRatio','revenue_growth':'QuarterlyRevenueGrowthYOY','eps':'EPS','earnings_growth':'QuarterlyEarningsGrowthYOY','operating_margin':'OperatingMarginTTM','profit_margin':'ProfitMargin'}
                stock.metrics = {k:number(info.get(v)) for k,v in mapping.items()}
            except (requests.RequestException, ValueError):
                stock.warnings.append('Alpha Vantage je nedostupné. Overte prístup k API a jeho limity.')
    try:
        history = asset.history(period='1y', auto_adjust=True, timeout=15)
        if not history.empty:
            stock.history = history['Close'].rename(symbol)
        else:
            stock.warnings.append('Cenová história nie je dostupná.')
    except Exception:
        stock.warnings.append('Cenová história nie je dostupná.')
    return stock
