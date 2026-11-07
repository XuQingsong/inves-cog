"""Post-session snapshots must not fire multi_3d/multi_5d (daily-residual paths)."""

import pytest

from inves_cog.perception.anomaly.assemble import detect_snapshot

pytestmark = pytest.mark.phase1_blocking


def _snapshot(session, *, resid=-0.15, sigma=0.03, ret=-0.08):
    hist = [{"ret": ret, "resid": resid, "sigma": sigma} for _ in range(6)]
    return {
        "trade_date": "2026-11-06",
        "session": session,
        "baskets": [],
        "basket_history": {},
        "member_returns": {},
        "daily": [
            {
                "ticker": "AAA",
                "ret": ret,
                "resid": resid,
                "resid_z": resid / sigma,
                "sigma": sigma,
                "l3_ex_ret": None,
                "primary_basket": None,
                "gap_open": None,
                "volume_mult": None,
                "ret_6m_rank": None,
                "corr_jump": None,
            }
        ],
        "daily_history": {"AAA": hist},
        "rotation": [],
        "macro": {},
        "bars": [],
        "shorts": {},
        "clusters": [],
        "levels": {},
        "names": {},
        "pool": ["AAA"],
    }


def test_post_session_skips_multi_paths():
    hits = detect_snapshot(_snapshot("post"))
    paths = {p for h in hits for p in h["entry_paths"]}
    assert "multi_3d" not in paths and "multi_5d" not in paths


def test_close_session_multi_5d_unchanged():
    hits = detect_snapshot(_snapshot("close"))
    paths = {p for h in hits for p in h["entry_paths"]}
    assert "multi_5d" in paths
    lite = next(h for h in hits if "AAA" in h.get("tickers", set()) and "multi_5d" in h["entry_paths"])
    assert abs(lite["max_abs_z"] - (5 * 0.15 / (0.03 * 5**0.5))) < 1e-9


def test_post_single_day_path_still_hits():
    snap = _snapshot("post", resid=0.28, sigma=0.03, ret=0.30)
    hits = detect_snapshot(snap)
    paths = {p for h in hits for p in h["entry_paths"]}
    assert "B" in paths  # single-day residual path still fires post-session
