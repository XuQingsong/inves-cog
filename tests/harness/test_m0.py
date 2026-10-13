import hashlib
import json
from pathlib import Path
import shutil

import pytest

from tests.harness.tools.testing import ROOT, output, run_probe

pytestmark = pytest.mark.phase1_blocking


def test_harness_no_network(tmp_path):
    from tests.harness.tools.network import NetworkGuard
    assert NetworkGuard
    attempts = (
        'socket.create_connection(("example.com", 80))',
        'socket.getaddrinfo("example.com", 80)',
        'requests.get("https://example.com", timeout=1)',
    )
    for operation in attempts:
        code = ('import socket, requests\ndef test_probe():\n'
                f'    try:\n        {operation}\n'
                '    except Exception:\n        pass\n')
        result = run_probe(tmp_path, code)
        assert result.returncode == 1, output(result)
        assert 'FR-M0-03' in output(result)
        assert 'test_probe.py:' in output(result)
    result = run_probe(tmp_path, 'import pytest\n@pytest.mark.phase1_live\n'
                       'def test_probe(clock):\n    assert clock.__class__.__name__ == "SystemClock"\n',
                       arguments=('-m', 'phase1_live'),
                       environment={'INVES_COG_LIVE': '1', 'CI': ''})
    assert result.returncode == 0, output(result)
    for env in ({'INVES_COG_LIVE': '0'}, {'INVES_COG_LIVE': '1', 'CI': 'true'}):
        result = run_probe(tmp_path, 'def test_probe():\n    assert True\n',
                           arguments=('-m', 'phase1_live'), environment=env)
        assert result.returncode != 0 and 'FR-M0-03' in output(result)


def test_injected_clock_only(tmp_path):
    from datetime import datetime, timezone
    from inves_cog.clock import FrozenClock
    from inves_cog.params import load_params
    from tests.harness.tools.checks import scan_clock
    scan_clock(ROOT / 'src/inves_cog')
    stamp = datetime(2026, 11, 2, 4, 30, tzinfo=timezone.utc)
    clock = FrozenClock(stamp)
    assert clock.now_utc() == stamp
    assert str(clock.today_trade_date()) == '2026-11-01'
    with pytest.raises(ValueError):
        FrozenClock(datetime(2026, 1, 1))
    assert load_params(ROOT / 'config/params/p-2026.10').params_version == 'p-2026.10'
    for source in ('from datetime import datetime\nx=datetime.now()',
                   'from datetime import datetime as dt\nx=dt.utcnow()',
                   'import time as t\nx=t.time()'):
        p = tmp_path / 'trading.py'
        p.write_text(source)
        with pytest.raises(AssertionError, match='FR-M0-04'):
            scan_clock(p)


def test_pending_registry(tmp_path):
    from tests.harness.tools.checks import requirement_tests, validate_registry
    rows, defined = validate_registry(ROOT)
    required = requirement_tests(ROOT)
    assert set(rows) | defined == set(required)
    assert not any(module == 'M0' for module in rows.values())
    source = (ROOT / 'tests/harness/pending.txt').read_text()
    for content in (source + source.splitlines()[0] + '\n',
                    source + 'broken line\n',
                    source + 'test_unknown | M99 | missing\n'):
        p = tmp_path / 'pending.txt'
        p.write_text(content)
        with pytest.raises(AssertionError, match='FR-M0-05'):
            validate_registry(ROOT, pending_path=p)
    for body, status in (('assert False', 0), ('assert True', 1)):
        result = run_probe(tmp_path, f'def test_bar_window_to_20et():\n    {body}\n')
        assert result.returncode == status, output(result)
        assert ('xfailed' if status == 0 else '已转绿，请从 pending 删除') in output(result)
    for decoration in ('skip', 'xfail'):
        result = run_probe(tmp_path, 'import pytest\n@pytest.mark.' + decoration +
                           '\ndef test_probe():\n    assert False\n')
        assert result.returncode != 0 and 'FR-M0-05' in output(result)
    result = run_probe(tmp_path, 'import pytest\ndef test_probe():\n    pytest.skip("hidden")\n')
    assert result.returncode == 1 and 'FR-M0-05' in output(result)


def test_milestones_consistency(tmp_path):
    from tests.harness.tools.checks import validate_registry
    validate_registry(ROOT)
    closed = tmp_path / 'milestones.txt'
    closed.write_text('M1\n')
    with pytest.raises(AssertionError, match='FR-M0-05'):
        validate_registry(ROOT, milestones_path=closed)
    pending = tmp_path / 'pending.txt'
    pending.write_text('\n'.join(line for line in (ROOT / 'tests/harness/pending.txt').read_text().splitlines()
                                 if '| M1 |' not in line) + '\n')
    with pytest.raises(AssertionError, match='FR-M0-05'):
        validate_registry(ROOT, pending_path=pending, milestones_path=closed)


def test_requirements_golden_unchanged(tmp_path):
    from tests.harness.tools.golden import load_golden, validate_golden
    real = ROOT / 'docs/phase1/golden'
    original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in real.iterdir()}
    assert len(validate_golden(real)) == 8
    assert isinstance(load_golden('m3_interp_points.json'), dict)
    copied = tmp_path / 'golden'
    shutil.copytree(real, copied)
    p = copied / 'm3_interp_points.json'
    p.write_bytes(p.read_bytes() + b' ')
    with pytest.raises(AssertionError, match='FR-M0-07'):
        validate_golden(copied)
    p.write_bytes((real / p.name).read_bytes())
    (copied / 'extra.json').write_text('{}')
    with pytest.raises(AssertionError, match='FR-M0-07'):
        validate_golden(copied)
    assert original == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in real.iterdir()}
    assert (ROOT / '.github/CODEOWNERS').read_text().strip() == 'docs/** @XuQingsong'


def test_frozen_fixtures_changelog(tmp_path):
    from tests.harness.tools.golden import validate_frozen
    validate_frozen(ROOT / 'tests/fixtures/phase1', ROOT / 'tests/harness/CHANGELOG.md')
    fixture = tmp_path / 'sample.json'
    fixture.write_text('{"value": null}\n')
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    (tmp_path / 'MANIFEST.sha256').write_text(f'{digest}  sample.json\n')
    log = tmp_path / 'CHANGELOG.md'
    log.write_text(f'sample.json {digest} FR-M0-08\n')
    validate_frozen(tmp_path, log, changelog_prefix='')
    fixture.write_text('{"value": 0}\n')
    with pytest.raises(AssertionError, match='FR-M0-08'):
        validate_frozen(tmp_path, log, changelog_prefix='')
    new = hashlib.sha256(fixture.read_bytes()).hexdigest()
    (tmp_path / 'MANIFEST.sha256').write_text(f'{new}  sample.json\n')
    with pytest.raises(AssertionError, match='FR-M0-08'):
        validate_frozen(tmp_path, log, changelog_prefix='')


def test_import_firewall(tmp_path):
    from tests.harness.tools.checks import scan_imports
    scan_imports(ROOT)
    negatives = (
        ('trading/entry.py', 'import inves_cog.valuation_v1'),
        ('trading/entry.py', 'from .. import valuation_v1'),
        ('trading/entry.py', 'import importlib as il\nil.import_module("inves_cog.valuation_v1")'),
        ('marketstate/entry.py', 'import inves_cog.perception.attribution'),
        ('ingest/entry.py', 'import ' + 'stock' + '_pm'),
        ('trading/entry.py', 'from inves_cog import shadow'),
        ('valuation_v1/entry.py', 'from inves_cog.trading import engine'),
    )
    for name, content in negatives:
        p = tmp_path / 'src/inves_cog' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        with pytest.raises(AssertionError, match='I01'):
            scan_imports(tmp_path)
        p.unlink()
    p = tmp_path / 'src/inves_cog/marketstate/entry.py'
    p.write_text('from inves_cog.perception.graph import baskets')
    scan_imports(tmp_path)


def test_llm_models_allowed(tmp_path):
    from inves_cog.llm.registry import Registry
    from tests.harness.tools.checks import scan_models
    registry = Registry(ROOT / 'config/llm_tasks.yaml')
    assert len(registry.tasks) == 10
    assert registry.resolve('anomaly_candidates').model == 'glm-5.3'
    assert registry.resolve('entity_tagging').model == 'deepseek-v4.1-flash'
    assert registry.resolve('anomaly_candidates').timeout_seconds == 900
    assert registry.resolve('entity_tagging').retries == 2
    with pytest.raises(ValueError):
        registry.resolve('unknown')
    scan_models(ROOT)
    for prefix in ('glm', 'gpt', 'claude', 'qwen', 'gemini', 'deepseek', 'llama', 'mistral'):
        p = tmp_path / 'negative.py'
        p.write_text('model=' + repr(prefix.upper() + '-999') + '\n')
        with pytest.raises(AssertionError, match='I37'):
            scan_models(p)


def test_schema_roles_migration(tmp_path):
    from tests.harness.tools.permissions import PermissionMatrix, assert_no_select, assert_no_write
    migration = ROOT / 'migrations/phase1_m0_0001_schemas_roles.sql'
    matrix = PermissionMatrix.from_sql(migration.read_text(), path=migration)
    matrix.validate()
    for schema in ('valuation_v1', 'perception', 'perception_shadow', 'factor_shadow', 'graph'):
        assert_no_select('role_trading', schema, matrix=matrix)
        assert_no_write('role_trading', schema, matrix=matrix)
    for schema in matrix.schemas:
        assert_no_write('role_web', schema, matrix=matrix)
    assert 'INSERT' in matrix.default_tables['role_shadow', 'factor_shadow']
    assert 'SELECT' in matrix.default_tables['role_valuation', 'trading']
    assert_no_write('role_valuation', 'trading', matrix=matrix)
    p = tmp_path / 'bad.sql'
    p.write_text(migration.read_text() + '\nGRANT SELECT ON ALL TABLES IN SCHEMA valuation_v1 TO role_trading;\n')
    with pytest.raises(AssertionError, match='FR-M0-11'):
        PermissionMatrix.from_sql(p.read_text(), path=p).validate()


def test_markers_registered(pytestconfig, tmp_path):
    import tomllib
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text())['tool']['pytest']['ini_options']
    assert '--strict-markers' in config['addopts']
    actual = {m.split(':', 1)[0] for m in config['markers']}
    assert actual == {'phase1_blocking', 'phase1_replay', 'phase1_cases', 'phase1_live'}
    result = run_probe(tmp_path, 'import pytest\n@pytest.mark.not_registered\ndef test_probe():\n    assert True\n')
    assert result.returncode != 0 and 'not_registered' in output(result)
