# M2 v2 首次红灯证据

基线：c0944bb，尚无本模块实现。

命令：`.venv/bin/python -m pytest tests/m2 -m phase1_blocking --harness-pending=/private/tmp/m2-red-pending.txt -q --tb=short`。临时 pending 副本只移除 M2 blocking 登记以显示真实失败；仓库 pending 棘轮保留。

```text
FFFFFFFFFFFFFFF                                                          [100%]
=================================== FAILURES ===================================
_____________________________ test_revenue_tag_gap _____________________________
tests/m2/test_fundamentals.py:33: in test_revenue_tag_gap
    legacy = extract(facts, extractor='legacy')
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/m2/test_fundamentals.py:25: in extract
    from inves_cog.ingest.fundamentals.extractors import extract_state
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
_________________________ test_q4_derived_from_annual __________________________
tests/m2/test_fundamentals.py:43: in test_q4_derived_from_annual
    from inves_cog.ingest.fundamentals.extractors import derive_quarters
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
____________________________ test_companyfacts_lag _____________________________
tests/m2/test_fundamentals.py:62: in test_companyfacts_lag
    plain = extract(filings=filings, as_of=date(2026, 10, 12))
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/m2/test_fundamentals.py:25: in extract
    from inves_cog.ingest.fundamentals.extractors import extract_state
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
_________________________ test_stale_fundamentals_code _________________________
tests/m2/test_fundamentals.py:78: in test_stale_fundamentals_code
    assert 'stale_fundamentals' not in extract(as_of=period + timedelta(days=180)).health_codes
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/m2/test_fundamentals.py:25: in extract
    from inves_cog.ingest.fundamentals.extractors import extract_state
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
__________________________ test_gross_margin_derived ___________________________
tests/m2/test_fundamentals.py:85: in test_gross_margin_derived
    state = extract(facts)
            ^^^^^^^^^^^^^^
tests/m2/test_fundamentals.py:25: in extract
    from inves_cog.ingest.fundamentals.extractors import extract_state
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
_____________________________ test_ni_tag_fallback _____________________________
tests/m2/test_fundamentals.py:96: in test_ni_tag_fallback
    assert extract(facts).values['ni_ttm'] == 40
           ^^^^^^^^^^^^^^
tests/m2/test_fundamentals.py:25: in extract
    from inves_cog.ingest.fundamentals.extractors import extract_state
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.extractors'
____________________________ test_industry_basis_na ____________________________
tests/m2/test_fundamentals.py:103: in test_industry_basis_na
    from inves_cog.ingest.fundamentals.health import health_row
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.health'
______________________________ test_fin_state_pit ______________________________
tests/m2/test_fundamentals.py:112: in test_fin_state_pit
    from inves_cog.ingest.fundamentals.state import StateStore
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.state'
_________________________ test_extractor_fixed_toggles _________________________
tests/m2/test_fundamentals.py:127: in test_extractor_fixed_toggles
    settings = yaml.safe_load((ROOT / 'config/params/p-2026.10/m2.yaml').read_text())['m2']
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Documents/Codex/2026-10-13/new-chat-2/work/m0-python/cpython-3.11.17-macos-aarch64-none/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Documents/Codex/2026-10-13/new-chat-2/work/m0-python/cpython-3.11.17-macos-aarch64-none/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/Users/xuqingsong/workspace/inves-cog/config/params/p-2026.10/m2.yaml'
___________________________ test_segment_extraction ____________________________
tests/m2/test_fundamentals.py:147: in test_segment_extraction
    from inves_cog.ingest.fundamentals.segments import parse_segments, segment_sum_ok
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.segments'
_____________________________ test_segment_recast ______________________________
tests/m2/test_fundamentals.py:161: in test_segment_recast
    from inves_cog.ingest.fundamentals.segments import apply_recast
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.segments'
_________________________ test_segment_mapping_pending _________________________
tests/m2/test_fundamentals.py:173: in test_segment_mapping_pending
    from inves_cog.ingest.fundamentals.mapping import MappingQueue
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.mapping'
__________________________ test_consensus_derived_pit __________________________
tests/m2/test_fundamentals.py:195: in test_consensus_derived_pit
    from inves_cog.ingest.fundamentals.consensus import derive_consensus
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.consensus'
_______________________ test_consensus_import_idempotent _______________________
tests/m2/test_fundamentals.py:218: in test_consensus_import_idempotent
    from inves_cog.ingest.fundamentals.consensus import ConsensusStore, import_muse_exports, read_copy_blocks
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.consensus'
_____________________________ test_health_contract _____________________________
tests/m2/test_fundamentals.py:235: in test_health_contract
    from inves_cog.ingest.fundamentals.health import health_row
E   ModuleNotFoundError: No module named 'inves_cog.ingest.fundamentals.health'
=========================== short test summary info ============================
FAILED tests/m2/test_fundamentals.py::test_revenue_tag_gap - ModuleNotFoundEr...
FAILED tests/m2/test_fundamentals.py::test_q4_derived_from_annual - ModuleNot...
FAILED tests/m2/test_fundamentals.py::test_companyfacts_lag - ModuleNotFoundE...
FAILED tests/m2/test_fundamentals.py::test_stale_fundamentals_code - ModuleNo...
FAILED tests/m2/test_fundamentals.py::test_gross_margin_derived - ModuleNotFo...
FAILED tests/m2/test_fundamentals.py::test_ni_tag_fallback - ModuleNotFoundEr...
FAILED tests/m2/test_fundamentals.py::test_industry_basis_na - ModuleNotFound...
FAILED tests/m2/test_fundamentals.py::test_fin_state_pit - ModuleNotFoundErro...
FAILED tests/m2/test_fundamentals.py::test_extractor_fixed_toggles - FileNotF...
FAILED tests/m2/test_fundamentals.py::test_segment_extraction - ModuleNotFoun...
FAILED tests/m2/test_fundamentals.py::test_segment_recast - ModuleNotFoundErr...
FAILED tests/m2/test_fundamentals.py::test_segment_mapping_pending - ModuleNo...
FAILED tests/m2/test_fundamentals.py::test_consensus_derived_pit - ModuleNotF...
FAILED tests/m2/test_fundamentals.py::test_consensus_import_idempotent - Modu...
FAILED tests/m2/test_fundamentals.py::test_health_contract - ModuleNotFoundEr...
15 failed, 2 deselected in 0.14s
```

所有新增 companyfacts、XBRL、CSV 和录音均为合成开发输入，不是 Muse 的真实输出。真实对照 replay 保留“等待 R7（Muse 导出）”。
