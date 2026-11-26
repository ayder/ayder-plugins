"""Console-capture switch (zdt-impl-6): spec rev 3 AC-C1…C10, C12.

The fixture server binds 127.0.0.1 (loopback), so auto capture is on for it.
Off-by-default is exercised with about:blank and an explicit console=false.
"""
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


# --- Step 2: start-time capture + auto default -----------------------------

def test_auto_on_loopback(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    assert state.console_auto is True
    assert state.console_capture is True
    assert "first-script-marker" in str(bt.browser_console(clear=False))


def test_off_at_start_and_tool_independence(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url, console=False), ToolSuccess)
    assert state.console_capture is False
    assert state.console_auto is False
    r = bt.browser_console(clear=False)
    assert isinstance(r, ToolSuccess)
    text = str(r)
    assert text.split("\n")[0] == untrusted_line(url)
    assert "off" in text.lower()
    assert "first-script-marker" not in text
    # every other tool still works with capture off
    assert isinstance(bt.browser_eval(script="document.title"), ToolSuccess)
    rej = bt.browser_eval(script="Promise.reject(new Error('rej-marker'))")
    assert isinstance(rej, ToolError) and "rej-marker" in str(rej)
    assert "rendered-text" in str(bt.browser_read())
    assert isinstance(bt.browser_click(selector="#btn"), ToolSuccess)
    assert "changed-text" in str(bt.browser_read())
    ty = bt.browser_type(selector="#field", value="xyz")
    assert isinstance(ty, ToolSuccess) and "xyz" not in str(ty)
    assert _js("document.getElementById('field').value") == "xyz"


def test_console_param_validation_no_browser(fixture_server):
    r = bt.browser_open(url=fixture_server + "/page.html", console="yes")
    assert isinstance(r, ToolError)
    assert state.browser is None


def test_close_resets_auto(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url, console=False), ToolSuccess)
    assert state.console_auto is False
    assert isinstance(bt.browser_close(), ToolSuccess)
    assert state.console_auto is True
    assert len(state.console_buffer) == 0
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    assert state.console_auto is True and state.console_capture is True
    assert "first-script-marker" in str(bt.browser_console(clear=False))
