"""Tool definitions for Temporal workflow operations."""

from typing import Tuple

import temporal_client
from ayder_cli.tools.definition import ToolDefinition


TOOL_DEFINITIONS: Tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="temporal_workflow",
        description="Manage Temporal workflows and queue operations using action-based commands.",
        description_template="Temporal workflow action {action} will be invoked",
        tags=("temporal",),
        func_ref="temporal:temporal_workflow",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Temporal action to perform",
                    "enum": [
                        "start_workflow",
                        "query_workflow",
                        "signal_workflow",
                        "escalate",
                        "cancel_workflow",
                        "report_phase_result",
                    ],
                },
                "workflow_id": {
                    "type": "string",
                    "description": "User/PM-assigned workflow identifier",
                },
                "queue_name": {
                    "type": "string",
                    "description": "Target queue name for worker/workflow routing",
                },
                "signal_name": {
                    "type": "string",
                    "description": "Signal identifier (v1: clarify)",
                },
                "payload": {
                    "type": "object",
                    "description": "Action-specific payload object",
                },
            },
            "required": ["action"],
        },
        permission="w",
        safe_mode_blocked=True,
    ),
)

# Publish the Temporal status badge (green/red "TMP") to ayder's status bar at
# load time. Never raises.
temporal_client.publish_status()
