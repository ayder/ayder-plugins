"""S2: argument validation happens before anything else; no browser starts."""
import pytest

import browser_tools as bt
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError


@pytest.fixture(autouse=True)
def no_browser():
    assert state.browser is None
    yield
    assert state.browser is None  # nothing may start in this module


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)",
                                 "ftp://x/", "chrome://settings", ""])
def test_bad_schemes(url):
    r = bt.browser_open(url=url)
    assert isinstance(r, ToolError)


@pytest.mark.parametrize("name", ["Throwaway", "throwaway", "-x", "a" * 33,
                                  "work space", "UPPER", ""])
def test_bad_profile_names(name):
    r = bt.browser_open(url="about:blank", profile=name)
    assert isinstance(r, ToolError)


@pytest.mark.parametrize("t", [0, -1, 121, 1000])
def test_timeout_range(t):
    assert isinstance(bt.browser_open(url="about:blank", timeout_seconds=t), ToolError)
    assert isinstance(bt.browser_read(timeout_seconds=t), ToolError)


@pytest.mark.parametrize("m", [0, -5, 100001])
def test_max_chars_range(m):
    assert isinstance(bt.browser_read(max_chars=m), ToolError)
    assert isinstance(bt.browser_eval(script="1", max_chars=m), ToolError)


def test_required_params():
    assert isinstance(bt.browser_click(), ToolError)          # selector required
    assert isinstance(bt.browser_type(selector="#x"), ToolError)  # value required
    assert isinstance(bt.browser_type(value="v"), ToolError)  # selector required
    assert isinstance(bt.browser_eval(), ToolError)           # script required


def test_wellformed_tools_say_open_first():
    calls = [
        lambda: bt.browser_read(),
        lambda: bt.browser_click(selector="#b"),
        lambda: bt.browser_type(selector="#i", value="v"),
        lambda: bt.browser_eval(script="1"),
        lambda: bt.browser_console(),
        lambda: bt.browser_close(),
    ]
    for call in calls:
        r = call()
        assert isinstance(r, ToolError)
        assert "browser_open" in str(r)


def test_validation_precedes_open_first():
    # invalid args must give the validation error, not the open-first error
    r = bt.browser_click()
    assert isinstance(r, ToolError) and "browser_open" not in str(r)
