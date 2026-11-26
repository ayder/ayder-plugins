"""S22 / Evidence 1 (workflow): through the real registry's registered
handlers, drive one localhost fixture end to end and check actual values."""
import time

import pytest

from ayder_cli.core.context import ProjectContext
from ayder_cli.tools.registry import create_default_registry
from zendriver_tools_format import untrusted_line

pytestmark = pytest.mark.browser


def test_registry_workflow(fixture_server, staged_project):
    reg = create_default_registry(ProjectContext(root_dir=str(staged_project)))
    url = fixture_server + "/page.html"

    r = reg.execute("browser_open", {"url": url})
    assert r.is_success, r
    assert str(r).split("\n")[0] == untrusted_line(url)
    assert "t1" in str(r) and "throwaway" in str(r)

    r = reg.execute("browser_read", {})
    assert r.is_success and "rendered-text" in str(r)
    assert str(r).split("\n")[0] == untrusted_line(url)

    r = reg.execute("browser_type", {"selector": "#field", "value": "xyz"})
    assert r.is_success and "xyz" not in str(r)

    r = reg.execute("browser_click", {"selector": "#btn"})
    assert r.is_success, r

    r = reg.execute("browser_read", {"selector": "#out"})
    assert r.is_success and "changed-text" in str(r)

    r = reg.execute("browser_eval", {"script": "document.getElementById('field').value"})
    assert r.is_success and str(r).endswith('\n"xyz"')

    r = reg.execute("browser_console", {"clear": False})
    assert r.is_success and "first-script-marker" in str(r)

    t0 = time.monotonic()
    r = reg.execute("browser_click", {"selector": "#never", "timeout_seconds": 2})
    assert not r.is_success
    assert time.monotonic() - t0 < 5

    assert reg.execute("browser_close", {}).is_success
