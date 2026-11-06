"""Page warm-up: refreshes only recently-requested keys, unconditionally."""

import logging

import inves_cog.web.api as api

KEY = ("brief", "page_brief_market", None, frozenset())


def test_warm_pass_skips_never_accessed_keys():
    cache = api._PageCache()
    built = []

    def produce():
        built.append(1)
        return "<html>warm</html>"

    api._warm_pass(cache, [(KEY, produce)], logging.getLogger("test"))
    assert built == []
    assert not cache._entries


def test_warm_pass_refreshes_after_user_access():
    cache = api._PageCache()
    built = []

    def produce():
        built.append(1)
        return f"<html>v{len(built)}</html>"

    cache.get(KEY, produce)  # user request -> renders once, marks access
    api._warm_pass(cache, [(KEY, produce)], logging.getLogger("test"))
    api._warm_pass(cache, [(KEY, produce)], logging.getLogger("test"))
    assert built == [1, 1, 1]  # refresh re-renders even while the entry is fresh
    assert cache.get(KEY, lambda: "miss").body == b"<html>v3</html>"


def test_warm_pass_stops_when_access_ages_out():
    now = [1000.0]
    cache = api._PageCache(now=lambda: now[0])
    built = []
    cache.get(KEY, lambda: built.append(1) or "x")
    api._warm_pass(cache, [(KEY, lambda: built.append(1) or "w")], logging.getLogger("test"))
    now[0] += cache._ACCESS_WINDOW + 1
    api._warm_pass(cache, [(KEY, lambda: built.append(1) or "w")], logging.getLogger("test"))
    assert built == [1, 1]  # second pass skipped — access aged out


def test_warm_pass_survives_failures():
    cache = api._PageCache()
    calls = []
    cache.get(("a",), lambda: "seed")

    def bad():
        calls.append("bad")
        raise RuntimeError("boom")

    def good():
        calls.append("good")
        return "ok"

    api._warm_pass(cache, [(("a",), bad), (("a",), good)], logging.getLogger("test"))
    assert calls == ["bad", "good"]
    assert cache.get(("a",), lambda: "miss").body == b"ok"


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
