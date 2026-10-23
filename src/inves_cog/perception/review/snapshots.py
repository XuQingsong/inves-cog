"""One precursor snapshot per pool ticker and basket on each trading day."""

from pathlib import Path

import yaml
from psycopg.types.json import Jsonb

from inves_cog.perception.review.calendar import is_session

MISSING = "数据暂缺"
_UNIVERSE = Path(__file__).resolve().parents[4] / "config" / "universe.yaml"
_DIMENSIONS = (
    ("拥挤度", ("六个月涨幅分位", "篮子内部相关性", "动量暴露")),
    ("空头", ("空头占流通股比例", "回补天数及变化")),
    ("期权", ("看涨看跌持仓比", "隐含波动率分位", "偏度", "到期集中度")),
    ("叙事热度", ("独立来源数", "搜索热度", "榜单名次变化")),
    ("估值", ("p", "delta_g")),
    ("价格结构", ("距均线", "波动率分位", "连续涨跌天数", "beta_share_5d")),
    ("预期", ("修订方向", "修订广度")),
)


def pool_tickers():
    payload = yaml.safe_load(_UNIVERSE.read_text())
    return [row["ticker"] for row in payload["stocks"]]


def write_snapshots(connection, day):
    if not is_session(day):
        return 0
    tickers = pool_tickers()
    baskets = [row["basket_id"] for row in connection.execute("SELECT basket_id FROM graph.baskets ORDER BY basket_id")]
    prices = _beta(connection, day, tickers)
    shorts = _shorts(connection, day, tickers)
    connection.execute("DELETE FROM perception.precursor_snapshots WHERE trade_date = %s", (day,))
    count = 0
    for ticker in tickers:
        _insert(connection, day, "ticker", ticker, _features(prices.get(ticker), shorts.get(ticker)))
        count += 1
    for basket in baskets:
        _insert(connection, day, "basket", basket, _features(None, None))
        count += 1
    return count


def _features(beta, short):
    stored = {}
    if beta is not None:
        stored[("价格结构", "beta_share_5d")] = {"value": beta}
    if short is not None:
        stored[("空头", "空头占流通股比例")] = {"value": short["si_pct_shares_outstanding"]}
        stored[("空头", "回补天数及变化")] = {"value": short["days_to_cover"]}
    features = {}
    for group, names in _DIMENSIONS:
        features[group] = {}
        for name in names:
            features[group][name] = stored.get((group, name), {"reason": MISSING})
    return features


def _beta(connection, day, tickers):
    rows = connection.execute(
        """
        SELECT ticker, beta_share_5d
        FROM marketstate.daily
        WHERE trade_date = %s AND session = 'close' AND ticker = ANY(%s) AND beta_share_5d IS NOT NULL
        """,
        (day, tickers),
    ).fetchall()
    return {row["ticker"]: row["beta_share_5d"] for row in rows}


def _shorts(connection, day, tickers):
    rows = connection.execute(
        """
        SELECT DISTINCT ON (ticker) ticker, si_pct_shares_outstanding, days_to_cover
        FROM ingest.short_interest
        WHERE ticker = ANY(%s) AND publish_date IS NOT NULL AND publish_date <= %s
        ORDER BY ticker, publish_date DESC
        """,
        (tickers, day),
    ).fetchall()
    return {row["ticker"]: row for row in rows}


def _insert(connection, day, kind, subject, features):
    connection.execute(
        """
        INSERT INTO perception.precursor_snapshots (trade_date, subject_kind, subject_id, features)
        VALUES (%s, %s, %s, %s)
        """,
        (day, kind, subject, Jsonb(features)),
    )
