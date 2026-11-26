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
    """Install the toolResponded and toolsRemoved parsers. Idempotent: installing
    again sets the same classes. Must run before the first invokeTool (AC-W11)."""
    from zendriver import cdp
    cdp.util._event_parsers["WebMCP.toolResponded"] = ToolResponded
    cdp.util._event_parsers["WebMCP.toolsRemoved"] = ToolsRemoved
    cdp.util._event_parsers["WebMCP.toolsAdded"] = ToolsAdded


class ToolsAdded:
    """WebMCP.toolsAdded keeping the raw tool dicts.

    zendriver 0.18's Annotation parser keeps only readOnly/autosubmit and drops
    untrustedContent/consequential/debugging, so the plugin preserves the raw
    tool JSON for faithful annotation mapping (spec §5.1).
    """

    def __init__(self, tools):
        self.tools = tools

    @classmethod
    def from_json(cls, json):
        return cls(tools=list(json["tools"]))


class RemovedTool:
    """The slim {name, frameId} shape Chrome sends for a removed tool."""

    def __init__(self, name, frame_id):
        self.name = name
        self.frame_id = frame_id


class ToolsRemoved:
    """WebMCP.toolsRemoved parsed from Chrome's slim {name, frameId} shape.

    zendriver 0.18 parses these as full Tool objects and raises on the missing
    ``description``, dropping the event; this accepts the slim shape so the live
    registry reflects unregistration (spec rev 2 §5.1, AC-W7).
    """

    def __init__(self, tools):
        self.tools = tools

    @classmethod
    def from_json(cls, json):
        return cls(tools=[RemovedTool(str(t["name"]), str(t["frameId"]))
                          for t in json["tools"]])
