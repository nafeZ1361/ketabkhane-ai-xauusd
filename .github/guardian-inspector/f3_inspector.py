from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal, Inexact, localcontext


def manifest(root: Path) -> dict[str, str]:
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache"}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(p for p in root.rglob("*") if p.is_file())
        if not any(part in excluded for part in path.parts)
    }


def load_modules(project_root: Path):
    import importlib
    source = str(project_root / "src")
    for name in tuple(sys.modules):
        if name == "guardian" or name.startswith("guardian."):
            del sys.modules[name]
    sys.path.insert(0, source)
    importlib.invalidate_caches()
    from guardian.domain.risk import RiskSpec
    from guardian.firewall.risk import revalidate_proposed_size
    from guardian.contracts.firewall import FirewallRequest
    from guardian.firewall.policy import PolicyContext, authorize_request
    return RiskSpec, revalidate_proposed_size, FirewallRequest, PolicyContext, authorize_request


def blackbox(project_root: Path) -> tuple[unittest.result.TestResult, str]:
    RiskSpec, validate, Request, Context, authorize = load_modules(project_root)

    def spec(**overrides):
        values = {
            "risk_fraction": Decimal("0.01"),
            "value_per_point_lot": Decimal("1"),
            "lot_step": Decimal("0.01"),
            "min_lot": Decimal("0.01"),
            "max_lot": Decimal("100"),
        }
        values.update(overrides)
        return RiskSpec(**values)

    class BoundaryProbes(unittest.TestCase):
        def check(self, lots, *, equity=Decimal("10000"), stop=Decimal("100"), risk_spec=None):
            return validate(equity, stop, lots, spec=spec() if risk_spec is None else risk_spec)

        def test_exact_maximum_and_smaller_size_pass(self):
            self.assertTrue(self.check(Decimal("1.00")).within_risk_limit)
            self.assertTrue(self.check(Decimal("0.50")).within_risk_limit)

        def test_over_limit_size_is_denied(self):
            result = self.check(Decimal("1.01"))
            self.assertFalse(result.within_risk_limit)
            self.assertEqual(result.reason_code, "PROPOSED_SIZE_EXCEEDS_RECOMPUTED_MAXIMUM")

        def test_off_step_and_below_minimum_are_denied(self):
            self.assertFalse(self.check(Decimal("0.505")).within_risk_limit)
            self.assertFalse(self.check(Decimal("0.005")).within_risk_limit)

        def test_invalid_types_and_non_finite_values_are_denied(self):
            for value in (1, 1.0, "1", None, Decimal("NaN"), Decimal("Infinity")):
                self.assertFalse(self.check(value).within_risk_limit)

        def test_invalid_equity_and_stop_are_denied(self):
            self.assertFalse(self.check(Decimal("0.5"), equity=Decimal("0")).within_risk_limit)
            self.assertFalse(self.check(Decimal("0.5"), stop=Decimal("0")).within_risk_limit)

        def test_low_level_mutated_spec_is_denied(self):
            changed = spec()
            object.__setattr__(changed, "risk_fraction", Decimal("NaN"))
            self.assertFalse(self.check(Decimal("0.5"), risk_spec=changed).within_risk_limit)

        def test_non_step_aligned_cap_is_denied(self):
            self.assertFalse(self.check(Decimal("0.5"), risk_spec=spec(max_lot=Decimal("0.505"))).within_risk_limit)

        def test_decimal_arithmetic_failure_is_denied(self):
            with localcontext() as context:
                context.prec = 2
                context.traps[Inexact] = True
                result = self.check(Decimal("10000"), equity=Decimal("12345"), stop=Decimal("37"))
            self.assertFalse(result.within_risk_limit)
            self.assertEqual(result.reason_code, "RISK_REVALIDATION_FAILED")

        def test_f2_policy_still_denies_execution_and_orders(self):
            stamp = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
            context = Context(phase=5, account_mode="DEMO")
            for operation in ("DEMO_EXECUTION", "ORDER_CHECK", "ORDER_SEND", "ORDER_MODIFY", "ORDER_CLOSE",
                              "LIVE_EXECUTION", "LIVE_ORDER_SEND", "READ_BALANCE", "READ_EQUITY",
                              "READ_MARGIN", "READ_PROFIT", "UNKNOWN"):
                request = Request("f3-independent", operation, stamp, {})
                self.assertFalse(authorize(request, context=context).allowed, operation)

        def test_only_empty_policy_status_remains_allowed(self):
            stamp = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
            context = Context(phase=5, account_mode="DEMO")
            good = Request("f3-independent", "POLICY_STATUS", stamp, {})
            bad = Request("f3-independent", "POLICY_STATUS", stamp, {"x": 1})
            self.assertTrue(authorize(good, context=context).allowed)
            self.assertFalse(authorize(bad, context=context).allowed)

    stream = __import__("io").StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryProbes)
    )
    return result, stream.getvalue()


def static_boundary(project_root: Path) -> list[str]:
    path = project_root / "src" / "guardian" / "firewall" / "risk.py"
    if not path.is_file():
        return ["F3 boundary module missing"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_imports = {
        "MetaTrader5", "socket", "requests", "urllib", "http", "ftplib",
        "subprocess", "sqlite3", "pathlib", "os", "shutil", "logging",
    }
    forbidden_names = {
        "order_send", "order_check", "send_order", "place_order", "account_info",
        "positions_get", "orders_get", "history_deals_get", "urlopen",
        "create_connection", "connect", "execute", "commit",
    }
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    findings.append("forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in forbidden_imports:
                findings.append("forbidden import-from: " + node.module)
        elif isinstance(node, ast.Name) and node.id in forbidden_names:
            findings.append("forbidden name: " + node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden_names:
            findings.append("forbidden attribute: " + node.attr)
    return sorted(set(findings))


def mutation_control(project_root: Path) -> dict:
    source = project_root / "src" / "guardian" / "firewall" / "risk.py"
    original = source.read_text(encoding="utf-8")
    anchors = (
        'if proposed_lots > safe_spec.max_lot or proposed_lots > maximum:\n            return _deny("PROPOSED_SIZE_EXCEEDS_RECOMPUTED_MAXIMUM", maximum)',
        'if proposed_risk > risk_budget:\n            return _deny("PROPOSED_RISK_EXCEEDS_BUDGET", maximum)',
    )
    if any(original.count(anchor) != 1 for anchor in anchors):
        return {"status": "BLOCK", "reason": "risk-denial mutation anchor missing/ambiguous"}
    mutant = original.replace(anchors[0], 'if False:\n            return _deny("MUTANT_SIZE_DENIAL", maximum)', 1)
    mutant = mutant.replace(anchors[1], 'if False:\n            return _deny("MUTANT_RISK_DENIAL", maximum)', 1)
    with tempfile.TemporaryDirectory(prefix="guardian-f3-mutant-") as temp:
        root = Path(temp) / "project"
        shutil.copytree(project_root / "src", root / "src")
        mutant_file = root / "src" / "guardian" / "firewall" / "risk.py"
        mutant_file.write_text(mutant, encoding="utf-8")
        result, output = blackbox(root)
        detected = not result.wasSuccessful()
        return {
            "status": "PASS" if detected else "FAIL",
            "mutant_detected": detected,
            "mutant_tests": result.testsRun,
            "mutant_failures": len(result.failures),
            "mutant_errors": len(result.errors),
            "output_tail": output[-5000:],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--frozen-root", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    project = Path(args.project_root).resolve()
    frozen = Path(args.frozen_root).resolve()
    archive = Path(args.archive).resolve()
    before = manifest(frozen)
    archive_before = hashlib.sha256(archive.read_bytes()).hexdigest()
    result, output = blackbox(project)
    findings = static_boundary(project)
    mutation = mutation_control(project)
    after = manifest(frozen)
    archive_after = hashlib.sha256(archive.read_bytes()).hexdigest()
    payload = {
        "schema": "guardian-f3-independent-inspector/v1",
        "target_commit": os.environ.get("GITHUB_SHA", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "python": sys.version,
        "blackbox": {
            "tests": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success": result.wasSuccessful(),
            "output": output,
        },
        "static_boundary_findings": findings,
        "mutation_control": mutation,
        "frozen_manifest_files": len(before),
        "frozen_manifest_stable": before == after,
        "archive_sha256_before": archive_before,
        "archive_sha256_after": archive_after,
        "archive_stable": archive_before == archive_after,
    }
    passed = (
        result.wasSuccessful() and not findings
        and mutation.get("status") == "PASS"
        and before == after and archive_before == archive_after
    )
    payload["verdict"] = "PASS" if passed else "BLOCK"
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
