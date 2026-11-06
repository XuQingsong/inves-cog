"""Page render cache: TTL, single-flight, per-app isolation."""

import threading
import time

import inves_cog.web.api as api


def test_second_request_within_ttl_skips_render():
    cache = api._PageCache()
    calls = []

    def produce():
        calls.append(1)
        return "<html>one</html>"

    r1 = cache.get(("k",), produce)
    r2 = cache.get(("k",), produce)
    assert calls == [1]
    assert r1.body == r2.body == b"<html>one</html>"


def test_expired_key_renders_again():
    now = [1000.0]
    cache = api._PageCache(now=lambda: now[0])
    calls = []

    def produce():
        calls.append(1)
        return "<html>x</html>"

    cache.get(("k",), produce)
    now[0] += api._RENDER_TTL + 1
    cache.get(("k",), produce)
    assert len(calls) == 2


def test_concurrent_requests_render_once():
    cache = api._PageCache()
    calls = []
    gate = threading.Event()

    def produce():
        calls.append(1)
        gate.wait(5)
        return "<html>s</html>"

    results = []
    t1 = threading.Thread(target=lambda: results.append(cache.get(("k",), produce)))
    t1.start()
    while not calls:  # t1 is inside produce holding the lock
        time.sleep(0.01)
    t2 = threading.Thread(target=lambda: results.append(cache.get(("k",), produce)))
    t2.start()
    time.sleep(0.1)  # t2 now waits on the key lock
    gate.set()
    t1.join(5)
    t2.join(5)
    assert calls == [1]
    assert all(r.body == b"<html>s</html>" for r in results)


def test_different_keys_render_separately():
    cache = api._PageCache()
    calls = []
    cache.get(("a",), lambda: calls.append("a") or "A")
    cache.get(("b",), lambda: calls.append("b") or "B")
    assert sorted(calls) == ["a", "b"]


def test_caches_are_isolated_per_instance():
    a, b = api._PageCache(), api._PageCache()
    calls = []
    a.get(("k",), lambda: calls.append(1) or "A")
    b.get(("k",), lambda: calls.append(1) or "B")
    assert calls == [1, 1]


def test_entries_capped_at_max():
    cache = api._PageCache()
    for i in range(40):
        cache.get((f"k{i}",), lambda i=i: f"<html>{i}</html>")
    assert len(cache._entries) <= 32


def test_expired_entries_purged_on_write():
    now = [1000.0]
    cache = api._PageCache(now=lambda: now[0])
    cache.get(("old",), lambda: "x")
    now[0] += api._RENDER_TTL + 1
    cache.get(("new",), lambda: "y")
    assert "old" not in {k[0] for k in cache._entries}
    assert "new" in {k[0] for k in cache._entries}


def test_concurrent_stress_no_errors_and_bounded():
    import random

    cache = api._PageCache()
    errors = []
    rng = random.Random(7)

    def worker():
        try:
            for _ in range(200):
                cache.get((f"k{rng.randrange(100)}",), lambda: "x" * 64)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert errors == []
    assert len(cache._entries) <= api._PageCache._MAX_ENTRIES
