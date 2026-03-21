"""func_ref dispatch target for MCP proxy tools.

This module is re-imported once per MCP tool by ayder's load_plugin_definitions.
Module-level __getattr__ delegates attribute lookups to state.handlers, which
was populated by mcp_definitions.py before the re-import loop started.

mcp_state is imported from the module cache each time (never popped by the loader),
so state.handlers always refers to the same dict with all registered closures.
"""
from mcp_state import state


def __getattr__(name: str):
    """Called by Python when getattr(module, name) finds no normal attribute."""
    if name in state.handlers:
        return state.handlers[name]
    raise AttributeError(f"mcp_tool has no handler '{name}'")
