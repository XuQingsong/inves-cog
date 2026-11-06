"""Page render cache: TTL, single-flight, 200-only."""

import threading
import time

import inves_cog.web.api as api


def _reset():
    api._render_cache.clear()
    api._render_locks.clear()


def test_second_request_within_ttl_skips_render(monkeypatch):
    _reset()
    calls = []

    def produce():
        calls.append(1)
        return "<html>one</html>"

    r1 = api._cached_page(("k",), produce)
    r2 = api._cached_page(("k",), produce)
    assert calls == [1]
    assert r1.body == r2.body == b"<html>one</html>"


def test_expired_key_renders_again(monkeypatch):
    _reset()
    calls = []
    now = [1000.0]
    monkeypatch.setattr(api, "_now", lambda: now[0])

    def produce():
        calls.append(1)
        return "<html>x</html>"

    api._cached_page(("k",), produce)
    now[0] += api._RENDER_TTL + 1
    api._cached_page(("k",), produce)
    assert len(calls) == 2


def test_concurrent_requests_render_once():
    _reset()
    calls = []
    gate = threading.Event()

    def produce():
        calls.append(1)
        gate.wait(5)
        return "<html>s</html>"

    results = []
    t1 = threading.Thread(target=lambda: results.append(api._cached_page(("k",), produce)))
    t1.start()
    while not calls:  # t1 is inside produce holding the lock
        time.sleep(0.01)
    t2 = threading.Thread(target=lambda: results.append(api._cached_page(("k",), produce)))
    t2.start()
    time.sleep(0.1)  # t2 now waits on the key lock
    gate.set()
    t1.join(5)
    t2.join(5)
    assert calls == [1]
    assert all(r.body == b"<html>s</html>" for r in results)


def test_different_keys_render_separately():
    _reset()
    calls = []
    api._cached_page(("a",), lambda: calls.append("a") or "A")
    api._cached_page(("b",), lambda: calls.append("b") or "B")
    assert sorted(calls) == ["a", "b"]
