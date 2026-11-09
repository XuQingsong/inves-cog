import zipfile
from pathlib import Path

import pytest

from inves_cog.ingest.f13 import load_dataset, visible_holdings

SUB = (
    "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
    "ACC-1\t15-AUG-2026\t13F-HR\t0001\t30-JUN-2026\n"
    "ACC-2\t20-AUG-2026\t13F-HR/A\t0001\t30-JUN-2026\n"
)
COV = (
    "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tISAMENDMENT\tAMENDMENTNO\tAMENDMENTTYPE\t"
    "CONFDENIEDEXPIRED\tDATEDENIEDEXPIRED\tDATEDEREPORTED\tREASONFORNONCONFIDENTIALITY\t"
    "FILINGMANAGER_NAME\tFILINGMANAGER_STREET1\tFILINGMANAGER_STREET2\tFILINGMANAGER_CITY\t"
    "FILINGMANAGER_STATEORCOUNTRY\tFILINGMANAGER_ZIPCODE\tREPORTTYPE\tFORM13FFILENUMBER\t"
    "CRDNUMBER\tSECFILENUMBER\tPROVIDEINFOFORINSTRUCTION5\tADDITIONALINFORMATION\n"
    "ACC-1\t30-JUN-2026\tN\t\t\t\t\t\t\tBig Fund\t\t\t\t\t\t13F HOLDINGS REPORT\t\t\t\t\t\n"
    "ACC-2\t30-JUN-2026\tY\t1\tRESTATEMENT\t\t\t\t\tBig Fund\t\t\t\t\t\t13F HOLDINGS REPORT\t\t\t\t\t\n"
)
INFO_HEADER = (
    "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\t"
    "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\tINVESTMENTDISCRETION\tOTHERMANAGER\t"
    "VOTING_AUTH_SOLE\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\n"
)


def _zip(tmp: Path, info_lines: str) -> Path:
    path = tmp / "t.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("SUBMISSION.tsv", SUB)
        zf.writestr("COVERPAGE.tsv", COV)
        zf.writestr("INFOTABLE.tsv", INFO_HEADER + info_lines)
        zf.writestr("OTHERMANAGER.tsv", "")
        zf.writestr("OTHERMANAGER2.tsv", "")
        zf.writestr("SIGNATURE.tsv", "")
        zf.writestr("SUMMARYPAGE.tsv", "")
    return path


@pytest.mark.phase1_blocking
def test_filter_keeps_only_mapped_cusips(tmp_path):
    lines = (
        "ACC-1\t1\tAPPLE INC\tCOM\t037833100\t\t100\t5\tSH\t\tSOLE\t\t5\t0\t0\n"
        "ACC-1\t2\tRANDOM CO\tCOM\t999999999\t\t100\t5\tSH\t\tSOLE\t\t5\t0\t0\n"
    )
    stats = load_dataset(_zip(tmp_path, lines), {"037833100": "AAPL"})
    assert stats["scanned"] == 2 and stats["kept"] == 1


@pytest.mark.phase1_blocking
def test_restatement_overrides_and_new_holdings_appends():
    base = {
        "filer_cik": "1",
        "period": "2026-06-30",
        "ticker": "AAPL",
        "accession": "A",
        "filing_date": "2026-08-01",
        "shares": 100,
        "is_amendment": False,
        "amendment_type": None,
    }
    restated = {
        **base,
        "accession": "B",
        "filing_date": "2026-08-15",
        "shares": 250,
        "is_amendment": True,
        "amendment_type": "RESTATEMENT",
    }
    best = visible_holdings([base, restated])
    assert best[("1", "2026-06-30", "AAPL")]["shares"] == 250
    newpos = {
        **base,
        "ticker": "NVDA",
        "accession": "B",
        "filing_date": "2026-08-15",
        "is_amendment": True,
        "amendment_type": "NEW HOLDINGS",
    }
    best = visible_holdings([base, newpos])
    assert best[("1", "2026-06-30", "AAPL")]["shares"] == 100  # original untouched
    assert best[("1", "2026-06-30", "NVDA")]["shares"] == 100  # appended


@pytest.mark.phase1_blocking
def test_load_dataset_row_fields(tmp_path):
    lines = "ACC-2\t7\tAPPLE INC\tCOM\t037833100\t\t388237\t5250\tSH\t\tSOLE\t\t5250\t0\t0\n"
    stats = load_dataset(_zip(tmp_path, lines), {"037833100": "AAPL"})
    assert stats["kept"] == 1
