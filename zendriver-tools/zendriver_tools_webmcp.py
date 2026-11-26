"""Raw WebMCP commands and the toolResponded parser (zendriver 0.18 gaps, D29).

zendriver 0.18 has no invokeTool/cancelInvocation bindings, and its
InvocationStatus enum is Success/Canceled/Error — it rejects Chrome's
"Completed" and drops every toolResponded event. This module sends the two
commands as raw generators and registers an idempotent parser that accepts
Completed/Canceled/Error.

Imported at module level by its users (D22); zendriver is imported lazily
inside the functions, so loading the plugin definitions does not import it.
"""


def invoke_tool(frame_id, tool_name, input):
    """Raw WebMCP.invokeTool; returns the invocationId response."""
    resp = yield {
        "method": "WebMCP.invokeTool",
        "params": {"frameId": frame_id, "toolName": tool_name, "input": input},
    }
    return resp


def cancel_invocation(invocation_id):
    """Raw WebMCP.cancelInvocation."""
    resp = yield {
        "method": "WebMCP.cancelInvocation",
        "params": {"invocationId": invocation_id},
    }
    return resp


class ToolResponded:
    """A WebMCP.toolResponded event parsed from raw JSON.

    ``status`` keeps Chrome's string (Completed/Canceled/Error). Registered
    into cdp.util._event_parsers so the connection delivers it to handlers.
    """

    def __init__(self, invocation_id, status, output=None, error_text=None,
                 exception=None):
        self.invocation_id = invocation_id
        self.status = status
        self.output = output
        self.error_text = error_text
        self.exception = exception

    @classmethod
    def from_json(cls, json):
        from zendriver.cdp import runtime
        exc = json.get("exception")
        return cls(
            invocation_id=str(json["invocationId"]),
            status=str(json["status"]),
            output=json.get("output"),
            error_text=json.get("errorText"),
            exception=runtime.RemoteObject.from_json(exc)
            if exc is not None else None,
        )


def register_parser():
    """Install the toolResponded parser. Idempotent: installing it again sets
    the same class. Must run before the first invokeTool (AC-W11)."""
    from zendriver import cdp
    cdp.util._event_parsers["WebMCP.toolResponded"] = ToolResponded
