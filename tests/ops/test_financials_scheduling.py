"""Register only the authorized M2 financial update, without Yahoo side effects."""

from configparser import ConfigParser
from datetime import datetime
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from scripts.install_ingest_service import configuration

pytestmark = pytest.mark.phase1_blocking


def test_installer_registers_restarting_financials_only_service():
    config = ConfigParser(interpolation=None)
    config.read_string(configuration(Path('/fixture/root'), Path('/fixture/python')))
    assert 'schedule_financials.py' in config.get('program:financials', 'command')
    assert config.getboolean('program:financials', 'autostart')
    assert config.getboolean('program:financials', 'autorestart')


@pytest.mark.parametrize('stamp,ready', [
    ('2026-10-17T01:14:59+00:00', False),
    ('2026-10-17T01:15:00+00:00', True),
    ('2026-10-17T01:44:59+00:00', True),
    ('2026-10-17T01:45:00+00:00', False),
    ('2026-11-03T02:15:00+00:00', True),
    ('2026-10-18T01:15:00+00:00', False),
])
def test_financials_slot_et_dst_and_no_repeat(stamp, ready):
    from scripts.schedule_financials import due

    clock = FrozenClock(datetime.fromisoformat(stamp))
    assert due(clock) == ready
    assert not due(clock, clock.now_utc())


def test_financials_dispatch_uses_existing_m2_runner_and_only_financials():
    from scripts.schedule_financials import run_once

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, *args):
            return self

        def fetchone(self):
            return None

    calls = []
    clock = FrozenClock(datetime.fromisoformat('2026-10-17T01:15:00+00:00'))

    def build(**kwargs):
        return None, 'existing-runner', {'financials': 'existing-task'}, None

    def dispatch(**kwargs):
        calls.append(kwargs)
        return {'financials': {'status': 'ok', 'processed_count': 59}}

    result = run_once(clock=clock, values={}, connect=lambda values: Connection(), build=build, dispatch=dispatch)
    assert result['financials']['processed_count'] == 59
    assert calls == [{'clock': clock, 'runner': 'existing-runner',
                      'tasks': {'financials': 'existing-task'}, 'names': ['financials']}]

    class Completed(Connection):
        def fetchone(self):
            return {'started_at': clock.now_utc()}

    assert run_once(clock=clock, values={}, connect=lambda values: Completed(),
                    build=lambda **kw: pytest.fail('repeated build'), dispatch=dispatch)['status'] == 'not_due'
