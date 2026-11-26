"""Shared fixtures: bare-name imports, a local-only fixture server, and
per-test browser teardown (on failure too)."""
import functools
import http.server
import pathlib
import sys
import threading

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"


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
