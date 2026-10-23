"""B-047: read graph relations, derive citation status, and grade exposure.

Fixtures use fictional tickers and fictional filing text. Nothing is written back
to graph.relations. G1 and G2 use the disposable database started by phase1.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.llm.client import Client
from inves_cog.overlay.rules import generate_overlay
from inves_cog.perception.attribution.chain import _candidates, _fill_ticker_exposure, _graph_context, _stamp_scope
from inves_cog.perception.attribution.graph_context import attach_graph
from inves_cog.perception.attribution.morning import _load
from inves_cog.perception.attribution.propose import (
    PROMPT_VERSION,
    candidate_instruction,
    propose_candidates,
    read_candidates,
)
from inves_cog.perception.attribution.replay_window import _event, slot_moment
from inves_cog.perception.attribution.report import explanation_report
from inves_cog.perception.attribution.snapshot import _row_event, m8_provider, read_replay_snapshot, read_snapshot
from tests.m8.test_attribution import _disposable_database
from tests.m8.test_b039_run import Pages
from tests.m8.test_b044 import _request_config, _send

pytestmark = pytest.mark.phase1_blocking

DAY = "2026-10-16"
CUTOFF = slot_moment(DAY, "attribution_candidates")
QUOTE = "AAA supplies storage units to the fictional buyer."
FLOW = "Demand shifts through the fictional channel."
TEXT = QUOTE + " " + FLOW
BASIS = "SEC原文引文核对"
DISK = "product:b047-disk"
INFO = "info-aaa"


class _Watch:
    """Record statements. The graph read must not write."""

    def __init__(self, connection):
        self.connection = connection
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append(" ".join(statement.split()))
        return self.connection.execute(statement, params)


class _Reply:
    def __init__(self, candidates):
        self.candidates = candidates

    def call(self, task, payload):
        assert task == "anomaly_candidates"
        return {"candidates": self.candidates}


def test_replay_without_a_database_keeps_edges_the_caller_supplied():
    anomaly = {
        "anomaly_id": "b047-none",
        "trade_date": DAY,
        "members": [{"ticker": "AAA"}],
        "edges": [{"relation_id": "kept"}],
    }
    assert attach_graph(None, [anomaly], CUTOFF) == [anomaly]
    assert anomaly["edges"] == [{"relation_id": "kept"}]


def test_g1_live_and_replay_keep_one_normalized_neighbor():
    _with_admin(_seed_visibility, _assert_visibility)


def test_g2_citation_status_is_derived_and_rows_stay_unchanged():
    _with_admin(_seed_citations, _assert_citations)


def test_g3_exposure_agrees_across_scope_status_and_both_snapshots():
    _with_admin(_seed_citations, _assert_exposure)


def test_g4_direct_exposure_turns_cooling_on_through_the_provider():
    _with_admin(_seed_citations, _assert_cooling)


def test_g5_system_message_matches_the_updated_instruction():
    instruction = Path(__file__).resolve().parents[2] / "docs/phase1/contracts/m8-candidate-prompt-v4/instruction.txt"
    file_bytes = instruction.read_bytes()
    assert candidate_instruction().encode("utf-8") == file_bytes
    assert b"PREFER this as the LAST link" in file_bytes
    assert PROMPT_VERSION == "evidence-bridge-v4.1-links"
    box = []
    client = Client.from_environment(_request_config(), send=_send(box))
    client.call("anomaly_candidates", {})
    assert box[-1]["messages"][0]["content"].encode("utf-8") == file_bytes


def test_g6_one_bad_candidate_is_dropped_and_all_bad_still_degrades():
    items = [{"info_id": INFO}]
    good = (_output("供给", [_hypothesis("AAA")], "AAA"), _output("需求", [_hypothesis("AAA")], "AAA"))
    bad = _output("竞争", [_hypothesis("AAA")], "AAA")
    bad["control_baskets"] = "peers"
    kept = propose_candidates(_anomaly("g6"), items, [], _Reply([*good, bad]), {"AAA"})
    assert sum(1 for row in kept if row.get("link_checked")) == 2
    assert read_candidates.rejections == [{"reason": "candidate_format_rejected", "field": "control_baskets"}]
    broken = [_output(name, [_hypothesis("AAA")], "AAA") for name in ("供给", "需求", "竞争")]
    for row in broken:
        row["control_baskets"] = "peers"
    with pytest.raises(ValueError, match="^结构不合格$"):
        read_candidates({"candidates": broken})
    assert len(read_candidates.rejections) == 3
    _rows, note = _candidates(_anomaly("g6-all"), items, _Reply(broken), as_of=CUTOFF)
    assert note == "结构不合格"
    assert len(read_candidates.rejections) == 3


def test_g7_forged_mismatched_and_candidate_links_are_not_observed_exposure():
    observed = _neighbor("rel-real", "业务关系", "观察到", "AAA")
    forged = _graded("forged", "供给", [_known("rel-forged", "disk", "AAA")], [observed], "AAA")
    assert forged["scope"] == []
    assert forged["kept_relations"] == []
    mismatch = _graded("mismatch", "供给", [_known("rel-real", "other", "AAA")], [observed], "AAA")
    assert mismatch["scope"] == []
    assert mismatch["kept_relations"] == []
    candidate = _neighbor("rel-maybe", "业务关系", "候选", "AAA")
    only_link = _graded("candidate-link", "供给", [_known("rel-maybe", "disk", "AAA")], [candidate], "AAA")
    assert only_link["scope"] == []
    walked = _graded(
        "candidate-walk",
        "供给",
        [_hypothesis("AAA"), _known("rel-maybe", "disk", "AAA")],
        [candidate],
        "AAA",
    )
    assert walked["scope"] == ["概念关联"]
    assert walked["kept_relations"] == []


def _assert_visibility(admin):
    watched = _Watch(admin)
    loaded = _load(watched, CUTOFF, DAY)
    assert loaded["anomalies"]
    live = _graph_context(loaded["anomalies"][0], CUTOFF)["neighbors"]
    replay_anomaly = {"anomaly_id": "b047-replay", "members": [{"ticker": "AAA"}], "universe": "pool"}
    attach_graph(watched, [replay_anomaly], CUTOFF)
    replay = _graph_context(replay_anomaly, CUTOFF)["neighbors"]
    _assert_selects(watched)
    for neighbors in (live, replay):
        assert [row["relation_id"] for row in neighbors] == ["b047-g1-visible"]
        row = neighbors[0]
        assert row["to_entity"] == "AAA"
        assert row["from_entity"] == DISK
        assert row["status"] == "观察到"
        assert "ticker:" not in row["from_entity"]
        assert "ticker:" not in row["to_entity"]


def _assert_citations(admin):
    before = _table(admin)
    watched = _Watch(admin)
    anomaly = {"anomaly_id": "b047-g2", "members": [{"ticker": "AAA"}], "universe": "pool"}
    attach_graph(watched, [anomaly], CUTOFF)
    _assert_selects(watched)
    neighbors = {row["relation_id"]: row for row in _graph_context(anomaly, CUTOFF)["neighbors"]}
    assert neighbors["b047-biz"]["status"] == "观察到"
    assert neighbors["b047-biz"]["status_basis"] == BASIS
    assert neighbors["b047-flow"]["status"] == "观察到"
    assert neighbors["b047-flow"]["status_basis"] == BASIS
    assert neighbors["b047-story"]["status"] == "候选"
    assert "status_basis" not in neighbors["b047-story"]
    assert neighbors["b047-miss"]["status"] == "候选"
    assert neighbors["b047-late"]["status"] == "候选"
    assert neighbors["b047-manual"]["status"] == "观察到"
    assert "status_basis" not in neighbors["b047-manual"]
    assert _table(admin) == before


def _assert_exposure(admin):
    neighbors = _projected(admin)
    biz = neighbors["b047-biz"]
    flow = neighbors["b047-flow"]
    story = neighbors["b047-story"]
    direct = _graded("direct", "供给", [_known(biz["relation_id"], DISK, "AAA")], [biz], "AAA")
    indirect = _graded("indirect", "供给", [_known(flow["relation_id"], DISK, "AAA")], [flow], "AAA")
    concept = _graded("concept", "供给", [_hypothesis("AAA")], [story], "AAA")
    resonance = _graded("resonance", "供给", [_hypothesis("CCC")], [], "CCC")
    multiple = _graded("multiple", "估值倍数", [_known(biz["relation_id"], DISK, "AAA")], [biz], "AAA")
    assert direct["scope"] == ["直接"]
    assert indirect["scope"] == ["间接"]
    assert concept["scope"] == ["概念关联"]
    assert resonance["scope"] == ["纯共振"]
    assert multiple["scope"] == ["概念关联"]
    assert multiple["ticker_status"] == [
        {"ticker": "AAA", "n_code": "N2", "mechanism": "估值倍数", "exposure": "概念关联"}
    ]
    for graded in (direct, indirect, concept, resonance):
        assert graded["ticker_status"] == []
    for graded in (direct, indirect, concept, resonance, multiple):
        assert graded["affected"] == graded["scope"]
        assert graded["live"] == graded["scope"]
        assert graded["replay"] == graded["scope"]


def _assert_cooling(admin):
    neighbors = _projected(admin)
    biz = neighbors["b047-biz"]
    direct = _graded("cool-direct", "供给", [_known(biz["relation_id"], DISK, "AAA")], [biz], "AAA")
    concept_neighbor = _neighbor("rel-bbb", "市场叙事", "候选", "BBB")
    concept = _graded("cool-concept", "供给", [_hypothesis("BBB")], [concept_neighbor], "BBB")
    assert direct["scope"] == ["直接"]
    assert concept["scope"] == ["概念关联"]
    pages = _snapshot("stage_completion", [direct["live_event"], concept["live_event"]])
    loaded = m8_provider(pages)(DAY, CUTOFF)
    overlay = generate_overlay(loaded["events"], clock=FrozenClock(CUTOFF), version=1, source_asof=CUTOFF)
    assert overlay["tickers"]["AAA"]["cooling_status"] == "on"
    assert overlay["tickers"]["BBB"]["cooling_status"] == "off"


def _graded(name, mechanism, links, neighbors, ticker):
    anomaly = _anomaly(name, ticker)
    items = [{"info_id": INFO}]
    universe = {"AAA", "BBB", "CCC"}
    rows = propose_candidates(anomaly, items, neighbors, _Reply([_output(mechanism, links, ticker)]), universe)
    scored = [row for row in rows if row.get("scored")]
    assert len(scored) == 1
    scored[0]["score"] = 0.8
    report = explanation_report(anomaly, None, rows, [], neighbors=neighbors)
    _stamp_scope(rows, report.get("scope"))
    codes = _fill_ticker_exposure(report.get("ticker_status"), report.get("scope"))
    scope = [row["exposure"] for row in report["scope"] if row.get("ticker") == ticker]
    affected = [
        item.get("exposure") for row in scored for item in row.get("affected") or [] if item.get("ticker") == ticker
    ]
    live_event, _reason = _row_event(_live_row(anomaly, mechanism, scored, codes, report), CUTOFF, DAY)
    replay_event, gaps = _event(_bundle(anomaly, mechanism, rows, report, codes), CUTOFF)
    assert "deadline_outcome" not in gaps
    return {
        "scope": scope,
        "affected": affected,
        "ticker_status": codes,
        "kept_relations": [
            link.get("relation_id")
            for row in scored
            for link in row.get("links") or []
            if link.get("kind") == "已有关系"
        ],
        "live": _read_exposure(_snapshot("stage_completion", [live_event]), ticker),
        "replay": _read_exposure(_snapshot("historical_backfill", [replay_event]), ticker),
        "live_event": live_event,
    }


def _live_row(anomaly, mechanism, scored, codes, report):
    return {
        "event_id": f"evt-{anomaly['anomaly_id']}",
        "anomaly_id": anomaly["anomaly_id"],
        "history": [{"at": CUTOFF.isoformat(), "new": "基本面核查中", "evidence_ids": []}],
        "generated_at": CUTOFF,
        "mechanism": mechanism,
        "deadline_outcome": "支持",
        "tickers": codes,
        "candidates": scored,
        "tracks": [],
        "claims": [],
        "report": report,
        "systemic_event_tag": None,
    }


def _bundle(anomaly, mechanism, rows, report, codes):
    bundle = {
        "anomaly_id": anomaly["anomaly_id"],
        "report": report,
        "candidates": rows,
        "linkage": {
            "event_id": f"evt-{anomaly['anomaly_id']}",
            "lifecycle": "基本面核查中",
            "mechanism": mechanism,
            "deadline_outcome": "支持",
        },
    }
    if codes:
        bundle["ticker_status"] = codes
    return bundle


def _snapshot(kind, events):
    pages = Pages()
    pages.snapshots.append(
        {
            "snapshot_id": 1,
            "trade_date": DAY,
            "snapshot_generated_at": CUTOFF,
            "source_asof": CUTOFF,
            "status": "complete",
            "kind": kind,
            "jobs": [],
            "events": events,
            "missing": {"stages": [], "events": [], "fields": {}},
        }
    )
    return pages


def _read_exposure(pages, ticker):
    if pages.snapshots[0]["kind"] == "historical_backfill":
        found = read_replay_snapshot(pages, DAY)
    else:
        found = read_snapshot(pages, DAY, CUTOFF)
    exposures = []
    for event in found["events"]:
        for affected in event.get("affected") or []:
            if affected.get("ticker") == ticker:
                exposures.append(affected.get("exposure"))
    return exposures


def _output(mechanism, links, ticker):
    return {
        "mechanism": mechanism,
        "info_ids": [INFO],
        "affected": [{"ticker": ticker, "direction": "down"}],
        "chain": [{"entity_id": ticker}],
        "control_baskets": ["peers"],
        "direction": "down",
        "links": links,
        "竞争解释": [],
        "反证条件": "下一季收入没有下降",
        "证伪预测": [{"ticker": ticker, "control_basket": "peers", "direction": "down", "window": "下一季"}],
    }


def _known(relation_id, origin, ticker):
    return {"kind": "已有关系", "from": origin, "to": ticker, "relation_id": relation_id}


def _hypothesis(ticker):
    return {
        "kind": "声明的假设",
        "from": "news",
        "to": ticker,
        "hypothesis": "供应变化影响该标的",
        "hypothesis_type": "暴露关系",
        "falsify": {"metric": "收入", "direction": "下降", "window": "下一季"},
    }


def _neighbor(relation_id, connection_type, status, ticker):
    return {
        "relation_id": relation_id,
        "from_entity": "disk",
        "to_entity": ticker,
        "connection_type": connection_type,
        "mechanism": "供给",
        "direction": "down",
        "status": status,
        "first_discovered_at": (CUTOFF - timedelta(days=1)).isoformat(),
        "source_info_ids": ["info-aaa"],
    }


def _anomaly(name, ticker="AAA"):
    return {
        "anomaly_id": f"b047-{name}",
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "pool",
        "members": [{"ticker": ticker}],
        "started_at": CUTOFF,
    }


def _projected(connection):
    anomaly = {"anomaly_id": "b047-projected", "members": [{"ticker": "AAA"}], "universe": "pool"}
    attach_graph(connection, [anomaly], CUTOFF)
    return {row["relation_id"]: row for row in _graph_context(anomaly, CUTOFF)["neighbors"]}


def _with_admin(seed, check):
    import psycopg
    from psycopg.rows import dict_row

    host = _disposable_database()
    admin = psycopg.connect(f"postgresql://inves_cog_admin@{host}/inves_cog", row_factory=dict_row, autocommit=True)
    try:
        _cleanup(admin)
        seed(admin)
        check(admin)
    finally:
        _cleanup(admin)
        admin.close()


def _seed_visibility(connection):
    _entity(connection, "ticker:AAA", "company", "AAA", "AAA")
    _entity(connection, DISK, "product", "disk", None)
    _relation(connection, "b047-g1-late", "候选", CUTOFF + timedelta(days=1), None, {})
    _relation(connection, "b047-g1-rejected", "驳回", CUTOFF - timedelta(days=2), None, {})
    _relation(connection, "b047-g1-visible", "观察到", CUTOFF - timedelta(days=1), None, {})
    connection.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
            direction, data_quality, coverage, amplification, type_candidates_prelim, status,
            universe, params_version, generated_at
        ) VALUES (
            'b047-g1', %s, 'close', '{}', 'L1', 'alert', '{}', %s::jsonb, 'down',
            %s::jsonb, %s::jsonb, %s::jsonb, '{}',
            '已发现·原因未明', 'pool', 'p-2026.10', %s
        )
        """,
        (DAY, json.dumps([{"ticker": "AAA"}]), "{}", "{}", "{}", CUTOFF),
    )


def _seed_citations(connection):
    _entity(connection, "ticker:AAA", "company", "AAA", "AAA")
    _entity(connection, DISK, "product", "disk", None)
    early = CUTOFF - timedelta(days=1)
    late = CUTOFF + timedelta(hours=1)
    _text(connection, "b047-ok", TEXT, early)
    _text(connection, "b047-miss", "Unrelated fictional filing text.", early)
    _text(connection, "b047-late", TEXT, late)
    spaced = "AAA\u3000supplies  storage units to the fictional buyer."
    flowed = "Demand  shifts through the fictional channel."
    _relation(connection, "b047-biz", "候选", early, None, _evidence("b047-ok", spaced), "业务关系")
    _relation(connection, "b047-flow", "候选", early, None, _evidence("b047-ok", flowed), "经营传导")
    _relation(connection, "b047-story", "候选", early, None, _evidence("b047-ok", QUOTE), "市场叙事")
    _relation(connection, "b047-miss", "候选", early, None, _evidence("b047-miss", QUOTE), "业务关系")
    _relation(connection, "b047-late", "候选", early, None, _evidence("b047-late", QUOTE), "业务关系")
    _relation(connection, "b047-manual", "观察到", early, None, _evidence("b047-ok", QUOTE), "业务关系")


def _entity(connection, entity_id, kind, name, ticker):
    connection.execute(
        """
        INSERT INTO graph.entities (entity_id, kind, name, ticker)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (entity_id) DO NOTHING
        """,
        (entity_id, kind, name, ticker),
    )


def _relation(connection, relation_id, status, discovered, reviewed, evidence, connection_type="业务关系"):
    connection.execute(
        """
        INSERT INTO graph.relations (
            relation_id, from_entity, to_entity, connection_type, mechanism, status,
            evidence, first_discovered_at, reviewed_at, drafted_by
        ) VALUES (%s, %s, 'ticker:AAA', %s, '供给', %s, %s::jsonb, %s, %s, 'b047-fixture')
        """,
        (relation_id, DISK, connection_type, status, json.dumps(evidence), discovered, reviewed),
    )


def _text(connection, accession, text, fetched_at):
    connection.execute(
        """
        INSERT INTO graph.source_texts (
            ticker, accession, section, text, char_start, char_end, fetched_at, source_url, source_sha256
        ) VALUES ('AAA', %s, 'item1', %s, 0, %s, %s, 'https://fixture.invalid/aaa', 'b047')
        """,
        (accession, text, len(text), fetched_at),
    )


def _evidence(accession, quote):
    return {"citation": {"accession": accession, "quote": quote, "section": "item1"}}


def _table(connection):
    relations = connection.execute(
        "SELECT * FROM graph.relations WHERE relation_id LIKE 'b047-%' ORDER BY relation_id"
    ).fetchall()
    texts = connection.execute(
        "SELECT * FROM graph.source_texts WHERE accession LIKE 'b047-%' ORDER BY accession, char_start"
    ).fetchall()
    return [_plain(row) for row in relations], [_plain(row) for row in texts]


def _plain(row):
    plain = {}
    for key, value in dict(row).items():
        plain[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return plain


def _assert_selects(watched):
    assert watched.statements
    for statement in watched.statements:
        assert statement.upper().startswith("SELECT")


def _cleanup(connection):
    connection.execute("DELETE FROM graph.relations WHERE relation_id LIKE 'b047-%'")
    connection.execute("DELETE FROM graph.source_texts WHERE accession LIKE 'b047-%'")
    connection.execute(
        """
        DELETE FROM graph.entities
        WHERE entity_id IN ('ticker:AAA', %s)
          AND NOT EXISTS (
            SELECT 1 FROM graph.relations
            WHERE from_entity = graph.entities.entity_id OR to_entity = graph.entities.entity_id
          )
        """,
        (DISK,),
    )
    connection.execute("DELETE FROM perception.anomalies WHERE anomaly_id = 'b047-g1'")
