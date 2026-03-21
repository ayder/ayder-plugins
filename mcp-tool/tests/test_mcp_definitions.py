import json
import sys
import importlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _reload_definitions(tmp_cwd=None, monkeypatch=None):
    """Import mcp_definitions fresh, optionally from a specific cwd."""
    sys.modules.pop("mcp_definitions", None)
    if monkeypatch and tmp_cwd:
        monkeypatch.chdir(tmp_cwd)
    return importlib.import_module("mcp_definitions")


def test_no_mcp_json_gives_empty_definitions(tmp_path, monkeypatch):
    """Missing mcp.json → TOOL_DEFINITIONS = ()"""
    mod = _reload_definitions(tmp_path, monkeypatch)
    assert mod.TOOL_DEFINITIONS == ()


def test_invalid_json_gives_empty_definitions(tmp_path, monkeypatch):
    """.ayder/mcp.json with invalid JSON → TOOL_DEFINITIONS = ()"""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    (ayder_dir / "mcp.json").write_text("not valid json")
    mod = _reload_definitions(tmp_path, monkeypatch)
    assert mod.TOOL_DEFINITIONS == ()


def test_valid_config_with_mock_server(tmp_path, monkeypatch):
    """Valid mcp.json + successful server connection → TOOL_DEFINITIONS has tools."""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    config = {"mcpServers": {"test-server": {"url": "http://localhost:9999/mcp"}}}
    (ayder_dir / "mcp.json").write_text(json.dumps(config))

    mock_tool = MagicMock()
    mock_tool.name = "do_thing"
    mock_tool.description = "Does a thing"
    mock_tool.inputSchema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }

    with patch("mcp_client.connect_server", return_value=[mock_tool]):
        with patch("mcp_client.ensure_loop"):
            with patch("mcp_client.make_handler", return_value=lambda **k: None):
                mod = _reload_definitions(tmp_path, monkeypatch)

    assert len(mod.TOOL_DEFINITIONS) == 1
    td = mod.TOOL_DEFINITIONS[0]
    assert td.name == "do_thing"   # no conflict → natural name
    assert td.tags == ("mcp",)
    assert td.permission == "http"
    assert td.func_ref == "mcp_tool:do_thing"


def test_conflict_with_existing_tool_uses_prefix(tmp_path, monkeypatch):
    """Tool name matching an existing ayder tool → prefixed with server name."""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    config = {"mcpServers": {"myserver": {"url": "http://localhost:9999/mcp"}}}
    (ayder_dir / "mcp.json").write_text(json.dumps(config))

    mock_tool = MagicMock()
    mock_tool.name = "list_tasks"   # conflicts with builtin
    mock_tool.description = "Lists tasks"
    mock_tool.inputSchema = {"type": "object", "properties": {}}

    # Simulate existing tool named "list_tasks"
    fake_existing = MagicMock()
    fake_existing.name = "list_tasks"

    with patch("mcp_client.connect_server", return_value=[mock_tool]):
        with patch("mcp_client.ensure_loop"):
            with patch("mcp_client.make_handler", return_value=lambda **k: None):
                with patch(
                    "ayder_cli.tools.definition.TOOL_DEFINITIONS",
                    (fake_existing,),
                ):
                    mod = _reload_definitions(tmp_path, monkeypatch)

    assert len(mod.TOOL_DEFINITIONS) == 1
    assert mod.TOOL_DEFINITIONS[0].name == "myserver__list_tasks"


def test_two_servers_same_tool_name_second_gets_prefix(tmp_path, monkeypatch):
    """Second server with duplicate tool name → prefixed, first keeps natural name."""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    config = {
        "mcpServers": {
            "server_a": {"url": "http://localhost:8001/mcp"},
            "server_b": {"url": "http://localhost:8002/mcp"},
        }
    }
    (ayder_dir / "mcp.json").write_text(json.dumps(config))

    def make_tool(name):
        t = MagicMock()
        t.name = name
        t.description = f"Tool {name}"
        t.inputSchema = {"type": "object", "properties": {}}
        return t

    tool_read = make_tool("read_file")

    call_count = 0
    def mock_connect(name, config):
        nonlocal call_count
        call_count += 1
        return [tool_read]

    with patch("mcp_client.connect_server", side_effect=mock_connect):
        with patch("mcp_client.ensure_loop"):
            with patch("mcp_client.make_handler", return_value=lambda **k: None):
                with patch("ayder_cli.tools.definition.TOOL_DEFINITIONS", ()):
                    mod = _reload_definitions(tmp_path, monkeypatch)

    names = {td.name for td in mod.TOOL_DEFINITIONS}
    assert "read_file" in names              # server_a gets natural name
    assert "server_b__read_file" in names    # server_b gets prefix


def test_failed_server_skipped(tmp_path, monkeypatch):
    """Server that fails to connect is skipped; other servers still load."""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    config = {
        "mcpServers": {
            "bad": {"url": "http://bad:1/mcp"},
            "good": {"url": "http://good:2/mcp"},
        }
    }
    (ayder_dir / "mcp.json").write_text(json.dumps(config))

    mock_tool = MagicMock()
    mock_tool.name = "good_tool"
    mock_tool.description = "A good tool"
    mock_tool.inputSchema = {"type": "object", "properties": {}}

    def mock_connect(name, _config):
        if name == "bad":
            raise ConnectionError("refused")
        return [mock_tool]

    with patch("mcp_client.connect_server", side_effect=mock_connect):
        with patch("mcp_client.ensure_loop"):
            with patch("mcp_client.make_handler", return_value=lambda **k: None):
                with patch("ayder_cli.tools.definition.TOOL_DEFINITIONS", ()):
                    mod = _reload_definitions(tmp_path, monkeypatch)

    assert len(mod.TOOL_DEFINITIONS) == 1
    assert mod.TOOL_DEFINITIONS[0].name == "good_tool"


def test_stdio_server_gets_x_permission(tmp_path, monkeypatch):
    """Stdio server (command/args) gets permission='x'."""
    ayder_dir = tmp_path / ".ayder"
    ayder_dir.mkdir()
    config = {"mcpServers": {"local": {"command": "npx", "args": ["-y", "server"]}}}
    (ayder_dir / "mcp.json").write_text(json.dumps(config))

    mock_tool = MagicMock()
    mock_tool.name = "local_tool"
    mock_tool.description = "Local tool"
    mock_tool.inputSchema = {"type": "object", "properties": {}}

    with patch("mcp_client.connect_server", return_value=[mock_tool]):
        with patch("mcp_client.ensure_loop"):
            with patch("mcp_client.make_handler", return_value=lambda **k: None):
                with patch("ayder_cli.tools.definition.TOOL_DEFINITIONS", ()):
                    mod = _reload_definitions(tmp_path, monkeypatch)

    assert mod.TOOL_DEFINITIONS[0].permission == "x"
