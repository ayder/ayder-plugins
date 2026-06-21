"""MCP connection management and sync→async bridge.

Responsibilities:
- ensure_loop(): start the background asyncio event loop thread (idempotent)
- connect_server(name, config): connect to one MCP server, return tool list
- make_handler(server_name, mcp_tool_name): return a sync callable for tool dispatch
- _build_transport(config): construct stdio or HTTP transport context manager
- _run_server(name, config, tools_ready): long-running coroutine keeping session alive
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from ayder_cli.core.result import ToolError, ToolSuccess
from mcp_state import state

logger = logging.getLogger(__name__)

try:
    from ayder_cli.tools.plugin_status import set_status as _set_status
except ImportError:
    def _set_status(name: str, label: str, color: str) -> None:  # no-op fallback
        pass


def ensure_loop() -> None:
    """Start the background asyncio event loop thread. Idempotent."""
    if state.loop is not None:
        return
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    state.loop = loop
    state.loop_thread = thread


def _build_transport(config: dict[str, Any]):
    """Return a transport context manager for the given server config."""
    if "url" in config:
        return streamable_http_client(config["url"])
    env = {**os.environ, **config.get("env", {})}
    params = StdioServerParameters(
        command=config["command"],
        args=config.get("args", []),
        env=env,
    )
    return stdio_client(params)


async def _run_server(
    name: str,
    config: dict[str, Any],
    tools_ready: "concurrent.futures.Future[list]",
) -> None:
    """Long-running coroutine that keeps an MCP server session alive."""
    try:
        async with _build_transport(config) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                state.sessions[name] = session
                tools_ready.set_result(result.tools)
                # Keep transport and session alive until task is cancelled
                await asyncio.Event().wait()
    except Exception as exc:
        if not tools_ready.done():
            tools_ready.set_exception(exc)


def connect_server(name: str, config: dict[str, Any]) -> list:
    """Connect to an MCP server and return its tool list. Blocks up to 30s."""
    assert state.loop is not None, "ensure_loop() must be called first"
    tools_ready: concurrent.futures.Future[list] = concurrent.futures.Future()
    asyncio.run_coroutine_threadsafe(_run_server(name, config, tools_ready), state.loop)
    return tools_ready.result(timeout=30)


def make_handler(server_name: str, mcp_tool_name: str):
    """Return a synchronous callable that calls an MCP tool via the background loop."""
    def handler(**kwargs: Any) -> ToolSuccess | ToolError:
        session = state.sessions.get(server_name)
        if session is None:
            return ToolError(f"MCP server '{server_name}' not connected")

        async def _call() -> ToolSuccess | ToolError:
            result = await session.call_tool(mcp_tool_name, kwargs)
            if result.isError is True:
                error_text = " ".join(
                    c.text for c in result.content if hasattr(c, "text")
                )
                return ToolError(f"MCP error: {error_text}")
            texts = [c.text for c in result.content if hasattr(c, "text")]
            return ToolSuccess("\n".join(texts) if texts else "(no output)")

        future = asyncio.run_coroutine_threadsafe(_call(), state.loop)
        try:
            return future.result(timeout=30)
        except TimeoutError:
            future.cancel()
            return ToolError("MCP tool call timed out after 30s")
        except Exception as exc:
            return ToolError(f"MCP tool call failed: {exc}")

    return handler


def set_green() -> None:
    # Name the connected server(s) in the badge so ayder's status bar shows the
    # active MCP, e.g. "MCP: news-digest".
    servers = sorted(state.sessions.keys())
    label = "MCP: " + ", ".join(servers) if servers else "MCP"
    _set_status("mcp", label, "green")


def set_red() -> None:
    _set_status("mcp", "MCP", "red")
