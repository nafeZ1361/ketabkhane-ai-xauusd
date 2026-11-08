"""Read-only MetaTrader 5 adapter.

This is the ONLY module allowed to import ``MetaTrader5`` (see
``tests/security/test_boundaries.py``). It exposes read-only operations:
attach, symbol table, and a minimal account identity. It never reads balance,
equity, margin or profit, and it never constructs or sends an order.
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType
from typing import Any

from guardian.config.settings import APPROVED_TERMINAL_PATH
from guardian.contracts.schemas import TradeMode, SymbolSpec


class TerminalGuardError(RuntimeError):
    """Raised when the terminal is unusable or does not match the approval."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def package_version() -> str:
    """Return the MetaTrader5 package version.

    The import stays inside this module so no caller needs to import
    ``MetaTrader5`` itself (enforced by tests/security/test_boundaries.py).
    """
    return str(importlib.import_module("MetaTrader5").__version__)


class Mt5ReadOnlyAdapter:
    def __init__(
        self,
        terminal_path: str = APPROVED_TERMINAL_PATH,
        *,
        require_path_match: bool = True,
    ) -> None:
        self._terminal_path = terminal_path
        self._require_path_match = require_path_match
        self._mt5: ModuleType | None = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "Mt5ReadOnlyAdapter":
        self.attach()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.detach()

    def attach(self) -> dict[str, Any]:
        if self._mt5 is not None:
            raise TerminalGuardError("adapter already attached")
        mt5 = importlib.import_module("MetaTrader5")
        if not mt5.initialize(path=self._terminal_path):
            raise TerminalGuardError(f"initialize failed: {mt5.last_error()}")
        self._mt5 = mt5

        info = mt5.terminal_info()
        if info is None:
            self.detach()
            raise TerminalGuardError("terminal_info() returned None after attach")
        reported = str(info.path or "")
        # MT5 reports the install directory; tolerate a build that reports the exe.
        approved_dir = _norm(os.path.dirname(self._terminal_path))
        reported_variants = {_norm(reported), _norm(os.path.dirname(reported))} if reported else set()
        if self._require_path_match and approved_dir not in reported_variants:
            self.detach()
            raise TerminalGuardError(
                f"terminal path mismatch: connected to {reported!r}, approved {self._terminal_path!r}"
            )
        return {
            "terminal_path": str(info.path),
            "build": int(info.build),
            "connected": bool(info.connected),
            "trade_allowed": bool(info.trade_allowed),
        }

    def detach(self) -> None:
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            finally:
                self._mt5 = None

    def _require(self) -> ModuleType:
        if self._mt5 is None:
            raise TerminalGuardError("adapter is not attached")
        return self._mt5

    def package_version(self) -> str:
        return str(self._require().__version__)

    # -- read-only reads ---------------------------------------------------
    def symbol_specs(self) -> list[SymbolSpec]:
        mt5 = self._require()
        specs: list[SymbolSpec] = []
        for info in mt5.symbols_get() or ():
            specs.append(
                SymbolSpec(
                    name=info.name,
                    path=getattr(info, "path", "") or "",
                    description=getattr(info, "description", "") or "",
                    trade_mode=int(getattr(info, "trade_mode", 0)),
                    digits=int(getattr(info, "digits", 0)),
                    point=float(getattr(info, "point", 0.0)),
                    tick_size=float(getattr(info, "trade_tick_size", 0.0)),
                    tick_value=float(getattr(info, "trade_tick_value", 0.0)),
                    contract_size=float(getattr(info, "trade_contract_size", 0.0)),
                    volume_min=float(getattr(info, "volume_min", 0.0)),
                    volume_max=float(getattr(info, "volume_max", 0.0)),
                    volume_step=float(getattr(info, "volume_step", 0.0)),
                    stops_level=int(getattr(info, "trade_stops_level", 0)),
                    freeze_level=int(getattr(info, "trade_freeze_level", 0)),
                    filling_mode=int(getattr(info, "filling_mode", 0)),
                    currency_base=getattr(info, "currency_base", "") or "",
                    currency_profit=getattr(info, "currency_profit", "") or "",
                    visible=bool(getattr(info, "visible", False)),
                )
            )
        return specs

    def symbol_spec(self, name: str) -> SymbolSpec | None:
        mt5 = self._require()
        info = mt5.symbol_info(name)
        if info is None:
            return None
        return next((s for s in self.symbol_specs() if s.name == name), None)

    def account_identity(self) -> dict[str, str]:
        """Minimum identity fields only. No balance, equity, margin or profit."""
        mt5 = self._require()
        info = mt5.account_info()
        if info is None:
            raise TerminalGuardError("account_info() returned None; account identity unavailable")
        return {
            "trade_mode": TradeMode.from_mt5(info.trade_mode).value,
            "server": str(info.server),
            "company": str(info.company),
            "currency": str(info.currency),
            "leverage": str(info.leverage),
        }

    def symbol_spread_points(self, name: str) -> int | None:
        mt5 = self._require()
        info = mt5.symbol_info(name)
        return None if info is None else int(info.spread)
