"""Monthly common-stock selection and daily liquidity exclusion ratchet."""

import re
from copy import deepcopy

EXCHANGES = {"NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEARCA", "BATS", "CBOEBZX", "AMEX", "ARCA", "CBOE"}
NON_COMMON = re.compile(r"\b(?:ETF|ETN|Fund|Trust|Notes|Preferred|Depositary|ADR|ADS|Warrants?|Units?|Rights?)\b", re.I)
SUFFIX = re.compile(r"(?:\.WS|\.U|\.R|-P\w*|\.PR\w*)$", re.I)


def security_evidence(candidate):
    attributes = {str(a).lower() for a in candidate.get("attributes", [])}
    bad = attributes & {"etf", "etn", "fund", "adr", "ads", "preferred", "warrant", "unit", "right"}
    if bad:
        return "asset_attribute:" + ",".join(sorted(bad))
    if SUFFIX.search(candidate["ticker"]):
        return "ticker_suffix:" + candidate["ticker"]
    match = NON_COMMON.search(candidate.get("name", ""))
    return "name_keyword:" + match.group() if match else None


def build_universe(candidates, trade_date, *, min_cap=2_000_000_000, min_adv=20_000_000):
    rows = []
    for candidate in candidates:
        if candidate.get("status") != "active" or candidate.get("asset_class") != "us_equity":
            continue
        if re.sub(r"[^A-Z]", "", candidate.get("exchange", "").upper()) not in EXCHANGES:
            continue
        note, reason = security_evidence(candidate), None
        shares, close = candidate.get("shares"), candidate.get("close")
        cap = shares * close if shares is not None and close is not None else None
        history = candidate.get("history", [])[-20:]
        valid = len(history) == 20 and all(
            row.get("close") is not None and row.get("volume") is not None for row in history
        )
        adv = sum(row["close"] * row["volume"] for row in history) / 20 if valid else None
        if note:
            reason = "non_common"
        elif not candidate.get("cik"):
            reason = "no_cik"
        elif shares is None:
            reason = "no_shares"
        elif close is None:
            reason = "no_price"
        elif cap < min_cap:
            reason = "below_mktcap"
        elif not valid:
            reason = "insufficient_history"
        elif adv < min_adv:
            reason = "below_adv"
        notes = [note] if note else []
        if candidate.get("multi_class"):
            notes.append("multi_class_approx")
        rows.append(
            {
                "trade_date": trade_date,
                "ticker": candidate["ticker"],
                "mktcap": cap,
                "adv20": adv,
                "included": reason is None,
                "exclude_reason": reason,
                "notes": notes,
            }
        )
    return rows


def daily_liquidity(previous, adv_by_ticker, trade_date, *, min_adv=20_000_000):
    rows = deepcopy(previous)
    for row in rows:
        row["trade_date"] = trade_date
        row["adv20"] = adv_by_ticker.get(row["ticker"])
        if row["included"]:
            if row["adv20"] is None:
                row.update(included=False, exclude_reason="insufficient_history")
            elif row["adv20"] < min_adv:
                row.update(included=False, exclude_reason="below_adv")
    return rows
