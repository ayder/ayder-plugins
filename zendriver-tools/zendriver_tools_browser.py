"""Driver helpers: launch, tab setup, loader-correlated navigation, capture.

Every coroutine here runs on the private loop via state.run_call.

zendriver is imported inside the functions that use it, so ayder can load the
plugin's definitions without it (and without paying its import time at every
start); a missing zendriver surfaces from browser_open as ModuleNotFoundError.
"""
import asyncio
import tempfile
import time
from pathlib import Path

import zendriver_tools_chrome as chrome
import zendriver_tools_console as zconsole
import zendriver_tools_profiles as profiles
import zendriver_tools_state as state
import zendriver_tools_webmcp as zwebmcp


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


async def enable_capture(tab, *, discard):
    """Arm console/exception capture. Handlers are attached BEFORE enable so
    the replay is delivered deterministically (review Finding 1). discard=True
    (the browser_open path, which navigates next) drops the page being left;
    discard=False (the browser_console path) keeps the current page's stored
    entries so they are recovered."""
    from zendriver import cdp
    if discard:
        await tab.send(cdp.runtime.discard_console_entries())
    tab.add_handler(cdp.runtime.ConsoleAPICalled, _on_console)
    tab.add_handler(cdp.runtime.ExceptionThrown, _on_exception)
    await tab.send(cdp.runtime.enable())


async def disable_capture(tab):
    """Stop capture and clear the buffer (explicit or automatic off, D-3)."""
    from zendriver import cdp
    tab.remove_handlers(cdp.runtime.ConsoleAPICalled, _on_console)
    tab.remove_handlers(cdp.runtime.ExceptionThrown, _on_exception)
    await tab.send(cdp.runtime.disable())
    state.console_buffer.clear()


async def settle_replay(deadline):
    """Drain the capture handler tasks spawned by Runtime.enable's replay so a
    browser_console(capture=true) call returns the recovered entries in that
    same call. zendriver dispatches handlers as tasks (core/connection.py:1103,
    asyncio.create_task); this drains them without running any page JavaScript.
    Bounded by the call deadline."""
    import asyncio
    while True:
        await asyncio.sleep(0)
        pending = [t for t in asyncio.all_tasks()
                   if not t.done()
                   and getattr(t.get_coro(), "__name__", "")
                   in ("_on_console", "_on_exception")]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        if time.monotonic() >= deadline:
            return


async def setup_tab(tab, capture):
    """Lifecycle events always; capture only when requested. Both armed BEFORE
    the first navigation. Page/lifecycle are independent of capture (D-5)."""
    from zendriver import cdp
    await tab.send(cdp.page.enable())
    await tab.send(cdp.page.set_lifecycle_events_enabled(True))
    if capture:
        await enable_capture(tab, discard=True)


async def navigate_and_wait(tab, url, deadline):
    """Arm the lifecycle observer, navigate, and wait for the destination's
    main-frame load with its loader. Events arriving before the navigate
    response are buffered, then matched (review 3, finding 3)."""
    from zendriver import cdp
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


async def _on_tools_added(ev):
    for t in ev.tools:
        state.webmcp_tools[(str(t["frameId"]), t["name"])] = t


async def _on_tools_removed(ev):
    for t in ev.tools:
        state.webmcp_tools.pop((str(t.frame_id), t.name), None)


async def _on_tool_responded(ev):
    # Buffer from the moment the handler is attached: a fast tool can answer
    # before the invokeTool response is processed (P-4, AC-W7b).
    state.webmcp_responses[ev.invocation_id] = ev
    if state.webmcp_response_event is not None:
        state.webmcp_response_event.set()


def _clear_webmcp_frame(fid):
    for key in [k for k in state.webmcp_tools if k[0] == fid]:
        del state.webmcp_tools[key]


async def _on_frame_navigated(ev):
    if ev.frame.parent_id is None:
        state.webmcp_tools.clear()   # main frame navigated: a new document
    else:
        _clear_webmcp_frame(str(ev.frame.id_))


async def _on_frame_detached(ev):
    _clear_webmcp_frame(str(ev.frame_id))


async def setup_webmcp(tab):
    """Enable WebMCP once, before the first navigation, and attach the live
    registry + response-buffer handlers (spec rev 2 §5.1). Handlers precede
    enable so no event is missed."""
    from zendriver import cdp
    zwebmcp.register_parser()
    state.webmcp_response_event = asyncio.Event()
    tab.add_handler(zwebmcp.ToolsAdded, _on_tools_added)
    tab.add_handler(zwebmcp.ToolsRemoved, _on_tools_removed)
    tab.add_handler(zwebmcp.ToolResponded, _on_tool_responded)
    tab.add_handler(cdp.page.FrameNavigated, _on_frame_navigated)
    tab.add_handler(cdp.page.FrameDetached, _on_frame_detached)
    await tab.send(cdp.web_mcp.enable())


async def settle_webmcp(deadline):
    """Drain pending WebMCP handler tasks so a read sees every event delivered
    so far, deterministically and without a fixed sleep."""
    names = ("_on_tools_added", "_on_tools_removed", "_on_tool_responded",
             "_on_frame_navigated", "_on_frame_detached")
    while True:
        await asyncio.sleep(0)
        pending = [t for t in asyncio.all_tasks()
                   if not t.done()
                   and getattr(t.get_coro(), "__name__", "") in names]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        if time.monotonic() >= deadline:
            return


async def webmcp_available(tab):
    """Whether the current page has document.modelContext (checked at call
    time, not cached; spec rev 2 §5.3)."""
    return await tab.evaluate("typeof document.modelContext") == "object"


async def wait_webmcp_response(invocation_id, deadline, name):
    """Wait for the toolResponded with this invocationId. Checks the buffer
    first so a fast tool's response is never lost to the race between the
    invokeTool response and the event (P-4, AC-W7b). No fixed sleep."""
    import asyncio
    while True:
        if invocation_id in state.webmcp_responses:
            return state.webmcp_responses.pop(invocation_id)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise state.DeadlineExpired(
                f"WebMCP tool '{name}' did not respond before the deadline")
        ev = state.webmcp_response_event
        if ev is None:
            raise state.DeadlineExpired(
                f"WebMCP tool '{name}' did not respond before the deadline")
        ev.clear()
        if invocation_id in state.webmcp_responses:
            continue
        try:
            await asyncio.wait_for(ev.wait(), remaining)
        except asyncio.TimeoutError:
            raise state.DeadlineExpired(
                f"WebMCP tool '{name}' did not respond before the deadline")


def close_worker(b, handle, directory, throwaway, end):
    """One executor worker owns the WHOLE normal shutdown: it takes
    cleanup_mutex BEFORE stop() (which itself signals the child), runs
    stop() on the loop and awaits it, confirms the reap through the
    recorded handle, deletes only an owned throwaway dir, resets state.
    Runs in an executor worker, never on the daemon loop thread."""
    import shutil
    with state.cleanup_mutex:
        try:
            fut = asyncio.run_coroutine_threadsafe(b.stop(), state.loop)
            fut.result(timeout=max(0.0, end - time.monotonic()))
        except Exception:
            pass
        if handle is not None:
            try:
                if handle.poll() is None:
                    handle.terminate()
                    try:
                        handle.wait(timeout=5)
                    except Exception:
                        handle.kill()
                        handle.wait(timeout=2)
            except Exception:
                pass
        reaped = handle is None or handle.poll() is not None
        if throwaway and reaped and directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        state.browser = None
        state.handle = None
        state.profile_dir = None
        state.profile_kind = None
        state.headless_setting = None
        state.tab = None
        state.console_buffer.clear()
        state.console_auto = True
        state.console_capture = False
        state.webmcp_setting = None
        state.webmcp_tools.clear()
        state.webmcp_responses.clear()
        state.webmcp_response_event = None


def webmcp_flags(webmcp):
    """The single WebMCP feature flag for the launch (D28). True/omitted enables;
    False disables (zendriver merges it into its --disable-features switch)."""
    if webmcp is False:
        return ["--disable-features=WebMCP"]
    return ["--enable-features=WebMCP"]


def make_open_config(exe, directory, headless, webmcp):
    """The zd.Config open_work launches with; extracted so the launch flags are
    unit-testable without Chrome (AC-W13)."""
    import zendriver as zd
    return zd.Config(
        browser="chrome",
        user_data_dir=directory,
        headless=headless,
        browser_executable_path=str(exe),
        browser_args=webmcp_flags(webmcp),
    )


async def open_work(ctx, url, profile, headless, console=None, webmcp=None):
    if state.browser is not None:
        kind = state.profile_kind
        if profile is not None and kind != f"persistent:{profile}":
            raise ConfigMismatch(
                "a different profile is in use; call browser_close first")
        if headless is not None and headless != state.headless_setting:
            raise ConfigMismatch(
                "a different headless setting is in use; call browser_close first")
        if webmcp is not None and webmcp != state.webmcp_setting:
            raise ConfigMismatch(
                "a different webmcp setting is in use; call browser_close first")
        # Capture is runtime-mutable, never a ConfigMismatch (D25/D26). An
        # explicit value sticks; auto reclassifies the requested URL; an
        # omitted value in explicit mode keeps the current setting.
        if console is not None:
            new_capture = console
            state.console_auto = False
        elif state.console_auto:
            new_capture = zconsole.default_capture_for(url)
        else:
            new_capture = state.console_capture
        if new_capture != state.console_capture:
            if new_capture:
                await enable_capture(state.tab, discard=True)
            else:
                await disable_capture(state.tab)
        state.console_capture = new_capture
    else:
        if state.cleanup_pending or state.pending_reap:
            raise StillShuttingDown(
                "the previous browser is still shutting down; try again later")
        import zendriver as zd   # before the Chrome search: a missing driver
        exe = chrome.resolve_executable()  # must not read as a missing Chrome
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
        config = make_open_config(exe, directory, h, webmcp)
        state.webmcp_setting = True if webmcp is None else webmcp
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
        if console is not None:
            state.console_capture = console
            state.console_auto = False
        else:
            state.console_capture = zconsole.default_capture_for(url)
            state.console_auto = True
        state.console_buffer.clear()
        tab = None
        while tab is None:
            tab = b.main_tab
            if tab is None:
                if time.monotonic() >= ctx.deadline:
                    raise state.DeadlineExpired("no tab appeared")
                await asyncio.sleep(0.05)
        state.tab = tab
        await setup_tab(tab, state.console_capture)
        if state.webmcp_setting:
            await setup_webmcp(tab)
    await navigate_and_wait(state.tab, url, ctx.deadline)
    final_url = await state.tab.evaluate("location.href")
    title = await state.tab.evaluate("document.title")
    return final_url, title, state.profile_kind
