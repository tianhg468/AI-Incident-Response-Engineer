"""Live Slack MCP server using real Slack API calls."""

from typing import Any
from mcp_servers.live_wrappers import LiveSlackClient


class LiveSlackMCPServer:
    """Live Slack MCP server that makes real Slack API calls.

    This server uses the LiveSlackClient to make actual Slack Bot API requests
    and post messages to your Slack workspace.
    """

    def __init__(self):
        """Initialize live Slack client."""
        self.client = LiveSlackClient()

    def get_service_name(self) -> str:
        return "slack"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available Slack tools."""
        return [
            {
                "name": "slack_post_message",
                "description": "Post a message to Slack channel",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel name or ID",
                            "default": "#incidents"
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text"
                        },
                        "blocks": {
                            "type": "array",
                            "description": "Slack block kit blocks (optional)"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "slack_request_approval",
                "description": "Request approval via Slack with interactive buttons",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "description": "Type of action requiring approval (e.g., 'rollback', 'restart')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the action"
                        },
                        "channel": {
                            "type": "string",
                            "description": "Channel to post to",
                            "default": "#incidents"
                        }
                    },
                    "required": ["action_type", "description"]
                }
            },
            {
                "name": "slack_post_incident_update",
                "description": "Post an incident status update",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "incident_id": {
                            "type": "string",
                            "description": "Incident identifier"
                        },
                        "status": {
                            "type": "string",
                            "description": "Current status",
                            "enum": ["investigating", "identified", "monitoring", "resolved"]
                        },
                        "message": {
                            "type": "string",
                            "description": "Update message"
                        },
                        "channel": {
                            "type": "string",
                            "description": "Channel to post to",
                            "default": "#incidents"
                        }
                    },
                    "required": ["incident_id", "status", "message"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a Slack tool with real API calls."""
        if tool_name == "slack_post_message":
            return self._post_message(arguments)
        elif tool_name == "slack_request_approval":
            return self._request_approval(arguments)
        elif tool_name == "slack_post_incident_update":
            return self._post_incident_update(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _post_message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Post a message to Slack."""
        text = arguments.get("text", "")
        blocks = arguments.get("blocks")

        # Post message using live client
        result = self.client.post_message(text, blocks=blocks)

        return {
            "success": result.get("success", False),
            "channel": self.client.channel,
            "ts": result.get("ts"),
            "error": result.get("error")
        }

    def _request_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Request approval via Slack."""
        import time

        action_type = arguments.get("action_type", "")
        description = arguments.get("description", "")

        # Generate approval_id FIRST (before posting to Slack)
        # This allows us to embed it in the button value
        approval_id = str(time.time())

        # Register approval with manager BEFORE posting to Slack
        # This ensures the approval exists when the button is clicked
        from webhook.approval_manager import get_approval_manager
        manager = get_approval_manager()
        manager.create_approval(
            approval_id=approval_id,
            action_type=action_type,
            description=description
        )

        # Now request approval using live client WITH the approval_id
        result = self.client.request_approval(action_type, description, approval_id=approval_id)

        return {
            "success": result.get("success", False),
            "ok": result.get("success", False),  # Add 'ok' for compatibility
            "channel": self.client.channel,
            "ts": result.get("ts"),
            "approval_id": approval_id,
            "error": result.get("error"),
            "message": f"Approval request posted for: {action_type}"
        }

    def _post_incident_update(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Post an incident status update."""
        incident_id = arguments.get("incident_id", "")
        status = arguments.get("status", "investigating")
        message = arguments.get("message", "")

        # Create formatted blocks for incident update
        status_emoji = {
            "investigating": "🔍",
            "identified": "✓",
            "monitoring": "👀",
            "resolved": "✅"
        }

        emoji = status_emoji.get(status, "📌")
        text = f"{emoji} **Incident {incident_id}** - Status: {status.upper()}\n\n{message}"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Incident {incident_id}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n<!date^{int(__import__('time').time())}^{{time}}|now>"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        # Post message using live client
        result = self.client.post_message(text, blocks=blocks)

        return {
            "success": result.get("success", False),
            "channel": self.client.channel,
            "ts": result.get("ts"),
            "error": result.get("error"),
            "incident_id": incident_id,
            "status": status
        }
