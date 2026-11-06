"""Bounded reproduction of the A031 TSM SEC access check; never prints credentials."""

import argparse
import json
import signal
import time
from pathlib import Path

from inves_cog.backtest.membership import AnnouncementHTML
from inves_cog.ingest.http import HTTPClient, SourceError
from inves_cog.ingest.sec_client import SECClient
from inves_cog.ingest.settings import read_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    signal.alarm(60)
    user_agent = read_environment(args.env).get("SEC_USER_AGENT", "")
    if "@" not in user_agent:
        raise ValueError("existing SEC contact User-Agent required")
    client = SECClient(user_agent=user_agent, http=HTTPClient(timeout=8, retries=0))
    roots = [
        "https://www.sec.gov/Archives/edgar/data/1046179/000201238326003352/index.json",
        "https://www.sec.gov/Archives/edgar/data/1046179/000104617926000728/index.json",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001046179.json",
        "https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/a3q26e_withguidancexfinal.htm",
    ]
    results = []
    for url in roots:
        time.sleep(1)
        try:
            content = client.get(url)
            item = dict(url=url, status=200)
            if isinstance(content, str):
                parsed = AnnouncementHTML()
                parsed.feed(content)
                item["eps_table_rows"] = [" ".join(row) for row in parsed.rows if "EPS (NT$)" in " ".join(row)]
            elif "directory" in content:
                item["items"] = len(content["directory"]["item"])
            results.append(item)
        except SourceError as error:
            results.append(dict(url=url, status=error.status_code, error_code=error.error_code))
    args.output.write_text(json.dumps(dict(contact_user_agent_present=True, results=results), indent=2) + "\n")


if __name__ == "__main__":
    main()
