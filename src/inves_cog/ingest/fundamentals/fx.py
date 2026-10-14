"""PIT FRED conversion with inspectable evidence and actionable exceptions."""
from collections import defaultdict
from datetime import date, timedelta
import math

SERIES={'EUR':('DEXUSEU',False),'TWD':('DEXTAUS',True),'KRW':('DEXKOUS',True)}


class FXGap(RuntimeError):
    def __init__(self,*,currency,field,period,as_of,reason):
        self.detail={'currency':currency,'field':field,'period':[str(v) for v in period],
                     'as_of':str(as_of),'series':SERIES.get(currency,(None,))[0],'reason':reason}
        super().__init__(f'{currency} {field} period={period} as_of={as_of}: {reason}')


def as_date(value):
    return value if isinstance(value,date) else date.fromisoformat(value)


class FXBook:
    def __init__(self,rows=()):
        self.rows=list(rows)
    def convert(self,value,*,currency,start,end,as_of,field):
        if currency=='USD': return value,{'original_currency':'USD','method':'identity'}
        if currency not in SERIES: raise FXGap(currency=currency,field=field,period=(start,end),as_of=as_of,reason='unsupported FRED currency series')
        end,as_of=as_date(end),as_date(as_of)
        # Q-M2-17: seven calendar days, including across a year boundary.
        first=as_date(start) if start else end-timedelta(days=7)
        visible={}; unpublished=set(); raw=[]
        for original in self.rows:
            if original.get('currency')!=currency: continue
            observed,released=as_date(original['observation_date']),as_date(original['realtime_start'])
            if not first<=observed<=end: continue
            raw.append(original)
            if released>as_of:
                if original.get('value') is not None: unpublished.add(observed)
                continue
            old=visible.get(observed)
            if old is None or as_date(old['realtime_start'])<released: visible[observed]=original
        unpublished-=set(visible)
        if unpublished: raise FXGap(currency=currency,field=field,period=(start,end),as_of=as_of,reason='H.10 observations not yet released: '+','.join(str(v) for v in sorted(unpublished)))
        quotes=[]
        for observed,row in sorted(visible.items()):
            rate=row.get('value')
            if rate is None or rate=='.': continue
            if not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<=0:
                raise FXGap(currency=currency,field=field,period=(start,end),as_of=as_of,reason='nonpositive/invalid quote on '+str(observed))
            per_usd=1/rate if SERIES[currency][1] else rate
            quotes.append({'observation_date':observed.isoformat(),'realtime_start':str(row['realtime_start']),
                           'raw_rate':rate,'usd_per_currency':per_usd})
        if not quotes: raise FXGap(currency=currency,field=field,period=(start,end),as_of=as_of,reason='no effective released quote in period' if start else 'no effective released quote within 7 calendar days before period end')
        selected=quotes if start else quotes[-1:]
        factor=sum(r['usd_per_currency'] for r in selected)/len(selected)
        return value*factor,{'original_currency':currency,'original_value':value,'series':SERIES[currency][0],
            'direction':'USD/currency','method':'daily_mean' if start else 'end_of_period',
            'period_start':first.isoformat(),'period_end':end.isoformat(),'visible_as_of':as_of.isoformat(),
            'effective_quote_date':selected[-1]['observation_date'],
            'lookback_days':None if start else (end-as_date(selected[-1]['observation_date'])).days,
            'factor':factor,'quotes':selected,
            'nonquoted_dates':[str(d) for d,r in sorted(visible.items()) if r.get('value') in (None,'.')]}


def fetch_fred_rates(http,*,key,currency,first,last,as_of,clock):
    if not key: raise FXGap(currency=currency,field='source',period=(first,last),as_of=as_of,reason='FRED_API_KEY missing')
    if currency not in SERIES: raise FXGap(currency=currency,field='source',period=(first,last),as_of=as_of,reason='unsupported series')
    series=SERIES[currency][0]; params={'api_key':key,'file_type':'json','series_id':series}
    metadata=http.get('https://api.stlouisfed.org/fred/series',params=params)
    server=as_date(metadata['realtime_end']); visible=min(as_date(as_of),server)
    rows=[]; offset=0; seen=set()
    while True:
        data=http.get('https://api.stlouisfed.org/fred/series/observations',params={**params,'observation_start':str(first),'observation_end':str(last),
            'realtime_start':'1776-07-04','realtime_end':str(visible),'output_type':1,'offset':offset,'limit':100000})
        batch=data.get('observations'); count=data.get('count')
        if not isinstance(batch,list) or not isinstance(count,int): raise FXGap(currency=currency,field='source',period=(first,last),as_of=as_of,reason='malformed observations pagination')
        for row in batch:
            identity=(row['date'],row['realtime_start'])
            if identity in seen: raise FXGap(currency=currency,field='source',period=(first,last),as_of=as_of,reason='repeated vintage page')
            seen.add(identity)
            rows.append({'currency':currency,'series_id':series,'observation_date':row['date'],'realtime_start':row['realtime_start'],
                         'value':None if row['value']=='.' else float(row['value']),'fetched_at':clock.now_utc()})
        offset+=len(batch)
        if offset>=count: return rows
        if not batch: raise FXGap(currency=currency,field='source',period=(first,last),as_of=as_of,reason='pagination ended before declared count')
