"""S15 / AC-11: close ends the recorded child and deletes the throwaway dir."""
import os

import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolSuccess

pytestmark = pytest.mark.browser


def test_close_ends_child_and_removes_throwaway(fixture_server):
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    pid = state.handle.pid
    directory = state.profile_dir
    assert directory.exists() and state.handle.poll() is None
    r = bt.browser_close()
    assert isinstance(r, ToolSuccess), r
    assert state.browser is None and state.handle is None
    assert not directory.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_close_without_browser_is_error():
    from ayder_cli.core.result import ToolError
    r = bt.browser_close()
    assert isinstance(r, ToolError) and "browser_open" in str(r)
