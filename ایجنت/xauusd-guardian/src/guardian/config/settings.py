"""Strict TOML settings loader.

Fail-closed rules:
- unknown top-level or table keys are rejected;
- ``DEMO`` execution is rejected in this build (needs approval A-05);
- risk values are bounded and never silently adjusted.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from guardian.contracts.schemas import ExecutionMode
from guardian.domain.market.session import SUPPORTED_ANCHORS
from guardian.domain.symbols import IDENTITY_POLICY, KNOWN_POLICIES

APPROVED_TERMINAL_PATH = r"C:\Program Files\Aron Markets MT5\terminal64.exe"
SUPPORTED_SCHEMA_VERSION = 1

ALLOWED_EXECUTION_MODES = {ExecutionMode.DRY_RUN, ExecutionMode.SIMULATED}
#: Single source of truth lives in the domain layer (audit finding F4).
KNOWN_SYMBOL_POLICIES = KNOWN_POLICIES

_TOP_LEVEL_KEYS = {"schema_version", "execution", "account", "risk", "logging", "symbol_expectations", "market_data"}
_EXPECTATION_KEYS = {
    "schema_version",
    "aliases",
    "required_symbol_name",
    "required_path_token",
    "required_profit_currency",
    "contract_size",
    "tick_size",
    "digits",
    "require_full_trade_mode",
}


class ConfigError(ValueError):
    """Raised when configuration is missing, unknown, or unsafe."""


@dataclass(frozen=True, slots=True)
class ExecutionSettings:
    mode: ExecutionMode
    terminal_path: str
    symbol_policy: str
    require_terminal_path_match: bool


@dataclass(frozen=True, slots=True)
class AccountSettings:
    expected_trade_mode: str
    expected_server: str
    expected_company: str
    currency: str
    reject_on_mismatch: bool


@dataclass(frozen=True, slots=True)
class RiskSettings:
    risk_percent: float
    min_effective_risk_ratio: float
    max_spread_points: int
    require_stop_loss: bool


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    level: str
    redact: bool


@dataclass(frozen=True, slots=True)
class SymbolExpectationsSettings:
    """Broker profile used for metadata corroboration. Versioned on purpose."""

    schema_version: int
    aliases: tuple[str, ...]
    required_symbol_name: str | None
    required_path_token: str
    required_profit_currency: str
    contract_size: float | None
    tick_size: float | None
    digits: int | None
    require_full_trade_mode: bool


@dataclass(frozen=True, slots=True)
class SessionSettings:
    anchor: str
    week_open_weekday: int
    week_open_hour: int
    week_close_weekday: int
    week_close_hour: int
    break_start_hour: int
    break_end_hour: int
    calibrate_from_history_days: int


@dataclass(frozen=True, slots=True)
class MarketDataSettings:
    gap_tolerance_bars: int
    stale_after_bars: int
    tick_quota_gb: float
    max_tick_window_h: int
    min_bars_per_day: float
    data_root: str
    session: SessionSettings


@dataclass(frozen=True, slots=True)
class Settings:
    schema_version: int
    execution: ExecutionSettings
    account: AccountSettings
    risk: RiskSettings
    logging: LoggingSettings
    symbol_expectations: SymbolExpectationsSettings | None = None
    market_data: MarketDataSettings | None = None
    source_path: str = "<memory>"


def _table(data: Mapping[str, Any], key: str, allowed: set[str]) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ConfigError(f"[{key}] section is required")
    unknown = set(value) - allowed
    if unknown:
        raise ConfigError(f"unknown key(s) in [{key}]: {sorted(unknown)}")
    return value


def _get(table: Mapping[str, Any], key: str, expected: type, where: str) -> Any:
    if key not in table:
        raise ConfigError(f"missing key {where}.{key}")
    value = table[key]
    if not isinstance(value, expected) or isinstance(value, bool) and expected is int:
        raise ConfigError(f"{where}.{key} must be {expected.__name__}, got {type(value).__name__}")
    return value


def _require_true(table: Mapping[str, Any], key: str, where: str) -> bool:
    """Fail-closed switches cannot be turned off by configuration."""
    value = _get(table, key, bool, where)
    if value is not True:
        raise ConfigError(
            f"{where}.{key} must be true; mismatch handling is fail-closed and is not configurable"
        )
    return True


def _optional_number(table: Mapping[str, Any], key: str, where: str) -> float | None:
    if key not in table or table[key] is None:
        return None
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}.{key} must be a number")
    if value < 0:
        raise ConfigError(f"{where}.{key} must be >= 0")
    return float(value)


def _parse_expectations(data: Mapping[str, Any], policy: str) -> SymbolExpectationsSettings | None:
    table = data.get("symbol_expectations")
    if table is None:
        if policy == IDENTITY_POLICY:
            raise ConfigError(
                "[symbol_expectations] is required when execution.symbol_policy = "
                f"{IDENTITY_POLICY!r}; refusing to run with hidden defaults"
            )
        return None
    if not isinstance(table, Mapping):
        raise ConfigError("[symbol_expectations] must be a table")
    unknown = set(table) - _EXPECTATION_KEYS
    if unknown:
        raise ConfigError(f"unknown key(s) in [symbol_expectations]: {sorted(unknown)}")

    schema_version = table.get("schema_version")
    if schema_version != 1:
        raise ConfigError("[symbol_expectations].schema_version must be 1")

    aliases = table.get("aliases", ["XAUUSD."])
    if (
        not isinstance(aliases, list)
        or not aliases
        or not all(isinstance(a, str) and a.strip() for a in aliases)
    ):
        raise ConfigError("[symbol_expectations].aliases must be a non-empty array of strings")

    required_name = table.get("required_symbol_name")
    if required_name is not None and (not isinstance(required_name, str) or not required_name.strip()):
        raise ConfigError("[symbol_expectations].required_symbol_name must be a non-empty string")

    digits_raw = table.get("digits")
    if digits_raw is not None and (isinstance(digits_raw, bool) or not isinstance(digits_raw, int)):
        raise ConfigError("[symbol_expectations].digits must be an integer")

    require_full = table.get("require_full_trade_mode", True)
    if not isinstance(require_full, bool):
        raise ConfigError("[symbol_expectations].require_full_trade_mode must be a boolean")

    return SymbolExpectationsSettings(
        schema_version=schema_version,
        aliases=tuple(aliases),
        required_symbol_name=required_name,
        required_path_token=str(table.get("required_path_token", "Spot Metals")),
        required_profit_currency=str(table.get("required_profit_currency", "")),
        contract_size=_optional_number(table, "contract_size", "[symbol_expectations]"),
        tick_size=_optional_number(table, "tick_size", "[symbol_expectations]"),
        digits=digits_raw,
        require_full_trade_mode=require_full,
    )


_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_hour(text: str, where: str) -> int:
    value = text.strip()
    if not value.endswith(":00"):
        raise ConfigError(f"{where} must be HH:00, got {text!r}")
    try:
        hour = int(value[:2])
    except ValueError:
        raise ConfigError(f"{where} must be HH:00, got {text!r}") from None
    if not 0 <= hour <= 23:
        raise ConfigError(f"{where} hour out of range: {hour}")
    return hour


def _parse_week_point(text: str, where: str) -> tuple[int, int]:
    parts = str(text).split()
    if len(parts) != 2 or parts[0].lower() not in _WEEKDAYS:
        raise ConfigError(f"{where} must look like 'sun 18:00', got {text!r}")
    return _WEEKDAYS[parts[0].lower()], _parse_hour(parts[1], where)


def _parse_break(text: str, where: str) -> tuple[int, int]:
    parts = str(text).split("-")
    if len(parts) != 2:
        raise ConfigError(f"{where} must look like '17:00-18:00', got {text!r}")
    start, end = _parse_hour(parts[0], where), _parse_hour(parts[1], where)
    if start >= end:
        raise ConfigError(f"{where} start must precede end")
    return start, end


def _parse_market_data(data: Mapping[str, Any]) -> MarketDataSettings | None:
    table = data.get("market_data")
    if table is None:
        return None
    if not isinstance(table, Mapping):
        raise ConfigError("[market_data] must be a table")
    allowed = {"gap_tolerance_bars", "stale_after_bars", "tick_quota_gb", "max_tick_window_h",
               "min_bars_per_day", "data_root", "session"}
    unknown = set(table) - allowed
    if unknown:
        raise ConfigError(f"unknown key(s) in [market_data]: {sorted(unknown)}")

    gap = _get(table, "gap_tolerance_bars", int, "[market_data]")
    stale = _get(table, "stale_after_bars", int, "[market_data]")
    quota = float(_get(table, "tick_quota_gb", (int, float), "[market_data]"))
    window = _get(table, "max_tick_window_h", int, "[market_data]")
    ratio = float(_get(table, "min_bars_per_day", (int, float), "[market_data]"))
    root = _get(table, "data_root", str, "[market_data]")

    if gap < 0:
        raise ConfigError("[market_data].gap_tolerance_bars must be >= 0")
    if stale < 1:
        raise ConfigError("[market_data].stale_after_bars must be >= 1")
    if not 0 < quota <= 50:
        raise ConfigError("[market_data].tick_quota_gb must be in (0, 50]")
    if not 1 <= window <= 24:
        raise ConfigError("[market_data].max_tick_window_h must be in [1, 24]")
    if not 0 < ratio <= 1:
        raise ConfigError("[market_data].min_bars_per_day must be in (0, 1]")
    if not root.strip():
        raise ConfigError("[market_data].data_root must not be empty")

    session = _table(table, "session",
                     {"anchor_tz", "week_open", "week_close", "daily_break", "calibrate_from_history_days"})
    anchor = _get(session, "anchor_tz", str, "[market_data.session]")
    if anchor not in SUPPORTED_ANCHORS:
        raise ConfigError(f"unsupported anchor_tz {anchor!r}; supported: {SUPPORTED_ANCHORS}")
    open_wd, open_hour = _parse_week_point(_get(session, "week_open", str, "[market_data.session]"),
                                           "[market_data.session].week_open")
    close_wd, close_hour = _parse_week_point(_get(session, "week_close", str, "[market_data.session]"),
                                             "[market_data.session].week_close")
    if open_wd != 6:
        raise ConfigError("[market_data.session].week_open must be a Sunday entry")
    if close_wd != 4:
        raise ConfigError("[market_data.session].week_close must be a Friday entry")
    break_start, break_end = _parse_break(
        _get(session, "daily_break", str, "[market_data.session]"),
        "[market_data.session].daily_break",
    )
    calibrate = _get(session, "calibrate_from_history_days", int, "[market_data.session]")
    if not 1 <= calibrate <= 365:
        raise ConfigError("[market_data.session].calibrate_from_history_days must be in [1, 365]")

    return MarketDataSettings(
        gap_tolerance_bars=gap,
        stale_after_bars=stale,
        tick_quota_gb=quota,
        max_tick_window_h=window,
        min_bars_per_day=ratio,
        data_root=root,
        session=SessionSettings(
            anchor=anchor,
            week_open_weekday=open_wd,
            week_open_hour=open_hour,
            week_close_weekday=close_wd,
            week_close_hour=close_hour,
            break_start_hour=break_start,
            break_end_hour=break_end,
            calibrate_from_history_days=calibrate,
        ),
    )


def parse_settings(data: Mapping[str, Any], *, source: str = "<memory>") -> Settings:
    unknown_top = set(data) - _TOP_LEVEL_KEYS
    if unknown_top:
        raise ConfigError(f"unknown top-level key(s): {sorted(unknown_top)}")

    schema_version = _get(data, "schema_version", int, "<root>")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported schema_version {schema_version}; expected {SUPPORTED_SCHEMA_VERSION}"
        )

    ex = _table(
        data,
        "execution",
        {"mode", "terminal_path", "symbol_policy", "require_terminal_path_match"},
    )
    mode_raw = _get(ex, "mode", str, "[execution]")
    try:
        mode = ExecutionMode(mode_raw)
    except ValueError:
        raise ConfigError(f"unknown execution mode: {mode_raw!r}") from None
    if mode is ExecutionMode.DEMO:
        raise ConfigError(
            "execution mode DEMO requires approval A-05 in approvals/ and is rejected by this build"
        )
    if mode not in ALLOWED_EXECUTION_MODES:
        raise ConfigError(f"execution mode {mode.value} is not allowed in Phase 1")

    terminal_path = _get(ex, "terminal_path", str, "[execution]")
    if not terminal_path.strip():
        raise ConfigError("[execution].terminal_path must not be empty")

    symbol_policy = _get(ex, "symbol_policy", str, "[execution]")
    if symbol_policy not in KNOWN_SYMBOL_POLICIES:
        raise ConfigError(f"unknown symbol policy: {symbol_policy!r}")

    acc = _table(
        data,
        "account",
        {"expected_trade_mode", "expected_server", "expected_company", "currency", "reject_on_mismatch"},
    )
    expected_trade_mode = _get(acc, "expected_trade_mode", str, "[account]")
    if expected_trade_mode != "DEMO":
        raise ConfigError("only DEMO accounts are supported; live/contest accounts are prohibited")

    for key in ("expected_server", "expected_company", "currency"):
        if not _get(acc, key, str, "[account]").strip():
            raise ConfigError(f"[account].{key} must not be empty; a blank value disables a gate")

    risk = _table(
        data,
        "risk",
        {"risk_percent", "min_effective_risk_ratio", "max_spread_points", "require_stop_loss"},
    )
    risk_percent = float(_get(risk, "risk_percent", (int, float), "[risk]"))
    if not 0.0 < risk_percent <= 5.0:
        raise ConfigError(f"[risk].risk_percent must be in (0, 5], got {risk_percent}")
    min_ratio = float(_get(risk, "min_effective_risk_ratio", (int, float), "[risk]"))
    if not 0.0 < min_ratio <= 1.0:
        raise ConfigError(f"[risk].min_effective_risk_ratio must be in (0, 1], got {min_ratio}")
    max_spread = _get(risk, "max_spread_points", int, "[risk]")
    if max_spread < 0:
        raise ConfigError("[risk].max_spread_points must be >= 0")

    log = _table(data, "logging", {"level", "redact"})
    level = _get(log, "level", str, "[logging]").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(f"unknown logging level: {level!r}")

    return Settings(
        schema_version=schema_version,
        symbol_expectations=_parse_expectations(data, symbol_policy),
        execution=ExecutionSettings(
            mode=mode,
            terminal_path=terminal_path,
            symbol_policy=symbol_policy,
            require_terminal_path_match=bool(_get(ex, "require_terminal_path_match", bool, "[execution]")),
        ),
        account=AccountSettings(
            expected_trade_mode=expected_trade_mode,
            expected_server=_get(acc, "expected_server", str, "[account]"),
            expected_company=_get(acc, "expected_company", str, "[account]"),
            currency=_get(acc, "currency", str, "[account]"),
            reject_on_mismatch=_require_true(acc, "reject_on_mismatch", "[account]"),
        ),
        risk=RiskSettings(
            risk_percent=risk_percent,
            min_effective_risk_ratio=min_ratio,
            max_spread_points=max_spread,
            require_stop_loss=bool(_get(risk, "require_stop_loss", bool, "[risk]")),
        ),
        logging=LoggingSettings(level=level, redact=bool(_get(log, "redact", bool, "[logging]"))),
        market_data=_parse_market_data(data),
        source_path=source,
    )


def load_settings(path: str | Path) -> Settings:
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"configuration file not found: {file_path}")
    with file_path.open("rb") as handle:
        data = tomllib.load(handle)
    return parse_settings(data, source=str(file_path))
