"""Explicit opt-in smoke; invoked only by the phase1_live harness."""
import os
from inves_cog.ingest.settings import read_environment
from inves_cog.ingest.cli import build, connect
from inves_cog.ingest.market import trading_day
from datetime import timedelta


def run_smoke(*, clock):
    if os.environ.get('INVES_COG_LIVE') != '1':
        raise RuntimeError('Live ingestion requires INVES_COG_LIVE=1 and explicit -m phase1_live')
    values = read_environment()
    with connect(values) as connection:
        pipeline = build(clock=clock,values=values,connection=connection)
        day = clock.today_trade_date()-timedelta(days=1)
        while not trading_day(day): day -= timedelta(days=1)
        pipeline.day_override = day
        report = pipeline.runtime().run(['bars_full','news_full'])
        bars, news = report['bars_full'], report['news_full']
        if bars.get('status') == 'failed' or news.get('status') == 'failed':
            raise RuntimeError('Live source smoke failed; inspect source_health and job_runs')
        return {**bars,'news_count':news['processed_count'],'source_health':pipeline.repo.health_rows()}
