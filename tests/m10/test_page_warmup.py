"""Page warm-up: entries fill the cache so first user requests hit it."""

import logging

import inves_cog.web.api as api


def test_warm_pass_fills_cache_and_user_hit_skips_builder():
    cache = api._PageCache()
    built = []

    def produce():
        built.append(1)
        return "<html>warm</html>"

    entries = [("brief", "page_brief_market", None, frozenset()), produce]
    api._warm_pass(cache, [entries], logging.getLogger("test"))
    assert built == [1]

    def user_produce():
        raise AssertionError("builder must not run on a cache hit")

    resp = cache.get(("brief", "page_brief_market", None, frozenset()), user_produce)
    assert resp.body == b"<html>warm</html>"


def test_warm_pass_survives_failures():
    cache = api._PageCache()
    calls = []

    def bad():
        calls.append("bad")
        raise RuntimeError("boom")

    def good():
        calls.append("good")
        return "ok"

    api._warm_pass(cache, [(("a",), bad), (("b",), good)], logging.getLogger("test"))
    assert calls == ["bad", "good"]
    assert cache.get(("b",), lambda: "miss").body == b"ok"


def test_warm_entries_cover_cached_routes():
    def fake_call(builder, day, **extra):
        return {"history": []}

    from datetime import datetime

    from inves_cog.clock import FrozenClock

    entries = api._warm_entries(fake_call, FrozenClock(datetime.fromisoformat("2026-11-06T12:00:00+00:00")))
    keys = {k[1] if len(k) > 1 else k[0] for k, _ in entries}
    assert len(entries) == 6
    assert {"page_brief_market", "page_brief_stocks", "page_brief_account", "page_brief_trust", "page_market"} <= keys
    assert any(k == ("barometer",) for k, _ in entries)
