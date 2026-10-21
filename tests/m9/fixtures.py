"""Synthetic, labelled input builders; never represent private production positions."""
from datetime import datetime

from inves_cog.clock import FrozenClock


def clock():
    return FrozenClock(datetime.fromisoformat('2026-10-20T12:15:00+00:00'))


def event(**changes):
    return {
        'event_id': 'synthetic-E1', 'lifecycle': '基本面核查中', 'mechanism': '供给',
        'direction': '不利', 'created_at': '2026-10-19T12:00:00+00:00',
        'evidence_ids': ['synthetic-info-1'],
        'affected': [{'ticker': 'WDC', 'exposure': '直接', 'divergence_tag': '合理重定价'}],
        **changes,
    }


def snapshot(**changes):
    return {
        'ticker': 'SYNTH', 'date': '2026-10-20', 'tier': 'attack',
        'books': {'quality': 55.0, 'growth': 85.0, 'valuation': 10.0, 'timing': 70.0},
        'm31_adjusted_valuation': 25.0, 'm32_ok': True, 'excluded_red_line': False,
        'entry_pass': False, 'params_version': 'p-2026.10', **changes,
    }
