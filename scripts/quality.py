"""Run the test suite and measure line coverage of the core modules (stdlib only)."""

from __future__ import annotations

import dis
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

THRESHOLD = 0.80
HITS: dict[str, set[int]] = {}


def _key(filename: str) -> str:
    return os.path.normcase(os.path.abspath(filename))


def _tracer(frame, event, arg):
    if event == "line":
        HITS.setdefault(_key(frame.f_code.co_filename), set()).add(frame.f_lineno)
    return _tracer


def executable_lines(path: Path) -> set[int]:
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    lines: set[int] = set()
    stack = [code]
    while stack:
        current = stack.pop()
        for _, lineno in dis.findlinestarts(current):
            lines.add(lineno)
        for const in current.co_consts:
            if hasattr(const, "co_code"):
                stack.append(const)
    lines.discard(0)
    return lines


def main() -> int:
    sys.settrace(_tracer)
    try:
        suite = unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        sys.settrace(None)

    rows = []
    total_hit = total_lines = 0
    for path in sorted((SRC / "xauusd_research").glob("*.py")):
        lines = executable_lines(path)
        hit = HITS.get(_key(str(path)), set())
        covered = len(lines & hit)
        missing = sorted(lines - hit)
        total_hit += covered
        total_lines += len(lines)
        rows.append((path.name, covered, len(lines), missing))

    total = total_hit / total_lines if total_lines else 1.0
    report = ["# Coverage report (line coverage, stdlib tracer)", "",
              "| module | covered | statements | missing lines |", "|---|---|---|---|"]
    for name, covered, lines, missing in rows:
        preview = ", ".join(str(n) for n in missing[:12])
        report.append(f"| {name} | {covered} | {lines} | {preview} |")
    report.append(f"| **total** | **{total_hit}** | **{total_lines}** | |")
    report += ["",
               f"- total coverage: {total:.2%}",
               f"- threshold: {THRESHOLD:.0%}",
               f"- tests: {result.testsRun}, failures: {len(result.failures)}, errors: {len(result.errors)}"]
    text = "\n".join(report)
    print(text)
    out = ROOT / "docs" / "evidence" / "coverage.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    ok = not result.failures and not result.errors and total >= THRESHOLD
    print("QUALITY_GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())