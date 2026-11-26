import os

import pytest

from guardian.firewall.launcher import RestrictedWorkerLauncher, WorkerLaunchError


def test_launcher_rejects_non_windows():
    if os.name != "nt":
        with pytest.raises(WorkerLaunchError):
            RestrictedWorkerLauncher().start(timeout=0.1)


def test_worker_has_no_execution_operation_surface():
    from guardian.firewall.worker import WorkerConfig
    assert WorkerConfig(max_requests=1).max_requests == 1
    with pytest.raises(ValueError):
        WorkerConfig(max_requests=0)
