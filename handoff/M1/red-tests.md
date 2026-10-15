# M1 v2 首次红灯证据

基线：3dfb30a，尚无本模块实现。

命令：`.venv/bin/python -m pytest tests/m1 -m phase1_blocking --harness-pending=/private/tmp/m1-red-pending.txt -q --tb=short`。临时 pending 副本仅移除 M1 的 blocking 登记，以显示真实失败；仓库 pending 保留棘轮规则。

```text
FFFFFFFFFFFFFF                                                           [100%]
=================================== FAILURES ===================================
___________________________ test_bar_window_to_20et ____________________________
tests/m1/test_market_info.py:41: in test_bar_window_to_20et
    from inves_cog.ingest.market import MarketCollector, market_window, schedule_times
E   ModuleNotFoundError: No module named 'inves_cog.ingest.market'
__________________________ test_bar_window_from_04et ___________________________
tests/m1/test_market_info.py:85: in test_bar_window_from_04et
    from inves_cog.ingest.market import market_window, bar_session, schedule_times
E   ModuleNotFoundError: No module named 'inves_cog.ingest.market'
______________________ test_post_close_null_when_no_trade ______________________
tests/m1/test_market_info.py:97: in test_post_close_null_when_no_trade
    from inves_cog.ingest.market import post_close, split_factors
E   ModuleNotFoundError: No module named 'inves_cog.ingest.market'
___________________________ test_wide_universe_rules ___________________________
tests/m1/test_market_info.py:108: in test_wide_universe_rules
    from inves_cog.ingest.universe import build_universe, daily_liquidity
E   ModuleNotFoundError: No module named 'inves_cog.ingest.universe'
__________________________ test_news_dedupe_and_times __________________________
tests/m1/test_market_info.py:125: in test_news_dedupe_and_times
    from inves_cog.ingest.info import InfoStore, make_item, source_root
E   ModuleNotFoundError: No module named 'inves_cog.ingest.info'
__________________________ test_earnings_reaction_day __________________________
tests/m1/test_market_info.py:150: in test_earnings_reaction_day
    from inves_cog.ingest.sec import earnings_event, parse_acceptance_et
E   ModuleNotFoundError: No module named 'inves_cog.ingest.sec'
_________________________ test_earnings_fallback_flag __________________________
tests/m1/test_market_info.py:162: in test_earnings_fallback_flag
    from inves_cog.ingest.sec import earnings_fallback
E   ModuleNotFoundError: No module named 'inves_cog.ingest.sec'
___________________________ test_form4_parse_code_p ____________________________
tests/m1/test_market_info.py:170: in test_form4_parse_code_p
    from inves_cog.ingest.sec import parse_form4
E   ModuleNotFoundError: No module named 'inves_cog.ingest.sec'
______________________________ test_app_rank_jump ______________________________
tests/m1/test_market_info.py:181: in test_app_rank_jump
    from inves_cog.ingest.signals import rank_jumps
E   ModuleNotFoundError: No module named 'inves_cog.ingest.signals'
________________________ test_trends_unavailable_marked ________________________
tests/m1/test_market_info.py:190: in test_trends_unavailable_marked
    from inves_cog.ingest.signals import trend_event, collect_trends
E   ModuleNotFoundError: No module named 'inves_cog.ingest.signals'
__________________________ test_source_level_mapping ___________________________
tests/m1/test_market_info.py:216: in test_source_level_mapping
    from inves_cog.ingest.info import source_level
E   ModuleNotFoundError: No module named 'inves_cog.ingest.info'
___________________________ test_info_item_contract ____________________________
tests/m1/test_market_info.py:229: in test_info_item_contract
    from inves_cog.ingest.info import make_item, InfoStore, enrich
E   ModuleNotFoundError: No module named 'inves_cog.ingest.info'
_________________________ test_info_fields_extraction __________________________
tests/m1/test_market_info.py:264: in test_info_fields_extraction
    from inves_cog.ingest.info import enrich, make_item
E   ModuleNotFoundError: No module named 'inves_cog.ingest.info'
_____________________ test_llm_extraction_failure_degrades _____________________
tests/m1/test_market_info.py:277: in test_llm_extraction_failure_degrades
    from inves_cog.ingest.info import enrich, make_item, InfoStore
E   ModuleNotFoundError: No module named 'inves_cog.ingest.info'
=========================== short test summary info ============================
FAILED tests/m1/test_market_info.py::test_bar_window_to_20et - ModuleNotFound...
FAILED tests/m1/test_market_info.py::test_bar_window_from_04et - ModuleNotFou...
FAILED tests/m1/test_market_info.py::test_post_close_null_when_no_trade - Mod...
FAILED tests/m1/test_market_info.py::test_wide_universe_rules - ModuleNotFoun...
FAILED tests/m1/test_market_info.py::test_news_dedupe_and_times - ModuleNotFo...
FAILED tests/m1/test_market_info.py::test_earnings_reaction_day - ModuleNotFo...
FAILED tests/m1/test_market_info.py::test_earnings_fallback_flag - ModuleNotF...
FAILED tests/m1/test_market_info.py::test_form4_parse_code_p - ModuleNotFound...
FAILED tests/m1/test_market_info.py::test_app_rank_jump - ModuleNotFoundError...
FAILED tests/m1/test_market_info.py::test_trends_unavailable_marked - ModuleN...
FAILED tests/m1/test_market_info.py::test_source_level_mapping - ModuleNotFou...
FAILED tests/m1/test_market_info.py::test_info_item_contract - ModuleNotFound...
FAILED tests/m1/test_market_info.py::test_info_fields_extraction - ModuleNotF...
FAILED tests/m1/test_market_info.py::test_llm_extraction_failure_degrades - M...
14 failed, 1 deselected in 0.11s
```

合成 Form 4 用于开发测试；第 7 节要求的真实 XML 样例以及 Q-M1-8 的三个真实 SEC 时间核对尚未到位，不能把本文件当真实采集证据。
