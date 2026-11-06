"""UD-A-58: discover and cache free official S&P membership-change announcements."""

import argparse
import hashlib
import json
import re
import signal
import time
from pathlib import Path

import httpx

from inves_cog.backtest.membership import AnnouncementHTML, parse_announcement


def save(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    signal.alarm(900)
    started = time.monotonic()
    requests = 0
    a.cache.mkdir(parents=True, exist_ok=True)
    a.output.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        timeout=10, follow_redirects=True, headers={"User-Agent": "inves-cog local historical research"}
    )

    def get(url):
        nonlocal requests
        path = a.cache / (hashlib.sha256(url.encode()).hexdigest() + ".html")
        if path.exists():
            return path.read_text()
        if requests >= 400:
            raise RuntimeError("official source request budget exhausted")
        time.sleep(0.5)
        response = client.get(url)
        requests += 1
        response.raise_for_status()
        path.write_text(response.text)
        return response.text

    articles, archives = {}, []
    for year in range(2018, 2027):
        ended = False
        for offset in range(0, 500, 100):
            url = f"https://press.spglobal.com/index.php?s=2429&l=100&year={year}&o={offset}"
            parsed = AnnouncementHTML()
            parsed.feed(get(url))
            links = {u: t for u, t in parsed.links if re.match(rf"https://press.spglobal.com/{year}-\d\d-\d\d-", u)}
            archives.append(dict(year=year, offset=offset, article_links=len(links), source=url))
            for link, title in links.items():
                if link.rsplit("/", 1)[-1][:10] > "2026-11-06":
                    continue
                if ("500" in title and re.search(r"join|replace|change|add|delete|rebalanc", title, re.I)) or re.search(
                    r"Indices.*(?:Changes|Rebalanc)|Quarterly.*Changes", title, re.I
                ):
                    articles[link] = title
            if len(links) < 100:
                ended = True
                break
        if not ended:
            raise RuntimeError(f"archive pagination incomplete: {year}")
        save(a.output / "official-discovery.json", dict(archives=archives, articles=articles, requests=requests))
    events, reviews = [], []
    for i, (url, title) in enumerate(sorted(articles.items())):
        html = get(url)
        rows = parse_announcement(html, url)
        if rows:
            events.extend(rows)
        else:
            reviews.append(dict(source=url, title=title, reason="no dated S&P500 table parsed"))
        save(
            a.output / "official-events.json",
            dict(
                events=events,
                unparsed_announcements=reviews,
                announcements_processed=i + 1,
                announcements_total=len(articles),
                requests=requests,
                elapsed=time.monotonic() - started,
                phase="complete" if i + 1 == len(articles) else "running",
            ),
        )
    client.close()
    print(json.dumps(dict(announcements=len(articles), events=len(events), unparsed=len(reviews), requests=requests)))


if __name__ == "__main__":
    main()
