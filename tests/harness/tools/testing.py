"""Run isolated pytest probes without modifying the project or its golden files."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def run_probe(tmp_path, code, *, arguments=(), environment=None):
    folder = tmp_path / f'probe-{len(list(tmp_path.glob("probe-*")))}'
    folder.mkdir()
    probe = folder / 'test_probe.py'
    probe.write_text(code)
    env = dict(os.environ)
    env.update(PYTHONPATH=str(ROOT) + os.pathsep + str(ROOT / 'src'),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', INVES_COG_LIVE='0')
    env.update(environment or {})
    return subprocess.run(
        [sys.executable, '-m', 'pytest', '-p', 'tests.harness.plugin',
         '-c', str(ROOT / 'pyproject.toml'), '--rootdir', str(ROOT),
         str(probe), '-q', *arguments], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=30,
    )


def output(result):
    return result.stdout + result.stderr
