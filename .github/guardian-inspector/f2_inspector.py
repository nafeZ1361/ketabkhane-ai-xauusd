from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime, timezone


def manifest(root: Path) -> dict[str, str]:
    result = {}
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if any(part in excluded for part in path.parts):
            continue
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def load_policy(project_root: Path):
    import sys
    source = str(project_root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from guardian.contracts.firewall import FirewallRequest
    from guardian.firewall.policy import PolicyContext, authorize_request
    return FirewallRequest, PolicyContext, authorize_request


def blackbox(project_root: Path) -> tuple[unittest.result.TestResult, str]:
    Request, Context, authorize = load_policy(project_root)
    stamp = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    good_context = Context(phase=5, account_mode="DEMO")

    def req(operation="POLICY_STATUS", payload=None):
        return Request(
            request_id="independent-f2-probe",
            message_type=operation,
            issued_at_utc=stamp,
            payload={} if payload is None else payload,
        )

    class PolicyProbes(unittest.TestCase):
        def test_only_empty_policy_status_is_allowed(self):
            result = authorize(req(), context=good_context)
            self.assertIs(result.allowed, True)
            self.assertEqual(result.reason_code, "POLICY_STATUS_ONLY")

        def test_demo_execution_and_order_operations_are_denied(self):
            for operation in ("DEMO_EXECUTION", "ORDER_CHECK", "ORDER_SEND", "ORDER_MODIFY", "ORDER_CLOSE"):
                with self.subTest(operation=operation):
                    result = authorize(req(operation), context=good_context)
                    self.assertIs(result.allowed, False)

        def test_live_operations_are_denied(self):
            for operation in ("LIVE_EXECUTION", "LIVE_ORDER_SEND"):
                with self.subTest(operation=operation):
                    result = authorize(req(operation), context=good_context)
                    self.assertIs(result.allowed, False)

        def test_account_financial_reads_are_denied(self):
            for operation in ("ACCOUNT_FINANCIAL_READ", "READ_BALANCE", "READ_EQUITY", "READ_MARGIN", "READ_PROFIT"):
                with self.subTest(operation=operation):
                    result = authorize(req(operation), context=good_context)
                    self.assertIs(result.allowed, False)

        def test_unknown_operation_is_denied(self):
            result = authorize(req("UNRECOGNIZED_OPERATION"), context=good_context)
            self.assertIs(result.allowed, False)

        def test_status_payload_must_be_empty(self):
            for payload in ({"include_secrets": True}, {"account": "demo"}, {"x": 0}):
                result = authorize(req("POLICY_STATUS", payload), context=good_context)
                self.assertIs(result.allowed, False)

        def test_wrong_phase_is_denied(self):
            for phase in (4, 6, 0, -1, True, 5.0):
                result = authorize(req(), context=Context(phase=phase, account_mode="DEMO"))
                self.assertIs(result.allowed, False)

        def test_wrong_account_mode_is_denied(self):
            for mode in ("LIVE", "CONTEST", "demo", "", None, 1):
                result = authorize(req(), context=Context(phase=5, account_mode=mode))
                self.assertIs(result.allowed, False)

        def test_invalid_context_and_request_types_are_denied(self):
            self.assertFalse(authorize(req(), context=object()).allowed)
            self.assertFalse(authorize(object(), context=good_context).allowed)

        def test_request_schema_tampering_is_denied(self):
            item = req()
            object.__setattr__(item, "schema_version", True)
            self.assertFalse(authorize(item, context=good_context).allowed)

        def test_privileged_operation_injection_is_denied(self):
            item = req()
            object.__setattr__(item, "message_type", "ORDER_SEND")
            self.assertFalse(authorize(item, context=good_context).allowed)

        def test_non_json_payload_injection_is_denied(self):
            item = req()
            object.__setattr__(item, "payload", {"unsafe": object()})
            self.assertFalse(authorize(item, context=good_context).allowed)

        def test_protocol_tampering_is_denied(self):
            item = req()
            object.__setattr__(item, "protocol", "untrusted.protocol")
            self.assertFalse(authorize(item, context=good_context).allowed)

        def test_a09_does_not_transfer_phase12_grant_to_phase5(self):
            for operation in ("DEMO_EXECUTION", "ORDER_SEND", "LIVE_ORDER_SEND"):
                self.assertFalse(authorize(req(operation), context=good_context).allowed)

        def test_decision_is_immutable_and_request_is_unchanged(self):
            item = req()
            before = item.to_dict()
            decision = authorize(item, context=good_context)
            self.assertEqual(item.to_dict(), before)
            with self.assertRaises((AttributeError, TypeError)):
                decision.allowed = False

    stream = __import__("io").StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PolicyProbes)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return result, stream.getvalue()


def static_boundary(project_root: Path) -> list[str]:
    path = project_root / "src" / "guardian" / "firewall" / "policy.py"
    if not path.is_file():
        return ["central policy module missing"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_imports = {
        "MetaTrader5", "socket", "requests", "urllib", "http", "ftplib",
        "subprocess", "sqlite3", "pathlib", "os", "shutil",
    }
    forbidden_names = {
        "order_send", "order_check", "send_order", "place_order",
        "urlopen", "create_connection", "connect", "execute", "commit",
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
    source = project_root / "src" / "guardian" / "firewall" / "policy.py"
    original = source.read_text(encoding="utf-8")
    anchor = "if operation in _EXECUTION_OPERATIONS:"
    mutant = "if False and operation in _EXECUTION_OPERATIONS:"
    if original.count(anchor) != 1:
        return {"status": "BLOCK", "reason": "execution-denial mutation anchor missing/ambiguous"}
    with tempfile.TemporaryDirectory(prefix="guardian-f2-mutant-") as temp:
        root = Path(temp) / "project"
        shutil.copytree(project_root / "src", root / "src")
        mutant_file = root / "src" / "guardian" / "firewall" / "policy.py"
        mutant_file.write_text(original.replace(anchor, mutant, 1), encoding="utf-8")
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
        "schema": "guardian-f2-independent-inspector/v1",
        "target_commit": os.environ.get("GITHUB_SHA", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "python": __import__("sys").version,
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
