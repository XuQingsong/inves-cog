"""Arelle instance extraction with explicit dimension and recast boundaries."""
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import re

REVENUE=['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet']


def segment_sum_ok(segments,eliminations,consolidated):
    eliminations = eliminations if isinstance(eliminations,list) else [eliminations]
    if consolidated is None or consolidated<=0 or any(value is None for value in segments+eliminations): return False
    difference=abs(sum(segments)+sum(eliminations)-consolidated)/abs(consolidated)
    return difference<=.01 or math.isclose(difference,.01,rel_tol=0,abs_tol=1e-12)


def load_instance(path,*,offline=True,cache_dir=None,fetch=None):
    from arelle.Cntlr import Cntlr
    controller=Cntlr(logFileName='logToBuffer',disable_persistent_config=True)
    controller.webCache.workOffline=offline
    if cache_dir is not None: controller.webCache.cacheDir=str(Path(cache_dir))
    if fetch and not offline:
        original=controller.webCache.getfilename
        def cached(url,*args,**kwargs):
            from urllib.parse import urlparse
            parts=urlparse(url)
            if parts.hostname in {'www.sec.gov','data.sec.gov','xbrl.sec.gov'}:
                target=Path(controller.webCache.urlToCacheFilepath(url))
                if not target.exists():
                    value=fetch(url.replace('http://','https://',1))
                    if not isinstance(value,str): raise ValueError('SEC taxonomy response is not text')
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
                return str(target)
            return original(url,*args,**kwargs)
        controller.webCache.getfilename=cached
    model=controller.modelManager.load(str(path))
    if model is None or model.modelDocument is None:
        controller.close(); raise ValueError('Arelle could not load the XBRL instance')
    return controller,model


def context_period(context):
    if context.isStartEndPeriod:
        start=context.startDatetime.date(); end=(context.endDatetime-timedelta(days=1)).date()
        return start,end,'Q' if 80<=(end-start).days<=100 else 'FY' if 350<=(end-start).days<=380 else None
    return None,None,None


def numeric(fact):
    if fact.isNil: return None
    try:
        value=float(fact.value)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError): return None


def parse_segments(path,*,ticker,accession,filed,offline=True,cache_dir=None,fx=None,fetch=None):
    controller,model=load_instance(path,offline=offline,cache_dir=cache_dir,fetch=fetch)
    try:
        grouped=defaultdict(list); consolidated={}; single=False
        for fact in model.factsInInstance:
            context=fact.context
            if context is None: continue
            start,end,length=context_period(context)
            dims=list(context.qnameDims.items())
            name=fact.qname.localName
            if name in {'NumberOfReportableSegments','NumberOfOperatingSegments'} and not dims and numeric(fact)==1: single=True
            if length is None: continue
            if not dims:
                if name in REVENUE:
                    key=(start,end); old=consolidated.get(key)
                    if old is None or REVENUE.index(name)<REVENUE.index(old.qname.localName): consolidated[key]=fact
                continue
            if len(dims)!=1: continue
            axis,dimension=dims[0]
            if not dimension.isExplicit: continue
            axis_name=axis.localName
            kind={'StatementBusinessSegmentsAxis':'business','ConsolidationItemsAxis':'elimination','ProductOrServiceAxis':'product'}.get(axis_name)
            if kind is None: continue
            member=dimension.memberQname
            if kind=='elimination' and member.localName not in {'IntersegmentEliminationMember','CorporateNonSegmentMember'}: continue
            grouped[(start,end,length,kind,member.localName,str(member))].append(fact)
        output=[]
        for (start,end,length,axis,member,qname),facts in sorted(grouped.items()):
            revenues=[f for f in facts if f.qname.localName in REVENUE]
            revenue_fact=min(revenues,key=lambda f:REVENUE.index(f.qname.localName)) if revenues else None
            profits=[f for f in facts if f.qname.localName=='OperatingIncomeLoss']
            if not profits: profits=[f for f in facts if f.qname.localName=='SegmentProfitLoss']
            if not profits: profits=[f for f in facts if re.search(r'(?:Profit|Income)',f.qname.localName) and not re.search(r'(?:Tax|Comprehensive|PerShare)',f.qname.localName)]
            profit_fact=profits[0] if len(profits)==1 else None
            revenue=numeric(revenue_fact) if revenue_fact is not None else None
            profit=numeric(profit_fact) if profit_fact is not None else None
            currency=None
            if revenue_fact is not None and revenue_fact.unit is not None:
                currency=revenue_fact.unit.measures[0][0].localName
            fx_evidence={}
            if currency and currency!='USD':
                from inves_cog.ingest.fundamentals.fx import FXGap
                if fx is None: raise FXGap(currency=currency,field='segment_revenue',period=(start,end),as_of=filed,reason='FRED conversion provider not configured')
                revenue,fx_evidence=fx.convert(revenue,currency=currency,start=start,end=end,as_of=filed,field='segment_revenue')
                if profit is not None: profit,_=fx.convert(profit,currency=currency,start=start,end=end,as_of=filed,field='segment_profit')
            total=numeric(consolidated[(start,end)]) if (start,end) in consolidated else None
            output.append({'ticker':ticker,'accession':accession,'filed':filed,'period_end':end,'period_start':start,
                'period_len':length,'axis':axis,'segment_raw':member,'segment_qname':qname,'segment_std':None,
                'revenue':revenue,'segment_profit':profit,'profit_basis':str(profit_fact.qname) if profit_fact is not None else None,
                'margin_pct':profit/revenue*100 if profit is not None and revenue is not None and revenue>0 else None,
                'yoy_pct':None,'share_pct':revenue/total*100 if revenue is not None and total is not None and total>0 else None,
                'recast_group':None,'health_codes':['segment_unmapped'] if axis=='business' else [],
                'evidence':{'currency':currency,'fx':fx_evidence,'profit_reason':'multiple_profit_elements' if len(profits)>1 else 'profit_element_missing' if not profits else None}})
        for key,total_fact in consolidated.items():
            rows=[r for r in output if (r['period_start'],r['period_end'])==key and r['axis'] in {'business','elimination'}]
            if not rows: continue
            total=numeric(total_fact)
            if total is None or total<=0:
                for row in rows: row['evidence']['sum_check_reason']='consolidated_revenue_nonpositive_or_missing'
            elif not segment_sum_ok([r['revenue'] for r in rows if r['axis']=='business'],[r['revenue'] for r in rows if r['axis']=='elimination'],total):
                for row in rows: row['health_codes'].append('segment_sum_mismatch')
        if not any(row['axis']=='business' for row in output):
            code='single_segment' if single else 'segment_missing'
            output.append({'ticker':ticker,'accession':accession,'filed':filed,'period_end':max((k[1] for k in consolidated),default=None),
                'period_start':None,'period_len':None,'axis':'evidence','segment_raw':None,'segment_std':None,'revenue':None,
                'segment_profit':None,'profit_basis':None,'margin_pct':None,'yoy_pct':None,'share_pct':None,'recast_group':None,
                'health_codes':[code],'evidence':{'single_segment_count':1 if single else None}})
        return output
    finally:
        model.close(); controller.close()


def apply_recast(current,previous,*,comparative):
    result=deepcopy(current)
    old={r['segment_raw']:r for r in previous if r.get('axis')=='business'}
    new={r['segment_raw'] for r in current if r.get('axis')=='business'}
    comparable={r['segment_raw']:r for r in comparative if r.get('axis')=='business'}
    changed=bool(old) and (set(old)!=new or comparable and set(comparable)!=set(old))
    for name,row in comparable.items():
        prior=old.get(name)
        if prior and prior.get('revenue') is not None and row.get('revenue') is not None:
            base=prior['revenue']; delta=abs(row['revenue']-base)
            if (base==0 and delta!=0) or base!=0 and delta/abs(base)>.01+1e-12: changed=True
    old_group=next((r.get('recast_group') for r in previous if r.get('recast_group')),None)
    group=old_group if old_group and not changed else hashlib.sha256(json.dumps(sorted(new)).encode()+str([(r.get('period_end'),r.get('accession')) for r in current]).encode()).hexdigest()[:20]
    for row in result:
        row['recast_group']=group; row.setdefault('health_codes',[]); row['yoy_pct']=None
        if changed: row['health_codes'].append('segment_recast')
        prior=old.get(row.get('segment_raw'))
        if not changed and prior and prior.get('recast_group')==group and prior.get('revenue') and row.get('revenue') is not None:
            row['yoy_pct']=(row['revenue']/prior['revenue']-1)*100
    return result
