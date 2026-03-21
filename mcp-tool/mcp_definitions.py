"""MCP plugin definitions file — load orchestrator.

Runs synchronously at import time:
1. Read .ayder/mcp.json
2. Start background event loop
3. Connect to each MCP server, get tool lists
4. Resolve names (natural first, prefix on conflict)
5. Build TOOL_DEFINITIONS tuple
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Tuple

import ayder_cli.tools.definition as _ayder_defs_mod
from ayder_cli.tools.definition import ToolDefinition

import mcp_client

logger = logging.getLogger(__name__)

_MCP_JSON_PATH = Path.cwd() / ".ayder" / "mcp.json"


def _load_config() -> dict | None:
    """Return parsed mcpServers dict or None on missing/invalid."""
    if not _MCP_JSON_PATH.exists():
        return None
    try:
        data = json.loads(_MCP_JSON_PATH.read_text(encoding="utf-8"))
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("mcp.json invalid: %s", exc)
        mcp_client.set_red()
        return None


def _resolve_name(natural: str, server_name: str, taken: set[str]) -> tuple[str, bool]:
    """Return (final_name, was_prefixed)."""
    if natural not in taken:
        return natural, False
    prefixed = f"{server_name}__{natural}"
    return prefixed, True


def _build_definitions(servers: dict) -> Tuple[ToolDefinition, ...]:
    """Connect to all servers and build TOOL_DEFINITIONS."""
    mcp_client.ensure_loop()

    taken: set[str] = {td.name for td in _ayder_defs_mod.TOOL_DEFINITIONS}
    defs: list[ToolDefinition] = []

    for server_name, server_config in servers.items():
        try:
            tools = mcp_client.connect_server(server_name, server_config)
        except Exception as exc:
            logger.debug("MCP server '%s' failed to connect: %s", server_name, exc)
            continue

        permission = "x" if "command" in server_config else "http"

        for tool in tools:
            resolved_name, was_prefixed = _resolve_name(tool.name, server_name, taken)
            if was_prefixed:
                print(
                    f"[mcp-tool] '{tool.name}' from server '{server_name}' conflicts "
                    f"— registering as '{resolved_name}'",
                    file=sys.stderr,
                )

            handler = mcp_client.make_handler(server_name, tool.name)
            from mcp_state import state
            state.handlers[resolved_name] = handler
            taken.add(resolved_name)

            defs.append(
                ToolDefinition(
                    name=resolved_name,
                    description=f"[{server_name}] {tool.description or tool.name}",
                    parameters=tool.inputSchema,
                    func_ref=f"mcp_tool:{resolved_name}",
                    tags=("mcp",),
                    permission=permission,
                    safe_mode_blocked=False,
                )
            )

    return tuple(defs)


# --- Module-level execution (runs at import time) ---

_servers = _load_config()

if _servers is None:
    # Missing or invalid mcp.json
    TOOL_DEFINITIONS: Tuple[ToolDefinition, ...] = ()
else:
    TOOL_DEFINITIONS = _build_definitions(_servers)
    if TOOL_DEFINITIONS:
        mcp_client.set_green()
    else:
        mcp_client.set_red()
