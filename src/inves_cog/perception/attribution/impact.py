"""Impact split. The three parts add back to the residual return."""


def anomaly_status(universe, scores):
    if universe == "wide":
        return "已记录"
    if not scores or all(score < 0.5 for score in scores):
        return "已发现·原因未明"
    return "假设中"


def require_anomaly_status(anomalies):
    missing = [row.get("anomaly_id") for row in anomalies if not row.get("status")]
    if missing:
        raise ValueError(f"异常缺少状态: {missing}")


def decompose(total, sum_delta_e, pe, market_cap, verdict, true_features, available_features):
    event = _event_part(total, sum_delta_e, pe, market_cap, verdict)
    ratio = 0.0 if not available_features else true_features / available_features
    amplification = (total - event) * ratio
    return {
        "event": event,
        "amplification": amplification,
        "unexplained": total - event - amplification,
    }


def _event_part(total, sum_delta_e, pe, market_cap, verdict):
    if verdict == "无法检验" or sum_delta_e is None or not market_cap:
        return 0.0
    cap = abs(sum_delta_e * pe / market_cap)
    sign = 1.0 if total >= 0 else -1.0
    return sign * min(abs(total), cap)
