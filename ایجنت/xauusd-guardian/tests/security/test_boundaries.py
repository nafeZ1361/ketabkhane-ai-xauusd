"""Boundary tests — the security envelope of Phase 1.

These are static (AST / source) checks, so they run without MT5 and without a
terminal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

FORBIDDEN_CALLS = {"order_send", "order_check", "order_calc_margin", "order_calc_profit"}
ADAPTER_MARKER = "adapters"
SCAN_ROOTS = ("src", "scripts")


def _python_files(root: Path):
    for base in SCAN_ROOTS:
        directory = root / base
        if not directory.exists():
            continue
        yield from sorted(directory.rglob("*.py"))


def test_no_forbidden_trade_calls_anywhere(project_root):
    offenders: list[str] = []
    for path in _python_files(project_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if name in FORBIDDEN_CALLS:
                    offenders.append(f"{path}:{node.lineno} calls {name}")
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CALLS:
                offenders.append(f"{path}:{node.lineno} references {node.attr}")
    assert offenders == [], "forbidden trade calls found: " + "; ".join(offenders)


def _imports_metatrader5(tree: ast.AST) -> bool:
    """True if the module really imports MetaTrader5 (import, from-import, or importlib)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "MetaTrader5" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "MetaTrader5":
                return True
        elif isinstance(node, ast.Call):
            func = node.func
            if getattr(func, "attr", None) == "import_module" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and first.value == "MetaTrader5":
                    return True
    return False


def test_metatrader5_import_is_confined_to_adapters(project_root):
    offenders: list[str] = []
    for path in _python_files(project_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not _imports_metatrader5(tree):
            continue
        if ADAPTER_MARKER not in path.parts:
            offenders.append(str(path))
    assert offenders == [], "MetaTrader5 imported outside adapters: " + ", ".join(offenders)


def test_adapters_never_touch_sensitive_account_fields(project_root):
    adapter = project_root / "src" / "guardian" / "adapters" / "mt5_readonly.py"
    tree = ast.parse(adapter.read_text(encoding="utf-8"), filename=str(adapter))
    sensitive = {"balance", "equity", "margin", "margin_free", "margin_level", "profit", "credit"}
    touched = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in sensitive
    }
    assert touched == set()


def test_no_live_trading_flags_in_config(project_root):
    config = (project_root / "configs" / "config.toml").read_text(encoding="utf-8").lower()
    for banned in ("live_mode", "allow_live", "live_trading = true", "force_live"):
        assert banned not in config


def test_engine_modules_do_not_import_adapters():
    """Layer rule: domain/contracts/config must not depend on adapters."""
    root = Path(__file__).resolve().parents[2] / "src" / "guardian"
    for layer in ("domain", "contracts", "config"):
        for path in (root / layer).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "guardian.adapters" not in source, f"{path} depends on adapters"
