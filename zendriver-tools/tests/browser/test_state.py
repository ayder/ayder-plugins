"""S16 / AC-18 (reduced): distinct registered handlers, one shared browser."""
import shutil

import pytest

import zendriver_tools_state as state
from ayder_cli.core.context import ProjectContext
from ayder_cli.tools.plugin_manager import load_plugin_definitions
from ayder_cli.tools.registry import create_default_registry

pytestmark = pytest.mark.browser


def test_registry_handlers_share_one_browser(fixture_server, tmp_path):
    from conftest import PLUGIN_ROOT
    project = tmp_path / "project"
    staged = project / ".ayder" / "plugins" / "zendriver-tools"
    staged.parent.mkdir(parents=True)
    shutil.copytree(PLUGIN_ROOT, staged,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    reg = create_default_registry(ProjectContext(root_dir=str(project)))
    names = set(reg.get_registered_tools())
    assert {"browser_open", "browser_read", "browser_close"} <= names

    # each func_ref resolved through its own re-import of browser_tools
    h_open = reg._registry["browser_open"]
    h_read = reg._registry["browser_read"]
    h_close = reg._registry["browser_close"]
    assert h_open is not h_read is not h_close

    url = fixture_server + "/page.html"
    r = reg.execute("browser_open", {"url": url})
    assert r.is_success, r
    first = state.browser
    assert first is not None
    r = reg.execute("browser_read", {})
    assert r.is_success and "rendered-text" in str(r)
    assert state.browser is first          # same object across handlers
    r = reg.execute("browser_close", {})
    assert r.is_success, r
    assert state.browser is None
