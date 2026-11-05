from pathlib import Path

import pytest

from scripts.a030_verify_eps_history import cached_eps_facts

pytestmark = pytest.mark.phase1_blocking


def test_schema_free_historical_eps_preserves_class_unit_issuer_and_filing(tmp_path):
    xml = '''<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:g="http://fasb.org/us-gaap/2019-01-31"
      xmlns:i="http://www.xbrl.org/2006/xbrldi"
      xmlns:c="http://www.xbrl.org/2003/iso4217">
    <context id="a"><entity><identifier scheme="sec">0001403161</identifier><segment>
      <i:explicitMember dimension="g:StatementClassOfStockAxis">g:CommonClassAMember</i:explicitMember>
    </segment></entity><period><startDate>2019-01-01</startDate><endDate>2019-03-31</endDate></period></context>
    <unit id="u"><divide><unitNumerator><measure>c:USD</measure></unitNumerator>
    <unitDenominator><measure>shares</measure></unitDenominator></divide></unit>
    <g:EarningsPerShareDiluted contextRef="a" unitRef="u">1.31</g:EarningsPerShareDiluted></xbrl>'''
    path = Path(tmp_path) / "instance.xml"
    filing = dict(cik="1403161", accession="test", filing_date="2019-04-26", form="10-Q")
    path.write_text(xml)
    rows = cached_eps_facts(path, filing)["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
    assert len(rows) == 1
    assert rows[0]["val"] == 1.31 and rows[0]["filed"] == "2019-04-26"
    assert rows[0]["d9_only"] and rows[0]["origin"] == "instance_parsed"
    for changed in (
        xml.replace("CommonClassAMember", "CommonClassBMember"),
        xml.replace("0001403161", "0000000001"),
        xml.replace("c:USD", "c:EUR"),
        xml.replace(">1.31<", ">NaN<"),
    ):
        path.write_text(changed)
        assert cached_eps_facts(path, filing)["facts"] == {}
