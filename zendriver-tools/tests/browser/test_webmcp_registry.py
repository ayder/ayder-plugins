"""AC-W7/W8 at the registry level (S3): live per-frame list, abort, iframe
removal (frameDetached), navigation clearing, late registration. Tested through
internal state/functions, not the webmcp tools (those arrive in S4/S5)."""
import time

import pytest

import browser_tools as bt
import zendriver_tools_browser as zb
import zendriver_tools_state as state
from ayder_cli.core.result import ToolSuccess

pytestmark = pytest.mark.browser


def _drain():
    async def work(ctx):
        await zb.settle_webmcp(ctx.deadline)
    state.run_call(work, timeout_s=10)


def _wait_registry(pred):
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


def _names():
    return [k[1] for k in state.webmcp_tools]


def test_registry_holds_main_and_child_tools(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    _drain()
    assert {"echo", "fail", "slow", "framed"} <= set(_names())
    assert sum(1 for n in _names() if n == "echo") == 2  # main + child


def test_registry_abort_removes_tool(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    _drain()
    assert isinstance(bt.browser_eval(script="window.__abortEcho()"), ToolSuccess)
    assert _wait_registry(lambda: sum(1 for n in _names() if n == "echo") == 1)
    assert "framed" in _names()  # child unaffected


def test_registry_iframe_removed_clears_child(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    _drain()
    assert "framed" in _names()
    assert isinstance(bt.browser_eval(script="window.__removeIframe()"), ToolSuccess)
    assert _wait_registry(lambda: "framed" not in _names())
    assert sum(1 for n in _names() if n == "echo") == 1  # only main echo left


def test_registry_navigation_clears_stale(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_main.html"), ToolSuccess)
    _drain()
    assert "echo" in _names()
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_empty.html"), ToolSuccess)
    _drain()
    assert _names() == []  # nothing stale


def test_registry_late_registration(fixture_server):
    assert isinstance(bt.browser_open(
        url=fixture_server + "/webmcp_late.html"), ToolSuccess)
    assert _wait_registry(lambda: "late" in _names())
    assert "late" in _names()
