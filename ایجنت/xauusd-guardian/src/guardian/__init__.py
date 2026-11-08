"""XAUUSD Guardian — DEMO-only trading research and execution system.

Public surface is intentionally tiny; everything else is imported explicitly
from its own module so the dependency direction stays visible.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = 1
PROJECT_NAME = "xauusd-guardian"

__all__ = ["__version__", "SCHEMA_VERSION", "PROJECT_NAME"]
