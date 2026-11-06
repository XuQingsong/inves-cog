from pathlib import Path

import pytest

from scripts.install_data_guard import ENV_TEMPLATE, append_program

pytestmark = pytest.mark.phase1_blocking


def test_only_append_named_program_and_preserve_all_others_byte_for_byte():
    existing = "[supervisord]\n[program:pages]\ncommand=server\n[program:review]\ncommand=review\n"
    value = append_program(existing, Path("/tmp/project with space"))
    assert value.startswith(existing)
    assert value.count("[program:data_guard]") == 1
    assert append_program(value, Path("/tmp/project with space")) == value
    assert "update" not in value
    assert "INVES_DATAGUARD_BACKFILL=0" in ENV_TEMPLATE


def test_existing_different_program_is_not_overwritten():
    with pytest.raises(ValueError):
        append_program("[program:data_guard]\ncommand=other\n", Path("/tmp/project"))
