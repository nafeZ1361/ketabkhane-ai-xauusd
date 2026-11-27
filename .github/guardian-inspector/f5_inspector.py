from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile


def run(cmd, cwd, timeout=180):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def manifest(root: pathlib.Path):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--frozen-root", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    root = pathlib.Path(a.project_root)
    frozen = pathlib.Path(a.frozen_root)
    result = {
        "schema": "guardian-f5-independent-inspection/v1",
        "target": str(root),
        "checks": {},
        "verdict": "BLOCK",
    }

    before = manifest(frozen)
    code, out, err = run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
         "tests/unit/test_firewall_kill_switch.py"],
        root,
    )
    result["checks"]["focused"] = {"exit": code, "stdout_tail": out[-4000:], "stderr_tail": err[-2000:]}
    if code != 0:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    code, out, err = run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"],
        root,
        timeout=300,
    )
    result["checks"]["full"] = {"exit": code, "stdout_tail": out[-4000:], "stderr_tail": err[-2000:]}
    if code != 0:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    code, out, err = run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "compileall", "-q", "src", "scripts", "tests"],
        root,
    )
    result["checks"]["compileall"] = {"exit": code, "stdout_tail": out[-2000:], "stderr_tail": err[-1000:]}
    if code != 0:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    source = (root / "src" / "guardian" / "firewall" / "kill_switch.py").read_text(encoding="utf-8")
    forbidden = ("order_send", "order_check", "MetaTrader5", "READ_BALANCE", "A-04", "LIVE_EXECUTION")
    findings = [x for x in forbidden if x in source]
    result["checks"]["static"] = {"forbidden_findings": findings}
    if findings:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    target = root / "src" / "guardian" / "firewall" / "kill_switch.py"
    original = target.read_text(encoding="utf-8")
    mutated = original.replace("return _invalid()", "return KillSwitchState(_VERSION, _CLEAR, 1, 'MUTANT')", 1)
    if mutated == original:
        result["checks"]["mutation"] = {"mutant_created": False, "control_detected": False}
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1
    target.write_text(mutated, encoding="utf-8")
    try:
        code, out, err = run(
            [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
             "tests/unit/test_firewall_kill_switch.py"],
            root,
        )
    finally:
        target.write_text(original, encoding="utf-8")
    mutation_detected = code != 0
    result["checks"]["mutation"] = {
        "mutant_created": True,
        "mutant_test_exit": code,
        "control_detected": mutation_detected,
        "stdout_tail": out[-3000:],
        "stderr_tail": err[-1500:],
    }
    if not mutation_detected:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    after = manifest(frozen)
    result["checks"]["manifest"] = {
        "files_before": len(before),
        "files_after": len(after),
        "stable": before == after,
    }
    result["checks"]["archive_sha256"] = hashlib.sha256(pathlib.Path(a.archive).read_bytes()).hexdigest()
    result["verdict"] = "PASS" if before == after else "BLOCK"
    pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
