"""Latched, policy-only kill switch. It blocks decisions; it never sends orders."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from .sizing import RiskError
from .controls import RiskDecision

class KillSwitchLevel(IntEnum):
    NONE = 0
    PAUSE = 1
    LATCHED = 2

@dataclass(frozen=True, slots=True)
class KillSwitchState:
    level: KillSwitchLevel = KillSwitchLevel.NONE
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.level, KillSwitchLevel):
            raise RiskError("level must be a KillSwitchLevel")
        if not isinstance(self.reasons, tuple) or any(not isinstance(x, str) or not x for x in self.reasons):
            raise RiskError("reasons must be a tuple of non-empty strings")

    @property
    def active(self) -> bool:
        return self.level is not KillSwitchLevel.NONE

    @property
    def allows_new_decisions(self) -> bool:
        return not self.active

_LATCH_REASONS = frozenset({"DAILY_LOSS_LIMIT", "WEEKLY_LOSS_LIMIT", "MAX_DRAWDOWN"})

def trip_kill_switch(state: KillSwitchState, decision: RiskDecision) -> KillSwitchState:
    """Escalate only. Severe loss/drawdown breaches require owner-approved reset."""
    if not isinstance(state, KillSwitchState) or not isinstance(decision, RiskDecision):
        raise RiskError("state and decision must use declared contracts")
    if decision.allowed:
        return state
    level = KillSwitchLevel.LATCHED if _LATCH_REASONS.intersection(decision.reasons) else KillSwitchLevel.PAUSE
    return KillSwitchState(max(state.level, level), tuple(dict.fromkeys(state.reasons + decision.reasons)))

def reset_kill_switch(state: KillSwitchState, *, owner_approved: bool) -> KillSwitchState:
    if not isinstance(state, KillSwitchState):
        raise RiskError("state must be a KillSwitchState")
    if state.active and owner_approved is not True:
        raise RiskError("active kill switch requires explicit owner approval to reset")
    return KillSwitchState()
