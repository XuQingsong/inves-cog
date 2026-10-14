"""PostgreSQL persistence. All SQL targets are fixed identifiers, values are bound."""
from contextlib import nullcontext
from datetime import date, datetime
import hashlib
import json


def json_text(value):
    def encode(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        raise TypeError(type(obj).__name__)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=encode, allow_nan=False)


TABLES = {
 'bars_minute': ('ticker ts_utc open high low close volume session source', 'ticker,ts_utc'),
 'bars_daily': ('ticker trade_date open high low close volume post_close adj_factor source', 'ticker,trade_date'),
 'wide_universe': ('trade_date ticker mktcap adv20 included exclude_reason notes', 'trade_date,ticker'),
 'sec_filings': ('ticker cik accession form filing_date report_date accepted_at items primary_document is_xbrl is_inline_xbrl fetched_at raw', 'accession'),
 'earnings_events': ('event_id ticker accession item accepted_at session reaction_day ref_close fiscal_period fallback flags reported_date fetched_at superseded_at', 'event_id'),
 'form4_events': ('event_id ticker filed_at insider_name is_officer transaction_code shares price accession transaction_index source raw', 'event_id'),
 'app_rank_snapshots': ('ts_utc chart rank app_id app_name developer', 'ts_utc,chart,app_id'),
 'short_interest': ('observation_id ticker settlement_date publish_date short_interest avg_daily_volume days_to_cover si_pct_shares_outstanding source raw', 'observation_id'),
 'options_stats': ('trade_date category call_volume put_volume put_call_ratio open_interest source', 'trade_date,category,source'),
 'macro_observations': ('series_id observation_date value units realtime_start fetched_at', 'series_id,observation_date,realtime_start'),
 'website_snapshots': ('url captured_at body', 'url,captured_at'),
 'source_health': ('source last_success_at last_attempt_at status latency_sec items_last_run note consecutive_failures', 'source'),
}
INFO_FIELDS = 'info_id kind published_at first_seen_at source source_root source_level headline body summary url tickers entities embedding extraction_status flags payload is_guidance guidance_direction is_rating_change extraction_source'.split()
JSON_COLUMNS = {'raw', 'payload', 'extraction_source'}


def identity(value):
    return hashlib.sha256(json_text(value).encode()).hexdigest()


def normalize_entity(row):
    if not isinstance(row.get('entity_id'),str) or not row['entity_id'] or not row.get('name'):
        raise ValueError('Graph entity requires entity_id and name')
    def values(name,legacy):
        result=row.get(name,row.get(legacy,[])) or []
        if not isinstance(result,list): raise ValueError('Entity channel values must be lists')
        return result
    channels=set(row['channels']) if row.get('channels') is not None else {'app','trend','site'}
    tickers=row.get('tickers') or ([row['ticker']] if row.get('ticker') else [])
    return {'entity_id':row['entity_id'],'name':row['name'],'aliases':row.get('aliases') or [],
        'tickers':tickers,'app_ids':values('app_ids','app_store_ids') if 'app' in channels else [],
        'trends_keywords':values('trends_keywords','trend_keywords') if 'trend' in channels else [],
        'urls':values('urls','official_urls') if 'site' in channels else []}


class Repository:
    def __init__(self, connection):
        self.connection = connection
        self.counts = {'collected': 0, 'inserted': 0, 'deduped': 0}
        self.processed = 0

    def transaction(self):
        return self.connection.transaction() if hasattr(self.connection, 'transaction') else nullcontext()

    def write(self, table, row, *, update=()):
        if table not in TABLES:
            raise ValueError('Unknown ingest table')
        columns, conflict = TABLES[table]
        fields = columns.split()
        if set(update) - set(fields):
            raise ValueError('Invalid update fields')
        values = [json_text(row.get(key, {})) if key in JSON_COLUMNS else row.get(key) for key in fields]
        placeholders = ['%s::jsonb' if key in JSON_COLUMNS else '%s' for key in fields]
        action = 'DO UPDATE SET ' + ','.join(f'{key}=EXCLUDED.{key}' for key in update) if update else 'DO NOTHING'
        sql = f"INSERT INTO ingest.{table} ({','.join(fields)}) VALUES ({','.join(placeholders)}) ON CONFLICT ({conflict}) {action}"
        with self.transaction():
            self.connection.execute(sql, values)
        self.processed += 1

    def write_job(self, row):
        fields = 'task_name trade_date started_at ended_at status processed_count error_summary params_version llm_input_tokens llm_output_tokens llm_usage_missing_calls'.split()
        with self.transaction():
            stats = self.connection.execute("""SELECT
                CASE WHEN count(*) FILTER (WHERE input_tokens IS NULL)>0 THEN NULL ELSE coalesce(sum(input_tokens),0) END AS input_tokens,
                CASE WHEN count(*) FILTER (WHERE output_tokens IS NULL)>0 THEN NULL ELSE coalesce(sum(output_tokens),0) END AS output_tokens,
                count(*) FILTER (WHERE input_tokens IS NULL OR output_tokens IS NULL) AS usage_missing_calls
                FROM ingest.llm_calls WHERE (created_at AT TIME ZONE 'America/New_York')::date=%s
                AND split_part(purpose,'|',1)=%s""", (row['trade_date'],row['task_name'])).fetchone()
            row = dict(row,llm_input_tokens=stats['input_tokens'],llm_output_tokens=stats['output_tokens'],
                       llm_usage_missing_calls=stats['usage_missing_calls'])
            self.connection.execute(f"INSERT INTO ingest.job_runs ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))})", [row[field] for field in fields])

    def write_health(self, row):
        self.write('source_health', row, update=tuple(field for field in TABLES['source_health'][0].split() if field != 'source'))

    def put_info(self, item):
        item = dict(item)
        item['summary'] = item['body'][:500] if item['body'] is not None else item.get('summary')
        fields = INFO_FIELDS
        values = [json_text(item.get(key)) if key in JSON_COLUMNS or key == 'embedding' and item.get(key) is not None else item.get(key) for key in fields]
        placeholders = ['%s::jsonb' if key in JSON_COLUMNS else '%s::vector' if key == 'embedding' else '%s' for key in fields]
        with self.transaction():
            inserted = self.connection.execute(f"INSERT INTO ingest.info_items ({','.join(fields)}) VALUES ({','.join(placeholders)}) ON CONFLICT (info_id) DO NOTHING RETURNING info_id", values).fetchone()
            if inserted is None:
                previous = self.connection.execute('SELECT * FROM ingest.info_items WHERE info_id=%s FOR UPDATE', (item['info_id'],)).fetchone()
                if (previous['headline'], previous['body']) != (item['headline'], item['body']):
                    self.connection.execute('INSERT INTO ingest.info_item_versions (info_id,version_seen_at,headline,body,raw) VALUES (%s,%s,%s,%s,%s::jsonb)',
                                            (item['info_id'], item['first_seen_at'], item['headline'], item['body'], json_text({'previous': dict(previous), 'incoming': item})))
                    mutable = [key for key in fields if key not in {'info_id', 'published_at', 'first_seen_at', 'source_root'}]
                    update_values = [values[fields.index(key)] for key in mutable]
                    assignments = [f"{key}={placeholders[fields.index(key)]}" for key in mutable]
                    self.connection.execute(f"UPDATE ingest.info_items SET {','.join(assignments)} WHERE info_id=%s", update_values + [item['info_id']])
        self.processed += 1
        self.counts['collected'] += 1
        self.counts['inserted' if inserted is not None else 'deduped'] += 1
        return 'inserted' if inserted is not None else 'deduped'

    def compact(self, as_of):
        with self.transaction():
            self.connection.execute("UPDATE ingest.info_items SET body=NULL WHERE first_seen_at < %s - INTERVAL '90 days' AND summary IS NOT NULL", (as_of,))

    def monitored_entities(self, fallback):
        exists = self.connection.execute("SELECT to_regclass('graph.monitored_entities') AS relation").fetchone()['relation']
        return [normalize_entity(row) for row in self.connection.execute('SELECT e.*,m.channels FROM graph.monitored_entities AS m JOIN graph.entities AS e USING(entity_id)').fetchall()] if exists else fallback

    def health_rows(self):
        return {row['source']: dict(row) for row in self.connection.execute('SELECT * FROM ingest.source_health').fetchall()}


    def count_duplicate(self):
        self.processed += 1
        self.counts['collected'] += 1
        self.counts['deduped'] += 1

    def info_signature(self, info_id):
        row = self.connection.execute('SELECT headline,body FROM ingest.info_items WHERE info_id=%s', (info_id,)).fetchone()
        return (row['headline'],row['body']) if row else None

    def graph_entities(self, fallback):
        exists = self.connection.execute("SELECT to_regclass('graph.entities') AS relation").fetchone()['relation']
        return [normalize_entity(row) for row in self.connection.execute('SELECT * FROM graph.entities').fetchall()] if exists else fallback

    def last_runs(self, *, trade_date=None):
        sql='SELECT task_name,max(started_at) AS started_at FROM ingest.job_runs'
        if trade_date is not None:
            sql+=" WHERE task_name NOT IN ('bars_full','bars_prefill','wide_universe') OR trade_date=%s"
        sql+=' GROUP BY task_name'
        cursor=self.connection.execute(sql,(trade_date,)) if trade_date is not None else self.connection.execute(sql)
        return {r['task_name']:r['started_at'] for r in cursor.fetchall()}

    def get_cursor(self,key):
        row=self.connection.execute('SELECT value FROM ingest.source_cursors WHERE cursor_key=%s',(key,)).fetchone()
        return row['value'] if row else None

    def set_cursor(self,key,value,stamp):
        with self.transaction():
            self.connection.execute('INSERT INTO ingest.source_cursors (cursor_key,value,updated_at) VALUES (%s,%s::jsonb,%s) ON CONFLICT (cursor_key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at',(key,json_text(value),stamp))

    def first_bar_date(self):
        return self.connection.execute('SELECT min(trade_date) AS day FROM ingest.bars_daily').fetchone()['day']

    def post_close(self,ticker,day):
        row=self.connection.execute('SELECT post_close FROM ingest.bars_daily WHERE ticker=%s AND trade_date=%s',(ticker,day)).fetchone()
        return row['post_close'] if row else None

    def closes(self,ticker):
        return {r['trade_date']:r['close'] for r in self.connection.execute('SELECT trade_date,close FROM ingest.bars_daily WHERE ticker=%s AND close IS NOT NULL',(ticker,)).fetchall()}

    def latest_wide(self):
        return list(self.connection.execute('SELECT * FROM ingest.wide_universe WHERE trade_date=(SELECT max(trade_date) FROM ingest.wide_universe)').fetchall())

    def filings(self,ticker):
        return {r['accession']:dict(r) for r in self.connection.execute('SELECT * FROM ingest.sec_filings WHERE ticker=%s',(ticker,)).fetchall()}

    def supersede_fallback(self,ticker,day,stamp):
        with self.transaction():
            self.connection.execute('UPDATE ingest.earnings_events SET superseded_at=%s WHERE ticker=%s AND fallback AND reported_date=%s AND superseded_at IS NULL',(stamp,ticker,day))

    def latest_app_ranks(self,chart):
        return {r['app_id']:r['rank'] for r in self.connection.execute('SELECT app_id,rank FROM ingest.app_rank_snapshots WHERE chart=%s AND ts_utc=(SELECT max(ts_utc) FROM ingest.app_rank_snapshots WHERE chart=%s)',(chart,chart)).fetchall()}

    def latest_website(self,url):
        row=self.connection.execute('SELECT body FROM ingest.website_snapshots WHERE url=%s ORDER BY captured_at DESC LIMIT 1',(url,)).fetchone()
        return row['body'] if row else None


    def pending_info(self,limit=32,*,as_of):
        return [dict(row) for row in self.connection.execute("""SELECT * FROM ingest.info_items
            WHERE extraction_status='pending'
            AND coalesce((extraction_source->'news_triage'->>'retry_at')::timestamptz,first_seen_at)<=%s
            ORDER BY first_seen_at,info_id LIMIT %s""",(as_of,limit)).fetchall()]

    def has_pending_info(self,*,as_of):
        return self.connection.execute("""SELECT EXISTS(SELECT 1 FROM ingest.info_items
            WHERE extraction_status='pending'
            AND coalesce((extraction_source->'news_triage'->>'retry_at')::timestamptz,first_seen_at)<=%s) AS pending""",
            (as_of,)).fetchone()['pending']

    def llm_usage(self,as_of):
        return dict(self.connection.execute("""SELECT
            coalesce(sum(input_tokens+output_tokens),0) AS tokens,
            count(*) FILTER (WHERE input_tokens IS NULL OR output_tokens IS NULL) AS missing
            FROM ingest.llm_calls WHERE model='deepseek-v4.1-flash'
            AND (created_at AT TIME ZONE 'America/New_York')::date=(%s AT TIME ZONE 'America/New_York')::date""",
            (as_of,)).fetchone())

    def enriched_root(self,root):
        row = self.connection.execute("""SELECT * FROM ingest.info_items WHERE source_root=%s
            AND extraction_status='ok' AND extraction_source ? 'news_triage'
            ORDER BY first_seen_at,info_id LIMIT 1""",(root,)).fetchone()
        return dict(row) if row else None

    def apply_enrichment(self,row):
        fields=['entities','embedding','extraction_status','flags','is_guidance','guidance_direction','is_rating_change','extraction_source']
        values=[json_text(row[key]) if key in {'embedding','extraction_source'} and row[key] is not None else row[key] for key in fields]
        assignments=[key+'=%s'+('::vector' if key=='embedding' else '::jsonb' if key=='extraction_source' else '') for key in fields]
        with self.transaction():
            result=self.connection.execute('UPDATE ingest.info_items SET '+','.join(assignments)+",published_at=COALESCE(published_at,%s) WHERE info_id=%s AND headline=%s AND body IS NOT DISTINCT FROM %s RETURNING info_id",values+[row['published_at'],row['info_id'],row['headline'],row['body']]).fetchone()
        # A newer upstream body remains pending instead of receiving stale tags.
        return result is not None
