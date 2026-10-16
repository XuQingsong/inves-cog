"""Ticker codes. Only the three named cases write a code."""


def n_code(*, mechanism, narrative_shock, fundamental_unchanged, unexplained):
    if unexplained:
        return "N6"
    if mechanism == "估值倍数":
        return "N2"
    if narrative_shock and fundamental_unchanged:
        return "N1"
    return None
