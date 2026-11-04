"""Weekly PIT panel for the 穿透估值 backtest — Friday closes 2018→2026."""

from datetime import date, timedelta

from inves_cog.valuation.ceiling import cap_multiplier, implied_m

CYCLICAL = {"MU", "WDC", "STX", "SNDK", "SKHY", "XOM", "CVX", "AMAT", "LRCX", "KLAC", "ASML"}
FINANCIAL = {"JPM", "V", "MA"}
FWD_WEEKS = (13, 26, 52, 104, 156)


def fridays(start, end):
    d = start
    while d.weekday() != 4:
        d += timedelta(days=1)
    while d <= end:
        yield d
        d += timedelta(days=7)


def build_panel(conn, tickers, prices, states_map, spy):
    """Weekly rows per ticker: raw close, shares/net_debt/NOPAT/E_next from
    latest fin_state filed <= Friday, EV multiple, m8/m7/m10, fwd SPY-excess."""
    out = []
    fridays_list = [f for f in fridays(date(2018, 1, 5), date(2026, 10, 30))]
    for t in tickers:
        bars = prices.get(t, {})
        states = states_map.get(t, [])
        for friday in fridays_list:
            # last bar day <= friday (PIT — use the latest close available)
            bar_days = [d for d in bars if d <= friday]
            if not bar_days:
                continue
            close = bars[max(bar_days)]["close"]
            st = next((s for s in reversed(states) if s.filed <= friday), None)
            if not st:
                continue
            v = st.values
            rev_ttm = v.get("rev_ttm") or 0
            # fin_state stores percents as numbers (33.3 = 33.3%)
            if v.get("op_margin_ttm") is not None:
                nopat = (v["op_margin_ttm"] / 100) * rev_ttm * 0.82
            elif v.get("ni_ttm"):
                nopat = v["ni_ttm"]  # fallback: NI as NOPAT proxy when op_margin missing
            else:
                nopat = 0
            e_next = nopat * (1 + max(-0.2, min(0.5, (v.get("rev_growth") or 0) / 100)))
            if t in FINANCIAL:
                ev = close * (v.get("shares") or 0)  # market cap, net debt meaningless for banks
            else:
                ev = close * (v.get("shares") or 0) + (v.get("net_debt") or 0)
            mult = ev / e_next if e_next > 0 else None
            row = {
                "ticker": t,
                "date": friday,
                "close": close,
                "e_next": e_next,
                "ev": ev,
                "multiple": mult,
                "quality": "low" if (v.get("fcf_ttm") or 0) / (v.get("ni_ttm") or 1) < 0.5 else "normal",
                "cyclical": t in CYCLICAL,
            }
            if nopat == 0:
                row.update(m8=None, m7=None, m10=None, bucket="data_missing")
            elif e_next > 0:
                row.update(m8=implied_m(mult, 0.08), m7=implied_m(mult, 0.07), m10=implied_m(mult, 0.10), bucket=None)
            else:
                implied_p = ev / cap_multiplier(10, 0.10)
                row.update(
                    m8=None,
                    m7=None,
                    m10=None,
                    bucket="no-earnings",
                    implied_margin=implied_p / rev_ttm if rev_ttm else None,
                )
            out.append(row)
    return out
