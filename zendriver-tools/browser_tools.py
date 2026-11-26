"""Tool handlers — the only func_ref target. All mutable state lives in
zendriver_tools_state (never re-imported by ayder). MVP: one tab."""
import functools
import time

from ayder_cli.core.result import ToolError, ToolSuccess

import zendriver_tools_state as state
import zendriver_tools_validation as v
from zendriver_tools_format import untrusted_line


def _err(exc):
    return ToolError(str(exc), "validation")


def _map_error(exc):
    import zendriver_tools_browser as zb
    import zendriver_tools_chrome as chrome
    import zendriver_tools_profiles as profiles
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
    import zendriver_tools_browser as zb
    try:
        final_url, title, kind = state.run_call(
            functools.partial(zb.open_work, url=url, profile=profile,
                              headless=headless),
            timeout_s=timeout_seconds, startup=True)
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
    from zendriver_tools_format import format_read

    async def work(ctx):
        import asyncio
        if selector is None:
            expr = "document.body ? document.body.innerText : ''"
        else:
            expr = ("(() => { const el = document.querySelector("
                    + json.dumps(selector) + "); return el ? el.innerText : null; })()")
        while True:
            text = await state.tab.evaluate(expr)
            if text or selector is None:
                break  # whole-page reads return immediately, even if empty
            if ctx.deadline - time.monotonic() <= 0:
                if text is None:
                    raise state.DeadlineExpired(
                        f"selector {selector!r} not found before the deadline")
                break  # element exists but is still empty at the deadline
            await asyncio.sleep(0.1)
        url = await state.tab.evaluate("location.href")
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
    return ToolError("not implemented")


def browser_type(selector=None, value=None, timeout_seconds=30):
    try:
        v.require_str(selector, "selector")
        if not isinstance(value, str):
            raise v.ValidationError("value is required and must be a string")
        v.check_timeout(timeout_seconds)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    return ToolError("not implemented")


def browser_eval(script=None, max_chars=20000, timeout_seconds=30):
    try:
        v.require_str(script, "script")
        v.check_timeout(timeout_seconds)
        v.check_max_chars(max_chars)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    return ToolError("not implemented")


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
    return ToolError("not implemented")
