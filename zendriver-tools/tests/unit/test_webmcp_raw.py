"""AC-W11: raw WebMCP commands + idempotent toolResponded parser (no Chrome)."""
import zendriver_tools_webmcp as wm
from zendriver import cdp


def test_raw_invoke_tool_generator():
    gen = wm.invoke_tool("F1", "echo", {"text": "hi"})
    assert next(gen) == {
        "method": "WebMCP.invokeTool",
        "params": {"frameId": "F1", "toolName": "echo", "input": {"text": "hi"}},
    }


def test_raw_cancel_invocation_generator():
    gen = wm.cancel_invocation("I1")
    assert next(gen) == {
        "method": "WebMCP.cancelInvocation", "params": {"invocationId": "I1"}}


def test_completed_event_delivered_with_output():
    wm.register_parser()
    ev = cdp.util.parse_json_event({
        "method": "WebMCP.toolResponded",
        "params": {"invocationId": "I1", "status": "Completed",
                   "output": {"content": [{"type": "text", "text": "echo:hi"}]}}})
    assert isinstance(ev, wm.ToolResponded)
    assert ev.status == "Completed"
    assert ev.invocation_id == "I1"
    assert ev.output["content"][0]["text"] == "echo:hi"


def test_canceled_and_error_status_accepted():
    wm.register_parser()
    for st in ("Canceled", "Error"):
        ev = cdp.util.parse_json_event({
            "method": "WebMCP.toolResponded",
            "params": {"invocationId": "I2", "status": st}})
        assert ev.status == st


def test_register_parser_idempotent():
    wm.register_parser()
    wm.register_parser()
    assert cdp.util._event_parsers["WebMCP.toolResponded"] is wm.ToolResponded
    ev = cdp.util.parse_json_event({
        "method": "WebMCP.toolResponded",
        "params": {"invocationId": "I3", "status": "Completed", "output": 1}})
    assert ev.status == "Completed" and ev.output == 1


def test_tools_removed_slim_shape_parsed():
    # Chrome sends {name, frameId} only; zendriver's full-Tool parser raises on
    # the missing description and drops the event. The plugin parser accepts it.
    wm.register_parser()
    ev = cdp.util.parse_json_event({
        "method": "WebMCP.toolsRemoved",
        "params": {"tools": [{"name": "echo", "frameId": "F1"}]}})
    assert isinstance(ev, wm.ToolsRemoved)
    assert ev.tools[0].name == "echo"
    assert str(ev.tools[0].frame_id) == "F1"


def test_tools_added_preserves_raw_annotations():
    # zendriver's Annotation parser drops untrustedContent/consequential; the
    # plugin keeps the raw tool dict so they can be mapped.
    wm.register_parser()
    ev = cdp.util.parse_json_event({
        "method": "WebMCP.toolsAdded",
        "params": {"tools": [{"name": "echo", "description": "d", "frameId": "F1",
                              "annotations": {"readOnly": True,
                                              "untrustedContent": True,
                                              "consequential": False}}]}})
    assert isinstance(ev, wm.ToolsAdded)
    ann = ev.tools[0]["annotations"]
    assert ann["untrustedContent"] is True and ann["consequential"] is False
