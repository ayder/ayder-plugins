"""S22 / Evidence 1 (definitions part): a fresh isolated process builds the
real registry from a project-installed copy."""
import json
import os
import subprocess
import sys

SCRIPT = r"""
import json, os
from ayder_cli.core.context import ProjectContext
from ayder_cli.tools.registry import create_default_registry
from ayder_cli.tools.definition import TOOL_DEFINITIONS
reg = create_default_registry(ProjectContext(root_dir=os.getcwd()))
defs = list(TOOL_DEFINITIONS) + reg._dynamic_definitions
browser = {td.name: td for td in defs if "browser" in td.tags}
out = {
    "names": sorted(browser),
    "flags": {n: [td.permission, td.safe_mode_blocked] for n, td in browser.items()},
    "budget": {n: td.max_result_chars for n, td in browser.items()},
    "prompt": bool(browser.get("browser_open") and browser["browser_open"].system_prompt),
    "handler_files": {n: reg._registry[n].__code__.co_filename for n in browser},
    "total": len(reg.get_registered_tools()),
}
print(json.dumps(out))
"""


def test_registry_smoke(tmp_path, staged_project):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")   # isolate global plugins
    (tmp_path / "home").mkdir()
    r = subprocess.run([sys.executable, "-I", "-c", SCRIPT],
                       cwd=staged_project, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["names"] == ["browser_click", "browser_close", "browser_console",
                            "browser_eval", "browser_open", "browser_read",
                            "browser_type"]
    assert out["flags"] == {
        "browser_open": ["http", True],
        "browser_read": ["r", False],
        "browser_click": ["x", True],
        "browser_type": ["x", True],
        "browser_eval": ["x", True],
        "browser_console": ["r", False],
        "browser_close": ["w", True],
    }
    assert out["budget"]["browser_read"] == 0
    assert out["budget"]["browser_eval"] == 0
    assert out["prompt"] is True
    installed = str(staged_project / ".ayder" / "plugins" / "zendriver-tools")
    for f in out["handler_files"].values():
        assert f.startswith(installed), f
