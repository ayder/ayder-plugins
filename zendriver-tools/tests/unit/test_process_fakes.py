"""S18: fake-handle ownership — own live child only, skip exited, block on
uncertain reap (Evidence 2)."""
import subprocess
import time

import pytest

import browser_tools as bt
import zendriver_tools_process as proc
import zendriver_tools_state as state
from ayder_cli.core.result import ToolError


class FakeHandle:
    def __init__(self, exits_on_term=False, never_exits=False):
        self.signals = []
        self._exited = False
        self._exits_on_term = exits_on_term
        self._never = never_exits

    def poll(self):
        return 0 if self._exited else None

    def terminate(self):
        self.signals.append("TERM")
        if self._exits_on_term:
            self._exited = True

    def kill(self):
        self.signals.append("KILL")
        if not self._never:
            self._exited = True

    def wait(self, timeout=None):
        if self._exited:
            return 0
        raise subprocess.TimeoutExpired("x", timeout)


@pytest.fixture(autouse=True)
def fresh():
    yield
    state.pending_reap = False
    state.handle = None


def _ctx(tmp_path, handle):
    ctx = state.CallCtx(time.monotonic() + 10)
    ctx.launch_began = True
    ctx.handle = handle
    ctx.throwaway = True
    ctx.profile_dir = tmp_path / "throwaway"
    ctx.profile_dir.mkdir()
    return ctx


def test_exited_handle_receives_no_signal(tmp_path):
    h = FakeHandle()
    h._exited = True
    ctx = _ctx(tmp_path, h)
    proc.cleanup_launch(ctx, time.monotonic() + 10)
    assert h.signals == []
    assert not ctx.profile_dir.exists()  # reaped -> owned dir deleted
    assert state.pending_reap is False


def test_live_child_terminated_and_dir_deleted(tmp_path):
    h = FakeHandle(exits_on_term=True)
    ctx = _ctx(tmp_path, h)
    proc.cleanup_launch(ctx, time.monotonic() + 10)
    assert h.signals == ["TERM"]
    assert not ctx.profile_dir.exists()
    assert state.pending_reap is False


def test_uncertain_reap_blocks_replacement(tmp_path):
    h = FakeHandle(never_exits=True)
    ctx = _ctx(tmp_path, h)
    proc.cleanup_launch(ctx, time.monotonic() + 10)
    assert h.signals == ["TERM", "KILL"]
    assert state.pending_reap is True
    assert ctx.profile_dir.exists()      # kept
    assert state.handle is h             # ownership kept
    r = bt.browser_open(url="about:blank")
    assert isinstance(r, ToolError)
    assert "shutting down" in str(r)
    assert state.browser is None         # no replacement started
