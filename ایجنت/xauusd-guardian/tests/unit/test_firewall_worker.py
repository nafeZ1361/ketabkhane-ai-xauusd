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


def test_launcher_anchors_worker_module_root():
    from guardian.firewall import launcher as launcher_module

    launcher = RestrictedWorkerLauncher()
    expected = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(launcher_module.__file__)))
    )
    assert launcher.worker_module_root == expected
    assert os.path.isfile(
        os.path.join(launcher.worker_module_root, "guardian", "firewall", "worker.py")
    )


def test_launched_worker_pid_binding_is_exact_or_direct_child():
    from guardian.firewall.worker_security import is_launched_worker

    current = os.getpid()
    assert is_launched_worker(current, current) is True
    assert is_launched_worker(current, 0) is False

    if os.name != "nt":
        pytest.skip("direct-child binding is Windows-only")
    import subprocess
    import sys

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"]
    )
    try:
        assert is_launched_worker(current, child.pid) is True
    finally:
        child.kill()
        child.wait()
