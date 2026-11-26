"""S1: the MVP tool contract — seven definitions, exact flags and schemas."""
import browser_definitions as bd

EXPECTED = {
    # name: (permission, safe_mode_blocked)
    "browser_open": ("http", True),
    "browser_read": ("r", False),
    "browser_click": ("x", True),
    "browser_type": ("x", True),
    "browser_eval": ("x", True),
    "browser_console": ("r", False),
    "browser_close": ("w", True),
}

SUPPORTED_PARAMS = {
    "browser_open": {"url", "profile", "headless", "console", "timeout_seconds"},
    "browser_read": {"selector", "max_chars", "timeout_seconds"},
    "browser_click": {"selector", "timeout_seconds"},
    "browser_type": {"selector", "value", "timeout_seconds"},
    "browser_eval": {"script", "max_chars", "timeout_seconds"},
    "browser_console": {"clear", "capture"},
    "browser_close": set(),
}

REQUIRED = {
    "browser_open": ["url"],
    "browser_read": [],
    "browser_click": ["selector"],
    "browser_type": ["selector", "value"],
    "browser_eval": ["script"],
    "browser_console": [],
    "browser_close": [],
}


def test_seven_definitions_with_exact_flags():
    defs = {td.name: td for td in bd.TOOL_DEFINITIONS}
    assert set(defs) == set(EXPECTED)
    for name, (perm, blocked) in EXPECTED.items():
        td = defs[name]
        assert td.permission == perm, name
        assert td.safe_mode_blocked is blocked, name
        assert td.tags == ("browser",), name
        assert td.func_ref == f"browser_tools:{name}", name


def test_schemas_publish_supported_parameters_only():
    for td in bd.TOOL_DEFINITIONS:
        props = set(td.parameters["properties"])
        assert props == SUPPORTED_PARAMS[td.name], td.name
        assert td.parameters.get("required", []) == REQUIRED[td.name], td.name
        assert td.parameters["type"] == "object"


def test_output_budget_and_prompt():
    defs = {td.name: td for td in bd.TOOL_DEFINITIONS}
    assert defs["browser_read"].max_result_chars == 0
    assert defs["browser_eval"].max_result_chars == 0
    prompt = defs["browser_open"].system_prompt
    assert prompt
    for needle in ("browser_open", "untrusted", "passwords", "headless=false"):
        assert needle in prompt, needle
    assert "ask" in prompt.lower()  # confirmation before consequential actions


def test_ranges_in_schemas():
    defs = {td.name: td for td in bd.TOOL_DEFINITIONS}
    for name in ("browser_open", "browser_read", "browser_click",
                 "browser_type", "browser_eval"):
        t = defs[name].parameters["properties"]["timeout_seconds"]
        assert t["minimum"] == 1 and t["maximum"] == 120
    for name in ("browser_read", "browser_eval"):
        m = defs[name].parameters["properties"]["max_chars"]
        assert m["minimum"] == 1 and m["maximum"] == 100000
