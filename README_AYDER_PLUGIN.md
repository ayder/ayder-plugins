# Ayder Plugin Development Guide

This guide covers everything you need to build, test, and publish a plugin for ayder-cli.

---

## Contents

1. [What is a plugin?](#1-what-is-a-plugin)
2. [Plugin directory layout](#2-plugin-directory-layout)
3. [plugin.toml reference](#3-plugintoml-reference)
4. [Definitions file reference](#4-definitions-file-reference)
5. [ToolDefinition field reference](#5-tooldefinition-field-reference)
6. [Implementation file conventions](#6-implementation-file-conventions)
7. [Writing a complete plugin: step-by-step](#7-writing-a-complete-plugin-step-by-step)
8. [Intra-plugin imports](#8-intra-plugin-imports)
9. [Testing your plugin locally](#9-testing-your-plugin-locally)
10. [Publishing to GitHub](#10-publishing-to-github)
11. [How ayder loads plugins](#11-how-ayder-loads-plugins)
12. [Constraints and gotchas](#12-constraints-and-gotchas)

---

## 1. What is a plugin?

A plugin is a directory with three things:

1. A `plugin.toml` manifest
2. A *definitions file* that exports a `TOOL_DEFINITIONS` tuple
3. One or more *implementation files* with the actual Python functions

Plugins are installed into `~/.ayder/plugins/` (global) or `.ayder/plugins/` inside a project (project-local). Once installed, their tools appear alongside ayder's builtin tools automatically.

---

## 2. Plugin directory layout

```
my-plugin/
├── plugin.toml              # required — manifest
├── my_tool_definitions.py   # required — tool schemas
└── my_tool.py               # required — implementation(s)
```

Additional Python modules are fine — just import them from within the plugin using bare module names (see [Intra-plugin imports](#8-intra-plugin-imports)).

```
my-plugin/
├── plugin.toml
├── my_definitions.py
├── my_tool.py
├── my_client.py             # helper module
└── my_models.py             # pydantic models, etc.
```

The directory name becomes the plugin's install name. It must match the `name` field in `plugin.toml`.

---

## 3. plugin.toml reference

```toml
[plugin]
name        = "my-plugin"       # must match directory name
version     = "1.0.0"           # semver string
api_version = 1                 # integer — must be 1 for current ayder
description = "What this does"
author      = "your-name"

[dependencies]                  # optional — pip-compatible specifiers
requests  = ">=2.28"
pydantic  = ">=2.0"

[tools]
definitions = "my_definitions.py"   # relative to plugin root
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Must match the directory name exactly |
| `version` | string | Semver; shown in `ayder list-plugins` |
| `api_version` | integer | Must be `1` |
| `description` | string | Shown in `ayder list-plugins` |
| `author` | string | Free-form string |
| `[tools] definitions` | string | Filename of the definitions module |

### `[dependencies]`

Keys are package names, values are pip version specifiers. When a user runs `ayder install-plugin`, they are prompted to install these packages (or run with `--yes` to skip the prompt). The specifiers are passed directly to `pip install`.

```toml
[dependencies]
libcst    = ">=1.0"
httpx     = ">=0.27,<1.0"
```

If your plugin has no third-party dependencies, omit the `[dependencies]` section entirely.

---

## 4. Definitions file reference

The definitions file must export a module-level `TOOL_DEFINITIONS` tuple containing `ToolDefinition` instances:

```python
from typing import Tuple
from ayder_cli.tools.definition import ToolDefinition

TOOL_DEFINITIONS: Tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="my_tool",
        description="A brief description of what this tool does.",
        parameters={
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The input to process",
                },
            },
            "required": ["input"],
        },
        func_ref="my_tool:my_tool_function",  # "module:function"
        tags=("my-plugin",),
        permission="r",
    ),
)
```

The `func_ref` format is `"module_name:function_name"` where `module_name` is the bare Python module name relative to the plugin root (no package prefix). ayder adds the plugin directory to `sys.path` temporarily to resolve it.

---

## 5. ToolDefinition field reference

All fields except `name`, `description`, `parameters`, and `func_ref` are optional.

### Identity

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Unique tool name. Must not conflict with any builtin tool or other installed plugin. Use underscores. |
| `description` | `str` | required | Shown to the LLM. Be precise — this is what the model uses to decide when to call the tool. |
| `parameters` | `dict` | required | OpenAI-compatible JSON Schema object. Include `"type": "object"`, `"properties"`, and `"required"`. |
| `func_ref` | `str` | required | `"module_name:function_name"`. Must not be empty. |

### Permission

| Field | Type | Default | Description |
|---|---|---|---|
| `permission` | `str` | `"r"` | Permission level shown to users before execution. |

Allowed values:

| Value | Meaning |
|---|---|
| `"r"` | Read-only — does not modify state |
| `"w"` | Write — modifies files or data |
| `"x"` | Execute — runs subprocesses or system commands |
| `"http"` | Network — makes outbound HTTP requests |

### Flags

| Field | Type | Default | Description |
|---|---|---|---|
| `is_terminal` | `bool` | `False` | If `True`, the tool's output ends the agent's response turn immediately. |
| `safe_mode_blocked` | `bool` | `False` | If `True`, the tool is unavailable when ayder runs in safe mode. Use for destructive or irreversible operations. |

### UI

| Field | Type | Default | Description |
|---|---|---|---|
| `description_template` | `str \| None` | `None` | Human-readable description shown in the TUI during execution. Supports `{param_name}` substitution from the call arguments. Example: `"Processing {file_path}"`. |

### Capability tags

| Field | Type | Default | Description |
|---|---|---|---|
| `tags` | `Tuple[str, ...]` | `("core",)` | Used by agents to filter which tools are available. Choose a tag that identifies your plugin (e.g., `("my-plugin",)`). Do not use builtin tags: `core`, `metadata`, `files`, `process`, `tasks`. |

### System prompt injection

| Field | Type | Default | Description |
|---|---|---|---|
| `system_prompt` | `str` | `""` | Text injected into the system prompt when this tool is included in the active tool set. Use to give the LLM context about when to use the tool. |

### Parameter normalization

| Field | Type | Default | Description |
|---|---|---|---|
| `parameter_aliases` | `Tuple[Tuple[str, str], ...]` | `()` | Alias mappings `(("alias", "canonical"), ...)`. If the LLM passes `alias`, ayder rewrites it to `canonical` before dispatch. |
| `path_parameters` | `Tuple[str, ...]` | `()` | Parameter names that hold file paths. ayder resolves these against the project root before dispatch. |

---

## 6. Implementation file conventions

### Function signature

Tool functions receive keyword arguments matching the parameter names in the schema, plus optional injection parameters:

```python
def my_tool_function(
    input: str,                              # from schema
    project_ctx=None,                        # injected if present in signature
    process_manager=None,                    # injected if present in signature
) -> str:
    ...
```

ayder inspects the function signature and injects `project_ctx` (a `ProjectContext` instance with `.root: Path`) and `process_manager` if those parameter names appear. Other parameters come from the LLM call.

### Return type

Functions should return either:

- `ayder_cli.core.result.ToolSuccess(str)` — successful result (subclass of `str`)
- `ayder_cli.core.result.ToolError(str)` — error result (subclass of `str`)

Plain `str` is accepted but not recommended. Both `ToolSuccess` and `ToolError` are `str` subclasses, so they work anywhere a string is expected.

```python
from ayder_cli.core.result import ToolSuccess, ToolError

def my_tool_function(input: str) -> ToolSuccess | ToolError:
    if not input:
        return ToolError("input must not be empty")
    return ToolSuccess(f"Processed: {input}")
```

`ToolError` has an optional `.category` property: `"security"`, `"validation"`, `"execution"`, or `"general"`.

---

## 7. Writing a complete plugin: step-by-step

This example builds a minimal `hello-plugin` with one tool.

### Step 1: Create the directory structure

```bash
mkdir hello-plugin
cd hello-plugin
```

### Step 2: Write `plugin.toml`

```toml
[plugin]
name        = "hello-plugin"
version     = "1.0.0"
api_version = 1
description = "A hello-world demonstration plugin"
author      = "your-name"

[tools]
definitions = "hello_definitions.py"
```

### Step 3: Write the implementation file (`hello.py`)

```python
from ayder_cli.core.result import ToolSuccess, ToolError


def greet(name: str, formal: bool = False) -> ToolSuccess | ToolError:
    if not name.strip():
        return ToolError("name must not be empty")
    greeting = "Good day" if formal else "Hello"
    return ToolSuccess(f"{greeting}, {name}!")
```

### Step 4: Write the definitions file (`hello_definitions.py`)

```python
from typing import Tuple
from ayder_cli.tools.definition import ToolDefinition

TOOL_DEFINITIONS: Tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="greet",
        description=(
            "Greet a person by name. "
            "Use when the user wants to say hello to someone."
        ),
        description_template="Greeting {name}",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The person's name",
                },
                "formal": {
                    "type": "boolean",
                    "description": "Use a formal greeting (default: false)",
                    "default": False,
                },
            },
            "required": ["name"],
        },
        func_ref="hello:greet",      # hello.py : greet function
        tags=("hello-plugin",),
        permission="r",
        safe_mode_blocked=False,
    ),
)
```

### Step 5: Install and test

```bash
# Install from local directory
ayder install-plugin ./hello-plugin

# Verify it appears
ayder list-plugins
```

---

## 8. Intra-plugin imports

When ayder loads your plugin, it temporarily adds the plugin directory to `sys.path`. This means all modules at the plugin root are importable by bare name — no package prefix needed.

**Correct** (intra-plugin import):
```python
# Inside temporal_client.py
from temporal_contract import MyDataClass   # bare name — works
```

**Wrong** (would fail outside the plugin install location):
```python
from temporal_tools.temporal_contract import MyDataClass  # no package, never works
from ayder_cli.services.temporal_contract import MyDataClass  # wrong namespace
```

Use bare module names for any cross-file imports *within* the same plugin. For imports from ayder itself (e.g., `ToolDefinition`, `ToolSuccess`), use the full `ayder_cli.*` path — these are always available since ayder is installed in the same environment.

---

## 9. Testing your plugin locally

### Install from local path

```bash
ayder install-plugin /absolute/path/to/my-plugin
# or, from within the plugin repo:
ayder install-plugin ./my-plugin
```

### Verify loading

```bash
ayder list-plugins
# Should show your plugin with scope "global"
```

### Force-reinstall after changes

```bash
ayder install-plugin ./my-plugin --force
```

### Project-local install (isolated to one project)

```bash
cd /path/to/your/project
ayder install-plugin ./my-plugin --project-local
ayder list-plugins
# Should show scope "project"
```

### Check for errors

If your plugin fails to load, ayder logs a warning and skips it. Run ayder with `--debug` (or set `AYDER_LOG_LEVEL=DEBUG`) to see the full traceback:

```bash
AYDER_LOG_LEVEL=DEBUG ayder
```

Look for lines like:
```
WARNING  Skipping plugin 'my-plugin': PluginError(...)
```

Common causes:
- `plugin.toml` missing a required field
- `TOOL_DEFINITIONS` missing from the definitions module
- `func_ref` pointing to a non-existent module or function
- A `ToolDefinition` with an empty `func_ref`
- `api_version` is not an integer in `plugin.toml`

---

## 10. Publishing to GitHub

Plugins can be installed directly from GitHub subdirectories. The standard layout for a multi-plugin repo is:

```
my-plugins-repo/
├── README.md
├── hello-plugin/
│   ├── plugin.toml
│   ├── hello_definitions.py
│   └── hello.py
└── another-plugin/
    ├── plugin.toml
    ├── another_definitions.py
    └── another.py
```

Users install from the subdirectory URL:

```bash
ayder install-plugin https://github.com/your-org/my-plugins-repo/tree/main/hello-plugin
```

ayder parses the URL, identifies `your-org/my-plugins-repo` as the owner/repo, `main` as the branch (stripped from the path), and `hello-plugin` as the subdirectory to download. It fetches the files via the GitHub API (no `git` required on the user's machine) and records the commit SHA so updates are deterministic.

### Single-plugin repo

If your repo contains exactly one plugin at the root:

```
my-plugin-repo/
├── plugin.toml
├── my_definitions.py
└── my_impl.py
```

```bash
ayder install-plugin https://github.com/your-org/my-plugin-repo
```

---

## 11. How ayder loads plugins

Understanding the loading lifecycle helps debug issues.

### Phase 1 — global plugins at import time

When `ayder_cli.tools.definition` is imported (at startup), it calls `discover_global_plugins()` which:

1. Iterates `~/.ayder/plugins/` sorted by directory name
2. For each plugin directory with a `plugin.toml`:
   - Checks `api_version` compatibility
   - Temporarily adds the plugin dir to `sys.path`
   - Imports the definitions module, reads `TOOL_DEFINITIONS`
   - Resolves each `func_ref` eagerly (imports the implementation module, looks up the function)
   - Removes the plugin dir from `sys.path`
3. Merges all definitions into `TOOL_DEFINITIONS`

A broken global plugin logs a warning and is skipped. Other plugins are unaffected.

### Phase 2 — project-local plugins at runtime

When `create_default_registry()` is called (when an agent session starts), it:

1. Looks for `.ayder/plugins/` in the project root
2. For each plugin directory there:
   - Checks for name conflicts with the global plugin list
   - Checks for tool name conflicts with already-registered tools
   - Only registers if all pre-checks pass (atomic — no partial registration)
   - Calls `register_dynamic_tool()` for each definition

### Tool name conflicts

- A tool name must be unique across all builtins, global plugins, and project-local plugins
- A plugin directory name (e.g., `venv-tools`) must not conflict with builtin tag names
- If a conflict is detected, the entire plugin is rejected with an error (not just the conflicting tool)

---

## 12. Constraints and gotchas

### `func_ref` is required

Every `ToolDefinition` in a plugin must have a non-empty `func_ref`. Unlike builtin tools (which can be registered manually), plugin tools are always auto-registered from `func_ref`.

### Module naming

Keep module filenames lowercase with underscores (e.g., `my_tool.py`, `my_client.py`). Avoid naming a module the same as a stdlib or popular third-party package — there is no package namespace isolation.

### `sys.path` is temporary during load

ayder adds the plugin directory to `sys.path` only while loading. The implementation modules are cached in `sys.modules` after import, so they remain accessible after `sys.path` is restored — but any subsequent dynamic imports from within those modules must use bare names only (see [Intra-plugin imports](#8-intra-plugin-imports)).

### No circular imports between plugins

Plugin A cannot import from Plugin B. Each plugin is loaded independently.

### `api_version` must be an integer in TOML

```toml
# correct
api_version = 1

# wrong — TOML treats this as a string
api_version = "1"
```

### Dependency installation is separate from loading

Installing a plugin copies the files but does not automatically install Python dependencies. The user is prompted during `ayder install-plugin` to run `pip install`. If dependencies are missing at load time, the plugin fails with an `ImportError` and is skipped.

### Plugin name must match directory name

The `name` field in `plugin.toml` must exactly match the directory name. The directory name is used as the install key; the `name` field is validated against it at install time.

### Safe mode

Set `safe_mode_blocked=True` on any tool that makes writes, executes subprocesses, or calls external services that cannot be undone. Users who run ayder in safe mode expect all such tools to be unavailable.
