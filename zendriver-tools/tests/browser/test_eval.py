"""S13: one JSON-valued evaluation, promises awaited, bounded output."""
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


def test_eval_title_promise_rejection_counter(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_eval(script="document.title")
    assert isinstance(r, ToolSuccess)
    assert str(r) == untrusted_line(url) + '\n"Fixture Page"'
    r = bt.browser_eval(script="Promise.resolve(42)")
    assert str(r).endswith("\n42")
    r = bt.browser_eval(script="Promise.reject(new Error('reject-marker'))")
    assert isinstance(r, ToolError)
    assert "reject-marker" in str(r)
    _js("window.__n = 0")
    r = bt.browser_eval(script="(window.__n++, {a: 1})")
    assert isinstance(r, ToolSuccess)
    assert str(r).endswith('\n{"a":1}')
    assert _js("window.__n") == 1  # evaluated exactly once


def test_eval_non_json_is_bounded_error(fixture_server):
    # MVP: the string-form fallback is backlog 2; non-serialisable -> error
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    r = bt.browser_eval(script="() => 1")
    assert isinstance(r, ToolError)


def test_eval_max_chars(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_eval(script="'x'.repeat(500)", max_chars=10)
    text = str(r)
    lines = text.split("\n")
    assert lines[0] == untrusted_line(url)
    assert "502" in lines[1]          # notice gives the full JSON length
    assert lines[2] == '"xxxxxxxxx'   # leading 10 characters of the JSON
