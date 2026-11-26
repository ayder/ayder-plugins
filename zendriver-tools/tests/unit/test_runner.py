"""S7: deadline runner — lock wait counts, work cancelled at deadline,
cleanup ownership survives the caller's return (fake workers, no Chrome)."""
import threading
import time

import pytest

import zendriver_tools_state as state


@pytest.fixture(autouse=True)
def fresh_state():
    yield
    state.reset_for_test()


def test_queued_call_times_out_and_never_runs():
    ran = []

    async def slow(ctx):
        await state.asyncio.sleep(1.5)
        return "slow"

    async def fast(ctx):
        ran.append(True)
        return "fast"

    t = threading.Thread(target=lambda: state.run_call(slow, timeout_s=5))
    t.start()
    time.sleep(0.1)  # let slow take the lock
    t0 = time.monotonic()
    with pytest.raises(state.DeadlineExpired):
        state.run_call(fast, timeout_s=1)
    assert time.monotonic() - t0 < 1.5
    t.join()
    time.sleep(0.2)
    assert ran == []  # the expired call never ran, even after the lock freed


def test_running_work_cancelled_at_deadline():
    cancelled = []

    async def work(ctx):
        try:
            await state.asyncio.sleep(5)
        except state.asyncio.CancelledError:
            cancelled.append(True)
            raise

    t0 = time.monotonic()
    with pytest.raises(state.DeadlineExpired):
        state.run_call(work, timeout_s=1)
    assert time.monotonic() - t0 < 1.6
    time.sleep(0.1)
    assert cancelled == [True]


def test_cleanup_ownership_survives_caller_return():
    events = []

    async def failing_launch(ctx):
        ctx.launch_began = True
        events.append("launch")
        raise RuntimeError("start failed")

    def fake_worker(ctx, end):
        events.append("worker-start")
        time.sleep(0.5)
        events.append("worker-end")

    state.cleanup_worker = fake_worker
    t0 = time.monotonic()
    with pytest.raises(RuntimeError):
        state.run_call(failing_launch, timeout_s=2, startup=True)
    # the call returns only after the worker recorded its outcome
    assert events == ["launch", "worker-start", "worker-end"]
    assert time.monotonic() - t0 >= 0.5
    assert state.cleanup_pending is False
    # lock is free again
    assert state.run_call(_ok, timeout_s=2) == "ok"


async def _ok(ctx):
    return "ok"


def test_no_launch_means_no_cleanup():
    def fake_worker(ctx, end):
        raise AssertionError("cleanup ran for a call that never launched")

    async def fails_before_launch(ctx):
        raise RuntimeError("early failure")

    state.cleanup_worker = fake_worker
    with pytest.raises(RuntimeError):
        state.run_call(fails_before_launch, timeout_s=2, startup=True)


def test_never_dispatched_open_gets_no_grace():
    # stall the loop so the submission cannot dispatch
    stall = state.asyncio.run_coroutine_threadsafe(
        _stall(), state.ensure_loop())
    time.sleep(0.05)

    async def work(ctx):
        ctx.launch_began = True
        return "late"

    t0 = time.monotonic()
    with pytest.raises(state.DeadlineExpired):
        state.run_call(work, timeout_s=1, startup=True)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.6  # no +10 grace: the launch never began
    stall.result(5)


async def _stall():
    time.sleep(1.2)  # blocks the loop thread synchronously
