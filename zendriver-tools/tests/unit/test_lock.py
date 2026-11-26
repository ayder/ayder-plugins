"""S5: SingletonLock arbitration — refuse live or unverifiable locks,
never modify them."""
import os
import socket
import subprocess
import sys

import pytest

import zendriver_tools_profiles as p


@pytest.fixture
def profile(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


def _lock(d, target):
    (d / "SingletonLock").symlink_to(target)


def test_no_lock(profile):
    p.check_profile_lock(profile)  # proceeds


def test_confirmed_stale(profile):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _lock(profile, f"{socket.gethostname()}-{dead.pid}")
    p.check_profile_lock(profile)  # proceeds
    assert os.readlink(profile / "SingletonLock")  # untouched


def test_live_local(profile):
    _lock(profile, f"{socket.gethostname()}-{os.getpid()}")
    with pytest.raises(p.ProfileError):
        p.check_profile_lock(profile)


def test_foreign_hostname(profile):
    _lock(profile, "some-other-host-123")
    with pytest.raises(p.ProfileError):
        p.check_profile_lock(profile)


@pytest.mark.parametrize("target", ["garbage-no-pid", "host-", "", "host-abc"])
def test_unreadable_target(profile, target):
    _lock(profile, target)
    with pytest.raises(p.ProfileError):
        p.check_profile_lock(profile)


def test_lock_never_modified(profile):
    _lock(profile, f"{socket.gethostname()}-{os.getpid()}")
    link = profile / "SingletonLock"
    before = os.readlink(link)
    with pytest.raises(p.ProfileError):
        p.check_profile_lock(profile)
    assert os.readlink(link) == before
    assert link.is_symlink()
