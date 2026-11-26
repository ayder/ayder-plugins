"""S10: rendered text, selector reads with retry, bounded output."""
import time

import pytest

import browser_tools as bt
from ayder_cli.core.result import ToolError, ToolSuccess
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def test_read_whole_selector_and_late(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_read()
    assert isinstance(r, ToolSuccess)
    assert str(r).split("\n")[0] == untrusted_line(url)
    assert "rendered-text" in str(r)
    r = bt.browser_read(selector="#out")
    assert "rendered-text" in str(r)
    # #late appears 500 ms after load; the lookup retries until the deadline
    r = bt.browser_read(selector="#late", timeout_seconds=5)
    assert isinstance(r, ToolSuccess)
    assert "late-text" in str(r)


def test_existing_empty_element_returns_promptly(fixture_server):
    # Spec: lookups retry only while the element is MISSING. An existing
    # element returns its text at once, even when empty — no error, no wait.
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    t0 = time.monotonic()
    r = bt.browser_read(selector="#empty", timeout_seconds=5)
    elapsed = time.monotonic() - t0
    assert isinstance(r, ToolSuccess), r
    assert elapsed < 2.0
    assert str(r) == untrusted_line(url) + "\n"  # header + empty payload


def test_missing_selector_bounded_error(fixture_server):
    assert isinstance(bt.browser_open(url=fixture_server + "/page.html"),
                      ToolSuccess)
    t0 = time.monotonic()
    r = bt.browser_read(selector="#never", timeout_seconds=2)
    assert isinstance(r, ToolError)
    assert time.monotonic() - t0 < 5


def test_max_chars_bounds_payload(fixture_server):
    url = fixture_server + "/page.html"
    assert isinstance(bt.browser_open(url=url), ToolSuccess)
    r = bt.browser_read(max_chars=5)
    text = str(r)
    lines = text.split("\n")
    assert lines[0] == untrusted_line(url)
    assert lines[1] == "rende"
    assert "cut" in lines[-1].lower()
