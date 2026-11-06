"""Normalize official announcement facts and preserve issuer/ticker continuity evidence."""

import csv
import json
from pathlib import Path

BASE = Path("handoff/A031/evidence/membership")


def main():
    raw = json.loads((BASE / "official-events.json").read_text())
    names = {r["ticker"] for r in csv.DictReader(open(Path.home() / "inves-cog-bt/valuation/panel_sp500.csv"))}
    grouped, seen, exceptions = {}, set(), []
    for row in raw["events"]:
        row = dict(row)
        if row["company"] == "Twenty-First Century Fox" and row["action"] == "deleted":
            exceptions.append(
                dict(
                    **row,
                    disposition="predecessor changes to TFCFA/TFCF before deletion; not the post-spin FOXA/FOX series",
                )
            )
            continue
        if row["ticker"] is None and row["company"] == "Evergy (renamed from Westar Energy)":
            row.update(ticker="EVRG", alias_note="official release: Westar renamed Evergy; EVRG effective 2018-06-05")
        copies = [row]
        if row["ticker"] == "FOXAV" and row["company"] == "Fox":
            copies = [
                {**row, "ticker": t, "alias_note": "official release says FOXAV/FOXBV become FOXA/FOX on 2019-03-19"}
                for t in ("FOXA", "FOX")
            ]
        copies = [
            {**event, "ticker": symbol}
            for event in copies
            for symbol in (event["ticker"].split("/") if event["ticker"] else [None])
        ]
        for event in copies:
            if event["ticker"] is None:
                exceptions.append(
                    dict(**event, disposition="unresolved symbol; company not represented in supplied panel")
                )
                continue
            key = event["ticker"], event["effective"], event["action"]
            if key in seen:
                continue
            seen.add(key)
            grouped.setdefault(event["ticker"], []).append(event)
    for rows in grouped.values():
        rows.sort(key=lambda r: r["effective"])
    reviews = []
    for row in raw["unparsed_announcements"]:
        title = row["title"]
        if "Kenvue" in title:
            reason = "TBA preliminary announcement; dated 2023-08-21 announcement parsed separately"
        elif "Tesla" in title:
            reason = "implementation narrative; dated 2020-11-16 and 2020-12-11 tables cover the effective event"
        elif "Fox" in title:
            reason = "continuing entity narrative; final 2019-03-14 announcement covers the event and alias"
        else:
            reason = "methodology, classification consultation or economic research; no S&P500 constituent event"
        reviews.append({**row, "disposition": reason})
    output = dict(
        events=grouped,
        exceptions=exceptions,
        reviewed_non_event_announcements=reviews,
        source_count=raw["announcements_total"],
        input_tickers=len(names),
        input_tickers_with_events=sorted(names & set(grouped)),
        input_tickers_without_events=sorted(names - set(grouped)),
        rule=(
            "entry inclusive, exit exclusive; first deletion implies initial member; "
            "no-event tickers retain supplied weekly membership"
        ),
        authority="only official S&P press release tables and explicitly cited issuer-continuity narrative",
    )
    (BASE / "ledger.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(dict(tickers=len(grouped), input_with_events=len(names & set(grouped)), exceptions=len(exceptions)))
    )


if __name__ == "__main__":
    main()
