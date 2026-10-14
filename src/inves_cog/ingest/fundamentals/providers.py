"""yfinance's approved estimates API mapped to the project snapshot contract."""
from datetime import date
import math
from zoneinfo import ZoneInfo
from inves_cog.ingest.fundamentals.consensus import FIELDS


def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [clean(v) for v in value]
    if hasattr(value,'item') and not isinstance(value,str): value=value.item()
    if isinstance(value,float) and not math.isfinite(value): return None
    if hasattr(value,'isoformat'): return value.isoformat()
    return value


def fiscal_years(latest_annual_end):
    if latest_annual_end is None: return None,None
    if isinstance(latest_annual_end,str): latest_annual_end=date.fromisoformat(latest_annual_end)
    import calendar
    def following(n):
        year=latest_annual_end.year+n
        return date(year,latest_annual_end.month,min(latest_annual_end.day,calendar.monthrange(year,latest_annual_end.month)[1]))
    return following(1),following(2)


def snapshot_from_tables(tables,*,ticker,clock,fy_cy,fy_ny):
    tables=clean(tables)
    row={'as_of':clock.now_utc().astimezone(ZoneInfo('Asia/Shanghai')).date(),'ticker':ticker,'source':'yfinance',
         'captured_at':clock.now_utc(),**{key:None for key in FIELDS},'raw':tables}
    row.update(fy_cy=fy_cy,fy_ny=fy_ny)
    earnings=tables.get('earnings_estimate',{}); revenue=tables.get('revenue_estimate',{}); revisions=tables.get('eps_revisions',{})
    for period,key in (('0q','eps_cq'),('+1q','eps_nq'),('0y','eps_cy'),('+1y','eps_ny')):
        row[key]=earnings.get(period,{}).get('avg')
    for period,key in (('0y','rev_cy'),('+1y','rev_ny')): row[key]=revenue.get(period,{}).get('avg')
    row.update(coverage=earnings.get('0y',{}).get('numberOfAnalysts'),eps_high_cy=earnings.get('0y',{}).get('high'),eps_low_cy=earnings.get('0y',{}).get('low'))
    for dest,src in (('up_7d','upLast7days'),('down_7d','downLast7days'),('up_30d','upLast30days'),('down_30d','downLast30days')):
        row[dest]=revisions.get('0y',{}).get(src)
    targets=tables.get('analyst_price_targets',{}) or {}
    row.update(pt_mean=targets.get('mean'),pt_median=targets.get('median'))
    history=[]
    for original in tables.get('earnings_history',[]):
        history.append({'quarter_date':str(original['quarter_date'])[:10], 'eps_actual':original.get('epsActual',original.get('eps_actual')),
            'eps_est':original.get('epsEstimate',original.get('eps_est')),
            'surprise_pct':original['surprisePercent']*100 if original.get('surprisePercent') is not None else original.get('surprise_pct'),
            'captured_at':clock.now_utc().isoformat()})
    row['raw']['earnings_history']=history
    return row


class YFinance:
    def __init__(self,*,clock,ticker_factory=None):
        self.clock,self.ticker_factory=clock,ticker_factory
    def collect(self,ticker,*,fy_cy,fy_ny):
        if self.ticker_factory is None:
            import yfinance
            factory=yfinance.Ticker
        else: factory=self.ticker_factory
        client=factory(ticker); tables={}
        for name in ('earnings_estimate','revenue_estimate','eps_revisions','eps_trend'):
            frame=getattr(client,'get_'+name)()
            tables[name]=frame.to_dict(orient='index') if frame is not None else {}
        tables['analyst_price_targets']=client.get_analyst_price_targets() or {}
        frame=client.get_earnings_history()
        tables['earnings_history']=[{'quarter_date':index.date(),**row.to_dict()} for index,row in frame.iterrows()] if frame is not None else []
        if not tables['earnings_estimate']: raise RuntimeError('yfinance returned no earnings estimates; snapshot not fabricated')
        return snapshot_from_tables(tables,ticker=ticker,clock=self.clock,fy_cy=fy_cy,fy_ny=fy_ny)
