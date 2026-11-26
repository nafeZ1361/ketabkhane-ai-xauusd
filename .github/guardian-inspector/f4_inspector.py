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
from decimal import Decimal


def manifest(root: Path) -> dict[str, str]:
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache", "data", "logs", "reports", "evidence"}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(p for p in root.rglob("*") if p.is_file())
        if not any(part in excluded for part in path.parts)
    }


def load_modules(project_root: Path):
    import importlib
    source = str(project_root / "src")
    sys.path[:] = [entry for entry in sys.path if entry != source]
    for name in tuple(sys.modules):
        if name == "guardian" or name.startswith("guardian."):
            del sys.modules[name]
    sys.path.insert(0, source)
    importlib.invalidate_caches()
    from guardian.firewall.ipc import (
        AuthenticatedCodec, IPCProtocolError, canonical_json, MAX_FRAME_BYTES,
    )
    from guardian.firewall.worker_host import RestrictedWorker, WorkerHostError
    from guardian.firewall.risk import revalidate_proposed_size
    from guardian.domain.risk import RiskSpec
    from guardian.contracts.firewall import FirewallRequest
    from guardian.firewall.policy import PolicyContext, authorize_request
    from guardian.firewall.ipc import _parse_canonical
    return (
        AuthenticatedCodec, IPCProtocolError, canonical_json, MAX_FRAME_BYTES,
        RestrictedWorker, WorkerHostError, revalidate_proposed_size, RiskSpec,
        FirewallRequest, PolicyContext, authorize_request, _parse_canonical,
    )


def blackbox(project_root: Path) -> tuple[unittest.result.TestResult, str]:
    (
        Codec, ProtocolError, canonical_json, max_frame, Worker, WorkerError,
        validate_risk, RiskSpec, Request, Context, authorize, parse_canonical,
    ) = load_modules(project_root)
    key = b"f" * 32
    session = "a1" * 32

    def endpoints():
        parent = Codec(
            key=key, session_id=session,
            send_direction="parent_to_worker",
            receive_direction="worker_to_parent",
        )
        worker = Codec(
            key=key, session_id=session,
            send_direction="worker_to_parent",
            receive_direction="parent_to_worker",
        )
        return parent, worker

    class F4Probes(unittest.TestCase):
        def test_authenticated_directional_round_trip(self):
            parent, worker = endpoints()
            request = worker.decode(parent.encode("HEALTH_CHECK", "c1", {}))
            self.assertEqual((request.sequence, request.correlation_id), (1, "c1"))
            response = parent.decode(worker.encode("RESULT", "c1", {"status": "OK"}))
            self.assertEqual(response.payload, {"status": "OK"})

        def test_tampered_payload_is_rejected(self):
            import json
            parent, worker = endpoints()
            envelope = json.loads(parent.encode("HEALTH_CHECK", "c1", {}))
            envelope["payload"] = {"privileged": True}
            with self.assertRaises(ProtocolError):
                worker.decode(canonical_json(envelope))

        def test_duplicate_and_stale_frames_are_rejected(self):
            parent, worker = endpoints()
            frame = parent.encode("HEALTH_CHECK", "c1", {})
            worker.decode(frame)
            with self.assertRaises(ProtocolError):
                worker.decode(frame)

        def test_sequence_gap_is_rejected_without_advancing(self):
            parent, worker = endpoints()
            first = parent.encode("HEALTH_CHECK", "c1", {})
            second = parent.encode("HEALTH_CHECK", "c2", {})
            with self.assertRaises(ProtocolError):
                worker.decode(second)
            self.assertEqual(worker.receive_sequence, 0)
            worker.decode(first)
            self.assertEqual(worker.decode(second).sequence, 2)

        def test_wrong_key_and_cross_session_are_rejected(self):
            parent, _ = endpoints()
            wrong_key = Codec(
                key=b"g" * 32, session_id=session,
                send_direction="worker_to_parent",
                receive_direction="parent_to_worker",
            )
            with self.assertRaises(ProtocolError):
                wrong_key.decode(parent.encode("HEALTH_CHECK", "c1", {}))
            other_session = Codec(
                key=key, session_id="b2" * 32,
                send_direction="worker_to_parent",
                receive_direction="parent_to_worker",
            )
            parent2, _ = endpoints()
            with self.assertRaises(ProtocolError):
                other_session.decode(parent2.encode("HEALTH_CHECK", "c2", {}))

        def test_duplicate_keys_and_noncanonical_json_are_rejected(self):
            with self.assertRaises(ProtocolError):
                parse_canonical(b'{"a":1,"a":2}')
            parent, worker = endpoints()
            import json
            frame = parent.encode("HEALTH_CHECK", "c1", {})
            pretty = json.dumps(json.loads(frame), indent=2).encode("utf-8")
            with self.assertRaises(ProtocolError):
                worker.decode(pretty)

        def test_oversized_frame_and_unknown_operation_are_rejected(self):
            from io import BytesIO
            from guardian.firewall.ipc import read_frame
            with self.assertRaises(ProtocolError):
                read_frame(BytesIO((max_frame + 1).to_bytes(4, "big")))
            parent, _ = endpoints()
            with self.assertRaises(ProtocolError):
                parent.encode("ORDER_SEND", "order", {"symbol": "XAUUSD"})

        def test_f2_policy_still_denies_execution_orders_live_and_financial_reads(self):
            stamp = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
            context = Context(phase=5, account_mode="DEMO")
            for operation in (
                "DEMO_EXECUTION", "ORDER_CHECK", "ORDER_SEND", "ORDER_MODIFY",
                "ORDER_CLOSE", "LIVE_EXECUTION", "LIVE_ORDER_SEND",
                "READ_BALANCE", "READ_EQUITY", "READ_MARGIN", "READ_PROFIT",
                "UNKNOWN",
            ):
                request = Request("f4-probe", operation, stamp, {})
                self.assertFalse(authorize(request, context=context).allowed, operation)
            status = Request("f4-status", "POLICY_STATUS", stamp, {})
            self.assertTrue(authorize(status, context=context).allowed)

        def test_f3_risk_revalidation_remains_pure_and_fail_closed(self):
            spec = RiskSpec(
                Decimal("0.01"), Decimal("1"), Decimal("0.01"),
                Decimal("0.01"), Decimal("100"),
            )
            accepted = validate_risk(
                Decimal("10000"), Decimal("100"), Decimal("0.50"), spec=spec
            )
            denied = validate_risk(
                Decimal("10000"), Decimal("100"), Decimal("1.01"), spec=spec
            )
            self.assertTrue(accepted.within_risk_limit)
            self.assertFalse(denied.within_risk_limit)

        def test_worker_os_token_job_limits_and_authenticated_operations(self):
            with Worker.launch() as worker:
                report = worker.security_report
                self.assertTrue(report["is_non_elevated"])
                self.assertEqual(report["integrity_rid"], 4096)
                self.assertLessEqual(report["privilege_count"], 1)
                self.assertTrue(report["job_limits_verified"])
                self.assertTrue(report["job_assigned"])
                self.assertEqual(worker.request("HEALTH_CHECK", {}), {"status": "OK"})
                result = worker.request("RISK_REVALIDATE", {
                    "equity": "10000",
                    "stop_points": "100",
                    "proposed_lots": "0.50",
                    "spec": {
                        "risk_fraction": "0.01",
                        "value_per_point_lot": "1",
                        "lot_step": "0.01",
                        "min_lot": "0.01",
                        "max_lot": "100",
                    },
                })
                self.assertTrue(result["within_risk_limit"])
                with self.assertRaises(WorkerError):
                    worker.request("ORDER_SEND", {"symbol": "XAUUSD"})
                with self.assertRaises(WorkerError):
                    worker.request("HEALTH_CHECK", {})

    stream = __import__("io").StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(F4Probes)
    )
    return result, stream.getvalue()


def static_boundary(project_root: Path) -> list[str]:
    files = [
        project_root / "src" / "guardian" / "firewall" / "ipc.py",
        project_root / "src" / "guardian" / "firewall" / "worker.py",
        project_root / "src" / "guardian" / "firewall" / "worker_host.py",
        project_root / "scripts" / "firewall_worker.py",
    ]
    forbidden_imports = {
        "MetaTrader5", "socket", "requests", "urllib", "http", "ftplib",
        "sqlite3", "multiprocessing", "winreg",
    }
    forbidden_names = {
        "order_send", "order_check", "send_order", "place_order",
        "account_info", "positions_get", "orders_get", "history_deals_get",
        "urlopen", "create_connection", "connect",
    }
    findings = []
    for path in files:
        if not path.is_file():
            findings.append("missing worker boundary file: " + str(path))
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_imports:
                        findings.append(f"{path.name}: forbidden import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden_imports:
                    findings.append(f"{path.name}: forbidden import-from {node.module}")
            elif isinstance(node, ast.Name) and node.id in forbidden_names:
                findings.append(f"{path.name}: forbidden name {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                findings.append(f"{path.name}: forbidden attribute {node.attr}")
            if path.name == "worker_host.py" and isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "subprocess":
                    if node.attr != "list2cmdline":
                        findings.append("worker_host.py: unexpected subprocess capability " + node.attr)
    return sorted(set(findings))


def _copy_project(source: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git", ".venv", "__pycache__", ".pytest_cache", "data",
        "logs", "reports", "evidence",
    )
    shutil.copytree(source, target, ignore=ignored)


def mutation_control(project_root: Path, name: str, relative_path: str, old: str, new: str) -> dict:
    source_file = project_root / relative_path
    original = source_file.read_text(encoding="utf-8")
    if original.count(old) != 1:
        return {"status": "BLOCK", "reason": name + ": mutation anchor missing/ambiguous"}
    with tempfile.TemporaryDirectory(prefix="guardian-f4-mutant-") as temp:
        root = Path(temp) / "project"
        _copy_project(project_root, root)
        target = root / relative_path
        target.write_text(target.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
        result, output = blackbox(root)
        detected = not result.wasSuccessful()
        return {
            "status": "PASS" if detected else "FAIL",
            "mutant": name,
            "mutant_detected": detected,
            "probes": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "output_tail": output[-3500:],
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
    mutations = [
        mutation_control(
            project, "HMAC verification disabled",
            "src/guardian/firewall/ipc.py",
            "if not hmac.compare_digest(tag, expected_tag):",
            "if False:",
        ),
        mutation_control(
            project, "sequence/replay check disabled",
            "src/guardian/firewall/ipc.py",
            "if type(sequence) is not int or sequence != self._receive_sequence + 1:",
            "if False:",
        ),
        mutation_control(
            project, "Low-integrity process restriction disabled",
            "src/guardian/firewall/worker_host.py",
            "if not advapi32.SetTokenInformation(",
            "if False and not advapi32.SetTokenInformation(",
        ),
    ]

    after = manifest(frozen)
    archive_after = hashlib.sha256(archive.read_bytes()).hexdigest()
    payload = {
        "schema": "guardian-f4-independent-inspector/v1",
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
        "mutation_controls": mutations,
        "frozen_manifest_files": len(before),
        "frozen_manifest_stable": before == after,
        "archive_sha256_before": archive_before,
        "archive_sha256_after": archive_after,
        "archive_stable": archive_before == archive_after,
    }
    passed = (
        result.wasSuccessful() and not findings
        and len(mutations) == 3
        and all(item.get("status") == "PASS" for item in mutations)
        and before == after and archive_before == archive_after
    )
    payload["verdict"] = "PASS" if passed else "BLOCK"
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
