"""S18 / AC-13 (reduced): failed start is cleaned up; retry starts one browser."""
import glob
import os
import tempfile
import time

import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess

pytestmark = pytest.mark.browser


def test_failed_start_cleanup_and_retry(fixture_server, tmp_path, monkeypatch):
    stub = tmp_path / "stub-chrome"
    stub.write_text("#!/bin/sh\nexec sleep 30\n")
    os.chmod(stub, 0o755)
    monkeypatch.setenv("AYDER_BROWSER_EXECUTABLE", str(stub))
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "ayder-zendriver-*")))
    t0 = time.monotonic()
    r = bt.browser_open(url=fixture_server + "/page.html", timeout_seconds=3)
    elapsed = time.monotonic() - t0
    assert isinstance(r, ToolError), r
    assert elapsed < 13
    assert state.browser is None
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "ayder-zendriver-*")))
    assert after - before == set()       # no throwaway dir left behind
    # retry with real Chrome: exactly one running browser
    monkeypatch.delenv("AYDER_BROWSER_EXECUTABLE")
    r = bt.browser_open(url=fixture_server + "/page.html")
    assert isinstance(r, ToolSuccess), r
    assert state.browser is not None and state.handle.poll() is None
