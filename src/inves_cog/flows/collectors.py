"""Flows collectors — Cboe chains, OCC volume/OI, ETF shares. Parsers kept pure."""

import csv
import io
import json
import logging
import re
from datetime import datetime

from inves_cog.flows.store import record_health, save_raw, upsert_many

log = logging.getLogger(__name__)
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


# ---------- a. Cboe delayed option chains ----------

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"


def parse_cboe_chain(payload, underlying, max_days=60, today=None):
    """data.options[] → option_chain rows. Option sym e.g. SPY  251219C00500000."""
    data = (payload or {}).get("data") or {}
    stamp = data.get("timestamp") or data.get("current_time")
    snap = (
        datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if stamp else (datetime.combine(today, datetime.min.time()) if today else datetime.now())
    )
    rows = []
    pat = re.compile(r"([CP])(\d+\.?\d*)$")
    for opt in data.get("options") or []:
        sym = opt.get("option", "")
        m = re.search(r"(\d{6})([CP])([\d.]+)$", sym)
        if not m:
            continue
        ymd, cp, strike = m.group(1), m.group(2), m.group(3)
        try:
            expiry = datetime.strptime(ymd, "%y%m%d").date()
        except ValueError:
            continue
        if today and (expiry - today).days > max_days:
            continue
        if float(strike) > 10000:
            strike = float(strike) / 1000.0
        rows.append(
            {
                "underlying": underlying.lstrip("_"),
                "snapshot_at": snap,
                "expiry": expiry,
                "strike": float(strike),
                "cp": cp,
                "oi": opt.get("open_interest"),
                "volume": opt.get("volume"),
                "iv": opt.get("iv"),
                "delta": opt.get("delta"),
                "gamma": opt.get("gamma"),
                "bid": opt.get("bid"),
                "ask": opt.get("ask"),
                "source": "CBOE",
            }
        )
    return rows


def collect_cboe_chain(http, connection, symbol, raw_dir, max_days=60, today=None):
    url = CBOE_URL.format(sym=symbol)
    try:
        r = http.request("GET", url, headers=UA)
        payload = r if isinstance(r, dict) else json.loads(r)
        raw = r.encode() if isinstance(r, str) else json.dumps(r).encode()
        rows = parse_cboe_chain(payload, symbol, max_days, today)
        if connection is not None:
            save_raw(raw_dir, "cboe-chain", url, str(today), raw, connection)
            n = upsert_many(connection, "option_chain", list(rows[0].keys()) if rows else [], rows)
            record_health(connection, "Flows:CboeChain", "ok", f"{symbol} {n}")
        return {"symbol": symbol, "rows": len(rows)}
    except Exception as exc:
        if connection is not None:
            record_health(connection, "Flows:CboeChain", "failed", f"{symbol} {exc!r}")
        log.warning("cboe chain %s failed: %r", symbol, exc)
        return {"symbol": symbol, "rows": 0, "error": str(exc)}


# ---------- b. OCC daily volume ----------

OCC_VOL_URL = (
    "https://marketdata.theocc.com/volume-query?reportDate={ymd}"
    "&format=csv&volumeQueryType=O&symbolType=ALL&symbol="
    "&reportType=D&accountType=ALL&productKind=ALL&porc=BOTH"
)

_ACT = {"C": "C", "F": "F", "M": "M", "B": "F"}


def parse_occ_volume(text):
    """Aggregate OCC daily volume csv → (date, underlying, account_type, cp, quantity)."""
    out = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        q = row.get("quantity")
        und = (row.get("underlying") or "").strip()
        cp = (row.get("porc") or "").strip()[:1].upper()
        act = _ACT.get((row.get("actype") or "").strip().upper())
        day = (row.get("actdate") or "").strip()
        if not (q and und and cp and act and day):
            continue
        key = (day, und, act, cp)
        out[key] = out.get(key, 0) + int(float(q))
    return [{"date": k[0], "underlying": k[1], "account_type": k[2], "cp": k[3], "quantity": v} for k, v in out.items()]


def collect_occ_volume(http, connection, day, raw_dir):
    url = OCC_VOL_URL.format(ymd=day.strftime("%Y%m%d"))
    try:
        r = http.request("GET", url, headers=UA)
        text = r if isinstance(r, str) else r.decode("utf-8", "replace")
        raw = r.encode() if isinstance(r, str) else r
        rows = parse_occ_volume(text)
        if connection is not None:
            save_raw(raw_dir, "occ-volume", url, str(day), raw, connection)
            if rows:
                upsert_many(connection, "option_volume_occ", list(rows[0].keys()), rows)
        record_health(connection, "Flows:OCCVolume", "ok", f"{day} {len(rows)}") if connection is not None else None
        return {"date": str(day), "rows": len(rows)}
    except Exception as exc:
        if connection is not None:
            record_health(connection, "Flows:OCCVolume", "failed", f"{day} {exc!r}")
        log.warning("occ volume %s failed: %r", day, exc)
        return {"date": str(day), "rows": 0, "error": str(exc)}


# ---------- c. OCC OI summary + per-contract cross-check ----------

OCC_OI_URL = "https://marketdata.theocc.com/daily-open-interest?reportDate={mdy}&action=download&format=csv"
OCC_SERIES_URL = "https://marketdata.theocc.com/series-search?symbolType=U&symbol={sym}"


def parse_occ_oi_summary(text, obs_date, published_at):
    """OCC daily-open-interest csv → observations rows (equity/index/debt calls/puts)."""
    out = []
    labels = {1: "occ_oi_equity_calls", 2: "occ_oi_equity_puts",
              4: "occ_oi_index_calls", 5: "occ_oi_index_puts",
              7: "occ_oi_debt_calls", 8: "occ_oi_debt_puts",
              11: "occ_oi_total"}
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not cells or not re.match(r"\d{2}/\d{2}/\d{4}", cells[0]):
            continue
        obs = datetime.strptime(cells[0], "%m/%d/%Y").date()
        for idx, series in labels.items():
            if len(cells) > idx and cells[idx].replace(",", "").isdigit():
                out.append({"series_id": series, "obs_date": obs, "value": float(cells[idx].replace(",", "")),
                            "published_at": published_at, "vintage": "initial"})
    return out


def collect_occ_oi(http, connection, day, raw_dir, published_at=None):
    url = OCC_OI_URL.format(mdy=day.strftime("%m/%d/%Y"))
    try:
        r = http.request("GET", url, headers=UA)
        text = r if isinstance(r, str) else r.decode("utf-8", "replace")
        raw = r.encode() if isinstance(r, str) else r
        rows = parse_occ_oi_summary(text, day, published_at or day)
        if connection is not None:
            save_raw(raw_dir, "occ-oi", url, str(day), raw, connection)
            if rows:
                upsert_many(connection, "observations", list(rows[0].keys()), rows)
        return {"date": str(day), "rows": len(rows)}
    except Exception as exc:
        log.warning("occ oi %s failed: %r", day, exc)
        return {"date": str(day), "rows": 0, "error": str(exc)}


def parse_occ_series(text, underlying):
    """Per-contract OI cross-check tab text → option_chain rows with source='OCC'."""
    out = []
    for line in text.splitlines():
        parts = re.split(r"\t|,|\s{2,}", line.strip())
        if len(parts) < 2 or not parts[0]:
            continue
        m = re.search(r"(\d{6})([CP])([\d.]+)", line)
        if not m:
            continue
        nums = [p for p in parts if p.replace(",", "").isdigit()]
        if not nums:
            continue
        out.append(
            {
                "underlying": underlying,
                "snapshot_at": datetime.now(),
                "expiry": datetime.strptime(m.group(1), "%y%m%d").date(),
                "strike": float(m.group(3)),
                "cp": m.group(2),
                "oi": int(nums[-1].replace(",", "")),
                "source": "OCC",
            }
        )
    return out


# ---------- d. ETF shares ----------

DIREXION_URL = "https://www.direxion.com/holdings/{t}.csv"
PROSHARES_URL = "https://accounts.profunds.com/etfdata/ByFund/{t}-historical_nav.csv"
SSGA_URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t}.xlsx"

DIREXION_TICKERS = ["SOXL", "SOXS", "TECL", "TECS", "TSLL"]
PROSHARES_TICKERS = ["TQQQ", "SQQQ", "UPRO", "SPXU", "QLD", "SSO", "USD"]
SSGA_TICKERS = ["SPY"] + [f"XL{c}" for c in "BCEFIKLPUVY"]

_SH0 = re.compile(r"Shares Outstanding")


def parse_direxion(text, ticker, published_at):
    """Direxion holdings csv — header line 'Shares Outstanding:N'."""
    rows = []
    for line in text.splitlines():
        if _SH0.search(line):
            num = re.sub(r"[^\d]", "", line.split(":")[-1])
            if num:
                rows.append(
                    {
                        "ticker": ticker,
                        "date": published_at,
                        "shares": int(num),
                        "issuer": "Direxion",
                        "published_at": published_at,
                    }
                )
            break
    return rows


def parse_proshares(text, ticker, published_at):
    """ProShares historical_nav csv — 'Shares Outstanding (000)', AUM."""
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        sh = row.get("Shares Outstanding (000)") or row.get("Shares Outstanding")
        nav = row.get("NAV")
        day = row.get("Date") or row.get("Trade Date")
        aum = row.get("AUM") or row.get("Total Net Assets")
        if not (day and sh):
            continue
        try:
            shares = int(float(sh.replace(",", ""))) * (1000 if "(000)" in str(row.keys()) else 1)
        except (ValueError, AttributeError):
            continue
        rows.append(
            {
                "ticker": ticker,
                "date": day,
                "nav": float(nav) if nav else None,
                "shares": shares,
                "aum": float(aum.replace(",", "")) if aum else None,
                "issuer": "ProShares",
                "published_at": published_at,
            }
        )
    return rows[-3:] if len(rows) > 3 else rows


def collect_etf_shares(http, connection, raw_dir, published_at=None, tickers=None):
    pub = published_at or datetime.now()
    out = {}
    for t in tickers or (DIREXION_TICKERS + PROSHARES_TICKERS):
        url = DIREXION_URL.format(t=t) if t in DIREXION_TICKERS else PROSHARES_URL.format(t=t)
        try:
            r = http.request("GET", url, headers=UA)
            text = r if isinstance(r, str) else r.decode("utf-8", "replace")
            raw = r.encode() if isinstance(r, str) else r
            rows = parse_direxion(text, t, pub) if t in DIREXION_TICKERS else parse_proshares(text, t, pub)
            if connection is not None and rows:
                save_raw(raw_dir, f"etf-{t.lower()}", url, str(pub.date()), raw, connection)
                upsert_many(connection, "etf_daily", list(rows[0].keys()), rows)
            out[t] = len(rows)
        except Exception as exc:
            log.warning("etf %s failed: %r", t, exc)
            out[t] = 0
    return out
