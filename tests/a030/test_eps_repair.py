from copy import deepcopy
from datetime import date

import pytest

from inves_cog.ingest.fundamentals.eps_repair import repair_missing_eps
from inves_cog.ingest.fundamentals.state import FinState

pytestmark = pytest.mark.phase1_blocking


def states():
    original = FinState(ticker='V',extractor='fixed',filed=date(2025,4,30),period_end=date(2025,3,31),
                        values={'eps_ttm':None,'eps_growth':None,'rev_ttm':100,'ni_ttm':20,'shares':10,'cash':1},
                        field_sources={'cash':{'method':'original'},'eps_ttm':{'reason':'missing'}},
                        health_codes=['core_field_missing','ni_tag_fallback'])
    candidate = deepcopy(original)
    candidate.values.update(eps_ttm=2.5,eps_growth=15,ni_ttm=999,cash=999)
    candidate.field_sources['eps_ttm']={'components':[{'filed':'2025-04-30','eps_fallback':'class_a_missing_company_period'}]}
    candidate.health_codes=['companyfacts_lag']
    return original,candidate


def test_historical_eps_patch_preserves_other_values_proof_and_health():
    original,candidate=states()
    old=deepcopy(original)
    result=repair_missing_eps(original,candidate)
    assert result.values['eps_ttm']==2.5 and result.values['eps_growth']==15
    assert {k:v for k,v in result.values.items() if not k.startswith('eps_')} == {k:v for k,v in old.values.items() if not k.startswith('eps_')}
    assert result.field_sources['cash']==old.field_sources['cash']
    assert result.health_codes==['ni_tag_fallback']
    assert original==old
    assert repair_missing_eps(result,candidate) is None


def test_patch_rejects_future_or_wrong_period_and_preserves_other_missing_fields():
    old,new=states()
    new.field_sources['eps_ttm']['components'][0]['filed']='2025-05-01'
    with pytest.raises(ValueError,match='PIT'):
        repair_missing_eps(old,new)
    old,new=states()
    new.period_end=date(2025,6,30)
    with pytest.raises(ValueError,match='period'):
        repair_missing_eps(old,new)
    old,new=states()
    old.values['shares']=None
    assert 'core_field_missing' in repair_missing_eps(old,new).health_codes
