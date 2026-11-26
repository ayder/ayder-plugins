"""S9: console capture before first navigation; bounded buffer; clear."""
import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def test_first_script_and_exception(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)

    async def boom(ctx):
        return await state.tab.evaluate(
            "setTimeout(() => { throw new Error('boom-marker'); }, 0); 1")
    state.run_call(boom, timeout_s=10)

    async def wait_marker(ctx):
        import asyncio
        for _ in range(100):
            if any("boom-marker" in t for _, t in state.console_buffer):
                return True
            await asyncio.sleep(0.05)
        return False
    assert state.run_call(wait_marker, timeout_s=10)

    r = bt.browser_console(clear=False)
    assert isinstance(r, ToolSuccess)
    text = str(r)
    assert text.split("\n")[0] == untrusted_line(url)
    assert "first-script-marker" in text
    assert "boom-marker" in text
    assert text.index("first-script-marker") < text.index("boom-marker")
    n = len(state.console_buffer)
    r2 = bt.browser_console(clear=False)
    assert str(r2) == text  # unchanged
    r3 = bt.browser_console(clear=True)
    assert "first-script-marker" in str(r3)
    assert len(state.console_buffer) == 0
    r4 = bt.browser_console()
    assert str(r4) == untrusted_line(url)  # empty: header alone


def test_buffer_bounded(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)

    async def flood(ctx):
        return await state.tab.evaluate(
            "for (let i = 1; i <= 600; i++) console.log('m' + i); 1")
    state.run_call(flood, timeout_s=10)

    async def settled(ctx):
        import asyncio
        for _ in range(100):
            if len(state.console_buffer) == 500:
                return True
            await asyncio.sleep(0.05)
        return False
    assert state.run_call(settled, timeout_s=10)
    entries = list(state.console_buffer)
    assert len(entries) == 500
    assert entries[0][1] == "m101"  # oldest dropped first
    assert entries[-1][1] == "m600"
