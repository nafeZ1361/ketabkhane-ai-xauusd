"""F4 Windows restricted-process integration probes."""

import sys

import pytest

from guardian.firewall.worker_host import RestrictedWorker, WorkerHostError


@pytest.mark.skipif(sys.platform != "win32", reason="F4 worker isolation is Windows-only")
def test_restricted_worker_starts_and_authenticates_health_check():
    with RestrictedWorker.launch() as worker:
        assert worker.security_report["is_restricted"] is True
        assert worker.security_report["integrity_rid"] == 4096
        assert worker.security_report["privilege_count"] <= 1
        assert worker.request("HEALTH_CHECK", {}) == {"status": "OK"}


@pytest.mark.skipif(sys.platform != "win32", reason="F4 worker isolation is Windows-only")
def test_restricted_worker_revalidates_synthetic_risk_only():
    payload = {
        "equity": "10000",
        "stop_points": "100",
        "proposed_lots": "0.50",
        "spec": {
            "risk_fraction": "0.01",
            "value_per_point_lot": "1",
            "lot_step": "0.01",
            "min_lot": "0.01",
            "max_lot": "100",
        },
    }
    with RestrictedWorker.launch() as worker:
        result = worker.request("RISK_REVALIDATE", payload)
    assert result == {
        "within_risk_limit": True,
        "reason_code": "RISK_WITHIN_LIMIT",
        "recomputed_max_lots": "1.00",
    }


@pytest.mark.skipif(sys.platform != "win32", reason="F4 worker isolation is Windows-only")
def test_restricted_worker_refuses_order_operation_and_poisoned_session():
    with RestrictedWorker.launch() as worker:
        with pytest.raises(WorkerHostError, match="WORKER_OPERATION_NOT_ALLOWED"):
            worker.request("ORDER_SEND", {"symbol": "XAUUSD"})
        with pytest.raises(WorkerHostError, match="WORKER_SESSION_NOT_AVAILABLE"):
            worker.request("HEALTH_CHECK", {})
