"""Additional PIT and provenance regressions for real-contract normalization."""

from datetime import date, datetime

import pytest

from tests.m9.fixtures import event

pytestmark = pytest.mark.phase1_blocking


def test_m9_event_eps_baseline_is_specific_to_each_event():
    from inves_cog.shadow.signals import generate_signals

    obs = {
        "WDC": {
            "holding": True,
            "holding_id": "synthetic-position",
            "close": 90,
            "ma50": 100,
            "event_inputs": {"synthetic-E1": {"eps_change_pct": -6}, "E2": {"eps_change_pct": -1}},
        }
    }
    events = [event(lifecycle="已验证·有影响"), event(event_id="E2", lifecycle="已验证·有影响")]
    x1 = [row for row in generate_signals(events, obs, day="2026-10-20", seen=set()) if row["signal"] == "X1"]
    assert [row["event_id"] for row in x1] == ["synthetic-E1"]


def test_m9_segment_core_uses_four_visible_quarters_and_one_axis():
    from inves_cog.shadow.normalization import segment_inputs

    rows = []
    for name, revenues in [("core", [10, 20, 30, 40]), ("other", [1, 2, 3, 4])]:
        for quarter, revenue in enumerate(revenues, 1):
            rows.append(
                {
                    "segment_raw": name,
                    "axis": "ProductAxis",
                    "period_len": "Q",
                    "period_end": date(2025, quarter * 3, 28),
                    "filed": date(2026, 1, 1),
                    "revenue": revenue,
                    "margin_pct": 10,
                    "yoy_pct": 20,
                    "recast_group": None,
                }
            )
    normalized = segment_inputs(rows, asof=date(2026, 2, 1))
    assert len(normalized) == 2 and max(normalized, key=lambda x: sum(x["revenue_4q"]))["name"] == "core"
    assert segment_inputs(rows + [{**rows[-1], "axis": "GeographicAxis"}], asof=date(2026, 2, 1)) is None
    assert (
        segment_inputs(rows + [{**row, "recast_group": "second-definition"} for row in rows], asof=date(2026, 2, 1))
        is None
    )
    assert segment_inputs([{**row, "filed": date(2026, 3, 1)} for row in rows], asof=date(2026, 2, 1)) is None


def test_m9_event_consensus_rejects_late_or_different_fiscal_year():
    from inves_cog.shadow.normalization import event_eps_change

    rows = [
        {
            "ticker": "SYNTH",
            "as_of": date(2026, 10, 1),
            "captured_at": datetime.fromisoformat("2026-10-01T01:00:00Z"),
            "eps_cy": 10,
            "fy_cy": date(2026, 12, 31),
        },
        {
            "ticker": "SYNTH",
            "as_of": date(2026, 10, 20),
            "captured_at": datetime.fromisoformat("2026-10-20T01:00:00Z"),
            "eps_cy": 9,
            "fy_cy": date(2026, 12, 31),
        },
    ]
    args = {
        "event_at": datetime.fromisoformat("2026-10-02T00:00:00Z"),
        "cutoff": datetime.fromisoformat("2026-10-20T12:00:00Z"),
        "asof": date(2026, 10, 20),
    }
    assert event_eps_change(rows, **args) == pytest.approx(-10)
    late = [{**rows[0], "captured_at": datetime.fromisoformat("2026-10-03T00:00:00Z")}, rows[1]]
    assert event_eps_change(late, **args) is None
    assert event_eps_change([rows[0], {**rows[1], "fy_cy": date(2027, 12, 31)}], **args) is None
