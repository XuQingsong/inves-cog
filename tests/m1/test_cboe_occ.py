from datetime import date

import pytest


@pytest.mark.phase1_blocking
def test_occ_statistics_aggregates_categories():
    from inves_cog.ingest.adapters import occ_statistics

    rows = [
        {"underlying": "NVDA", "cp": "C", "q": 100},
        {"underlying": "NVDA", "cp": "P", "q": 50},
        {"underlying": "SPX", "cp": "C", "q": 400},
        {"underlying": "SPX", "cp": "P", "q": 200},
        {"underlying": "SPY", "cp": "C", "q": 300},
        {"underlying": "SPY", "cp": "P", "q": 150},
    ]

    class C:
        def execute(self, sql, params):
            class R:
                def fetchall(self):
                    return rows

            return R()

    out = {r["category"]: r for r in occ_statistics(C(), date(2026, 11, 6))}
    assert out["total"]["call_volume"] == 800 and out["total"]["put_volume"] == 400
    assert out["index"]["call_volume"] == 400 and out["index"]["put_call_ratio"] == 0.5
    assert out["etf"]["call_volume"] == 300
    assert out["equity"]["call_volume"] == 100
    assert all(r["source"] == "OCC" for r in out.values())
