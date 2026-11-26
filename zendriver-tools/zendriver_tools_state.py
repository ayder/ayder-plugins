"""Shared mutable state for zendriver-tools.

ayder re-imports browser_tools for every func_ref, so every handler holds
its own copy of that module; this module is never a func_ref target and is
imported once, so all handlers and registries share it (D11).

The private event loop runs on a daemon thread; every zendriver call runs
on it. One asyncio lock serialises tool calls; one threading mutex
(cleanup_mutex) serialises cleanup sections, whose single owner is its
holder. Cleanup ownership survives a timed-out caller: the lock is
released by the cleanup worker's outcome, never by the unwinding call.
"""
import asyncio
import concurrent.futures
import threading
import time
from collections import deque

browser = None          # the zendriver Browser, once started
handle = None           # recorded Popen handle of the Chrome child we launched
profile_dir = None      # active profile directory (Path)
profile_kind = None     # "throwaway" | "persistent:<name>"
headless_setting = None
tab = None              # the single current tab (MVP)
console_buffer = deque(maxlen=500)

loop = None
_loop_thread = None
_lock = None            # asyncio.Lock, created on the private loop
cleanup_mutex = threading.Lock()
cleanup_pending = False  # a cleanup worker is submitted, outcome not recorded
pending_reap = False     # a child may still be alive; blocks every new launch
cleanup_worker = None    # injectable for tests; default: process.cleanup_launch


class DeadlineExpired(Exception):
    pass


class CallCtx:
    """Per-call record. Cleanup reads ONLY this record, so a queued or
    reused-browser call can never clean up an existing browser."""

    def __init__(self, deadline):
        self.deadline = deadline
        self.launch_began = False
        self.browser = None
        self.handle = None
        self.profile_dir = None
        self.throwaway = False


def ensure_loop():
    global loop, _loop_thread, _lock
    if loop is not None and _loop_thread is not None and _loop_thread.is_alive():
        return loop
    loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(
        target=loop.run_forever, daemon=True, name="zendriver-tools-loop")
    _loop_thread.start()

    async def _init():
        global _lock
        _lock = asyncio.Lock()

    asyncio.run_coroutine_threadsafe(_init(), loop).result(5)
    return loop


def run_call(work, *, timeout_s, startup=False):
    """Run one tool's driver work on the private loop under the lock.
    The deadline is absolute from tool entry; the extra 10 s grace applies
    only to a call that actually began a launch."""
    deadline = time.monotonic() + timeout_s
    if time.monotonic() >= deadline:
        raise DeadlineExpired("deadline expired before dispatch")
    ctx = CallCtx(deadline)
    lp = ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(
        _guarded(work, ctx, deadline + 10.0, startup), lp)
    try:
        return fut.result(timeout=max(0.0, deadline - time.monotonic()))
    except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError):
        if startup and ctx.launch_began:
            try:
                return fut.result(
                    timeout=max(0.0, deadline + 10.0 - time.monotonic()))
            except (concurrent.futures.TimeoutError,
                    concurrent.futures.CancelledError):
                pass
            except Exception as exc:
                raise exc
        # Never cancel fut: the loop-side guards invalidate late work, and
        # state-owned cleanup must finish regardless of this caller.
        raise DeadlineExpired("call exceeded its deadline")


async def _guarded(work, ctx, cleanup_end, startup):
    remaining = ctx.deadline - time.monotonic()
    if remaining <= 0:
        raise DeadlineExpired("expired before dispatch")
    try:
        await asyncio.wait_for(_lock.acquire(), remaining)
    except asyncio.TimeoutError:
        raise DeadlineExpired("still waiting for the lock at the deadline")
    ownership_transferred = False
    try:
        remaining = ctx.deadline - time.monotonic()
        if remaining <= 0:
            raise DeadlineExpired("expired while queued")
        try:
            return await asyncio.wait_for(work(ctx), remaining)
        except BaseException:
            if startup and ctx.launch_began:
                global cleanup_pending
                cleanup_pending = True
                worker = cleanup_worker
                if worker is None:
                    try:
                        from zendriver_tools_process import cleanup_launch as worker
                    except ImportError:
                        worker = None
                if worker is None:
                    # No worker available: block replacement conservatively.
                    global pending_reap
                    pending_reap = True
                    cleanup_pending = False
                else:
                    exec_fut = loop.run_in_executor(None, worker, ctx, cleanup_end)
                    exec_fut.add_done_callback(_finish_cleanup)
                    ownership_transferred = True
                    try:
                        await asyncio.shield(exec_fut)
                    except BaseException:
                        pass  # the worker records its own outcome
            raise
    finally:
        if not ownership_transferred:
            _lock.release()


def _finish_cleanup(exec_fut):
    """Runs on the loop when the worker has recorded its outcome."""
    global cleanup_pending
    cleanup_pending = False
    _lock.release()


def reset_for_test():
    """Teardown helper: drain/stop/join/close the loop, then clear state."""
    global loop, _loop_thread, _lock, browser, handle, profile_dir
    global profile_kind, headless_setting, tab, cleanup_pending, pending_reap
    global cleanup_worker
    if loop is not None and _loop_thread is not None:
        async def _drain():
            tasks = [t for t in asyncio.all_tasks()
                     if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            asyncio.run_coroutine_threadsafe(_drain(), loop).result(5)
            loop.call_soon_threadsafe(loop.stop)
            _loop_thread.join(5)
            loop.close()
        except Exception:
            pass
    loop = None
    _loop_thread = None
    _lock = None
    browser = None
    handle = None
    profile_dir = None
    profile_kind = None
    headless_setting = None
    tab = None
    console_buffer.clear()
    cleanup_pending = False
    pending_reap = False
    cleanup_worker = None
