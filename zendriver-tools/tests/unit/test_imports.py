"""Installed operation: ayder's loader puts the plugin folder on sys.path only
while the plugin loads (plugin_manager.load_plugin_definitions), so every
plugin-local import must run at module level, never first inside a function."""
import ast
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LOCAL = ("zendriver_tools_", "browser_tools", "browser_definitions")


def _is_local(name):
    return bool(name) and name.split(".")[0].startswith(LOCAL)


def test_no_plugin_local_import_inside_functions():
    found = []
    for path in sorted(PLUGIN_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                found += [f"{path.name}:{node.lineno} {n}"
                          for n in names if _is_local(n)]
    assert found == []


def test_no_module_loaded_from_the_global_install():
    """conftest binds ayder's global plugin folder to an empty home, so the
    suite never runs a copy installed in the real ~/.ayder/plugins."""
    real_global = os.path.join(os.path.expanduser("~"), ".ayder", "plugins")
    leaked = [
        f"{name}: {mod.__file__}" for name, mod in list(sys.modules.items())
        if _is_local(name) and getattr(mod, "__file__", None)
        and os.path.realpath(mod.__file__).startswith(os.path.realpath(real_global))
    ]
    assert leaked == []
    import ayder_cli.tools.plugin_manager as pm
    assert not os.path.realpath(pm.GLOBAL_PLUGINS_DIR).startswith(
        os.path.realpath(real_global))
