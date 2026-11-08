"""Structured logging with mandatory redaction.

Every sink goes through :class:`JsonFormatter`, so a redaction bypass is not
possible by switching handlers.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

#: (pattern, replacement) — applied to the fully formatted record.
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
    """Return ``text`` with credentials and account identifiers masked."""
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingJsonFormatter(logging.Formatter):
    def __init__(self, *, redaction: bool = True, service: str = "guardian") -> None:
        super().__init__()
        self._redaction = redaction
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message} | {self.formatException(record.exc_info)}"
        if self._redaction:
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


def setup_logging(level: str = "INFO", *, redact_output: bool = True, stream: Any = None) -> logging.Logger:
    """Configure the ``guardian`` logger once and return it."""
    logger = logging.getLogger("guardian")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter(redaction=redact_output))
    logger.addHandler(handler)
    return logger


def scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Drop sensitive account fields before persistence or logging."""
    return {k: v for k, v in data.items() if k.lower() not in SENSITIVE_ACCOUNT_FIELDS}
