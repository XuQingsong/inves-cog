"""A014: local offline scheduling contracts; no services or model calls."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.ops.test_daily_scheduling import frozen

pytestmark = pytest.mark.phase1_blocking


def poll(root, stamp, calls, *, code=0, values=None):
    from scripts.schedule_morning_page import run_once

    def invoke(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=code)

    return run_once(
        root=root,
        python=Path("/fixture/python"),
        clock=frozen(stamp),
        run=invoke,
        load_environment=lambda path: {"FIXTURE_PRIVATE_KEY": "private-value", **(values or {})},
    )


@pytest.mark.parametrize("stamp", ["2026-10-20T01:14:59Z", "2026-11-03T01:15:00Z", "2026-10-19T01:15:00Z"])
def test_morning_poll_outside_slot_does_nothing(tmp_path, stamp):
    from scripts.schedule_morning_page import run_once

    def never(*args, **kwargs):
        pytest.fail("Read credentials or ran morning command outside the slot")

    result = run_once(root=tmp_path / "repo", clock=frozen(stamp), run=never, load_environment=never)
    assert result["status"] == "not_due"
    assert not (tmp_path / "repo/.harness").exists()


@pytest.mark.parametrize("code", [0, 1])
def test_morning_attempt_survives_failure_and_restart(tmp_path, code):
    root, calls = tmp_path / "repo", []
    first = poll(root, "2026-10-20T01:15:00Z", calls, code=code)
    assert first["returncode"] == code
    assert first["status"] == ("ok" if code == 0 else "failed")
    assert poll(root, "2026-10-20T01:15:30Z", calls)["status"] == "already_attempted"
    from scripts import schedule_morning_page

    importlib.reload(schedule_morning_page)
    assert poll(root, "2026-10-20T01:15:59Z", calls)["status"] == "already_attempted"
    assert len(calls) == 1
    assert poll(root, "2026-10-21T01:15:00Z", calls)["status"] == "ok"
    assert len(calls) == 2
    assert len(list((root / ".harness/service").glob("morning-page-*.json"))) == 2


def test_morning_poll_uses_existing_winter_slot(tmp_path):
    calls = []
    assert poll(tmp_path / "repo", "2026-11-03T01:15:00Z", calls)["status"] == "not_due"
    assert poll(tmp_path / "repo", "2026-11-03T02:15:00Z", calls)["status"] == "ok"
    assert len(calls) == 1


def test_morning_child_receives_private_environment_but_never_logs_page(tmp_path, capsys):
    import subprocess

    root, calls = tmp_path / "repo", []
    root.mkdir()
    (root / ".env").write_text("FIXTURE_PRIVATE_KEY=private-value\n")
    from scripts.schedule_morning_page import run_once

    def invoke(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    run_once(root=root, python=Path("/fixture/python"), clock=frozen("2026-10-20T01:15:00Z"), run=invoke)
    command, options = calls[0]
    assert command == ["/fixture/python", "-m", "inves_cog.perception.attribution.morning", "--page-only"]
    assert "--at" not in command and options["cwd"] == root
    assert options["env"]["FIXTURE_PRIVATE_KEY"] == "private-value"
    folder = Path(options["env"]["INVES_COG_PAGE_DIR"])
    assert folder == tmp_path / "daily-pages" and not folder.is_relative_to(root)
    assert options["stdout"] == subprocess.DEVNULL and options["stderr"] == subprocess.DEVNULL
    assert not any(capsys.readouterr())
    assert "private-value" not in next((root / ".harness/service").glob("*.json")).read_text()


def test_morning_rejects_page_directory_inside_repository(tmp_path):
    calls, root = [], tmp_path / "repo"
    result = poll(root, "2026-10-20T01:15:00Z", calls, values={"INVES_COG_PAGE_DIR": str(root / "private-pages")})
    assert result["status"] == "failed" and result["error_type"] == "ValueError"
    assert calls == []
    assert poll(root, "2026-10-20T01:15:30Z", calls)["status"] == "already_attempted"
