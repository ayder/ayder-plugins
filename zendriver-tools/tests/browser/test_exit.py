"""S19 / AC-18 exit part (reduced): normal interpreter exit ends Chrome and
removes the throwaway dir. Exact marker timings are backlog 3."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parents[1]


def test_normal_exit_ends_child_and_removes_dir(fixture_server, tmp_path):
    env = os.environ.copy()
    env["AYDER_BROWSER_PROFILES_DIR"] = str(tmp_path / "profiles")
    env["PYTHONPATH"] = str(PLUGIN_ROOT)
    child = subprocess.Popen(
        [sys.executable, str(HERE / "_exit_child.py"),
         fixture_server + "/page.html"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        record = json.loads(child.stdout.readline())
        assert "pid" in record, record
        pid, profile = record["pid"], Path(record["profile"])
        os.kill(pid, 0)                  # Chrome alive before exit
        assert profile.exists()
        child.stdin.write("\n")          # ack: allow normal exit
        child.stdin.flush()
        assert child.wait(timeout=30) == 0
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)              # child gone after exit
        assert not profile.exists()      # throwaway removed
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
