"""Own-table persistence and read-only SQL access to M1/graph contracts."""
from contextlib import nullcontext
from dataclasses import asdict
from datetime import date,datetime
import hashlib,json
from inves_cog.ingest.fundamentals.state import FinState,FIELDS
from inves_cog.ingest.fundamentals.consensus import FIELDS as CONSENSUS_FIELDS


def text(value):
    def encode(obj):
        if isinstance(obj,(date,datetime)): return obj.isoformat()
        raise TypeError(type(obj).__name__)
    return json.dumps(value,ensure_ascii=False,default=encode,allow_nan=False,sort_keys=True)


TABLES={
 'fin_state':('ticker extractor accession form filed period_end fiscal_period '+' '.join(FIELDS)+' health_codes field_sources values_extra','ticker,extractor,filed'),
 'segments':('ticker accession filed period_end period_len axis segment_raw segment_std revenue segment_profit profit_basis margin_pct yoy_pct share_pct recast_group health_codes evidence row_id','row_id'),
 'segment_mapping':('id ticker segment_raw graph_node_ids drafted_by draft_reason status reviewed_at reviewer','id'),
 'consensus_snapshot':('as_of ticker source captured_at '+' '.join(CONSENSUS_FIELDS)+' raw','as_of,ticker,source'),
 'consensus_derived':('as_of ticker chg_7d_pct chg_30d_pct chg_90d_pct breadth_7d breadth_30d dispersion surprise_last4 window_status values_extra','as_of,ticker'),
 'profile':('as_of ticker profile','as_of,ticker'),
 'health':('ticker latest_period_end latest_filed latest_8k_202 health_codes can_score can_trade reason','ticker'),
 'fx_rates':('currency series_id observation_date realtime_start value fetched_at','currency,observation_date,realtime_start'),
}
JSON={'field_sources','values_extra','evidence','raw','surprise_last4','window_status','profile'}


def state_from_row(row):
    return FinState(ticker=row['ticker'],extractor=row['extractor'],filed=row['filed'],period_end=row['period_end'],
        accession=row['accession'],form=row['form'],fiscal_period=row['fiscal_period'],
        values={**row['values_extra'],**{key:row[key] for key in FIELDS}},field_sources=row['field_sources'],health_codes=row['health_codes'])


class Repository:
    def __init__(self,connection): self.connection=connection
    def transaction(self): return self.connection.transaction() if hasattr(self.connection,'transaction') else nullcontext()
    def write(self,table,row):
        if table not in TABLES: raise ValueError('Unknown fundamentals table')
        fields,conflict=TABLES[table]; fields=fields.split(); primary=set(conflict.split(','))
        columns=','.join(fields); placeholders=','.join('%s::jsonb' if key in JSON else '%s' for key in fields)
        values=[text(row.get(key,{})) if key in JSON else row.get(key) for key in fields]
        update=','.join(f'{key}=EXCLUDED.{key}' for key in fields if key not in primary)
        with self.transaction(): self.connection.execute(f'INSERT INTO fundamentals.{table} ({columns}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {update}',values)
    def put_state(self,state):
        row=asdict(state); row.update(state.values); row['values_extra']={key:value for key,value in state.values.items() if key not in FIELDS}
        self.write('fin_state',row)
    def state_asof(self,ticker,as_of_date,extractor):
        if extractor not in {'legacy','fixed'}: raise ValueError('Unknown extractor')
        row=self.connection.execute('SELECT * FROM fundamentals.fin_state WHERE ticker=%s AND extractor=%s AND filed<=%s ORDER BY filed DESC LIMIT 1',(ticker,extractor,as_of_date)).fetchone()
        return state_from_row(row) if row else None
    def read_shared_filings(self,ticker):
        return list(self.connection.execute('SELECT * FROM ingest.sec_filings WHERE ticker=%s ORDER BY filing_date,accepted_at NULLS FIRST,accession',(ticker,)).fetchall())
    def bars_available(self,ticker,as_of):
        return self.connection.execute('SELECT 1 FROM ingest.bars_daily WHERE ticker=%s AND trade_date<=%s LIMIT 1',(ticker,as_of)).fetchone() is not None
    def put_health(self,row): self.write('health',row)
    def put_profile(self,row): self.write('profile',{'as_of':row['as_of'],'ticker':row['ticker'],'profile':row})
    def profile_rows(self):
        return [row['profile'] for row in self.connection.execute('SELECT DISTINCT ON (ticker) profile FROM fundamentals.profile ORDER BY ticker,as_of DESC').fetchall()]
    def put_snapshot(self,row): self.write('consensus_snapshot',row)
    def snapshot_rows(self,ticker): return list(self.connection.execute('SELECT * FROM fundamentals.consensus_snapshot WHERE ticker=%s ORDER BY as_of',(ticker,)).fetchall())
    def put_derived(self,row): self.write('consensus_derived',{**row,'values_extra':row})
    def put_segments(self,rows):
        for row in rows:
            self.write('segments',{**row,'evidence':{**row.get('evidence',{}),'period_start':row.get('period_start') or row.get('evidence',{}).get('period_start'),'segment_qname':row.get('segment_qname') or row.get('evidence',{}).get('segment_qname')},
                'row_id':row.get('row_id') or hashlib.sha256(text({key:row.get(key) for key in ('ticker','accession','period_end','period_start','axis','segment_raw')}).encode()).hexdigest()})
    def segment_rows(self,ticker): return list(self.connection.execute('SELECT * FROM fundamentals.segments WHERE ticker=%s ORDER BY filed,period_end',(ticker,)).fetchall())
    def mapping_rows(self):
        rows=list(self.connection.execute('SELECT * FROM fundamentals.segment_mapping').fetchall())
        for row in rows:
            row['segment_std']=row['graph_node_ids'] if row['status']=='已确认' else None
            row['health_codes']=[] if row['status']=='已确认' else ['segment_unmapped']
        return rows
    def put_mapping(self,row): self.write('segment_mapping',row)
    def graph_nodes(self):
        exists=self.connection.execute("SELECT to_regclass('graph.entities') AS relation").fetchone()['relation']
        if not exists: return []
        return list(self.connection.execute('SELECT * FROM graph.entities').fetchall())
    def guidance_rows(self,ticker,as_of):
        return list(self.connection.execute("SELECT * FROM ingest.info_items WHERE kind='sec_8k' AND %s=ANY(tickers) AND is_guidance AND published_at<=%s",(ticker,as_of)).fetchall())
    def health_rows(self): return {r['ticker']:dict(r) for r in self.connection.execute('SELECT * FROM fundamentals.health').fetchall()}
    def put_rates(self,rows):
        for row in rows: self.write('fx_rates',row)
    def rates(self): return list(self.connection.execute('SELECT * FROM fundamentals.fx_rates').fetchall())

    def latest_earnings(self,ticker,as_of):
        return self.connection.execute("SELECT max(accepted_at) AS accepted FROM ingest.sec_filings WHERE ticker=%s AND form='8-K' AND '2.02'=ANY(items) AND accepted_at<=%s",(ticker,as_of)).fetchone()['accepted']
