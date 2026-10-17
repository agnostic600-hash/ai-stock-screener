"""Dáta Yahoo Finance, voliteľne fundamenty Alpha Vantage."""
import requests
import pandas as pd
import yfinance as yf
from screener import Stock, number, METRICS
from providers import error_reason, DataError
from secdata import load_sec


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
            if not isinstance(info, dict):
                raise DataError('Neplatná odpoveď Yahoo Finance.')
            returned_symbol = info.get('symbol')
            if returned_symbol and returned_symbol.upper() != symbol.upper():
                raise DataError('Yahoo vrátilo údaje iného tickera.')
            if not any(number(info.get(k)) is not None for k in ('trailingPE', 'trailingEps', 'totalRevenue', 'freeCashflow')):
                stock.warnings.append('Yahoo vrátilo iba čiastočnú odpoveď bez základných fundamentov; neznamená to neplatný ticker.')
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
            except Exception as exc:
                stock.warnings.append('ROIC je N/A: ' + error_reason(exc))
        except Exception as exc:
            stock.warnings.append('Yahoo Finance – fundamenty: ' + error_reason(exc))
        stock.provenance = {k: 'Yahoo Finance (obdobie podľa poskytovateľa)' for k,v in stock.metrics.items() if v is not None}
        # SEC je nezávislá bezplatná záloha pre chýbajúce historické fundamenty.
        supported = ('eps','revenue_growth','earnings_growth','gross_margin','operating_margin','profit_margin','fcf','current_ratio')
        if any(stock.metrics.get(k) is None for k in supported):
            try:
                name, metrics, fiscal_date = load_sec(symbol)
                if stock.financial_currency and stock.financial_currency != 'USD':
                    raise DataError('Mena výkazov Yahoo nie je USD; SEC USD údaje sa kvôli neporovnateľnosti nemiešajú.')
                added = []
                for k,v in metrics.items():
                    if stock.metrics.get(k) is None and v is not None:
                        stock.metrics[k] = v
                        stock.provenance[k] = 'SEC EDGAR – ročné obdobie do ' + fiscal_date
                        added.append(k)
                if added:
                    stock.name = name if stock.name in ('', symbol) else stock.name
                    stock.financial_currency = stock.financial_currency or 'USD'
                    stock.source += ' + SEC EDGAR (ročná záloha)'
                    stock.warnings.append('SEC overilo ticker a doplnilo ročné údaje: ' + ', '.join(METRICS[k] for k in added) + '. Nie sú to TTM ani analytické odhady; podrobné obdobia sú v detaile.')
            except DataError as exc:
                stock.warnings.append('Záloha SEC EDGAR: ' + str(exc))
            except Exception:
                stock.warnings.append('Záloha SEC EDGAR: odpoveď má nepodporovaný formát; údaje zostávajú N/A.')
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
                    stock.warnings.append(('Alpha Vantage: limit API alebo servisné oznámenie; skúste neskôr.' if info.get('Note') or info.get('Information') else 'Alpha Vantage: ticker nemá dostupné údaje alebo bol odmietnutý; overte symbol a pokrytie.'))
                stock.name = info.get('Name', symbol)
                stock.currency = stock.financial_currency = info.get('Currency', '')
                stock.sector = info.get('Sector') or 'N/A'
                stock.fiscal_date = info.get('LatestQuarter') or 'N/A'
                mapping = {'pe':'PERatio','forward_pe':'ForwardPE','peg':'PEGRatio','revenue_growth':'QuarterlyRevenueGrowthYOY','eps':'EPS','earnings_growth':'QuarterlyEarningsGrowthYOY','operating_margin':'OperatingMarginTTM','profit_margin':'ProfitMargin'}
                stock.metrics = {k:number(info.get(v)) for k,v in mapping.items()}
            except (requests.RequestException, ValueError) as exc:
                stock.warnings.append('Alpha Vantage: ' + error_reason(exc))
    try:
        history = asset.history(period='1y', auto_adjust=True, timeout=15)
        if not history.empty:
            stock.history = history['Close'].rename(symbol)
        else:
            stock.warnings.append('Cenová história nie je dostupná.')
    except Exception as exc:
        stock.warnings.append('Cenová história je N/A: ' + error_reason(exc))
    missing = [label for k,label in METRICS.items() if stock.metrics.get(k) is None]
    if missing:
        stock.warnings.append('N/A – zdroje neposkytli použiteľné údaje: ' + ', '.join(missing) + '. Podrobnosti o prístupe a pokrytí sú vyššie; chýbajúce odhady ani ceny sa nedopočítavajú.')
    return stock

