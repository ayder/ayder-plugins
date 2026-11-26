"""Tool handlers — the only func_ref target. All mutable state lives in
zendriver_tools_state (never re-imported by ayder). MVP: one tab."""
from ayder_cli.core.result import ToolError, ToolSuccess


def browser_open(url, profile=None, headless=None, timeout_seconds=30):
    return ToolError("not implemented")


def browser_read(selector=None, max_chars=20000, timeout_seconds=30):
    return ToolError("not implemented")


def browser_click(selector=None, timeout_seconds=30):
    return ToolError("not implemented")


def browser_type(selector=None, value=None, timeout_seconds=30):
    return ToolError("not implemented")


def browser_eval(script=None, max_chars=20000, timeout_seconds=30):
    return ToolError("not implemented")


def browser_console(clear=True):
    return ToolError("not implemented")


def browser_close():
    return ToolError("not implemented")
