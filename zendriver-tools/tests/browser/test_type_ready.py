"""zdt-impl-4: browser_type readiness gate + value post-check (spec rev5, D23).

A focused decoy holds existing text; targeting an ineligible field must give a
bounded ToolError and leave the decoy untouched. Late-ready fields are waited
for. A focus-stealing Backspace handler stops the edit. A maxlength field that
cannot retain the value gives the mismatch ToolError with no value echoed.
"""
import json

import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError, ToolSuccess

pytestmark = pytest.mark.browser


def _val(el_id):
    expr = "document.getElementById(" + json.dumps(el_id) + ").value"

    async def work(ctx):
        return await state.tab.evaluate(expr)
    return state.run_call(work, timeout_s=10)


def _active():
    async def work(ctx):
        return await state.tab.evaluate(
            "document.activeElement ? document.activeElement.id : null")
    return state.run_call(work, timeout_s=10)


def _open(fixture_server):
    assert isinstance(
        bt.browser_open(url=fixture_server + "/type_ready.html"), ToolSuccess)


def test_hidden_field_errors_and_decoy_untouched(fixture_server):
    _open(fixture_server)
    assert _active() == "decoy"
    r = bt.browser_type(selector="#hidden", value="hello", timeout_seconds=2)
    assert isinstance(r, ToolError), r
    assert "hidden" in str(r)
    assert "hello" not in str(r)
    assert _val("decoy") == "keep"
    assert _val("hidden") == "secret"
    assert _active() == "decoy"


def test_readonly_field_errors_and_decoy_untouched(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#readonly", value="hello", timeout_seconds=2)
    assert isinstance(r, ToolError), r
    assert "not editable" in str(r)
    assert "hello" not in str(r)
    assert _val("decoy") == "keep"
    assert _val("readonly") == "ro"
    assert _active() == "decoy"


def test_late_editable_waits_then_types(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#late-editable", value="hello",
                        timeout_seconds=5)
    assert isinstance(r, ToolSuccess), r
    assert _val("late-editable") == "hello"
    assert "hello" not in str(r)
    assert "5" in str(r)


def test_late_visible_waits_then_types(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#late-visible", value="hello",
                        timeout_seconds=5)
    assert isinstance(r, ToolSuccess), r
    assert _val("late-visible") == "hello"
    assert "hello" not in str(r)


def test_button_ineligible(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#btn", value="hello", timeout_seconds=2)
    assert isinstance(r, ToolError), r
    assert "not a text field" in str(r)
    assert "hello" not in str(r)


def test_checkbox_ineligible(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#chk", value="hello", timeout_seconds=2)
    assert isinstance(r, ToolError), r
    assert "not a text field" in str(r)


def test_focus_lost_stops_and_other_untouched(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#trap", value="hello", timeout_seconds=5)
    assert isinstance(r, ToolError), r
    assert "hello" not in str(r)
    assert _val("other") == "untouched"


def test_maxlength_mismatch_no_echo(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#maxlen", value="abcdef", timeout_seconds=5)
    assert isinstance(r, ToolError), r
    s = str(r)
    assert "3 characters present" in s
    assert "abcdef" not in s
    assert "abc" not in s
    assert _val("maxlen") == "abc"


def test_prefilled_email_replaced(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#email", value="new@example.org",
                        timeout_seconds=5)
    assert isinstance(r, ToolSuccess), r
    assert _val("email") == "new@example.org"
    assert "new@example.org" not in str(r)


def test_prefilled_number_replaced(fixture_server):
    _open(fixture_server)
    r = bt.browser_type(selector="#num", value="7", timeout_seconds=5)
    assert isinstance(r, ToolSuccess), r
    assert _val("num") == "7"
    assert "7" not in str(r)
