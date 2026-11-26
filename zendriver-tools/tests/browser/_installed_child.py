"""Child for the installed-operation test. Run with `python -I`, so neither the
plugin source nor this folder is on sys.path: the plugin is reachable only
through ayder's loader, from the copy staged in <project>/.ayder/plugins.

argv: project, empty_home, stub_chrome, url
"""
import json
import os
import sys

project, empty_home, stub, url = sys.argv[1:5]

# Bind ayder's global plugin folder (Path.home() at import) to an empty home,
# then restore HOME so Chrome runs in the normal user environment.
real_home = os.environ["HOME"]
os.environ["HOME"] = empty_home
import ayder_cli.tools.plugin_manager as pm  # noqa: E402
from ayder_cli.core.context import ProjectContext  # noqa: E402
from ayder_cli.tools.registry import create_default_registry  # noqa: E402
os.environ["HOME"] = real_home

out = {
    "global_dir": str(pm.GLOBAL_PLUGINS_DIR),
    "plugin_on_path": [p for p in sys.path if "zendriver-tools" in p],
}
reg = create_default_registry(ProjectContext(root_dir=project))


def call(name, args):
    r = reg.execute(name, args)
    return {"ok": r.is_success, "text": str(r)}


# 1. A launch that begins but never serves CDP: cleanup must reap the stub.
os.environ["AYDER_BROWSER_EXECUTABLE"] = stub
out["failed_open"] = call("browser_open", {"url": url, "timeout_seconds": 3})
del os.environ["AYDER_BROWSER_EXECUTABLE"]
st = sys.modules.get("zendriver_tools_state")
out["after_failure"] = None if st is None else {
    "pending_reap": st.pending_reap, "cleanup_pending": st.cleanup_pending,
    "browser": st.browser is not None}

# 2. Real Chrome through the same registry.
out["open"] = call("browser_open", {"url": url})
out["eval"] = call("browser_eval", {"script": "1 + 1"})
out["close"] = call("browser_close", {})

out["module_files"] = {
    name: getattr(mod, "__file__", None) for name, mod in sys.modules.items()
    if name.startswith("zendriver_tools_") or name == "browser_tools"}
print(json.dumps(out), flush=True)
