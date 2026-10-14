"""The sole PIT financial-state lookup for downstream consumers."""
from dataclasses import dataclass, field
from datetime import date

FIELDS = ('rev_ttm ni_ttm rev_growth rev_q_yoy rev_accel_pp eps_ttm eps_growth gross_margin '
          'gross_margin_change_pp fcf_ttm fcf_margin fcf_conversion roe cash debt net_debt '
          'net_debt_fcf current_ratio shares fcf_margin_change_pp op_margin_ttm').split()


@dataclass
class FinState:
    ticker: str
    extractor: str
    filed: date
    period_end: date | None
    accession: str | None = None
    form: str | None = None
    fiscal_period: str | None = None
    values: dict = field(default_factory=dict)
    field_sources: dict = field(default_factory=dict)
    health_codes: list = field(default_factory=list)
    oracle_values: dict = field(default_factory=dict)


class StateStore:
    def __init__(self, states=()):
        self.states = list(states)
    def put(self, state):
        self.states = [s for s in self.states if (s.ticker,s.extractor,s.filed) != (state.ticker,state.extractor,state.filed)]
        self.states.append(state)
    def state_asof(self,ticker,as_of_date,extractor):
        if extractor not in {'legacy','fixed'}: raise ValueError('Unknown extractor')
        rows = [s for s in self.states if s.ticker == ticker and s.extractor == extractor and s.filed <= as_of_date]
        return max(rows,key=lambda s:s.filed) if rows else None


_configured_store = None


def configure(store):
    global _configured_store
    _configured_store = store


def state_asof(ticker,as_of_date,extractor):
    if _configured_store is None:
        raise RuntimeError('Configure the financial-state repository before lookup')
    return _configured_store.state_asof(ticker,as_of_date,extractor)
