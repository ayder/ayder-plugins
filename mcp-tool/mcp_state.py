"""Persistent singleton state for the MCP client plugin.

This module is NEVER referenced in any func_ref, so it is never popped
from sys.modules by ayder's load_plugin_definitions loop. It is imported
exactly once and its state persists across all re-imports of mcp_tool.py.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPState:
    """All mutable state for the MCP plugin. Mutate fields — never rebind `state`."""
    loop: asyncio.AbstractEventLoop | None = None
    loop_thread: threading.Thread | None = None
    sessions: dict[str, Any] = field(default_factory=dict)
    handlers: dict[str, Any] = field(default_factory=dict)


# Module-level singleton — imported by reference so mutations are visible everywhere
state = MCPState()
