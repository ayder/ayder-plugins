"""S8: browser_open — launch, one tab, loader-correlated load wait, reuse."""
import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def _js(expr):
    async def work(ctx):
        return await state.tab.evaluate(expr)
    return state.run_call(work, timeout_s=10)


def test_open_load_and_output(fixture_server):
    url = fixture_server + "/page.html"
    r = bt.browser_open(url=url)
    assert isinstance(r, ToolSuccess), r
    text = str(r)
    assert text.split("\n")[0] == untrusted_line(url)
    assert "t1" in text and "Fixture Page" in text and "throwaway" in text
    # load completed: the JS-written text is already there
    assert _js("document.getElementById('out').textContent") == "rendered-text"
    assert state.browser is not None and state.handle is not None
    assert state.handle.poll() is None  # child running


def test_reuse_and_mismatch(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    first = state.browser
    r = bt.browser_open(url=url, headless=False)
    assert isinstance(r, ToolError) and "browser_close" in str(r)
    r = bt.browser_open(url=url, profile="work")
    assert isinstance(r, ToolError) and "browser_close" in str(r)
    r = bt.browser_open(url="about:blank")
    assert isinstance(r, ToolSuccess)
    assert state.browser is first  # reused, never restarted
