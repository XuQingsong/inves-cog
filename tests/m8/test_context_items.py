"""PR-C: candidate prompt v5 and the synthetic context items (earnings, sector/macro)."""

from datetime import date, datetime, timezone

import pytest

_CUTOFF = datetime(2026, 10, 30, 21, 0, tzinfo=timezone.utc)


def _anomaly(members=("AAA", "BBB"), baskets=(), trade_date="2026-10-30", ended="2026-10-30T21:00:00+00:00"):
    return {
        "anomaly_id": f"{trade_date}:close:001",
        "trade_date": trade_date,
        "session": "close",
        "members": [{"ticker": m} for m in members],
        "baskets": list(baskets),
        "direction": "down",
        "started_at": datetime(2026, 10, 30, 13, 30, tzinfo=timezone.utc),
        "ended_at": datetime.fromisoformat(ended),
        "universe": "pool",
    }


def _event(ticker="AAA", accepted="2026-10-29T20:08:53+00:00", accession="0001-26-000001", **extra):
    row = {
        "ticker": ticker,
        "item": "2.02",
        "session": "post",
        "accession": accession,
        "accepted_at": datetime.fromisoformat(accepted),
        "reaction_day": date(2026, 10, 30),
    }
    row.update(extra)
    return row


_REGISTRY = {
    "l2_00": {"name": "AI 算力芯片", "level": "L2", "members": ["AAA"], "factor_basis": {"kind": "market_only"}},
    "l2_01": {"name": "存储", "level": "L2", "members": ["BBB"], "factor_basis": {"kind": "market_only"}},
    "ai_capex_chain": {
        "name": "AI 资本开支链",
        "level": "L3",
        "members": ["AAA"],
        "factor_basis": {"kind": "benchmark", "tickers": ["SMH"]},
    },
    "hdd": {
        "name": "HDD",
        "level": "L3",
        "members": ["BBB"],
        "factor_basis": {"kind": "l2", "sector": "存储"},
    },
}

_KEYWORDS = {"l2_00": ["ai chip", "gpu"], "l2_01": ["memory chip", "nand", "dram"]}


def test_v5_instruction_is_the_only_system_message():
    from pathlib import Path

    from inves_cog.perception.attribution.propose import PROMPT_VERSION, candidate_instruction, candidate_output

    root = Path(__file__).resolve().parents[2]
    contract = root / "docs/phase1/contracts/m8-candidate-prompt-v5"
    assert candidate_instruction().encode("utf-8") == (contract / "instruction.txt").read_bytes()
    assert candidate_output() == __import__("json").loads((contract / "output.json").read_text())
    v4 = root / "docs/phase1/contracts/m8-candidate-prompt-v4/instruction.txt"
    assert candidate_instruction() != v4.read_text()
    assert "板块或宏观" in candidate_instruction() and "财报事件" in candidate_instruction()
    assert PROMPT_VERSION == "evidence-bridge-v5-links"


@pytest.mark.phase1_blocking
def test_earnings_items_window_and_pit_cutoff():
    from inves_cog.perception.attribution.context import earnings_items

    anomaly = _anomaly()
    in_window = _event()
    before_lower = _event(accepted="2026-10-28T15:00:00+00:00", accession="old-1")
    after_cutoff = _event(accepted="2026-10-30T22:00:00+00:00", accession="late-1")
    other_member = _event(ticker="ZZZ", accession="other-1")
    items = earnings_items(anomaly, [in_window, before_lower, after_cutoff, other_member], [], [], cutoff=_CUTOFF)
    assert [item["info_id"] for item in items] == ["earn:0001-26-000001"]
    assert items[0]["role"] == "财报事件"
    assert "受理 2026-10-29T20:08:53+00:00，盘后" in items[0]["headline"]
    assert items[0]["summary"] == "实际业绩未解析"


@pytest.mark.phase1_blocking
def test_earnings_summary_pit_and_conflicting_estimates():
    from inves_cog.perception.attribution.context import earnings_items

    anomaly = _anomaly()
    card = {
        "ticker": "AAA",
        "report_date": date(2026, 10, 29),
        "card": {
            "events": [
                {
                    "kind": "earnings_result",
                    "first_seen_at": "2026-10-29T20:11:00+00:00",
                    "facts": {"eps_actual": 0.52, "eps_est": 0.40},
                },
                {
                    "kind": "earnings_result",
                    "first_seen_at": "2026-10-30T22:30:00+00:00",
                    "facts": {"eps_actual": 9.9, "eps_est": 9.9},
                },
            ]
        },
    }
    calendar = {
        "ticker": "AAA",
        "report_date": date(2026, 10, 29),
        "eps_forecast": 0.28,
        "source": "Nasdaq",
    }
    items = earnings_items(anomaly, [_event()], [card], [calendar], cutoff=_CUTOFF)
    summary = items[0]["summary"]
    assert "实际 EPS 0.52，预期 0.4" in summary
    assert "earnings_calendar 预期 0.28（来源：Nasdaq）" in summary
    assert "9.9" not in summary  # event after cutoff is invisible


@pytest.mark.phase1_blocking
def test_earnings_items_stay_first_inside_the_cap():
    from inves_cog.perception.attribution.chain import _retrieved

    members = [f"T{i:02d}" for i in range(6)]
    anomaly = _anomaly(members=members)
    context = [
        {
            "info_id": "earn:x1",
            "published_at": datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc),
            "headline": "x",
            "role": "财报事件",
        },
        {
            "info_id": "macro:1",
            "published_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            "headline": "y",
            "role": "板块或宏观",
        },
    ]
    anomaly["context_items"] = context
    news = []
    for index in range(45):
        news.append(
            {
                "info_id": f"n{index:03d}",
                "published_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
                "first_seen_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
                "headline": f"news {index} {members[index % len(members)]}",
                "tickers": [members[index % len(members)]],
                "source_root": f"r{index}",
            }
        )
    visible = _retrieved(anomaly, news, _CUTOFF)
    assert len(visible) == 40
    assert [item["info_id"] for item in visible[:2]] == ["earn:x1", "macro:1"]


@pytest.mark.phase1_blocking
def test_sector_macro_items_gated_by_breadth():
    from inves_cog.perception.attribution.context import sector_macro_items

    pool = [
        {
            "info_id": "m1",
            "kind": "macro",
            "source": "FRED",
            "published_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            "headline": "Fed minutes",
        }
    ]
    cfg = {"min_members": 5, "min_baskets": 2, "max_items": 10, "etfs": ["SMH"], "macro_sources": []}
    small = _anomaly(members=("AAA", "BBB"), baskets=["l2_00"])
    assert sector_macro_items(small, pool, registry=_REGISTRY, keywords=_KEYWORDS, cfg=cfg, cutoff=_CUTOFF) == []
    wide = _anomaly(members=[f"T{i}" for i in range(6)], baskets=["l2_00"])
    found = sector_macro_items(wide, pool, registry=_REGISTRY, keywords=_KEYWORDS, cfg=cfg, cutoff=_CUTOFF)
    assert [item["info_id"] for item in found] == ["m1"]
    assert found[0]["role"] == "板块或宏观"
    two_baskets = _anomaly(members=("AAA", "BBB"), baskets=["l2_00", "l2_01"])
    assert sector_macro_items(two_baskets, pool, registry=_REGISTRY, keywords=_KEYWORDS, cfg=cfg, cutoff=_CUTOFF)


@pytest.mark.phase1_blocking
def test_sector_macro_sources_sort_and_cap():
    from inves_cog.perception.attribution.context import sector_macro_items

    anomaly = _anomaly(members=[f"T{i}" for i in range(6)], baskets=["l2_00", "hdd"])
    pool = [
        {  # keyword match on two baskets -> first
            "info_id": "kw",
            "kind": "news",
            "source": "benzinga",
            "headline": "GPU and memory chip supply worries",
            "summary": None,
            "tickers": [],
            "published_at": datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
        },
        {  # ETF-tagged -> one affected basket via benchmark
            "info_id": "etf",
            "kind": "news",
            "source": "benzinga",
            "headline": "Semis selloff",
            "tickers": ["SMH"],
            "published_at": datetime(2026, 10, 30, 19, 30, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 19, 30, tzinfo=timezone.utc),
        },
        {  # macro, no basket match -> last
            "info_id": "macro",
            "kind": "macro",
            "source": "FRED",
            "headline": "rates",
            "published_at": datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc),
        },
        {  # ordinary ticker news -> excluded
            "info_id": "plain",
            "kind": "news",
            "source": "benzinga",
            "headline": "AAA beats",
            "tickers": ["AAA"],
            "published_at": datetime(2026, 10, 30, 19, 30, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 30, 19, 30, tzinfo=timezone.utc),
        },
        {  # visible only after cutoff -> excluded
            "info_id": "late",
            "kind": "macro",
            "source": "FRED",
            "headline": "late",
            "published_at": datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc),
            "first_seen_at": datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc),
        },
    ]
    cfg = {"min_members": 5, "min_baskets": 2, "max_items": 10, "etfs": ["SMH"], "macro_sources": ["FRED"]}
    found = sector_macro_items(anomaly, pool, registry=_REGISTRY, keywords=_KEYWORDS, cfg=cfg, cutoff=_CUTOFF)
    assert [item["info_id"] for item in found] == ["kw", "etf", "macro"]


@pytest.mark.phase1_blocking
def test_sec_8k_items_gain_tickers_from_cik():
    from inves_cog.ingest.pipeline import Pipeline

    class _Result:
        def fetchall(self):
            return [{"cik": "0001701108", "ticker": "SPRO"}, {"cik": "0000320193", "ticker": "AAPL"}]

    class _Conn:
        def execute(self, statement, params=None):
            return _Result()

    class _Repo:
        connection = _Conn()

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.repo = _Repo()
    items = [
        {
            "info_id": "sec_8k:SEC:a",
            "headline": "8-K - Spero Therapeutics, Inc. (0001701108) (Filer)",
            "payload": {},
            "tickers": [],
        },
        {"info_id": "sec_8k:SEC:b", "headline": "ACME 8-K", "payload": {"cik": "320193"}, "tickers": []},
        {"info_id": "sec_8k:SEC:c", "headline": "8-K - Unknown Co (9999999999) (Filer)", "payload": {}, "tickers": []},
        {"info_id": "sec_8k:SEC:d", "headline": "MSFT 8-K", "payload": {}, "tickers": ["MSFT"]},
    ]
    tagged = pipeline._tag_filing_tickers(items)
    by_id = {item["info_id"]: item["tickers"] for item in tagged}
    assert by_id["sec_8k:SEC:a"] == ["SPRO"]
    assert by_id["sec_8k:SEC:b"] == ["AAPL"]
    assert by_id["sec_8k:SEC:c"] == []
    assert by_id["sec_8k:SEC:d"] == ["MSFT"]
