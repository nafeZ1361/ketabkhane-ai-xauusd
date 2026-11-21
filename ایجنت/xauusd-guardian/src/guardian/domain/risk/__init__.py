"""Phase 4 — risk sizing.

Pure ``Decimal`` arithmetic over numbers supplied by the caller. This package never
imports ``MetaTrader5``, never reads an account, and never constructs an order: it turns
(equity, risk fraction, stop distance, contract economics) into a lot size.
"""

from .sizing import RiskError, RiskSpec, position_size

__all__ = ["RiskError", "RiskSpec", "position_size"]
