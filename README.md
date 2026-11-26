# ayder-plugins

Official plugin collection for [ayder-cli](https://github.com/ayder/ayder-cli). Each plugin directory is a self-contained, installable unit that extends ayder with additional tools.

## Built-in Plugins

Plugins maintained in this repository:

| Plugin | Description | Dependencies |
|---|---|---|
| [`python-tools`](#python-tools) | CST-based Python code editor | `libcst>=1.0` |
| [`venv-tools`](#venv-tools) | Python virtual environment management | none |
| [`zendriver-tools`](#zendriver-tools) | Drive a real Chrome browser (open, read, click, type, eval, console, close) | `zendriver>=0.18,<0.19` |

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
ayder install-plugin https://github.com/ayder/ayder-plugins/tree/main/venv-tools

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
ayder install-plugin ./venv-tools --project-local
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
ayder update-plugin venv-tools

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

### zendriver-tools

Drive a real Chrome browser from ayder: read JavaScript-heavy pages, debug a localhost app, or work on a site you signed in to by hand. MVP: seven tools, one browser, one tab; macOS and Linux.

**Tools:** `browser_open`, `browser_read`, `browser_click`, `browser_type`, `browser_eval`, `browser_console`, `browser_close`

| Tool | Description |
|---|---|
| `browser_open` | Open an `http`/`https`/`about:blank` URL and wait for load; starts Chrome (headless, throwaway profile by default) |
| `browser_read` | Read rendered page text, optionally by CSS selector |
| `browser_click` | Click the first visible element matching a CSS selector |
| `browser_type` | Replace an input field's value (never echoes the value) |
| `browser_eval` | Evaluate a JSON-valued JavaScript expression once; promises awaited |
| `browser_console` | Read captured console messages and uncaught exceptions |
| `browser_close` | Stop the browser; deletes a throwaway profile, keeps a persistent one |

Permissions: `http` for open, `r` for read/console, `x` for click/type/eval, `w` for close. Open, click, type, eval and close are blocked in safe mode.

**Install (project-local):**

```bash
ayder install-plugin ./zendriver-tools --project
```

**Signing in by hand (persistent profile):**

1. `browser_open(url="<login page>", profile="work", headless=false)` — a visible window opens.
2. You sign in in that window yourself. Never ask the agent to type passwords or one-time codes.
3. `browser_close()`.
4. Later, reopen with `browser_open(url=..., profile="work")` to reuse the session. On a signed-in profile, the agent asks you before submitting forms, sending messages, buying, or deleting anything.

**License:** this plugin is AGPL-3.0 (matching zendriver); it carries its own `LICENSE` and is not distributed with ayder-cli, which stays MIT.

---

## Contributing a New Plugin

See [README_AYDER_PLUGIN.md](README_AYDER_PLUGIN.md) for the full plugin development guide.
