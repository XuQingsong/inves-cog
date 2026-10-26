"""B-064: batched Chinese translation of the day's page-visible news headlines.

Candidates are the same rows the today page shows: the feed whitelist (the
first 40 the page can expand to), hot themes, mover rows and earnings
previews. Each batch is at most 50 titles, translated verbatim with the fixed
prompt in docs/phase1/design/b064-translate-prompt.md. Calls are capped per
ET day; usage metering reuses ingest.llm_calls via the standard Client.
"""

import json
import logging
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from inves_cog.ingest.market import NY, trading_day
from inves_cog.perception.news.rules import feed_keep, rank_day, theme_of

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[4]
PROMPT_PATH = ROOT / "docs" / "phase1" / "design" / "b064-translate-prompt.md"
UNIVERSE_PATH = ROOT / "config" / "universe.yaml"
TASK = "news_translate"
BATCH = 50
MAX_CALLS_PER_DAY = 6
MAX_TOKENS_PER_DAY = 50_000


def _prompt():
    """Return (system, user_template) from the fixed prompt document, verbatim."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    system = re.search(r"## system\n(.*?)## user", text, re.S).group(1).strip()
    user = re.search(r"（每批最多 50 条）\n(.*)", text, re.S).group(1).strip()
    return system, user


def _universe():
    stocks = yaml.safe_load(UNIVERSE_PATH.read_text())["stocks"]
    return [row["ticker"] for row in stocks]


def _day_window(day):
    start = datetime.combine(day, time(4, 0), tzinfo=NY)
    return start, start + timedelta(days=1)


def page_candidates(connection, day, cutoff):
    """info_ids the today page can show for `day`, in page order."""
    start, end = _day_window(day)
    rows = connection.execute(
        """
        SELECT info_id, published_at, first_seen_at, source, headline, tickers, url
        FROM ingest.info_items
        WHERE kind = 'news' AND published_at >= %s AND published_at < %s
        ORDER BY published_at DESC, info_id
        """,
        (start, end),
    ).fetchall()
    items = [dict(row) for row in rows]
    holdings = _holdings(connection, day, cutoff)
    universe = set(_universe()) | holdings
    ranked = rank_day(items, universe, holdings, day)
    seen, ordered = set(), []

    def take(item):
        if item["info_id"] not in seen:
            seen.add(item["info_id"])
            ordered.append(item)

    feed = [n for n in ranked if _feed_keep(n["rule"], holdings)][:40]
    for n in feed:
        take(n)
    grouped = _groups(connection)
    theme_map = {t: sector for sector in grouped for t in grouped[sector]}
    by_theme = {}
    for n in ranked:
        if n["rule"].weak_rating_only:
            continue
        theme = theme_of(n, theme_map, holdings)
        if theme:
            by_theme.setdefault(theme, []).append(n)
    for _theme, group in sorted(by_theme.items(), key=lambda kv: (-max(i["rule"].importance for i in kv[1]), kv[0])):
        for n in sorted(group, key=lambda n: (-n["rule"].importance, n["published"]))[:1]:
            take(n)
    for ticker in _mover_tickers(connection, day, universe, holdings):
        own = sorted(
            (n for n in ranked if ticker in n["rule"].primary_tickers),
            key=lambda n: (-n["rule"].importance, n["published"]),
        )
        for n in own[:1]:
            take(n)
    for n in ranked:
        if "财报前瞻" in n["rule"].tags:
            take(n)
    return ordered


def _feed_keep(rule, holdings):
    return feed_keep(rule, holdings)


def _holdings(connection, day, cutoff):
    row = connection.execute(
        """
        SELECT state FROM trading.ledger
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY observed_at DESC LIMIT 1
        """,
        (day, cutoff),
    ).fetchone()
    if row is None:
        row = connection.execute(
            """
            SELECT state FROM trading.ledger
            WHERE trade_date < %s AND observed_at < %s
            ORDER BY trade_date DESC, observed_at DESC LIMIT 1
            """,
            (day, cutoff),
        ).fetchone()
    state = (row or {}).get("state") if row else None
    positions = state.get("positions") if isinstance(state, dict) else None
    return {t for t in (positions or {})} if isinstance(positions, dict) else set()


def _groups(connection):
    rows = connection.execute(
        "SELECT group_id FROM marketstate.rotation WHERE group_kind = 'sector' AND trade_date = %s",
        (_latest_rotation_day(connection),),
    ).fetchall()
    sectors = [r["group_id"] for r in rows]
    stocks = yaml.safe_load(UNIVERSE_PATH.read_text())["stocks"]
    grouped = {}
    for sector in sectors:
        grouped[sector] = [s["ticker"] for s in stocks if s.get("sector") == sector]
    return grouped


def _latest_rotation_day(connection):
    row = connection.execute("SELECT MAX(trade_date) AS d FROM marketstate.rotation").fetchone()
    return row["d"] if row else None


def _mover_tickers(connection, day, universe, holdings):
    rows = connection.execute(
        """
        SELECT ticker, ret FROM marketstate.daily
        WHERE trade_date = %s AND session = 'close'
        """,
        (day,),
    ).fetchall()
    if not rows:
        prior = connection.execute(
            "SELECT MAX(trade_date) AS d FROM marketstate.daily WHERE trade_date < %s", (day,)
        ).fetchone()
        if prior and prior["d"]:
            rows = connection.execute(
                """
                SELECT ticker, ret FROM marketstate.daily
                WHERE trade_date = %s AND session = 'close'
                """,
                (prior["d"],),
            ).fetchall()
    members = {r["ticker"]: r["ret"] for r in rows if r["ticker"] in universe and r["ret"] is not None}
    return sorted(members, key=lambda t: -abs(members[t]))[:8]


def translate_day(connection, writer, client, day, *, clock):
    """Translate today's page candidates that lack a Chinese title.

    connection: read DSN; writer: role_perception connection; client: object with
    .call(task, payload) -> dict (the LLM Client or a counting fake in tests).
    Returns a summary dict. Caps: <=6 calls, <=50k tokens per ET day, tracked in
    ingest.llm_calls via the standard recorder.
    """
    if not trading_day(day):
        return {"status": "skipped", "reason": "non_trading_day", "day": str(day)}
    usage = _usage(connection, day)
    if usage["calls"] >= MAX_CALLS_PER_DAY:
        return {"status": "capped", "reason": "calls", **usage}
    _, user_template = _prompt()
    cutoff = clock.now_utc().astimezone(NY)
    candidates = page_candidates(connection, day, cutoff)
    if not candidates:
        return {"status": "ok", "translated": 0, "remaining": 0}
    ids = [n["info_id"] for n in candidates]
    have = set()
    if writer is not None:
        rows = writer.execute(
            "SELECT info_id FROM perception.news_translations WHERE info_id = ANY(%s)", (ids,)
        ).fetchall()
        have = {r["info_id"] for r in rows}
    todo = [n for n in candidates if n["info_id"] not in have]
    calls, tokens, written = usage["calls"], usage["tokens"], 0
    for start in range(0, len(todo), BATCH):
        if calls >= MAX_CALLS_PER_DAY or tokens >= MAX_TOKENS_PER_DAY:
            log.info("news_translate day cap reached calls=%s tokens=%s", calls, tokens)
            break
        batch = todo[start : start + BATCH]
        headlines = [n["headline"] or "" for n in batch]
        user = user_template.replace("{headlines_json_array}", json.dumps(headlines, ensure_ascii=False))
        try:
            result = client.call(
                TASK,
                {"system": _prompt()[0], "user": user, "count": len(batch)},
            )
        except Exception as exc:  # noqa: BLE001 - failure logged, next batch still attempted
            log.warning("news_translate call failed: %s", type(exc).__name__)
            break
        titles = result.get("titles") if isinstance(result, dict) else None
        if isinstance(result, dict) and titles is None and isinstance(result.get("items"), list):
            titles = result["items"]
        if not isinstance(titles, list) or len(titles) != len(batch):
            log.warning("news_translate count mismatch expected=%s got=%s", len(batch), titles)
            calls += 1
            continue
        for item, title in zip(batch, titles, strict=True):
            writer.execute(
                """
                INSERT INTO perception.news_translations (info_id, title_zh, model, translated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (info_id) DO NOTHING
                """,
                (item["info_id"], str(title), "deepseek-v4.1-flash", clock.now_utc()),
            )
            written += 1
        calls += 1
    return {"status": "ok", "translated": written, "remaining": len(todo) - written, "calls": calls}


def _usage(connection, day):
    """Today's recorded calls/token spend for this task in ingest.llm_calls."""
    start, _ = _day_window(day)
    row = connection.execute(
        """
        SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
        FROM ingest.llm_calls
        WHERE task = %s AND created_at >= %s AND created_at < %s
        """,
        (TASK, start, start + timedelta(days=1)),
    ).fetchone()
    return {"calls": int(row["calls"]), "tokens": int(row["tokens"])}
