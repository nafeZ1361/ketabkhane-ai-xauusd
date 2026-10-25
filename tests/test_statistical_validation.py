"""Acceptance tests for the A2.5 statistical validation layer.

Covers Charter v2.0 section 14 acceptance tests:
- AT-STAT-01 pure noise must not pass PBO gate
- AT-STAT-02 a known planted edge must be detected
- AT-STAT-03 signal shift / leakage guard on splits
- AT-STAT-04 reproducibility under fixed seed
- AT-STAT-05 ledger tampering => integrity failure
Plus contract tests for gates.yaml parsing and the JSON output shape.
"""

import json
import math
import random

import sys
from pathlib import Path

import pytest

from validation.gates import config_hash, evaluate, load_gates
from validation.ledger import GENESIS_HASH, Ledger, LedgerError, record_hash
from validation.metrics import (
    block_bootstrap_ci,
    cscv_pbo,
    deflated_sharpe_ratio,
    expected_max_sr,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)
from validation.splits import walk_forward


# ---------------------------------------------------------------- fixtures
def _noise_matrix(m=8, slices=16, seed=7):
    rng = random.Random(seed)  # one stream: independent draws everywhere
    return [[rng.gauss(0.0, 1.0) for _ in range(slices)] for _ in range(m)]


def _edge_matrix(m=8, slices=16, seed=7, edge_index=0, edge_strength=3.0):
    rng = random.Random(seed)
    matrix = []
    for s in range(m):
        mu = edge_strength if s == edge_index else 0.0
        matrix.append([rng.gauss(mu, 1.0) for _ in range(slices)])
    return matrix


# ------------------------------------------------------------------ ledger
def test_ledger_chain_and_genesis(tmp_path):
    path = tmp_path / "experiments.jsonl"
    ledger = Ledger(path)
    first = ledger.append({"strategy": "ma_10_50", "net_pnl": 12.5})
    assert first["seq"] == 1
    assert first["prev_hash"] == GENESIS_HASH
    second = ledger.append({"strategy": "ma_20_100", "net_pnl": -3.25})
    assert second["prev_hash"] == first["record_hash"]
    report = ledger.verify()
    assert report["intact"] is True
    assert report["records"] == 2


def test_ledger_rejects_reserved_fields(tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError):
        ledger.append({"seq": 99, "strategy": "x"})


def test_at_stat_05_deleted_record_breaks_chain(tmp_path):
    """AT-STAT-05: removing one ledger line must be reported as corruption."""
    path = tmp_path / "experiments.jsonl"
    ledger = Ledger(path)
    for i in range(5):
        ledger.append({"strategy": f"s{i}", "value": i})
    assert ledger.verify()["intact"] is True
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[2]  # drop the middle record
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = Ledger(path).verify()
    assert report["intact"] is False
    assert any("prev_hash" in issue for issue in report["issues"])


def test_at_stat_05_edited_record_breaks_chain(tmp_path):
    """AT-STAT-05 variant: editing content without rehashing is detected."""
    path = tmp_path / "experiments.jsonl"
    ledger = Ledger(path)
    ledger.append({"strategy": "honest", "value": 1})
    rec = ledger.append({"strategy": "target", "value": 2})
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["value"] = 999  # content edit; hash NOT recomputed
    lines[1] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = Ledger(path).verify()
    assert report["intact"] is False
    assert any("record_hash mismatch" in issue for issue in report["issues"])
    assert rec["record_hash"] != record_hash(tampered)


# ------------------------------------------------------------------ metrics
def test_psr_direction():
    rng = random.Random(1)
    positive_edge = [rng.gauss(0.5, 1.0) for _ in range(200)]
    rng = random.Random(200)
    zero_edge = [rng.gauss(0.0, 1.0) for _ in range(200)]
    assert probabilistic_sharpe_ratio(positive_edge) > 0.95
    # under the true null (mean exactly zero), PSR must not certify an edge:
    # its value stays far from the 0.95 acceptance level.
    assert probabilistic_sharpe_ratio(zero_edge) < 0.90


def test_psr_rejects_constant_series():
    with pytest.raises(ValueError):
        probabilistic_sharpe_ratio([1.0] * 50)
    with pytest.raises(ValueError):
        probabilistic_sharpe_ratio([0.1, 0.2, 0.3])


def test_expected_max_sr_increases_with_trials():
    assert expected_max_sr(10) > expected_max_sr(4) > expected_max_sr(2) >= 0.0


def test_dsr_inactive_below_two_trials():
    assert deflated_sharpe_ratio([0.5]) is None
    assert deflated_sharpe_ratio([]) is None


def test_block_bootstrap_contains_point_estimate():
    rng = random.Random(3)
    series = [rng.gauss(1.0, 2.0) for _ in range(500)]
    ci = block_bootstrap_ci(series, lambda xs: sum(xs) / len(xs),
                            block_size=60, samples=400, seed=42)
    assert ci["lower"] <= ci["point"] <= ci["upper"]
    assert ci["seed"] == 42


# ------------------------------------------------------- AT-STAT acceptance
def test_at_stat_01_noise_does_not_pass():
    """AT-STAT-01: pure noise across strategies must yield high PBO."""
    result = cscv_pbo(_noise_matrix(m=8, slices=16, seed=11), groups=16)
    assert result is not None
    assert result["pbo"] > 0.5, f"noise PBO unexpectedly low: {result}"


def test_at_stat_02_planted_edge_is_detected():
    """AT-STAT-02: one clearly better strategy should keep PBO low-ish."""
    result = cscv_pbo(_edge_matrix(m=8, slices=16, seed=13, edge_strength=5.0),
                      groups=16)
    assert result is not None
    assert result["pbo"] < 0.30, f"planted edge missed: {result}"


def test_at_stat_03_split_leakage_guard():
    """AT-STAT-03: purge+embargo must separate train end from test start."""
    splits = walk_forward(n=1000, train_size=400, test_size=100,
                          purge=10, embargo=20)
    assert splits, "expected at least one split"
    for sp in splits:
        assert sp.gap >= 30  # purge + embargo enforced
        assert sp.train_stop <= sp.test_start
        assert max(sp.train()) < min(sp.test())


def test_at_stat_04_reproducible_bootstrap():
    """AT-STAT-04: same seed => byte-identical CI numbers."""
    rng = random.Random(5)
    series = [rng.gauss(0.1, 1.0) for _ in range(300)]
    run_a = block_bootstrap_ci(series, lambda xs: sharpe_ratio(xs), seed=777,
                               samples=300)
    run_b = block_bootstrap_ci(series, lambda xs: sharpe_ratio(xs), seed=777,
                               samples=300)
    assert run_a == run_b
    run_c = block_bootstrap_ci(series, lambda xs: sharpe_ratio(xs), seed=778,
                               samples=300)
    assert (run_c["lower"], run_c["upper"]) != (run_a["lower"], run_a["upper"])


# ------------------------------------------------------------------- gates
def test_gates_yaml_parses_locked_values():
    gates = load_gates()
    assert gates["dsr"]["activation_threshold"] == 10
    assert gates["dsr"]["min_allowed"] == 0.95
    assert gates["pbo"]["max_allowed"] == 0.20
    assert gates["bootstrap"]["block_size"] == 60
    assert gates["oos"]["pristine_range"] is None


def test_config_hash_matches_locked_sha_file():
    from pathlib import Path
    digest = config_hash()
    stored = Path("validation/gates.sha256").read_text(encoding="utf-8").strip()
    assert digest == stored


def test_evaluate_small_sample_is_insufficient_not_fail():
    records = [{"seq": 1, "strategy": "ma_10_50"}]
    report = evaluate(records, {1: {"sharpe": 0.1}}, families={"ma"},
                      data_version_hash="x", seed=1)
    assert report["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert report["gates"]["dsr"]["status"] == "INACTIVE_N_TOO_SMALL"


def test_evaluate_fail_beats_insufficient():
    """A breached numeric gate must produce FAIL even if others are inactive."""
    records = [{"seq": i} for i in range(1, 11)]
    metrics = {i: {"dsr": 0.10, "pf_lower_ci": 0.8} for i in range(1, 11)}
    report = evaluate(records, metrics, families={"ma", "breakout"},
                      data_version_hash="x", seed=1)
    assert report["verdict"] == "FAIL"
    assert report["fail_reasons"]


def test_output_contract_shape():
    records = [{"seq": 1}]
    report = evaluate(records, {1: {}}, families={"ma"},
                      data_version_hash="abc", seed=42)
    for key in ("verdict", "gates", "metrics", "config_hash",
                "data_version_hash", "seed"):
        assert key in report
    assert report["verdict"] in ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE")
    json.dumps(report)  # must be JSON serializable


# ------------------------------------------------- A3 runner end-to-end smoke
def _write_mini_csv(path, rows=400, seed=11):
    """Deterministic synthetic M1-like CSV for the grid runners (fixture only)."""
    import random
    from datetime import datetime, timedelta
    rng = random.Random(seed)
    t = datetime(2026, 1, 5, 0, 0)
    path.write_text("DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL,VOL,SPREAD\n",
                    encoding="utf-8")
    price = 2000.0
    with path.open("a", encoding="utf-8") as fh:
        for _ in range(rows):
            o = price
            c = o + rng.gauss(0.0, 0.5)
            h = max(o, c) + abs(rng.gauss(0, 0.2))
            lo = min(o, c) - abs(rng.gauss(0, 0.2))
            fh.write(f"{t:%Y.%m.%d},{t:%H:%M:%S},{o:.5f},{h:.5f},{lo:.5f},"
                     f"{c:.5f},10,0,20\n")
            price = c
            t += timedelta(minutes=1)


def test_a3_breakout_runner_end_to_end(tmp_path):
    """A3 breakout runner: ledger append + chain integrity on a tiny fixture.

    The ledger path is redirected into tmp_path via --out so the real
    artifacts/ directory is never touched by tests.
    """
    import os
    import subprocess
    root = Path(__file__).resolve().parents[1]
    csv = tmp_path / "mini.csv"
    _write_mini_csv(csv)
    out_ledger = tmp_path / "ledger" / "experiments.jsonl"
    env = dict(os.environ)
    env["A3_LEDGER_PATH"] = str(out_ledger)
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "a3_breakout.py"),
         "--csv", str(csv)],
        capture_output=True, text=True, cwd=str(root),
        env={**env, "PYTHONPATH": str(root / "src")})
    assert proc.returncode == 0, proc.stderr
    assert "intact=True" in proc.stdout
    sys.path.insert(0, str(root))
    from validation.ledger import Ledger
    report = Ledger(out_ledger).verify()
    assert report["intact"] is True
    assert report["records"] >= 1
    last = Ledger(out_ledger).last_record()
    assert last["family"] == "breakout"
    assert last["is_retroactive"] is False


def test_a3_runners_refuse_missing_dataset():
    """Honesty rule: without a dataset the runners exit non-zero, no fabrication."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    for script in ("a3_grid.py", "a3_breakout.py"):
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / script),
             "--csv", str(root / "data" / "does_not_exist.csv")],
            capture_output=True, text=True, cwd=str(root),
            env={"PYTHONPATH": str(root / "src")})
        assert proc.returncode == 2, (script, proc.stdout, proc.stderr)
        assert "refusing to fabricate evidence" in proc.stderr


# ------------------------------------------------------- gates-from-ledger API
def test_build_report_from_ledger_end_to_end(tmp_path):
    """Ledger records -> contract report: N<10 and M=2 families => INSUFFICIENT."""
    ledger = Ledger(tmp_path / "l.jsonl")
    for i in range(4):
        ledger.append({"strategy": f"ma_{i}", "family": "ma",
                       "metrics": {"sharpe": 0.1, "pf_lower_ci": 0.9}})
    ledger.append({"strategy": "donchian_20_10", "family": "breakout",
                   "metrics": {"sharpe": 0.2, "pf_lower_ci": 1.1}})
    from validation.gates import build_report_from_ledger
    report = build_report_from_ledger(ledger, data_version_hash="h", seed=3)
    assert report["verdict"] == "INSUFFICIENT_EVIDENCE"   # DSR inactive at N=5<10
    assert report["gates"]["dsr"]["status"] == "INACTIVE_N_TOO_SMALL"
    # PBO sees two families but no pbo metric supplied -> MISSING_METRIC, still insufficient
    assert report["gates"]["pbo"]["status"] in ("MISSING_METRIC", "INACTIVE_M_LESS_THAN_2")
    json.dumps(report)


def test_gates_cli_renders_contract(tmp_path):
    """python -m validation.gates --ledger ... --out ... writes the JSON contract."""
    import os
    import subprocess
    root = Path(__file__).resolve().parents[1]
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append({"strategy": "s", "family": "ma", "metrics": {}})
    out = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, "-m", "validation.gates", "--ledger", str(tmp_path / "l.jsonl"),
         "--out", str(out)],
        capture_output=True, text=True, cwd=str(root),
        env={**os.environ, "PYTHONPATH": f"{root}:{root / 'src'}"})
    assert proc.returncode == 0, proc.stderr
    loaded = json.loads(out.read_text(encoding="utf-8"))
    for key in ("verdict", "gates", "metrics", "config_hash",
                "data_version_hash", "seed"):
        assert key in loaded
