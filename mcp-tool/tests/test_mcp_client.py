from unittest.mock import MagicMock, AsyncMock


def _reset_state():
    """Reset MCPState between tests."""
    import sys
    for mod in ["mcp_state", "mcp_client"]:
        sys.modules.pop(mod, None)


def test_ensure_loop_starts_thread():
    _reset_state()
    import mcp_client
    from mcp_state import state
    assert state.loop is None
    mcp_client.ensure_loop()
    assert state.loop is not None
    assert state.loop_thread is not None
    assert state.loop_thread.is_alive()


def test_ensure_loop_is_idempotent():
    _reset_state()
    import mcp_client
    from mcp_state import state
    mcp_client.ensure_loop()
    first_loop = state.loop
    mcp_client.ensure_loop()
    assert state.loop is first_loop   # same loop, not restarted


def test_make_handler_returns_callable():
    _reset_state()
    import mcp_client
    handler = mcp_client.make_handler("myserver", "my_tool")
    assert callable(handler)


def test_make_handler_returns_error_when_no_session():
    _reset_state()
    import mcp_client
    from ayder_cli.core.result import ToolError
    mcp_client.ensure_loop()
    handler = mcp_client.make_handler("missing_server", "my_tool")
    result = handler(arg="value")
    assert isinstance(result, ToolError)
    assert "missing_server" in str(result)


def test_make_handler_calls_tool_successfully():
    _reset_state()
    import mcp_client
    from mcp_state import state
    from ayder_cli.core.result import ToolSuccess

    mcp_client.ensure_loop()

    # Mock session
    mock_session = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "hello world"
    mock_result = MagicMock()
    mock_result.isError = False
    mock_result.content = [mock_content]
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    state.sessions["myserver"] = mock_session

    handler = mcp_client.make_handler("myserver", "my_tool")
    result = handler(param="value")
    assert isinstance(result, ToolSuccess)
    assert "hello world" in str(result)


def test_make_handler_returns_error_on_mcp_error():
    _reset_state()
    import mcp_client
    from mcp_state import state
    from ayder_cli.core.result import ToolError

    mcp_client.ensure_loop()

    mock_session = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "something went wrong"
    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = [mock_content]
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    state.sessions["myserver"] = mock_session

    handler = mcp_client.make_handler("myserver", "my_tool")
    result = handler()
    assert isinstance(result, ToolError)
    assert "MCP error" in str(result)


def test_build_transport_http():
    _reset_state()
    import mcp_client
    transport = mcp_client._build_transport({"url": "http://localhost:8000/mcp"})
    # Should return a context manager (async generator / async context manager)
    assert hasattr(transport, "__aenter__") or hasattr(transport, "__anext__")


def test_build_transport_stdio():
    _reset_state()
    import mcp_client
    transport = mcp_client._build_transport({
        "command": "echo",
        "args": ["hello"],
    })
    assert hasattr(transport, "__aenter__") or hasattr(transport, "__anext__")
