from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


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
    sys.path.insert(0, source)
    importlib.invalidate_caches()
    from guardian.firewall.ipc import AuthenticatedSession, IPCError
    from guardian.firewall.launcher import RestrictedWorkerLauncher, WorkerLaunchError
    from guardian.firewall.worker_security import verify_current_worker_token
    return AuthenticatedSession, IPCError, RestrictedWorkerLauncher, WorkerLaunchError, verify_current_worker_token


def blackbox(project_root: Path) -> tuple[unittest.result.TestResult, str]:
    Session, IPCError, Launcher, LaunchError, verify_token = load_modules(project_root)

    class F4Probes(unittest.TestCase):
        def test_replay_is_rejected(self):
            a = Session(b"k" * 32, b"n" * 16)
            b = Session(b"k" * 32, b"n" * 16)
            frame = a.encode({"type": "hello"})
            self.assertEqual(b.decode(frame[4:]), {"type": "hello"})
            with self.assertRaisesRegex(IPCError, "replayed"):
                b.decode(frame[4:])

        def test_forgery_is_rejected(self):
            a = Session(b"k" * 32, b"n" * 16)
            b = Session(b"x" * 32, b"n" * 16)
            frame = a.encode({"type": "hello"})
            with self.assertRaisesRegex(IPCError, "authentication"):
                b.decode(frame[4:])

        def test_wrong_nonce_is_rejected(self):
            a = Session(b"k" * 32, b"n" * 16)
            b = Session(b"k" * 32, b"m" * 16)
            frame = a.encode({"type": "hello"})
            with self.assertRaisesRegex(IPCError, "nonce"):
                b.decode(frame[4:])

        def test_malformed_envelope_is_rejected(self):
            a = Session(b"k" * 32, b"n" * 16)
            with self.assertRaisesRegex(IPCError, "unexpected IPC fields"):
                a.decode(b'{"v":1}')

        def test_worker_token_is_restricted_on_windows(self):
            if os.name != "nt":
                self.skipTest("Windows-only F4 token probe")
            report = verify_token()
            self.assertTrue(report.restricted)
            self.assertLess(report.integrity_rid, 0x3000)

        def test_restricted_worker_lifecycle(self):
            if os.name != "nt":
                self.skipTest("Windows-only F4 lifecycle probe")
            handle = Launcher().start(timeout=10)
            try:
                self.assertGreater(handle.pid, 0)
            finally:
                Launcher.shutdown(handle, timeout=5)

        def test_non_windows_launcher_fails_closed(self):
            if os.name == "nt":
                self.skipTest("Windows-only negative control")
            with self.assertRaises(LaunchError):
                Launcher().start(timeout=0.1)

    stream = __import__("io").StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(F4Probes)
    )
    return result, stream.getvalue()


def static_boundary(project_root: Path) -> list[str]:
    paths = [
        project_root / "src/guardian/firewall/ipc.py",
        project_root / "src/guardian/firewall/worker.py",
        project_root / "src/guardian/firewall/worker_security.py",
        project_root / "src/guardian/firewall/launcher.py",
    ]
    forbidden_imports = {"MetaTrader5", "requests", "urllib", "http", "ftplib", "sqlite3"}
    forbidden_names = {
        "order_send", "order_check", "send_order", "place_order",
        "account_info", "positions_get", "orders_get", "history_deals_get",
    }
    findings = []
    for path in paths:
        if not path.is_file():
            findings.append("missing boundary module: " + path.name)
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
    return sorted(set(findings))


def mutation_control(project_root: Path) -> dict:
    source = project_root / "src/guardian/firewall/ipc.py"
    original = source.read_text(encoding="utf-8")
    anchor = "if not hmac.compare_digest(expected, supplied):\n            raise IPCError(\"IPC authentication failed\")"
    if original.count(anchor) != 1:
        return {"status": "BLOCK", "reason": "authentication mutation anchor missing/ambiguous"}
    mutant = original.replace(anchor, "if False:\n            raise IPCError(\"MUTANT_AUTH_BYPASS\")", 1)
    with tempfile.TemporaryDirectory(prefix="guardian-f4-mutant-") as temp:
        root = Path(temp) / "project"
        shutil.copytree(project_root / "src", root / "src")
        mf = root / "src/guardian/firewall/ipc.py"
        mf.write_text(mutant, encoding="utf-8")
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
        "mutation_control": mutation,
        "frozen_manifest_files": len(before),
        "frozen_manifest_stable": before == after,
        "archive_sha256_before": archive_before,
        "archive_sha256_after": archive_after,
        "archive_stable": archive_before == archive_after,
    }
    passed = result.wasSuccessful() and not findings and mutation.get("status") == "PASS" and before == after and archive_before == archive_after
    payload["verdict"] = "PASS" if passed else "BLOCK"
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
