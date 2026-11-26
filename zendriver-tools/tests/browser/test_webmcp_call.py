"""AC-W1b/W2/W3/W4/W5/W7b/W9/W10(call)/W16(call): browser_webmcp_call."""
import json
import time

import pytest

import browser_tools as bt
import zendriver_tools_browser as zb
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def _js(expr):
    async def work(ctx):
        return await state.tab.evaluate(expr)
    return state.run_call(work, timeout_s=10)


def _payload(result):
    return str(result).split("\n", 1)[1]


def test_call_frame_selection(fixture_server):
    url = fixture_server + "/webmcp_main.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    tools = json.loads(_payload(bt.browser_webmcp_list()))
    child_fid = next(t["frameId"] for t in tools
                     if t["name"] == "echo" and t["frame"] == "child")
    r = bt.browser_webmcp_call(name="framed", arguments={"text": "hi"})
    assert isinstance(r, ToolSuccess) and "framed:hi" in str(r)
    r = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"})
    assert isinstance(r, ToolSuccess) and "main-echo:hi" in str(r)
    r = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"},
                               frame_id=child_fid)
    assert isinstance(r, ToolSuccess) and "child-echo:hi" in str(r)


def test_call_output_and_max_chars(fixture_server):
    url = fixture_server + "/webmcp_main.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"})
    assert isinstance(r, ToolSuccess)
    assert str(r).split("\n")[0] == untrusted_line(url)
    assert "echo:hi" in _payload(r)
    r1 = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"}, max_chars=1)
    text = str(r1)
    assert text.split("\n")[0] == untrusted_line(url)
    assert "Truncated" in text


def test_call_error_maps_message(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    r = bt.browser_webmcp_call(name="fail")
    assert isinstance(r, ToolError) and "tool-failed-marker" in str(r)


def test_call_deadline_cancels_then_next_succeeds(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    start = time.monotonic()
    r = bt.browser_webmcp_call(name="slow", timeout_seconds=1)
    elapsed = time.monotonic() - start
    assert isinstance(r, ToolError) and "slow" in str(r)
    assert elapsed < 2.5
    r2 = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"})
    assert isinstance(r2, ToolSuccess) and "main-echo:hi" in str(r2)


def test_call_unknown_tool(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    r = bt.browser_webmcp_call(name="nope")
    assert isinstance(r, ToolError)
    assert "No WebMCP tool named 'nope'" in str(r)


def test_call_instant_not_lost(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_instant.html"), ToolSuccess)
    r = bt.browser_webmcp_call(name="instant")
    assert isinstance(r, ToolSuccess) and "instant-done" in str(r)


def test_call_zone_like_thenable(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_zone.html"), ToolSuccess)
    r = bt.browser_webmcp_call(name="zone")
    assert isinstance(r, ToolSuccess) and "zone-done" in str(r)
    assert "__zone_symbol__" not in str(r)


def test_call_not_available(fixture_server, monkeypatch):
    monkeypatch.setattr(zb, "webmcp_flags", lambda w: [])
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html", webmcp=True), ToolSuccess)
    r = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"})
    assert isinstance(r, ToolError)
    assert "WebMCP is not available on this page" in str(r)


def test_call_ambiguous_children(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_two_children.html"), ToolSuccess)
    r = bt.browser_webmcp_call(name="dup")
    assert isinstance(r, ToolError) and "frame_id" in str(r)


def test_call_declarative_fill_and_submit(fixture_server):
    url = fixture_server + "/webmcp_declarative.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_webmcp_call(name="dplain", arguments={"q": "filled"})
    assert isinstance(r, (ToolSuccess, ToolError))  # maps per §5.2
    assert _js("document.querySelector('form[toolname=dplain] input').value") == "filled"
    assert "webmcp_declarative.html" in _js("location.href")  # not submitted
    r2 = bt.browser_webmcp_call(name="dauto", arguments={"q": "go"})
    assert isinstance(r2, (ToolSuccess, ToolError))
    assert "webmcp_submitted.html" in _js("location.href")  # autosubmit navigated


def test_call_off_error(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html", webmcp=False), ToolSuccess)
    r = bt.browser_webmcp_call(name="echo", arguments={"text": "hi"})
    assert isinstance(r, ToolError) and "WebMCP is off for this browser" in str(r)


def test_call_arguments_validation(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    assert isinstance(bt.browser_webmcp_call(name="echo", arguments="x"), ToolError)
    assert isinstance(bt.browser_webmcp_call(name=""), ToolError)
