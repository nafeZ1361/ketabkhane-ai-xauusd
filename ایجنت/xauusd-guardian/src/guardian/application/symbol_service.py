"""Application service: resolve the gold symbol against a live terminal.

Owns the attach/verify/detach lifecycle so callers never talk to the adapter
directly. Returns ``CONNECTION_FAILED`` instead of raising for terminal-level
problems, so every failure mode is a value the gate can print.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from guardian.contracts.schemas import ResolutionStatus, SymbolResolution
from guardian.domain.symbols import GoldExpectations, identify_gold_symbol


@dataclass(frozen=True, slots=True)
class ResolutionOutcome:
    resolution: SymbolResolution
    fingerprint: Mapping[str, Any] | None = None
    identity: Mapping[str, str] | None = None
    spread_points: tuple[int | None, ...] = ()
    #: True when the terminal was reachable but the account/server failed the
    #: DEMO gate. Lets the caller report BLOCKED instead of a connection fault.
    account_gate_failed: bool = False


def check_account_identity(
    identity: Mapping[str, str],
    *,
    expected_trade_mode: str,
    expected_server: str,
    expected_currency: str,
    expected_company: str | None = None,
) -> str | None:
    """Return a BLOCK reason when the terminal identity is not the approved one."""
    if identity.get("trade_mode") != expected_trade_mode:
        return f"account trade_mode is {identity.get('trade_mode')!r}, expected {expected_trade_mode!r}"
    if identity.get("server") != expected_server:
        return f"server is {identity.get('server')!r}, expected {expected_server!r}"
    if identity.get("currency") != expected_currency:
        return f"currency is {identity.get('currency')!r}, expected {expected_currency!r}"
    if expected_company is not None and identity.get("company") != expected_company:
        return f"company is {identity.get('company')!r}, expected {expected_company!r}"
    return None


class SymbolResolverService:
    def __init__(
        self,
        adapter: Any,
        *,
        policy: str,
        expectations: GoldExpectations,
        expected_server: str,
        expected_currency: str,
        expected_trade_mode: str = "DEMO",
        expected_company: str | None = None,
        sample_spread: bool = False,
        spread_samples: int = 3,
    ) -> None:
        self._adapter = adapter
        self._policy = policy
        self._expectations = expectations
        self._expected_server = expected_server
        self._expected_currency = expected_currency
        self._expected_trade_mode = expected_trade_mode
        self._expected_company = expected_company
        self._sample_spread = sample_spread
        self._spread_samples = max(1, spread_samples)

    def _connection_problem(self, identity: Mapping[str, str]) -> str | None:
        return check_account_identity(
            identity,
            expected_trade_mode=self._expected_trade_mode,
            expected_server=self._expected_server,
            expected_currency=self._expected_currency,
            expected_company=self._expected_company,
        )

    def resolve(self) -> ResolutionOutcome:
        try:
            fingerprint = self._adapter.attach()
        except Exception as exc:  # terminal absent, wrong path, IPC failure
            return ResolutionOutcome(
                resolution=SymbolResolution(
                    status=ResolutionStatus.CONNECTION_FAILED,
                    policy=self._policy,
                    reason=f"terminal attach failed: {exc}",
                )
            )

        try:
            identity = self._adapter.account_identity()
            problem = self._connection_problem(identity)
            if problem:
                return ResolutionOutcome(
                    resolution=SymbolResolution(
                        status=ResolutionStatus.CONNECTION_FAILED,
                        policy=self._policy,
                        reason=problem,
                    ),
                    fingerprint=fingerprint,
                    identity=identity,
                    account_gate_failed=True,
                )

            resolution = identify_gold_symbol(
                self._adapter.symbol_specs(),
                policy=self._policy,
                account_currency=self._expected_currency,
                expectations=self._expectations,
            )

            spreads: tuple[int | None, ...] = ()
            if self._sample_spread and resolution.ok and resolution.symbol_name:
                spreads = tuple(
                    self._adapter.symbol_spread_points(resolution.symbol_name)
                    for _ in range(self._spread_samples)
                )

            return ResolutionOutcome(
                resolution=resolution,
                fingerprint=fingerprint,
                identity=identity,
                spread_points=spreads,
            )
        except ValueError:
            # configuration / programming error, never a terminal fault
            raise
        except Exception as exc:
            return ResolutionOutcome(
                resolution=SymbolResolution(
                    status=ResolutionStatus.CONNECTION_FAILED,
                    policy=self._policy,
                    reason=f"terminal read failed: {exc}",
                )
            )
        finally:
            self._adapter.detach()


def build_resolver_service(settings: Any, adapter: Any) -> SymbolResolverService:
    """Wire the resolver from validated settings.

    Single construction point so the config→service mapping is testable without
    running the gate script (audit finding F7).
    """
    profile = settings.symbol_expectations
    expectations = (
        GoldExpectations()
        if profile is None
        else GoldExpectations(
            schema_version=profile.schema_version,
            aliases=profile.aliases,
            required_symbol_name=profile.required_symbol_name,
            required_path_token=profile.required_path_token,
            required_profit_currency=profile.required_profit_currency,
            contract_size=profile.contract_size,
            tick_size=profile.tick_size,
            digits=profile.digits,
            require_full_trade_mode=profile.require_full_trade_mode,
        )
    )
    return SymbolResolverService(
        adapter,
        policy=settings.execution.symbol_policy,
        expectations=expectations,
        expected_server=settings.account.expected_server,
        expected_currency=settings.account.currency,
        expected_trade_mode=settings.account.expected_trade_mode,
        expected_company=settings.account.expected_company,
        sample_spread=True,
    )
