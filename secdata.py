"""Bezplatná záloha SEC EDGAR: overené tickery a ročné US-GAAP údaje, nie odhady."""
import os
import threading
import time
from datetime import date
from functools import lru_cache
from providers import get_json, DataError
from screener import number
from resilience_data import annual_bundle


def headers():
    # SEC vyžaduje identifikáciu aplikácie; prevádzkovateľ môže pridať kontaktný email.
    return {'User-Agent': os.getenv('SEC_USER_AGENT') or 'AIStockScreener/1.0 https://github.com/agnostic600-hash/ai-stock-screener', 'Accept-Encoding':'gzip, deflate'}


_sec_lock = threading.Lock()
_last_request = 0.0


def sec_json(url):
    global _last_request
    # Najviac 4 začiatky požiadaviek/s na proces, aj pri súbežných reláciách.
    with _sec_lock:
        time.sleep(max(0, .25 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        return get_json(url, headers=headers())


@lru_cache(maxsize=1)
def company_index():
    return sec_json('https://www.sec.gov/files/company_tickers.json')


def annual_values(facts, tags, unit, end=None):
    """Len ročné 10-K, približne 52/53 týždňov; žiadne štvrťročné/TTM miešanie."""
    all_candidates = []
    for tag in tags:
        items = facts.get(tag, {}).get('units', {}).get(unit, [])
        candidates = []
        for item in items:
            try:
                duration = (date.fromisoformat(item['end'])-date.fromisoformat(item['start'])).days if 'start' in item else None
                if item.get('form') not in ('10-K','10-K/A') or (duration is not None and not 330 <= duration <= 380):
                    continue
                if end and item['end'] != end:
                    continue
                if number(item.get('val')) is not None:
                    candidates.append(item)
            except (ValueError, KeyError):
                continue
        all_candidates.extend(candidates)
    # Najnovšie obdobie naprieč alternatívnymi tagmi, nie prvý historický tag.
    return max(all_candidates, key=lambda i:(i['end'],i.get('filed',''))) if all_candidates else None


def parse_facts(payload):
    facts = payload.get('facts', {}).get('us-gaap', {})
    revenue_tags = ['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet']
    revenue = annual_values(facts, revenue_tags, 'USD')
    if not revenue or 'start' not in revenue:
        raise DataError('SEC nemá podporované ročné US-GAAP tržby v USD; ostatné hodnoty zostávajú N/A.')
    end = revenue['end']
    # Nevyberáme starší alternatívny účtovný tag po skončení dostupného obdobia.
    def val(tags, unit='USD', period=end, instant=False):
        record = annual_values(facts, tags, unit, period)
        if record is None:
            return None
        if instant:
            if 'start' in record:
                return None
        elif record.get('start') != revenue['start'] and period == end:
            return None
        return number(record['val'])
    rev = number(revenue['val'])
    metrics = {'eps':val(['EarningsPerShareDiluted','EarningsPerShareBasic'],'USD/shares')}
    for key, tags in [('gross_margin',['GrossProfit']),('operating_margin',['OperatingIncomeLoss']),('profit_margin',['NetIncomeLoss'])]:
        numerator = val(tags)
        metrics[key] = numerator/rev if numerator is not None and rev and rev > 0 else None
    cash = val(['NetCashProvidedByUsedInOperatingActivities'])
    capex = val(['PaymentsToAcquirePropertyPlantAndEquipment'])
    metrics['fcf'] = cash-capex if cash is not None and capex is not None and capex>=0 else None
    assets, liabilities = val(['AssetsCurrent'], instant=True), val(['LiabilitiesCurrent'], instant=True)
    metrics['current_ratio'] = assets/liabilities if assets is not None and liabilities is not None and liabilities > 0 else None
    previous_records=[]
    for tag in revenue_tags:
        for record in facts.get(tag,{}).get('units',{}).get('USD',[]):
            try:
                delta=(date.fromisoformat(end)-date.fromisoformat(record['end'])).days
                if 330 <= delta <= 380:
                    previous_records.append(record['end'])
            except (ValueError,KeyError):
                continue
    previous_end = max(previous_records) if previous_records else None
    for key, tags in [('revenue_growth',revenue_tags),('earnings_growth',['NetIncomeLoss'])]:
        current = val(tags)
        previous = annual_values(facts,tags,'USD',previous_end) if previous_end else None
        prev = number(previous['val']) if previous else None
        # Pri zápornom základe medziročný percentuálny rast nie je porovnateľný.
        metrics[key] = current/prev-1 if current is not None and prev is not None and prev > 0 else None
    # All annual flow inputs use exactly the revenue start/end; balances use end.
    current_shares = val(['WeightedAverageNumberOfDilutedSharesOutstanding'], 'shares')
    previous_shares_record = annual_values(facts, ['WeightedAverageNumberOfDilutedSharesOutstanding'], 'shares', previous_end) if previous_end else None
    previous_shares = None
    prior_rev = annual_values(facts, revenue_tags, 'USD', previous_end) if previous_end else None
    prior_revenue = number(prior_rev['val']) if prior_rev else None
    if previous_shares_record and prior_rev and previous_shares_record.get('start') == prior_rev.get('start'):
        previous_shares = number(previous_shares_record['val'])
    # Do not treat one current portion as total debt. Require explicit total or both components.
    debt = val(['LongTermDebtAndFinanceLeaseObligationsIncludingCurrentPortion'], instant=True)
    short = val(['ShortTermBorrowings'], instant=True)
    if debt is None:
        long_debt, current_debt = val(['LongTermDebtNoncurrent'], instant=True), val(['LongTermDebtCurrent'], instant=True)
        debt = long_debt+current_debt if long_debt is not None and current_debt is not None else None
    debt = debt+short if debt is not None and short is not None else None
    year1 = val(['LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths'], instant=True)
    year2 = val(['LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo'], instant=True)
    due = year1+year2+short if all(v is not None and v>=0 for v in (year1,year2,short)) else None
    # US-GAAP depreciation may include amortization; require an explicit combined tag.
    depreciation = val(['DepreciationDepletionAndAmortization'])
    ebit = val(['OperatingIncomeLoss'])
    ebitda = ebit+depreciation if ebit is not None and depreciation is not None else None
    bundle=annual_bundle(rev,metrics['fcf'],val(['GrossProfit']),ebit,
        val(['CashAndCashEquivalentsAtCarryingValue'], instant=True),debt,ebitda,current_shares,previous_shares,prior_revenue,due)
    metrics['_resilience'] = bundle
    return metrics, end


def load_sec(symbol):
    # Bodka pri US triede (BRK.B) zodpovedá SEC BRK-B; suffixy búrz sa neodstraňujú.
    symbol = symbol.replace('.', '-')
    companies = company_index()
    company = next((c for c in companies.values() if isinstance(c,dict) and c.get('ticker','').upper() == symbol), None)
    if company is None:
        raise DataError('Ticker sa nenašiel v registri SEC. To nevylučuje jeho platnosť na európskej burze; overte suffix a pokrytie.')
    cik = str(company['cik_str']).zfill(10)
    payload = sec_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
    if str(payload.get('cik','')).lstrip('0') != cik.lstrip('0'):
        raise DataError('SEC vrátilo inú identitu firmy; údaje boli odmietnuté.')
    metrics, end = parse_facts(payload)
    return company.get('title',symbol), metrics, end
