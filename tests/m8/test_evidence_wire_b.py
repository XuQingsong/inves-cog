"""PR-B evidence wiring: edges->relations exposure mapping and the T-1 precursor annotation."""

from datetime import date, datetime, timezone

import pytest

_RULES = {
    "mechanism_exposure": {"估值倍数": "概念关联"},
    "connection_exposure": {"业务关系": "直接", "经营传导": "间接", "市场叙事": "概念关联", "市场共振": "概念关联"},
    "include_status": ["候选", "观察到", "有支持", "已确立"],
    "default_exposure": "概念关联",
}

_CUTOFF = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
_OLD = "2026-10-01T00:00:00+00:00"
_NEW = "2026-11-02T00:00:00+00:00"


def _edge(**extra):
    edge = {
        "relation_id": "r1",
        "from_entity": "AAA",
        "to_entity": "BBB",
        "connection_type": "业务关系",
        "mechanism": "需求",
        "status": "观察到",
        "first_discovered_at": _OLD,
    }
    edge.update(extra)
    return edge


@pytest.mark.phase1_blocking
def test_derive_relations_maps_connection_and_mechanism_with_override():
    from inves_cog.perception.attribution.graph_context import derive_relations

    members = [{"ticker": "AAA"}, {"ticker": "BBB"}]
    rows = derive_relations(members, [_edge()], _CUTOFF, mapping=_RULES)
    assert {row["ticker"]: row["exposure"] for row in rows} == {"AAA": "直接", "BBB": "直接"}
    kinds = {
        "业务关系": "直接",
        "经营传导": "间接",
        "市场叙事": "概念关联",
        "市场共振": "概念关联",
        None: "概念关联",
    }
    for connection_type, expected in kinds.items():
        mapped = derive_relations(members, [_edge(connection_type=connection_type)], _CUTOFF, mapping=_RULES)
        assert mapped[0]["exposure"] == expected, connection_type
    valued = derive_relations(
        members, [_edge(connection_type="业务关系", mechanism="估值倍数")], _CUTOFF, mapping=_RULES
    )
    assert valued[0]["exposure"] == "概念关联"


@pytest.mark.phase1_blocking
def test_derive_relations_filters_status_and_pit():
    from inves_cog.perception.attribution.graph_context import derive_relations

    members = [{"ticker": "AAA"}]
    assert derive_relations(members, [_edge(status="驳回")], _CUTOFF, mapping=_RULES) == []
    for status in ("候选", "观察到", "有支持", "已确立"):
        rows = derive_relations(members, [_edge(status=status)], _CUTOFF, mapping=_RULES)
        assert rows and rows[0]["status"] == status
    late = derive_relations(members, [_edge(first_discovered_at=_NEW)], _CUTOFF, mapping=_RULES)
    assert late == []
    assert derive_relations(members, [_edge(first_discovered_at=_OLD)], _CUTOFF, mapping=_RULES)


@pytest.mark.phase1_blocking
def test_derive_relations_keeps_highest_tier_per_member_downstream():
    from inves_cog.perception.attribution.evidence import exposure_gradient
    from inves_cog.perception.attribution.graph_context import derive_relations

    members = [
        {"ticker": "AAA", "resid_z": -3.0},
        {"ticker": "BBB", "resid_z": -1.0},
        {"ticker": "CCC", "resid_z": 2.0},
    ]
    edges = [
        _edge(connection_type="经营传导", relation_id="r1"),
        _edge(connection_type="业务关系", relation_id="r2"),
        _edge(from_entity="CCC", to_entity="XYZ", connection_type="市场共振", relation_id="r3"),
    ]
    rows = derive_relations(members, edges, _CUTOFF, mapping=_RULES)
    by_ticker = {}
    for row in rows:
        by_ticker.setdefault(row["ticker"], []).append(row["exposure"])
    assert by_ticker["AAA"] == ["间接", "直接"] and by_ticker["BBB"] == ["间接", "直接"]
    assert by_ticker["CCC"] == ["概念关联"]
    score = exposure_gradient(members, rows, direction="down")
    assert score == pytest.approx(0.866025, abs=1e-6)


@pytest.mark.phase1_blocking
def test_components_notes_all_candidate_relations():
    from inves_cog.perception.attribution.chain import _components

    anomaly = {
        "started_at": datetime(2026, 10, 29, 13, 30, tzinfo=timezone.utc),
        "ended_at": datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc),
        "direction": "down",
        "members": [
            {"ticker": "AAA", "resid_z": -3.0},
            {"ticker": "BBB", "resid_z": -1.0},
            {"ticker": "CCC", "resid_z": 2.0},
        ],
        "relations": [
            {"ticker": "AAA", "exposure": "直接", "status": "候选"},
            {"ticker": "BBB", "exposure": "间接", "status": "候选"},
            {"ticker": "CCC", "exposure": "概念关联", "status": "候选"},
        ],
    }
    components = _components({"affected": [], "chain": [], "mechanism": "需求"}, anomaly, [])
    assert components["gradient"] == 1.0
    assert components["_notes"]["relation_basis"] == "关系均未经证实（候选）"
    anomaly["relations"][0]["status"] = "观察到"
    components = _components({"affected": [], "chain": [], "mechanism": "需求"}, anomaly, [])
    assert "relation_basis" not in components.get("_notes", {})


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _PrecursorDB:
    def __init__(self, short_rows, occ_rows):
        self.short_rows = short_rows
        self.occ_rows = occ_rows

    def execute(self, statement, params):
        ticker, trade_date = params[0], params[1]
        rows = self.short_rows if "short_volume" in statement else self.occ_rows
        visible = [row for row in rows.get(ticker, []) if row["date"] < trade_date]
        if "short_volume" in statement:
            return _Result(visible[: params[2]])
        grouped = {}
        for row in visible:
            key = (row["date"], row["cp"])
            grouped[key] = grouped.get(key, 0) + row["quantity"]
        return _Result(
            [
                {"date": day, "cp": cp, "quantity": quantity}
                for (day, cp), quantity in sorted(grouped.items(), reverse=True)
            ]
        )


def _flat_series(end_day, count, ratio=0.5, puts=50, calls=100):
    """Slightly varying flat series so the baseline stdev is non-zero."""
    from datetime import timedelta

    rows, occ = [], []
    for offset in range(1, count + 1):
        day = date.fromisoformat(end_day) - timedelta(days=offset)
        jitter = (offset % 3 - 1) * 0.01
        rows.append({"date": day, "short_volume": int((ratio + jitter) * 1000), "total_volume": 1000})
        occ.append({"date": day, "cp": "P", "quantity": puts + (offset % 3 - 1) * 2})
        occ.append({"date": day, "cp": "C", "quantity": calls})
    return sorted(rows, key=lambda row: row["date"], reverse=True), occ


@pytest.mark.phase1_blocking
def test_precursor_uses_only_prior_days_and_flags_z():
    from inves_cog.perception.anomaly.precursor import compute_precursor

    short_rows, occ_rows = _flat_series("2026-10-30", 21)
    t_minus_1 = short_rows[0]["date"]
    trade = date(2026, 10, 30)
    # T-day rows must never feed the annotation even when present.
    short_rows.insert(0, {"date": trade, "short_volume": 1000, "total_volume": 1000})
    occ_rows.extend(
        [
            {"date": trade, "cp": "P", "quantity": 400},
            {"date": trade, "cp": "C", "quantity": 100},
        ]
    )
    # T-1 put/call jumps ~0.5 -> ~2.0 against a flat baseline.
    occ_rows.extend(
        [
            {"date": t_minus_1, "cp": "P", "quantity": 350},
            {"date": t_minus_1, "cp": "C", "quantity": 100},
        ]
    )
    connection = _PrecursorDB({"AAA": short_rows}, {"AAA": occ_rows})
    result = compute_precursor(connection, [{"ticker": "AAA"}], trade, "down", min_baseline=10)
    detail = result["details"][0]
    assert detail["as_of"] == t_minus_1.isoformat()
    assert detail["pc_z"] is not None and detail["pc_z"] >= 2.0
    assert detail["short_z"] is not None and abs(detail["short_z"]) < 2.0
    assert result["members_flagged"] == 1 and result["aligned"] == 1
    up = compute_precursor(connection, [{"ticker": "AAA"}], trade, "up", min_baseline=10)
    assert up["members_flagged"] == 1 and up["aligned"] == 0


@pytest.mark.phase1_blocking
def test_precursor_up_alignment_on_falling_put_call():
    from inves_cog.perception.anomaly.precursor import compute_precursor

    short_rows, occ_rows = _flat_series("2026-10-30", 21)
    t_minus_1 = short_rows[0]["date"]
    occ_rows = [row for row in occ_rows if row["date"] != t_minus_1]
    occ_rows.extend(
        [
            {"date": t_minus_1, "cp": "P", "quantity": 5},
            {"date": t_minus_1, "cp": "C", "quantity": 100},
        ]
    )
    connection = _PrecursorDB({"AAA": short_rows}, {"AAA": occ_rows})
    trade = date(2026, 10, 30)
    up = compute_precursor(connection, [{"ticker": "AAA"}], trade, "up", min_baseline=10)
    assert up["details"][0]["pc_z"] <= -2.0
    assert up["aligned"] == 1
    down = compute_precursor(connection, [{"ticker": "AAA"}], trade, "down", min_baseline=10)
    assert down["aligned"] == 0


@pytest.mark.phase1_blocking
def test_precursor_occ_insufficient_and_line():
    from inves_cog.perception.anomaly.precursor import compute_precursor, precursor_line

    short_rows, _ = _flat_series("2026-10-30", 21)
    connection = _PrecursorDB({"AAA": short_rows, "BBB": short_rows}, {"AAA": [], "BBB": []})
    result = compute_precursor(
        connection, [{"ticker": "AAA"}, {"ticker": "BBB"}], date(2026, 10, 30), "down", min_baseline=10
    )
    assert all(row["occ_missing"] for row in result["details"])
    assert result["details"][0]["notes"] == ["期权数据不足"]
    assert precursor_line(result, 2) == "异动前一日：0/2 只成员场外做空或看跌期权异常（同向 0），期权数据不足"
    flagged = {
        "members_flagged": 3,
        "aligned": 2,
        "details": [{"occ_missing": False}] * 5,
    }
    assert precursor_line(flagged, 5) == "异动前一日：3/5 只成员场外做空或看跌期权异常（同向 2）"
    assert precursor_line(None, 5) is None
    assert precursor_line({"unavailable": "precursor_failed"}, 5) is None


@pytest.mark.phase1_blocking
def test_precursor_annotation_never_enters_candidate_components():
    from inves_cog.perception.attribution.chain import _components

    anomaly = {
        "started_at": datetime(2026, 10, 29, 13, 30, tzinfo=timezone.utc),
        "ended_at": datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc),
        "direction": "down",
        "members": [{"ticker": "AAA", "resid_z": -3.0}],
        "precursor": {"members_flagged": 1, "aligned": 1, "details": []},
    }
    components = _components({"affected": [], "chain": []}, anomaly, [])
    assert "precursor" not in components
    assert set(components) <= {
        "time",
        "gradient",
        "specificity",
        "narrative",
        "magnitude",
        "alternatives",
        "_notes",
    }
