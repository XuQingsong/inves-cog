"""Read project credentials as data and report readiness without secret values."""
import ast
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
ALIASES = {
    'APCA_API_BASE_URL': ('ALPACA_BASE_URL', 'ALPACA_API_BASE_URL'),
    'APCA_API_KEY_ID': ('ALPACA_API_KEY_ID', 'ALPACA_API_KEY'),
    'APCA_API_SECRET_KEY': ('ALPACA_API_SECRET_KEY', 'ALPACA_API_SECRET'),
    'SEC_USER_AGENT': ('SEC_EDGAR_USER_AGENT',),
    'ALPHA_VANTAGE_API_KEY': ('ALPHAVANTAGE_API_KEY',),
    'GOOGLE_CSE_CX': ('GOOGLE_CSE_ID',),
}
REQUIRED = {
    'Alpaca': ('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY'),
    'SEC': ('SEC_USER_AGENT',),
    'FRED': ('FRED_API_KEY',),
    'AlphaVantage': ('ALPHA_VANTAGE_API_KEY',),
    'DashScope': ('DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL'),
    'LLM_hard': ('LLM_HARD_PROVIDER', 'LLM_HARD_BASE_URL', 'LLM_HARD_API_STYLE', 'LLM_HARD_API_KEY'),
    'LLM_standard': ('LLM_STANDARD_PROVIDER', 'LLM_STANDARD_BASE_URL', 'LLM_STANDARD_API_STYLE', 'LLM_STANDARD_API_KEY'),
    'Tavily': ('TAVILY_API_KEY',),
    'Exa': ('EXA_API_KEY',),
    'GoogleCSE': ('GOOGLE_CSE_API_KEY', 'GOOGLE_CSE_CX'),
    'Database': ('INVES_COG_DATABASE_URL',),
}


def read_environment(path=None, *, environ=None):
    """No shell execution or interpolation; process variables have priority."""
    values = {}
    path = Path(path or ROOT / '.env')
    if path.exists():
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.removeprefix('export ').partition('=')
            key, value = key.strip(), value.strip()
            if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                raise ValueError(f'Invalid environment assignment at line {number}')
            if value.startswith(('"', "'")):
                try:
                    value = ast.literal_eval(value)
                except (SyntaxError, ValueError):
                    raise ValueError(f'Invalid quoted environment value at line {number}') from None
                if not isinstance(value, str):
                    raise ValueError(f'Expected a string at line {number}')
            else:
                value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
            if key in values and values[key] != value:
                raise ValueError(f'Conflicting duplicate environment name at line {number}: {key}')
            values[key] = value
    values.update(os.environ if environ is None else environ)
    for canonical, aliases in ALIASES.items():
        supplied = {values[name] for name in (canonical, *aliases) if values.get(name)}
        if len(supplied) > 1:
            raise ValueError(f'conflicting aliases for {canonical}')
        if supplied:
            values[canonical] = supplied.pop()
    return values


def source_configuration(values):
    result = {}
    for source, names in REQUIRED.items():
        missing = [name for name in names if not values.get(name)]
        issues = []
        result[source] = {'configured': not missing and not issues, 'missing': missing, 'issues': issues}
    result['Alpaca']['feed'] = 'sip'
    return result
