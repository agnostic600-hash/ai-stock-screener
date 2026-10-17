"""Provider-neutral annual inputs. No ticker universe or UI dependencies."""
import pandas as pd
from screener import number

INPUT_KEYS = ('annual_revenue','annual_fcf','annual_gross_margin','cash','debt_due_24m','fcf_margin','operating_margin','revenue_growth','net_debt_ebitda','share_dilution','ai_capex_exposure','forward_pe')


def annual_bundle(revenue, fcf, gross_profit, operating_income, cash, debt, ebitda,
                  shares, previous_shares, previous_revenue, debt_due_24m=None):
    ratio = lambda a,b: a/b if a is not None and b is not None and b>0 else None
    return dict(annual_revenue=revenue, annual_fcf=fcf,
        annual_gross_margin=ratio(gross_profit,revenue), cash=cash, debt_due_24m=debt_due_24m,
        fcf_margin=ratio(fcf,revenue), operating_margin=ratio(operating_income,revenue),
        revenue_growth=(revenue/previous_revenue-1 if revenue is not None and revenue>0 and previous_revenue is not None and previous_revenue>0 else None),
        net_debt_ebitda=(ratio(debt-cash,ebitda) if debt is not None and debt>=0 and cash is not None and cash>=0 else None),
        share_dilution=(shares/previous_shares-1 if shares is not None and shares>0 and previous_shares is not None and previous_shares>0 else None),
        ai_capex_exposure=None)


def yahoo_annual(income, cashflow, balance, currency):
    """Annual statement frames from the same verified Yahoo Ticker; never info TTM ratios."""
    if not currency or any(not isinstance(f,pd.DataFrame) or f.empty for f in (income,cashflow,balance)):
        return {}, None
    dates=sorted(set(income.columns)&set(cashflow.columns)&set(balance.columns),reverse=True)
    if not dates: return {}, None
    end=dates[0]
    def get(frame,row,d=end):
        if row not in frame.index or d not in frame.columns:return None
        value=frame.loc[row,d]
        return number(value) if not isinstance(value,pd.Series) else None
    previous=[d for d in dates if 330<=(end-d).days<=380]
    prev=max(previous) if previous else None
    rev=get(income,'Total Revenue'); ocf=get(cashflow,'Operating Cash Flow'); capex=get(cashflow,'Capital Expenditure')
    # Yahoo cash-flow statement capex uses a cash outflow (negative) sign.
    fcf=ocf+capex if ocf is not None and capex is not None and capex<=0 else None
    values=annual_bundle(rev,fcf,get(income,'Gross Profit'),get(income,'Operating Income'),
        get(balance,'Cash And Cash Equivalents'),get(balance,'Total Debt'),get(income,'EBITDA'),
        get(income,'Diluted Average Shares'),get(income,'Diluted Average Shares',prev) if prev is not None else None,
        get(income,'Total Revenue',prev) if prev is not None else None)
    return values, str(end.date())
