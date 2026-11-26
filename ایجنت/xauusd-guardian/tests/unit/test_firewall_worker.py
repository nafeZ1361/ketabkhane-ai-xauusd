import os

import pytest

from guardian.firewall.launcher import RestrictedWorkerLauncher, WorkerLaunchError


def test_launcher_rejects_non_windows():
    if os.name != "nt":
        with pytest.raises(WorkerLaunchError):
            RestrictedWorkerLauncher().start(timeout=0.1)


def test_worker_config_is_bounded():
    from guardian.firewall.worker import WorkerConfig

    assert WorkerConfig(max_requests=1).max_requests == 1
    with pytest.raises(ValueError):
        WorkerConfig(max_requests=0)


def test_worker_security_does_not_use_uac_as_restriction_predicate():
    from guardian.firewall import worker_security

    source = open(worker_security.__file__, encoding="utf-8").read()
    assert "TokenHasRestrictions" in source
    assert "elevation_type" in source
    assert "restricted" in source
