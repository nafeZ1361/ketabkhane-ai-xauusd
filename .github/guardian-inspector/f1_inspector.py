from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone, tzinfo
from collections.abc import Mapping

SCHEMA_VERSION = 1
PROTOCOL = "xauusd-guardian.firewall.v1"


def file_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class ExplodingMapping(Mapping):
    def __getitem__(self, key):
        raise RuntimeError("hostile mapping access")

    def __iter__(self):
        return iter(("payload",))

    def __len__(self):
        return 1


class ChangingUTC(tzinfo):
    def __init__(self):
        self.calls = 0

    def utcoffset(self, dt):
        self.calls += 1
        return timedelta(0) if self.calls == 1 else timedelta(hours=1)

    def dst(self, dt):
        return timedelta(0)


def load_contracts(project_root: Path):
    source = project_root / "src"
    sys.path.insert(0, str(source))
    from guardian.contracts.firewall import (
        FIREWALL_PROTOCOL,
        FIREWALL_SCHEMA_VERSION,
        FirewallContractError,
        FirewallRequest,
        FirewallResponse,
    )
    return (
        FIREWALL_PROTOCOL,
        FIREWALL_SCHEMA_VERSION,
        FirewallContractError,
        FirewallRequest,
        FirewallResponse,
    )


def run_blackbox(project_root: Path) -> tuple[unittest.result.TestResult, str]:
    protocol, version, ContractError, Request, Response = load_contracts(project_root)
    stamp = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)

    def request_data():
        return {
            "schema_version": version,
            "protocol": protocol,
            "request_id": "independent-probe",
            "message_type": "INSPECT",
            "issued_at_utc": "2026-11-24T12:00:00Z",
            "payload": {"nested": {"ok": True}, "items": [1, "x"]},
        }

    def response_data():
        return {
            "schema_version": version,
            "protocol": protocol,
            "request_id": "independent-probe",
            "status": "REJECTED",
            "reason_code": "NOT_AUTHORIZED",
            "responded_at_utc": "2026-11-24T12:00:00Z",
        }

    class ContractProbes(unittest.TestCase):
        def test_valid_request_response_round_trip(self):
            req = Request.from_dict(request_data())
            res = Response.from_dict(response_data())
            self.assertEqual(Request.from_dict(req.to_dict()), req)
            self.assertEqual(Response.from_dict(res.to_dict()), res)

        def test_exact_schema_and_protocol(self):
            for invalid in (True, 1.0, "1", 0, 2, None):
                data = request_data()
                data["schema_version"] = invalid
                with self.assertRaises(ContractError):
                    Request.from_dict(data)
            data = request_data()
            data["protocol"] = "other.v1"
            with self.assertRaises(ContractError):
                Request.from_dict(data)

        def test_missing_unknown_and_non_string_fields(self):
            data = request_data()
            del data["payload"]
            with self.assertRaises(ContractError):
                Request.from_dict(data)
            data = request_data()
            data["extra"] = 1
            with self.assertRaises(ContractError):
                Request.from_dict(data)
            data[1] = "bad-key"
            with self.assertRaises(ContractError):
                Request.from_dict(data)

        def test_timestamp_must_be_explicit_iso_utc(self):
            for value in (
                "2026-11-24T12:00:00",
                "2026-11-24T12:00:00+01:00",
                "2026-11-24X12:00:00Z",
                "2026-11-24 12:00:00Z",
                123,
            ):
                data = request_data()
                data["issued_at_utc"] = value
                with self.assertRaises(ContractError):
                    Request.from_dict(data)

        def test_payload_rejects_non_json_and_non_finite_values(self):
            for value in (object(), float("nan"), float("inf"), float("-inf")):
                data = request_data()
                data["payload"] = {"bad": value}
                with self.assertRaises(ContractError):
                    Request.from_dict(data)

        def test_payload_rejects_bad_keys_depth_cycles_and_subclasses(self):
            bad_key = request_data()
            bad_key["payload"] = {1: "bad"}
            with self.assertRaises(ContractError):
                Request.from_dict(bad_key)
            deep = {}
            cursor = deep
            for _ in range(66):
                cursor["x"] = {}
                cursor = cursor["x"]
            data = request_data()
            data["payload"] = deep
            with self.assertRaises(ContractError):
                Request.from_dict(data)
            cyclic = {}
            cyclic["self"] = cyclic
            data["payload"] = cyclic
            with self.assertRaises(ContractError):
                Request.from_dict(data)

            class StrangeList(list):
                pass

            data["payload"] = {"bad": StrangeList([1])}
            with self.assertRaises(ContractError):
                Request.from_dict(data)

        def test_payload_is_detached_deeply_immutable_and_exported_copy_is_fresh(self):
            original = {"nested": {"items": [1, {"ok": True}]}}
            req = Request("id", "TEST", stamp, original)
            original["nested"]["items"][1]["ok"] = False
            exported = req.to_dict()
            self.assertTrue(exported["payload"]["nested"]["items"][1]["ok"])
            exported["payload"]["nested"]["items"].append("changed")
            self.assertTrue(req.to_dict()["payload"]["nested"]["items"][1]["ok"])
            with self.assertRaises(TypeError):
                req.payload["new"] = "blocked"
            with self.assertRaises(AttributeError):
                req.payload["nested"]["items"].append(2)

        def test_hostile_mappings_fail_closed(self):
            with self.assertRaises(ContractError):
                Request("id", "TEST", stamp, ExplodingMapping())
            with self.assertRaises(ContractError):
                Request.from_dict(ExplodingMapping())
            with self.assertRaises(ContractError):
                Response.from_dict(ExplodingMapping())

        def test_mutable_timezone_is_snapshotted_once(self):
            hostile = ChangingUTC()
            req = Request("id", "TEST", datetime(2026, 11, 24, 12, 0, tzinfo=hostile), {})
            self.assertEqual(hostile.calls, 1)
            self.assertIs(req.issued_at_utc.tzinfo, timezone.utc)
            self.assertTrue(req.to_dict()["issued_at_utc"].endswith("Z"))
            self.assertEqual(hostile.calls, 1)

        def test_to_dict_revalidates_injected_state(self):
            req = Request("id", "TEST", stamp, {"ok": True})
            object.__setattr__(req, "request_id", "")
            with self.assertRaises(ContractError):
                req.to_dict()
            res = Response("id", "REJECTED", "NO_AUTH", stamp)
            object.__setattr__(res, "reason_code", "")
            with self.assertRaises(ContractError):
                res.to_dict()

        def test_response_rejects_missing_unknown_and_bad_timestamp(self):
            data = response_data()
            del data["reason_code"]
            with self.assertRaises(ContractError):
                Response.from_dict(data)
            data = response_data()
            data["unexpected"] = True
            with self.assertRaises(ContractError):
                Response.from_dict(data)
            data = response_data()
            data["responded_at_utc"] = "2026-11-24T12:00:00"
            with self.assertRaises(ContractError):
                Response.from_dict(data)

    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContractProbes)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return result, stream.getvalue()


def static_boundary_check(project_root: Path) -> list[str]:
    path = project_root / "src" / "guardian" / "contracts" / "firewall.py"
    if not path.is_file():
        return ["F1 contract module missing"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = {"MetaTrader5", "order_send", "order_check", "socket", "requests", "urlopen"}
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden:
                    findings.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in forbidden:
                findings.append(f"forbidden import: {node.module}")
        elif isinstance(node, ast.Name) and node.id in forbidden:
            findings.append(f"forbidden name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            findings.append(f"forbidden attribute: {node.attr}")
    return sorted(set(findings))


def mutation_control(project_root: Path) -> dict:
    source = project_root / "src" / "guardian" / "contracts" / "firewall.py"
    original = source.read_text(encoding="utf-8")
    good = "schema_version != FIREWALL_SCHEMA_VERSION"
    mutant = "schema_version == FIREWALL_SCHEMA_VERSION"
    if original.count(good) != 1:
        return {"status": "BLOCK", "reason": "mutation anchor missing or ambiguous"}
    with tempfile.TemporaryDirectory(prefix="guardian-f1-mutant-") as temp:
        root = Path(temp) / "project"
        shutil.copytree(project_root / "src" / "guardian", root / "src" / "guardian")
        mutant_file = root / "src" / "guardian" / "contracts" / "firewall.py"
        mutant_file.write_text(original.replace(good, mutant, 1), encoding="utf-8")
        script = Path(__file__).resolve()
        run = subprocess.run(
            [sys.executable, str(script), "--project-root", str(root), "--blackbox-only"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
        detected = run.returncode != 0
        return {
            "status": "PASS" if detected else "FAIL",
            "mutant_exit_code": run.returncode,
            "mutant_detected": detected,
            "output_tail": run.stdout[-4000:],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--frozen-root")
    parser.add_argument("--output")
    parser.add_argument("--blackbox-only", action="store_true")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    result, test_output = run_blackbox(project_root)
    if args.blackbox_only:
        print(test_output)
        return 0 if result.wasSuccessful() else 1

    findings = static_boundary_check(project_root)
    mutation = mutation_control(project_root)
    frozen_manifest = None
    if args.frozen_root:
        frozen_manifest = file_manifest(Path(args.frozen_root).resolve())

    payload = {
        "schema": "guardian-f1-independent-inspector/v1",
        "target_commit": os.environ.get("GITHUB_SHA", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "python": sys.version,
        "blackbox": {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success": result.wasSuccessful(),
            "output": test_output,
        },
        "static_boundary_findings": findings,
        "mutation_control": mutation,
        "frozen_manifest": frozen_manifest,
        "status": "PASS" if result.wasSuccessful() and not findings and mutation["status"] == "PASS" else "BLOCK",
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
