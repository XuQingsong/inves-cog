"""Static effective table permissions for existing and future admin-owned tables."""
from dataclasses import dataclass, field
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
OWNERS = {
    'ingest': 'role_ingest', 'fundamentals': 'role_ingest',
    'marketstate': 'role_marketstate', 'graph': 'role_perception',
    'trading': 'role_trading', 'valuation_v1': 'role_valuation',
    'perception': 'role_perception', 'perception_shadow': 'role_shadow',
    'factor_shadow': 'role_shadow', 'overlay': 'role_overlay',
}
READS = {
    'role_ingest': set(),
    'role_trading': {'ingest', 'fundamentals', 'marketstate', 'overlay'},
    'role_marketstate': {'ingest', 'graph'},
    'role_valuation': {'ingest', 'fundamentals', 'graph', 'trading'},
    'role_perception': {'ingest', 'fundamentals', 'marketstate', 'trading'},
    'role_overlay': {'perception', 'graph'},
    'role_shadow': set(OWNERS), 'role_web': set(OWNERS),
}
WRITE = {'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'}
ALL = {'SELECT'} | WRITE


@dataclass
class PermissionMatrix:
    path: Path
    schemas: set = field(default_factory=set)
    roles: set = field(default_factory=set)
    tables: dict = field(default_factory=dict)
    default_tables: dict = field(default_factory=dict)
    revokes: set = field(default_factory=set)
    default_schemas: set = field(default_factory=set)
    admin_selected: bool = False

    @classmethod
    def from_sql(cls, text, *, path='<migration>'):
        obj = cls(Path(path))
        text = re.sub(r'--[^\n]*', '', text)
        obj.schemas = set(re.findall(r'CREATE SCHEMA IF NOT EXISTS (\w+) AUTHORIZATION inves_cog_admin', text, re.I))
        obj.roles = set(re.findall(r'CREATE ROLE (role_\w+) NOLOGIN NOINHERIT NOSUPERUSER', text, re.I))
        obj.admin_selected = bool(re.search(r'SET ROLE inves_cog_admin\s*;', text, re.I))
        if re.search(r'GRANT\s+(?:inves_cog_admin|role_\w+)\s+TO', text, re.I):
            raise AssertionError(f'{path}:1: FR-M0-11: role membership can bypass isolation')
        current = re.compile(r'(GRANT|REVOKE)\s+([A-Z, ]+?)\s+ON ALL TABLES IN SCHEMA (\w+)\s+(TO|FROM)\s+([\w, ]+)\s*;', re.I)
        defaults = re.compile(r'ALTER DEFAULT PRIVILEGES FOR ROLE inves_cog_admin IN SCHEMA (\w+)\s+(GRANT|REVOKE)\s+([A-Z, ]+?)\s+ON TABLES\s+(TO|FROM)\s+([\w, ]+)\s*;', re.I)
        # Process statements in source order so a later unauthorized GRANT is visible.
        statements = []
        for m in current.finditer(text):
            action, privileges, schema, _, roles = m.groups()
            statements.append((m.start(), False, schema, action, privileges, roles))
        for m in defaults.finditer(text):
            schema, action, privileges, _, roles = m.groups()
            statements.append((m.start(), True, schema, action, privileges, roles))
        for _, future, schema, action, privileges, roles in sorted(statements):
            table = obj.default_tables if future else obj.tables
            obj.default_schemas.update({schema} if future else set())
            rights = {x.strip().upper() for x in privileges.split(',')}
            if 'ALL' in rights or 'ALL PRIVILEGES' in rights:
                rights = set(ALL)
            for role in (x.strip() for x in roles.split(',')):
                key = (role, schema)
                existing = table.setdefault(key, set())
                if action.upper() == 'GRANT':
                    existing.update(rights)
                else:
                    existing.difference_update(rights)
                    obj.revokes.add((role, schema, future))
        return obj

    def effective(self, role, schema, future=False):
        table = self.default_tables if future else self.tables
        return table.get((role, schema), set()) | table.get(('PUBLIC', schema), set())

    def validate(self):
        def error(message):
            raise AssertionError(f'{self.path}:1: FR-M0-11: {message}')
        if self.schemas != set(OWNERS) or self.roles != set(READS) or not self.admin_selected:
            error('schema/role/admin matrix differs from README §3.6')
        if self.default_schemas != self.schemas:
            error('missing admin ALTER DEFAULT PRIVILEGES')
        for schema, writer in OWNERS.items():
            for role in READS:
                expected = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'} if role == writer else (
                    {'SELECT'} if schema in READS[role] else set())
                for future in (False, True):
                    actual = self.effective(role, schema, future)
                    if actual != expected:
                        error(f'{role} / {schema} / future={future}: {sorted(actual)} != {sorted(expected)}')
                    if (role, schema, future) not in self.revokes:
                        error(f'missing explicit REVOKE for {role} / {schema}')
            for future in (False, True):
                if self.effective('PUBLIC', schema, future):
                    error(f'PUBLIC access on {schema}')
        return self


def _matrix(matrix):
    if matrix is not None:
        return matrix
    p = ROOT / 'migrations/phase1_m0_0001_schemas_roles.sql'
    return PermissionMatrix.from_sql(p.read_text(), path=p)


def assert_no_select(role, schema, *, matrix=None):
    matrix = _matrix(matrix)
    for future in (False, True):
        if 'SELECT' in matrix.effective(role, schema, future):
            raise AssertionError(f'{matrix.path}:1: FR-M0-11: {role} can SELECT {schema}, future={future}')


def assert_no_write(role, schema, *, matrix=None):
    matrix = _matrix(matrix)
    for future in (False, True):
        if matrix.effective(role, schema, future) & WRITE:
            raise AssertionError(f'{matrix.path}:1: FR-M0-11: {role} can write {schema}, future={future}')
