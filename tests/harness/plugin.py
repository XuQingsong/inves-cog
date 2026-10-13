"""Session-wide gates, strict pending ratchet, network policing and timing."""
import json
import os
from pathlib import Path
import time
import pytest

from inves_cog.params import load_params
from tests.harness.conftest import clock
from tests.harness.tools.checks import ROOT, requirement_catalog, validate_registry
from tests.harness.tools.network import NetworkGuard


def pytest_addoption(parser):
    parser.addoption('--harness-pending', default=None)
    parser.addoption('--harness-milestones', default=None)


def pytest_sessionstart(session):
    config = session.config
    if config.option.markexpr.strip() == 'phase1_live':
        if os.environ.get('INVES_COG_LIVE') != '1' or os.environ.get('CI'):
            raise pytest.UsageError('FR-M0-03: live needs explicit -m phase1_live, INVES_COG_LIVE=1 and no CI')
    config._harness_start = time.perf_counter()
    config._harness_guard = NetworkGuard()
    config._harness_guard.install()


def pytest_collection_modifyitems(config, items):
    try:
        rows, _ = validate_registry(
            ROOT, pending_path=config.getoption('--harness-pending'),
            milestones_path=config.getoption('--harness-milestones'),
            collected_names={i.originalname or i.name.split('[')[0] for i in items},
        )
    except AssertionError as exc:
        raise pytest.UsageError(str(exc)) from exc
    selected, live = [], []
    for item in items:
        name = item.originalname or item.name.split('[')[0]
        if any(list(item.iter_markers(marker)) for marker in ('skip', 'skipif', 'xfail')):
            raise pytest.UsageError(f'{item.path}:{item.location[1] + 1}: FR-M0-05: developer-added skip/xfail: {name}')
        if name in rows:
            item.add_marker(pytest.mark.xfail(strict=True, reason='已转绿，请从 pending 删除'))
            item._harness_pending = True
        if item.get_closest_marker('phase1_live'):
            if item.get_closest_marker('phase1_blocking'):
                raise pytest.UsageError(f'{item.path}:1: FR-M0-03: live cannot also be blocking')
            if config.option.markexpr.strip() != 'phase1_live' or os.environ.get('INVES_COG_LIVE') != '1':
                live.append(item)
                continue
        selected.append(item)
    if live:
        config.hook.pytest_deselected(items=live)
    items[:] = selected
    config._harness_pending = rows


def pytest_collection_finish(session):
    if session.config._harness_guard.events:
        raise pytest.UsageError('\n'.join(session.config._harness_guard.events))


def pytest_runtest_setup(item):
    guard = item.config._harness_guard
    guard.events.clear()
    guard.allowed = bool(item.get_closest_marker('phase1_live')
                         and item.config.option.markexpr.strip() == 'phase1_live'
                         and os.environ.get('INVES_COG_LIVE') == '1' and not os.environ.get('CI'))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    violations = list(item.config._harness_guard.events)
    if call.excinfo and call.excinfo.errisinstance((pytest.skip.Exception, pytest.xfail.Exception)):
        violations.append(f'{item.path}:{item.location[1] + 1}: FR-M0-05: manual skip/xfail is forbidden')
    if violations:
        report.outcome = 'failed'
        report.longrepr = '\n'.join(violations)
        if hasattr(report, 'wasxfail'):
            del report.wasxfail
    return report


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    guard = getattr(config, '_harness_guard', None)
    if guard:
        guard.restore()
    mark = config.option.markexpr.strip()
    elapsed = time.perf_counter() - config._harness_start
    maximum = load_params(ROOT / 'config/params/p-2026.10').values['harness']['blocking_max_seconds']
    if mark == 'phase1_blocking' and elapsed > maximum:
        session.exitstatus = 1
        terminal = config.pluginmanager.getplugin('terminalreporter')
        if terminal:
            terminal.write_line(f'FR-M0-12: blocking took {elapsed:.3f}s > {maximum}s')
    status = 'failed' if int(session.exitstatus) else 'passed'
    pending = 0
    if int(exitstatus) == 5 and session.testscollected == 0 and mark in {'phase1_replay', 'phase1_cases'}:
        catalog = requirement_catalog(ROOT)
        short = mark.removeprefix('phase1_')
        pending = sum(catalog[name][1] == short for name in getattr(config, '_harness_pending', {}))
        session.exitstatus = 0
        status = 'no_tests'
        terminal = config.pluginmanager.getplugin('terminalreporter')
        if terminal:
            terminal.write_line(f'NO TESTS COLLECTED — pending: {pending}')
            terminal.write_line('无测试（待实现）')
    record = dict(mark=mark, exit_code=int(session.exitstatus), collected=session.testscollected,
                  duration_seconds=elapsed, status=status, pending=pending)
    if mark in {'phase1_blocking', 'phase1_replay', 'phase1_cases'}:
        directory = ROOT / '.harness'
        directory.mkdir(exist_ok=True)
        (directory / (mark.removeprefix('phase1_') + '.json')).write_text(json.dumps(record, ensure_ascii=False) + '\n')


def pytest_unconfigure(config):
    guard = getattr(config, '_harness_guard', None)
    if guard:
        guard.restore()
