"""Without zendriver in ayder's environment, browser_open names the missing
dependency instead of reporting a missing Chrome, and launches nothing."""
import sys

import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError


@pytest.mark.parametrize("override", [False, True])
def test_open_without_zendriver(monkeypatch, tmp_path, override):
    for name in [m for m in sys.modules if m == "zendriver" or m.startswith("zendriver.")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "zendriver", None)
    if override:
        monkeypatch.setenv("AYDER_BROWSER_EXECUTABLE", sys.executable)
    else:
        monkeypatch.delenv("AYDER_BROWSER_EXECUTABLE", raising=False)
    monkeypatch.setenv("AYDER_BROWSER_PROFILES_DIR", str(tmp_path / "profiles"))
    try:
        r = bt.browser_open(url="about:blank", timeout_seconds=5)
        assert isinstance(r, ToolError), r
        assert "zendriver is not installed" in str(r)
        assert "Chrome" not in str(r)
        assert state.browser is None and state.handle is None
    finally:
        state.reset_for_test()
