import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.harness.tools.testing import ROOT, output, run_probe

pytestmark = pytest.mark.phase1_blocking


def test_harness_no_network(tmp_path):
    from tests.harness.tools.network import NetworkGuard
    assert NetworkGuard
    attempts = (
        'socket.create_connection(("example.com", 80))',
        'socket.create_connection(("127.0.0.1", 1))',
        'socket.create_connection(("::1", 1))',
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
    result = run_probe(tmp_path, 'import socket\ndef test_bar_window_to_20et():\n'
                       '    try:\n        socket.getaddrinfo("example.com", 80)\n'
                       '    except Exception:\n        pass\n    assert False\n')
    assert result.returncode == 1 and 'FR-M0-03' in output(result)
    result = run_probe(tmp_path, 'import pytest\n@pytest.mark.phase1_live\n'
                       'def test_probe(clock):\n    assert clock.__class__.__name__ == "SystemClock"\n',
                       arguments=('-m', 'phase1_live'),
                       environment={'INVES_COG_LIVE': '1', 'CI': ''})
    assert result.returncode == 0, output(result)
    for env in ({'INVES_COG_LIVE': '0'}, {'INVES_COG_LIVE': '1', 'CI': 'true'}):
        result = run_probe(tmp_path, 'def test_probe():\n    assert True\n',
                           arguments=('-m', 'phase1_live'), environment=env)
        assert result.returncode != 0 and 'FR-M0-03' in output(result)
    # The same offline guard must allow asyncio and in-process ASGI requests.
    from tests.harness.tools.probes import LOCAL_COMMUNICATION_PROBES
    failures = []
    for label, code in LOCAL_COMMUNICATION_PROBES.items():
        try:
            result = run_probe(tmp_path, code, arguments=('-s',))
            if result.returncode:
                failures.append(f'{label}: {output(result)}')
        except subprocess.TimeoutExpired:
            failures.append(f'{label}: TIMEOUT after 30 seconds')
    assert not failures, '\n'.join(failures)
    result = run_probe(tmp_path, '''import socket, tempfile
def test_probe():
    # macOS limits AF_UNIX paths to 104 bytes; pytest's nested temp path is longer.
    with tempfile.TemporaryDirectory(dir='/tmp', prefix='m0-') as directory:
        address = directory + '/local.sock'
        with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:
            server.bind(address)
            server.listen(1)
            client.connect(address)
            peer, _ = server.accept()
            with peer:
                client.sendall(b'ok')
                assert peer.recv(2) == b'ok'
''')
    assert result.returncode == 0, output(result)
    for family in ('AF_INET', 'AF_INET6'):
        for method in ('connect', 'connect_ex', 'send', 'sendall', 'sendto', 'sendmsg', 'listen'):
            code = (f'import socket\ndef test_probe():\n'
                    f'    with socket.socket(socket.{family}) as sock:\n'
                    f'        if hasattr(sock, {method!r}):\n'
                    f'            sock.{method}()\n')
            result = run_probe(tmp_path, code)
            assert result.returncode == 1 and 'FR-M0-03' in output(result), output(result)


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
    sources = (
        'from datetime import datetime\nx=datetime.now()',
        'from datetime import datetime as dt\nx=dt.utcnow()',
        'from datetime import date as d\nx=d.today()',
        'import time as t\nx=t.time()',
        'from datetime import datetime\nx=datetime.today()',
        'import datetime as dt\nx=dt.datetime.today()',
        'import time as t\nx=t.time_ns()',
        'from time import time_ns as ns\nf=ns',
        'import pandas as pd\nx=pd.Timestamp.now()',
        'from pandas import Timestamp as TS\nx=TS.today()',
        'import pandas\nx=pandas.Timestamp.utcnow()',
        'from datetime import datetime\nf=datetime.now',
        'import datetime as dt\nf=dt.datetime.now; f()',
        'import pandas as pd\nf=pd.Timestamp.today',
        'import numpy as np\nx=np.datetime64("now")',
        'from numpy import datetime64 as dt64\nx=dt64("today")',
    )
    for source in sources:
        p = tmp_path / 'trading.py'
        p.write_text(source)
        with pytest.raises(AssertionError, match='FR-M0-04'):
            scan_clock(p)
    p.write_text('import time as t\nx=t.monotonic(); y=t.perf_counter()\n'
                 'import numpy as np\nx=np.datetime64("2026-10-13")\n')
    scan_clock(p)


def test_pending_registry(tmp_path):
    from tests.harness.tools.checks import requirement_tests, validate_registry
    rows, defined = validate_registry(ROOT)
    required = requirement_tests(ROOT)
    assert set(rows) | defined == set(required)
    assert not any(module == 'M0' for module in rows.values())
    # Probe input stays pending even after the real module graduates.
    source = ''.join(f'{name} | {module} | fixture pending\n'
                     for name, module in required.items() if module != 'M0')
    closed = tmp_path / 'milestones.txt'
    closed.write_text('M0\n')
    pending = tmp_path / 'probe-pending.txt'
    pending.write_text(source)
    validate_registry(ROOT, pending_path=pending, milestones_path=closed)
    for content in (source + source.splitlines()[0] + '\n',
                    source + 'broken line\n',
                    source + 'test_unknown | M99 | missing\n'):
        p = tmp_path / 'pending.txt'
        p.write_text(content)
        with pytest.raises(AssertionError, match='FR-M0-05'):
            validate_registry(ROOT, pending_path=p, milestones_path=closed)
    for body, status in (('assert False', 0), ('assert True', 1)):
        result = run_probe(tmp_path, f'def test_bar_window_to_20et():\n    {body}\n',
                           arguments=('--harness-pending', str(pending),
                                      '--harness-milestones', str(closed)))
        assert result.returncode == status, output(result)
        assert ('xfailed' if status == 0 else '已转绿，请从 pending 删除') in output(result)
    for decoration in ('skip', 'xfail'):
        result = run_probe(tmp_path, 'import pytest\n@pytest.mark.' + decoration +
                           '\ndef test_probe():\n    assert False\n')
        assert result.returncode != 0 and 'FR-M0-05' in output(result)
    result = run_probe(tmp_path, 'import pytest\ndef test_probe():\n    pytest.skip("hidden")\n')
    assert result.returncode == 1 and 'FR-M0-05' in output(result)


def test_milestones_consistency(tmp_path):
    from tests.harness.tools.checks import validate_registry, requirement_tests
    validate_registry(ROOT)
    # Isolated data makes both negatives independent of actual module progress.
    copied = tmp_path / 'registry'
    shutil.copytree(ROOT / 'docs/phase1', copied / 'docs/phase1')
    required = requirement_tests(copied)
    closed = tmp_path / 'milestones.txt'
    closed.write_text('M1\n')
    pending = tmp_path / 'pending.txt'
    pending.write_text(''.join(f'{name} | {module} | fixture pending\n'
                               for name, module in required.items() if module != 'M0'))
    with pytest.raises(AssertionError, match='FR-M0-05'):
        validate_registry(copied, pending_path=pending, milestones_path=closed)
    pending.write_text(''.join(f'{name} | {module} | fixture pending\n'
                               for name, module in required.items() if module not in {'M0', 'M1'}))
    with pytest.raises(AssertionError, match='FR-M0-05'):
        validate_registry(copied, pending_path=pending, milestones_path=closed)
    tests = copied / 'tests'
    tests.mkdir()
    (tests / 'test_complete.py').write_text(''.join(f'def {name}(): pass\n'
                                                  for name, module in required.items() if module in {'M0', 'M1'}))
    validate_registry(copied, pending_path=pending, milestones_path=closed)


def test_requirements_golden_unchanged(tmp_path):
    from tests.harness.tools.golden import load_golden, read_manifest, validate_golden
    real = ROOT / 'docs/phase1/golden'
    original = {str(p.relative_to(real)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in real.rglob('*') if p.is_file()}
    rows = read_manifest(real, 'FR-M0-07')
    assert validate_golden(real) == rows
    for name in rows:
        value = load_golden(name)
        assert value == (json.loads((real / name).read_text()) if Path(name).suffix == '.json'
                         else (real / name).read_bytes())
    copied = tmp_path / 'golden'
    shutil.copytree(real, copied)
    name = next(iter(rows))
    p = copied / name
    p.write_bytes(p.read_bytes() + b' ')
    with pytest.raises(AssertionError, match='FR-M0-07'):
        validate_golden(copied)
    p.write_bytes((real / name).read_bytes())
    (copied / 'extra.json').write_text('{}')
    with pytest.raises(AssertionError, match='FR-M0-07'):
        validate_golden(copied)
    (copied / 'extra.json').unlink()
    extra = copied / 'additional.bin'
    extra.write_bytes(b'\x00\xffadditional golden\n')
    digest = hashlib.sha256(extra.read_bytes()).hexdigest()
    manifest = copied / 'MANIFEST.sha256'
    manifest.write_text(manifest.read_text().rstrip('\n') + f'\n{digest}  {extra.name}\n')
    assert validate_golden(copied) == rows | {extra.name: digest}
    assert load_golden(extra.name, copied) == extra.read_bytes()
    assert original == {str(p.relative_to(real)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in real.rglob('*') if p.is_file()}
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
    from tests.harness.tools.style import check_style
    clean = tmp_path / 'clean.py'
    clean.write_text('a = 1\nb = 2\n')
    check_style(ROOT, paths=[clean])
    clean.write_text('a=1;b=2\n')
    with pytest.raises(AssertionError, match='RUFF'):
        check_style(ROOT, paths=[clean])
    check_style(ROOT)
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
    for prefix in ('glm', 'gpt', 'claude', 'qwen', 'gemini', 'deepseek', 'llama', 'mistral'):
        p = tmp_path / 'negative.py'
        p.write_text('model=' + repr(prefix.upper() + '-999') + '\n')
        with pytest.raises(AssertionError, match='I37'):
            scan_models(p)
    directory = tmp_path / 'repository'
    for name in ('Dockerfile.x', 'scripts/Dockerfile.harness', 'Makefile', '.env', '.env.test',
                 'config/a.txt', 'config/a.ini', 'config/a.cfg', 'src/a.md',
                 'tests/a.data', '.github/workflows/a.yaml', 'docker-compose.test.yml'):
        p = directory / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('model=' + 'glm' + '-999' + '\n')
        with pytest.raises(AssertionError, match='I37') as error:
            scan_models(directory)
        assert str(p) + ':1:' in str(error.value)
        p.unlink()
    (directory / 'config/binary.bin').write_bytes(b'\x00\xff' + b'glm' + b'-999')
    recording = directory / 'tests/recordings/a.json'
    recording.parent.mkdir(parents=True)
    recording.write_text(json.dumps({'response': 'glm' + '-999'}))
    (directory / '.env').write_text('MODEL=glm-5.3\n')
    (directory / 'config/allowed.txt').write_text('MODEL=deepseek-v4.1-flash\n')
    website = directory / 'config/websites.txt'
    website.write_text('https://www.deepseek.com/\nhttps://claude.ai/\n'
                       'https://gemini.google.com:443/about\n')
    scan_models(directory)
    illegal = 'deepseek' + '-chat'
    for content in (f'MODEL={illegal}\n', f'https://deepseek.com/models/{illegal}\n',
                    f'https://deepseek.com/?model={illegal}\n',
                    f'https://{illegal}.example.com/\n',
                    f'https://deepseek.com/#{illegal}\n',
                    'MODEL=' + 'deepseek' + '.com\n'):
        website.write_text(content)
        with pytest.raises(AssertionError, match='I37'):
            scan_models(directory)
    website.write_text('https://www.deepseek.com/\n')
    scan_models(directory)
    scan_models(ROOT)


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
