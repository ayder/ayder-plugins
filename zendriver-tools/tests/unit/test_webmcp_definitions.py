"""AC-W12: WebMCP definitions, validation, ranges, guidance; D22 guard stays green."""
import browser_definitions as bd
import browser_tools as bt
from ayder_cli.core.result import ToolError


def _defs():
    return {td.name: td for td in bd.TOOL_DEFINITIONS}


def test_webmcp_permissions_and_safe_mode():
    d = _defs()
    assert d["browser_webmcp_list"].permission == "r"
    assert d["browser_webmcp_list"].safe_mode_blocked is False
    assert d["browser_webmcp_call"].permission == "x"
    assert d["browser_webmcp_call"].safe_mode_blocked is True
    assert d["browser_webmcp_list"].func_ref == "browser_tools:browser_webmcp_list"
    assert d["browser_webmcp_call"].func_ref == "browser_tools:browser_webmcp_call"
    assert d["browser_webmcp_list"].tags == ("browser",)
    assert d["browser_webmcp_call"].tags == ("browser",)


def test_webmcp_params_and_ranges():
    d = _defs()
    lp = d["browser_webmcp_list"].parameters["properties"]
    assert set(lp) == {"max_chars", "timeout_seconds"}
    assert lp["max_chars"]["minimum"] == 1 and lp["max_chars"]["maximum"] == 100000
    assert lp["timeout_seconds"]["minimum"] == 1 and lp["timeout_seconds"]["maximum"] == 120
    cp = d["browser_webmcp_call"].parameters["properties"]
    assert {"name", "arguments", "frame_id", "max_chars", "timeout_seconds"} <= set(cp)
    assert d["browser_webmcp_call"].parameters["required"] == ["name"]


def test_webmcp_descriptions_guidance():
    d = _defs()
    for n in ("browser_webmcp_list", "browser_webmcp_call"):
        assert "untrusted" in d[n].description.lower()
    cd = d["browser_webmcp_call"].description.lower()
    assert "readonlyhint" in cd or "read-only" in cd
    assert "browser_webmcp_list" in cd  # re-list after a call that navigates


def test_browser_open_webmcp_published():
    w = _defs()["browser_open"].parameters["properties"]["webmcp"]
    assert w["type"] == "boolean" and w["default"] is True


def test_call_validation_before_browser():
    assert isinstance(bt.browser_webmcp_call(name=""), ToolError)
    assert isinstance(bt.browser_webmcp_call(name="echo", arguments="x"), ToolError)
    assert isinstance(bt.browser_webmcp_list(max_chars=0), ToolError)
