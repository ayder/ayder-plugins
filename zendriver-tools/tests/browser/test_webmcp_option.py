"""AC-W17 (option/mismatch/reset) + webmcp validation, through browser_open and
browser_eval — not the webmcp tools (those arrive in S4/S5)."""
import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess

pytestmark = pytest.mark.browser


def _js(expr):
    async def work(ctx):
        return await state.tab.evaluate(expr)
    return state.run_call(work, timeout_s=10)


def test_webmcp_false_modelcontext_undefined(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url, webmcp=False), ToolSuccess)
    assert state.webmcp_setting is False
    assert _js("typeof document.modelContext") == "undefined"
    assert _js("document.getElementById('out').textContent") == "rendered-text"


def test_webmcp_mismatch_on_running(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    first = state.browser
    r = bt.browser_open(url=url, webmcp=False)
    assert isinstance(r, ToolError) and "browser_close" in str(r)
    assert state.browser is first and state.webmcp_setting is True


def test_webmcp_close_resets_default(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url, webmcp=False), ToolSuccess)
    assert isinstance(bt.browser_close(), ToolSuccess)
    assert state.webmcp_setting is None
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    assert state.webmcp_setting is True
    assert _js("typeof document.modelContext") == "object"


def test_webmcp_validation_no_browser(fixture_server):
    r = bt.browser_open(url=fixture_server + "/page.html", webmcp="yes")
    assert isinstance(r, ToolError)
    assert state.browser is None
