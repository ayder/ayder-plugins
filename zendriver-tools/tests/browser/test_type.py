"""S12: type replaces the field and never echoes the value."""
import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess

pytestmark = pytest.mark.browser


def _field_value():
    async def work(ctx):
        return await state.tab.evaluate("document.getElementById('field').value")
    return state.run_call(work, timeout_s=10)


def test_type_replaces_and_never_echoes(fixture_server):
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    assert _field_value() == "abc"
    r = bt.browser_type(selector="#field", value="xyz")
    assert isinstance(r, ToolSuccess), r
    assert _field_value() == "xyz"
    assert "xyz" not in str(r)          # never the value itself
    assert "#field" in str(r) and "3" in str(r)  # selector + char count


def test_type_missing_selector(fixture_server):
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    r = bt.browser_type(selector="#never", value="v", timeout_seconds=2)
    assert isinstance(r, ToolError)
