"""Dynamic-P/E (穿透估值) ceiling model — docs/phase2/valuation-system.md §1-§4.

dyn_pe: E0=1 grows at g=(m**(1/n)-1) for n years to m, then flat perpetuity.
implied_m: bisection inverse of dyn_pe.
cap_multiplier: no-earnings convention — linear arithmetic growth 0→P over n years,
flat perpetuity after; value/P.
"""


def dyn_pe(m, r, n=10):
    if m <= 0 or n <= 0:
        return 0.0
    g = m ** (1 / n) - 1
    grow = sum(((1 + g) ** t) / ((1 + r) ** t) for t in range(1, n + 1))
    terminal = (m / r) / ((1 + r) ** n)
    return (grow + terminal) / (1 + g)


def implied_m(multiple, r, n=10):
    if multiple is None or multiple <= 0:
        return None
    cap = dyn_pe(200, r, n)
    if multiple > cap:
        return None
    lo, hi = 0.2, 200.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if dyn_pe(mid, r, n) < multiple:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cap_multiplier(n, r):
    """Value/P for profit reaching P by linear arithmetic growth 0→P over n years,
    flat perpetuity after. Book convention: profit = P*t/n in year t."""
    grow = sum((t / n) / ((1 + r) ** t) for t in range(1, n + 1))
    terminal = (1 / r) / ((1 + r) ** n)
    return grow + terminal
