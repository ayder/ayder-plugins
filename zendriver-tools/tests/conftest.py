"""Shared fixtures: bare-name imports, an isolated ayder global plugin folder,
a staged project install, a local-only fixture server, and per-test browser
teardown (on failure too)."""
import atexit
import functools
import http.server
import os
import pathlib
import shutil
import sys
import tempfile
import threading

import pytest

# ayder binds its global plugin folder from Path.home() when
# ayder_cli.tools.plugin_manager is imported, and ayder_cli.tools.definition
# loads every plugin found there. Do both under an empty home, before any test
# module imports ayder, so the suite never runs a copy installed in the real
# ~/.ayder/plugins. HOME is restored at once: Chrome runs with the real one.
_EMPTY_HOME = tempfile.mkdtemp(prefix="zdt-test-home-")
atexit.register(shutil.rmtree, _EMPTY_HOME, True)
_real_home = os.environ.get("HOME")
os.environ["HOME"] = _EMPTY_HOME
try:
    import ayder_cli.tools.plugin_manager as _pm
    import ayder_cli.tools.definition  # noqa: F401  (global discovery runs here)
finally:
    if _real_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = _real_home
assert str(_pm.GLOBAL_PLUGINS_DIR).startswith(_EMPTY_HOME), _pm.GLOBAL_PLUGINS_DIR

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
_STAGE_IGNORE = shutil.ignore_patterns(
    "tests", "__pycache__", ".pytest_cache", "*.pyc")


@pytest.fixture
def staged_project(tmp_path):
    """A temp project with this working tree's plugin copied into its
    .ayder/plugins, as `ayder install-plugin --project` lays it out."""
    project = tmp_path / "project"
    shutil.copytree(PLUGIN_ROOT,
                    project / ".ayder" / "plugins" / "zendriver-tools",
                    ignore=_STAGE_IGNORE)
    return project


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture
def fixture_server():
    handler = functools.partial(_QuietHandler, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture(autouse=True)
def browser_teardown(request, tmp_path, monkeypatch):
    """Browser tests: temp profiles root; afterwards kill any recorded
    child through its handle, remove temp dirs, drain/stop/join/close the
    private loop and reset state — independent of plugin close/exit code."""
    is_browser = request.node.get_closest_marker("browser") is not None
    if is_browser:
        monkeypatch.setenv("AYDER_BROWSER_PROFILES_DIR",
                           str(tmp_path / "profiles"))
    yield
    if not is_browser:
        return
    import zendriver_tools_state as state
    h = state.handle
    if h is not None:
        try:
            if h.poll() is None:
                h.terminate()
                try:
                    h.wait(timeout=5)
                except Exception:
                    h.kill()
                    h.wait(timeout=2)
        except Exception:
            pass
    import shutil
    if state.profile_dir is not None and state.profile_kind == "throwaway":
        shutil.rmtree(state.profile_dir, ignore_errors=True)
    shutil.rmtree(tmp_path / "profiles", ignore_errors=True)
    state.reset_for_test()
