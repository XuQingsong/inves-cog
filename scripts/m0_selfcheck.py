"""Nine destructive checks in disposable files, without touching real golden."""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.harness.tools.checks import requirement_catalog, validate_registry
from tests.harness.tools.testing import ROOT, output, run_probe


def fingerprints(directory):
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file()
    }


def main():
    evidence = ROOT / ".harness/destructive"
    evidence.mkdir(parents=True, exist_ok=True)
    golden = ROOT / "docs/phase1/golden"
    before = fingerprints(golden)
    with tempfile.TemporaryDirectory(prefix="inves-cog-m0-") as name:
        temp = Path(name)
        sources = temp / "src/inves_cog"
        (sources / "trading").mkdir(parents=True)
        (sources / "marketstate").mkdir()
        (sources / "ingest").mkdir()
        time_file = sources / "trading/bad_time.py"
        time_file.write_text("from datetime import datetime\nvalue = datetime.now()\n")
        copied_golden = temp / "golden"
        shutil.copytree(golden, copied_golden)
        p = copied_golden / "m3_interp_points.json"
        p.write_bytes(p.read_bytes() + b" ")
        copied_fixtures = temp / "frozen"
        shutil.copytree(ROOT / "tests/fixtures/phase1", copied_fixtures)
        p = copied_fixtures / "harness/sample.json"
        p.write_bytes(p.read_bytes() + b" ")
        valuation_file = sources / "trading/bad_valuation.py"
        valuation_file.write_text("import inves_cog.valuation_v1\n")
        attribution_file = sources / "marketstate/bad_attribution.py"
        attribution_file.write_text("import inves_cog.perception.attribution\n")
        external_file = sources / "ingest/bad_external.py"
        external_file.write_text("import " + "stock" + "_pm\n")
        model_file = temp / "bad_model.py"
        model_file.write_text("model=" + repr("glm" + "-5" + ".2") + "\n")

        def scanner(function, path):
            return (
                f"from pathlib import Path\nfrom tests.harness.tools.checks import {function}\n"
                f"def test_probe():\n    {function}(Path({str(path)!r}))\n"
            )

        # Each import check gets a separate root so the diagnostic identifies that item.
        import_roots = []
        for index, p in enumerate((valuation_file, attribution_file, external_file)):
            root = temp / f"import-{index}"
            dst = root / p.relative_to(temp)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
            import_roots.append(root)
        cases = [
            (
                "01-network",
                "FR-M0-03",
                'import socket\ndef test_probe():\n    socket.create_connection(("example.com", 80))\n',
            ),
            ("02-clock", "FR-M0-04", scanner("scan_clock", time_file)),
            ("03-skip", "FR-M0-05", "import pytest\n@pytest.mark.skip\ndef test_probe():\n    assert False\n"),
            (
                "04-golden",
                "FR-M0-07",
                "from pathlib import Path\nfrom tests.harness.tools.golden import validate_golden\n"
                f"def test_probe():\n    validate_golden(Path({str(copied_golden)!r}))\n",
            ),
            (
                "05-frozen",
                "FR-M0-08",
                "from pathlib import Path\nfrom tests.harness.tools.golden import validate_frozen\n"
                f"def test_probe():\n    validate_frozen(Path({str(copied_fixtures)!r}), "
                f"Path({str(ROOT / 'tests/harness/CHANGELOG.md')!r}))\n",
            ),
            ("06-valuation-import", "I01", scanner("scan_imports", import_roots[0])),
            ("07-model", "I37", scanner("scan_models", model_file)),
            ("08-marketstate-import", "I01", scanner("scan_imports", import_roots[1])),
            ("09-external-import", "I01", scanner("scan_imports", import_roots[2])),
        ]
        results = []
        for label, rule, code in cases:
            result = run_probe(temp, code)
            log = output(result)
            (evidence / (label + ".log")).write_text("\n".join(line.rstrip() for line in log.splitlines()) + "\n")
            good = result.returncode != 0 and rule in log
            results.append(dict(case=label, expected_rule=rule, exit_code=result.returncode, red=good))
            print(f"{label}: exit={result.returncode}; {rule}; red={good}")
            if not good:
                raise AssertionError("Destructive check did not produce the expected red light: " + label)
    after = fingerprints(golden)
    assert after == before, "Real golden changed"
    (evidence / "summary.json").write_text(
        json.dumps(dict(checks=results, real_golden_unchanged=True), indent=2) + "\n"
    )
    rows, defined = validate_registry(ROOT)
    catalog = requirement_catalog(ROOT)
    report = [
        dict(test=name, module=module, marker=mark, pending=name in rows, defined=name in defined)
        for name, (module, mark) in sorted(catalog.items())
    ]
    (ROOT / ".harness/pending-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
