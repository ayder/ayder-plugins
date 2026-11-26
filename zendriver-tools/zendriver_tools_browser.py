"""Driver helpers: launch, tab setup, loader-correlated navigation, capture.

Every coroutine here runs on the private loop via state.run_call.
"""
import asyncio
import tempfile
import time
from pathlib import Path

import zendriver as zd
from zendriver import cdp

import zendriver_tools_chrome as chrome
import zendriver_tools_profiles as profiles
import zendriver_tools_state as state


class NavigationError(Exception):
    pass


class StillShuttingDown(Exception):
    pass


class ConfigMismatch(Exception):
    pass


async def _on_console(event):
    parts = []
    for arg in event.args or []:
        val = getattr(arg, "value", None)
        parts.append(str(val if val is not None else getattr(arg, "description", "")))
    state.console_buffer.append((str(event.type_), " ".join(parts)))


async def _on_exception(event):
    d = event.exception_details
    text = d.text or "uncaught exception"
    exc = getattr(d, "exception", None)
    if exc is not None and getattr(exc, "description", None):
        text = f"{text}: {exc.description}"
    state.console_buffer.append(("exception", text))


async def setup_tab(tab):
    """Capture and lifecycle events, enabled BEFORE the first navigation."""
    await tab.send(cdp.runtime.enable())
    await tab.send(cdp.page.enable())
    await tab.send(cdp.page.set_lifecycle_events_enabled(True))
    tab.add_handler(cdp.runtime.ConsoleAPICalled, _on_console)
    tab.add_handler(cdp.runtime.ExceptionThrown, _on_exception)


async def navigate_and_wait(tab, url, deadline):
    """Arm the lifecycle observer, navigate, and wait for the destination's
    main-frame load with its loader. Events arriving before the navigate
    response are buffered, then matched (review 3, finding 3)."""
    events = []
    signaled = asyncio.Event()

    async def on_lifecycle(ev):
        events.append(ev)
        signaled.set()

    tab.add_handler(cdp.page.LifecycleEvent, on_lifecycle)
    try:
        frame_id, loader_id, error_text, _is_download = await tab.send(
            cdp.page.navigate(url))
        if error_text:
            raise NavigationError(f"navigation failed: {error_text}")
        pos = 0
        while True:
            while pos < len(events):
                ev = events[pos]
                pos += 1
                if (ev.name == "load" and ev.frame_id == frame_id
                        and (loader_id is None or ev.loader_id == loader_id)):
                    return
            signaled.clear()
            if pos < len(events):
                continue  # an event arrived while clearing
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise state.DeadlineExpired("page did not load before the deadline")
            try:
                await asyncio.wait_for(signaled.wait(), remaining)
            except asyncio.TimeoutError:
                raise state.DeadlineExpired("page did not load before the deadline")
    finally:
        tab.remove_handlers(cdp.page.LifecycleEvent, on_lifecycle)


async def open_work(ctx, url, profile, headless):
    if state.browser is not None:
        kind = state.profile_kind
        if profile is not None and kind != f"persistent:{profile}":
            raise ConfigMismatch(
                "a different profile is in use; call browser_close first")
        if headless is not None and headless != state.headless_setting:
            raise ConfigMismatch(
                "a different headless setting is in use; call browser_close first")
    else:
        if state.cleanup_pending or state.pending_reap:
            raise StillShuttingDown(
                "the previous browser is still shutting down; try again later")
        exe = chrome.resolve_executable()
        if profile is not None:
            directory = profiles.prepare_profile(profile)
            profiles.check_profile_lock(directory)
            kind = f"persistent:{profile}"
            throwaway = False
        else:
            directory = Path(tempfile.mkdtemp(prefix="ayder-zendriver-"))
            kind = "throwaway"
            throwaway = True
        h = True if headless is None else headless
        ctx.profile_dir = directory
        ctx.throwaway = throwaway
        config = zd.Config(
            browser="chrome",
            user_data_dir=directory,
            headless=h,
            browser_executable_path=str(exe),
        )
        b = zd.Browser(config)   # retained BEFORE awaiting start (finding 2)
        ctx.browser = b
        ctx.launch_began = True
        await b.start()
        ctx.handle = b._process
        state.browser = b
        state.handle = b._process
        state.profile_dir = directory
        state.profile_kind = kind
        state.headless_setting = h
        state.console_buffer.clear()
        tab = None
        while tab is None:
            tab = b.main_tab
            if tab is None:
                if time.monotonic() >= ctx.deadline:
                    raise state.DeadlineExpired("no tab appeared")
                await asyncio.sleep(0.05)
        state.tab = tab
        await setup_tab(tab)
    await navigate_and_wait(state.tab, url, ctx.deadline)
    final_url = await state.tab.evaluate("location.href")
    title = await state.tab.evaluate("document.title")
    return final_url, title, state.profile_kind
