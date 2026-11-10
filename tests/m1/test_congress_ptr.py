import io
import json
import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/congress"


@pytest.mark.phase1_blocking
def test_parse_index_text_keeps_only_ptr():
    from inves_cog.ingest.congress import parse_index_text

    text = (
        "Prefix\tLast\tFirst\tSuffix\tFilingType\tStateDst\tYear\tFilingDate\tDocID\n"
        "Hon.\tAderholt\tRobert B.\t\tP\tAL04\t2025\t9/10/2025\t20032062\n"
        "\tAbel\tWilliam P.\t\tC\tTX31\t2025\t10/12/2025\t10072640\n"
        "\tSmith\tJane\t\tD\tCA01\t2025\t3/1/2025\t20030001\n"
    )
    rows = parse_index_text(text)
    assert rows == [
        {"doc_id": "20032062", "member": "Robert B. Aderholt", "state_dst": "AL04", "filing_date": "2025-09-10"}
    ]


@pytest.mark.phase1_blocking
def test_parse_ptr_electronic_fixture():
    from inves_cog.ingest.congress import parse_ptr

    parsed = parse_ptr((FIXTURES / "20032062.pdf").read_bytes())
    assert parsed["member"] == "Hon. Robert B. Aderholt"
    assert parsed["state_dst"] == "AL04"
    assert parsed["doc_id"] == "20032062"
    assert parsed["transactions"] == [
        {
            "owner": None,
            "asset": "GSK plc American Depositary Shares",
            "ticker": "GSK",
            "cusip": None,
            "txn_type": "S",
            "txn_date": "2025-07-28",
            "notification_date": "2025-08-11",
            "amount_low": 1001,
            "amount_high": 15000,
        }
    ]


@pytest.mark.phase1_blocking
def test_parse_ptr_multi_transaction_fixture():
    from inves_cog.ingest.congress import parse_ptr

    parsed = parse_ptr((FIXTURES / "20026537.pdf").read_bytes())
    assert parsed["member"] == "Hon. Richard W. Allen"
    assert len(parsed["transactions"]) == 4
    rol = parsed["transactions"][0]
    assert rol["ticker"] == "ROL" and rol["txn_type"] == "P"
    assert rol["amount_low"] == 15001 and rol["amount_high"] == 50000
    cusip_txn = parsed["transactions"][1]
    assert cusip_txn["cusip"] == "91282CJP7" and cusip_txn["ticker"] is None


@pytest.mark.phase1_blocking
def test_parse_ptr_oversize_and_timeout_skip():
    from inves_cog.ingest.congress import MAX_PDF_BYTES, parse_ptr

    assert parse_ptr(b"%PDF" + b"x" * (MAX_PDF_BYTES + 1)) is None
    import time

    assert parse_ptr((FIXTURES / "20032062.pdf").read_bytes(), _deadline=time.monotonic() - 1) is None


@pytest.mark.phase1_blocking
def test_parse_ptr_scanned_returns_none():
    from inves_cog.ingest.congress import parse_ptr

    assert parse_ptr((FIXTURES / "8220768.pdf").read_bytes()) is None


@pytest.mark.phase1_blocking
def test_collect_index_enqueues_pending_rows():
    from inves_cog.ingest.congress import collect_index

    text = (
        "Prefix\tLast\tFirst\tSuffix\tFilingType\tStateDst\tYear\tFilingDate\tDocID\n"
        "Hon.\tAderholt\tRobert B.\t\tP\tAL04\t2025\t9/10/2025\t20032062\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2025FD.txt", text)

    class HTTP:
        def get(self, url):
            assert "2025FD.zip" in url
            return buf.getvalue()

    inserts = []

    class Cur:
        rowcount = 1

    class Conn:
        def execute(self, sql, params=None):
            inserts.append(params)
            return Cur()

    out = collect_index(Conn(), HTTP(), 2025)
    assert out == {"indexed": 1, "enqueued": 1}
    assert inserts[0][0] == "20032062" and inserts[0][1] == "2025-09-10"


@pytest.mark.phase1_blocking
def test_collect_pending_backoff_on_failure():
    from inves_cog.ingest.congress import collect_pending

    updates = []
    rows = [
        {"doc_id": "a", "source_url": "u1", "filing_date": "2025-01-01"},
        {"doc_id": "b", "source_url": "u2", "filing_date": "2025-01-02"},
    ]

    class Res:
        def fetchall(self):
            return rows

    class Conn:
        def execute(self, sql, params=None):
            if sql.strip().startswith("SELECT"):
                return Res()
            updates.append((sql.strip()[:30], params))
            return Res()

    class HTTP:
        def get(self, url, **kw):
            raise TimeoutError("stalled")

    out = collect_pending(Conn(), HTTP(), spacing_seconds=0, sleep=lambda s: None)
    assert out["stopped"] is True and out["downloaded"] == 0
    assert len(updates) == 1 and updates[0][1][1] == "a"


@pytest.mark.phase1_blocking
def test_congress_pit_window():
    from inves_cog.perception.smartmoney import congress

    rows = [
        {
            "doc_id": "d1",
            "member": "M One",
            "filing_date": "2025-09-10",
            "parse_status": "parsed",
            "transactions": json.dumps(
                [
                    {
                        "ticker": "NVDA",
                        "txn_type": "P",
                        "txn_date": "2025-08-01",
                        "amount_low": 1001,
                        "amount_high": 15000,
                    }
                ]
            ),
        },
        {
            "doc_id": "d2",
            "member": "M Two",
            "filing_date": "2025-10-01",
            "parse_status": "parsed",
            "transactions": json.dumps(
                [
                    {
                        "ticker": "NVDA",
                        "txn_type": "S",
                        "txn_date": "2025-09-15",
                        "amount_low": 15001,
                        "amount_high": 50000,
                    }
                ]
            ),
        },
        {
            "doc_id": "d3",
            "member": "M Three",
            "filing_date": "2025-09-20",
            "parse_status": "scanned_unparsed",
            "transactions": "[]",
        },
    ]

    class Res:
        def fetchall(self):
            return rows

    class Conn:
        def execute(self, sql, params=None):
            self.params = params
            return Res()

    c = Conn()
    out = congress(c, "NVDA", "2025-11-10")
    assert out["member_count"] == 2 and out["buy_count"] == 1 and out["sell_count"] == 1
    assert out["recent"][0]["member"] == "M Two"
    assert "只列不计" in out["label"] and "参议院暂未接入" in out["as_of_note"]
    empty = congress(c, "AAPL", "2025-11-10")
    assert empty["missing"] and empty["label"] == "暂缺"


@pytest.mark.phase1_blocking
def test_live_cause_prompt_keeps_evidence_levels():
    from inves_cog.perception.live.llm_cause import QUESTION

    assert "如实转述承认、指控、传闻、确认的层级" in QUESTION
    assert "不得升级或降级" in QUESTION
