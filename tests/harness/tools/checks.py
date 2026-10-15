"""Static phase-one gates. Every failure includes its source and rule."""

import ast
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IGNORED = {".git", ".venv", ".harness", "__pycache__", "docs", "handoff"}
BUSINESS = {"ingest", "marketstate", "trading", "valuation_v1", "perception", "shadow", "overlay", "web"}
ALLOWED = {
    "ingest": set(),
    "marketstate": {"ingest"},
    "trading": {"ingest", "marketstate", "overlay"},
    "valuation_v1": {"ingest", "trading"},
    "perception": {"ingest", "marketstate"},
    "overlay": {"perception"},
    "shadow": BUSINESS,
    "web": BUSINESS,
}
MODEL_PATTERN = re.compile(
    r"(?i)(?<![\w-])(?:glm|gpt|claude|qwen|gemini|deepseek|llama|mistral)"
    r"(?:[-_.][a-z0-9]+|\d[a-z0-9]*)(?:[-_.][a-z0-9]+)*(?![\w-])"
)
URL_HOST_PATTERN = re.compile(r"""(?i)https?://(?P<host>[a-z0-9.-]+)(?=[:/?#\s'"<>]|$)""")


def _brand_hostname(line, token):
    # Only alphabetic brand/TLD tokens in an HTTP(S) hostname are domains.
    # Versions and hyphenated model tokens, and URL paths/queries, still fail.
    if not re.fullmatch(r"[a-z]+(?:\.[a-z]{2,}){1,2}", token.group(), re.I):
        return False
    return any(
        host.start("host") <= token.start() and token.end() <= host.end("host")
        for host in URL_HOST_PATTERN.finditer(line)
    )


def fail(path, line, rule, reason):
    raise AssertionError(f"{path}:{line}: {rule}: {reason}")


def source_files(root):
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*.py") if not (set(p.relative_to(root).parts) & IGNORED))


def requirement_catalog(root):
    catalog = {}
    for path in sorted((Path(root) / "docs/phase1").glob("M*-*.md")):
        module = re.match(r"M\d+", path.name).group()
        text = path.read_text()
        match = re.search(r"^## 7\..*?(?=^## 8\.|\Z)", text, re.M | re.S)
        if not match:
            fail(path, 1, "FR-M0-06", "missing test table")
        for name, mark in re.findall(r"^\| `(test_[^`]+)` \| (\w+) \|", match.group(), re.M):
            if name in catalog:
                fail(path, 1, "FR-M0-06", f"duplicate documented test {name}")
            catalog[name] = (module, mark)
    return catalog


def requirement_tests(root):
    return {name: module for name, (module, _) in requirement_catalog(root).items()}


def defined_tests(root):
    names = set()
    for path in source_files(Path(root) / "tests"):
        tree = ast.parse(path.read_text(), filename=str(path))
        names.update(
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
        )
    return names


def validate_registry(root, *, pending_path=None, milestones_path=None, collected_names=()):
    root = Path(root)
    pending_path = Path(pending_path or root / "tests/harness/pending.txt")
    milestones_path = Path(milestones_path or root / "tests/harness/milestones.txt")
    required = requirement_tests(root)
    rows = {}
    for line_no, raw in enumerate(pending_path.read_text().splitlines(), 1):
        if not raw.strip() or raw.startswith("#"):
            continue
        fields = [field.strip() for field in raw.split("|")]
        if len(fields) != 3 or not all(fields):
            fail(pending_path, line_no, "FR-M0-05", "expected test | module | reason")
        name, module, reason = fields
        if name in rows or not re.fullmatch(r"M(?:[1-9]|10)", module):
            fail(pending_path, line_no, "FR-M0-05", "duplicate test or invalid module")
        if required.get(name) != module:
            fail(pending_path, line_no, "FR-M0-05", f"unknown test or wrong module: {name}")
        rows[name] = module
    closed = []
    for number, line in enumerate(milestones_path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        if not re.fullmatch(r"M(?:[0-9]|10)", line) or line in closed:
            fail(milestones_path, number, "FR-M0-05", "invalid or duplicate milestone")
        closed.append(line)
    defined = defined_tests(root) | set(collected_names)
    for module in closed:
        remaining = {name for name, owner in rows.items() if owner == module}
        missing = {name for name, owner in required.items() if owner == module} - defined
        if remaining or missing:
            fail(
                milestones_path,
                1,
                "FR-M0-05",
                f"{module}: pending residual {sorted(remaining)}; missing definitions {sorted(missing)}",
            )
    # A documented test must either have a definition or be openly registered.
    # This preserves the initial 142+12 equality while permitting future modules to graduate.
    missing = set(required) - (set(rows) | defined)
    if missing:
        fail(pending_path, 1, "FR-M0-05", f"undocumented completion: missing {sorted(missing)}")
    return rows, defined & set(required)


def _imports(tree, package):
    importlib_aliases = {"importlib"}
    loaders = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "importlib":
                    importlib_aliases.add(a.asname or a.name)
                yield n.lineno, a.name
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                try:
                    base = importlib.util.resolve_name("." * n.level + base, package)
                except ImportError:
                    base = "<invalid-relative>"
            for a in n.names:
                if base == "importlib" and a.name == "import_module":
                    loaders.add(a.asname or a.name)
                yield n.lineno, base + ("." + a.name if a.name != "*" else "")
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not n.args or not isinstance(n.args[0], ast.Constant):
            continue
        dynamic = (
            isinstance(n.func, ast.Attribute)
            and n.func.attr == "import_module"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id in importlib_aliases
        )
        dynamic |= isinstance(n.func, ast.Name) and n.func.id in loaders
        dynamic |= isinstance(n.func, ast.Name) and n.func.id == "__import__"
        if dynamic and isinstance(n.args[0].value, str):
            target = n.args[0].value
            if target.startswith("."):
                target = importlib.util.resolve_name(target, package)
            yield n.lineno, target


def scan_imports(root):
    root = Path(root)
    for path in source_files(root):
        parts = path.relative_to(root).parts
        origin = None
        package = "inves_cog"
        if parts[:2] == ("src", "inves_cog"):
            if len(parts) > 3:
                origin = parts[2]
            tail = parts[1:]
            module = ".".join(tail)[:-3]
            package = module[:-9] if module.endswith(".__init__") else module.rsplit(".", 1)[0]
        tree = ast.parse(path.read_text(), filename=str(path))
        for line, target in _imports(tree, package):
            first = target.split(".")[0]
            if first == "stock_pm" or re.match(
                r"^(paper_trade_|paper_tracker(?:\.|$)|factor_framework|screen_asof_)", first
            ):
                fail(path, line, "I01/FR-M0-09", f"external project import {target}")
            target_parts = target.split(".")
            if origin not in BUSINESS or len(target_parts) < 2 or target_parts[0] != "inves_cog":
                continue
            dependency = target_parts[1]
            if dependency not in BUSINESS or dependency == origin:
                continue
            graph_exception = origin == "marketstate" and target.startswith("inves_cog.perception.graph.")
            graph_exception |= origin == "marketstate" and target == "inves_cog.perception.graph"
            if dependency not in ALLOWED[origin] and not graph_exception:
                fail(path, line, "I01/FR-M0-09", f"{origin} may not import {target}")
            if (
                dependency == "trading"
                and origin != "trading"
                and any(segment in {"engine", "orders", "order_writer"} for segment in target_parts[2:])
            ):
                fail(path, line, "I01/FR-M0-09", f"order-writing interface {target}")
        if origin in {"marketstate", "trading"}:
            for line, target in _imports(tree, package):
                if target.startswith("inves_cog.llm"):
                    fail(path, line, "I01/FR-M0-09", f"{origin} may not import LLM")


def scan_clock(root):
    for path in source_files(root):
        if Path(root).is_dir() and path == Path(root) / "clock.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        aliases = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                aliases.update({a.asname or a.name: a.name for a in n.names})
            elif isinstance(n, ast.ImportFrom) and not n.level:
                aliases.update({a.asname or a.name: (n.module or "") + "." + a.name for a in n.names})
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                reference = n.func
            elif isinstance(n, (ast.Attribute, ast.Name)) and isinstance(n.ctx, ast.Load):
                reference = n
            else:
                continue
            name = ast.unparse(reference)
            first, *rest = name.split(".")
            resolved = ".".join([aliases.get(first, first), *rest])
            forbidden = {
                "datetime.now",
                "datetime.utcnow",
                "datetime.today",
                "datetime.datetime.now",
                "datetime.datetime.utcnow",
                "datetime.datetime.today",
                "date.today",
                "datetime.date.today",
                "time.time",
                "time.time_ns",
                "pandas.Timestamp.now",
                "pandas.Timestamp.today",
                "pandas.Timestamp.utcnow",
            }
            numpy_current = (
                isinstance(n, ast.Call)
                and resolved == "numpy.datetime64"
                and n.args
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value in ("now", "today")
            )
            if resolved in forbidden or numpy_current:
                fail(path, n.lineno, "FR-M0-04", f"system time {name}; inject Clock")


def scan_models(root):
    from inves_cog.ingest.embedding_models import MODEL_DIMENSIONS
    from inves_cog.llm.registry import ALLOWED_MODELS

    root = Path(root)
    if root.is_file():
        files = [root]
    else:
        files = []
        for name in ("src", "config", "tests", "scripts", ".github"):
            for p in (root / name).rglob("*"):
                if not p.is_file():
                    continue
                if "__pycache__" in p.parts:
                    continue
                if "recordings" in p.parts and p.suffix in {".json", ".jsonl"}:
                    continue
                files.append(p)
        for pattern in ("Makefile", "Dockerfile*", "docker-compose*.yml", ".env*"):
            files.extend(p for p in root.glob(pattern) if p.is_file())
    for path in files:
        raw = path.read_bytes()
        if b"\x00" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in MODEL_PATTERN.finditer(line):
                if (
                    match.group() not in ALLOWED_MODELS
                    and match.group() not in MODEL_DIMENSIONS
                    and not _brand_hostname(line, match)
                ):
                    fail(path, line_no, "I37/FR-M0-10", f"non-whitelisted model {match.group()}")
