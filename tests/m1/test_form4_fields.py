import pytest

from inves_cog.ingest.sec import parse_form4

BASE = """<ownershipDocument>
  <issuer><issuerTradingSymbol>NVDA</issuerTradingSymbol></issuer>
  <reportingOwner><reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>{rel}</reportingOwnerRelationship></reportingOwner>
  {plan}
  <nonDerivativeTable><nonDerivativeTransaction>
    <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>{sh}</value></transactionShares>
    <transactionPricePerShare><value>{px}</value></transactionPricePerShare></transactionAmounts>
  </nonDerivativeTransaction></nonDerivativeTable>
</ownershipDocument>"""


@pytest.mark.phase1_blocking
def test_form4_officer_director_and_plan():
    rows = parse_form4(
        BASE.format(
            rel="<isDirector>1</isDirector><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle>",
            plan="<aff10b5One>true</aff10b5One>",
            sh="100",
            px="10.5",
        ),
        accession="a1",
        filed_at="2026-01-01",
    )
    row = rows[0]
    assert row["is_director"] is True and row["is_officer"] is True
    assert row["officer_title"] == "CFO"
    assert row["aff10b5_one"] is True
    assert row["amount"] == 1050.0


@pytest.mark.phase1_blocking
def test_form4_missing_plan_and_zero_price_stay_null():
    rows = parse_form4(
        BASE.format(rel="<isTenPercentOwner>true</isTenPercentOwner>", plan="", sh="500", px="0"),
        accession="a2",
        filed_at="2026-01-01",
    )
    row = rows[0]
    assert row["aff10b5_one"] is None
    assert row["is_ten_percent_owner"] is True
    assert row["is_director"] is None
    assert row["amount"] is None
