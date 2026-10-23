"""Daily page JSON. Every number is copied from an upstream column or is a SQL count of those rows."""

import json
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.ingest.market import NY, trading_day

MISSING = "数据暂缺"
CLOSED = "非交易日"
PAPER_LABEL = "纸面跟踪，非投资建议"
VALUATION_LABEL = "估值参考 v1，不参与仓位"
UNCONNECTED = "未接通"
STALE = "今日未更新"
COMPLETENESS_MISSING = "输入完整性未报告"
# The page copies a stored sentence when the review job saved one. It does not call a model.
MODEL_CALLS = 0

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_MOVE_ABS = 0.07
# 200 亿美元. Stored mktcap is dollars (shares times price).
_CAP_FLOOR = 20_000_000_000
_TRADE_STATUSES = ("pending", "filled", "canceled")
_UNIVERSE = Path(__file__).resolve().parents[3] / "config" / "universe.yaml"
# No stored SPY/QQQ weight table exists, so that linkage clause is not applied.


def _shanghai_midnight(day):
    return datetime.combine(day, time.min, tzinfo=_SHANGHAI)


def _deadline(day):
    # Calendar D+1 01:00 in America/New_York. Daylight time is Beijing D+1 13:00; standard time is 14:00.
    return datetime.combine(day + timedelta(days=1), time(1, 0), tzinfo=NY)


def _cutoff(clock, day):
    return min(clock.now_utc(), _deadline(day))


def _open(clock, day):
    if not trading_day(day):
        return None, {"message": CLOSED}
    return _cutoff(clock, day), None


def _parse_ts(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=_SHANGHAI)
        return value
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_SHANGHAI)
    return parsed


def _rows(connection, sql, params):
    return list(connection.execute(sql, params).fetchall())


def _one(connection, sql, params):
    return connection.execute(sql, params).fetchone()


def _universe():
    loaded = yaml.safe_load(_UNIVERSE.read_text())
    return [row["ticker"] for row in loaded["stocks"]], list(loaded["etfs"])


def _tickers(value):
    if isinstance(value, dict):
        found = []
        if isinstance(value.get("ticker"), str):
            found.append(value["ticker"])
        nested = value.get("tickers") or value.get("members") or []
        found.extend(name for name in nested if isinstance(name, str))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_tickers(item) if not isinstance(item, str) else [item])
        return found
    return []


def _section(connection, day, cutoff, task_name):
    row = _one(
        connection,
        """
        SELECT status, error_summary
        FROM ingest.job_runs
        WHERE trade_date = %s AND task_name = %s AND started_at < %s
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (day, task_name, cutoff),
    )
    summary = "" if row is None or row["error_summary"] is None else row["error_summary"]
    stale = row is not None and (row["status"] == "failed" or "skipped_upstream:" in summary)
    if stale:
        return {
            "task_name": task_name,
            "state": STALE,
            "job_status": row["status"],
            "error_summary": row["error_summary"],
        }
    return {
        "task_name": task_name,
        "state": "ok",
        "job_status": None if row is None else row["status"],
        "error_summary": None if row is None else row["error_summary"],
    }


def _anomalies(connection, day, cutoff):
    return _rows(
        connection,
        """
        SELECT anomaly_id, trade_date, session, layer, severity, baskets, members, direction,
               max_abs_z, status, universe, generated_at
        FROM perception.anomalies
        WHERE trade_date = %s AND (generated_at IS NULL OR generated_at < %s)
        ORDER BY anomaly_id
        """,
        (day, cutoff),
    )


def _event_view(event, cutoff):
    history = event.get("history") or []
    visible, future = [], False
    for item in history:
        if not isinstance(item, dict):
            continue
        moment = _parse_ts(item.get("at"))
        if moment is None:
            continue
        if moment >= cutoff:
            future = True
        else:
            visible.append((moment, item))
    if history and not visible:
        return None
    visible.sort(key=lambda pair: pair[0])
    if visible:
        moment, item = visible[-1]
        lifecycle = item.get("new") or event["lifecycle"]
    else:
        moment, lifecycle = None, event["lifecycle"]
    outcome = None if future else event.get("deadline_outcome")
    return {
        "event_id": event["event_id"],
        "anomaly_id": event["anomaly_id"],
        "lifecycle": lifecycle,
        "mechanism": event.get("mechanism"),
        "deadline_outcome": outcome,
        "deadline_visible": outcome is not None and outcome != "",
        "at": moment,
    }


def _events(connection, anomalies, cutoff):
    if not anomalies:
        return {}
    ids = [row["anomaly_id"] for row in anomalies]
    stored = _rows(
        connection,
        """
        SELECT event_id, anomaly_id, lifecycle, history, deadline_outcome, mechanism
        FROM perception.linkage_events
        WHERE anomaly_id = ANY(%s)
        ORDER BY event_id
        """,
        (ids,),
    )
    chosen = {}
    for event in stored:
        view = _event_view(event, cutoff)
        if view is None:
            continue
        current = chosen.get(view["anomaly_id"])
        if current is None or (view["at"] or datetime.min.replace(tzinfo=_SHANGHAI)) >= (
            current["at"] or datetime.min.replace(tzinfo=_SHANGHAI)
        ):
            chosen[view["anomaly_id"]] = view
    return chosen


def _overlay(connection, day, cutoff):
    row = _one(
        connection,
        """
        SELECT payload
        FROM overlay.versions
        WHERE date = %s AND generated_at < %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    if row is None or not isinstance(row["payload"], dict):
        return {}, {}, MISSING
    payload = row["payload"]
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    by_event = {}
    for item in tickers.values():
        if not isinstance(item, dict):
            continue
        for link in item.get("linkage_events") or []:
            if isinstance(link, dict) and link.get("event_id"):
                by_event[link["event_id"]] = link.get("exposure")
    completeness = payload["m8_completeness"] if "m8_completeness" in payload else MISSING
    return tickers, by_event, completeness


def _orders(connection, day):
    return _rows(
        connection,
        """
        SELECT order_id, ticker, side, kind, qty, fill_price, cost, status, signal_date, trade_date, reason_zh
        FROM trading.orders
        WHERE trade_date = %s AND status = ANY(%s)
        ORDER BY order_id
        """,
        (day, list(_TRADE_STATUSES)),
    )


def _plan(connection, day, cutoff):
    return _one(
        connection,
        """
        SELECT payload, signal_date, published, generated_at, params_version
        FROM trading.plan
        WHERE trade_date = %s AND generated_at < %s
        ORDER BY generated_at DESC
        LIMIT 1
        """,
        (day, cutoff),
    )


def _acted(orders, payload):
    acted = {row["ticker"] for row in orders}
    cancels = payload.get("cancels") if isinstance(payload, dict) else None
    for item in cancels or []:
        if isinstance(item, dict) and isinstance(item.get("ticker"), str):
            acted.add(item["ticker"])
        elif isinstance(item, str):
            acted.add(item)
    return acted


def _cooling_on(tickers, names):
    for name in names:
        item = tickers.get(name)
        if isinstance(item, dict) and item.get("cooling_status") == "on":
            return True
    return False


def _disposition(view, cooling_on, acted, missed=False):
    if missed:
        return "⑤"
    if view is not None and view["deadline_visible"]:
        return "④"
    if cooling_on or acted:
        return "③"
    if view is None or view["lifecycle"] in (None, "已发现"):
        return "①"
    return "②"


def _confirmed_misses(connection, cutoff):
    rows = _rows(
        connection,
        """
        SELECT anomaly_id FROM perception.miss_samples
        WHERE judgment = '应发现' AND anomaly_id IS NOT NULL
          AND judged_at IS NOT NULL AND judged_at < %s
        """,
        (cutoff,),
    )
    return {row["anomaly_id"] for row in rows}


def _stored_oneliner(connection, day, cutoff):
    row = _one(
        connection,
        """
        SELECT payload->>'sentence' AS sentence
        FROM perception.reports_weekly
        WHERE report_id = %s AND generated_at < %s
        """,
        ("oneliner:" + day.isoformat(), cutoff),
    )
    if row is None:
        return None
    sentence = row["sentence"]
    return sentence or None


def _highlighted(clock, day):
    return clock.now_utc() >= _deadline(day)


def _status_counts(anomalies, events):
    counts = {}
    for anomaly in anomalies:
        view = events.get(anomaly["anomaly_id"])
        status = anomaly["status"] if view is None else view["lifecycle"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _count(connection, sql, params):
    return int(_one(connection, sql, params)["n"])


def page_home(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    tickers, _, _ = _overlay(connection, day, cutoff)
    plan = _plan(connection, day, cutoff)
    payload = plan["payload"] if plan and isinstance(plan["payload"], dict) else {}
    orders = _orders(connection, day)
    acted = _acted(orders, payload)
    missed = _confirmed_misses(connection, cutoff)
    red = _highlighted(clock, day)
    unhandled = []
    for anomaly in anomalies:
        names = _tickers(anomaly["members"])
        view = events.get(anomaly["anomaly_id"])
        state = _disposition(
            view,
            _cooling_on(tickers, names),
            bool(set(names) & acted),
            anomaly["anomaly_id"] in missed,
        )
        if state != "①":
            continue
        unhandled.append({"anomaly_id": anomaly["anomaly_id"], "disposition": state, "highlighted": red})
    start = _shanghai_midnight(day)
    counts = {
        "anomaly_count": len(anomalies),
        "status_counts": _status_counts(anomalies, events),
        "high_priority_info_count": _count(
            connection,
            """
            SELECT count(*) AS n FROM ingest.info_items
            WHERE source_level = 1 AND first_seen_at >= %s AND first_seen_at < %s
            """,
            (start, cutoff),
        ),
        "trade_action_count": len(orders),
        "no_action_count": _count(
            connection,
            """
            SELECT count(*) AS n
            FROM perception.ticker_status AS status
            JOIN perception.anomalies AS anomaly ON anomaly.anomaly_id = status.anomaly_id
            WHERE anomaly.trade_date = %s AND (anomaly.generated_at IS NULL OR anomaly.generated_at < %s)
            """,
            (day, cutoff),
        ),
        "shadow_divergence_count": _count(
            connection,
            """
            SELECT count(*) AS n FROM factor_shadow.daily
            WHERE date = %s AND generated_at < %s AND would_pass IS DISTINCT FROM rule_a_entry_pass
            """,
            (day, cutoff),
        ),
    }
    return {
        "page": "/",
        "date": day,
        "summary_oneliner": _stored_oneliner(connection, day, cutoff)
        or f"今日异常 {counts['anomaly_count']} 个，详见下方",
        "counts": counts,
        "unhandled": unhandled,
        "sections": {
            "anomalies": _section(connection, day, cutoff, "anomaly_daily"),
            "info": _section(connection, day, cutoff, "bars_prefill"),
        },
    }


def _prefer_session(rows):
    chosen = {}
    for row in rows:
        current = chosen.get(row["ticker"])
        if current is None or (row["session"] == "post" and current["session"] != "post"):
            chosen[row["ticker"]] = row
    return chosen


def _eligible(connection, day, pool, etfs):
    names = set(pool) | set(etfs)
    for row in _rows(
        connection,
        """
        SELECT ticker, mktcap, included, exclude_reason
        FROM ingest.wide_universe
        WHERE trade_date = %s
        """,
        (day,),
    ):
        cap = row["mktcap"]
        if row["included"] and row["exclude_reason"] != "non_common" and cap is not None and cap >= _CAP_FLOOR:
            names.add(row["ticker"])
    return names


def _tags(connection, day, cutoff, ticker):
    start = _shanghai_midnight(day)
    tags = []
    earnings = _one(
        connection,
        """
        SELECT event_id FROM ingest.earnings_events
        WHERE ticker = %s AND reaction_day = %s AND fetched_at < %s
        LIMIT 1
        """,
        (ticker, day, cutoff),
    )
    if earnings is not None:
        tags.append("财报")
    kinds = {
        row["kind"]
        for row in _rows(
            connection,
            """
            SELECT kind FROM ingest.info_items
            WHERE %s = ANY(tickers) AND kind = ANY(%s) AND first_seen_at >= %s AND first_seen_at < %s
            """,
            (ticker, ["sec_8k", "form4"], start, cutoff),
        )
    }
    filing = _one(
        connection,
        """
        SELECT form FROM ingest.sec_filings
        WHERE ticker = %s AND filing_date = %s AND fetched_at < %s AND form LIKE '8-K%%'
        LIMIT 1
        """,
        (ticker, day, cutoff),
    )
    form4 = _one(
        connection,
        """
        SELECT event_id FROM ingest.form4_events
        WHERE ticker = %s AND filed_at IS NOT NULL AND filed_at >= %s AND filed_at < %s
        LIMIT 1
        """,
        (ticker, start, cutoff),
    )
    if "sec_8k" in kinds or filing is not None:
        tags.append("8-K")
    if "form4" in kinds or form4 is not None:
        tags.append("Form 4")
    return tags


def _ranks(connection, day):
    chosen = {}
    for row in _rows(
        connection,
        """
        SELECT group_id, session, rank
        FROM marketstate.rotation
        WHERE trade_date = %s AND rank IS NOT NULL
        """,
        (day,),
    ):
        current = chosen.get(row["group_id"])
        if current is None or (row["session"] == "post" and current["session"] != "post"):
            chosen[row["group_id"]] = row
    return chosen


def _move_row(row, peers, rank, anomaly_names, connection, day, cutoff):
    peers_out = [
        {"ticker": peer["ticker"], "ret": peer["ret"]} for peer in sorted(peers, key=lambda item: item["ticker"])
    ]
    return {
        "ticker": row["ticker"],
        "ret": row["ret"],
        "resid_z": row["resid_z"],
        "primary_basket": row["primary_basket"] if row["primary_basket"] else MISSING,
        "has_anomaly": row["ticker"] in anomaly_names,
        "peers": peers_out,
        "rank": rank if rank is not None else MISSING,
        "tags": _tags(connection, day, cutoff, row["ticker"]),
    }


def _peers(daily, row):
    basket = row["primary_basket"]
    if not basket:
        return []
    found = []
    for other in daily.values():
        if other["ticker"] == row["ticker"] or other["primary_basket"] != basket or other["ret"] is None:
            continue
        if other["ret"] * row["ret"] > 0 and abs(other["ret"]) * 3 >= abs(row["ret"]):
            found.append(other)
    return found


def _move_board(connection, day, cutoff, anomalies):
    daily = _prefer_session(
        _rows(
            connection,
            """
            SELECT ticker, session, ret, resid_z, primary_basket
            FROM marketstate.daily
            WHERE trade_date = %s AND ret IS NOT NULL
            """,
            (day,),
        )
    )
    pool, etfs = _universe()
    allowed = _eligible(connection, day, pool, etfs)
    anomaly_names = {name for anomaly in anomalies for name in _tickers(anomaly["members"])}
    ranks = _ranks(connection, day)
    linked, single = [], []
    for row in daily.values():
        if row["ticker"] not in allowed or abs(row["ret"]) < _MOVE_ABS:
            continue
        peers = _peers(daily, row)
        rank_row = ranks.get(row["primary_basket"])
        item = _move_row(
            row,
            peers,
            None if rank_row is None else rank_row["rank"],
            anomaly_names,
            connection,
            day,
            cutoff,
        )
        if peers or row["ticker"] in anomaly_names:
            linked.append(item)
        else:
            single.append(item)
    linked.sort(key=lambda item: item["ticker"])
    single.sort(key=lambda item: item["ticker"])
    return {"联动": linked, "单股事件": single}


def _anomaly_public(anomaly, events, tickers, acted, missed):
    names = _tickers(anomaly["members"])
    view = events.get(anomaly["anomaly_id"])
    return {
        "anomaly_id": anomaly["anomaly_id"],
        "layer": anomaly["layer"],
        "severity": anomaly["severity"],
        "baskets": list(anomaly["baskets"] or []),
        "members": [{"ticker": name} for name in names],
        "direction": anomaly["direction"],
        "max_abs_z": anomaly["max_abs_z"],
        "universe": anomaly["universe"],
        "status": anomaly["status"],
        "disposition": _disposition(
            view, _cooling_on(tickers, names), bool(set(names) & acted), anomaly["anomaly_id"] in missed
        ),
    }


def page_market(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    tickers, _, _ = _overlay(connection, day, cutoff)
    plan = _plan(connection, day, cutoff)
    payload = plan["payload"] if plan and isinstance(plan["payload"], dict) else {}
    acted = _acted(_orders(connection, day), payload)
    missed = _confirmed_misses(connection, cutoff)
    market = _one(
        connection,
        "SELECT l1_state, spy_5d_pct, vix, shock_flag FROM marketstate.market WHERE trade_date = %s",
        (day,),
    )
    tag = _one(
        connection,
        "SELECT systemic_event_tag FROM perception.market_day WHERE trade_date = %s",
        (day,),
    )
    l1 = market["l1_state"] if market else MISSING
    return {
        "page": "/market",
        "date": day,
        "layers": {
            "L1": {"state": l1, "coverage": MISSING},
            "L2": {"state": MISSING, "coverage": MISSING},
            "L3": {"state": MISSING, "coverage": MISSING},
            "L4": {"state": MISSING, "coverage": MISSING},
        },
        "market": None
        if market is None
        else {
            "l1_state": market["l1_state"],
            "spy_5d_pct": market["spy_5d_pct"],
            "vix": market["vix"],
            "shock_flag": market["shock_flag"],
        },
        "anomalies": [_anomaly_public(row, events, tickers, acted, missed) for row in anomalies],
        "linkage_events": [
            {
                "event_id": view["event_id"],
                "anomaly_id": view["anomaly_id"],
                "lifecycle": view["lifecycle"],
                "mechanism": view["mechanism"],
            }
            for view in events.values()
        ],
        "systemic_event_tag": tag["systemic_event_tag"] if tag else MISSING,
        "move_board": _move_board(connection, day, cutoff, anomalies),
        "sections": {
            "layers": _section(connection, day, cutoff, "market_structure"),
            "moves": _section(connection, day, cutoff, "bars_full"),
        },
    }


def _passthrough_ticker(tickers, by_event, completeness, event_id, names):
    exposure = by_event.get(event_id, MISSING) if event_id else MISSING
    if len(names) == 1 and isinstance(tickers.get(names[0]), dict):
        item = tickers[names[0]]
        return {
            "exposure": exposure,
            "cooling_status": item.get("cooling_status", MISSING),
            "m8_gaps": item.get("m8_gaps", MISSING),
            "m8_completeness": completeness,
        }
    if names:
        return {
            "exposure": exposure,
            "cooling_status": {
                name: tickers[name].get("cooling_status", MISSING)
                for name in names
                if isinstance(tickers.get(name), dict)
            }
            or MISSING,
            "m8_gaps": {
                name: tickers[name].get("m8_gaps", MISSING) for name in names if isinstance(tickers.get(name), dict)
            }
            or MISSING,
            "m8_completeness": completeness,
        }
    return {
        "exposure": exposure,
        "cooling_status": MISSING,
        "m8_gaps": MISSING,
        "m8_completeness": completeness,
    }


def _report(connection, anomaly_id):
    row = _one(connection, "SELECT report FROM perception.reports WHERE anomaly_id = %s", (anomaly_id,))
    if row is None or not isinstance(row["report"], dict):
        return {}
    return row["report"]


def _linkage_body(connection, day, cutoff, view, names, tickers, by_event, completeness):
    anomaly_id = None if view is None else view["anomaly_id"]
    report = {} if anomaly_id is None else _report(connection, anomaly_id)
    candidates = []
    if anomaly_id is not None:
        candidates = _rows(
            connection,
            """
            SELECT candidate_id, mechanism, score, confidence, evidence, chain, affected, magnitude
            FROM perception.candidates
            WHERE anomaly_id = %s
            ORDER BY candidate_id
            """,
            (anomaly_id,),
        )
    timeline = []
    generated = None
    if anomaly_id is not None:
        anomaly = _one(
            connection,
            "SELECT generated_at FROM perception.anomalies WHERE anomaly_id = %s",
            (anomaly_id,),
        )
        generated = None if anomaly is None else anomaly["generated_at"]
        for row in _rows(
            connection,
            """
            SELECT info_id, published_at, relevance
            FROM perception.retrievals
            WHERE anomaly_id = %s AND (published_at IS NULL OR published_at < %s)
            ORDER BY info_id
            """,
            (anomaly_id, cutoff),
        ):
            published = row["published_at"]
            mark = None
            if published is not None and generated is not None and published > generated:
                mark = "晚于异常"
            timeline.append(
                {"info_id": row["info_id"], "published_at": published, "relevance": row["relevance"], "mark": mark}
            )
    hits = []
    tracks = []
    impact = None
    if view is not None:
        hits = _rows(
            connection,
            """
            SELECT info_id, expected_z, control_z, outcome, published_at
            FROM perception.second_hits
            WHERE event_id = %s AND published_at < %s
            ORDER BY info_id
            """,
            (view["event_id"], cutoff),
        )
        tracks = _rows(
            connection,
            """
            SELECT trade_date, emotion, capital, fundamental, metrics
            FROM perception.tracks
            WHERE event_id = %s AND trade_date = %s
            """,
            (view["event_id"], day),
        )
    if anomaly_id is not None:
        impact = _one(
            connection,
            """
            SELECT total_residual, event_part, amplification, unexplained
            FROM perception.impact_decomposition
            WHERE anomaly_id = %s
            """,
            (anomaly_id,),
        )
    passed = _passthrough_ticker(tickers, by_event, completeness, None if view is None else view["event_id"], names)
    return {
        "page": "/linkage/{id}",
        "date": day,
        "event_id": None if view is None else view["event_id"],
        "lifecycle": MISSING if view is None else view["lifecycle"],
        "evidence_timeline": timeline,
        "candidates": candidates,
        "magnitude_channels": report.get("magnitude_channels", MISSING),
        "second_hits": hits,
        "chain": report.get("weakest_link", MISSING),
        "fingerprint": report.get("market_fingerprint", MISSING),
        "dimensions": tracks[0] if tracks else MISSING,
        "tracking": report.get("tracking", MISSING),
        "constraints": report.get("constraint_conclusion", MISSING),
        "impact": impact if impact is not None else MISSING,
        **passed,
    }


def page_linkage(connection, day, clock, event_id):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    view = next((item for item in events.values() if item["event_id"] == event_id), None)
    names = []
    if view is not None:
        anomaly = next(row for row in anomalies if row["anomaly_id"] == view["anomaly_id"])
        names = _tickers(anomaly["members"])
    tickers, by_event, completeness = _overlay(connection, day, cutoff)
    body = _linkage_body(connection, day, cutoff, view, names, tickers, by_event, completeness)
    body["sections"] = {"attribution": _section(connection, day, cutoff, "attribution_candidates")}
    return body


def _what_changed(report):
    if not report:
        return MISSING
    return {
        "scope": report.get("scope", MISSING),
        "fundamental_standing": report.get("fundamental_standing", MISSING),
        "market_confidence": report.get("market_confidence", MISSING),
    }


def page_stock(connection, day, clock, symbol):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    tickers, by_event, completeness = _overlay(connection, day, cutoff)
    links = []
    reports = []
    for anomaly in anomalies:
        names = _tickers(anomaly["members"])
        if symbol not in names:
            continue
        view = events.get(anomaly["anomaly_id"])
        passed = _passthrough_ticker(
            tickers,
            by_event,
            completeness,
            None if view is None else view["event_id"],
            [symbol],
        )
        links.append(
            {
                "anomaly_id": anomaly["anomaly_id"],
                "event_id": None if view is None else view["event_id"],
                "lifecycle": MISSING if view is None else view["lifecycle"],
                **passed,
            }
        )
        report = _report(connection, anomaly["anomaly_id"])
        if report:
            reports.append(report)
    profile = _one(
        connection,
        "SELECT profile FROM fundamentals.profile WHERE as_of = %s AND ticker = %s",
        (day, symbol),
    )
    return {
        "page": "/stock/{symbol}",
        "date": day,
        "symbol": symbol,
        "linkage_events": links,
        "what_changed": _what_changed(reports[0]) if reports else MISSING,
        "fundamental_profile": profile["profile"] if profile else MISSING,
        "m8_completeness": completeness,
        "sections": {
            "attribution": _section(connection, day, cutoff, "attribution_candidates"),
            "fundamentals": _section(connection, day, cutoff, "m2_financials"),
        },
    }


def _status_basis(evidence):
    if isinstance(evidence, dict) and isinstance(evidence.get("status_basis"), str):
        return evidence["status_basis"]
    return None


def page_graph(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    rows = _rows(
        connection,
        """
        SELECT relation_id, from_entity, to_entity, connection_type, mechanism, status,
               exposure_usd, strength, evidence
        FROM graph.relations
        WHERE first_discovered_at < %s AND (reviewed_at IS NULL OR reviewed_at < %s)
        ORDER BY relation_id
        """,
        (cutoff, cutoff),
    )
    return {
        "page": "/graph",
        "date": day,
        "relations": [
            {
                "relation_id": row["relation_id"],
                "from_entity": row["from_entity"],
                "to_entity": row["to_entity"],
                "connection_type": row["connection_type"],
                "mechanism": row["mechanism"],
                "status": row["status"],
                "status_basis": _status_basis(row["evidence"]),
                "exposure_usd": row["exposure_usd"],
                "strength": row["strength"],
                "evidence": row["evidence"],
            }
            for row in rows
        ],
    }


def page_settings(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    sources = []
    for row in _rows(
        connection,
        """
        SELECT source, status, latency_sec, items_last_run
        FROM ingest.source_health
        WHERE last_attempt_at < %s
        ORDER BY source
        """,
        (cutoff,),
    ):
        if row["status"] == UNCONNECTED:
            sources.append({"source": row["source"], "status": UNCONNECTED, "display": UNCONNECTED})
        else:
            sources.append(
                {
                    "source": row["source"],
                    "status": row["status"],
                    "display": row["status"],
                    "latency_sec": row["latency_sec"],
                    "items_last_run": row["items_last_run"],
                }
            )
    return {
        "page": "/settings/data",
        "date": day,
        "sources": sources if sources else MISSING,
        "sections": {"sources": _section(connection, day, cutoff, "bars_full")},
    }


def _candidate_tickers(connection, anomalies):
    if not anomalies:
        return []
    ids = [row["anomaly_id"] for row in anomalies]
    found = []
    for row in _rows(
        connection,
        "SELECT affected FROM perception.candidates WHERE anomaly_id = ANY(%s)",
        (ids,),
    ):
        found.extend(_tickers(row["affected"]))
    return found


def _ledger(connection, day, cutoff):
    return _one(
        connection,
        """
        SELECT cash, equity, peak_equity, state, observed_at, phase
        FROM trading.ledger
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        (day, cutoff),
    )


def _position_tickers(state):
    if not isinstance(state, dict):
        return []
    positions = state.get("positions")
    if isinstance(positions, dict):
        return [key for key in positions if isinstance(key, str)]
    return _tickers(positions)


def _timeline_records(connection, day, cutoff, anomalies):
    plan = _plan(connection, day, cutoff)
    payload = plan["payload"] if plan and isinstance(plan["payload"], dict) else {}
    ledger = _ledger(connection, day, cutoff)
    required = set(_position_tickers(None if ledger is None else ledger["state"]))
    required.update(_candidate_tickers(connection, anomalies))
    grouped = {ticker: [] for ticker in required}
    for skip in payload.get("skips") or []:
        if not isinstance(skip, dict) or skip.get("ticker") not in grouped:
            continue
        grouped[skip["ticker"]].append(
            {
                "ticker": skip["ticker"],
                "kind": "不动",
                "n_code": skip.get("n_code", MISSING),
                "next_check_date": skip.get("next_check_date", MISSING),
                "reason_zh": skip.get("reason_zh"),
            }
        )
    if anomalies:
        ids = [row["anomaly_id"] for row in anomalies]
        for row in _rows(
            connection,
            """
            SELECT ticker, n_code, exposure, mechanism, note
            FROM perception.ticker_status
            WHERE anomaly_id = ANY(%s)
            ORDER BY ticker
            """,
            (ids,),
        ):
            if row["ticker"] not in grouped:
                continue
            grouped[row["ticker"]].append(
                {
                    "ticker": row["ticker"],
                    "kind": "不动",
                    "n_code": row["n_code"],
                    "next_check_date": MISSING,
                    "exposure": row["exposure"],
                    "mechanism": row["mechanism"],
                    "note": row["note"],
                }
            )
    lines = []
    for ticker in sorted(grouped):
        if grouped[ticker]:
            lines.extend(grouped[ticker])
        else:
            lines.append({"ticker": ticker, "text": MISSING})
    return lines


def _paper(page, day, extra):
    return {"page": page, "date": day, "label": PAPER_LABEL, **extra}


def page_plan(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    plan = _plan(connection, day, cutoff)
    payload = None if plan is None else plan["payload"]
    if isinstance(payload, dict) and "input_completeness" in payload:
        completeness = payload["input_completeness"]
    else:
        completeness = COMPLETENESS_MISSING
    n9 = _rows(
        connection,
        """
        SELECT ticker, factor_id, version, value, would_pass, rule_a_entry_pass, gap_detail
        FROM factor_shadow.daily
        WHERE date = %s AND generated_at < %s AND would_pass IS TRUE AND rule_a_entry_pass IS FALSE
        ORDER BY ticker, factor_id
        """,
        (day, cutoff),
    )
    shadow = _rows(
        connection,
        """
        SELECT signal_key, signal, ticker, event_id, condition_detail, shadow_action, rule_a_action, params_version
        FROM perception_shadow.signals
        WHERE date = %s
        ORDER BY signal_key
        """,
        (day,),
    )
    return _paper(
        "/paper/plan",
        day,
        {
            "plan": payload if payload is not None else MISSING,
            "input_completeness": completeness,
            "n9_records": n9,
            "shadow_summary": shadow,
            "sections": {"plan": _section(connection, day, cutoff, "paper_plan")},
        },
    )


def page_portfolio(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    ledger = _ledger(connection, day, cutoff)
    plan = _plan(connection, day, cutoff)
    payload = plan["payload"] if plan and isinstance(plan["payload"], dict) else {}
    portfolio = payload.get("portfolio") if isinstance(payload.get("portfolio"), dict) else {}
    state = ledger["state"] if ledger and isinstance(ledger["state"], dict) else {}
    panels = _rows(
        connection,
        """
        SELECT ticker, payload FROM valuation_v1.position_panel
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY ticker
        """,
        (day, cutoff),
    )
    return _paper(
        "/paper/portfolio",
        day,
        {
            "holdings": state.get("positions", MISSING),
            "tier_budget": portfolio.get("tier_usage", MISSING),
            "gates": portfolio.get("gates", MISSING),
            "cash": None if ledger is None else ledger["cash"],
            "equity": None if ledger is None else ledger["equity"],
            "peak_equity": None if ledger is None else ledger["peak_equity"],
            "valuation_position_panel": [row["payload"] for row in panels],
            "valuation_label": VALUATION_LABEL,
            "timeline": _timeline_records(connection, day, cutoff, anomalies),
            "sections": {
                "portfolio": _section(connection, day, cutoff, "rule_a_scores"),
                "valuation": _section(connection, day, cutoff, "valuation_v1"),
            },
        },
    )


def _books(score):
    if score is None:
        return MISSING
    return {
        "quality": score["quality"],
        "growth": score["growth"],
        "valuation": score["valuation"],
        "timing": score["timing"],
    }


def _scores(connection, day):
    rows = _rows(
        connection,
        """
        SELECT ticker, quality, growth, valuation, timing
        FROM trading.daily_scores
        WHERE signal_date = %s
        """,
        (day,),
    )
    return {row["ticker"]: row for row in rows}


def _health_map(connection):
    rows = _rows(
        connection,
        """
        SELECT ticker, health_codes, can_score, can_trade, reason, latest_period_end, latest_filed
        FROM fundamentals.health
        """,
        (),
    )
    return {row["ticker"]: row for row in rows}


def _ranges(connection, day, cutoff):
    rows = _rows(
        connection,
        """
        SELECT ticker, bear, neutral, bull, status, payload
        FROM valuation_v1.ranges
        WHERE trade_date = %s AND observed_at < %s
        """,
        (day, cutoff),
    )
    return {row["ticker"]: row for row in rows}


def _factor_map(connection, day, cutoff):
    rows = _rows(
        connection,
        """
        SELECT ticker, factor_id, version, value, would_pass, rule_a_entry_pass, gap_detail
        FROM factor_shadow.daily
        WHERE date = %s AND generated_at < %s
        ORDER BY ticker, factor_id
        """,
        (day, cutoff),
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row["ticker"], []).append(row)
    return grouped


def _event_states(anomalies, events):
    states = {}
    for anomaly in anomalies:
        view = events.get(anomaly["anomaly_id"])
        if view is None:
            continue
        for name in _tickers(anomaly["members"]):
            states.setdefault(name, []).append(view["lifecycle"])
    return states


def _universe_row(ticker, health, score, ranges, factors, states):
    row_health = health.get(ticker)
    return {
        "ticker": ticker,
        "health_codes": MISSING if row_health is None else row_health["health_codes"],
        "books": _books(score.get(ticker)),
        "can_trade": MISSING if row_health is None else row_health["can_trade"],
        "blocker": MISSING if row_health is None else row_health["reason"],
        "event_state": states.get(ticker, MISSING),
        "valuation_reference": ranges.get(ticker, MISSING),
        "factor_shadow": factors.get(ticker, MISSING),
        "valuation_label": VALUATION_LABEL,
    }


def page_universe(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    pool, _ = _universe()
    health = _health_map(connection)
    scores = _scores(connection, day)
    ranges = _ranges(connection, day, cutoff)
    factors = _factor_map(connection, day, cutoff)
    states = _event_states(anomalies, events)
    return _paper(
        "/paper/universe",
        day,
        {
            "rows": [_universe_row(ticker, health, scores, ranges, factors, states) for ticker in pool],
            "valuation_label": VALUATION_LABEL,
            "sections": {"scores": _section(connection, day, cutoff, "rule_a_scores")},
        },
    )


def page_paper_stock(connection, day, clock, symbol):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    anomalies = _anomalies(connection, day, cutoff)
    history = _rows(
        connection,
        """
        SELECT signal_date, quality, growth, valuation, timing
        FROM trading.daily_scores
        WHERE ticker = %s AND signal_date <= %s
        ORDER BY signal_date
        """,
        (symbol, day),
    )
    profile = _one(
        connection,
        "SELECT profile FROM fundamentals.profile WHERE as_of = %s AND ticker = %s",
        (day, symbol),
    )
    ranges = _ranges(connection, day, cutoff).get(symbol, MISSING)
    factors = _factor_map(connection, day, cutoff).get(symbol, MISSING)
    lines = [row for row in _timeline_records(connection, day, cutoff, anomalies) if row["ticker"] == symbol]
    if not lines:
        lines = [{"ticker": symbol, "text": MISSING}]
    return _paper(
        "/paper/stock/{symbol}",
        day,
        {
            "symbol": symbol,
            "books_history": [_books(row) | {"signal_date": row["signal_date"]} for row in history] or MISSING,
            "timeline": lines,
            "valuation_card": ranges,
            "valuation_label": VALUATION_LABEL,
            "fundamental_profile": profile["profile"] if profile else MISSING,
            "factor_shadow": factors,
        },
    )


def page_health(connection, day, clock):
    _, closed = _open(clock, day)
    if closed is not None:
        return closed
    rows = _rows(
        connection,
        """
        SELECT ticker, latest_period_end, latest_filed, latest_8k_202, health_codes, can_score, can_trade, reason
        FROM fundamentals.health
        ORDER BY ticker
        """,
        (),
    )
    return _paper("/paper/health", day, {"health": rows if rows else MISSING})


def page_ledger(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return closed
    fills = _rows(
        connection,
        """
        SELECT order_id, ticker, side, qty, fill_price, cost, status, trade_date, signal_date
        FROM trading.orders
        WHERE trade_date = %s AND status = 'filled'
        ORDER BY order_id
        """,
        (day,),
    )
    snapshots = _rows(
        connection,
        """
        SELECT phase, cash, equity, peak_equity, observed_at
        FROM trading.ledger
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY observed_at
        """,
        (day, cutoff),
    )
    return _paper(
        "/paper/ledger",
        day,
        {
            "fills": fills,
            "snapshots": snapshots,
            "sections": {"ledger": _section(connection, day, cutoff, "paper_plan")},
        },
    )


def _object(value):
    if isinstance(value, str):
        return json.loads(value)
    return value if isinstance(value, dict) else {}


def page_review(connection, day, clock):
    del clock
    _, cutoff = _window(day)
    cases = _rows(
        connection,
        """
        SELECT case_id, anomaly_id, trade_date, status, reason
        FROM perception.cases
        WHERE trade_date <= %s
        ORDER BY case_id
        """,
        (day,),
    )
    labels = _rows(
        connection,
        """
        SELECT case_id, horizon, as_of, drafted, reason, labels
        FROM perception.case_labels
        WHERE as_of <= %s AND written_at < %s
        ORDER BY case_id, horizon
        """,
        (day, cutoff),
    )
    grouped = {}
    for row in labels:
        grouped.setdefault(row["case_id"], []).append(
            {
                "horizon": row["horizon"],
                "as_of": row["as_of"],
                "drafted": row["drafted"],
                "reason": row["reason"],
                "labels": _object(row["labels"]),
            }
        )
    weekly = _one(
        connection,
        """
        SELECT payload FROM perception.reports_weekly
        WHERE report_id LIKE 'week:%%' AND period_end <= %s AND generated_at < %s
        ORDER BY period_end DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    monthly = _one(
        connection,
        """
        SELECT payload FROM perception.reports_monthly
        WHERE period_end <= %s AND generated_at < %s
        ORDER BY period_end DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    samples = _rows(
        connection,
        """
        SELECT item_ref, discovered, judgment, gap_ring, anomaly_id
        FROM perception.miss_samples
        WHERE period_end <= %s AND (judged_at IS NULL OR judged_at < %s)
        ORDER BY sample_id
        """,
        (day, cutoff),
    )
    patterns = _rows(
        connection,
        """
        SELECT pattern_id, trigger_type, mechanism, capital_behavior, outcome,
               example_count, retained_holds, status, examples, counterexamples
        FROM perception.patterns
        WHERE updated_at < %s
        ORDER BY pattern_id
        """,
        (cutoff,),
    )
    return {
        "page": "/review",
        "date": day,
        "案例库": [
            {
                "case_id": row["case_id"],
                "anomaly_id": row["anomaly_id"],
                "trade_date": row["trade_date"],
                "status": row["status"],
                "reason": row["reason"],
                "labels": grouped.get(row["case_id"], []),
            }
            for row in cases
        ],
        "周报": _object(weekly["payload"]) if weekly else {},
        "月报": _object(monthly["payload"]) if monthly else {},
        "漏检报告": samples,
        "模式库候选": patterns,
    }
