"""Real-source smoke is never part of CI."""
import os
from inves_cog.ingest.fundamentals.cli import build


def run_smoke(*,clock):
    if os.environ.get('INVES_COG_LIVE')!='1':raise RuntimeError('Explicit phase1_live opt-in required')
    from inves_cog.ingest.settings import read_environment
    from inves_cog.ingest.cli import connect
    values=read_environment()
    with connect(values) as connection:
        service,runner,tasks,operational=build(clock=clock,values=values,connection=connection)
        report=runner.run('m2_live_financials','SECCompanyfacts',service.collect_financials)
        if report.get('status')=='failed':raise RuntimeError('Live fundamentals failed; inspect source_health')
        return {'health':service.repo.health_rows(),'report':report}
