"""Ruff gates restricted to changed Python files, with named legacy exceptions."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path


def changed_python(root):
    root = Path(root)
    manifest = root / ".harness/changed-python.json"
    if os.environ.get("CI"):
        if not manifest.is_file():
            raise AssertionError("RUFF: CI changed-file manifest is missing")
        names = json.loads(manifest.read_text())
    else:
        names = []
        for arguments in (
            ["diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"],
            ["diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            result = subprocess.run(["git", *arguments], cwd=root, capture_output=True, text=True, check=True)
            names.extend(result.stdout.splitlines())
    paths = []
    for name in sorted(set(names)):
        path = root / name
        if path.suffix != ".py" or not path.is_file():
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            raise AssertionError("RUFF: changed-file path escapes the repository")
        paths.append(path)
    return paths


def qualified_functions(path):
    result = {}

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            scope = prefix
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                scope += child.name
                result[child.lineno] = scope
                scope += "."
            visit(child, scope)

    visit(ast.parse(path.read_text()))
    return result


def check_style(root, *, paths=None):
    root = Path(root)
    paths = changed_python(root) if paths is None else list(paths)
    if not paths:
        return
    command = [sys.executable, "-m", "ruff"]
    config = str(root / "pyproject.toml")
    formatter = subprocess.run(
        [*command, "format", "--check", "--config", config, *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    if formatter.returncode:
        raise AssertionError("RUFF format: " + formatter.stdout + formatter.stderr)
    lint = subprocess.run(
        [*command, "check", "--config", config, "--output-format", "json", *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    if lint.returncode not in (0, 1):
        raise AssertionError("RUFF check: " + lint.stderr)
    exemptions = json.loads((root / "tests/harness/complexity_exemptions.json").read_text())
    failures = []
    for item in json.loads(lint.stdout):
        path = Path(item["filename"])
        if item["code"] == "C901" and path.is_relative_to(root):
            function = qualified_functions(path).get(item["location"]["row"])
            key = str(path.relative_to(root)) + ":" + str(function)
            if key in exemptions:
                continue
        failures.append(f"{path}:{item['location']['row']}: {item['code']}: {item['message']}")
    if failures:
        raise AssertionError("RUFF check:\n" + "\n".join(failures))
