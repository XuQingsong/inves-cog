"""Shadow-vs-Rule-A comparison report: counting, counterfactuals, PIT, page labels."""

import ast
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from inves_cog.valuation_v1.shadow_report import divergence_counts, shadow_report

pytestmark = pytest.mark.phase1_blocking

UTC = ZoneInfo("UTC")
AS_OF = date(2026, 11, 10)
CUTOFF = datetime(2026, 11, 11, 1, 0, tzinfo=UTC)
D1, D2 = date(2026, 11, 2), date(2026, 11, 3)
SEEN = datetime(2026, 11, 4, 3, 35, tzinfo=UTC)
LATE = datetime(2026, 11, 12, 3, 35, tzinfo=UTC)


class _Rows:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return next(iter(self._rows), None)


class Conn:
    """Routes shadow_report queries by their FROM clause and applies the bound params."""

    def __init__(self, **tables):
        self.tables = {name: list(rows) for name, rows in tables.items()}
        self.queries = []

    def execute(self, sql, params=()):
        text = " ".join(sql.split())
        self.queries.append((text, params))
        if "count(*) FILTER" in text:
            day, cutoff = params
            rows = [
                row
                for row in self.tables.get("factors", [])
                if str(row["date"]) == str(day) and row["generated_at"] < cutoff
            ]
            evaluated = sum(1 for row in rows if row["would_pass"] is not None and row["rule_a_entry_pass"] is not None)
            divergent = sum(
                1
                for row in rows
                if row["would_pass"] is not None
                and row["rule_a_entry_pass"] is not None
                and row["would_pass"] != row["rule_a_entry_pass"]
            )
            unevaluable = sum(1 for row in rows if row["would_pass"] is None or row["rule_a_entry_pass"] is None)
            return _Rows([{"evaluated": evaluated, "divergent": divergent, "unevaluable": unevaluable}])
        if "DISTINCT trade_date FROM valuation_v1.shadow_rules" in text:
            as_of, limit = params
            days = sorted(
                {row["trade_date"] for row in self.tables.get("shadows", []) if row["trade_date"] <= as_of},
                reverse=True,
            )[:limit]
            return _Rows([{"trade_date": day} for day in days])
        if "FROM valuation_v1.shadow_rules" in text:
            days, cutoff = params
            return _Rows(
                [
                    row
                    for row in self.tables.get("shadows", [])
                    if row["trade_date"] in days and row["observed_at"] <= cutoff
                ]
            )
        if "FROM trading.orders" in text:
            return _Rows([row for row in self.tables.get("orders", []) if row["trade_date"] in params[0]])
        if "FROM trading.ledger" in text:
            days, cutoff = params
            return _Rows(
                [
                    row
                    for row in self.tables.get("positions", [])
                    if row["trade_date"] in days and row["observed_at"] <= cutoff
                ]
            )
        if "FROM factor_shadow.daily" in text:
            days, cutoff = params
            return _Rows(
                [row for row in self.tables.get("factors", []) if row["date"] in days and row["generated_at"] <= cutoff]
            )
        if "FROM trading.plan" in text:
            return _Rows([row for row in self.tables.get("plans", []) if row["trade_date"] in params[0]])
        if "FROM trading.daily_scores" in text:
            return _Rows([row for row in self.tables.get("scores", []) if str(row["signal_date"]) in params[0]])
        if "FROM ingest.bars_daily" in text:
            tickers, as_of, floor = params
            return _Rows(
                [
                    row
                    for row in self.tables.get("bars", [])
                    if row["ticker"] in tickers and floor < row["trade_date"] <= as_of
                ]
            )
        raise AssertionError(f"unstubbed query: {text}")


def _shadow(ticker, day=D1, *, observed_at=SEEN, **flags):
    row = {
        "trade_date": day,
        "ticker": ticker,
        "vt1": False,
        "vt2": False,
        "v1_score": None,
        "v2_coef": None,
        "v3_trim_flag": False,
        "observed_at": observed_at,
    }
    row.update(flags)
    return row


def _order(ticker, day, action, *, status="filled", qty=None, fill=None, reason="确认加仓"):
    return {
        "trade_date": day,
        "ticker": ticker,
        "status": status,
        "qty": qty,
        "fill_price": fill,
        "reason_zh": reason,
        "action": action,
        "label": None,
    }


def _factor(ticker, day=D1, *, factor_id="F-01", would_pass=None, entry_pass=None, generated_at=SEEN, value=None):
    return {
        "date": day,
        "ticker": ticker,
        "factor_id": factor_id,
        "would_pass": would_pass,
        "rule_a_entry_pass": entry_pass,
        "value": value,
        "substituted_value": value,
        "gap_detail": {},
        "generated_at": generated_at,
    }


def _bar(ticker, day, *, open_=None, close=None):
    return {"ticker": ticker, "trade_date": day, "open": open_, "close": close}


def _position(ticker, day, shares):
    return {"trade_date": day, "ticker": ticker, "shares": shares, "observed_at": SEEN}


def test_divergence_count_excludes_null_and_reports_unevaluable():
    conn = Conn(
        factors=[
            _factor("PLTR", would_pass=False, entry_pass=True),
            _factor("AMD", would_pass=True, entry_pass=True),  # agreement, not divergence
            _factor("ZS", factor_id="F-03", would_pass=None, entry_pass=False),  # shadow cannot evaluate
            _factor("LATE", would_pass=False, entry_pass=True, generated_at=LATE),  # past cutoff
        ]
    )
    counts = divergence_counts(conn, D1, CUTOFF)
    assert counts == {"evaluated": 2, "divergent": 1, "unevaluable": 1}
    sql = conn.queries[0][0]
    assert "would_pass IS NOT NULL" in sql and "rule_a_entry_pass IS NOT NULL" in sql
    assert "IS DISTINCT FROM" not in sql


def test_blocked_buy_hypothetical_uses_latest_close():
    conn = Conn(
        shadows=[_shadow("MU", vt1=True)],
        orders=[_order("MU", D1, "buy_to", qty=8, fill=890.5, reason="M-40 确认加仓")],
        factors=[],
        positions=[],
        plans=[],
        scores=[],
        bars=[_bar("MU", D1, open_=880, close=885), _bar("MU", AS_OF, open_=795, close=800)],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    (row,) = report["blocked_buys"]
    assert row["ticker"] == "MU" and row["sold_on"] is None and row["end_price"] == 800
    assert row["delta_usd"] == pytest.approx(8 * (890.5 - 800))
    assert row["delta_pct"] == pytest.approx((890.5 - 800) / 890.5 * 100)
    assert report["summary"]["blocked_delta_usd"] == pytest.approx(row["delta_usd"])


def test_blocked_buy_stops_at_later_actual_sell():
    sold = date(2026, 11, 6)
    conn = Conn(
        shadows=[_shadow("MU", vt1=True), _shadow("AMD", sold)],
        orders=[
            _order("MU", D1, "buy_to", qty=8, fill=890.5),
            _order("MU", sold, "sell_all", qty=8, fill=850.0, reason="破位减仓"),
        ],
        factors=[],
        positions=[],
        plans=[],
        scores=[],
        bars=[_bar("MU", AS_OF, open_=795, close=800)],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    (row,) = report["blocked_buys"]
    assert row["sold_on"] == str(sold) and row["end_price"] == 850.0
    assert row["delta_usd"] == pytest.approx(8 * (890.5 - 850.0))


def test_missed_trim_hypothetical_and_held_only():
    conn = Conn(
        shadows=[_shadow("GOOGL", D2, v3_trim_flag=True), _shadow("XXX", D2, v3_trim_flag=True)],
        orders=[],
        factors=[],
        positions=[_position("GOOGL", D2, 90)],  # XXX is not held and must drop out
        plans=[],
        scores=[],
        bars=[
            _bar("GOOGL", D2, open_=295, close=298),
            _bar("GOOGL", date(2026, 11, 4), open_=300, close=290),
            _bar("GOOGL", AS_OF, open_=255, close=250),
        ],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    (row,) = report["missed_trims"]
    assert row["ticker"] == "GOOGL" and row["trim_shares"] == pytest.approx(30)
    assert row["open_date"] == "2026-11-04" and row["open_price"] == 300
    assert row["delta_usd"] == pytest.approx(30 * (300 - 250))
    assert all(item["ticker"] != "XXX" for item in report["missed_trims"])


def test_missed_trim_skips_days_rule_a_sold():
    conn = Conn(
        shadows=[_shadow("GOOGL", D2, v3_trim_flag=True)],
        orders=[_order("GOOGL", D2, "sell_frac", status="filled", qty=10, fill=310)],
        factors=[],
        positions=[_position("GOOGL", D2, 90)],
        plans=[],
        scores=[],
        bars=[_bar("GOOGL", date(2026, 11, 4), open_=300, close=290)],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    assert report["missed_trims"] == []


def test_pit_cutoff_excludes_late_shadow_and_factor_rows():
    conn = Conn(
        shadows=[_shadow("LATE", D2, vt1=True, observed_at=LATE)],
        orders=[_order("LATE", D2, "buy_to", qty=1, fill=10.0)],
        factors=[_factor("LATE", D2, would_pass=False, entry_pass=True, generated_at=LATE)],
        positions=[],
        plans=[],
        scores=[],
        bars=[],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    assert report["blocked_buys"] == [] and report["entry_divergence"] == []
    # The cutoff flows into every PIT-scoped query.
    pit_queries = [q for q in conn.queries if "observed_at <=" in q[0] or "generated_at <=" in q[0]]
    assert pit_queries and all(params[-1] == CUTOFF for _, params in pit_queries)


def test_entry_divergence_collapses_to_one_row_per_ticker():
    conn = Conn(
        shadows=[_shadow("PLTR"), _shadow("PLTR", D2)],
        orders=[],
        factors=[
            _factor("PLTR", D1, would_pass=False, entry_pass=True, value={"value": 44.2}),
            _factor("PLTR", D2, would_pass=False, entry_pass=True, value={"value": 50.5}),
            _factor("ZS", factor_id="F-03", would_pass=None, entry_pass=False),
        ],
        positions=[],
        plans=[
            {"trade_date": D1, "signal_date": date(2026, 10, 31)},
            {"trade_date": D2, "signal_date": date(2026, 11, 2)},
        ],
        scores=[
            {
                "signal_date": date(2026, 10, 31),
                "ticker": "PLTR",
                "tier": "attack",
                "entry_pass": True,
                "valuation": 17.2,
                "growth": None,
                "quality": None,
                "timing": None,
                "m31_adjusted_valuation": 44.2,
            },
            {
                "signal_date": date(2026, 11, 2),
                "ticker": "PLTR",
                "tier": "attack",
                "entry_pass": True,
                "valuation": 20.0,
                "growth": None,
                "quality": None,
                "timing": None,
                "m31_adjusted_valuation": 50.5,
            },
        ],
        bars=[],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    (row,) = report["entry_divergence"]
    assert row["ticker"] == "PLTR" and row["direction"] == "影子拒绝、规则 A 放行"
    assert row["first_date"] == str(D1) and row["days"] == 2
    # Latest record day's evidence, not the earliest.
    assert row["factor_label"] == "成长调整估值" and "F-01" not in row["factor_label"]
    assert row["book_label"] == "估值账" and row["tier_label"] == "进攻层"
    assert row["shadow_value"] == pytest.approx(50.5) and row["rule_effective_value"] == pytest.approx(50.5)
    assert report["summary"]["entry_divergence"] == 1
    assert report["summary"]["entry_divergence_days"] == 2


def test_account_section_hides_internal_identifiers():
    conn = Conn(
        shadows=[_shadow("MU", vt1=True), _shadow("CAT", v3_trim_flag=True)],
        orders=[_order("MU", D1, "buy_to", qty=8, fill=890.5, reason="M-40 确认加仓")],
        factors=[_factor("PLTR", would_pass=False, entry_pass=True, value={"value": 44.2})],
        positions=[_position("CAT", D1, 49)],
        plans=[{"trade_date": D1, "signal_date": date(2026, 10, 31)}],
        scores=[],
        bars=[
            _bar("MU", AS_OF, open_=795, close=800),
            _bar("CAT", D2, open_=618.94, close=600),
            _bar("CAT", AS_OF, open_=570, close=571.82),
        ],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    from inves_cog.web.investor_html import _account

    html = _account({"shadow_report": report, "holdings": []})
    banned = re.compile(r"M-\d+|V-T\d|F-\d{2}|\bvt1\b|\bvt2\b|\bv3\b|v3_trim|entry_pass|would_pass")
    assert not banned.search(html), banned.search(html).group()
    assert "影子规则只做记录，不影响规则 A 实际订单" in html
    assert "影子未定义仓位，不计收益差" in html
    assert "已于" not in html or "卖出" in html


def test_shadow_section_wording_and_rounded_trim_shares():
    conn = Conn(
        shadows=[_shadow("CAT", v3_trim_flag=True), _shadow("MU", v3_trim_flag=True)],
        orders=[],
        factors=[],
        positions=[_position("CAT", D1, 49), _position("MU", D1, 101)],
        plans=[],
        scores=[],
        bars=[
            _bar("CAT", D2, open_=618.94, close=600),
            _bar("CAT", AS_OF, open_=570, close=571.82),
            _bar("MU", D2, open_=859.93, close=800),
            _bar("MU", AS_OF, open_=708, close=708.35),
        ],
    )
    report = shadow_report(conn, AS_OF, days=20, cutoff=CUTOFF)
    from inves_cog.web.investor_html import _account

    html = _account({"shadow_report": report, "holdings": []})
    # 49/3 = 16.33 → display rounds to "约 16 股（1/3）"; math keeps exact shares.
    cat = next(row for row in report["missed_trims"] if row["ticker"] == "CAT")
    assert cat["trim_shares"] == pytest.approx(49 / 3)
    assert "减持约 16 股（1/3）" in html and "减持约 34 股（1/3）" in html
    assert "按影子减持可少亏" in html or "按影子减持会少赚" in html
    assert "至今多" not in html and "至今少 $" not in html


def test_rule_a_does_not_read_shadow_report():
    offenders = []
    for directory in ("src/inves_cog/trading", "src/inves_cog/valuation"):
        root = Path(directory)
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                if any("shadow_report" in name for name in names):
                    offenders.append(str(path))
    assert not offenders, f"rule A imports shadow_report: {offenders}"
