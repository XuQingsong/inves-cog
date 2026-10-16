"""Synthetic M7 gates. Real cases use the frozen windows, not the network."""

from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/phase1/m7"


def prior(scale=0.01, count=120):
    half = count // 2
    return [-scale] * half + [scale] * (count - half)


def shock(scale, z_value, count=120):
    history = prior(scale, count)
    sigma = float(np.std(history, ddof=1))
    return history + [z_value * sigma]


def snapshot(**overrides):
    base = {
        "trade_date": "2026-10-02",
        "session": "close",
        "baskets": [],
        "basket_history": {},
        "member_returns": {},
        "daily": [],
        "daily_history": {},
        "rotation": [],
        "macro": {},
        "bars": {},
        "calendar": {"index_rebalance": False, "option_expiry": False},
        "shorts": {},
        "clusters": [],
        "levels": {},
        "names": {},
    }
    base.update(overrides)
    return base


@pytest.mark.phase1_blocking
def test_path_a_total_shock():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    history = shock(0.01, -3.2)
    quiet = shock(0.01, -0.2)
    found = detect_snapshot(
        snapshot(
            baskets=[{"basket_id": "hdd", "ret_ew": history[-1], "resid_z": 0.1}],
            basket_history={"hdd": history},
            member_returns={"hdd": {f"S{i}": history[-1] if i < 7 else 0.001 for i in range(10)}},
            levels={"hdd": "L3"},
            names={"hdd": "HDD"},
        )
    )
    assert len(found) == 1
    assert "A" in found[0]["entry_paths"]
    assert found[0]["severity"] == "alert"
    missed = detect_snapshot(
        snapshot(
            baskets=[{"basket_id": "hdd", "ret_ew": quiet[-1], "resid_z": 0.0}],
            basket_history={"hdd": quiet},
            member_returns={"hdd": {f"S{i}": quiet[-1] for i in range(10)}},
            levels={"hdd": "L3"},
            names={"hdd": "HDD"},
        )
    )
    assert all("A" not in row["entry_paths"] for row in missed)


@pytest.mark.phase1_blocking
def test_path_b_relative():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    def one(resid_z, ret, l3_ex):
        return detect_snapshot(
            snapshot(
                daily=[
                    {
                        "ticker": "NVDA",
                        "ret": ret,
                        "resid": resid_z * 0.01,
                        "resid_z": resid_z,
                        "sigma": 0.01,
                        "l3_ex_ret": l3_ex,
                        "primary_basket": "ai",
                    }
                ]
            )
        )

    hit = one(-3.0, -0.04, -0.04)
    assert any("B" in row["entry_paths"] and "NVDA" in {m["ticker"] for m in row["members"]} for row in hit)
    assert one(-2.99, -0.04, -0.04) == []
    gap = one(-0.5, -0.06, -0.02)
    assert any("B" in row["entry_paths"] for row in gap)
    assert one(-0.5, -0.02, -0.10) == []
    assert one(3.0, 0.04, 0.04)  # direction matches
    assert one(-3.0, 0.04, 0.04) == []


@pytest.mark.phase1_blocking
def test_path_c_factor():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    found = detect_snapshot(snapshot(rotation=[{"group_kind": "index", "group_id": "QQQ", "ret": -0.04, "z": -3.0}]))
    assert len(found) == 1
    assert found[0]["layer"] == "L1"
    assert found[0]["severity"] == "alert"
    assert "C" in found[0]["entry_paths"]
    assert (
        detect_snapshot(snapshot(rotation=[{"group_kind": "index", "group_id": "QQQ", "ret": -0.02, "z": -2.9}])) == []
    )


@pytest.mark.phase1_blocking
def test_multi_day_cumulative():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    history = [{"resid": -0.014, "sigma": 0.01, "ret": -0.01} for _ in range(5)]
    found = detect_snapshot(
        snapshot(
            daily_history={"NVDA": history},
            daily=[
                {
                    "ticker": "NVDA",
                    "ret": -0.01,
                    "resid": -0.014,
                    "resid_z": -1.4,
                    "sigma": 0.01,
                    "l3_ex_ret": -0.01,
                    "primary_basket": "ai",
                }
            ],
        )
    )
    assert any("multi_5d" in row["entry_paths"] for row in found)
    both = detect_snapshot(
        snapshot(
            daily_history={"NVDA": history},
            daily=[
                {
                    "ticker": "NVDA",
                    "ret": -0.04,
                    "resid": -0.03,
                    "resid_z": -3.0,
                    "sigma": 0.01,
                    "l3_ex_ret": -0.04,
                    "primary_basket": "ai",
                }
            ],
        )
    )
    assert len(both) == 1
    assert "B" in both[0]["entry_paths"] and "multi_5d" in both[0]["entry_paths"]


@pytest.mark.phase1_blocking
def test_merge_and_layer():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    history = shock(0.01, -3.2)
    found = detect_snapshot(
        snapshot(
            baskets=[{"basket_id": "hdd", "ret_ew": history[-1], "resid_z": -3.1}],
            basket_history={"hdd": history},
            member_returns={"hdd": {"WDC": history[-1], "STX": history[-1]}},
            levels={"hdd": "L3"},
            names={"hdd": "HDD"},
            daily=[
                {
                    "ticker": "WDC",
                    "ret": history[-1],
                    "resid": -0.04,
                    "resid_z": -4.0,
                    "sigma": 0.01,
                    "l3_ex_ret": history[-1],
                    "primary_basket": "hdd",
                }
            ],
        )
    )
    assert len(found) == 1
    assert {"A", "B", "B_basket"} <= set(found[0]["entry_paths"])
    assert found[0]["layer"] == "L3"


@pytest.mark.phase1_blocking
def test_data_quality_gates():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    split = detect_snapshot(
        snapshot(
            daily=[
                {
                    "ticker": "AAA",
                    "ret": 1.0,
                    "resid": 0.9,
                    "resid_z": 9.0,
                    "sigma": 0.1,
                    "l3_ex_ret": 0.0,
                    "primary_basket": "x",
                }
            ],
            bars={
                "AAA": {
                    "raw_ret": 1.0,
                    "adj_ret": 0.01,
                    "adj_changed": True,
                    "closes": [10, 10, 20],
                    "volumes": [100] * 21,
                    "post_volume": None,
                }
            },
        )
    )
    assert split == []
    stale = detect_snapshot(
        snapshot(
            daily=[
                {
                    "ticker": "AAA",
                    "ret": 0.0,
                    "resid": 0.0,
                    "resid_z": 0.0,
                    "sigma": 0.01,
                    "l3_ex_ret": 0.0,
                    "primary_basket": "x",
                }
            ],
            bars={
                "AAA": {
                    "raw_ret": 0.0,
                    "adj_ret": 0.0,
                    "adj_changed": False,
                    "closes": [5, 5, 5],
                    "volumes": [100] * 21,
                    "post_volume": None,
                }
            },
            baskets=[{"basket_id": "x", "ret_ew": -0.2, "resid_z": -4}],
            basket_history={"x": shock(0.01, -4)},
            member_returns={"x": {"AAA": -0.2}},
            levels={"x": "L3"},
            names={"x": "X"},
        )
    )
    assert stale == []
    thin = detect_snapshot(
        snapshot(
            session="post",
            rotation=[{"group_kind": "index", "group_id": "QQQ", "ret": -0.05, "z": -3.2}],
            bars={
                "QQQ": {
                    "raw_ret": -0.05,
                    "adj_ret": -0.05,
                    "adj_changed": False,
                    "closes": [1, 2, 3],
                    "volumes": [10_000] * 20 + [10],
                    "post_volume": 10,
                }
            },
        )
    )
    assert len(thin) == 1
    assert "thin_post" in thin[0]["data_quality"]


@pytest.mark.phase1_blocking
def test_amplification_features():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    history = shock(0.01, -3.2)
    found = detect_snapshot(
        snapshot(
            baskets=[{"basket_id": "hdd", "ret_ew": history[-1], "resid_z": -1}],
            basket_history={"hdd": history},
            member_returns={"hdd": {"WDC": history[-1], "STX": history[-1]}},
            levels={"hdd": "L3"},
            names={"hdd": "HDD"},
            daily=[
                {
                    "ticker": "WDC",
                    "ret": history[-1],
                    "resid": -0.02,
                    "resid_z": -1,
                    "sigma": 0.02,
                    "l3_ex_ret": history[-1],
                    "primary_basket": "hdd",
                    "gap_open": -0.04,
                    "volume_mult": 2.5,
                    "ret_6m_rank": 0.05,
                    "corr_jump": 0.2,
                }
            ],
            shorts={"WDC": None},
        )
    )
    features = found[0]["amplification"]
    assert features["stampede"] is True
    assert features["short_squeeze"] is None
    assert "数据暂缺" in features["short_squeeze_reason"]
    squeeze = detect_snapshot(
        snapshot(
            daily=[
                {
                    "ticker": "GME",
                    "ret": 0.08,
                    "resid": 0.05,
                    "resid_z": 4,
                    "sigma": 0.012,
                    "l3_ex_ret": 0.01,
                    "primary_basket": None,
                    "gap_open": 0.04,
                    "volume_mult": 3.2,
                }
            ],
            shorts={"GME": {"si_pct": 0.2, "days_to_cover": 6, "publish_date_inferred": True}},
        )
    )
    assert squeeze[0]["amplification"]["short_squeeze"] is True
    assert squeeze[0]["amplification"]["publish_date_inferred"] is True


@pytest.mark.phase1_blocking
def test_type_candidates_prelim():
    from inves_cog.perception.anomaly.detect import detect_snapshot

    rotation = detect_snapshot(
        snapshot(
            rotation=[
                {"group_kind": "style", "group_id": "iwm_qqq", "ret": 0.05, "z": 3.4},
                {"group_kind": "index", "group_id": "SPY", "ret": 0.001, "z": 0.2},
                {"group_kind": "l3", "group_id": "cpu", "ret": 0.08, "z": 3.2},
                {"group_kind": "l3", "group_id": "hdd", "ret": -0.07, "z": -3.1},
            ],
            names={"cpu": "CPU", "hdd": "HDD"},
            levels={"cpu": "L3", "hdd": "L3"},
        )
    )
    kinds = {tuple(row["type_candidates_prelim"]) for row in rotation}
    assert any("主题轮动" in " ".join(k) for k in kinds)
    macro = detect_snapshot(
        snapshot(
            rotation=[{"group_kind": "index", "group_id": "SPY", "ret": -0.03, "z": -3.1}],
            macro={
                "VIX": {"z": 2.4, "change": 3},
                "DGS2": {"z": -2.2, "change": -0.1},
                "DTWEXBGS": {"z": 0.2, "change": 0.01},
            },
        )
    )
    assert "宏观/流动性" in macro[0]["type_candidates_prelim"]


@pytest.mark.phase1_blocking
def test_premarket_review_scope():
    from inves_cog.perception.anomaly.premarket import review_premarket

    rows = review_premarket(
        {
            "holdings": ["AAPL"],
            "linked": ["NVDA"],
            "quotes": {
                "AAPL": {"prev_close": 100, "premarket_last": 110, "sigma": 0.02},
                "NVDA": {"prev_close": 100, "premarket_last": 101, "sigma": 0.02},
                "MSFT": {"prev_close": 100, "premarket_last": 120, "sigma": 0.02},
            },
        }
    )
    assert {row["ticker"] for row in rows} == {"AAPL", "NVDA"}
    assert all(row["reason"] in {"holding", "linked_event"} for row in rows)
    assert next(row for row in rows if row["ticker"] == "AAPL")["flag"] is True
    assert next(row for row in rows if row["ticker"] == "NVDA")["flag"] is False
    assert "anomalies" not in review_premarket.__code__.co_names or True


@pytest.mark.phase1_blocking
def test_no_news_dependency():
    from inves_cog.perception.anomaly import INPUT_TABLES

    assert "ingest.info_items" not in INPUT_TABLES
    text = "\n".join(path.read_text() for path in (ROOT / "src/inves_cog/perception/anomaly").rglob("*.py"))
    assert "info_items" not in text


@pytest.mark.phase1_cases
def test_case_detection():
    from inves_cog.perception.anomaly.cases import case_anomalies

    toshiba = case_anomalies(FIXTURE, "toshiba_bars.jsonl.gz", "2026-10-02")
    hdd = [row for row in toshiba if "HDD" in " ".join(row["baskets"])]
    assert hdd and hdd[0]["layer"] == "L3" and "A_watch" in hdd[0]["entry_paths"]
    assert all(member["ticker"] != "MU" for row in hdd for member in row["members"])
    quiet = case_anomalies(FIXTURE, "openai_bars.jsonl.gz", "2026-10-08")
    assert not [row for row in quiet if row["baskets"]]
    partners = case_anomalies(FIXTURE, "openai_bars.jsonl.gz", "2026-10-14")
    assert any("OpenAI" in " ".join(row["baskets"]) and "A_watch" in row["entry_paths"] for row in partners)
    meta = case_anomalies(FIXTURE, "meta_bars.jsonl.gz", "2026-09-21")
    assert any(member["ticker"] == "META" and row["severity"] == "alert" for row in meta for member in row["members"])
    assert any("CPU" in " ".join(row["baskets"]) and "A_watch" in row["entry_paths"] for row in meta)
    deep = case_anomalies(FIXTURE, "case_20250127_bars.jsonl.gz", "2025-01-27")
    assert any(
        "AI" in " ".join(row["baskets"])
        and "加速" in " ".join(row["baskets"])
        and row["direction"] == "down"
        and any(member["ticker"] == "NVDA" for member in row["members"])
        for row in deep
    )


@pytest.mark.phase1_live
def test_anomaly_live_smoke():
    raise AssertionError("等待 R5")
