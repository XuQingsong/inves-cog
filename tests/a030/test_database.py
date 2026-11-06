from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.trading.execution.repository import Repository as Plans
from inves_cog.valuation_v1.ceiling_daily import calculate_ceiling
from inves_cog.valuation_v1.repository import Repository
from tests.a030.test_daily import BANDS, inputs
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking


def test_ceiling_writer_upserts_and_plan_read_is_visible_and_read_only():
    host = _disposable_database()
    now = datetime(2026, 11, 6, 4, tzinfo=timezone.utc)
    day = date(2026, 11, 5)
    with psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", autocommit=True, row_factory=dict_row
    ) as db:
        db.execute("DELETE FROM valuation_v1.ceiling_daily WHERE ticker='TEST'")
        try:
            row = calculate_ceiling(inputs(), day=day, kind="稳定", tier="防守", bands=BANDS, asof=now)
            db.execute("SET ROLE role_valuation")
            repo = Repository(db)
            repo.save_ceiling(day, row, now)
            repo.save_ceiling(day, row, now)
            assert (
                db.execute("SELECT count(*) AS n FROM valuation_v1.ceiling_daily WHERE ticker='TEST'").fetchone()["n"]
                == 1
            )
            db.execute("RESET ROLE")
            db.execute("SET ROLE role_trading")
            assert Plans(db).ceiling_notes(day, now - timedelta(seconds=1)) == {}
            assert Plans(db).ceiling_notes(day, now)["TEST"]["m"] == row["m"]
            assert not db.execute(
                "SELECT has_table_privilege(current_user,'valuation_v1.ceiling_daily','INSERT') AS yes"
            ).fetchone()["yes"]
            db.execute("RESET ROLE")
            db.execute("SET ROLE role_web")
            assert (
                db.execute("SELECT payload FROM valuation_v1.ceiling_daily WHERE ticker='TEST'").fetchone()["payload"][
                    "band"
                ]
                == row["band"]
            )
        finally:
            db.execute("RESET ROLE")
            db.execute("DELETE FROM valuation_v1.ceiling_daily WHERE ticker='TEST'")


def test_eps_backfill_uses_business_role_is_idempotent_and_preserves_other_fields():
    from copy import deepcopy

    from inves_cog.ingest.fundamentals.eps_repair import persist_eps_patches, repair_missing_eps
    from inves_cog.ingest.fundamentals.repository import Repository as Financials
    from tests.a030.test_eps_repair import states

    old, new = states()
    old.filed = new.filed = date(2099, 4, 30)
    old.period_end = new.period_end = date(2099, 3, 31)
    new.field_sources["eps_ttm"]["components"][0]["filed"] = "2099-04-30"
    patched = repair_missing_eps(old, new)
    change = dict(
        ticker="V",
        filed=str(old.filed),
        period_end=str(old.period_end),
        eps_ttm=patched.values["eps_ttm"],
        eps_growth=patched.values["eps_growth"],
        field_sources_patch=deepcopy(patched.field_sources),
    )
    host = _disposable_database()
    with psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", autocommit=True, row_factory=dict_row
    ) as db:
        try:
            db.execute("SET ROLE role_ingest")
            Financials(db).put_state(old)
            db.execute("RESET ROLE")
            db.execute("SET ROLE role_web")
            with pytest.raises(ValueError, match="business login"):
                persist_eps_patches(db, [change])
            db.execute("RESET ROLE")
            db.execute("SET ROLE role_ingest")
            assert persist_eps_patches(db, [change])["updated"] == 1
            assert persist_eps_patches(db, [change])["already_present"] == 1
            row = db.execute(
                "SELECT eps_ttm,ni_ttm,cash,field_sources FROM fundamentals.fin_state "
                "WHERE ticker='V' AND extractor='fixed' AND filed=%s",
                (old.filed,),
            ).fetchone()
            assert row["eps_ttm"] == 2.5 and row["ni_ttm"] == 20 and row["cash"] == 1
            assert row["field_sources"]["cash"] == old.field_sources["cash"]
        finally:
            db.execute("RESET ROLE")
            db.execute(
                "DELETE FROM fundamentals.fin_state WHERE ticker='V' AND extractor='fixed' AND filed=%s", (old.filed,)
            )
