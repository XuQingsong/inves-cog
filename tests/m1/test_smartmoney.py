import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from inves_cog.perception.smartmoney import money_flow


class FakeConn:
    """Rows are dicts, matching the production dict_row connections."""

    def __init__(self, form4=(), short_vol=(), bars=(), si=(), shares=None, f13=()):
        self._form4 = list(form4)
        self._map = {
            "flows.short_volume": list(short_vol),
            "bars_daily": list(bars),
            "ingest.short_interest": list(si),
            "fin_state": list(shares or []),
            "ingest.f13_holdings": list(f13 or []),
        }

    def execute(self, sql, params=()):
        if "form4_events" in sql:
            as_of = params[1]
            keys = (
                "insider_name officer_title is_director aff10b5_one transaction_code shares price amount filed_at"
            ).split()
            return _Result([dict(zip(keys, r, strict=True)) for r in self._form4 if r[8] <= as_of])
        if "ingest.f13_holdings" in sql:
            return _Result([r for r in self._map["ingest.f13_holdings"] if r["filing_date"] <= params[1]])
        for key, rows in self._map.items():
            if key in sql:
                return _Result(rows)
        raise AssertionError(f"unexpected query: {sql[:80]}")


class _Result(list):
    def fetchall(self):
        return list(self)

    def fetchone(self):
        return self[0] if self else None


def _f4(name, title, director, plan, code, shares, price, amount, filed):
    return (name, title, director, plan, code, shares, price, amount, filed)


def _sv(day, total):
    return {"date": day, "total_volume": total}


def _bar(day, close, adj=1.0):
    return {"trade_date": day, "close": close, "adj_factor": adj}


def _si(settlement, publish, short, dtc):
    return {"settlement_date": settlement, "publish_date": publish, "short_interest": short, "days_to_cover": dtc}


DAY = date(2026, 11, 9)


@pytest.mark.phase1_blocking
def test_ps_only_and_excluded_count():
    conn = FakeConn(
        form4=[
            _f4("A Doe", "CFO", False, False, "S", 10, 100.0, 1000.0, DAY),
            _f4("A Doe", "CFO", False, False, "P", 5, 50.0, 250.0, DAY),
            _f4("A Doe", "CFO", False, None, "G", 999, 0.0, None, DAY),
            _f4("B Roe", None, True, None, "A", 1, 1.0, None, DAY),
        ]
    )
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["excluded_count"] == 2  # G + A counted as excluded, not as amounts
    assert ins["totals"]["buys"]["usd"] == 250.0
    assert ins["totals"]["unplanned"]["usd"] == 1000.0


@pytest.mark.phase1_blocking
def test_unknown_plan_not_counted_as_unplanned():
    conn = FakeConn(form4=[_f4("A Doe", "CFO", False, None, "S", 10, 1.0, 20_000_000.0, DAY)])
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["totals"]["unknown_plan"]["usd"] == 20_000_000.0
    assert ins["totals"]["unplanned"]["usd"] == 0.0
    assert ins["label"] == "中性"  # NULL plan must not trigger 偏空


@pytest.mark.phase1_blocking
def test_label_thresholds():
    bullish = FakeConn(form4=[_f4("A", "t", False, None, "P", 1, 1.0, 1_500_000.0, DAY)])
    assert money_flow(bullish, "T", DAY, params={})["insiders"]["label"] == "偏多"
    bearish = FakeConn(form4=[_f4("A", "t", False, False, "S", 1, 1.0, 15_000_000.0, DAY)])
    assert money_flow(bearish, "T", DAY, params={})["insiders"]["label"] == "偏空"
    below = FakeConn(form4=[_f4("A", "t", False, False, "S", 1, 1.0, 9_000_000.0, DAY)])
    assert money_flow(below, "T", DAY, params={})["insiders"]["label"] == "中性"


@pytest.mark.phase1_blocking
def test_pit_cutoff_excludes_later_filings():
    conn = FakeConn(
        form4=[
            _f4("Old", "t", False, False, "S", 1, 1.0, 1000.0, date(2026, 10, 1)),
            _f4("New", "t", False, False, "S", 1, 1.0, 20_000_000.0, date(2026, 11, 10)),
        ]
    )
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["totals"]["unplanned"]["usd"] == 1000.0  # 11-10 filing is after as_of
    assert ins["label"] == "中性"


@pytest.mark.phase1_blocking
def test_missing_blocks_say_why():
    out = money_flow(FakeConn(), "T", DAY, params={})
    assert out["insiders"]["missing"]
    assert out["offexchange"]["missing"] == "该股不在 FINRA 返回中"
    assert out["short"]["missing"] == "无 FINRA 持仓记录"


@pytest.mark.phase1_blocking
def test_short_visibility_uses_publish_date():
    si = [_si(date(2026, 10, 15), date(2026, 11, 30), 100.0, 2.0)]
    out = money_flow(FakeConn(si=si), "T", date(2026, 10, 28), params={})
    assert out["short"]["missing"] == "无 FINRA 持仓记录"
    out2 = money_flow(FakeConn(si=si), "T", date(2026, 12, 1), params={})
    assert out2["short"]["missing"] is None
    assert out2["short"]["latest"]["publish_inferred"] is False
    si_null = [_si(date(2026, 10, 15), None, 100.0, 2.0)]
    out3 = money_flow(FakeConn(si=si_null), "T", date(2026, 12, 1), params={})
    assert out3["short"]["latest"]["publish_inferred"] is True


@pytest.mark.phase1_blocking
def test_offexchange_label():
    from datetime import timedelta

    days = [date(2026, 10, 5) + timedelta(days=i) for i in range(25)]
    conn = FakeConn(
        short_vol=[_sv(d, 100.0) for d in days],
        bars=[_bar(d, 10.0) for d in days],
    )
    out = money_flow(conn, "T", DAY, params={})["offexchange"]
    assert out["label"] == "正常"
    assert out["latest_amount"] == 1000.0


@pytest.mark.phase1_blocking
def test_rule_a_does_not_import_smartmoney():
    offenders = []
    for path in Path("src/inves_cog/trading").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any("smartmoney" in n for n in names):
                offenders.append(str(path))
    assert not offenders, f"trading imports smartmoney: {offenders}"


@pytest.mark.phase1_blocking
def test_offexchange_insufficient_history_shows_no_ratio():
    days = [date(2026, 10, 20) + timedelta(days=i) for i in range(7)]
    conn = FakeConn(short_vol=[_sv(d, 100.0) for d in days], bars=[_bar(d, 10.0) for d in days])
    out = money_flow(conn, "T", DAY, params={})["offexchange"]
    assert out["insufficient"] is True
    assert out["ratio"] is None
    assert "数据自" in out["as_of_note"]


@pytest.mark.phase1_blocking
def test_summary_sentence_from_labels():
    days = [date(2026, 10, 5) + timedelta(days=i) for i in range(25)]
    conn = FakeConn(
        form4=[_f4("A", "t", False, False, "S", 1, 1.0, 15_000_000.0, DAY)],
        short_vol=[_sv(d, 100.0) for d in days],
        bars=[_bar(d, 10.0) for d in days],
        si=[
            _si(date(2026, 10, 15), date(2026, 10, 20), 100.0, 2.0),
            _si(date(2026, 9, 30), date(2026, 10, 5), 99.0, 2.0),
        ],
    )
    out = money_flow(conn, "T", DAY, params={})
    assert "内部人偏空" in out["summary"] and "无明显变化" in out["summary"]
    out2 = money_flow(FakeConn(), "T", DAY, params={})
    assert "暂缺" in out2["summary"]


def _f13(period, fd, cik, name, shares, pc=None, value=None):
    return {
        "period": period,
        "filing_date": fd,
        "filer_cik": cik,
        "filer_name": name,
        "shares": shares,
        "value": value if value is not None else shares * 100,
        "put_call": pc,
    }


@pytest.mark.phase1_blocking
def test_institutions_multi_row_and_options():
    from inves_cog.perception.smartmoney import institutions

    f13 = [
        _f13(date(2026, 6, 30), date(2026, 8, 15), "C1", "Fund One", 100),
        _f13(date(2026, 6, 30), date(2026, 8, 15), "C1", "Fund One", 50),  # other-manager row merges
        _f13(date(2026, 6, 30), date(2026, 8, 15), "C1", "Fund One", 999, "Put"),  # option leg excluded
        _f13(date(2026, 6, 30), date(2026, 8, 15), "C2", "Fund Two", 80),
    ]
    out = institutions(FakeConn(f13=f13), "T", DAY, params={})
    assert out["holders"][0]["shares"] == 150  # common rows summed
    assert out["holders"][0]["options"] == 1  # put leg counted separately


@pytest.mark.phase1_blocking
def test_institutions_pit_and_newcomer():
    from inves_cog.perception.smartmoney import institutions

    f13 = [
        _f13(date(2026, 6, 30), date(2026, 8, 15), "C1", "Fund One", 100),
        _f13(date(2026, 3, 31), date(2026, 5, 15), "C1", "Fund One", 90),
        _f13(date(2026, 9, 30), date(2026, 12, 1), "C1", "Fund One", 200),  # after as_of
    ]
    out = institutions(FakeConn(f13=f13), "T", DAY, params={})
    assert out["period"] == date(2026, 6, 30)  # 12-01 filing not yet visible
    assert out["holders"][0]["change_pct"] == pytest.approx((100 - 90) / 90 * 100)
    out2 = institutions(FakeConn(f13=[]), "T", DAY, params={})
    assert out2["missing"] == "无 13F 持仓记录"


@pytest.mark.phase1_blocking
def test_institutions_filing_anomaly_excluded():
    from inves_cog.perception.smartmoney import institutions

    period = date(2026, 6, 30)
    f13 = [
        _f13(period, date(2026, 8, 15), "C1", "Normal Fund", 150, value=15000),  # implied 100 ≈ close
        _f13(period, date(2026, 8, 15), "C2", "Glitch Fund", 10**9, value=1000),  # implied ~0 → anomaly
    ]
    bars = [_bar(period - timedelta(days=i), 100.0) for i in range(3)]
    out = institutions(FakeConn(f13=f13, bars=bars), "T", DAY, params={})
    assert out["anomalies"] == ["Glitch Fund"]
    assert [h["name"] for h in out["holders"]] == ["Normal Fund"]


@pytest.mark.phase1_blocking
def test_institutions_unit_error_corrected_not_excluded():
    from inves_cog.perception.smartmoney import institutions

    period = date(2026, 6, 30)
    f13 = [
        _f13(period, date(2026, 8, 15), "C1", "Normal Fund", 150, value=15000),
        _f13(period, date(2026, 8, 15), "C2", "Kilo Fund", 200, value=20),  # implied $0.1? -> 20*?
        _f13(period, date(2026, 8, 15), "C3", "Glitch Fund", 10**9, value=1000),
    ]
    bars = [_bar(period, 100.0)]
    # Kilo: 20/200=0.1 vs close 100 -> ratio 0.001 -> unit band -> corrected
    # Glitch: 1000/1e9 ~ 1e-6 vs 100 -> 1e-8 -> excluded
    out = institutions(FakeConn(f13=f13, bars=bars), "T", DAY, params={})
    assert out["unit_fixed"] == 1
    assert out["anomalies"] == ["Glitch Fund"]
    assert [h["name"] for h in out["holders"]][0] == "Kilo Fund"
