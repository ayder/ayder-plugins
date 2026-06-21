# ayder-plugins

Official plugin collection for [ayder-cli](https://github.com/ayder/ayder-cli). Each plugin directory is a self-contained, installable unit that extends ayder with additional tools.

## Built-in Plugins

Plugins maintained in this repository:

| Plugin | Description | Dependencies |
|---|---|---|
| [`dbs-tools`](#dbs-tools) | DBS RAG API — semantic search over issues, tasks, and SQL | none |
| [`mcp-tool`](#mcp-tool) | MCP client proxy — connects to MCP servers and exposes their tools | `mcp>=1.0` |
| [`python-tools`](#python-tools) | CST-based Python code editor | `libcst>=1.0` |
| [`temporal-tools`](#temporal-tools) | Temporal workflow orchestration | `temporalio>=1.22,<1.23`, `pydantic>=2.0` |
| [`venv-tools`](#venv-tools) | Python virtual environment management | none |

## External Plugins

ayder plugins can be hosted anywhere — any public GitHub repository that contains a valid `plugin.toml` is installable directly:

```bash
ayder install-plugin https://github.com/some-user/my-ayder-plugin
ayder install-plugin https://github.com/some-org/ayder-tools/tree/main/my-plugin
```

Community-contributed plugins are not listed here. If you're building one, see [README_AYDER_PLUGIN.md](README_AYDER_PLUGIN.md) for the plugin development guide and contract.

---

## Installation

### Install from this repo (GitHub)

Install a plugin directly from a subdirectory of this repository:

```bash
# Install globally (available in every project)
ayder install-plugin https://github.com/ayder/ayder-plugins/tree/main/dbs-tools

# Install project-locally (only for the current project)
ayder install-plugin https://github.com/ayder/ayder-plugins/tree/main/venv-tools --project-local

# Install a plugin with pip dependencies
ayder install-plugin https://github.com/ayder/ayder-plugins/tree/main/python-tools
# → prompts to install libcst if not present; pass --yes to skip the prompt
```

### Install from a local directory

```bash
# Useful during development or for private plugins
ayder install-plugin /path/to/my-plugin
ayder install-plugin ./dbs-tools --project-local
```

### Force-overwrite an existing install

```bash
ayder install-plugin https://github.com/ayder/ayder-plugins/tree/main/venv-tools --force
```

---

## Managing Plugins

```bash
# List all installed plugins (global and project-local)
ayder list-plugins

# Update all plugins to their latest version
ayder update-plugin

# Update a specific plugin
ayder update-plugin dbs-tools

# Remove a plugin
ayder uninstall-plugin python-tools
```

---

## Plugin Scopes

**Global** (`~/.ayder/plugins/`) — available in every project on this machine.

**Project-local** (`.ayder/plugins/` in project root) — only available when ayder is run from that project. Use `--project-local` when installing.

Project-local plugins take precedence over global ones if there are tool name conflicts. A plugin name cannot exist in both scopes simultaneously.

---

## Plugin Reference

### dbs-tools

Semantic search over a DBS RAG API. Use it to find DBS-related issues, tasks, documentation, or SQL queries/files.

**Tool:** `dbs_tool`

```
dbs_tool(query, mode, url?, limit?, source_filter?, min_time?, timeout_seconds?)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Semantic query text |
| `mode` | `"md"` \| `"sql"` | yes | `md` = issues/tasks/docs; `sql` = SQL queries/files |
| `url` | string | no | Base API URL (default: `http://127.0.0.1:8000`) |
| `limit` | integer | no | Max results to return |
| `source_filter` | string | no | Exact-match source filter |
| `min_time` | number | no | SQL mode: minimum execution time in ms |
| `timeout_seconds` | integer | no | Request timeout (default: 60) |

Permission: `http` (makes outbound HTTP requests). Blocked in safe mode.

---

### python-tools

Structural Python code editor using Concrete Syntax Tree (CST) via `libcst`. Preserves indentation and comments during transformations.

**Tool:** `python_editor`

```
python_editor(file_path, method, params?)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_path` | string | yes | Path to the `.py` file |
| `method` | string | yes | One of: `get`, `list_all`, `replace`, `delete`, `rename`, `add_decorator`, `add_import`, `verify` |
| `params` | string (JSON) | no | Method-specific arguments (see below) |

**Method params:**

| Method | `params` JSON |
|---|---|
| `get` | `{"target_name": "MyClass"}` |
| `replace` | `{"target_name": "my_func", "new_code": "def my_func(): ..."}` |
| `delete` | `{"target_name": "old_func"}` |
| `rename` | `{"old_name": "OldName", "new_name": "NewName"}` |
| `add_decorator` | `{"target_name": "my_func", "decorator": "cache"}` |
| `add_import` | `{"module": "os", "name": "path"}` |
| `list_all` / `verify` | `{}` or omit `params` |

Permission: `w` (modifies files).

---

### temporal-tools

Manage Temporal workflows and queue operations from within ayder.

**Tool:** `temporal_workflow`

```
temporal_workflow(action, workflow_id?, queue_name?, signal_name?, payload?)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `action` | string | yes | One of: `start_workflow`, `query_workflow`, `signal_workflow`, `escalate`, `cancel_workflow`, `report_phase_result` |
| `workflow_id` | string | no | User/PM-assigned workflow identifier |
| `queue_name` | string | no | Target queue name for worker/workflow routing |
| `signal_name` | string | no | Signal identifier (e.g., `clarify`) |
| `payload` | object | no | Action-specific payload |

Permission: `w`. Blocked in safe mode.

The temporal worker is launched separately via `ayder --temporal-task-queue <queue>` (only available when this plugin is installed).

---

### mcp-tool

MCP client proxy that connects ayder to any running [Model Context Protocol](https://modelcontextprotocol.io) server and exposes its tools as first-class ayder tools.

**Tool:** `mcp_tool`

```
mcp_tool(server_name, tool_name, arguments?)
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `server_name` | string | yes | Name of the configured MCP server |
| `tool_name` | string | yes | Tool to invoke on the server |
| `arguments` | object | no | Tool-specific arguments |

MCP servers are configured in your ayder config. Once connected, their tools are available via `mcp_tool` or discovered automatically depending on your setup.

Permission: `r` by default; individual tool calls inherit the permission level of the MCP server's declared capabilities.

---

### venv-tools

Create and manage Python virtual environments from within ayder.

**Tools:** `create_virtualenv`, `install_requirements`, `list_virtualenvs`, `activate_virtualenv`, `remove_virtualenv`

| Tool | Description |
|---|---|
| `create_virtualenv` | Create a new venv (default name: `.venv`, default Python: `3.12`) |
| `install_requirements` | Install dependencies from `requirements.txt` or `pyproject.toml` |
| `list_virtualenvs` | List all venvs in the project directory |
| `activate_virtualenv` | Print activation instructions for a venv |
| `remove_virtualenv` | Remove a venv (supports `force=true`) |

Permission: `x` for create/install/remove, `r` for list/activate.

---

## Contributing a New Plugin

See [README_AYDER_PLUGIN.md](README_AYDER_PLUGIN.md) for the full plugin development guide.
