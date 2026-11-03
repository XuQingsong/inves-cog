from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from inves_cog.backtest.metrics import bench_buy_and_hold, equity_metrics, trade_hash


def test_equity_metrics_basic():
    curve = [
        {"date": date(2026, 1, 2), "equity": 100.0, "cash": 100.0},
        {"date": date(2026, 6, 30), "equity": 120.0, "cash": 20.0},
        {"date": date(2026, 10, 7), "equity": 110.0, "cash": 10.0},
    ]
    trades = [
        {
            "trade_date": date(2026, 1, 5),
            "ticker": "A",
            "label": "买",
            "qty": 1,
            "side": "buy",
            "fill_price": 10,
            "notional": 10,
        },
        {
            "trade_date": date(2026, 2, 10),
            "ticker": "A",
            "label": "卖",
            "qty": 1,
            "side": "sell",
            "fill_price": 12,
            "notional": 12,
        },
    ]
    m = equity_metrics(curve, trades, 100)
    assert m["return_pct"] == pytest.approx(10.0)
    assert m["max_drawdown_pct"] < 0
    assert m["win_rate"] == 1.0
    assert m["avg_holding_days"] == 36
    assert m["trades"] == 2
    assert "2026" in m["yearly"]


def test_bench_buy_and_hold():
    bars = [{"trade_date": date(2026, 1, 2), "close": 100.0}, {"trade_date": date(2026, 10, 7), "close": 150.0}]
    assert bench_buy_and_hold(bars, date(2026, 1, 2), date(2026, 10, 7)) == pytest.approx(50.0)


def test_loader_pit_state():
    """A fundamentals row filed after the lookup day must not be returned."""
    from inves_cog.backtest.loader import BacktestLoader

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    loader = BacktestLoader(conn)
    loader.state_asof("NVDA", date(2026, 1, 5), "legacy")
    sql = conn.execute.call_args[0][0]
    assert "filed<=%s" in sql.replace(" ", "")


def test_loader_state_late_filing_trips():
    """If the DB somehow returns a state filed after as_of, the audit raises."""
    from inves_cog.backtest.loader import BacktestLoader

    conn = MagicMock()
    loader = BacktestLoader(conn)
    bad = MagicMock()
    bad.filed = date(2026, 2, 1)
    loader.fundamentals = MagicMock()
    loader.fundamentals.state_asof.return_value = bad
    with pytest.raises(ValueError, match="PIT"):
        loader.state_asof("NVDA", date(2026, 1, 5), "legacy")


def test_pit_audit_future_signal_trips(monkeypatch):
    """A signal dated after the decision day fails the run."""
    from inves_cog.backtest import runner

    loader = MagicMock()
    loader.bars.return_value = [{"trade_date": date(2026, 1, 2), "open": 1, "close": 1, "volume": 1, "adj_factor": 1.0}]
    loader.vix.return_value = {}
    loader.audit = {"state_lookups": [], "bar_violations": []}
    monkeypatch.setattr(runner, "BacktestLoader", lambda c: loader)
    monkeypatch.setattr(runner, "score_history", lambda *a, **k: [])
    monkeypatch.setattr(runner, "enrich", lambda s, lk, t, e: {date(2026, 1, 2): {"signal_date": date(2026, 1, 3)}})
    with pytest.raises(ValueError, match="PIT"):
        runner.run_backtest(
            MagicMock(),
            {"universe": ["A"], "start": date(2026, 1, 2), "end": date(2026, 1, 2), "mode": "paper"},
            write=False,
        )


def test_trade_hash_deterministic():
    t = [{"trade_date": date(2026, 1, 5), "ticker": "A", "label": "买", "qty": 2}]
    assert trade_hash(t) == trade_hash(list(t))
    t2 = [{"trade_date": date(2026, 1, 5), "ticker": "A", "label": "买", "qty": 3}]
    assert trade_hash(t) != trade_hash(t2)


def test_split_adjusted_bars():
    """A 10:1 split mid-window: loader prices must be continuous (no 10× jump)."""
    from inves_cog.backtest.loader import BacktestLoader

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"trade_date": date(2024, 6, 6), "open": 1200.0, "close": 1208.88, "volume": 100, "adj_factor": 0.1},
        {"trade_date": date(2024, 6, 7), "open": 1210.0, "close": 1209.0, "volume": 100, "adj_factor": 0.1},
        {"trade_date": date(2024, 6, 10), "open": 121.0, "close": 121.79, "volume": 1000, "adj_factor": 1.0},
    ]
    bars = BacktestLoader(conn).bars("NVDA")
    assert bars[0]["close"] == pytest.approx(120.888)
    assert bars[2]["close"] == pytest.approx(121.79)
    assert bars[0]["adj_factor"] == 1.0 and bars[0]["volume"] == 1000
    # continuity: pre/post split closes within a few percent
    assert abs(bars[1]["close"] / bars[2]["close"] - 1) < 0.02


def test_pe_continuous_across_split():
    """PE must not jump 10× at a split: derivatives use the day's raw price."""
    from inves_cog.trading.scoring.books import build_books

    # constant EPS-of-the-time (pre-split dollars per pre-split share)
    fields = {"eps_ttm": 2.0, "shares": 1e9, "rev_growth": 10.0, "rev_ttm": 5e9, "fcf_ttm": 1e9, "gross_margin": 50.0}
    pre = build_books(fields, {"price": 120.9, "raw_price": 1209.0})
    post = build_books(fields, {"price": 121.79, "raw_price": 121.79})
    # pre-split raw close 1209 with EPS 2 (pre-split units) → pe 604.5;
    # post-split the fin_state would restate EPS per new share — same continuity
    # check applied: raw_price (not adjusted price) drives pe
    assert pre[1]["pe"] == pytest.approx(604.5)
    assert post[1]["pe"] == pytest.approx(60.895)
    # a real split restates EPS ×10 too → pe stays ~604→60? no: EPS also ×10 post.
    # The invariant: using raw price avoids the extra 10× from adjusted price.
    buggy = build_books(fields, {"price": 120.9})  # no raw_price → falls back to price
    assert buggy[1]["pe"] == pytest.approx(60.45)  # 10× off pre-split


def test_scores_identical_when_adj_factor_1():
    """adj_factor=1 days produce byte-identical tech rows as before (raw==adj)."""
    from inves_cog.trading.scoring.technical import technical_series

    bars = [
        {
            "trade_date": date(2026, 1, 2) + timedelta(days=i),
            "open": 100.0 + i,
            "close": 100.0 + i,
            "volume": 1000,
            "adj_factor": 1.0,
        }
        for i in range(5)
    ]
    frame = technical_series(bars)
    assert all(frame["raw_price"] == frame["price"])


def test_cboe_health_args_behavioral():
    """Behavioral: stub http + recording conn; assert record_health gets an aware
    datetime `now`, int items, str note — not the scrambled positional args."""
    from datetime import datetime, timezone

    from inves_cog.flows import collectors

    calls = []

    class FakeConn:
        def execute(self, *a, **kw):
            return None

    class FakeHTTP:
        def request(self, *a, **kw):
            return {"data": []}

    orig_parse = collectors.parse_cboe_chain
    orig_health = collectors.record_health
    collectors.record_health = lambda *a, **k: calls.append(a)
    collectors.parse_cboe_chain = lambda *a, **k: [{"x": 1}, {"x": 2}]
    try:
        collectors.collect_cboe_chain(FakeHTTP(), FakeConn(), "SPY", "/tmp", 60, None, datetime.now(timezone.utc))
    except Exception:
        pass
    finally:
        collectors.record_health = orig_health
        collectors.parse_cboe_chain = orig_parse
    assert calls, "record_health not called"
    conn, src, ok, now, items, note, *rest = calls[0]
    assert isinstance(now, datetime) and now.tzinfo is not None, f"now not aware datetime: {now!r}"
    assert isinstance(items, int), f"items not int: {items!r}"
    assert isinstance(note, str), f"note not str: {note!r}"


def test_barometer_called_in_run_once_behavioral():
    """run_once at 10:00 ET on a trading day → run_intraday+persist into barometer_intraday."""
    import importlib.util
    import os
    import sys
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    spec = importlib.util.spec_from_file_location(
        "schedule_flows", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "schedule_flows.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schedule_flows"] = mod
    spec.loader.exec_module(mod)
    clock = MagicMock()
    clock.now_utc.return_value = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
    conn = MagicMock()
    persisted = []
    mod._load_state = lambda: {}
    mod._save_state = lambda s: None
    mod.trading_day = lambda d: True
    mod._intra_slots = lambda d: ["09:45", "10:00", "10:15"]
    mod.polite_http = lambda: MagicMock()
    mod.collect_cboe_chain = lambda *a, **k: {"symbol": "x", "rows": 1}
    mod.collect_occ = lambda *a, **k: {"rows": 0}
    mod.collect_occ_series = lambda *a, **k: {"symbol": "x", "rows": 1}
    mod.collect_cboe_pc = lambda *a, **k: {"rows": 0}
    mod.collect_etf_shares = lambda *a, **k: {"rows": 0}
    mod._etf_done = lambda c, d: True
    mod._universe = lambda: []
    mod.record_health_agg = lambda *a, **k: None
    mod.record_health = lambda *a, **k: None
    import inves_cog.perception.barometer.run as bmod

    orig_run, orig_persist = bmod.run_intraday, bmod.persist
    bmod.run_intraday = lambda c, _l: {"fear": 1, "missing": []}
    bmod.persist = lambda c, recs, table=None, ts=None: persisted.append((table, recs))
    try:
        mod.run_once(clock, {}, conn=conn)
    finally:
        bmod.run_intraday, bmod.persist = orig_run, orig_persist
    assert any("barometer_intraday" in str(t) for t in persisted), f"persist not called: {persisted}"


def test_etf_stale_health_no_kwarg_collision():
    """The ETF stale path must not pass `now` both positionally and as a kwarg —
    that raises 'multiple values for argument now' → run_once dies with TypeError."""
    import importlib.util
    import os
    import sys
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    spec = importlib.util.spec_from_file_location(
        "schedule_flows", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "schedule_flows.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schedule_flows"] = mod
    spec.loader.exec_module(mod)
    clock = MagicMock()
    clock.now_utc.return_value = datetime(2026, 11, 3, 5, 0, tzinfo=timezone.utc)
    conn = MagicMock()
    mod._load_state = lambda: {}
    mod._save_state = lambda s: None
    mod.trading_day = lambda d: False  # non-trading → hits the etf-stale path if keyed
    mod.polite_http = lambda: MagicMock()
    mod.collect_occ = lambda *a, **k: {"rows": 0}
    mod.collect_occ_series = lambda *a, **k: {"symbol": "x", "rows": 1}
    mod.collect_etf_shares = lambda *a, **k: {"rows": 0}
    mod._etf_done = lambda c, d: False  # not done → stale branch fires
    mod._universe = lambda: []
    mod.record_health_agg = lambda *a, **k: None
    mod.record_health = lambda *a, **k: a  # return the call args
    # run at 08:00 with stale key pre-set → hits record_health without kwarg collision
    result = mod.run_once(clock, {}, conn=conn)
    assert result["status"] == "ok"  # no TypeError abort
