"""Approved public releases, preserving each publisher's native identity."""

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from inves_cog.ingest.info import make_item

PUBLIC_FEEDS = {
    "FederalReserveNews": "https://www.federalreserve.gov/feeds/press_all.xml",
    "EIANews": "https://www.eia.gov/rss/press_rss.xml",
    "EIATodayInEnergy": "https://www.eia.gov/rss/todayinenergy.xml",
}


def parse_rss(text, *, source, clock):
    if source not in PUBLIC_FEEDS:
        raise ValueError("RSS source is not approved")
    root = ElementTree.fromstring(text)
    output = []
    for element in root.findall(".//item"):
        title = element.findtext("title")
        url = element.findtext("link")
        native = element.findtext("guid") or url
        if not title or not native:
            continue
        body = element.findtext("description")
        raw_date = element.findtext("pubDate")
        published = None
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date)
                if published.tzinfo is None:
                    published = None
            except (TypeError, ValueError):
                published = None
        output.append(
            make_item(
                "news",
                source,
                native,
                headline=title,
                body=body,
                url=url,
                clock=clock,
                published_at=published,
                upstream_provider=source,
                upstream_id=native,
                payload={"feed_url": PUBLIC_FEEDS[source], "guid": native, "pub_date_raw": raw_date},
            )
        )
    return output
