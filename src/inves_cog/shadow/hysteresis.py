"""B2 holding state is a counterfactual record, never a trade instruction."""

from copy import deepcopy

from inves_cog.shadow.settings import settings


def step_hysteresis(state, observation):
    c = settings()["f02"]
    state = deepcopy(state)
    state.setdefault("active", False)
    state.setdefault("bad_filings", 0)
    state.setdefault("pending_exit", False)
    action, reason = "none", None
    event = observation.get("event")
    filing = observation.get("filing_id") if event == "filing" else None
    fresh = filing is not None and filing != state.get("last_filing_id")
    if event == "entry":
        state.update(
            active=observation.get("b2_active") is True,
            pending_exit=False,
            bad_filings=0,
            last_filing_id=observation.get("filing_id"),
        )
        return state, {"action": "entry", "reason": "仅影子入场状态"}
    quality, growth = observation.get("raw_quality"), observation.get("growth")
    if fresh:
        accel, margin = observation.get("rev_accel_pp"), observation.get("gm_change_pp")
        bad = accel is not None and margin is not None and accel < 0 and margin < 0
        state["bad_filings"] = state["bad_filings"] + 1 if bad else 0
        state["last_filing_id"] = filing
    if state.get("closed"):
        return state, {"action": action, "reason": reason}
    if observation.get("other_m50") is True:
        state.update(active=False, closed=True, pending_exit=False)
        action, reason = "close", "其他M50硬条件（仅影子）"
    elif state["pending_exit"] and fresh and filing != state.get("exit_filing_id"):
        line = observation.get("quality_line")
        if quality is not None and line is not None and quality < line:
            action, reason = "close", "下一份财报原始质量仍低于M50质量线（仅影子）"
            state.update(closed=True, pending_exit=False)
        elif quality is not None and line is not None:
            state["pending_exit"] = False
    elif state["active"]:
        upgraded = quality is not None and quality >= c["quality_upgrade"]
        deterioration = (growth is not None and growth < c["growth_exit"]) or state["bad_filings"] >= c["bad_filings"]
        if upgraded:
            state["active"] = False
        elif deterioration:
            state["active"] = False
            line = observation.get("quality_line")
            if quality is not None and line is not None and quality < line:
                state.update(pending_exit=True, exit_filing_id=state.get("last_filing_id"))
                action, reason = "half", "B2退出程序：次日开盘减1/2（仅影子）"
    return state, {"action": action, "reason": reason}
