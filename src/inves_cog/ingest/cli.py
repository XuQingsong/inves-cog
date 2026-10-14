"""Run once, poll the persisted ET schedule, or inspect source health."""
import argparse
import json
from pathlib import Path
import time
import subprocess
import sys
from inves_cog.clock import SystemClock
from inves_cog.ingest.settings import read_environment
from inves_cog.ingest.repository import Repository, json_text
from inves_cog.ingest.runtime import due_tasks


def build(*, clock, values, connection):
    from inves_cog.ingest.providers import Alpaca, FRED
    from inves_cog.ingest.sec_client import SECClient
    from inves_cog.llm.client import Client
    from inves_cog.ingest.pipeline import Pipeline
    alpaca = Alpaca(clock=clock,key=values['APCA_API_KEY_ID'],secret=values['APCA_API_SECRET_KEY'],assets_base_url=values.get('APCA_API_BASE_URL') or 'https://paper-api.alpaca.markets') if values.get('APCA_API_KEY_ID') and values.get('APCA_API_SECRET_KEY') else None
    fred = FRED(clock=clock,key=values['FRED_API_KEY']) if values.get('FRED_API_KEY') else None
    sec = SECClient(user_agent=values['SEC_USER_AGENT']) if values.get('SEC_USER_AGENT') else None
    return Pipeline(clock=clock,repository=Repository(connection),values=values,
                    llm=Client.from_environment(values,clock=clock),sec=sec,alpaca=alpaca,fred=fred)


def connect(values):
    import psycopg
    from psycopg.rows import dict_row
    if not values.get('INVES_COG_DATABASE_URL'):
        raise ValueError('INVES_COG_DATABASE_URL is required')
    return psycopg.connect(values['INVES_COG_DATABASE_URL'],row_factory=dict_row,autocommit=True)


def schedule_once(pipeline, runtime, *, names=None):
    if names is not None and set(names)-set(runtime.tasks):
        raise ValueError('Unknown scheduled task')
    due=due_tasks(pipeline.clock,pipeline.repo.last_runs(trade_date=pipeline.clock.today_trade_date()))
    if names is not None:
        due=[name for name in due if name in names]
    return runtime.run(due) if due else {}


def main():
    parser = argparse.ArgumentParser(description='Independent market ingestion')
    parser.add_argument('action',choices=['run','schedule','health','enrich'])
    parser.add_argument('--tasks',nargs='+')
    parser.add_argument('--trade-date',type=__import__('datetime').date.fromisoformat)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--once',action='store_true',help='Process one enrichment batch')
    args = parser.parse_args()
    values, clock = read_environment(), SystemClock()
    with connect(values) as connection:
        if args.action == 'health':
            output = Repository(connection).health_rows()
        else:
            pipeline = build(clock=clock,values=values,connection=connection)
            pipeline.day_override = args.trade_date
            runtime = pipeline.runtime()
            if args.action == 'enrich':
                from inves_cog.ingest.jobs import HealthBook,JobRunner
                runner=JobRunner(clock=clock,health=HealthBook(clock=clock,rows=pipeline.repo.health_rows(),persist=pipeline.repo.write_health),persist=pipeline.repo.write_job)
                while True:
                    if pipeline.repo.has_pending_info():
                        output=runner.run('info_enrichment','InfoExtraction',pipeline.enrich_pending)
                        print(json_text(output),flush=True)
                    else: output={'processed_count':0,'note':'no pending information'}
                    if args.once: break
                    time.sleep(2 if output['processed_count'] else 30)
            elif args.action == 'schedule':
                if args.trade_date: parser.error('schedule uses the injected current clock')
                log_path=Path(__file__).resolve().parents[3]/'.harness/enrichment.log'
                log_path.parent.mkdir(parents=True,exist_ok=True)
                with log_path.open('a') as log:
                    needs_enrichment=args.tasks is None or bool(set(args.tasks)-{'bars_full','bars_prefill','wide_universe'})
                    worker=subprocess.Popen([sys.executable,'-m','inves_cog.ingest.cli','enrich'],stdout=log,stderr=log) if needs_enrichment else None
                    try:
                        while True:
                            if worker is not None and worker.poll() is not None: raise RuntimeError('Enrichment worker exited; inspect .harness/enrichment.log')
                            output=schedule_once(pipeline,runtime,names=args.tasks)
                            if output: print(json_text(output),flush=True)
                            time.sleep(30)
                    finally:
                        if worker is not None:
                            worker.terminate()
                            try: worker.wait(timeout=5)
                            except subprocess.TimeoutExpired: worker.kill();worker.wait()
            else:
                if not args.tasks: parser.error('run requires --tasks')
                output = runtime.run(args.tasks)
                pipeline.repo.compact(clock.now_utc())
        text = json_text(output)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(text + '\n')
        print(text)


if __name__ == '__main__':
    main()
