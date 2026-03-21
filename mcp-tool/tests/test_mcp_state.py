import pytest
import asyncio
import threading


def test_mcp_state_initial_values():
    from mcp_state import state
    assert state.loop is None
    assert state.loop_thread is None
    assert state.sessions == {}
    assert state.handlers == {}


def test_mcp_state_is_mutable():
    from mcp_state import state
    state.sessions["test"] = "value"
    # Re-import should give same object (module cached)
    import importlib, sys
    # Don't pop it in this test since we want to test mutation works
    # Just verify the value is there
    assert state.sessions["test"] == "value"
    state.sessions.clear()


def test_mcp_state_loop_assignment():
    from mcp_state import state
    loop = asyncio.new_event_loop()
    state.loop = loop
    assert state.loop is loop
    loop.close()
    state.loop = None
