"""The sole order write entry point for deterministic rule A paper portfolios."""

import copy
import hashlib
import json
from datetime import date

from psycopg.types.json import Jsonb

from inves_cog.ingest.market import exchange
from inves_cog.trading.execution import buys, settlement
from inves_cog.trading.execution.contracts import coverage, overlay_state, validate_order
from inves_cog.trading.execution.risk import update_risk, vix_panic
from inves_cog.trading.execution.sells import sell_signal
from inves_cog.trading.execution.state import PARAMS, TIERS


class ExecutionEngine:
    def __init__(self, *, clock, initial_cash=None, mode="paper", portfolio_id="paper-fixed"):
        if mode not in {"paper", "replay_v18"}:
            raise ValueError("Only approved rule A execution modes")
        self.clock, self.mode, self.portfolio_id = clock, mode, portfolio_id
        self.cash = float(PARAMS["initial_cash"] if initial_cash is None else initial_cash)
        self.initial_cash, self.peak_equity = self.cash, self.cash
        self.positions, self.exits, self.watch_first = {}, {}, {}
        self.pending, self.trades, self.curve, self.skips = [], [], [], []
        self.history, self.insiders, self.scores = {}, {}, {}
        self.index, self.last_swan, self.swan_until = 0, -100, -1
        self.dd8, self.dd12, self.panic = False, False, False
        self.signal_date, self.vix_detail = None, {"status": "missing", "threshold": None}
        self.last_equity, self.last_prices = self.cash, {}
        self.settled_dates = set()
        self.cancels = []

    @property
    def health_codes(self):
        return ["cash_negative"] if self.cash < 0 else ["ok"]

    def equity(self, prices):
        if any(prices.get(t) is None for t in self.positions):
            return None
        return self.cash + sum(p["shares"] * prices[t] for t, p in self.positions.items())

    def skip(self, ticker, rule, n_code, text):
        self.skips.append(
            {
                "ticker": ticker,
                "n_code": n_code,
                "rule_ids": [rule],
                "reason_zh": rule + " " + text,
                "params_version": "p-2026.10",
            }
        )

    def queue(self, ticker, action, rule, label, **values):
        target = exchange(self.signal_date.year).next_session(str(self.signal_date)).date()
        order = {
            "ticker": ticker,
            "action": action,
            "label": label,
            "rule_ids": [rule],
            "reason_zh": rule + " " + label,
            "signal_date": self.signal_date,
            "trade_date": target,
            "rule_set": "A",
            "params_version": "p-2026.10",
            **values,
        }
        raw = f"{self.portfolio_id}:{self.signal_date}:{len(self.pending)}:{ticker}:{action}"
        order["order_id"] = hashlib.sha256(raw.encode()).hexdigest()
        validate_order(order)
        order["kind"] = self.order_kind(order)
        self.pending.append(order)

    def fill(self, day, opening, execution_scores=None):
        if day in self.settled_dates:
            return []
        available = [o for o in self.pending if o["trade_date"] == day and o["signal_date"] < day]
        if not available:
            return []
        equity = self.equity(opening)
        if equity is None:
            return []
        fills, deferred = [], []
        # Muse aacea04 L277–385: stable sells first; one equity mark before any fill this session.
        for order in sorted(available, key=lambda o: not o["action"].startswith("sell")):
            price = opening.get(order["ticker"])
            if price is None or price <= 0:
                deferred.append(order)
                self.skip(order["ticker"], "M-35", "N8", "缺少实际开盘价，未成交")
                continue
            selling = order["action"].startswith("sell")
            detail = (
                settlement.sell(self, order, day, price)
                if selling
                else settlement.buy(self, order, day, price, equity, execution_scores or {})
            )
            if detail:
                fills.append(
                    {
                        **order,
                        **detail,
                        "side": "sell" if selling else "buy",
                        "fill_price": price,
                        "notional": detail["qty"] * price,
                        "status": "filled",
                    }
                )
        self.pending = [o for o in self.pending if o not in available] + deferred
        self.trades.extend(fills)
        if not deferred:
            self.settled_dates.add(day)
        return fills

    def decide(self, day, scores, *, prices, history=None, spy_returns=(None, None), vix=None, vix_history=()):
        self.signal_date, self.scores, self.skips, self.cancels = day, scores, [], []
        self.last_prices = dict(prices)
        if history is not None:
            self.history = history
        else:
            for ticker, value in prices.items():
                if value is not None:
                    self.history.setdefault(ticker, []).append(value)
        equity = self.equity(prices)
        if equity is None:
            return {"status": "no_bar", "missing": [t for t in self.positions if prices.get(t) is None]}
        self.last_equity = equity
        self.curve.append({"day": day, "equity": equity, "cash": self.cash})
        self.panic, self.vix_detail = vix_panic(vix, vix_history)
        risks = update_risk(self, equity, spy_returns, self.panic)
        for ticker, rule, fraction, label in risks:
            self.queue(ticker, "sell_frac", rule, label, fraction=fraction)
        sold = set()
        for ticker, position in self.positions.items():
            score = scores.get(ticker)
            if not score:
                continue
            position["tier_now"] = score.get("tier") or position["tier_now"]
            order = sell_signal(position, score, index=self.index, panic=self.panic)
            if order:
                self.queue(
                    ticker,
                    order["action"],
                    order["rule_ids"][0],
                    order["label"],
                    **{k: v for k, v in order.items() if k not in {"action", "rule_ids", "label", "reason_zh"}},
                )
                sold.add(ticker)
        values = {
            tier: sum(p["shares"] * prices[t] for t, p in self.positions.items() if p["tier_now"] == tier)
            for tier in TIERS
        }
        if self.index > self.swan_until:
            allowed = {t: s for t, s in scores.items() if self.mode == "replay_v18" or s.get("tradable", True)}
            buys.core_adds(self, allowed, values, equity, sold)
            buys.core_swings(self, allowed, values, equity, sold)
            buys.watch_buys(self, allowed, values, equity)
            buys.entries(self, allowed, values, equity)
        else:
            for ticker, score in scores.items():
                if score.get("entry_pass"):
                    self.skip(ticker, "M-61", "N7", "黑天鹅暂停买入")
        self.index += 1
        return {"status": "ok", "equity": equity}

    def plan(self, day, *, overlay=None, tradable=None, with_bars=None):
        n = len(self.scores) if tradable is None else tradable
        bars = sum(self.last_prices.get(t) is not None for t in self.scores) if with_bars is None else with_bars
        data, published = coverage(n, bars)
        layer, rows = overlay_state(overlay, day, asof=self.clock.now_utc())
        canceled, orders, keep = list(self.cancels), [], []
        for intent in self.pending:
            selling = intent["action"].startswith("sell")
            item = rows.get(intent["ticker"], {})
            if not selling and item.get("cooling_off"):
                canceled.append(
                    {
                        "ticker": intent["ticker"],
                        "original_order": copy.deepcopy(intent),
                        "n_code": "N5",
                        "overlay_event_ids": item.get("event_ids", []),
                        "reason_zh": "事件冷静期，撤销买单",
                    }
                )
                self.skip(intent["ticker"], "M-34", "N5", "事件冷静期，暂停买入")
                continue
            if published:
                estimated = self.estimated_notional(intent)
                if estimated is not None and estimated <= 0:
                    text = (
                        "持仓已达到本次目标金额，预计新增金额为0"
                        if intent["action"] == "buy_to"
                        else "当前持仓按计划股数计算的金额为0"
                    )
                    self.skip(intent["ticker"], intent["rule_ids"][0], "N7", text)
                    continue
                multiplier = item.get("first_lot_multiplier", 1)
                if not selling and isinstance(multiplier, (int, float)) and 0 <= multiplier <= 1:
                    intent["overlay_multiplier"] = min(intent.get("overlay_multiplier", 1), multiplier)
                keep.append(intent)
                orders.append(
                    {
                        **intent,
                        "side": "sell" if selling else "buy",
                        "kind": self.order_kind(intent),
                        "qty": None,
                        "notional_est": estimated,
                        "overlay_version": layer["version"],
                    }
                )
        self.pending = keep
        self.cancels = canceled
        return {
            "trade_date": day,
            "signal_date": self.signal_date,
            "rule_set": "A",
            "params_version": "p-2026.10",
            "overlay": layer,
            "data_coverage": data,
            "published": published,
            "unpublished_reason": None if published else "data_coverage_below_95",
            "orders": orders,
            "cancels": canceled,
            "skips": copy.deepcopy(self.skips),
            "health_codes": self.health_codes,
            "holdings": [self.holding_status(t, p) for t, p in self.positions.items()],
            "portfolio": {
                "equity": self.last_equity,
                "invested_pct": (self.last_equity - self.cash) / self.last_equity * 100,
                "holdings_count": len(self.positions),
                "tier_usage": self.tier_usage(),
                "gates": {
                    "panic": self.panic,
                    "black_swan": self.index - 1 <= self.swan_until,
                    "drawdown_brake": self.dd12,
                    "vix": self.vix_detail,
                },
            },
        }

    def order_kind(self, order):
        if order["action"] == "buy_to":
            return "add" if order["ticker"] in self.positions else "open"
        return {
            "buy_swing": "swing_buy",
            "buy_watch": "swing_buy",
            "sell_swing": "swing_sell",
            "sell_all": "exit",
            "sell_frac": "reduce",
        }[order["action"]]

    def holding_status(self, ticker, position):
        score = self.scores.get(ticker)
        missing = (
            ["score"]
            if not score
            else [key for key in ("quality", "growth", "valuation", "timing") if score["books"].get(key) is None]
        )
        orders = [o for o in self.pending if o["ticker"] == ticker]
        order = next((o for o in orders if o["action"].startswith("sell")), orders[0] if orders else None)
        reason = (
            order["reason_zh"]
            if order
            else "N8 缺失账本的卖出条款未判定"
            if missing
            else "M-59 未触发卖出规则，继续持有"
        )
        detail = "；N8 缺少 " + ",".join(missing) + "，相关条款未判定" if missing else ""
        return {
            "ticker": ticker,
            "qty": position["shares"],
            "tier": position["tier_now"],
            "status": reason + detail,
            "n_code": "N8" if missing else None,
            "reason_zh": reason + detail,
        }

    def estimated_notional(self, order):
        position = self.positions.get(order["ticker"])
        price = self.last_prices.get(order["ticker"])
        if order["action"].startswith("sell"):
            if position is None or price is None:
                return None
            qty = (
                position["shares"]
                if order["action"] == "sell_all"
                else position["swing_shares"]
                if order["action"] == "sell_swing"
                else int(position["shares"] * order["fraction"])
            )
            return qty * price
        amount = order.get("value")
        if order["action"] == "buy_to":
            amount = order["fraction"] * TIERS[order["tier"]]["cap"] * self.last_equity
            if position:
                if price is None:
                    return None
                amount -= position["shares"] * price
            if order.get("half"):
                amount *= 0.5
        return max(0.0, amount) * order.get("overlay_multiplier", 1) if amount is not None else None

    def tier_usage(self):
        values = {
            tier: sum(
                p["shares"] * self.last_prices[t]
                for t, p in self.positions.items()
                if p["tier_now"] == tier and self.last_prices.get(t) is not None
            )
            for tier in TIERS
        }
        return {
            tier: {
                "market_value": value,
                "weight_pct": value / self.last_equity * 100,
                "buy_limit": buys.limit(self, tier, values, self.last_equity),
                "holdings_count": sum(p["tier_now"] == tier for p in self.positions.values()),
            }
            for tier, value in values.items()
        }

    def persist_orders(self, connection, orders):
        for order in orders:
            validate_order(order)
            connection.execute(
                "INSERT INTO trading.orders (portfolio_id,order_id,signal_date,trade_date,ticker,side,kind,"
                "qty,fill_price,"
                "cost,rule_ids,reason_zh,tier,rule_set,params_version,overlay_version,status,intent) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'A','p-2026.10',%s,%s,%s) "
                "ON CONFLICT (portfolio_id,order_id) DO UPDATE SET status=EXCLUDED.status,qty=EXCLUDED.qty,"
                "fill_price=EXCLUDED.fill_price,cost=EXCLUDED.cost,intent=EXCLUDED.intent",
                (
                    self.portfolio_id,
                    order["order_id"],
                    order["signal_date"],
                    order["trade_date"],
                    order["ticker"],
                    order.get("side"),
                    order.get("kind", self.order_kind(order)),
                    order.get("qty"),
                    order.get("fill_price"),
                    order.get("cost"),
                    order["rule_ids"],
                    order["reason_zh"],
                    order.get("tier"),
                    order.get("overlay_version"),
                    order.get("status", "pending"),
                    Jsonb(order, dumps=lambda v: json.dumps(v, default=str, allow_nan=False)),
                ),
            )

    def snapshot(self):
        keys = (
            "cash",
            "peak_equity",
            "positions",
            "exits",
            "watch_first",
            "pending",
            "index",
            "last_swan",
            "swan_until",
            "dd8",
            "dd12",
            "signal_date",
            "last_equity",
            "last_prices",
            "scores",
            "skips",
            "cancels",
            "vix_detail",
            "panic",
        )
        return {
            **{key: copy.deepcopy(getattr(self, key)) for key in keys},
            "settled_dates": sorted(self.settled_dates),
            "params_version": "p-2026.10",
            "rule_set": "A",
        }

    def restore(self, state):
        if state.get("params_version") != "p-2026.10" or state.get("rule_set") != "A":
            raise ValueError("Ledger execution version does not match rule A")
        for key, value in state.items():
            if key not in {"params_version", "rule_set", "settled_dates"}:
                setattr(self, key, copy.deepcopy(value))
        if isinstance(self.signal_date, str):
            self.signal_date = date.fromisoformat(self.signal_date)
        self.settled_dates = {date.fromisoformat(d) if isinstance(d, str) else d for d in state["settled_dates"]}
        for order in self.pending:
            for key in ("signal_date", "trade_date"):
                if isinstance(order[key], str):
                    order[key] = date.fromisoformat(order[key])
