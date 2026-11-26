"""Installed operation: in a fresh `python -I` process, with the plugin
reachable only through ayder's loader from a staged project copy, a failed
launch is cleaned up and a real open → eval → close succeeds."""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

HERE = Path(__file__).resolve().parent


def test_installed_copy_works_without_plugin_on_path(
        fixture_server, staged_project, tmp_path):
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    child_tmp = tmp_path / "child-tmp"
    child_tmp.mkdir()
    pidfile = tmp_path / "stub.pid"
    stub = tmp_path / "stub-chrome"
    stub.write_text(f"#!/bin/sh\necho $$ > '{pidfile}'\nexec sleep 30\n")
    os.chmod(stub, 0o755)
    env = os.environ.copy()
    env["TMPDIR"] = str(child_tmp)          # throwaway profiles land here
    env["AYDER_BROWSER_PROFILES_DIR"] = str(tmp_path / "profiles")
    env.pop("AYDER_BROWSER_EXECUTABLE", None)

    r = subprocess.run(
        [sys.executable, "-I", str(HERE / "_installed_child.py"),
         str(staged_project), str(empty_home), str(stub),
         fixture_server + "/page.html"],
        cwd=staged_project, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])

    assert out["global_dir"].startswith(str(empty_home))
    assert out["plugin_on_path"] == []

    failed = out["failed_open"]
    assert not failed["ok"]
    assert "No module named" not in failed["text"], failed["text"]
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)                     # the stub child was reaped
    assert out["after_failure"] == {
        "pending_reap": False, "cleanup_pending": False, "browser": False}

    assert out["open"]["ok"], out["open"]["text"]
    assert "t1" in out["open"]["text"] and "throwaway" in out["open"]["text"]
    assert out["eval"]["ok"] and out["eval"]["text"].endswith("\n2")
    assert out["close"]["ok"], out["close"]["text"]

    installed = str(staged_project / ".ayder" / "plugins" / "zendriver-tools")
    assert out["module_files"], "no plugin module was loaded"
    for name, f in out["module_files"].items():
        assert f and f.startswith(installed), (name, f)
    assert glob.glob(str(child_tmp / "ayder-zendriver-*")) == []
