"""AC-W1/W6/W7(list)/W8(list)/W10(list)/W16(list)/W17(list): browser_webmcp_list."""
import json
import time

import pytest

import browser_tools as bt
import zendriver_tools_browser as zb
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def _list(**kw):
    return bt.browser_webmcp_list(**kw)


def _tools(result):
    text = str(result)
    body = text.split("\n", 1)[1]
    return json.loads(body)


def _wait_pred(pred):
    async def work(ctx):
        import asyncio
        while not pred():
            await zb.settle_webmcp(ctx.deadline)
            if pred():
                return True
            if time.monotonic() >= ctx.deadline:
                return False
            await asyncio.sleep(0.02)
        return True
    return state.run_call(work, timeout_s=10)


def test_list_all_frames_sorted(fixture_server):
    url = fixture_server + "/webmcp_main.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = _list()
    assert isinstance(r, ToolSuccess)
    assert str(r).split("\n")[0] == untrusted_line(url)
    tools = _tools(r)
    names = [t["name"] for t in tools]
    assert names == sorted(names)
    assert names.count("echo") == 2 and {"fail", "framed", "slow"} <= set(names)
    for t in tools:
        assert {"name", "description", "inputSchema", "declarative",
                "frameId", "frame", "origin"} <= set(t)
        assert t["frame"] in ("main", "child")
    main_echo = next(t for t in tools if t["name"] == "echo" and t["frame"] == "main")
    child_echo = next(t for t in tools if t["name"] == "echo" and t["frame"] == "child")
    assert main_echo["frameId"] != child_echo["frameId"]
    assert main_echo["annotations"]["readOnlyHint"] is True
    assert main_echo["declarative"] is False


def test_list_no_tools(fixture_server):
    url = fixture_server + "/webmcp_empty.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = _list()
    assert isinstance(r, ToolSuccess)
    assert "No WebMCP tools are registered on this page." in str(r)


def test_list_reflects_abort_iframe_navigation(fixture_server):
    base = fixture_server
    assert isinstance(bt.browser_open(url=base + "/webmcp_main.html"), ToolSuccess)
    assert isinstance(bt.browser_eval(script="window.__abortEcho()"), ToolSuccess)
    assert _wait_pred(lambda: sum(
        1 for k in state.webmcp_tools if k[1] == "echo") == 1)
    assert [t["name"] for t in _tools(_list())].count("echo") == 1
    assert isinstance(bt.browser_eval(script="window.__removeIframe()"), ToolSuccess)
    assert _wait_pred(lambda: "framed" not in [k[1] for k in state.webmcp_tools])
    assert "framed" not in [t["name"] for t in _tools(_list())]
    assert isinstance(bt.browser_open(url=base + "/webmcp_empty.html"), ToolSuccess)
    assert "No WebMCP tools" in str(_list())


def test_list_late_registration_no_sleep(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_late.html"), ToolSuccess)
    assert _wait_pred(lambda: "late" in [k[1] for k in state.webmcp_tools])
    assert "late" in [t["name"] for t in _tools(_list())]


def test_list_not_available(fixture_server, monkeypatch):
    monkeypatch.setattr(zb, "webmcp_flags", lambda w: [])  # test-only: no flag
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html", webmcp=True), ToolSuccess)
    assert state.webmcp_setting is True
    r = _list()
    assert isinstance(r, ToolError)
    assert "WebMCP is not available on this page" in str(r)


def test_list_declarative(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_declarative.html"), ToolSuccess)
    tools = _tools(_list())
    by = {t["name"]: t for t in tools}
    assert by["dplain"]["declarative"] is True
    assert by["dauto"]["declarative"] is True
    assert by["dauto"]["annotations"]["autosubmit"] is True
    assert "autosubmit" not in by["dplain"].get("annotations", {})


def test_list_off_and_reopen(fixture_server):
    url = fixture_server + "/webmcp_main.html"
    assert isinstance(bt.browser_open(url=url, webmcp=False), ToolSuccess)
    r = _list()
    assert isinstance(r, ToolError) and "WebMCP is off for this browser" in str(r)
    assert isinstance(bt.browser_close(), ToolSuccess)
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    assert "echo" in [t["name"] for t in _tools(_list())]


def test_list_max_chars_truncation(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    r = _list(max_chars=1)
    text = str(r)
    assert text.split("\n")[0] == untrusted_line(fixture_server + "/webmcp_main.html")
    assert "Truncated" in text
