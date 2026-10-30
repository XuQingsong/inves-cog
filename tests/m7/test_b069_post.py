"""B-069: core config, post resid path, post direction."""

import numpy as np
import pandas as pd


def test_core_companies_reader():
    from inves_cog.perception.core_companies import core_companies

    companies = core_companies()
    assert len(companies) == 29
    assert companies["INTC"] == "cpu_pc" and companies["VRT"] == "power"


def _panel(tmp_path):
    """Minimal Panel-like stub exercising _post_resid via the real method."""
    from inves_cog.perception.anomaly.panel import PricePanel

    panel = PricePanel.__new__(PricePanel)
    idx = pd.date_range("2026-07-01", "2026-10-29", freq="B").date
    raw = pd.Series(100.0, index=idx)
    wiggle = 1 + np.linspace(-0.02, 0.02, len(idx))
    intc = raw * wiggle
    intc.iloc[-1] = raw.iloc[-1] * 0.77
    panel.post_close = {"INTC": intc, "AMD": raw * wiggle, "MU": raw}
    panel.raw_close = {t: raw.copy() for t in ("INTC", "AMD", "MU")}
    panel.l3_of = {"INTC": {"basket_id": "cpu", "members": ["INTC", "AMD", "MU"]}}
    model = {"sigma": pd.Series(0.02, index=idx)}
    return panel, len(idx) - 1, model


def test_post_resid_uses_basket_mean_and_sigma():
    panel, index, model = _panel(None)
    resid, resid_z, fallback = panel._post_resid("INTC", model, index)
    # -23% vs flat mates -> resid ~ -0.23; sigma = own post history stdev
    assert resid < -0.20 and resid_z < -1 and fallback is False


def test_post_sigma_fallback_short_history():
    from inves_cog.perception.anomaly.panel import PricePanel

    panel = PricePanel.__new__(PricePanel)
    idx = pd.date_range("2026-10-20", "2026-10-29", freq="B").date  # 8 < 20 valid
    panel.post_close = {"X": pd.Series(1.0, index=idx) * 0.9}
    panel.raw_close = {"X": pd.Series(1.0, index=idx)}
    panel.l3_of = {}
    model = {"sigma": pd.Series(0.02, index=idx)}
    resid, resid_z, fallback = panel._post_resid("X", model, len(idx) - 1)
    assert fallback is True and abs(resid_z - (-0.10 / 0.02)) < 1e-9


def test_post_direction_follows_post_ret():
    from inves_cog.perception.anomaly.assemble import _post_direction

    assert _post_direction([{"ret": -0.045}], 3.2) == "down"
    assert _post_direction([{"ret": 0.02}], -5.0) == "up"


def test_post_resid_median_vs_extreme_peer():
    """One extreme mate (INTC -23%) should not drag the peer baseline: median
    of the OTHER mates stays near the majority, keeping resid sign aligned."""
    from inves_cog.perception.anomaly.panel import PricePanel

    panel = PricePanel.__new__(PricePanel)
    idx = pd.date_range("2026-07-01", "2026-10-29", freq="B").date
    raw = pd.Series(100.0, index=idx)
    w = 1 + np.linspace(-0.02, 0.02, len(idx))

    def stock(px):
        s = raw * w
        s.iloc[-1] = raw.iloc[-1] * px
        return s

    panel.post_close = {"INTC": stock(0.77), "ARM": stock(0.922), "QCOM": stock(0.995), "AMD": stock(0.93)}
    panel.raw_close = {t: raw.copy() for t in panel.post_close}
    panel.l3_of = {"ARM": {"basket_id": "cpu", "members": ["ARM", "INTC", "QCOM", "AMD"]}}
    model = {"sigma": pd.Series(0.02, index=idx)}
    resid, _, _ = panel._post_resid("ARM", model, len(idx) - 1)
    # median of mates (-23%, -0.5%, -7%) = -7% -> resid = -7.8 - (-7) = -0.8%
    assert -0.03 < resid < 0
    # mean would give (-23-0.5-7)/3 = -10.17 -> resid +2.4% (wrong sign)
