"""Durable per-issuer SEC progress, stored in the existing source cursor table."""


class SECProgress:
    key = "sec-submissions-progress"

    def __init__(self, repo, clock, day, tickers):
        self.repo, self.clock, self.tickers = repo, clock, list(tickers)
        previous = repo.get_cursor(self.key) or {}
        self.state = (
            previous
            if previous.get("day") == day.isoformat() and previous.get("universe") == self.tickers
            else {"day": day.isoformat(), "universe": self.tickers, "completed": [], "failures": {}, "gaps": {}}
        )
        self.pending = [ticker for ticker in self.tickers if ticker not in self.state["completed"]]

    def save(self):
        self.state["updated_at"] = self.clock.now_utc().isoformat()
        self.repo.set_cursor(self.key, self.state, self.clock.now_utc())

    def start(self, ticker):
        self.state["current_ticker"] = ticker
        self.save()

    def fail(self, ticker, exc):
        chain, cause = [], exc
        while cause is not None and type(cause).__name__ not in chain:
            chain.append(type(cause).__name__)
            cause = cause.__cause__
        self.state["failures"][ticker] = {
            "ticker": ticker,
            "error_type": type(exc).__name__,
            "error_code": getattr(exc, "error_code", None),
            "http_status": getattr(exc, "status_code", None),
            "request_url": getattr(exc, "request_url", None),
            "exception_chain": chain,
            "message": str(exc)[:300],
            "observed_at": self.clock.now_utc().isoformat(),
        }
        self.save()

    def complete(self, ticker, gaps):
        self.state["completed"].append(ticker)
        self.state["failures"].pop(ticker, None)
        self.state["gaps"][ticker] = gaps
        self.state["current_ticker"] = None
        self.save()

    def result(self, count):
        failed = list(self.state["failures"].values())
        gaps = [gap for values in self.state["gaps"].values() for gap in values]
        return {
            "processed_count": count,
            "status": "degraded" if failed or gaps else "ok",
            "source_success": not failed,
            "note": f"Completed issuers: {len(self.state['completed'])}/{len(self.tickers)}; "
            f"failed issuers: {len(failed)}; unverified earnings accessions: {len(gaps)}; "
            f"resumed issuers this run: {len(self.pending)}",
            "completed_companies": len(self.state["completed"]),
            "failed_companies": failed,
            "acceptance_gaps": gaps,
            "cached_completed_cycle": not self.pending,
        }
