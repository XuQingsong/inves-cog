"""Read-only health JSON; callers supply a connection factory."""
from fastapi import FastAPI
from inves_cog.ingest.repository import Repository


def extraction_counts(rows):
    total = len(rows)
    attempted = sum(row.get('extraction_status') != 'pending' for row in rows)
    embedding = sum('embedding_failed' in row['flags'] for row in rows)
    tagging = sum('entity_tagging_failed' in row['flags'] for row in rows)
    return {'total':total,'embedding_failed':embedding,'entity_tagging_failed':tagging,
        'embedding_failure_rate':embedding / attempted if attempted else None,
        'entity_tagging_failure_rate':tagging / attempted if attempted else None}


def create_app(connection_factory):
    app = FastAPI(title='Inves Cog source health')
    @app.get('/health/sources')
    def sources():
        with connection_factory() as connection:
            return list(Repository(connection).health_rows().values())
    @app.get('/health/extraction')
    def extraction():
        with connection_factory() as connection:
            rows=connection.execute('SELECT flags,extraction_status FROM ingest.info_items').fetchall()
            return extraction_counts(rows)
    return app
