"""Structured logging with mandatory, non-configurable redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(login|account|acct|account_number)\b\s*[=:]\s*[-\w]+"), r"\1=<redacted>"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|apikey)\b\s*[=:]\s*\S+"), r"\1=<redacted>"),
    (re.compile(r"(?i)\b(authorization|bearer)\b\s*[=:]?\s*\S+"), r"\1=<redacted>"),
    (re.compile(r"(?i)\binvestor\s*password\b\s*[=:]?\s*\S*"), "investor_password=<redacted>"),
    (re.compile(r"\b\d{9,}\b"), "<redacted-id>"),
)

SENSITIVE_ACCOUNT_FIELDS = frozenset(
    {"balance", "equity", "margin", "margin_free", "margin_level", "profit", "credit"}
)


def redact(text: str) -> str:
    """Return text with credentials and account identifiers masked."""
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingJsonFormatter(logging.Formatter):
    def __init__(self, *, service: str = "guardian") -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message} | {self.formatException(record.exc_info)}"
        message = redact(message)
        payload: dict[str, Any] = {
            "ts_utc": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "message": message,
        }
        if record.__dict__.get("run_id"):
            payload["run_id"] = record.__dict__["run_id"]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def setup_logging(level: str = "INFO", *, stream: Any = None) -> logging.Logger:
    """Configure the guardian logger; redaction cannot be disabled."""
    logger = logging.getLogger("guardian")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter())
    logger.addHandler(handler)
    return logger


def _scrub_value(value: Any) -> Any:
    """Recursively scrub nested mappings and list/tuple containers."""
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, nested in value.items():
            if isinstance(key, str):
                field = key.casefold()
                if field in SENSITIVE_ACCOUNT_FIELDS or field.startswith("margin"):
                    continue
            cleaned[key] = _scrub_value(nested)
        return cleaned
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(item) for item in value)
    return value


def scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively drop sensitive account fields from all nested containers."""
    if not isinstance(data, dict):
        raise TypeError("data must be a dict")
    return _scrub_value(data)
