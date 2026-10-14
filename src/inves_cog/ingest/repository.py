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


class Repository:
    def __init__(self, connection):
        self.connection = connection
        self.counts = {'collected': 0, 'inserted': 0, 'deduped': 0}

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

    def write_job(self, row):
        fields = 'task_name trade_date started_at ended_at status processed_count error_summary params_version'.split()
        with self.transaction():
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
        self.counts['collected'] += 1
        self.counts['inserted' if inserted is not None else 'deduped'] += 1
        return 'inserted' if inserted is not None else 'deduped'

    def compact(self, as_of):
        with self.transaction():
            self.connection.execute("UPDATE ingest.info_items SET body=NULL WHERE first_seen_at < %s - INTERVAL '90 days' AND summary IS NOT NULL", (as_of,))

    def monitored_entities(self, fallback):
        exists = self.connection.execute("SELECT to_regclass('graph.monitored_entities') AS relation").fetchone()['relation']
        return list(self.connection.execute('SELECT * FROM graph.monitored_entities').fetchall()) if exists else fallback

    def health_rows(self):
        return {row['source']: dict(row) for row in self.connection.execute('SELECT * FROM ingest.source_health').fetchall()}
