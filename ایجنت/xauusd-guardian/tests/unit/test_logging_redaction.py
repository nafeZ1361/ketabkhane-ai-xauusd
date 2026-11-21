from __future__ import annotations

import io
import json
import logging

import pytest

from guardian.observability.logging_setup import redact, scrub_mapping, setup_logging


def test_credentials_are_redacted():
    text = "login=12345678 password=hunter2 token=abc123 api_key=zzz"
    cleaned = redact(text)
    assert "12345678" not in cleaned
    assert "hunter2" not in cleaned
    assert "abc123" not in cleaned
    assert "zzz" not in cleaned
    assert "<redacted>" in cleaned


def test_long_identifiers_are_masked():
    assert "1234567890" not in redact("account 1234567890 refused")


def test_prices_survive_redaction():
    text = "entry=2650.35 sl=2649.90 spread=10"
    assert redact(text) == text


def test_formatter_emits_json_with_utc_timestamp_and_redacts():
    stream = io.StringIO()
    logger = setup_logging("INFO", stream=stream)
    logger.info("order rejected for login=99887766")
    payload = json.loads(stream.getvalue().strip())
    assert payload["level"] == "INFO"
    assert payload["service"] == "guardian"
    assert payload["ts_utc"].endswith("+00:00")
    assert "99887766" not in payload["message"]


def test_setup_logging_has_no_redaction_disable_parameter():
    import inspect
    assert "redact_output" not in inspect.signature(setup_logging).parameters


def test_formatter_cannot_disable_redaction():
    from guardian.observability.logging_setup import RedactingJsonFormatter
    with pytest.raises(TypeError):
        RedactingJsonFormatter(redaction=False)


def test_scrub_mapping_drops_sensitive_account_fields_recursively():
    cleaned = scrub_mapping({
        "trade_mode": "DEMO",
        "nested": {"server": "AronMarkets-Demo", "balance": 1000.0},
        "items": [{"equity": 1000.0, "symbol": "XAUUSD."}],
    })
    assert cleaned == {
        "trade_mode": "DEMO",
        "nested": {"server": "AronMarkets-Demo"},
        "items": [{"symbol": "XAUUSD."}],
    }


def test_logger_does_not_propagate_to_root():
    logger = setup_logging("INFO", stream=io.StringIO())
    assert logger.propagate is False
    assert logging.getLogger("guardian") is logger
