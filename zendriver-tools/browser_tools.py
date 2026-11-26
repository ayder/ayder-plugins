"""Tool handlers — the only func_ref target. All mutable state lives in
zendriver_tools_state (never re-imported by ayder). MVP: one tab.

Every plugin-local import is at module level: ayder's loader puts the plugin
folder on sys.path only while the plugin loads, so a sibling imported first
inside a tool function cannot be found at call time. zendriver itself is an
installed package and stays lazy (imported inside zendriver_tools_browser's
functions), so loading the definitions does not import it."""
import functools
import time

from ayder_cli.core.result import ToolError, ToolSuccess

import zendriver_tools_browser as zb
import zendriver_tools_chrome as chrome
import zendriver_tools_process as process
import zendriver_tools_profiles as profiles
import zendriver_tools_state as state
import zendriver_tools_validation as v
from zendriver_tools_format import format_eval, format_read, untrusted_line

MISSING_DRIVER = (
    "zendriver is not installed in ayder's Python environment. Reinstall the "
    "plugin with its dependencies: ayder install-plugin <source> --force --yes")


def _err(exc):
    return ToolError(str(exc), "validation")


def _missing_driver(exc):
    return (isinstance(exc, ModuleNotFoundError)
            and (exc.name or "").split(".")[0] == "zendriver")


def _map_error(exc):
    if _missing_driver(exc):
        return ToolError(MISSING_DRIVER, "execution")
    if isinstance(exc, (v.ValidationError, profiles.ProfileError)):
        return ToolError(str(exc), "validation")
    if isinstance(exc, state.DeadlineExpired):
        return ToolError(f"browser call exceeded its deadline: {exc}", "execution")
    if isinstance(exc, (chrome.ChromeError, zb.NavigationError,
                        zb.StillShuttingDown, zb.ConfigMismatch)):
        return ToolError(str(exc), "execution")
    return ToolError(f"browser error: {exc}", "execution")


def browser_open(url, profile=None, headless=None, timeout_seconds=30):
    try:
        v.check_url(url)
        v.check_profile(profile)
        v.check_timeout(timeout_seconds)
        if headless is not None:
            v.check_bool(headless, "headless")
    except v.ValidationError as e:
        return _err(e)
    try:
        final_url, title, kind = state.run_call(
            functools.partial(zb.open_work, url=url, profile=profile,
                              headless=headless),
            timeout_s=timeout_seconds, startup=True,
            cleanup=process.cleanup_launch)
    except Exception as e:
        return _map_error(e)
    return ToolSuccess(
        f"{untrusted_line(final_url)}\nt1 | {final_url} | {title} | {kind}")


def browser_read(selector=None, max_chars=20000, timeout_seconds=30):
    try:
        v.check_timeout(timeout_seconds)
        v.check_max_chars(max_chars)
        if selector is not None:
            v.require_str(selector, "selector")
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    import json

    async def work(ctx):
        import asyncio
        # Fetch the URL first: no driver call may run after the retry loop,
        # and the URL does not change during a read.
        url = await state.tab.evaluate("location.href")
        if selector is None:
            text = await state.tab.evaluate(
                "document.body ? document.body.innerText : ''")
        else:
            expr = ("(() => { const el = document.querySelector("
                    + json.dumps(selector) + "); return el ? el.innerText : null; })()")
            # Retry only while the element is MISSING; an existing element
            # returns its text at once, even when empty (spec: lookups double
            # as waits for an element to appear).
            while True:
                text = await state.tab.evaluate(expr)
                if text is not None:
                    break
                remaining = ctx.deadline - time.monotonic()
                if remaining <= 0:
                    raise state.DeadlineExpired(
                        f"selector {selector!r} not found before the deadline")
                await asyncio.sleep(min(0.1, remaining))
        return text, url

    try:
        text, url = state.run_call(work, timeout_s=timeout_seconds)
    except Exception as e:
        return _map_error(e)
    return ToolSuccess(format_read(url, text, max_chars))


def browser_click(selector=None, timeout_seconds=30):
    try:
        v.require_str(selector, "selector")
        v.check_timeout(timeout_seconds)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    import json

    async def work(ctx):
        import asyncio
        expr = ("(() => { for (const el of document.querySelectorAll("
                + json.dumps(selector) + ")) {"
                " if (el.getClientRects().length > 0) {"
                " el.scrollIntoView({block: 'center'}); el.click(); return true; } }"
                " return false; })()")
        while True:
            if ctx.deadline - time.monotonic() <= 0:
                raise state.DeadlineExpired(
                    f"selector {selector!r} not clickable before the deadline")
            if await state.tab.evaluate(expr):
                break
            await asyncio.sleep(0.1)
        url = await state.tab.evaluate("location.href")
        title = await state.tab.evaluate("document.title")
        return url, title

    try:
        url, title = state.run_call(work, timeout_s=timeout_seconds)
    except Exception as e:
        return _map_error(e)
    return ToolSuccess(f"{untrusted_line(url)}\n{url} | {title}")


def browser_type(selector=None, value=None, timeout_seconds=30):
    try:
        v.require_str(selector, "selector")
        if not isinstance(value, str):
            raise v.ValidationError("value is required and must be a string")
        v.check_timeout(timeout_seconds)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    import json
    from zendriver import cdp

    sel = json.dumps(selector)
    val = json.dumps(value)
    # Readiness (spec rev5): the first match must be a text field with a
    # positive rendered box, editable, and able to take focus. Returns the
    # blocking reason, or null once ready — focus taken and the old value
    # selected via el.select() so Backspace replaces it (setSelectionRange
    # throws on type=email/number, which would append instead of replace). A
    # zero-sized control can still take focus, so the box check comes first.
    ready = (
        "(() => { const el = document.querySelector(" + sel + ");"
        " if (!el) return 'not found';"
        " const tag = el.tagName;"
        " const types = ['text','search','tel','url','password','email','number'];"
        " const isText = tag === 'TEXTAREA' || (tag === 'INPUT' &&"
        "   types.indexOf((el.type || '').toLowerCase()) !== -1);"
        " if (!isText) return 'not a text field';"
        " const r = el.getBoundingClientRect();"
        " if (!(r.width > 0 && r.height > 0)) return 'hidden';"
        " if (el.disabled || el.readOnly) return 'not editable';"
        " el.focus();"
        " if (document.activeElement !== el) return 'not focused';"
        " try { el.select(); } catch (e) {}"
        " return null; })()")
    focused = ("(() => { const el = document.querySelector(" + sel + ");"
               " return !!el && document.activeElement === el; })()")
    # Post-check: compare the field's value in-page and return only whether it
    # matches and the length present — never either value.
    post = ("(() => { const el = document.querySelector(" + sel + ");"
            " if (!el || typeof el.value !== 'string')"
            "   return {match: false, len: -1};"
            " return {match: el.value === " + val + ", len: el.value.length}; })()")

    last_reason = ["not found"]

    async def work(ctx):
        import asyncio
        while True:
            if ctx.deadline - time.monotonic() <= 0:
                raise state.DeadlineExpired("not ready before the deadline")
            reason = await state.tab.evaluate(ready)
            if reason is None:
                break
            last_reason[0] = reason
            await asyncio.sleep(
                min(0.1, max(0.0, ctx.deadline - time.monotonic())))
        for kind in ("keyDown", "keyUp"):
            await state.tab.send(cdp.input_.dispatch_key_event(
                type_=kind, key="Backspace", code="Backspace",
                windows_virtual_key_code=8, native_virtual_key_code=8))
        # A Backspace/keydown handler may have moved focus; stop without
        # replaying the edit so the element that took focus is not typed into.
        if not await state.tab.evaluate(focused):
            return "focus_lost", 0
        if value:
            await state.tab.send(cdp.input_.insert_text(value))
        result = await state.tab.evaluate(post)
        if result.get("match"):
            return "ok", result.get("len", 0)
        return "mismatch", result.get("len", 0)

    try:
        outcome, length = state.run_call(work, timeout_s=timeout_seconds)
    except state.DeadlineExpired:
        return ToolError(
            f"browser call exceeded its deadline: selector {selector!r} "
            f"not ready before the deadline: {last_reason[0]}", "execution")
    except Exception as e:
        return _map_error(e)
    if outcome == "focus_lost":
        return ToolError(
            "Focus left the field during the edit; input was not sent.",
            "execution")
    if outcome == "mismatch":
        return ToolError(
            f"The field did not retain the requested text "
            f"({length} characters present).", "execution")
    return ToolSuccess(f"{selector} | {length} characters typed")


def browser_eval(script=None, max_chars=20000, timeout_seconds=30):
    try:
        v.require_str(script, "script")
        v.check_timeout(timeout_seconds)
        v.check_max_chars(max_chars)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    from zendriver.core.connection import ProtocolException

    wrapped = ("(async () => { const v = await (" + script + ");"
               " const s = JSON.stringify(v);"
               " if (s === undefined) throw new Error('result is not JSON-serialisable');"
               " return s; })()")

    async def work(ctx):
        return await state.tab.evaluate(wrapped, await_promise=True)

    try:
        json_text = state.run_call(work, timeout_s=timeout_seconds)
        url = state.run_call(_current_url, timeout_s=10)
    except ProtocolException as e:
        detail = e.args[0] if e.args else None
        msg = getattr(detail, "text", None) or str(e)
        exc_obj = getattr(detail, "exception", None)
        if exc_obj is not None and getattr(exc_obj, "description", None):
            msg = exc_obj.description
        return ToolError(f"eval failed: {msg}", "execution")
    except Exception as e:
        return _map_error(e)
    return ToolSuccess(format_eval(url, json_text, max_chars))


async def _current_url(ctx):
    return await state.tab.evaluate("location.href")


def browser_console(clear=True):
    try:
        v.check_bool(clear, "clear")
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)

    async def work(ctx):
        entries = list(state.console_buffer)
        if clear:
            state.console_buffer.clear()
        url = await state.tab.evaluate("location.href")
        return entries, url

    try:
        entries, url = state.run_call(work, timeout_s=30)
    except Exception as e:
        return _map_error(e)
    lines = [f"[{level}] {text}" for level, text in entries]
    body = ("\n" + "\n".join(lines)) if lines else ""
    return ToolSuccess(untrusted_line(url) + body)


def browser_close():
    try:
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    import asyncio

    async def work(ctx):
        b = state.browser
        handle = state.handle
        directory = state.profile_dir
        throwaway = state.profile_kind == "throwaway"
        await asyncio.get_running_loop().run_in_executor(
            None, zb.close_worker, b, handle, directory, throwaway, ctx.deadline)
        return True

    try:
        state.run_call(work, timeout_s=30)
    except Exception as e:
        return _map_error(e)
    return ToolSuccess("browser closed")
