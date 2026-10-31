"""Phase-2 D2 — one-off historical backfill. Idempotent; reuses D1 parsers/tables.
Every job writes/prints a coverage report: source, first/last date, rows, gaps."""

import csv
import io
import json
import logging
import re
import time
from datetime import date, datetime, timedelta

from inves_cog.flows.collectors import (
    OCC_VOL_URL,
    PROSHARES_TICKERS,
    SSGA_TICKERS,
    _mdy,
    parse_cboe_pc,
    parse_occ_volume,
)
from inves_cog.flows.store import UA, save_raw, upsert_many
from inves_cog.ingest.market import NY, trading_day

log = logging.getLogger(__name__)

# PIT rules: published_at = estimated ORIGINAL release time (America/New_York);
# ingested_at = run time (column default); vintage='backfill' everywhere.
_HM = "%H:%M"


def _biz_next(d):
    while not trading_day(d):
        d += timedelta(days=1)
    return d


def _at(d, hms):
    return datetime.combine(d, datetime.strptime(hms, _HM).time(), tzinfo=NY)


def published_at(source, obs_date):
    """Estimated original release time per source (documented in the review)."""
    if source in ("proshares", "ssga"):
        return _at(obs_date, "21:00")
    if source == "cboe_pc":
        return _at(obs_date, "19:00")
    if source == "cboe_idx":
        return _at(obs_date, "17:00")
    if source in ("occ_volume", "occ_oi"):
        return _at(_biz_next(obs_date + timedelta(days=1)), "07:00")
    if source == "finra_margin":
        return _at(obs_date + timedelta(days=21), "17:00")  # note: estimated
    if source == "ofr_fsi":
        return _at(_biz_next(obs_date + timedelta(days=1)), "09:00")
    return _at(obs_date, "17:00")


def published_at_fred(series, obs_date):
    """FRED release rules per series (documented in the review)."""
    sid = series.lower()
    if sid in ("walcl", "wtregen"):  # Wednesday → Thursday 16:30
        return _at(_biz_next(obs_date + timedelta(days=1)), "16:30")
    if sid == "rrpontsyd":
        return _at(obs_date, "17:00")
    if sid == "sofr":
        return _at(_biz_next(obs_date + timedelta(days=1)), "08:00")
    if sid in ("iorb", "ioer"):
        return _at(obs_date, "00:00")
    if sid == "stiflsi4" or sid == "stlfsi4":  # Friday → following Thursday 10:00
        return _at(obs_date + timedelta(days=6), "10:00")
    if sid == "wrmfns":  # Monday → Thursday 16:30
        return _at(obs_date + timedelta(days=3), "16:30")
    return _at(_biz_next(obs_date + timedelta(days=1)), "08:00")


FRED_FREQ = {
    "WALCL": "weekly",
    "WTREGEN": "daily",
    "RRPONTSYD": "daily",
    "SOFR": "daily",
    "IORB": "daily",
    "IOER": "daily",
    "STLFSI4": "weekly",
    "WRMFNS": "weekly",
}


def _report(source, rows_by_date, total=None):
    days = sorted(rows_by_date)
    gaps = [
        d.isoformat()
        for a, b in zip(days, days[1:], strict=False)
        for d in [a + timedelta(days=x) for x in range(1, (b - a).days)]
        if trading_day(d)
    ]
    if total is not None:
        rows_total = total
    elif isinstance(rows_by_date, dict) and all(isinstance(v, int) for v in rows_by_date.values()):
        rows_total = sum(rows_by_date.values())
    else:
        rows_total = len(rows_by_date)
    return {
        "source": source,
        "first": str(days[0]) if days else None,
        "last": str(days[-1]) if days else None,
        "dates": len(days),
        "rows": rows_total,
        "gap_days": gaps[:50],
        "gap_count": len(gaps),
    }


def _fetch(http, url):
    r = http.request("GET", url, headers=UA)
    return r


# ---------- ProShares full history (all levered funds incl SDS, QID) ----------

PSHF_TICKERS = PROSHARES_TICKERS + ["SDS", "QID"]
PSHF_URL = "https://accounts.profunds.com/etfdata/ByFund/{t}-historical_nav.csv"


def backfill_proshares(http, connection, raw_dir, today, _now=None):
    out = {}
    for t in PSHF_TICKERS:
        url = PSHF_URL.format(t=t)
        try:
            text = _fetch(http, url)
            reader = csv.DictReader(io.StringIO(text))
            header = reader.fieldnames or []
            mult = 1000 if any("(000)" in h for h in header) else 1
            rows = []
            for row in reader:
                sh = row.get("Shares Outstanding (000)") or row.get("Shares Outstanding")
                day = _mdy(row.get("Date") or row.get("Trade Date"))
                if not (day and sh):
                    continue
                rows.append(
                    {
                        "ticker": t,
                        "date": day,
                        "nav": float(row["NAV"]) if row.get("NAV") not in (None, "-", "") else None,
                        "shares": int(float(sh.replace(",", ""))) * mult,
                        "aum": float(row["AUM"].replace(",", "")) if row.get("AUM") not in (None, "-", "") else None,
                        "issuer": "ProShares",
                        "published_at": published_at,
                    }
                )
            save_raw(raw_dir, f"etf-{t.lower()}", url, str(today), text.encode(), connection)
            if rows:
                upsert_many(connection, "etf_daily", list(rows[0].keys()), rows, "update")
            out[t] = {r["date"] for r in rows}
        except Exception as exc:
            log.warning("proshares %s failed: %r", t, exc)
            out[t] = set()
    return [_report(f"ProShares:{t}", days) for t, days in out.items()]


# ---------- SSGA full history (12 funds, one xlsx each) ----------

SSGA_URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t}.xlsx"


def backfill_ssga(http, connection, raw_dir, today, _now=None):
    out = {}
    for t in SSGA_TICKERS:
        url = SSGA_URL.format(t=t.lower())
        try:
            import urllib.request

            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=60).read()
            from inves_cog.flows.collectors import _xlsx_date, _xlsx_rows

            rows = []
            for cells in _xlsx_rows(data):
                if not cells or cells[0] in ("Date", "", None):
                    continue
                day = _xlsx_date(cells[0])
                if day and len(cells) >= 3:
                    rows.append(
                        {
                            "ticker": t,
                            "date": day,
                            "nav": float(cells[1]) if cells[1] not in ("-", "") else None,
                            "shares": int(float(cells[2].replace(",", ""))) if cells[2] not in ("-", "") else None,
                            "aum": float(cells[3].replace(",", ""))
                            if len(cells) > 3 and cells[3] not in ("-", "")
                            else None,
                            "issuer": "SSGA",
                            "published_at": published_at,
                        }
                    )
            save_raw(raw_dir, f"etf-{t.lower()}", url, str(today), data, connection)
            if rows:
                upsert_many(connection, "etf_daily", list(rows[0].keys()), rows, "update")
            out[t] = {r["date"] for r in rows}
        except Exception as exc:
            log.warning("ssga %s failed: %r", t, exc)
            out[t] = set()
    return [_report(f"SSGA:{t}", days) for t, days in out.items()]


# ---------- Cboe put/call history: archive CSV 2006–2019-10 + daily JSON ----------

CBOE_PC_ARCHIVE = "https://cdn.cboe.com/data/us/options/market_statistics/daily/2019-10-07_daily_options"
CBOE_PC_DAILY = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{day}_daily_options"
CBOE_PC_CSV = {"equity": "equitypc", "total": "totalpc", "index": "indexpc"}
CBOE_PC_CSV_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/{name}.csv"


def parse_cboe_pc_csv(text, kind):
    """Archive csv: 2 preamble lines, header DATE,CALL(S),PUT(S),TOTAL,P/C Ratio."""
    out = []
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not cells or not re.match(r"\d{1,2}/\d{1,2}/\d{4}", cells[0]):
            continue
        obs = _mdy(cells[0])
        if not obs:
            continue
        val = cells[4] if len(cells) > 4 else None
        if val:
                try:
                    out.append(
                        {"series_id": f"cboe_pc_{kind}", "obs_date": obs, "value": float(val), "vintage": "backfill"}
                    )
                except ValueError:
                    pass
    return out


def backfill_cboe_pc_csv(http, connection, raw_dir, published_at_fn):
    """Archive CSVs 2006–2019-10 → same series ids as the daily JSON."""
    out = {}
    for kind, name in CBOE_PC_CSV.items():
        url = CBOE_PC_CSV_URL.format(name=name)
        try:
            text = _fetch(http, url)
            rows = parse_cboe_pc_csv(text, kind)
            if connection is not None and rows:
                save_raw(raw_dir, f"cboe-pc-{name}", url, str(date.today()), text.encode(), connection)
                catalog = [
                    {
                        "series_id": f"cboe_pc_{kind}",
                        "name_zh": f"cboe pc {kind}",
                        "unit": "ratio",
                        "frequency": "daily",
                        "source": "Cboe",
                    }
                ]
                upsert_many(
                    connection, "series_catalog", ["series_id", "name_zh", "unit", "frequency", "source"], catalog
                )
                for x in rows:
                    x["published_at"] = published_at_fn("cboe_pc", x["obs_date"])
                upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
            out[kind] = {r["obs_date"]: 1 for r in rows}
        except Exception as exc:
            log.warning("cboe pc %s failed: %r", name, exc)
            out[kind] = set()
    return [_report(f"CboePC:{t}", days) for t, days in out.items()]


def backfill_cboe_pc(http, connection, raw_dir, start, end, _now, pace=0.25):
    """Daily JSON 2019-10-07 → end (archive CSVs for 2006–2019 have a different
    layout and are noted in the report until that parser lands)."""
    days = {}
    d = max(start, date(2019, 10, 7))
    while d <= end:
        if trading_day(d):
            url = CBOE_PC_DAILY.format(day=d)
            try:
                r = _fetch(http, url)
                payload = r if isinstance(r, dict) else json.loads(r)
                rows = parse_cboe_pc(payload, d, published_at("cboe_pc", d))
                if connection is not None and rows:
                    raw = save_raw(
                        raw_dir,
                        "cboe-pc",
                        url,
                        str(d),
                        (r.encode() if isinstance(r, str) else json.dumps(r).encode()),
                        connection,
                    )
                    catalog = [
                        {
                            "series_id": x["series_id"],
                            "name_zh": x["series_id"],
                            "unit": "ratio",
                            "frequency": "daily",
                            "source": "Cboe",
                        }
                        for x in rows
                    ]
                    upsert_many(
                        connection, "series_catalog", ["series_id", "name_zh", "unit", "frequency", "source"], catalog
                    )
                    for x in rows:
                        x["raw_file_id"] = raw["raw_file_id"]
                    upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
                days[d] = len(rows)
            except Exception as exc:
                log.warning("cboe pc %s failed: %r", d, exc)
            time.sleep(pace)
        d += timedelta(days=1)
    return _report("CboePC:daily", days, sum(days.values()))


# ---------- Cboe index history (VIX9D, VVIX, SKEW) ----------

CBOE_IDX = {"VIX9D": "vix9d", "VVIX": "vvix", "SKEW": "skew"}
CBOE_IDX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"


def backfill_cboe_index(http, connection, raw_dir, today, _now=None):
    out = {}
    for sym in CBOE_IDX:
        url = CBOE_IDX_URL.format(sym=sym)
        try:
            text = _fetch(http, url)
            rows = []
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                day = _mdy(row.get("DATE") or row.get("date"))
                val = row.get("CLOSE") or row.get("close") or row.get(sym) or row.get(sym.upper())
                if day and val:
                    rows.append(
                        {
                            "series_id": f"cboe_idx_{sym.lower()}",
                            "obs_date": day,
                            "value": float(val),
                            "published_at": published_at,
                            "vintage": "backfill",
                        }
                    )
            if connection is not None and rows:
                save_raw(raw_dir, f"cboe-idx-{sym.lower()}", url, str(today), text.encode(), connection)
                upsert_many(
                    connection,
                    "series_catalog",
                    ["series_id", "name_zh", "unit", "frequency", "source"],
                    [
                        {
                            "series_id": f"cboe_idx_{sym.lower()}",
                            "name_zh": sym,
                            "unit": "index",
                            "frequency": "daily",
                            "source": "Cboe",
                        }
                    ],
                )
                upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
            out[sym] = {r["obs_date"] for r in rows}
        except Exception as exc:
            log.warning("cboe idx %s failed: %r", sym, exc)
            out[sym] = set()
    return [_report(f"CboeIdx:{t}", days) for t, days in out.items()]


# ---------- OCC volume backfill (last 2 years, rate-limited) ----------


def backfill_occ(http, connection, raw_dir, start, end, _now, pace=0.5):
    days = {}
    d = start
    while d <= end:
        if trading_day(d):
            url = OCC_VOL_URL.format(ymd=d.strftime("%Y%m%d"))
            try:
                text = _fetch(http, url)
                rows, _skipped = parse_occ_volume(text)
                if connection is not None and rows:
                    save_raw(raw_dir, "occ-volume", url, str(d), text.encode(), connection)
                    upsert_many(connection, "option_volume_occ", list(rows[0].keys()), rows)
                days[d] = len(rows)
            except Exception as exc:
                log.warning("occ vol %s failed: %r", d, exc)
            time.sleep(pace)
        d += timedelta(days=1)
    return _report("OCC:volume", days, sum(days.values()))


# ---------- CFTC TFF via Socrata ----------

CFTC_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
CFTC_MARKETS = [
    "NASDAQ-100 Consolidated",
    "S&P 500 Consolidated",
    "E-MINI S&P 500",
    "NASDAQ MINI",
    "VIX FUTURES",
    "JAPANESE YEN",
    "UST 10Y NOTE",
    "UST 2Y NOTE",
]
_TFF_CLASSES = {
    "lev_money": ("lev_money_positions_long", "lev_money_positions_short", "lev_money_positions_spread"),
    "asset_mgr": ("asset_mgr_positions_long", "asset_mgr_positions_short", "asset_mgr_positions_spread"),
    "dealer": ("dealer_positions_long_all", "dealer_positions_short_all", "dealer_positions_spread_all"),
    "other_rept": ("other_rept_positions_long", "other_rept_positions_short", "other_rept_positions_spread"),
}


def _cftc_names(http, market):
    """Distinct full market_and_exchange_names matching the short name."""
    params = {
        "$select": "market_and_exchange_names",
        "$limit": 500,
        "$where": f"market_and_exchange_names like '{market}%'",
    }
    try:
        r = http.request("GET", CFTC_URL, params=params, headers=UA)
        return list({x["market_and_exchange_names"] for x in (r if isinstance(r, list) else [])})
    except Exception:
        return []


def backfill_cftc(http, connection, raw_dir, start, end, _now=None):
    rows = []
    for short in CFTC_MARKETS:
        names = _cftc_names(http, short) or [short + " - CHICAGO MERCANTILE EXCHANGE"]
        for name in names:
            offset = 0
            while True:
                params = {
                    "market_and_exchange_names": name,
                    "$limit": 2000,
                    "$offset": offset,
                    "$order": "report_date_as_yyyy_mm_dd",
                    "$where": f"report_date_as_yyyy_mm_dd between '{start}' and '{end}'",
                }
                try:
                    r = http.request("GET", CFTC_URL, params=params, headers=UA)
                    recs = r if isinstance(r, list) else []
                except Exception as exc:
                    log.warning("cftc %s failed: %r", name, exc)
                    break
                if not recs:
                    break
                for rec in recs:
                    report = _mdy(str(rec.get("report_date_as_yyyy_mm_dd", ""))[:10])
                    if not report:
                        continue
                    release = _at(_biz_next(report + timedelta(days=3)), "15:30")
                    oi = rec.get("open_interest_all")
                    for cls, (lk, sk, spk) in _TFF_CLASSES.items():
                        rows.append(
                            {
                                "report_date": report,
                                "release_at": release,
                                "market": name,
                                "trader_class": cls,
                                "long": int(rec.get(lk) or 0),
                                "short": int(rec.get(sk) or 0),
                                "spread": int(rec.get(spk) or 0),
                                "open_interest": int(oi) if oi is not None else None,
                            }
                        )
                offset += len(recs)
                if len(recs) < 2000:
                    break
    if connection is not None and rows:
        upsert_many(connection, "cftc_positions", list(rows[0].keys()), rows)
    return _report("CFTC:TFF", {r["report_date"] for r in rows}, len(rows))


# ---------- FINRA margin statistics xlsx ----------

FINRA_MARGIN_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"


def backfill_finra_margin(http, connection, raw_dir, published_at):
    try:
        import urllib.request

        req = urllib.request.Request(FINRA_MARGIN_URL, headers=UA)
        data = urllib.request.urlopen(req, timeout=60).read()
        from inves_cog.flows.collectors import _xlsx_date, _xlsx_rows

        rows = []
        for cells in _xlsx_rows(data):
            if len(cells) < 4 or not cells[0]:
                continue
            m = _xlsx_date(cells[0])
            if m:
                for name, idx in (("margin_debit", 1), ("cash_accounts", 2), ("margin_free_credit", 3)):
                    try:
                        val = float(str(cells[idx]).replace(",", ""))
                    except (ValueError, IndexError):
                        continue
                    pub = m.replace(day=28) + timedelta(days=22)
                    rows.append(
                        {
                            "series_id": f"finra_margin_{name}",
                            "obs_date": m,
                            "value": val,
                            "published_at": pub,
                            "vintage": "backfill",
                        }
                    )
        if connection is not None and rows:
            save_raw(raw_dir, "finra-margin", FINRA_MARGIN_URL, str(date.today()), data, connection)
            upsert_many(
                connection,
                "series_catalog",
                ["series_id", "name_zh", "unit", "frequency", "source"],
                [
                    {
                        "series_id": f"finra_margin_{n}",
                        "name_zh": n,
                        "unit": "usd",
                        "frequency": "monthly",
                        "source": "FINRA",
                    }
                    for n in ("margin_debit", "cash_accounts", "margin_free_credit")
                ],
            )
            upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
        return _report("FINRA:margin", {r["obs_date"] for r in rows})
    except Exception as exc:
        log.warning("finra margin failed: %r", exc)
        return _report("FINRA:margin", set())


# ---------- FRED series ----------

FRED_SERIES = ["WALCL", "WTREGEN", "RRPONTSYD", "SOFR", "IORB", "IOER", "STLFSI4", "WRMFNS"]
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
FRED_API = "https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json"


def _fred_rows(text, sid, pub_fn):
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        day = _mdy(row.get("observation_date") or row.get("DATE"))
        val = row.get(sid)
        if day and val not in (None, ".", ""):
            rows.append(
                {
                    "series_id": f"fred_{sid.lower()}",
                    "obs_date": day,
                    "value": float(val),
                    "published_at": pub_fn(sid, day),
                    "vintage": "backfill",
                }
            )
    return rows


def backfill_fred(http, connection, raw_dir, _now=None):
    out = {}
    for sid in FRED_SERIES:
        url = FRED_URL.format(sid=sid)
        try:
            text = _fetch(http, url)
            rows = []
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                day = _mdy(row.get("observation_date") or row.get("DATE"))
                val = row.get(sid)
                if day and val not in (None, ".", ""):
                    rows.append(
                        {
                            "series_id": f"fred_{sid.lower()}",
                            "obs_date": day,
                            "value": float(val),
                            "published_at": published_at,
                            "vintage": "backfill",
                        }
                    )
            if connection is not None and rows:
                save_raw(raw_dir, f"fred-{sid.lower()}", url, str(date.today()), text.encode(), connection)
                upsert_many(
                    connection,
                    "series_catalog",
                    ["series_id", "name_zh", "unit", "frequency", "source"],
                    [
                        {
                            "series_id": f"fred_{sid.lower()}",
                            "name_zh": sid,
                            "unit": "usd|pct",
                            "frequency": "daily",
                            "source": "FRED",
                        }
                    ],
                )
                upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
            out[sid] = {r["obs_date"] for r in rows}
            time.sleep(0.3)
        except Exception as exc:
            log.warning("fred %s failed: %r", sid, exc)
            out[sid] = set()
    return [_report(f"FRED:{t}", days) for t, days in out.items()]


# ---------- OFR FSI ----------

OFR_FSI_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"


def backfill_ofr(http, connection, raw_dir, _now=None):
    try:
        text = _fetch(http, OFR_FSI_URL)
        rows = []
        for row in csv.DictReader(io.StringIO(text)):
            day = _mdy(row.get("date") or row.get("Date"))
            val = row.get("OFR FSI") or row.get("fsi")
            if day and val:
                rows.append(
                    {
                        "series_id": "ofr_fsi",
                        "obs_date": day,
                        "value": float(val),
                        "published_at": published_at,
                        "vintage": "backfill",
                    }
                )
        if connection is not None and rows:
            save_raw(raw_dir, "ofr-fsi", OFR_FSI_URL, str(date.today()), text.encode(), connection)
            upsert_many(
                connection,
                "series_catalog",
                ["series_id", "name_zh", "unit", "frequency", "source"],
                [
                    {
                        "series_id": "ofr_fsi",
                        "name_zh": "OFR FSI",
                        "unit": "index",
                        "frequency": "daily",
                        "source": "OFR",
                    }
                ],
            )
            upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
        return _report("OFR:FSI", {r["obs_date"] for r in rows})
    except Exception as exc:
        log.warning("ofr fsi failed: %r", exc)
        return _report("OFR:FSI", set())
