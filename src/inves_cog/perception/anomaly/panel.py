"""File-backed market snapshots. One pass over history, then one detect call per day."""

import gzip
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from inves_cog.marketstate.factors import basket_return, orthogonalize
from inves_cog.marketstate.regression import fit_columns
from inves_cog.marketstate.rotation import SECTORS, STYLES
from inves_cog.marketstate.sic import load_sic, sector_etf
from inves_cog.perception.anomaly.detect import detect_snapshot
from inves_cog.perception.anomaly.universe import pool_names, rotation_names

MACRO_SERIES = {
    "VIX": ("VIX_CBOE", "VIXCLS"),
    "DGS2": ("DGS2",),
    "DTWEXBGS": ("DTWEXBGS",),
    "DCOILWTICO": ("DCOILWTICO",),
}
MEMBERSHIP_NOTE = "成员按导出日的名单回看"


def read_rows(path):
    path = Path(path)
    if path.suffix == ".json":
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, list) else [payload]
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def find_table(directory, stem, bars_name=None):
    directory = Path(directory)
    if bars_name and stem == "bars_daily":
        return directory / bars_name
    for name in (f"{stem}.jsonl.gz", f"{stem}.jsonl", f"{stem}.json", f"{stem}.json.gz"):
        path = directory / name
        if path.is_file():
            return path
    return None


def _parse_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def load_bars(path):
    frame = pd.DataFrame(read_rows(path))
    frame["trade_date"] = frame["trade_date"].map(_parse_date)
    for column in ("open", "high", "low", "close", "volume", "post_close", "adj_factor"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["trade_date", "ticker"])


def active_tickers(basket, day):
    chosen = []
    for member in basket["members"]:
        if isinstance(member, str):
            chosen.append(member)
            continue
        start, end = member.get("effective_from"), member.get("effective_to")
        if (start is None or str(start) <= str(day)) and (end is None or str(day) < str(end)):
            chosen.append(member["ticker"])
    return chosen


def membership_is_constant(baskets):
    for basket in baskets:
        for member in basket["members"]:
            if isinstance(member, str):
                return False
            if member.get("effective_to") not in (None, "") or str(member.get("effective_from")) > "2015-01-01":
                return False
    return True


def rolling_z(series):
    values = series.to_numpy(dtype=float)
    scores = np.full(len(values), np.nan)
    scales = np.full(len(values), np.nan)
    for index, current in enumerate(values):
        prior = values[max(0, index - 120) : index]
        prior = prior[np.isfinite(prior)]
        if len(prior) < 60 or not np.isfinite(current):
            continue
        scale = float(prior.std(ddof=1))
        if scale == 0:
            continue
        scales[index] = scale
        scores[index] = current / scale
    return pd.Series(scores, index=series.index), pd.Series(scales, index=series.index)


def model_frame(target, factors):
    resid, resid_z, sigma, alpha, beta_m = fit_columns(target, factors)
    return pd.DataFrame(
        {"resid": resid, "resid_z": resid_z, "sigma": sigma, "alpha": alpha, "beta_m": beta_m},
        index=target.index,
    )


def _pair_gap(short, long):
    left, right = _mean_corr(short), _mean_corr(long)
    if left is None or right is None:
        return None
    return left - right


def _mean_corr(values):
    finite = np.isfinite(values)
    with np.errstate(invalid="ignore", divide="ignore"):
        deviation = np.nanstd(np.where(finite, values, np.nan), axis=0)
    keep = (finite.sum(axis=0) >= max(5, values.shape[0] // 2)) & (deviation > 0)
    usable = values[:, keep]
    if usable.shape[1] < 2:
        return None
    corr = np.corrcoef(usable, rowvar=False)
    upper = corr[np.triu_indices(corr.shape[0], k=1)]
    upper = upper[np.isfinite(upper)]
    if len(upper) == 0:
        return None
    return float(upper.mean())


def _number(value):
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _pivot(frame, column):
    return frame.pivot(index="trade_date", columns="ticker", values=column).sort_index()


class PricePanel:
    def __init__(self, directory, bars_name=None):
        directory = Path(directory)
        bars = load_bars(find_table(directory, "bars_daily", bars_name))
        basket_path = find_table(directory, "baskets")
        self.baskets = json.loads(basket_path.read_text()) if basket_path else []
        self.membership_note = MEMBERSHIP_NOTE if membership_is_constant(self.baskets) else None
        self._macro_rows = None
        self._short_input = None
        self._build(directory, bars)

    @classmethod
    def from_records(cls, bars, baskets, macro_rows=None, short_rows=None):
        panel = cls.__new__(cls)
        panel.baskets = list(baskets)
        panel.membership_note = MEMBERSHIP_NOTE if membership_is_constant(panel.baskets) else None
        panel._macro_rows = list(macro_rows or [])
        panel._short_input = list(short_rows or [])
        frame = pd.DataFrame(bars)
        frame["trade_date"] = frame["trade_date"].map(_parse_date)
        for column in ("open", "high", "low", "close", "volume", "post_close", "adj_factor"):
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        panel._build(None, frame.sort_values(["trade_date", "ticker"]))
        return panel

    def _build(self, directory, bars):
        as_of = max(bars["trade_date"])
        self.levels = {row["basket_id"]: row["level"] for row in self.baskets}
        self.names = {row["basket_id"]: row["name"] for row in self.baskets}
        self.members = {row["basket_id"]: active_tickers(row, as_of) for row in self.baskets}
        self.classified = pool_names(self.baskets)
        adjusted = bars.assign(adjusted=bars["close"] * bars["adj_factor"])
        self.prices = _pivot(adjusted, "adjusted")
        self.raw_close = _pivot(bars, "close")
        self.opens = _pivot(bars, "open")
        self.volume = _pivot(bars, "volume")
        self.post_close = _pivot(bars, "post_close")
        self.adj = _pivot(bars, "adj_factor")
        self.source = _pivot(bars, "source")
        self.returns = self.prices.pct_change(fill_method=None)
        self.raw_returns = self.raw_close.pct_change(fill_method=None)
        self.sessions = list(self.returns.index)
        self.position = {day: index for index, day in enumerate(self.sessions)}
        self._baskets_and_rotation()
        self._macro(directory)
        self._shorts(directory)
        self._stocks(directory)
        self._ranks()

    def _baskets_and_rotation(self):
        self.basket_ret = {}
        self.basket_z = {}
        self.basket_resid_z = {}
        factor_cache = {}
        market = pd.DataFrame({"m": self.returns["SPY"]})
        for basket in self.baskets:
            identifier = basket["basket_id"]
            own = basket_return(self.returns, self.members[identifier])
            self.basket_ret[identifier] = own
            self.basket_z[identifier] = rolling_z(own)[0]
            factors = self._basket_factors(basket, market, factor_cache)
            self.basket_resid_z[identifier] = model_frame(own, factors)["resid_z"]
        self.rotation = {}
        for ticker in ("SPY", "QQQ", "IWM"):
            if ticker in self.returns:
                self.rotation[("index", ticker)] = self.returns[ticker]
        for ticker in SECTORS:
            if ticker in self.returns:
                self.rotation[("sector", ticker)] = self.returns[ticker]
        for name, pair in STYLES.items():
            if pair[0] in self.returns and pair[1] in self.returns:
                self.rotation[("style", name)] = self.returns[pair[0]] - self.returns[pair[1]]
        for basket in self.baskets:
            if basket["level"] == "L3":
                self.rotation[("l3", basket["basket_id"])] = self.basket_ret[basket["basket_id"]]
        self.rotation_z = {key: rolling_z(series)[0] for key, series in self.rotation.items()}

    def _basket_factors(self, basket, market, cache):
        if basket["level"] != "L3":
            return market
        basis = basket["factor_basis"]
        if basis["kind"] == "l2":
            parent = next(row for row in self.baskets if row["level"] == "L2" and row["name"] == basis["sector"])
            key = ("l2", parent["basket_id"])
            sector = cache.get(key)
            if sector is None and key not in cache:
                series = basket_return(self.returns, self.members[parent["basket_id"]])
                sector = orthogonalize(series, market) if series.notna().any() else None
                cache[key] = sector
            sector = cache[key]
        else:
            columns = [ticker for ticker in basis["tickers"] if ticker in self.returns]
            key = ("bench", tuple(columns))
            if key not in cache:
                series = self.returns[columns].mean(axis=1) if columns else pd.Series(np.nan, index=self.returns.index)
                cache[key] = orthogonalize(series, market) if series.notna().any() else None
            sector = cache[key]
        if sector is None:
            return market
        factors = market.copy()
        factors["s"] = sector
        return factors

    def _macro(self, directory):
        if self._macro_rows is not None:
            rows = self._macro_rows
        else:
            path = find_table(directory, "macro") if directory is not None else None
            rows = read_rows(path) if path else []
        frame = pd.DataFrame(rows)
        self.macro_level = {}
        self.macro_z = {}
        if frame.empty:
            return
        frame["observation_date"] = frame["observation_date"].map(_parse_date)
        frame["realtime_start"] = frame["realtime_start"].map(_parse_date)
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        sessions = pd.DataFrame({"day": pd.to_datetime(self.sessions)})
        for key, series_ids in MACRO_SERIES.items():
            chosen = frame[frame["series_id"].isin(series_ids)].copy()
            if key == "VIX":
                preferred = chosen[chosen["series_id"] == "VIX_CBOE"]
                if not preferred.empty:
                    chosen = preferred
            chosen["visible_on"] = pd.to_datetime(chosen[["observation_date", "realtime_start"]].max(axis=1))
            chosen = chosen.sort_values(["visible_on", "observation_date"]).drop_duplicates("visible_on", keep="last")
            merged = pd.merge_asof(sessions, chosen, left_on="day", right_on="visible_on", direction="backward")
            level = pd.Series(merged["value"].to_numpy(dtype=float), index=self.returns.index)
            self.macro_level[key] = level
            self.macro_z[key] = rolling_z(level.diff())[0]

    def _shorts(self, directory):
        self.short_rows = {}
        if self._short_input is not None:
            rows = self._short_input
        else:
            path = find_table(directory, "short_interest") if directory is not None else None
            rows = read_rows(path) if path else []
        for row in rows:
            settlement = _parse_date(row["settlement_date"])
            visible = self._plus_sessions(settlement, 9)
            if visible is None:
                continue
            self.short_rows.setdefault(row["ticker"], []).append(
                {
                    "visible": visible,
                    "si_pct": row.get("si_pct_shares_outstanding", row.get("si_pct")),
                    "days_to_cover": row.get("days_to_cover"),
                    "publish_date_inferred": row.get("publish_date") in (None, ""),
                }
            )

    def _plus_sessions(self, settlement, lag):
        start = next((index for index, day in enumerate(self.sessions) if day >= settlement), None)
        if start is None or start + lag >= len(self.sessions):
            return None
        return self.sessions[start + lag]

    def _stocks(self, directory):
        rules, ticker_map = load_sic()
        profiles = {}
        path = find_table(directory, "issuer_profiles") if directory is not None else None
        if path is not None:
            for row in read_rows(path):
                profiles[row["ticker"]] = row.get("sic")
        self.l2_of, self.l3_of = {}, {}
        for basket in self.baskets:
            for member in basket["members"]:
                ticker = member["ticker"] if isinstance(member, dict) else member
                if basket["level"] == "L2":
                    self.l2_of[ticker] = basket
                elif basket["level"] == "L3" and (isinstance(member, str) or member.get("primary")):
                    self.l3_of[ticker] = basket
        self.pool = sorted(ticker for ticker in set(self.l2_of) | set(self.l3_of) if ticker in self.returns.columns)
        self.stock = {}
        self.loo = {}
        sector_cache = {}
        for ticker in list(self.pool) + self._wide_tickers():
            if ticker not in self.returns:
                continue
            factors = self._stock_factors(ticker, profiles, rules, ticker_map, sector_cache)
            self.stock[ticker] = model_frame(self.returns[ticker], factors)
            primary = self.l3_of.get(ticker)
            if primary is not None:
                self.loo[ticker] = basket_return(self.returns, self.members[primary["basket_id"]], exclude=ticker)

    def _wide_tickers(self):
        # Sector and style ETFs are rotation inputs. They are not wide stocks.
        skipped = rotation_names()
        return sorted(
            ticker for ticker in self.returns.columns if ticker not in self.classified and ticker not in skipped
        )

    def _stock_factors(self, ticker, profiles, rules, ticker_map, cache):
        factors = pd.DataFrame({"m": self.returns["SPY"]}, index=self.returns.index)
        l2, l3 = self.l2_of.get(ticker), self.l3_of.get(ticker)
        sector = self._sector_series(ticker, l2, profiles, rules, ticker_map, cache)
        if sector is not None:
            factors["s"] = sector
        if l3 is not None and not self._same_leave_one_out(ticker, l2, l3):
            theme = basket_return(self.returns, self.members[l3["basket_id"]], exclude=ticker)
            if theme.notna().any():
                factors["t"] = orthogonalize(theme, factors.copy())
        return factors

    def _sector_series(self, ticker, l2, profiles, rules, ticker_map, cache):
        if l2 is not None:
            key = ("loo", l2["basket_id"], ticker)
            if key not in cache:
                series = basket_return(self.returns, self.members[l2["basket_id"]], exclude=ticker)
                market = pd.DataFrame({"m": self.returns["SPY"]})
                cache[key] = orthogonalize(series, market) if series.notna().any() else None
            return cache[key]
        etf = sector_etf(profiles.get(ticker), rules, ticker=ticker, tickers=ticker_map)
        if etf in (None, "SPY") or etf not in self.returns:
            return None
        key = ("etf", etf)
        if key not in cache:
            cache[key] = orthogonalize(self.returns[etf], pd.DataFrame({"m": self.returns["SPY"]}))
        return cache[key]

    def _same_leave_one_out(self, ticker, l2, l3):
        if l2 is None or l3 is None:
            return False
        left = set(self.members[l2["basket_id"]]) - {ticker}
        right = set(self.members[l3["basket_id"]]) - {ticker}
        return left == right

    def _ranks(self):
        six_month = self.prices[self.pool] / self.prices[self.pool].shift(126) - 1
        self.rank = six_month.rank(axis=1, ascending=False, pct=True)
        prior = self.volume.shift(1)
        self.volume_mult = self.volume / prior.rolling(20, min_periods=10).mean()
        previous_close = self.raw_close.shift(1)
        previous_adj = self.adj.shift(1)
        self.gap = (self.opens * self.adj) / (previous_close * previous_adj) - 1
        self.corr_jump = self._corr_jumps()

    def _corr_jumps(self):
        arrays = {ticker: np.full(len(self.sessions), np.nan) for ticker in self.pool}
        for members in self.members.values():
            columns = [ticker for ticker in members if ticker in arrays]
            if len(columns) < 2:
                continue
            block = self.returns[columns].to_numpy(dtype=float)
            for index in range(60, len(block)):
                gap = _pair_gap(block[index - 20 : index], block[index - 60 : index])
                if gap is None:
                    continue
                for ticker in columns:
                    current = arrays[ticker][index]
                    if not np.isfinite(current) or gap > current:
                        arrays[ticker][index] = gap
        return {ticker: pd.Series(values, index=self.returns.index) for ticker, values in arrays.items()}

    def detect(self, day, session="close"):
        day = _parse_date(day)
        if day not in self.position:
            return []
        return detect_snapshot(self.snapshot(day, session))

    def snapshot(self, day, session="close"):
        index = self.position[day]
        returns = self._session_returns(session)
        baskets, history, member_returns = [], {}, {}
        for identifier, series in self.basket_ret.items():
            ret = _number(returns[identifier].iloc[index] if session == "post" else series.iloc[index])
            if ret is None:
                continue
            baskets.append(
                {
                    "basket_id": identifier,
                    "ret_ew": ret,
                    "resid_z": None if session == "post" else _number(self.basket_resid_z[identifier].iloc[index]),
                }
            )
            window = returns[identifier].iloc[max(0, index - 120) : index + 1]
            history[identifier] = [None if not np.isfinite(value) else float(value) for value in window]
            member_returns[identifier] = self._member_returns(identifier, session, index)
        return {
            "trade_date": day.isoformat(),
            "session": session,
            "baskets": baskets,
            "basket_history": history,
            "member_returns": member_returns,
            "daily": self._daily_rows(index, session),
            "daily_history": self._daily_history(index),
            "rotation": self._rotation_rows(index, session),
            "macro": self._macro_row(index),
            "bars": self._quality_bars(index, session),
            "calendar": self._calendar(day),
            "shorts": self._short_row(day),
            "clusters": [],
            "levels": self.levels,
            "names": self.names,
            "pool": sorted(self.classified),
        }

    def _session_returns(self, session):
        if session != "post":
            return self.basket_ret
        post = {}
        for identifier, members in self.members.items():
            columns = [ticker for ticker in members if ticker in self.post_close]
            if len(columns) < 2:
                post[identifier] = pd.Series(np.nan, index=self.returns.index)
                continue
            ret = self.post_close[columns] / self.raw_close[columns] - 1
            post[identifier] = ret.mean(axis=1).where(ret.notna().sum(axis=1) >= 2)
        return post

    def _member_returns(self, identifier, session, index):
        values = {}
        for ticker in self.members[identifier]:
            ret = self._name_return(ticker, session, index)
            if ret is not None:
                values[ticker] = ret
        return values

    def _name_return(self, ticker, session, index):
        if session == "post":
            if ticker not in self.post_close or ticker not in self.raw_close:
                return None
            return _number((self.post_close[ticker] / self.raw_close[ticker] - 1).iloc[index])
        if ticker not in self.returns:
            return None
        return _number(self.returns[ticker].iloc[index])

    def _daily_rows(self, index, session):
        rows = []
        for ticker, model in self.stock.items():
            if session == "post":
                ret = self._name_return(ticker, session, index)
                resid = None
                resid_z = None
            else:
                ret = _number(self.returns[ticker].iloc[index])
                resid = _number(model["resid"].iloc[index])
                resid_z = _number(model["resid_z"].iloc[index])
            if ret is None and resid_z is None:
                continue
            primary = self.l3_of.get(ticker)
            rows.append(
                {
                    "ticker": ticker,
                    "ret": ret,
                    "resid": resid,
                    "resid_z": resid_z,
                    "sigma": _number(model["sigma"].iloc[index]),
                    "l3_ex_ret": None if ticker not in self.loo else _number(self.loo[ticker].iloc[index]),
                    "primary_basket": None if primary is None else primary["basket_id"],
                    "gap_open": _number(self.gap[ticker].iloc[index]) if ticker in self.gap else None,
                    "volume_mult": (
                        _number(self.volume_mult[ticker].iloc[index]) if ticker in self.volume_mult else None
                    ),
                    "ret_6m_rank": _number(self.rank[ticker].iloc[index]) if ticker in self.rank else None,
                    "corr_jump": _number(self.corr_jump[ticker].iloc[index]) if ticker in self.corr_jump else None,
                }
            )
        return rows

    def _daily_history(self, index):
        history = {}
        for ticker, model in self.stock.items():
            rows = []
            for cursor in range(max(0, index - 4), index + 1):
                rows.append(
                    {
                        "resid": _number(model["resid"].iloc[cursor]),
                        "sigma": _number(model["sigma"].iloc[cursor]),
                        "ret": _number(self.returns[ticker].iloc[cursor]),
                    }
                )
            history[ticker] = rows
        return history

    def _rotation_rows(self, index, session):
        rows = []
        for key, series in self.rotation.items():
            kind, name = key
            if session == "post":
                ret = self._post_group_return(kind, name, index)
                score = None
            else:
                ret = _number(series.iloc[index])
                score = _number(self.rotation_z[key].iloc[index])
            rows.append({"group_kind": kind, "group_id": name, "ret": ret, "z": score})
        return rows

    def _post_group_return(self, kind, name, index):
        if kind in {"index", "sector"} and name in self.post_close:
            return _number((self.post_close[name] / self.raw_close[name] - 1).iloc[index])
        if kind == "style":
            left, right = STYLES[name]
            if left not in self.post_close or right not in self.post_close:
                return None
            first = (self.post_close[left] / self.raw_close[left] - 1).iloc[index]
            second = (self.post_close[right] / self.raw_close[right] - 1).iloc[index]
            if not np.isfinite(first) or not np.isfinite(second):
                return None
            return float(first - second)
        if kind == "l3":
            return None
        return None

    def _macro_row(self, index):
        payload = {}
        for key, level in self.macro_level.items():
            current = _number(level.iloc[index])
            previous = _number(level.iloc[index - 1]) if index else None
            payload[key] = {
                "z": _number(self.macro_z[key].iloc[index]),
                "level": current,
                "prev": previous,
                "change": None if current is None or previous is None else current - previous,
            }
        return payload

    def _quality_bars(self, index, _session):
        bars = {}
        tickers = set(self.pool) | set(self.rotation_names())
        for ticker in tickers:
            if ticker not in self.raw_close:
                continue
            close_window = self.raw_close[ticker].iloc[max(0, index - 2) : index + 1]
            volume_window = self.volume[ticker].iloc[max(0, index - 20) : index + 1]
            closes = [float(value) for value in close_window if np.isfinite(value)]
            volumes = [float(value) for value in volume_window if np.isfinite(value)]
            adj_now = _number(self.adj[ticker].iloc[index]) if ticker in self.adj else None
            adj_prev = _number(self.adj[ticker].iloc[index - 1]) if index and ticker in self.adj else None
            source = None if ticker not in self.source else self.source[ticker].iloc[index]
            previous = None if index == 0 or ticker not in self.source else self.source[ticker].iloc[index - 1]
            bars[ticker] = {
                "raw_ret": _number(self.raw_returns[ticker].iloc[index]) if ticker in self.raw_returns else None,
                "adj_ret": _number(self.returns[ticker].iloc[index]) if ticker in self.returns else None,
                "adj_changed": adj_now is not None and adj_prev is not None and adj_now != adj_prev,
                "closes": closes,
                "volumes": volumes,
                "post_volume": None,
                "source_changed": previous not in (None, source) and source is not None,
            }
        return bars

    def rotation_names(self):
        return {name for kind, name in self.rotation if kind in {"index", "sector"}}

    def _calendar(self, day):
        return {
            "index_rebalance": False,
            "option_expiry": day.weekday() == 4 and 15 <= day.day <= 21,
            "index_rebalance_connected": False,
        }

    def _short_row(self, day):
        chosen = {}
        for ticker in self.pool:
            rows = [row for row in self.short_rows.get(ticker, []) if row["visible"] <= day]
            if ticker not in self.short_rows:
                chosen[ticker] = None
                continue
            if not rows:
                chosen[ticker] = None
                continue
            latest = max(rows, key=lambda row: row["visible"])
            chosen[ticker] = {
                "si_pct": latest["si_pct"],
                "days_to_cover": latest["days_to_cover"],
                "publish_date_inferred": latest["publish_date_inferred"],
            }
        return chosen
