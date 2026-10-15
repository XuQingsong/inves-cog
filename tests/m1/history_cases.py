"""Historical events must not silently inherit the latest-only verification limit."""

from datetime import date


def assert_historical_events(clock):
    from inves_cog.ingest.earnings_history import backfill_events

    rows = [
        {
            "ticker": "SYN",
            "cik": "1",
            "accession": str(i),
            "form": "8-K",
            "items": ["2.02"],
            "filing_date": date(2015, 1, 2),
            "report_date": date(2014, 12, 31),
            "accepted_at": None,
            "primary_document": "x.htm",
            "raw": {},
        }
        for i in range(25)
    ]
    seen, events = [], []

    class SEC:
        def get(self, url):
            seen.append(url)
            return '<div class="infoHead">Accepted</div><div class="info">2015-01-02 16:30:00</div>'

    report = backfill_events(
        rows,
        sec=SEC(),
        clock=clock,
        closes_for=lambda _: {date(2015, 1, 2): 10},
        persist_filing=lambda _: None,
        persist_event=events.append,
    )
    assert report["processed_count"] == 25 and len(seen) == 25 and len(events) == 25
    assert all(row["session"] == "post" and row["reaction_day"] == date(2015, 1, 5) for row in events)
    assert all(row["ref_close"] == 10 for row in events)

    class Bad:
        def get(self, url):
            return "<html>No Accepted evidence</html>"

    failed = backfill_events(
        rows[:1],
        sec=Bad(),
        clock=clock,
        closes_for=lambda _: {},
        persist_filing=lambda _: None,
        persist_event=events.append,
    )
    assert len(events) == 25 and failed["unverified"] == ["0"]
