"""M2 entry points; production resolves the one M1-owned client implementation."""
import argparse,json,os,time
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml
from inves_cog.clock import SystemClock
from inves_cog.ingest.fundamentals.repository import Repository,text
from inves_cog.ingest.fundamentals.state import configure as configure_states
from inves_cog.ingest.fundamentals.mapping import configure as configure_mappings
from inves_cog.ingest.fundamentals.service import FinancialService
from inves_cog.ingest.fundamentals.consensus import ConsensusStore,import_muse_exports
from inves_cog.ingest.fundamentals.providers import YFinance
from inves_cog.ingest.fundamentals.instances import InstanceLoader
from inves_cog.ingest.fundamentals.fx import FXBook,fetch_fred_rates,SERIES

ROOT=Path(__file__).resolve().parents[4]


def build(*,clock,values,connection):
    try:
        from inves_cog.ingest.sec_client import SECClient
        from inves_cog.ingest.http import HTTPClient,RateLimiter
        from inves_cog.llm.client import Client
        from inves_cog.ingest.jobs import HealthBook,JobRunner
        from inves_cog.ingest.repository import Repository as OperationalRepository
    except ImportError as exc:
        raise RuntimeError('Production M2 needs the merged M1 clients/tables; use injected test doubles before that merge') from exc
    repository=Repository(connection); operational=OperationalRepository(connection)
    sec=SECClient(user_agent=values.get('SEC_USER_AGENT',''))
    universe=yaml.safe_load((ROOT/'config/universe.yaml').read_text())['stocks']
    ciks={row['ticker']:row['cik'] for row in connection.execute('SELECT DISTINCT ticker,cik FROM ingest.sec_filings').fetchall()}
    fx=FXBook(repository.rates())
    service=FinancialService(clock=clock,repository=repository,sec=sec,llm=Client.from_environment(values),
        universe=universe,ciks=ciks,consensus_provider=YFinance(clock=clock),fx=fx,
        instance_loader=InstanceLoader(sec=sec,cache_dir=ROOT/'.harness/xbrl',offline=False))
    configure_states(repository);configure_mappings(service.queue)
    health=HealthBook(clock=clock,rows=operational.health_rows(),persist=operational.write_health)
    runner=JobRunner(clock=clock,health=health,persist=operational.write_job)
    http=HTTPClient(limiter=RateLimiter(30,60))
    def rates():
        count=0
        for currency in SERIES:
            rows=fetch_fred_rates(http,key=values.get('FRED_API_KEY'),currency=currency,first=date(2006,1,1),
                                  last=service.as_of,as_of=service.as_of,clock=clock)
            repository.put_rates(rows); count+=len(rows)
        fx.rows=repository.rates()
        return {'processed_count':count}
    tasks={'financials':('SECCompanyfacts',service.collect_financials),'consensus':('YFinance',service.collect_consensus),'fx':('FREDFX',rates)}
    return service,runner,tasks,operational


def run_tasks(*,clock,runner,tasks,names):
    if set(names)-set(tasks): raise ValueError('Unknown M2 tasks')
    output={}
    for name in names:
        if name=='financials':
            now=clock.now_utc().astimezone(ZoneInfo('America/New_York'))
            start=now.replace(hour=21,minute=15,second=0,microsecond=0); end=now.replace(hour=21,minute=45,second=0,microsecond=0)
            if not start<=now<end:
                output[name]={'status':'not_due','note':'M2 SEC slot is 21:15–21:45 ET'}; continue
            runner.timeout_seconds=min(1800,(end-now).total_seconds())
        else: runner.timeout_seconds=1800
        source,operation=tasks[name]
        output[name]=runner.run('m2_'+name,source,operation)
    return output


def main():
    parser=argparse.ArgumentParser(description='Independent PIT fundamentals')
    parser.add_argument('action',choices=['run','schedule','health','import-muse','mappings','confirm'])
    parser.add_argument('--tasks',nargs='+',choices=['financials','consensus','fx'])
    parser.add_argument('--folder',type=Path);parser.add_argument('--sector');parser.add_argument('--ids',nargs='+')
    parser.add_argument('--reviewer');parser.add_argument('--decision',choices=['已确认','驳回'])
    args=parser.parse_args()
    try:
        from inves_cog.ingest.settings import read_environment
        values=read_environment()
    except ImportError:
        values=dict(os.environ)
    import psycopg
    from psycopg.rows import dict_row
    if not values.get('INVES_COG_DATABASE_URL'): parser.error('INVES_COG_DATABASE_URL missing; before M1 merge pass it in the process environment')
    clock=SystemClock()
    with psycopg.connect(values['INVES_COG_DATABASE_URL'],row_factory=dict_row,autocommit=True) as connection:
        repository=Repository(connection)
        if args.action=='health': output=repository.health_rows()
        elif args.action=='import-muse':
            if args.folder is None: parser.error('--folder is required; files stay outside the repository')
            store=ConsensusStore();output=import_muse_exports(args.folder,store=store,annual_end_asof=repository.annual_end_asof)
            for row in store.rows.values():repository.put_snapshot(row)
            output['database_snapshots']=connection.execute("SELECT count(*) AS n FROM fundamentals.consensus_snapshot WHERE source='muse_import'").fetchone()['n']
        else:
            service,runner,tasks,operational=build(clock=clock,values=values,connection=connection)
            if args.action=='mappings': output=service.queue.list_pending_mappings(args.sector)
            elif args.action=='confirm': output=service.queue.confirm_mappings(args.ids or [],args.reviewer,args.decision)
            elif args.action=='schedule':
                while True:
                    now=clock.now_utc();ny=now.astimezone(ZoneInfo('America/New_York'));bj=now.astimezone(ZoneInfo('Asia/Shanghai'))
                    last=operational.last_runs();names=[]
                    for name,allowed in [('financials',(ny.hour==21 and 15<=ny.minute<45)),('consensus',((bj.hour,bj.minute)>=(9,15) and (bj.hour,bj.minute)<(10,30))),('fx',((bj.hour,bj.minute)>=(8,30) and (bj.hour,bj.minute)<(9,15)))]:
                        stamp=last.get('m2_'+name)
                        if allowed and (stamp is None or stamp.astimezone(ZoneInfo('Asia/Shanghai')).date()<bj.date()):names.append(name)
                    if names:print(text(run_tasks(clock=clock,runner=runner,tasks=tasks,names=names)),flush=True)
                    time.sleep(30)
            else:
                if not args.tasks: parser.error('--tasks is required')
                output=run_tasks(clock=clock,runner=runner,tasks=tasks,names=args.tasks)
        print(text(output))


if __name__=='__main__':main()
