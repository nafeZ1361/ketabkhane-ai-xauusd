from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile


def run(cmd, cwd, timeout=300):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--target-commit", required=True)
    a = ap.parse_args()
    root = pathlib.Path(a.project_root)
    result = {"schema": "guardian-f5-independent-inspection/v2", "verdict": "BLOCK", "checks": {}}

    test_path = root / "tests" / "unit" / "test_firewall_kill_switch.py"
    result["checks"]["source_probe"] = {
        "cwd": str(root),
        "test_exists": test_path.exists(),
        "test_path": str(test_path),
        "test_sha256": hashlib.sha256(test_path.read_bytes()).hexdigest() if test_path.exists() else None,
        "test_excerpt": test_path.read_text(encoding="utf-8").splitlines()[48:63] if test_path.exists() else [],
    }
    code, out, err = run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
         "tests/unit/test_firewall_kill_switch.py"],
        root,
    )
    result["checks"]["focused"] = {"exit": code, "stdout_tail": out[-5000:], "stderr_tail": err[-2000:]}
    if code != 0:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    code, out, err = run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"],
        root,
    )
    result["checks"]["full"] = {"exit": code, "stdout_tail": out[-5000:], "stderr_tail": err[-2000:]}
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

    mutant_dir = pathlib.Path(tempfile.mkdtemp(prefix="guardian-f5-mutant-"))
    mutant = mutant_dir / "kill_switch.py"
    mutated = source.replace("return _invalid()", "return KillSwitchState(_VERSION, _CLEAR, 1, 'MUTANT')", 1)
    mutant.write_text(mutated, encoding="utf-8")
    probe = mutant_dir / "probe.py"
    probe.write_text(
        "import importlib.util, pathlib\n"
        "p=pathlib.Path(__file__).with_name('kill_switch.py')\n"
        "s=importlib.util.spec_from_file_location('mutant_ks',p)\n"
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "assert m.KillSwitchStore(pathlib.Path(__file__).with_name('missing.json')).is_active() is True\n",
        encoding="utf-8",
    )
    code, out, err = run([str(root / ".venv" / "Scripts" / "python.exe"), str(probe)], mutant_dir)
    mutation_detected = code != 0
    result["checks"]["mutation"] = {
        "mutant_created": True,
        "probe_exit": code,
        "control_detected": mutation_detected,
        "stdout_tail": out[-2000:],
        "stderr_tail": err[-2000:],
    }
    shutil.rmtree(mutant_dir, ignore_errors=True)
    if not mutation_detected:
        pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    result["verdict"] = "PASS"
    pathlib.Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
