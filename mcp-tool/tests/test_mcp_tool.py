import sys
import importlib
import pytest


PLUGIN_ROOT = str(__import__("pathlib").Path(__file__).parent.parent)


def _fresh_import():
    """Import mcp_tool fresh (as loader would)."""
    sys.modules.pop("mcp_tool", None)
    if PLUGIN_ROOT not in sys.path:
        sys.path.insert(0, PLUGIN_ROOT)
    return importlib.import_module("mcp_tool")


def test_getattr_returns_handler_from_state():
    from mcp_state import state
    state.handlers.clear()

    def fake_handler(**kwargs):
        return f"called: {kwargs}"

    state.handlers["server__my_tool"] = fake_handler
    mod = _fresh_import()

    result = getattr(mod, "server__my_tool")
    assert result is fake_handler


def test_getattr_raises_on_unknown_name():
    from mcp_state import state
    state.handlers.clear()
    mod = _fresh_import()

    with pytest.raises(AttributeError):
        getattr(mod, "nonexistent_tool")


def test_getattr_survives_reimport():
    """Simulates what load_plugin_definitions does: pop + reimport per tool."""
    from mcp_state import state
    state.handlers.clear()

    def h1(**kwargs): return "h1"
    def h2(**kwargs): return "h2"
    state.handlers["server__tool_a"] = h1
    state.handlers["server__tool_b"] = h2

    # Simulate two loop iterations
    sys.modules.pop("mcp_tool", None)
    mod1 = importlib.import_module("mcp_tool")
    handler_a = getattr(mod1, "server__tool_a")

    sys.modules.pop("mcp_tool", None)
    mod2 = importlib.import_module("mcp_tool")
    handler_b = getattr(mod2, "server__tool_b")

    assert handler_a is h1
    assert handler_b is h2
