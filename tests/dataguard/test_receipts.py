from datetime import date, datetime, timezone
import pytest
from inves_cog.dataguard.receipts import bounded_rows

pytestmark=pytest.mark.phase1_blocking
DAY=date(2026,11,5)
NOW=datetime(2026,11,7,tzinfo=timezone.utc)


def test_historical_parser_output_is_clipped_to_requested_date_and_receipt_is_actual_now():
    rows=[dict(series_id='yahoo_px_hyg',obs_date=DAY,value=80,published_at=NOW.replace(year=2020),vintage='backfill'),
          dict(series_id='yahoo_px_hyg',obs_date=date(2026,11,4),value=81,published_at=NOW,vintage='backfill'),
          dict(series_id='unrequested',obs_date=DAY,value=1,published_at=NOW,vintage='backfill')]
    got=bounded_rows('observations',rows,day=DAY,now=NOW,filters={'series_id':['yahoo_px_hyg']})
    assert len(got)==1
    assert got[0]['published_at']==NOW and got[0]['ingested_at']==NOW
    assert got[0]['vintage']=='dataguard'
    assert rows[0]['vintage']=='backfill'


def test_unknown_table_is_rejected_instead_of_unbounded_business_writes():
    with pytest.raises(ValueError): bounded_rows('orders',[],day=DAY,now=NOW,filters={})
