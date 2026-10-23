import json

from tests.harness.tools.testing import ROOT


def test_clean_env_bootstrap():
    record = json.loads((ROOT / ".harness/bootstrap.json").read_text())
    assert record["python_version"].startswith("3.11.")
    assert record["lock_frozen"] is True
    assert record["database"] == "inves_cog"
    assert record["database_user"] == "inves_cog_admin"
    assert int(record["postgres_version"]) >= 150000
    assert record["pgvector_version"]
    expected = sorted(path.name for path in (ROOT / "migrations").glob("*.sql"))
    assert "phase1_m0_0001_schemas_roles.sql" in expected
    assert record["migrations"] == expected
    assert record["temporary_database"] is True
    assert record["clean_container"] is True


def test_blocking_duration():
    record = json.loads((ROOT / ".harness/blocking.json").read_text())
    assert record["mark"] == "phase1_blocking"
    assert record["exit_code"] == 0
    assert record["collected"] >= 10
    assert record["duration_seconds"] <= 300
