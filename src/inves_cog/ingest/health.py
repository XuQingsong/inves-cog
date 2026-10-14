"""Read-only health JSON; callers supply a connection factory."""
from fastapi import FastAPI
from inves_cog.ingest.repository import Repository


def extraction_counts(rows):
    total = len(rows)
    def attempted(row, key):
        meta = row.get('extraction_source', {}).get('news_triage')
        return bool(meta.get(key)) if meta is not None else row.get('extraction_status') != 'pending'
    embedding_attempts = sum(attempted(row,'embedding_attempted') for row in rows)
    tagging_attempts = sum(attempted(row,'llm_full') for row in rows)
    embedding = sum('embedding_failed' in row['flags'] for row in rows)
    tagging = sum('entity_tagging_failed' in row['flags'] for row in rows)
    return {'total':total,'embedding_failed':embedding,'entity_tagging_failed':tagging,
        'embedding_failure_rate':embedding / embedding_attempts if embedding_attempts else None,
        'entity_tagging_failure_rate':tagging / tagging_attempts if tagging_attempts else None}


def create_app(connection_factory):
    app = FastAPI(title='Inves Cog source health')
    @app.get('/health/sources')
    def sources():
        with connection_factory() as connection:
            return list(Repository(connection).health_rows().values())
    @app.get('/health/extraction')
    def extraction():
        with connection_factory() as connection:
            rows=connection.execute('SELECT flags,extraction_status,extraction_source FROM ingest.info_items').fetchall()
            return extraction_counts(rows)
    @app.get('/health/llm')
    def llm_usage():
        with connection_factory() as connection:
            # Group by persisted call timestamps; never consult a system clock.
            return connection.execute("""SELECT (created_at AT TIME ZONE 'America/New_York')::date AS day,
                model,split_part(purpose,'|',2) AS purpose,count(*) AS calls,
                sum(input_tokens) AS input_tokens,sum(output_tokens) AS output_tokens,
                count(*) FILTER (WHERE input_tokens IS NULL OR output_tokens IS NULL) AS usage_missing
                FROM ingest.llm_calls GROUP BY 1,2,3 ORDER BY 1 DESC,2,3""").fetchall()
    @app.get('/health/news-triage')
    def news_triage():
        with connection_factory() as connection:
            return connection.execute("""SELECT extraction_source->'news_triage'->>'layer' AS layer,
                extraction_source->'news_triage'->>'reason' AS reason,extraction_status,count(*) AS items
                FROM ingest.info_items GROUP BY 1,2,3 ORDER BY 1,2,3""").fetchall()
    return app
