"""Frozen market-state rules plus independent numerical/graph counterexamples."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.harness.tools.golden import load_golden

ROOT = Path(__file__).resolve().parents[2]


def linear_sample(n=162):
    x = np.arange(n, dtype=float)
    factors = pd.DataFrame({"m": np.sin(x / 4) / 100, "s": np.cos(x / 7) / 150, "t": np.sin(x / 11) / 200})
    y = 0.001 + factors @ np.array([1.2, 0.5, 0.8])
    return y, factors


@pytest.mark.phase1_blocking
def test_marketstate_flags():
    from inves_cog.marketstate.market import market_flags

    for row in load_golden("m6_marketstate.json")["cases"]:
        result = market_flags(**row["input"])
        assert {key: result[key] for key in row["expected"]} == row["expected"]
    assert not market_flags(spy_5d_pct=-2, down_share_5d_pct=70)["shock_flag"]
    assert market_flags(spy_5d_pct=-5, down_share_5d_pct=70)["shock_flag"]


@pytest.mark.phase1_blocking
def test_residual_exact_linear():
    from inves_cog.marketstate.regression import fit_predict

    y, factors = linear_sample()
    result = fit_predict(y, factors, signal_index=160)
    assert result["alpha"] == pytest.approx(0.001, abs=1e-12)
    assert list(result["betas"].values()) == pytest.approx([1.2, 0.5, 0.8], abs=1e-9)
    assert result["resid"] == pytest.approx(0, abs=1e-12)
    assert result["nobs"] == 120 and result["dof"] == 116


@pytest.mark.phase1_blocking
def test_residual_leave_one_out():
    from inves_cog.marketstate.factors import basket_return

    sample = pd.DataFrame({"A": [0.1, 0.2], "B": [-0.1, 0.3]})
    expected = basket_return(sample, ["A", "B"], exclude="A")
    sample["A"] *= 10
    pd.testing.assert_series_equal(basket_return(sample, ["A", "B"], exclude="A"), expected)
    assert list(expected) == [-0.1, 0.3]  # Q-M6-13: a single remaining member is valid.
    assert basket_return(sample, ["A"], exclude="A").isna().all()
    assert basket_return(sample, ["A"]).isna().all()  # Standalone basket still needs two.


@pytest.mark.phase1_blocking
def test_residual_window_excludes_today():
    from inves_cog.marketstate.regression import fit_predict

    y, factors = linear_sample()
    before = fit_predict(y, factors, signal_index=160)
    y.iloc[160] += 10
    after = fit_predict(y, factors, signal_index=160)
    assert before["betas"] == after["betas"] and before["alpha"] == after["alpha"]
    assert after["resid"] - before["resid"] == pytest.approx(10)


@pytest.mark.phase1_blocking
def test_insufficient_history_null():
    from inves_cog.marketstate.regression import fit_predict

    y, factors = linear_sample()
    result = fit_predict(y, factors, signal_index=59)
    assert result["resid"] is None and result["null_reason"] == "insufficient_history"
    assert fit_predict(y, factors, signal_index=60)["resid"] is not None
    duplicate = factors.assign(duplicate=factors["m"])
    assert fit_predict(y, duplicate, signal_index=160)["null_reason"] == "rank_deficient"


@pytest.mark.phase1_blocking
def test_post_session_null_when_missing():
    from inves_cog.marketstate.factors import adjusted_returns, post_return

    assert post_return(100, None) is None and post_return(100, 101) == pytest.approx(0.01)
    frame = pd.DataFrame({"close": [100, 50], "adj_factor": [0.5, 1]})
    assert adjusted_returns(frame).iloc[-1] == 0


@pytest.mark.phase1_blocking
def test_beta_share_bounds():
    from inves_cog.marketstate.market import beta_share

    assert beta_share(0.01, 0.00499) is None
    assert beta_share(0, 0.005) == 1
    assert beta_share(0.02, 0.01) == 0
    assert beta_share(0.001, -0.01) == pytest.approx(0.9)
    assert beta_share(None, 0.1) is None


@pytest.mark.phase1_blocking
def test_marketstate_price_only(tmp_path):
    from inves_cog.marketstate.repository import assert_price_query

    for table in ("ingest.bars_daily", "graph.baskets", "ingest.issuer_profiles", "ingest.macro_observations"):
        assert_price_query("SELECT * FROM " + table)
    for table in ("ingest.info_items", "fundamentals.fin_state", "graph.relations", "trading.daily_scores"):
        with pytest.raises(ValueError):
            assert_price_query("SELECT * FROM " + table)
    from tests.harness.tools.checks import scan_imports

    scan_imports(ROOT)


@pytest.mark.phase1_blocking
def test_graph_draft_requires_citation(clock, tmp_path):
    from tests.m6.recordings import assert_graph_request_bounds, recorded_draft

    assert_graph_request_bounds()

    fixture = json.loads((ROOT / "tests/fixtures/phase1/m6/draft.json").read_text())
    result = recorded_draft(fixture, clock=clock, recordings=tmp_path)
    assert len(result["relations"]) == 1 and len(result["exposures"]) == 1
    assert result["relations"][0]["status"] == "候选"
    assert result["exposures"][0]["exposure_usd"] == 123
    fixture["source"]["text"] = "Changed evidence with no valid cited passage."
    result = recorded_draft(fixture, clock=clock, recordings=tmp_path)
    assert result["relations"] == [] and result["exposures"] == []


@pytest.mark.phase1_blocking
def test_candidate_edges_not_used(clock):
    from inves_cog.perception.graph.review import ReviewQueue

    queue = ReviewQueue(clock=clock)
    queue.add({"relation_id": "r1", "status": "候选", "basket_ids": ["hdd"], "exposure_usd": 123})
    assert queue.confirmed() == [] and len(queue.candidates("hdd")) == 1
    queue.review(["r1"], action="confirm")
    assert len(queue.confirmed()) == 1 and queue.confirmed()[0]["reviewed_at"] == clock.now_utc()
    queue.review(["r1"], action="confirm")
    assert len(queue.confirmed()) == 1
    queue.add({"relation_id": "r2", "status": "候选", "basket_ids": ["hdd"]})
    queue.review(["r2"], action="reject")
    assert len(queue.confirmed()) == 1 and queue.candidates("hdd") == []


@pytest.mark.phase1_blocking
def test_auto_cluster_suggestion():
    from inves_cog.marketstate.clustering import suggestions

    y, factors = linear_sample(60)
    returns = pd.DataFrame({"A": y, "B": y * 2, "C": y * 3, "D": factors["s"]})
    found = suggestions(returns, existing=[])
    assert ["A", "B", "C"] in [row["members"] for row in found]
    assert suggestions(returns, existing=[{"members": ["A", "B", "C"]}]) == []
    assert suggestions(returns.iloc[:59], existing=[]) == []


@pytest.mark.phase1_live
def test_marketstate_live_smoke(clock):
    from inves_cog.marketstate.live import run_smoke

    result = run_smoke(clock=clock)
    assert result["coverage"] == result["expected"]
    assert result["expected"] >= 59
