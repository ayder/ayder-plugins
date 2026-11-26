"""S11: selector click, retry-until-deadline, bounded missing-selector error."""
import time

import pytest

import browser_tools as bt
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def test_click_changes_page(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_click(selector="#btn")
    assert isinstance(r, ToolSuccess)
    assert str(r).split("\n")[0] == untrusted_line(url)
    assert "changed-text" in str(bt.browser_read(selector="#out"))


def test_missing_selector_bounded(fixture_server):
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    t0 = time.monotonic()
    r = bt.browser_click(selector="#never", timeout_seconds=2)
    assert isinstance(r, ToolError)
    assert time.monotonic() - t0 < 5
