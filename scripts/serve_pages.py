"""One public read-only page process; only private env supplies its database login."""

import shlex
from pathlib import Path


def configuration(root, python):
    state = root / '.harness/service'
    return f'''[program:pages]
command={shlex.join([str(python), '-u', str(root / 'scripts/serve_pages.py')])}
directory={root}
autostart=true
autorestart=true
startsecs=3
startretries=3
stopasgroup=true
killasgroup=true
stopwaitsecs=15
stdout_logfile={state}/pages.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
redirect_stderr=true
environment=PYTHONUNBUFFERED="1"
'''


def main():
    import uvicorn

    from inves_cog.ingest.settings import read_environment
    from inves_cog.web.public import create_app

    root = Path(__file__).resolve().parents[1]
    values = read_environment(root / '.env', environ={})
    dsn = values.get('INVES_COG_WEB_DATABASE_URL')
    if not dsn:
        raise SystemExit('INVES_COG_WEB_DATABASE_URL is required')
    app = create_app(dsn=dsn)
    uvicorn.run(app, host='0.0.0.0', port=8080, workers=1, proxy_headers=False,
                server_header=False, access_log=False, log_level='critical')


if __name__ == '__main__':
    main()
