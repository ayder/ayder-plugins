"""S6: Chrome executable resolution — override checked, search chrome-only."""
import os
from unittest import mock

import pytest

import zendriver_tools_chrome as c


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("AYDER_BROWSER_EXECUTABLE", raising=False)


def test_search_failure_names_both_remedies(monkeypatch):
    monkeypatch.setattr(c, "_search", lambda: None)
    with pytest.raises(c.ChromeError) as ei:
        c.resolve_executable()
    msg = str(ei.value)
    assert "Chrome" in msg and "AYDER_BROWSER_EXECUTABLE" in msg


def test_override_missing_path(monkeypatch, tmp_path):
    monkeypatch.setenv("AYDER_BROWSER_EXECUTABLE", str(tmp_path / "nope"))
    with mock.patch.object(c, "_search", side_effect=AssertionError("search ran")):
        with pytest.raises(c.ChromeError) as ei:
            c.resolve_executable()
    assert "AYDER_BROWSER_EXECUTABLE" in str(ei.value)


def test_override_non_executable(monkeypatch, tmp_path):
    f = tmp_path / "chrome"
    f.write_text("not executable")
    os.chmod(f, 0o644)
    monkeypatch.setenv("AYDER_BROWSER_EXECUTABLE", str(f))
    with pytest.raises(c.ChromeError) as ei:
        c.resolve_executable()
    assert "AYDER_BROWSER_EXECUTABLE" in str(ei.value)


def test_override_valid(monkeypatch, tmp_path):
    f = tmp_path / "chrome"
    f.write_text("#!/bin/sh\n")
    os.chmod(f, 0o755)
    monkeypatch.setenv("AYDER_BROWSER_EXECUTABLE", str(f))
    assert str(c.resolve_executable()) == str(f)


def test_search_is_chrome_only():
    # the real search must be asked for chrome, never auto/brave/edge
    with mock.patch("zendriver.core.config.find_executable",
                    return_value="/x/chrome") as fe:
        assert str(c.resolve_executable()) == "/x/chrome"
        fe.assert_called_once_with(browser="chrome")
