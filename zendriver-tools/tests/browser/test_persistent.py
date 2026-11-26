"""S20 / AC-12: persistent profile — visible sign-in window, 0700, cookie
survives close and headless reopen. No real account needed."""
import stat

import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolSuccess

pytestmark = pytest.mark.browser


def test_persistent_profile_cookie_and_mode(fixture_server):
    url = fixture_server + "/cookie.html"
    r = bt.browser_open(url=url, profile="work", headless=False)
    assert isinstance(r, ToolSuccess), r
    assert "persistent:work" in str(r)
    directory = state.profile_dir
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert "zdt_test=1" in str(bt.browser_eval(script="document.cookie"))
    assert bt.browser_close().is_success
    assert directory.exists()            # preserved by close
    r = bt.browser_open(url=url, profile="work")   # headless again
    assert isinstance(r, ToolSuccess), r
    assert "persistent:work" in str(r)
    assert "zdt_test=1" in str(bt.browser_eval(script="document.cookie"))
    assert bt.browser_close().is_success
    assert directory.exists()
