"""Tool handlers — the only func_ref target. All mutable state lives in
zendriver_tools_state (never re-imported by ayder). MVP: one tab.

Every plugin-local import is at module level: ayder's loader puts the plugin
folder on sys.path only while the plugin loads, so a sibling imported first
inside a tool function cannot be found at call time. zendriver itself is an
installed package and stays lazy (imported inside zendriver_tools_browser's
functions), so loading the definitions does not import it."""
import functools
import json
import time

from ayder_cli.core.result import ToolError, ToolSuccess

import zendriver_tools_browser as zb
import zendriver_tools_chrome as chrome
import zendriver_tools_process as process
import zendriver_tools_profiles as profiles
import zendriver_tools_state as state
import zendriver_tools_validation as v
import zendriver_tools_webmcp as zwebmcp
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


def browser_open(url, profile=None, headless=None, console=None, webmcp=None,
                 timeout_seconds=30):
    try:
        v.check_url(url)
        v.check_profile(profile)
        v.check_timeout(timeout_seconds)
        if headless is not None:
            v.check_bool(headless, "headless")
        if console is not None:
            v.check_bool(console, "console")
        if webmcp is not None:
            v.check_bool(webmcp, "webmcp")
    except v.ValidationError as e:
        return _err(e)
    try:
        final_url, title, kind = state.run_call(
            functools.partial(zb.open_work, url=url, profile=profile,
                              headless=headless, console=console, webmcp=webmcp),
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


def browser_console(clear=True, capture=None):
    try:
        v.check_bool(clear, "clear")
        if capture is not None:
            v.check_bool(capture, "capture")
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)

    async def work(ctx):
        if capture is not None:
            state.console_auto = False
            if capture != state.console_capture:
                if capture:
                    # No navigation: keep the current page's stored entries and
                    # recover them in this same call (review Finding 3).
                    await zb.enable_capture(state.tab, discard=False)
                    await zb.settle_replay(ctx.deadline)
                else:
                    await zb.disable_capture(state.tab)
                state.console_capture = capture
        entries = list(state.console_buffer)
        if clear:
            state.console_buffer.clear()
        url = await state.tab.evaluate("location.href")
        return entries, url, state.console_capture

    try:
        entries, url, capture_state = state.run_call(work, timeout_s=30)
    except Exception as e:
        return _map_error(e)
    lines = [f"[{level}] {text}" for level, text in entries]
    body = ("\n" + "\n".join(lines)) if lines else ""
    if not capture_state:
        body = ("\nConsole capture is off; enable it with "
                "browser_console(capture=true) or browser_open(console=true).")
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


WEBMCP_OFF = ("WebMCP is off for this browser; call browser_close, then "
              "browser_open(..., webmcp=true).")


def _webmcp_tool_json(t, fid, frame, origin):
    obj = {"name": t["name"], "description": t.get("description", ""),
           "inputSchema": t.get("inputSchema") or {},
           "declarative": t.get("backendNodeId") is not None,
           "frameId": fid, "frame": frame, "origin": origin}
    ann = t.get("annotations") or {}
    mapped = {}
    if ann.get("readOnly") is not None:
        mapped["readOnlyHint"] = ann["readOnly"]
    if ann.get("untrustedContent") is not None:
        mapped["untrustedContentHint"] = ann["untrustedContent"]
    if ann.get("consequential") is not None:
        mapped["consequentialHint"] = ann["consequential"]
    if ann.get("autosubmit") is not None:
        mapped["autosubmit"] = ann["autosubmit"]
    if mapped:
        obj["annotations"] = mapped
    return obj


def browser_webmcp_list(max_chars=20000, timeout_seconds=30):
    try:
        v.check_max_chars(max_chars)
        v.check_timeout(timeout_seconds)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    if state.webmcp_setting is False:
        return ToolError(WEBMCP_OFF, "execution")

    async def work(ctx):
        from zendriver import cdp
        if not await zb.webmcp_available(state.tab):
            info = await state.tab.send(cdp.browser.get_version())
            product = info[1]
            ver = product.split("/", 1)[-1] if "/" in product else product
            return ("unavailable", ver)
        await zb.settle_webmcp(ctx.deadline)
        tree = await state.tab.send(cdp.page.get_frame_tree())
        frames = {}

        def walk(node):
            f = node.frame
            frames[str(f.id_)] = (
                "main" if f.parent_id is None else "child", f.security_origin)
            for c in node.child_frames or []:
                walk(c)
        walk(tree)
        tools = []
        for (fid, name), t in state.webmcp_tools.items():
            frame, origin = frames.get(fid, ("child", ""))
            tools.append(_webmcp_tool_json(t, fid, frame, origin))
        tools.sort(key=lambda x: (x["name"], x["frameId"]))
        url = await state.tab.evaluate("location.href")
        return ("ok", url, tools)

    try:
        res = state.run_call(work, timeout_s=timeout_seconds)
    except Exception as e:
        return _map_error(e)
    if res[0] == "unavailable":
        return ToolError(
            f"WebMCP is not available on this page (Chrome {res[1]}).",
            "execution")
    _, url, tools = res
    if not tools:
        return ToolSuccess(untrusted_line(url)
                           + "\nNo WebMCP tools are registered on this page.")
    return ToolSuccess(format_eval(
        url, json.dumps(tools, ensure_ascii=False), max_chars))


def _webmcp_error_message(ev):
    exc = ev.exception
    if exc is not None and getattr(exc, "description", None):
        return exc.description.split("\n")[0]
    if ev.error_text:
        return ev.error_text
    return "no error message"


def browser_webmcp_call(name, arguments=None, frame_id=None, max_chars=20000,
                        timeout_seconds=30):
    if arguments is None:
        arguments = {}
    try:
        v.require_str(name, "name")
        if not isinstance(arguments, dict):
            raise v.ValidationError("arguments must be a JSON object")
        if frame_id is not None and not isinstance(frame_id, str):
            raise v.ValidationError("frame_id must be a string")
        v.check_max_chars(max_chars)
        v.check_timeout(timeout_seconds)
        v.require_browser(state.browser is not None)
    except v.ValidationError as e:
        return _err(e)
    if state.webmcp_setting is False:
        return ToolError(WEBMCP_OFF, "execution")

    async def work(ctx):
        from zendriver import cdp
        if not await zb.webmcp_available(state.tab):
            info = await state.tab.send(cdp.browser.get_version())
            product = info[1]
            ver = product.split("/", 1)[-1] if "/" in product else product
            return ("unavailable", ver)
        await zb.settle_webmcp(ctx.deadline)
        tree = await state.tab.send(cdp.page.get_frame_tree())
        main_fid = str(tree.frame.id_)
        origins = {}

        def walk(node):
            origins[str(node.frame.id_)] = node.frame.security_origin
            for c in node.child_frames or []:
                walk(c)
        walk(tree)
        matches = [(fid, t) for (fid, n), t in state.webmcp_tools.items()
                   if n == name]
        if frame_id is not None:
            matches = [(fid, t) for fid, t in matches if fid == frame_id]
            if not matches:
                return ("notfound", None)
            fid = matches[0][0]
        else:
            main_matches = [fid for fid, _ in matches if fid == main_fid]
            if main_matches:
                fid = main_matches[0]
            elif len(matches) == 1:
                fid = matches[0][0]
            elif len(matches) > 1:
                listing = ", ".join(f"{f} ({origins.get(f, '')})"
                                    for f, _ in matches)
                return ("ambiguous", listing)
            else:
                return ("notfound", None)
        zwebmcp.register_parser()
        try:
            resp = await state.tab.send(
                zwebmcp.invoke_tool(fid, name, arguments))
        except Exception as e:
            if "Tool not found" in str(e):
                return ("notfound", None)
            raise
        invocation_id = resp["invocationId"]
        try:
            ev = await zb.wait_webmcp_response(invocation_id, ctx.deadline, name)
        except BaseException:
            import asyncio
            try:
                await asyncio.shield(
                    state.tab.send(zwebmcp.cancel_invocation(invocation_id)))
            except Exception:
                pass
            raise
        url = await state.tab.evaluate("location.href")
        return ("responded", ev, url)

    try:
        res = state.run_call(work, timeout_s=timeout_seconds)
    except state.DeadlineExpired:
        return ToolError(f"WebMCP tool '{name}' exceeded its deadline.",
                         "execution")
    except Exception as e:
        return _map_error(e)
    if res[0] == "unavailable":
        return ToolError(
            f"WebMCP is not available on this page (Chrome {res[1]}).",
            "execution")
    if res[0] == "notfound":
        return ToolError(
            f"No WebMCP tool named '{name}' on this page; "
            "call browser_webmcp_list.", "execution")
    if res[0] == "ambiguous":
        return ToolError(
            f"Several frames register '{name}'; pass frame_id to choose. "
            f"Frames: {res[1]}.", "execution")
    _, ev, url = res
    if ev.status == "Completed":
        return ToolSuccess(format_eval(
            url, json.dumps(ev.output, ensure_ascii=False), max_chars))
    if ev.status == "Error":
        return ToolError(
            f"WebMCP tool '{name}' failed: {_webmcp_error_message(ev)}",
            "execution")
    return ToolError(f"WebMCP tool '{name}' was cancelled.", "execution")
