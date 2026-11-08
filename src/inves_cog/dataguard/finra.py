"""UD-A-59: official consolidated FINRA daily short volume; never short interest.
Layout: https://www.finra.org/sites/default/files/DailyShortSaleVolumeFileLayout.pdf
Publication: FINRA daily-file page promises 18:00 ET, corrections may arrive later.
"""

import csv
import io

from inves_cog.flows.store import save_raw, upsert_many

URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt"


def parse_daily(text, day, tickers):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[-1].isdigit():
        raise ValueError("FINRA daily file has no valid trailer")
    header = lines[0].replace(" ", "")
    if header != "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market":
        raise ValueError("Unexpected FINRA daily file header")
    if int(lines[-1]) != len(lines) - 2:
        raise ValueError("FINRA daily file count does not match trailer")
    source = csv.DictReader(io.StringIO("\n".join([header, *lines[1:-1]])), delimiter="|")
    rows, seen = [], set()
    for row in source:
        if row.get("Date") != day.strftime("%Y%m%d"):
            raise ValueError("FINRA file date does not match requested session")
        symbol = row["Symbol"]
        if not symbol or symbol in seen:
            raise ValueError("Duplicate or missing FINRA symbol")
        seen.add(symbol)
        # FINRA began shipping fractional-share volumes (e.g. 562765.465412); bounds-check the
        # float, then round to the bigint storage columns.
        short, exempt, total = (float(row[k]) for k in ("ShortVolume", "ShortExemptVolume", "TotalVolume"))
        if not 0 <= exempt <= short <= total:
            raise ValueError("Invalid FINRA volume bounds")
        if symbol in tickers:
            rows.append(dict(date=day, ticker=symbol, short_volume=int(round(short)), total_volume=int(round(total))))
    return rows


def collect(http, connection, raw_dir, *, day, tickers, now):
    url = URL.format(day=day.strftime("%Y%m%d"))
    text = http.request("GET", url)
    rows = parse_daily(text, day, set(tickers))
    # save_raw records actual fetched_at, not the historical session's supposed availability.
    raw = save_raw(raw_dir, "FINRA:CNMS", url, day, text, connection=connection)
    with connection.transaction():
        upsert_many(connection, "short_volume", ("date", "ticker", "short_volume", "total_volume"), rows, "update")
    return {"rows": len(rows), "data_date": str(day), "fetched_at": now.isoformat(), "sha256": raw["sha256"]}
