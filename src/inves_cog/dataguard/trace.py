"""Sanitized recovery evidence: status codes and exception classes, never URLs or messages."""

import urllib.request


class SourceTrace:
    def __init__(self):
        self.errors = []

    def record(self, exc):
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        status = status if isinstance(status, int) else None
        value = {"error_type": type(exc).__name__, "http_status": status}
        if value not in self.errors and len(self.errors) < 20:
            self.errors.append(value)

    def wrap(self, http):
        owner = self

        class HTTP:
            def request(self, *args, **kwargs):
                try:
                    return http.request(*args, **kwargs)
                except Exception as exc:
                    owner.record(exc)
                    raise

        return HTTP()

    def __enter__(self):
        self.original = urllib.request.urlopen

        def urlopen(*args, **kwargs):
            try:
                return self.original(*args, **kwargs)
            except Exception as exc:
                self.record(exc)
                raise

        urllib.request.urlopen = urlopen
        return self

    def __exit__(self, *_):
        urllib.request.urlopen = self.original


def reason(evidence):
    statuses = {e.get("http_status") for e in evidence.get("source_errors", [])}
    if 429 in statuses:
        return "来源限流（HTTP 429），未通过目标日期数据复核"
    if statuses & {401, 403}:
        return "来源拒绝访问，需要核查权限；未绕过限制"
    if 404 in statuses:
        return "来源未提供目标文件（HTTP 404）"
    if any(e.get("error_type") == "ValueError" for e in evidence.get("source_errors", [])):
        return "来源文件的格式、日期或数值校验失败"
    if evidence.get("source_errors"):
        return "来源请求失败，错误类型与状态码已记录"
    if evidence.get("candidate_rows") == 0:
        return "采集入口未返回目标日期有效行，需要核查来源当日可用性"
    return "补数后指定日期数据或下游仍未通过复核，需要核查采集与计算记录"
