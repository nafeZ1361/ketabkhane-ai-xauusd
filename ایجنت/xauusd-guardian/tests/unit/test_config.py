from __future__ import annotations

import pytest

from guardian.config.settings import ConfigError, load_settings, parse_settings

BASE = {
    "schema_version": 1,
    "execution": {
        "mode": "DRY_RUN",
        "terminal_path": r"C:\Program Files\Aron Markets MT5\terminal64.exe",
        "symbol_policy": "xauusd_strict_v1",
        "require_terminal_path_match": True,
    },
    "account": {
        "expected_trade_mode": "DEMO",
        "expected_server": "AronMarkets-Demo",
        "expected_company": "Aron Markets Ltd",
        "currency": "USD",
        "reject_on_mismatch": True,
    },
    "risk": {
        "risk_percent": 0.25,
        "min_effective_risk_ratio": 0.5,
        "max_spread_points": 30,
        "require_stop_loss": True,
    },
    "logging": {"level": "INFO", "redact": True},
}


def _mutate(path, value):
    import copy

    data = copy.deepcopy(BASE)
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def test_shipped_config_is_valid(project_root):
    settings = load_settings(project_root / "configs" / "config.toml")

    assert settings.execution.mode.value == "DRY_RUN"
    assert settings.execution.symbol_policy == "xauusd_identity_v3"
    assert settings.risk.risk_percent == 0.25
    assert settings.account.expected_trade_mode == "DEMO"
    profile = settings.symbol_expectations
    assert profile is not None
    assert profile.aliases == ("XAUUSD.",)
    assert profile.required_symbol_name == "XAUUSD."
    assert profile.required_path_token == "Spot Metals"
    assert profile.contract_size == 100.0
    assert profile.digits == 2


def test_unknown_top_level_key_is_rejected():
    data = dict(BASE, surprise=1)
    with pytest.raises(ConfigError, match="unknown top-level"):
        parse_settings(data)


def test_unknown_section_key_is_rejected():
    with pytest.raises(ConfigError, match="unknown key"):
        parse_settings(_mutate(["execution", "extra"], True))


def test_demo_execution_mode_is_rejected_without_approval():
    with pytest.raises(ConfigError, match="A-05"):
        parse_settings(_mutate(["execution", "mode"], "DEMO"))


def test_live_expected_mode_is_rejected():
    with pytest.raises(ConfigError, match="DEMO accounts are supported"):
        parse_settings(_mutate(["account", "expected_trade_mode"], "REAL"))


@pytest.mark.parametrize("value", [0.0, -0.1, 5.1, 50])
def test_risk_percent_bounds(value):
    with pytest.raises(ConfigError, match="risk_percent"):
        parse_settings(_mutate(["risk", "risk_percent"], value))


def test_unsupported_schema_version_is_rejected():
    with pytest.raises(ConfigError, match="schema_version"):
        parse_settings(_mutate(["schema_version"], 99))


def test_unknown_symbol_policy_is_rejected():
    with pytest.raises(ConfigError, match="symbol policy"):
        parse_settings(_mutate(["execution", "symbol_policy"], "guess_v0"))


def test_missing_section_is_rejected():
    data = {k: v for k, v in BASE.items() if k != "risk"}
    with pytest.raises(ConfigError, match="risk"):
        parse_settings(data)


def test_missing_file_raises(project_root):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(project_root / "configs" / "nope.toml")


def test_identity_policy_requires_expectations_table():
    with pytest.raises(ConfigError, match="symbol_expectations"):
        parse_settings(_mutate(["execution", "symbol_policy"], "xauusd_identity_v3"))


def test_identity_policy_accepts_expectations_table():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {
        "schema_version": 1,
        "aliases": ["XAUUSD", "XAUUSD."],
        "required_path_token": "Spot Metals",
        "required_profit_currency": "USD",
        "contract_size": 100.0,
        "tick_size": 0.01,
        "digits": 2,
        "require_full_trade_mode": True,
    }
    settings = parse_settings(data)
    assert settings.symbol_expectations.aliases == ("XAUUSD", "XAUUSD.")


def test_unknown_expectation_key_is_rejected():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {"schema_version": 1, "magic": True}
    with pytest.raises(ConfigError, match="unknown key"):
        parse_settings(data)


def test_empty_alias_list_is_rejected():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {"schema_version": 1, "aliases": []}
    with pytest.raises(ConfigError, match="aliases"):
        parse_settings(data)


def test_expectation_schema_version_is_enforced():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {"schema_version": 2}
    with pytest.raises(ConfigError, match="schema_version"):
        parse_settings(data)


def test_blank_account_identity_fields_are_rejected():
    with pytest.raises(ConfigError, match="must not be empty"):
        parse_settings(_mutate(["account", "expected_company"], "   "))


def test_fail_closed_switch_cannot_be_disabled():
    with pytest.raises(ConfigError, match="must be true"):
        parse_settings(_mutate(["account", "reject_on_mismatch"], False))


def test_required_symbol_name_must_be_a_string():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {"schema_version": 1, "required_symbol_name": ""}
    with pytest.raises(ConfigError, match="required_symbol_name"):
        parse_settings(data)


def test_policy_registry_is_shared_with_the_domain():
    from guardian.domain import symbols as domain_symbols
    from guardian.config import settings as config_settings

    assert config_settings.KNOWN_SYMBOL_POLICIES is domain_symbols.KNOWN_POLICIES


def test_optional_expectation_checks_may_be_omitted():
    data = _mutate(["execution", "symbol_policy"], "xauusd_identity_v3")
    data["symbol_expectations"] = {"schema_version": 1}
    profile = parse_settings(data).symbol_expectations
    assert profile.contract_size is None
    assert profile.tick_size is None
    assert profile.digits is None
    assert profile.require_full_trade_mode is True
