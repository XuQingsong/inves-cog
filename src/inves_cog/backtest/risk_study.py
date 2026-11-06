"""Historical-panel risk statistics; no trading engine or production imports."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import timedelta
from math import ceil, sqrt
from statistics import stdev

from .selection_gap import quantile


@dataclass
class PriceSeries:
    days: list
    values: list

    @classmethod
    def from_prices(cls, prices):
        days = sorted(d for d, v in prices.items() if v is not None and v > 0)
        return cls(days, [prices[d] for d in days])

    def index(self, day):
        return bisect_right(self.days, day) - 1

    def at(self, day):
        i = self.index(day)
        return self.values[i] if i >= 0 else None


def max_drawdown(values):
    high, low = None, 0.0
    for value in values:
        high = value if high is None else max(high, value)
        low = min(low, 100 * (value / high - 1))
    return low


def horizon_metrics(prices, spy, start, weeks):
    p = prices if isinstance(prices, PriceSeries) else PriceSeries.from_prices(prices)
    s = spy if isinstance(spy, PriceSeries) else PriceSeries.from_prices(spy)
    target = start + timedelta(weeks=weeks)
    if not p.days or not s.days or target > s.days[-1]:
        return None
    i, j = p.index(start), p.index(target)
    if i < 0 or j < i or (start - p.days[i]).days > 7 or s.at(start) is None:
        return None
    # Last available quote is the terminal cash proxy; no invented delisting proceeds.
    return dict(
        excess_pct=100 * ((p.values[j] / p.values[i] - 1) - (s.at(target) / s.at(start) - 1)),
        maxdd_pct=-max_drawdown(p.values[i : j + 1]),
        terminal_quote_proxy=p.days[-1] < target,
        last_quote=p.days[j],
    )


def weights(multiples, variant):
    valid = sorted(v for v in multiples.values() if v is not None)
    cutoff = valid[-ceil(len(valid) / 5)] if valid else None
    raw = {}
    for ticker, value in multiples.items():
        top = cutoff is not None and value is not None and value >= cutoff
        raw[ticker] = 0.0 if variant == "B" and top else 0.5 if variant == "C" and top else 1.0
    total = sum(raw.values())
    return {t: w / total for t, w in raw.items() if w and total} if total else {}


def curve_metrics(curve):
    values = [r["equity"] for r in curve]
    if len(values) < 2:
        return None
    returns = [b / a - 1 for a, b in zip(values[:-1], values[1:], strict=True)]
    years = (curve[-1]["date"] - curve[0]["date"]).days / 365.25
    annualized = 100 * ((values[-1] / values[0]) ** (1 / years) - 1) if years else None
    dd = max_drawdown(values)
    by_year, anchor, year = {}, values[0], curve[0]["date"].year
    previous = values[0]
    for row in curve:
        if row["date"].year != year:
            by_year[str(year)] = 100 * (previous / anchor - 1)
            anchor, year = previous, row["date"].year
        previous = row["equity"]
    by_year[str(year)] = 100 * (previous / anchor - 1)
    return dict(
        cumulative_pct=100 * (values[-1] / values[0] - 1),
        annualized_pct=annualized,
        maxdd_pct=dd,
        annualized_vol_pct=100 * stdev(returns) * sqrt(252),
        return_over_maxdd=annualized / abs(dd) if dd else None,
        yearly=by_year,
    )


def monthly_portfolio(panel, prices, spy, start, variant, memberships=None):
    weeks = sorted(panel)
    days = [d for d in spy.days if d >= start]
    units, curve, month, rebalances = {}, [], None, []
    for day in days:
        equity = sum(q * prices[t].at(day) for t, q in units.items()) if units else 1.0
        if (day.year, day.month) != month or not units:
            index = bisect_left(weeks, day) - 1
            if index >= 0:
                sample = {t: m for t, m in panel[weeks[index]].items() if t in prices and prices[t].at(day) is not None}
                if memberships:
                    from .membership import is_member

                    sample = {t: m for t, m in sample.items() if is_member(memberships.get(t, []), day) is not False}
                    for ticker, events in memberships.items():
                        if (
                            ticker in prices
                            and prices[ticker].at(day) is not None
                            and any(e["action"] == "added" and e["effective"] <= str(day) for e in events)
                            and is_member(events, day)
                        ):
                            sample.setdefault(ticker, None)
                allocations = weights(sample, variant)
                if allocations:
                    units = {t: equity * w / prices[t].at(day) for t, w in allocations.items()}
                    rebalances.append(dict(date=day, panel_date=weeks[index], members=len(sample), held=len(units)))
            month = day.year, day.month
        curve.append(dict(date=day, equity=equity))
    return dict(metrics=curve_metrics(curve), curve=curve, rebalances=rebalances)


def risk_summary(rows):
    result = {}
    for group in ("top_fifth", "rest"):
        for horizon in (52, 104):
            selected = [r for r in rows if r["group"] == group and r["weeks"] == horizon]
            years = sorted({r["year"] for r in selected})
            result[f"{group}_{horizon}"] = {}
            for year in [*years, "all"]:
                sample = [r for r in selected if year == "all" or r["year"] == year]
                excess, dd = [r["excess_pct"] for r in sample], [r["maxdd_pct"] for r in sample]
                result[f"{group}_{horizon}"][str(year)] = dict(
                    n=len(sample),
                    median_excess_pct=quantile(excess, 0.5),
                    below_minus30_pct=100 * sum(v < -30 for v in excess) / len(excess) if excess else None,
                    below_minus50_pct=100 * sum(v < -50 for v in excess) / len(excess) if excess else None,
                    maxdd_median_pct=quantile(dd, 0.5),
                    maxdd_p90_pct=quantile(dd, 0.9),
                    terminal_quote_proxies=sum(r["terminal_quote_proxy"] for r in sample),
                )
    return result
