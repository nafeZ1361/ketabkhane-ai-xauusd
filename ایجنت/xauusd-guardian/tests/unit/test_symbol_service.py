"""Application service: attach → verify → resolve → detach, with typed failures."""

from __future__ import annotations

import pytest

from guardian.application.symbol_service import SymbolResolverService
from guardian.contracts.schemas import ResolutionStatus
from guardian.domain.symbols import GoldExpectations

DEMO_IDENTITY = {
    "trade_mode": "DEMO",
    "server": "AronMarkets-Demo",
    "company": "Aron Markets Ltd",
    "currency": "USD",
    "leverage": "400",
}


class FakeAdapter:
    """Test double. Mirrors the read-only adapter surface used by the service."""

    def __init__(
        self,
        specs=(),
        identity=None,
        attach_error: Exception | None = None,
        identity_error: Exception | None = None,
        specs_error: Exception | None = None,
        spread: int | None = 10,
    ) -> None:
        self._specs = list(specs)
        self._identity = dict(identity or DEMO_IDENTITY)
        self._attach_error = attach_error
        self._identity_error = identity_error
        self._specs_error = specs_error
        self._spread = spread
        self.detached = False
        self.attach_calls = 0

    def attach(self):
        self.attach_calls += 1
        if self._attach_error:
            raise self._attach_error
        return {"terminal_path": r"C:\Program Files\Aron Markets MT5", "build": 6230}

    def detach(self) -> None:
        self.detached = True

    def account_identity(self):
        if self._identity_error:
            raise self._identity_error
        return dict(self._identity)

    def symbol_specs(self):
        if self._specs_error:
            raise self._specs_error
        return list(self._specs)

    def symbol_spread_points(self, name):
        return self._spread


def _service(adapter, **overrides) -> SymbolResolverService:
    kwargs = dict(
        policy="xauusd_identity_v3",
        expectations=GoldExpectations(),
        expected_server="AronMarkets-Demo",
        expected_currency="USD",
        sample_spread=True,
    )
    kwargs.update(overrides)
    return SymbolResolverService(adapter, **kwargs)


def test_verified_path_reports_identity_evidence_and_spreads(captured_symbols):
    adapter = FakeAdapter(specs=captured_symbols)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.VERIFIED
    assert outcome.resolution.symbol_name == "XAUUSD."
    assert outcome.identity["server"] == "AronMarkets-Demo"
    assert outcome.fingerprint["build"] == 6230
    assert outcome.spread_points == (10, 10, 10)
    assert adapter.detached is True


def test_attach_failure_is_connection_failed(captured_symbols):
    adapter = FakeAdapter(specs=captured_symbols, attach_error=RuntimeError("IPC timeout"))
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert "IPC timeout" in outcome.resolution.reason
    assert outcome.fingerprint is None


def test_wrong_server_is_connection_failed(captured_symbols):
    identity = dict(DEMO_IDENTITY, server="SomeOtherBroker-Live")
    adapter = FakeAdapter(specs=captured_symbols, identity=identity)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert "SomeOtherBroker-Live" in outcome.resolution.reason
    assert outcome.account_gate_failed is True
    assert adapter.detached is True


def test_real_account_is_refused_before_symbol_work(captured_symbols):
    identity = dict(DEMO_IDENTITY, trade_mode="REAL")
    adapter = FakeAdapter(specs=captured_symbols, identity=identity)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert "REAL" in outcome.resolution.reason
    assert outcome.resolution.symbol_name is None
    assert outcome.account_gate_failed is True


def test_wrong_currency_is_refused(captured_symbols):
    identity = dict(DEMO_IDENTITY, currency="EUR")
    adapter = FakeAdapter(specs=captured_symbols, identity=identity)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert "EUR" in outcome.resolution.reason


def test_read_failure_is_connection_failed_and_always_detaches(captured_symbols):
    adapter = FakeAdapter(specs=captured_symbols, specs_error=OSError("terminal closed"))
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert "terminal read failed" in outcome.resolution.reason
    assert adapter.detached is True


def test_metadata_mismatch_blocks_and_skips_spread_sampling(captured_symbols):
    broken = [
        captured_symbols[0].__class__(**{**_as_dict(s), "contract_size": 10.0})
        if s.name == "XAUUSD."
        else s
        for s in captured_symbols
    ]
    adapter = FakeAdapter(specs=broken)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.METADATA_MISMATCH
    assert outcome.spread_points == ()


def _as_dict(spec) -> dict:
    from dataclasses import asdict

    return asdict(spec)


@pytest.mark.parametrize("missing", ["server", "currency", "trade_mode"])
def test_identity_fields_are_required(captured_symbols, missing):
    identity = dict(DEMO_IDENTITY)
    identity[missing] = "UNEXPECTED"
    adapter = FakeAdapter(specs=captured_symbols, identity=identity)
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert outcome.account_gate_failed is True


def test_configuration_errors_are_not_masked_as_connection_faults(captured_symbols):
    """Audit finding F4: an unknown policy is a programming error, not a dead terminal."""
    adapter = FakeAdapter(specs=captured_symbols)
    with pytest.raises(ValueError, match="unknown symbol policy"):
        _service(adapter, policy="not_a_policy").resolve()


def test_build_resolver_service_wires_the_account_gate(project_root, captured_symbols):
    """Audit F7: the config→service wiring must enforce the company."""
    from guardian.application.symbol_service import build_resolver_service
    from guardian.config.settings import load_settings

    settings = load_settings(project_root / "configs" / "config.toml")
    adapter = FakeAdapter(specs=captured_symbols, identity=dict(DEMO_IDENTITY, company="Other Broker"))
    outcome = build_resolver_service(settings, adapter).resolve()

    assert outcome.account_gate_failed is True
    assert "Other Broker" in outcome.resolution.reason


def test_build_resolver_service_passes_the_live_control(project_root, captured_symbols):
    from guardian.application.symbol_service import build_resolver_service
    from guardian.config.settings import load_settings

    settings = load_settings(project_root / "configs" / "config.toml")
    outcome = build_resolver_service(settings, FakeAdapter(specs=captured_symbols)).resolve()

    assert outcome.resolution.status is ResolutionStatus.VERIFIED
    assert outcome.resolution.policy == "xauusd_identity_v3"


def test_wrong_company_is_refused(captured_symbols):
    identity = dict(DEMO_IDENTITY, company="Another Broker Ltd")
    adapter = FakeAdapter(specs=captured_symbols, identity=identity)
    outcome = _service(adapter, expected_company="Aron Markets Ltd").resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert outcome.account_gate_failed is True
    assert "Another Broker Ltd" in outcome.resolution.reason


def test_attach_failure_is_not_an_account_gate_failure(captured_symbols):
    adapter = FakeAdapter(specs=captured_symbols, attach_error=RuntimeError("no terminal"))
    outcome = _service(adapter).resolve()

    assert outcome.resolution.status is ResolutionStatus.CONNECTION_FAILED
    assert outcome.account_gate_failed is False
