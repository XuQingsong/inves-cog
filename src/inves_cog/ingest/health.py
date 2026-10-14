"""Read-only health JSON; callers supply a connection factory."""
from fastapi import FastAPI
from inves_cog.ingest.repository import Repository


def create_app(connection_factory):
    app = FastAPI(title='Inves Cog source health')
    @app.get('/health/sources')
    def sources():
        with connection_factory() as connection:
            return list(Repository(connection).health_rows().values())
    return app
