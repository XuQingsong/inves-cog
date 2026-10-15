"""Daily orchestration with injected state_asof, explicit task time and job recording."""

from datetime import timedelta

from inves_cog.trading.scoring import score_history
from inves_cog.trading.scoring.rules import load_rule_a


class ScoringService:
    def __init__(self, *, repository, state_asof, universe, clock, params_path=None):
        self.repo, self.lookup, self.universe, self.clock = repository, state_asof, universe, clock
        self.params = load_rule_a(params_path)

    def run(self, signal_date, *, extractor="fixed", start=None):
        coverage, count = [], 0
        for entity in self.universe:
            ticker = entity["ticker"]
            bars = self.repo.bars(ticker, signal_date)
            if not any(row["trade_date"] == signal_date and row["close"] is not None for row in bars):
                coverage.append({"ticker": ticker, "null_reason": "no_bar"})
                continue
            previous = self.repo.previous(ticker, signal_date, extractor, "p-2026.10") if start is None else None
            begin = previous["signal_date"] + timedelta(days=1) if previous else start
            snapshots = score_history(
                ticker,
                bars,
                state_asof=self.lookup,
                extractor=extractor,
                start=begin,
                end=signal_date,
                previous=previous,
            )
            for snapshot in snapshots:
                self.repo.put(snapshot)
                count += 1
            latest = snapshots[-1]
            coverage.append(
                {
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "null_reason": latest["null_reason"],
                    "tradable": latest["tradable"],
                    "books": latest["books"],
                }
            )
        return {
            "processed_count": count,
            "coverage": coverage,
            "signal_date": signal_date,
            "observed_at": self.clock.now_utc(),
            "status": "ok" if len(coverage) == len(self.universe) else "degraded",
        }
