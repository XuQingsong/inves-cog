"""Flows collectors — Cboe chains, OCC volume/OI, ETF shares. Parsers kept pure."""

import csv
import io
import json
import logging
import re
import time
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

from inves_cog.flows.store import UA, record_health, save_raw, upsert_many
from inves_cog.ingest.market import NY

log = logging.getLogger(__name__)
INDEX_SYMS = ["_SPX", "SPY", "QQQ", "IWM", "SMH"]
CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"


def parse_cboe_chain(payload, underlying, max_days=60, today=None, asof=None):
    """data.options[] → option_chain rows. Strikes are 8-digit OSI ÷1000.
    max_days=None keeps the full chain (EOD)."""
    data = (payload or {}).get("data") or {}
    stamp = payload.get("timestamp") or data.get("timestamp") or data.get("current_time")
    snap = asof
    if stamp:
        try:
            snap = datetime.strptime(str(stamp), "%Y-%m-%d %H:%M:%S").replace(tzinfo=NY)
        except ValueError:
            try:
                snap = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            except ValueError:
                pass
    if snap is None:
        if today is None:
            raise ValueError("no chain timestamp and no asof/today injected")
        snap = datetime.combine(today, datetime.min.time(), tzinfo=NY)
    if snap.tzinfo is None:
        snap = snap.replace(tzinfo=NY)
    rows = []
    und = underlying.lstrip("_")
    for opt in data.get("options") or []:
        sym = opt.get("option", "")
        m = re.search(r"(\d{6})([CP])([\d.]+)$", sym)
        if not m:
            continue
        try:
            expiry = datetime.strptime(m.group(1), "%y%m%d").date()
        except ValueError:
            continue
        if max_days is not None and today and (expiry - today).days > max_days:
            continue
        rows.append(
            {
                "underlying": und,
                "snapshot_at": snap,
                "expiry": expiry,
                "strike": float(m.group(3)) / 1000.0,
                "cp": m.group(2),
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


def collect_cboe_chain(http, connection, symbol, raw_dir, max_days=60, today=None, asof=None):
    url = CBOE_URL.format(sym=symbol)
    t0 = time.monotonic()
    try:
        r = http.request("GET", url, headers=UA)
        payload = r if isinstance(r, dict) else json.loads(r)
        raw = r.encode() if isinstance(r, str) else json.dumps(r).encode()
        rows = parse_cboe_chain(payload, symbol, max_days, today, asof)
        lat = time.monotonic() - t0
        if connection is not None:
            save_raw(raw_dir, "cboe-chain", url, str(today), raw, connection)
            if rows:
                upsert_many(connection, "option_chain", list(rows[0].keys()), rows)
            record_health(connection, "Flows:CboeChain", True, len(rows), f"{symbol}", lat, asof)
        return {"symbol": symbol, "rows": len(rows)}
    except Exception as exc:
        if connection is not None:
            record_health(connection, "Flows:CboeChain", False, 0, f"{symbol} {exc!r}")
        log.warning("cboe chain %s failed: %r", symbol, exc)
        return {"symbol": symbol, "rows": 0, "error": str(exc)}


OCC_VOL_URL = (
    "https://marketdata.theocc.com/volume-query?reportDate={ymd}"
    "&format=csv&volumeQueryType=O&symbolType=ALL&symbol="
    "&reportType=D&accountType=ALL&productKind=ALL&porc=BOTH"
)
OCC_OI_URL = "https://marketdata.theocc.com/daily-open-interest?reportDate={mdy}&action=download&format=csv"
OCC_SERIES_URL = "https://marketdata.theocc.com/series-search?symbolType=U&symbol={sym}"
_ACT = {"C": "C", "F": "F", "M": "M"}


def _mdy(v):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_occ_volume(text):
    out = {}
    skipped = 0
    for row in csv.DictReader(io.StringIO(text)):
        q, und = row.get("quantity"), (row.get("underlying") or "").strip()
        cp = (row.get("porc") or "").strip()[:1].upper()
        act = _ACT.get((row.get("actype") or "").strip().upper())
        day = _mdy(row.get("actdate"))
        if not (q and und and cp and act and day):
            skipped += 1
            continue
        key = (day, und, act, cp)
        out[key] = out.get(key, 0) + int(float(q))
    rows = [{"date": k[0], "underlying": k[1], "account_type": k[2], "cp": k[3], "quantity": v} for k, v in out.items()]
    return rows, skipped


def parse_occ_oi_summary(text, published_at):
    """Date,Equity C/P/T,Index C/P/T,Debt C/P/T,Futures T,OCC T → observations."""
    out = []
    labels = {
        1: "occ_oi_equity_calls",
        2: "occ_oi_equity_puts",
        4: "occ_oi_index_calls",
        5: "occ_oi_index_puts",
        7: "occ_oi_debt_calls",
        8: "occ_oi_debt_puts",
        11: "occ_oi_total",
    }
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not cells or not re.match(r"\d{2}/\d{2}/\d{4}", cells[0]):
            continue
        obs = datetime.strptime(cells[0], "%m/%d/%Y").date()
        for idx, series in labels.items():
            if len(cells) > idx and cells[idx].replace(",", "").isdigit():
                out.append(
                    {
                        "series_id": series,
                        "obs_date": obs,
                        "value": float(cells[idx].replace(",", "")),
                        "published_at": published_at,
                        "vintage": "initial",
                    }
                )
    return out


def parse_occ_series(text, underlying, published_at):
    """OCC series-search tab text → option_chain rows (source='OCC', 2 per line).
    Columns: root, year, month, day, strike_int, strike_dec, 'C P', call_oi, put_oi, pos_limit."""
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("\t")]
        parts = [p for p in parts if p]
        if len(parts) < 9 or not parts[1].isdigit() or parts[1] > "9999":
            continue
        try:
            expiry = date(int(parts[1]), int(parts[2]), int(parts[3]))
            strike = float(parts[4]) + float(parts[5]) / 1000.0
        except (ValueError, IndexError):
            continue
        for cp, oi in (("C", parts[7] if len(parts) > 7 else None), ("P", parts[8] if len(parts) > 8 else None)):
            out.append(
                {
                    "underlying": underlying,
                    "snapshot_at": published_at,
                    "expiry": expiry,
                    "strike": strike,
                    "cp": cp,
                    "oi": int(oi.replace(",", "")) if oi and oi.replace(",", "").isdigit() else None,
                    "source": "OCC",
                }
            )
    return out


def collect_occ(http, connection, day, raw_dir, kind="volume", published_at=None, raw_id_link=None):
    url = (
        OCC_VOL_URL.format(ymd=day.strftime("%Y%m%d"))
        if kind == "volume"
        else OCC_OI_URL.format(mdy=day.strftime("%m/%d/%Y"))
    )
    t0 = time.monotonic()
    try:
        r = http.request("GET", url, headers=UA)
        text = r if isinstance(r, str) else r.decode("utf-8", "replace")
        pub = published_at
        src = "Flows:OCCVolume" if kind == "volume" else "Flows:OCCOpenInterest"
        raw = (
            save_raw(raw_dir, f"occ-{kind}", url, str(day), r.encode() if isinstance(r, str) else r, connection)
            if connection is not None
            else {"raw_file_id": None}
        )
        skipped = 0
        if kind == "volume":
            rows, skipped = parse_occ_volume(text)
            if connection is not None and rows:
                upsert_many(connection, "option_volume_occ", list(rows[0].keys()), rows)
        else:
            rows = parse_occ_oi_summary(text, pub)
            if connection is not None and rows:
                catalog = [
                    {
                        "series_id": r["series_id"],
                        "name_zh": r["series_id"],
                        "unit": "contracts",
                        "frequency": "daily",
                        "source": "OCC",
                    }
                    for r in rows
                ]
                upsert_many(
                    connection, "series_catalog", ["series_id", "name_zh", "unit", "frequency", "source"], catalog
                )
                for row in rows:
                    row["raw_file_id"] = raw["raw_file_id"]
                upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
        lat = time.monotonic() - t0
        if connection is not None:
            note = str(day) + (f" skipped:{skipped}" if kind == "volume" and skipped else "")
            record_health(connection, src, True, pub, len(rows), note, lat)
        return {"date": str(day), "rows": len(rows)}
    except Exception as exc:
        src = "Flows:OCCVolume" if kind == "volume" else "Flows:OCCOpenInterest"
        if connection is not None:
            record_health(connection, src, False, pub, 0, f"{day} {exc!r}")
        log.warning("occ %s %s failed: %r", kind, day, exc)
        return {"date": str(day), "rows": 0, "error": str(exc)}


def collect_occ_series(http, connection, symbol, raw_dir, published_at=None):
    url = OCC_SERIES_URL.format(sym=symbol)
    try:
        r = http.request("GET", url, headers=UA)
        text = r if isinstance(r, str) else r.decode("utf-8", "replace")
        rows = parse_occ_series(text, symbol, published_at)
        if connection is not None and rows:
            upsert_many(connection, "option_chain", list(rows[0].keys()), rows)
        return {"symbol": symbol, "rows": len(rows)}
    except Exception as exc:
        log.warning("occ series %s failed: %r", symbol, exc)
        return {"symbol": symbol, "rows": 0, "error": str(exc)}


# ---------- ETF shares ----------

DIREXION_URL = "https://www.direxion.com/holdings/{t}.csv"
PROSHARES_URL = "https://accounts.profunds.com/etfdata/ByFund/{t}-historical_nav.csv"
SSGA_URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t}.xlsx"
DIREXION_TICKERS = ["SOXL", "SOXS", "TECL", "TECS", "TSLL"]
PROSHARES_TICKERS = ["TQQQ", "SQQQ", "UPRO", "SPXU", "QLD", "SSO", "USD"]
SSGA_TICKERS = ["SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def parse_direxion(text, ticker, published_at):
    rows = []
    reader = csv.DictReader(
        io.StringIO("\n".join(x for x in text.splitlines() if not x.startswith("Shares Outstanding"))),
        skipinitialspace=True,
    )
    for row in reader:
        day = _mdy(row.get("TradeDate") or row.get("Trade Date") or row.get("Date"))
        if day:
            break
    for line in text.splitlines():
        if "Shares Outstanding" in line:
            num = re.sub(r"[^\d]", "", line.split(":")[-1])
            if num:
                rows.append(
                    {
                        "ticker": ticker,
                        "date": day or published_at.date(),
                        "shares": int(num),
                        "issuer": "Direxion",
                        "published_at": published_at,
                    }
                )
            break
    return rows


def parse_proshares(text, ticker, published_at):
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    mult = 1000 if any("(000)" in h for h in header) else 1
    for row in reader:
        sh = row.get("Shares Outstanding (000)") or row.get("Shares Outstanding")
        day = _mdy(row.get("Date") or row.get("Trade Date"))
        if not (day and sh):
            continue
        rows.append(
            {
                "ticker": ticker,
                "date": day,
                "nav": float(row["NAV"]) if row.get("NAV") and row["NAV"] != "-" else None,
                "shares": int(float(sh.replace(",", ""))) * mult,
                "aum": float(row["AUM"].replace(",", "")) if row.get("AUM") and row["AUM"] != "-" else None,
                "issuer": "ProShares",
                "published_at": published_at,
            }
        )
    return sorted(rows, key=lambda r: r["date"])


def _xlsx_rows(data):
    """Shared-strings + first-sheet rows → list of lists."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append(
                    "".join(
                        t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )
        sheet = z.read(z.namelist()[z.namelist().index([n for n in z.namelist() if "sheet" in n][0])])
    out = []
    for row in ET.fromstring(sheet).iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
        cells = []
        for c in row.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
            v = c.find("m:v", ns)
            val = v.text if v is not None else ""
            if c.get("t") == "s" and val.isdigit():
                val = shared[int(val)]
            cells.append(val)
        out.append(cells)
    return out


def _xlsx_date(v):
    """Excel serial (1899-12-30 base) or text → date."""
    try:
        return date(1899, 12, 30) + __import__("datetime").timedelta(days=int(float(v)))
    except (ValueError, TypeError):
        return _mdy(v)


def parse_ssga_xlsx(data, ticker, published_at):
    rows = []
    for cells in _xlsx_rows(data):
        if not cells or cells[0] in ("Date", "", None) or cells[0].startswith("NAV"):
            continue
        day = _xlsx_date(cells[0])
        if day and len(cells) >= 3:
            rows.append(
                {
                    "ticker": ticker,
                    "date": day,
                    "nav": float(cells[1]) if cells[1] not in ("-", "") else None,
                    "shares": int(float(cells[2].replace(",", ""))) if cells[2] not in ("-", "") else None,
                    "aum": float(cells[3].replace(",", "")) if len(cells) > 3 and cells[3] not in ("-", "") else None,
                    "issuer": "SSGA",
                    "published_at": published_at,
                }
            )
    return rows[-3:]


def collect_etf_shares(http, connection, raw_dir, published_at=None, tickers=None, today=None):
    pub = published_at
    out = {}
    latest_dates = {}
    for t in tickers or (DIREXION_TICKERS + PROSHARES_TICKERS + SSGA_TICKERS):
        if t in DIREXION_TICKERS:
            url, parse = DIREXION_URL.format(t=t), "direxion"
        elif t in PROSHARES_TICKERS:
            url, parse = PROSHARES_URL.format(t=t), "proshares"
        else:
            url, parse = SSGA_URL.format(t=t.lower()), "ssga"
        try:
            if parse == "ssga":
                import urllib.request

                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                r = body
            else:
                r = http.request("GET", url, headers=UA)
                body = r.encode() if isinstance(r, str) else r
            rows = (
                parse_direxion(r if isinstance(r, str) else r.decode("utf-8", "replace"), t, pub)
                if parse == "direxion"
                else parse_proshares(r if isinstance(r, str) else r.decode("utf-8", "replace"), t, pub)
                if parse == "proshares"
                else parse_ssga_xlsx(body, t, pub)
            )
            rows = sorted(rows, key=lambda r: r["date"])[-3:]
            if connection is not None:
                save_raw(raw_dir, f"etf-{t.lower()}", url, str(pub.date()), body, connection)
                if rows:
                    upsert_many(connection, "etf_daily", list(rows[0].keys()), rows, "update")
            out[t] = len(rows)
        except Exception as exc:
            log.warning("etf %s failed: %r", t, exc)
            out[t] = 0
    if connection is not None:
        prev_td = today - timedelta(days=1) if today else None
        if prev_td:
            while prev_td.weekday() >= 5:
                prev_td -= timedelta(days=1)
        for issuer, tickers in (
            ("Flows:ETFShares:Direxion", [t for t in out if t in DIREXION_TICKERS]),
            ("Flows:ETFShares:ProShares", [t for t in out if t in PROSHARES_TICKERS]),
            ("Flows:ETFShares:SSGA", [t for t in out if t in SSGA_TICKERS]),
        ):
            failed = [t for t in tickers if out[t] == 0]
            stale = [t for t in tickers if latest_dates.get(t) and latest_dates[t] < prev_td]
            note = ("failed: " + ",".join(failed) if failed else "") + (" stale:" + ",".join(stale) if stale else "")
            record_health(
                connection,
                issuer,
                not failed and not stale,
                pub,
                sum(out[t] for t in tickers),
                note.strip()[:500],
            )
    return out


CBOE_PC_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{day}_daily_options"


_PC_SERIES = {
    "TOTAL PUT/CALL RATIO": "cboe_pc_total",
    "INDEX PUT/CALL RATIO": "cboe_pc_index",
    "EQUITY PUT/CALL RATIO": "cboe_pc_equity",
    "EXCHANGE TRADED PRODUCTS PUT/CALL RATIO": "cboe_pc_etp",
    "SPX + SPXW PUT/CALL RATIO": "cboe_pc_spx",
    "CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO": "cboe_pc_vix",
    "OEX PUT/CALL RATIO": "cboe_pc_oex",
}
_PC_NAMES_ZH = {
    "cboe_pc_total": "全市场看跌看涨比",
    "cboe_pc_index": "指数看跌看涨比",
    "cboe_pc_equity": "股票看跌看涨比",
    "cboe_pc_etp": "ETP 看跌看涨比",
    "cboe_pc_spx": "SPX 看跌看涨比",
    "cboe_pc_vix": "VIX 看跌看涨比",
    "cboe_pc_oex": "OEX 看跌看涨比",
}


def pc_series_id(name):
    """Map a Cboe ratios[] name to a stable series id."""
    n = (name or "").strip().upper()
    if n in _PC_SERIES:
        return _PC_SERIES[n]
    slug = re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")
    return f"cboe_pc_other_{slug}" if slug else None


def parse_cboe_pc(payload, obs_date, published_at):
    """Cboe daily market_statistics ratios[] → observations rows (stable ids)."""
    out = []
    for r in (payload or {}).get("ratios") or []:
        name = (r.get("name") or "").strip().upper()
        series = pc_series_id(name)
        val = r.get("value")
        if not series or val is None:
            continue
        try:
            out.append(
                {
                    "series_id": series,
                    "obs_date": obs_date,
                    "value": float(val),
                    "published_at": published_at,
                    "vintage": "initial",
                }
            )
        except (ValueError, TypeError):
            continue
    return out


def collect_cboe_pc(http, connection, day, raw_dir, published_at=None):
    url = CBOE_PC_URL.format(day=day)
    t0 = time.monotonic()
    try:
        r = http.request("GET", url, headers=UA)
        payload = r if isinstance(r, dict) else json.loads(r)
        raw = r.encode() if isinstance(r, str) else json.dumps(r).encode()
        rows = parse_cboe_pc(payload, day, published_at)
        lat = time.monotonic() - t0
        if connection is not None:
            save_raw(raw_dir, "cboe-pc", url, str(day), raw, connection)
            if rows:
                catalog = [
                    {
                        "series_id": x["series_id"],
                        "name_zh": _PC_NAMES_ZH.get(x["series_id"], x["series_id"]),
                        "unit": "ratio",
                        "frequency": "daily",
                        "source": "Cboe",
                    }
                    for x in rows
                ]
                upsert_many(
                    connection, "series_catalog", ["series_id", "name_zh", "unit", "frequency", "source"], catalog
                )
                upsert_many(connection, "observations", list(rows[0].keys()), rows, "update")
            record_health(connection, "Flows:CboePC", True, published_at, len(rows), str(day), lat)
        return {"date": str(day), "rows": len(rows)}
    except Exception as exc:
        if connection is not None:
            record_health(connection, "Flows:CboePC", False, published_at, 0, f"{day} {exc!r}")
        log.warning("cboe pc %s failed: %r", day, exc)
        return {"date": str(day), "rows": 0, "error": str(exc)}
