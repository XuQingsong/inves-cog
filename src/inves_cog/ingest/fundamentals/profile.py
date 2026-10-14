"""Daily three-part profiles and immutable, idempotent change records."""
from copy import deepcopy
from zoneinfo import ZoneInfo


class ProfileBook:
    def __init__(self,*,clock,previous=()):
        self.clock=clock; self.profiles={p['ticker']:deepcopy(p) for p in previous}
    def generate(self,state,*,segments,consensus,guidance):
        old=self.profiles.get(state.ticker,{})
        records=deepcopy(old.get('changes',[])); seen={row['id'] for row in records}
        today=self.clock.now_utc().astimezone(ZoneInfo('Asia/Shanghai')).date()
        def change(identifier,kind,data):
            if identifier not in seen:
                records.append({'id':identifier,'kind':kind,'recorded_at':self.clock.now_utc(),'data':data}); seen.add(identifier)
        filing=(str(state.filed),state.accession)
        if old.get('filing_key')!=list(filing): change('filing:'+':'.join(str(v) for v in filing),'新财报生效',{'filed':state.filed,'accession':state.accession})
        base=deepcopy(old.get('consensus_base'))
        current=consensus.get('eps_cy') if consensus else None
        target=consensus.get('fy_cy') if consensus else None
        if current is not None and target is not None:
            marker={'eps_cy':current,'fy_cy':str(target)}
            if base is None: base=marker
            elif base['fy_cy']!=str(target):
                change('fy:'+str(today)+':'+str(target),'财年切换',marker); base=marker
            else:
                amount=base['eps_cy']
                triggered=(abs(current/amount-1)>.03+1e-12) if amount>0 else ((current>0)-(current<0))!=((amount>0)-(amount<0))
                if triggered:
                    change('consensus:'+str(today)+':'+str(current),'一致预期变化',{'before':base,'after':marker}); base=marker
        for item in guidance:
            items=item.get('items',item.get('payload',{}).get('items',[]))
            if isinstance(items,str): items=[part.strip() for part in items.split(',')]
            if not item.get('is_guidance') or not {'2.02','7.01'}&set(items or []): continue
            published=item.get('published_at')
            if published and published>self.clock.now_utc(): continue
            identity=item.get('info_id') or item.get('accession')
            if not identity: raise ValueError('Guidance needs source identity')
            change('guidance:'+identity,'业绩指引',{'info_id':identity,'direction':item.get('guidance_direction')})
        business=[row for row in segments if row.get('axis')=='business']
        output={'ticker':state.ticker,'as_of':today,'filing_key':list(filing),'consensus_base':base,'changes':records,
            'business':{'data':business or None,'reason':None if business else '分部原件尚未取得/不存在可解析业务分部；见分部健康码'},
            'financials':{'data':{'filed':state.filed,'period_end':state.period_end,'values':deepcopy(state.values),'field_sources':deepcopy(state.field_sources),'health_codes':state.health_codes},'reason':None},
            'consensus':{'data':deepcopy(consensus),'reason':None if consensus else '当日一致预期快照未取得；不回补或外推'}}
        self.profiles[state.ticker]=output
        return output
