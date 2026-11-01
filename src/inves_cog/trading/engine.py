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
from inves_cog.trading.execution.state import PARAMS, RULE_A, TIERS


class ExecutionEngine:
    def __init__(self, *, clock, initial_cash=None, mode="paper", portfolio_id="paper-fixed", flags=None):
        self.flags = flags or {}
        self.cooldown = {}   # ticker -> {until, line, closes_above}
        self.limit_orders = {}  # order_id -> {ticker, limit, expiry_index, order}
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
        self.terminal_orders, self.order_lifecycle = [], []

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
        if self.mode == "paper":
            previous = [o for o in self.pending if o["ticker"] == ticker and o["action"] == action]
            if previous:
                raw += ":" + ":".join(o["order_id"] for o in previous)
                for old in previous:
                    self.record_terminal(old, "superseded", "同标的同动作的新意向替代旧单")
        order["order_id"] = hashlib.sha256(raw.encode()).hexdigest()
        validate_order(order)
        order["kind"] = self.order_kind(order)
        if (self.flags.get("pullback_entry") or self.flags.get("pullback_entry_ma20")) and action == "buy":
            hist = self.history.get(ticker) or []
            anchor = hist[-1] if hist else (values.get("price") or 0)
            if self.flags.get("pullback_entry_ma20") and len(hist) >= 20:
                ma20 = sum(hist[-20:]) / 20
                order["limit"] = min(anchor, max(ma20, 0.95 * anchor))
            else:
                order["limit"] = anchor
            order["anchor"] = anchor
            self.limit_orders[order["order_id"]] = {
                "ticker": ticker, "limit": order["limit"],
                "expiry_index": self.index + 10, "order": order,
            }
        self.pending.append(order)

    def record_terminal(self, order, status, reason):
        if status not in {"filled", "canceled", "expired", "superseded"}:
            raise ValueError("Unknown terminal order status")
        terminal = copy.deepcopy(order)
        identity = (
            terminal.get("order_id")
            or hashlib.sha256(json.dumps(order, default=str, sort_keys=True).encode()).hexdigest()
        )
        terminal.update(order_id=identity, status=status, terminal_reason=reason)
        terminal["reason_zh"] = order["reason_zh"] + "；" + reason
        self.pending = [o for o in self.pending if o is not order and o.get("order_id") != identity]
        self.terminal_orders = [o for o in self.terminal_orders if o["order_id"] != identity] + [terminal]
        self.order_lifecycle.append(
            {"order_id": identity, "status": status, "reason": reason, "observed_at": self.clock.now_utc().isoformat()}
        )
        return terminal

    def fill(self, day, opening, execution_scores=None, *, delayed=False, day_bars=None):
        if day in self.settled_dates:
            return []
        available = [o for o in self.pending if o["trade_date"] == day and o["signal_date"] < day]
        # pullback_entry: convert eligible market buys into anchored limit orders
        if self.flags.get("pullback_entry") or self.flags.get("pullback_entry_ma20"):
            still = []
            for order in available:
                if order["action"] != "buy" or "limit" not in order:
                    still.append(order)
                    continue
                bar = (day_bars or {}).get(order["ticker"], {})
                lo, op = bar.get("low"), bar.get("open")
                if lo is None or op is None or lo > order["limit"]:
                    # not touched today — stays pending until expiry
                    continue
                fill_px = min(op, order["limit"])
                equity0 = self.equity(opening)
                if equity0 is not None:
                    detail = settlement.buy(self, order, day, fill_px, equity0, execution_scores or {})
                    if detail:
                        self.trades.append({**order, **detail, "side": "buy", "fill_price": fill_px,
                                            "notional": detail["qty"] * fill_px, "status": "filled",
                                            "execution_note": "回调限价成交"})
                        if self.mode == "paper":
                            self.record_terminal(self.trades[-1], "filled", "回调限价成交")
                continue
            # expire stale limit orders after 10 sessions
            for order in [o for o in self.limit_orders.values() if o["expiry_index"] < self.index]:
                self.record_terminal(order["order"], "expired", "限价单 10 日未成交")
            available = still
        if not available:
            if self.mode == "paper":
                self.settled_dates.add(day)
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
                if (
                    selling
                    and self.flags.get("cooldown_recover")
                    and order["ticker"] not in self.positions
                ):
                    label = order.get("label", "")
                    if any(k in label for k in ("破位", "止损", "减仓")) and "基本面" not in label:
                        hist = self.history.get(order["ticker"]) or []
                        line = sum(hist[-50:]) / 50 if len(hist) >= 50 else (hist[-1] if hist else 0)
                        self.cooldown[order["ticker"]] = {
                            "until": self.index + 10, "line": line, "closes_above": 0}
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
                if self.mode == "paper":
                    if delayed:
                        fills[-1]["execution_note"] = "补撮合（计划延误）"
                    self.record_terminal(fills[-1], "filled", fills[-1].get("execution_note", "按计划开盘成交"))
            elif self.mode == "paper":
                self.record_terminal(order, "expired", "未满足成交约束，未成交")
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
            if self.flags.get("sell_confirm") and order and "破位" in order.get("label", ""):
                h = self.history.get(ticker) or []
                atr = 0.0
                if len(h) >= 15:
                    diffs = [abs(h[i] - h[i - 1]) for i in range(-14, 0)]
                    atr = sum(diffs) / len(diffs)
                line = sum(h[-50:]) / 50 if len(h) >= 50 else (h[-1] if h else 0)
                below2 = len(h) >= 2 and h[-1] < line and h[-2] < line
                big_break = atr > 0 and (line - h[-1]) > atr
                if not (below2 or big_break):
                    order = None
                elif not position.get("_confirm_half_done"):
                    order["fraction"] = min(order.get("fraction", 1.0), 0.5)
                    position["_confirm_half_done"] = True
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
        if self.flags.get("cooldown_recover"):
            hist_map = self.history or {}
            for t in [t for t in self.cooldown]:
                cd = self.cooldown[t]
                h = hist_map.get(t) or []
                if self.index <= cd["until"]:
                    if t in scores:
                        scores[t] = dict(scores[t], entry_pass=False)
                elif h and h[-1] is not None and h[-1] > cd["line"]:
                    cd["closes_above"] += 1
                    if cd["closes_above"] < 3 and t in scores:
                        scores[t] = dict(scores[t], entry_pass=False)
                else:
                    cd["closes_above"] = 0
                    if t in scores:
                        scores[t] = dict(scores[t], entry_pass=False)
                if cd["closes_above"] >= 3:
                    del self.cooldown[t]
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
                if self.mode == "paper":
                    self.record_terminal(intent, "canceled", "事件冷静期，撤销买单")
                continue
            if not published:
                keep.append(intent)
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
                    if self.mode == "paper":
                        self.record_terminal(intent, "expired", text)
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
        result = {
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

        if self.mode == "paper":
            self.explain_plan(result)
        return result

    def explain_plan(self, plan):
        explanations = {}
        for skip in plan["skips"]:
            matching = [o for o in plan["orders"] if o["ticker"] == skip["ticker"]]
            old = [o for o in matching if o["signal_date"] < self.signal_date]
            if old:
                labels = sorted({f"{o['trade_date'].month} 月 {o['trade_date'].day} 日" for o in old})
                skip["reason_zh"] += "；另有 " + "、".join(labels) + "待成交单"
            core_blocked = "M-58" in skip["rule_ids"] or ("M-40" in skip["rule_ids"] and "额度" in skip["reason_zh"])
            if core_blocked and any(o["action"] in {"buy_swing", "buy_watch"} for o in matching):
                reason = "冷却期" if "M-58" in skip["rule_ids"] else "额度满"
                explanations[skip["ticker"]] = f"核心加仓暂停（{reason}），波段仓按独立规则买入"
        pending = [o for o in self.pending if o["action"] == "buy_to"]
        count = len(self.positions) + len(pending)
        # Frozen source aacea04 L649–667 includes additions to already-held names.
        plan["portfolio"]["slot_count"] = {
            "holdings": len(self.positions),
            "buy_to_pending": len(pending),
            "total": count,
            "held_additions": sum(o["ticker"] in self.positions for o in pending),
            "limit": RULE_A["max_positions"],
        }
        plan["portfolio"]["slot_count_note"] = f"持仓 {len(self.positions)} + 加仓挂单 {len(pending)} = {count}"
        plan["explanations"] = explanations

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
                "fill_price=EXCLUDED.fill_price,cost=EXCLUDED.cost,reason_zh=EXCLUDED.reason_zh,"
                "intent=EXCLUDED.intent",
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
            "order_lifecycle",
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
