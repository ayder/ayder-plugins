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


# --- Step 3: browser_open reuse toggle, auto reclassification, discard -----

def test_open_toggle_unique_markers_no_restart(fixture_server):
    base = fixture_server + "/console_marker.html"
    assert isinstance(bt.browser_open(url=base + "?m=one", console=False),
                      ToolSuccess)
    first = state.browser
    assert isinstance(bt.browser_open(url=base + "?m=two", console=True),
                      ToolSuccess)
    assert state.browser is first          # reused, never restarted
    text = str(bt.browser_console(clear=False))
    assert "marker-two" in text
    assert "marker-one" not in text        # discard removed the page being left


def test_open_on_never_shows_page_left(fixture_server):
    base = fixture_server + "/console_marker.html"
    assert isinstance(bt.browser_open(url=base + "?m=alpha", console=False),
                      ToolSuccess)
    assert isinstance(bt.browser_open(url=base + "?m=beta", console=True),
                      ToolSuccess)
    text = str(bt.browser_console(clear=False))
    assert "marker-beta" in text
    assert "marker-alpha" not in text


def test_auto_default_and_stickiness(fixture_server):
    base = fixture_server + "/console_marker.html"
    assert isinstance(bt.browser_open(url="about:blank"), ToolSuccess)
    assert state.console_auto is True and state.console_capture is False
    assert isinstance(bt.browser_open(url=base + "?m=loc"), ToolSuccess)
    assert state.console_auto is True and state.console_capture is True
    assert "marker-loc" in str(bt.browser_console(clear=False))
    # explicit false leaves auto and sticks across later omitted opens
    assert isinstance(bt.browser_open(url=base + "?m=x", console=False),
                      ToolSuccess)
    assert state.console_auto is False and state.console_capture is False
    assert isinstance(bt.browser_open(url=base + "?m=y"), ToolSuccess)
    assert state.console_capture is False
    assert "marker-y" not in str(bt.browser_console(clear=False))


def test_auto_switch_off_clears_buffer(fixture_server):
    base = fixture_server + "/console_marker.html"
    assert isinstance(bt.browser_open(url=base + "?m=stay"), ToolSuccess)
    assert state.console_auto is True and state.console_capture is True
    assert "marker-stay" in str(bt.browser_console(clear=False))
    # leaving the local page for a non-loopback URL in auto switches off
    assert isinstance(bt.browser_open(url="about:blank"), ToolSuccess)
    assert state.console_auto is True and state.console_capture is False
    assert len(state.console_buffer) == 0   # automatic off clears like explicit
    assert "marker-stay" not in str(bt.browser_console(clear=False))


def test_mismatch_boundary_no_capture_enforcement(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    first = state.browser
    assert isinstance(bt.browser_open(url=url, headless=False), ToolError)
    assert isinstance(bt.browser_open(url=url, profile="work"), ToolError)
    # console toggle applies immediately, no mismatch error, no restart
    assert isinstance(bt.browser_open(url=url, console=False), ToolSuccess)
    assert state.browser is first and state.console_capture is False
    # switching local -> remote in one browser is permitted (not enforced)
    assert isinstance(bt.browser_open(url="about:blank"), ToolSuccess)
    assert state.browser is first


def test_navigation_independent_of_capture(fixture_server):
    # The MVP suite has no held-subresource fixture; page.html's JS-written
    # load-time text proves browser_open waited for load with capture off
    # (Page domain + lifecycle stay enabled, D-5). Behaviour-preserving detail.
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url, console=False), ToolSuccess)
    assert state.console_capture is False
    assert "rendered-text" in str(bt.browser_read())
    assert isinstance(bt.browser_click(selector="#btn"), ToolSuccess)
    assert "changed-text" in str(bt.browser_read())
