"""S4: profile path safety — containment, protected data areas, 0700."""
import os
import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

import zendriver_tools_profiles as p


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("AYDER_BROWSER_PROFILES_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CHROME_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CHROME_USER_DATA_DIR", raising=False)
    return h


def test_default_root_and_override(home, monkeypatch, tmp_path):
    assert p.profiles_root() == home / ".ayder" / "browser-profiles"
    monkeypatch.setenv("AYDER_BROWSER_PROFILES_DIR", str(tmp_path / "custom"))
    assert p.profiles_root() == tmp_path / "custom"


def test_new_profile_dir_mode_0700(home):
    d = p.prepare_profile("work")
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert d == p.profiles_root() / "work"


def test_symlink_escape_refused(home, tmp_path):
    root = p.profiles_root()
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "work").symlink_to(outside, target_is_directory=True)
    with pytest.raises(p.ProfileError):
        p.prepare_profile("work")


@pytest.mark.parametrize("case", [
    "macos-root", "macos-symlink", "macos-case-chrome",
    "linux-xdg-config", "chrome-user-data-dir", "chrome-config-home",
])
def test_protected_data_areas(home, monkeypatch, case):
    if case == "macos-root":
        plat = "darwin"
        root = home / "Library" / "Application Support" / "Google"
        name = "work"
    elif case == "macos-symlink":
        plat = "darwin"
        area = home / "Library" / "Application Support" / "Google" / "Chrome"
        area.mkdir(parents=True)
        root = home / "profiles"
        root.mkdir()
        (root / "work").symlink_to(area, target_is_directory=True)
        name = "work"
    elif case == "macos-case-chrome":
        plat = "darwin"
        root = home / "Library" / "Application Support" / "Google"
        (root / "Chrome").mkdir(parents=True)
        name = "chrome"  # different spelling, same area on a case-insensitive FS
    elif case == "linux-xdg-config":
        plat = "linux"
        root = home / ".config"
        name = "google-chrome-canary"
    elif case == "chrome-user-data-dir":
        plat = "linux"
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(home / "custom-chrome"))
        root = home
        name = "custom-chrome"
    else:
        plat = "darwin"
        monkeypatch.setenv("CHROME_CONFIG_HOME", str(home / "custom-chrome"))
        root = home
        name = "custom-chrome"
    monkeypatch.setenv("AYDER_BROWSER_PROFILES_DIR", str(root))
    with pytest.raises(p.ProfileError):
        p.prepare_profile(name, platform=plat)


def test_case_insensitive_identity(home, monkeypatch):
    # profile root outside the area, but an existing ancestor is the SAME
    # directory as a protected area under a different spelling (fake stat).
    plat = "darwin"
    area = home / "Library" / "Application Support"
    area.mkdir(parents=True)
    root = home / "profiles"
    root.mkdir()
    monkeypatch.setenv("AYDER_BROWSER_PROFILES_DIR", str(root))
    real_stat = os.stat

    def fake_stat(path, *a, **k):
        st = real_stat(path, *a, **k)
        if str(path) == str(root):  # pretend root IS the area (same dev/ino)
            st_area = real_stat(area)
            return os.stat_result((st.st_mode, st_area.st_ino, st_area.st_dev,
                                   st.st_nlink, st.st_uid, st.st_gid,
                                   st.st_size, st.st_atime, st.st_mtime,
                                   st.st_ctime))
        return st

    with mock.patch("zendriver_tools_profiles.os.stat", side_effect=fake_stat):
        with pytest.raises(p.ProfileError):
            p.prepare_profile("work", platform=plat)


def test_safe_profile_allowed(home):
    d = p.prepare_profile("work")  # default root is outside every area
    assert d.exists()
