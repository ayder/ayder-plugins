"""Tool handlers — the only func_ref target. All mutable state lives in
zendriver_tools_state (never re-imported by ayder). MVP: one tab."""
import functools

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
    return ToolError("not implemented")


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
    return ToolError("not implemented")


def browser_close():
    try:
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    return ToolError("not implemented")
