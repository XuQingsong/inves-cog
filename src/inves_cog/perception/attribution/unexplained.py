"""An unexplained anomaly is rechecked once per session for five sessions, then it stops."""


def classify_unexplained(scores):
    if any(score >= 0.5 for score in scores):
        return None
    return "已发现·原因未明"


def recheck_flags(session_count):
    return [index < 5 for index in range(session_count)]


def attention_line(held, max_abs_z):
    if held and max_abs_z >= 4:
        return "请人工查看"
    return None
