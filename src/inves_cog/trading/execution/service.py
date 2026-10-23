"""Plan from a closed signal session; never use the target session's unseen prices."""

from inves_cog.ingest.market import exchange
from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.completeness import describe_inputs
from inves_cog.trading.execution.contracts import members_asof
from inves_cog.trading.execution.repository import Repository


def decide_day(engine, day, inputs):
    bars = inputs["bars"]
    closing = {ticker: rows[day]["close"] for ticker, rows in bars.items() if day in rows}
    opening = {ticker: rows[day]["open"] for ticker, rows in bars.items() if day in rows}
    engine.fill(day, opening)
    scores = {t: rows[day] for t, rows in inputs["signals"].items() if day in rows}
    spy = [row["close"] for d, row in sorted(bars["SPY"].items()) if d <= day and row["close"] is not None]
    spy_returns = (
        100 * (spy[-1] / spy[-2] - 1) if len(spy) >= 2 else None,
        100 * (spy[-1] / spy[-6] - 1) if len(spy) >= 6 else None,
    )
    history = {
        t: [r["close"] for d, r in sorted(rows.items()) if d <= day and r["close"] is not None]
        for t, rows in bars.items()
    }
    result = engine.decide(
        day,
        scores,
        prices=closing,
        history=history,
        spy_returns=spy_returns,
        vix=inputs["vix"].get(day),
        vix_history=[v for d, v in sorted(inputs["vix"].items()) if d <= day],
    )
    engine.vix_detail.update(
        source=inputs["vix_sources"].get(day), observation_date=day if day in inputs["vix"] else None
    )
    return result


def prepare(engine, target, inputs, universe, overlay=None):
    signal_day = exchange(target.year).previous_session(str(target)).date()
    if engine.signal_date != signal_day:
        decide_day(engine, signal_day, inputs)
    known_members = [
        {**r, "first_trade_date": inputs.get("first_trade_dates", {}).get(r["ticker"])}
        for r in universe
        if not r.get("foreign", False)
    ]
    included = members_asof(known_members, signal_day)
    available = [
        t
        for t in included
        if signal_day in inputs["bars"].get(t, {})
        and all(inputs["bars"][t][signal_day].get(k) is not None for k in ("open", "close"))
    ]
    plan = engine.plan(target, overlay=overlay, tradable=len(included), with_bars=len(available))
    plan.update(
        missing_tickers=sorted(set(included) - set(available)),
        score_source=inputs["score_source"],
        input_asof=signal_day,
        generated_at=engine.clock.now_utc(),
        portfolio_id=engine.portfolio_id,
        missing_scores=sorted(set(included) - set(engine.scores)),
    )
    if plan["missing_scores"]:
        plan["health_codes"] = sorted((set(plan["health_codes"]) - {"ok"}) | {"upstream_scores_missing"})
    return plan


def daily_plan(*, clock, connection, universe, target, overlay=None, persist=True):
    signal_day = exchange(target.year).previous_session(str(target)).date()
    repository = Repository(connection)
    inputs = repository.inputs(signal_day, [r["ticker"] for r in universe])
    engine = ExecutionEngine(clock=clock)
    old = None
    if persist:
        old = repository.restore(engine.portfolio_id, target)
        if old:
            engine.restore(old["state"])
    engine.insiders = repository.insider_events(signal_day)
    plan = prepare(engine, target, inputs, universe, overlay)
    plan["input_completeness"] = describe_inputs(
        plan,
        inputs,
        universe,
        signal_day=signal_day,
        cutoff=clock.now_utc(),
        insiders=engine.insiders,
        ledger=old,
        ledger_checked=persist,
        overlay=overlay,
    )
    if persist:
        with connection.transaction():
            engine.persist_orders(connection, plan["orders"])
            engine.persist_orders(connection, engine.trades)
            for canceled in plan["cancels"]:
                engine.persist_orders(connection, [{**canceled["original_order"], "status": "canceled"}])
            repository.save(engine, plan)
    return plan


def historical_plans(*, clock, connection, universe, targets):
    last_signal = exchange(targets[-1].year).previous_session(str(targets[-1])).date()
    repository = Repository(connection)
    inputs = repository.inputs(last_signal, [r["ticker"] for r in universe], historical=True)
    engine = ExecutionEngine(clock=clock, portfolio_id="acceptance-fixed-five-days")
    engine.insiders = repository.insider_events(last_signal)
    plans = []
    for target in targets:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from inves_cog.clock import FrozenClock

        visible = FrozenClock(datetime.combine(target, datetime.min.time(), ZoneInfo("Asia/Shanghai")).replace(hour=20))
        engine.clock = visible
        plans.append(prepare(engine, target, inputs, universe))
    return plans
