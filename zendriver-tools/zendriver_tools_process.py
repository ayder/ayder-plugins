"""Cleanup of a failed launch: signal only the recorded child, through the
original handle; keep ownership on an uncertain reap and block replacement.
Runs in an executor worker under cleanup_mutex (single owner)."""
import shutil
import subprocess
import time

import zendriver_tools_state as state


def cleanup_launch(ctx, end):
    with state.cleanup_mutex:
        h = ctx.handle
        if h is None and ctx.browser is not None:
            h = getattr(ctx.browser, "_process", None)
        try:
            if h is not None and h.poll() is None:
                h.terminate()
                try:
                    h.wait(timeout=max(0.0, min(5.0, end - time.monotonic())))
                except subprocess.TimeoutExpired:
                    h.kill()
                    try:
                        h.wait(timeout=max(0.0, min(2.0, end - time.monotonic())))
                    except subprocess.TimeoutExpired:
                        pass
        except Exception:
            pass
        reaped = h is None or h.poll() is not None
        if reaped:
            if ctx.throwaway and ctx.profile_dir is not None:
                shutil.rmtree(ctx.profile_dir, ignore_errors=True)
        else:
            # Uncertain reap: keep the handle and the directory, and block
            # every new launch until the process is restarted (MVP; the
            # automatic recovery path is backlog 3).
            state.pending_reap = True
            state.handle = h
