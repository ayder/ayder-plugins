---
name: ayder-plugin-development
description: Use when creating, modifying, or debugging an ayder-cli plugin — adding tools to plugin.toml, writing ToolDefinition, implementing tool functions, or troubleshooting plugin loading failures.
---

# Ayder Plugin Development

## Overview

An ayder plugin is a directory with three pieces: `plugin.toml` (manifest), a definitions file (tool schemas), and implementation files (Python functions). Installed plugins appear alongside builtin tools automatically.

Full reference: `README_AYDER_PLUGIN.md` in the ayder-plugins repo root.

---

## Plugin Directory Layout

```
my-plugin/             ← directory name MUST match plugin.toml `name`
├── plugin.toml
├── my_definitions.py  ← filename set in [tools] definitions
└── my_impl.py
```

---

## plugin.toml Quick Reference

```toml
[plugin]
name        = "my-plugin"    # must match directory name exactly
version     = "1.0.0"
api_version = 1              # integer — NOT "1" (string breaks loading)
description = "What it does"
author      = "your-name"

[dependencies]               # optional — pip specifiers
requests = ">=2.28"

[tools]
definitions = "my_definitions.py"
```

---

## Definitions File

```python
from typing import Tuple
from ayder_cli.tools.definition import ToolDefinition

TOOL_DEFINITIONS: Tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="my_tool",
        description="...",
        parameters={"type": "object", "properties": {...}, "required": [...]},
        func_ref="my_impl:my_function",   # "bare_module:function" — no package prefix
        tags=("my-plugin",),
        permission="r",
    ),
)
```

---

## ToolDefinition Field Reference

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | str | required | Unique; underscores; no conflict with builtins or other plugins |
| `description` | str | required | Shown to the LLM — be precise |
| `parameters` | dict | required | OpenAI JSON Schema: `type/properties/required` |
| `func_ref` | str | required | `"module:function"` — **never empty** |
| `permission` | str | `"r"` | `"r"` read, `"w"` write, `"x"` execute, `"http"` network |
| `tags` | tuple | `("core",)` | Pick a plugin-specific tag; avoid builtin tags (see below) |
| `safe_mode_blocked` | bool | `False` | `True` for destructive/irreversible operations |
| `is_terminal` | bool | `False` | `True` ends the agent turn immediately after this tool |
| `description_template` | str | `None` | TUI label, supports `{param_name}` substitution |
| `system_prompt` | str | `""` | Injected into system prompt when tool is active |
| `parameter_aliases` | tuple | `()` | `(("alias", "canonical"), ...)` — LLM alias rewriting |
| `path_parameters` | tuple | `()` | Param names resolved against project root |

**Reserved tags** (do not use): `core`, `metadata`, `files`, `process`, `tasks`

---

## Implementation File

```python
from ayder_cli.core.result import ToolSuccess, ToolError

def my_function(
    input: str,
    project_ctx=None,      # injected: .root is a Path to project root
    process_manager=None,  # injected: background process manager
) -> ToolSuccess | ToolError:
    if not input:
        return ToolError("input must not be empty")
    return ToolSuccess(f"result: {input}")
```

`project_ctx` and `process_manager` are injected by name if present in the signature. All other parameters come from the LLM call.

---

## Intra-Plugin Imports

ayder adds the plugin directory to `sys.path` during loading. Use **bare module names** for imports within the same plugin:

```python
# Correct — bare module name
from my_client import MyClient

# Wrong — package path does not exist
from my_plugin.my_client import MyClient
```

---

## Common Mistakes

| Mistake | Effect | Fix |
|---|---|---|
| `api_version = "1"` (string in TOML) | `PluginError: api_version must be an integer` | `api_version = 1` |
| `func_ref = "my_pkg.my_module:fn"` | `ModuleNotFoundError` | `func_ref = "my_module:fn"` (bare name) |
| Empty `func_ref = ""` | `PluginError: ToolDefinition '...' has no func_ref` | Always set a valid func_ref |
| Dir name ≠ `name` in plugin.toml | Install rejected | Keep them identical |
| Intra-plugin import uses package path | `ModuleNotFoundError` at load time | Use bare module names |
| Using builtin tag (`core`, `files`, …) | `PluginError: conflicts with builtin tag` | Use a plugin-specific tag |
| Expecting auto-installed deps | `ImportError` at load time | User must run `ayder install-plugin` which prompts for deps |

---

## Testing Locally

```bash
# Install from local path
ayder install-plugin ./my-plugin

# Force-reinstall after changes
ayder install-plugin ./my-plugin --force

# See loading errors
AYDER_LOG_LEVEL=DEBUG ayder

# Check installed plugins
ayder list-plugins
```

---

## Install from GitHub

```bash
# Subdirectory of a multi-plugin repo
ayder install-plugin https://github.com/org/repo/tree/main/my-plugin

# Root of a single-plugin repo
ayder install-plugin https://github.com/org/my-plugin-repo
```
