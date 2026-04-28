"""Mock Slack MCP server."""

from typing import Any, Optional
from datetime import datetime
import uuid

from mcp_servers.mock.base import BaseMockMCPServer, FixtureLoader


class MockSlackMCPServer(BaseMockMCPServer):
    """Mock Slack MCP server serving fixture data.

    Tools provided:
    - post_message: Post a message to a Slack channel
    - post_approval_request: Post an approval request with interactive buttons
    - get_approval_status: Check status of an approval request
    - update_message: Update an existing message
    """

    def __init__(self, fixture_loader: Optional[FixtureLoader] = None):
        super().__init__(fixture_loader)
        # Track posted messages and approvals in memory
        self.messages = []
        self.approvals = {}

        # Load Slack configuration from fixtures
        try:
            self.config = self._load_fixture("config.json")
        except FileNotFoundError:
            # Default config if fixture doesn't exist
            self.config = {
                "auto_approve": True,  # Auto-approve in mock mode
                "approval_delay_seconds": 0,
                "default_channel": "#incidents"
            }

    def get_service_name(self) -> str:
        return "slack"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available Slack tools."""
        return [
            {
                "name": "slack_post_message",
                "description": "Post a message to a Slack channel",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel name or ID (e.g., #incidents)"
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text (supports Markdown)"
                        },
                        "blocks": {
                            "type": "array",
                            "description": "Slack blocks for rich formatting (optional)"
                        }
                    },
                    "required": ["channel", "text"]
                }
            },
            {
                "name": "slack_post_approval_request",
                "description": "Post an approval request with interactive buttons",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel name or ID",
                            "default": "#incidents"
                        },
                        "title": {
                            "type": "string",
                            "description": "Approval request title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of what needs approval"
                        },
                        "action_details": {
                            "type": "object",
                            "description": "Details about the action (expected effect, blast radius, etc.)"
                        }
                    },
                    "required": ["title", "description"]
                }
            },
            {
                "name": "slack_get_approval_status",
                "description": "Check the status of an approval request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "approval_id": {
                            "type": "string",
                            "description": "Approval request ID"
                        }
                    },
                    "required": ["approval_id"]
                }
            },
            {
                "name": "slack_update_message",
                "description": "Update an existing Slack message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel name or ID"
                        },
                        "message_ts": {
                            "type": "string",
                            "description": "Message timestamp (from post_message response)"
                        },
                        "text": {
                            "type": "string",
                            "description": "New message text"
                        }
                    },
                    "required": ["channel", "message_ts", "text"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a Slack tool with fixture-driven behavior."""
        if tool_name == "slack_post_message":
            return self._post_message(arguments)
        elif tool_name == "slack_post_approval_request":
            return self._post_approval_request(arguments)
        elif tool_name == "slack_get_approval_status":
            return self._get_approval_status(arguments)
        elif tool_name == "slack_update_message":
            return self._update_message(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _post_message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Post a message to Slack (mocked)."""
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()

        message = {
            "message_id": message_id,
            "ts": timestamp,
            "channel": arguments.get("channel", self.config.get("default_channel")),
            "text": arguments.get("text"),
            "blocks": arguments.get("blocks"),
            "posted_at": timestamp
        }

        self.messages.append(message)

        return {
            "ok": True,
            "message_id": message_id,
            "ts": timestamp,
            "channel": message["channel"],
            "permalink": f"https://mock-slack.com/archives/{message['channel']}/p{message_id}"
        }

    def _post_approval_request(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Post an approval request (mocked with auto-approval option)."""
        approval_id = f"approval_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()

        channel = arguments.get("channel", self.config.get("default_channel"))

        # Create approval record
        approval = {
            "approval_id": approval_id,
            "channel": channel,
            "title": arguments.get("title"),
            "description": arguments.get("description"),
            "action_details": arguments.get("action_details", {}),
            "status": "approved" if self.config.get("auto_approve", True) else "pending",
            "requested_at": timestamp,
            "decided_at": timestamp if self.config.get("auto_approve", True) else None,
            "decided_by": "auto-approve" if self.config.get("auto_approve", True) else None,
            "reasoning": "Auto-approved in eval mode" if self.config.get("auto_approve", True) else None
        }

        self.approvals[approval_id] = approval

        # Also post as a message
        message = self._post_message({
            "channel": channel,
            "text": f"🔔 Approval Request: {arguments.get('title')}\n\n{arguments.get('description')}"
        })

        return {
            "ok": True,
            "approval_id": approval_id,
            "message_ts": message["ts"],
            "channel": channel,
            "status": approval["status"],
            "auto_approved": self.config.get("auto_approve", True)
        }

    def _get_approval_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get approval status (mocked)."""
        approval_id = arguments.get("approval_id")

        if approval_id not in self.approvals:
            return {
                "ok": False,
                "error": f"Approval not found: {approval_id}"
            }

        approval = self.approvals[approval_id]

        return {
            "ok": True,
            "approval_id": approval_id,
            "status": approval["status"],
            "decided_at": approval.get("decided_at"),
            "decided_by": approval.get("decided_by"),
            "reasoning": approval.get("reasoning")
        }

    def _update_message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Update a message (mocked)."""
        message_ts = arguments.get("message_ts")

        # Find and update the message
        for msg in self.messages:
            if msg["ts"] == message_ts:
                msg["text"] = arguments.get("text")
                msg["updated_at"] = datetime.now().isoformat()
                return {
                    "ok": True,
                    "message_id": msg["message_id"],
                    "ts": message_ts,
                    "channel": arguments.get("channel")
                }

        return {
            "ok": False,
            "error": f"Message not found: {message_ts}"
        }

    def simulate_approval(self, approval_id: str, approved: bool, reasoning: str = "") -> dict[str, Any]:
        """Simulate a human approval decision (for testing).

        This is not a tool - it's a testing helper to simulate human interaction.
        """
        if approval_id not in self.approvals:
            return {"error": f"Approval not found: {approval_id}"}

        approval = self.approvals[approval_id]
        approval["status"] = "approved" if approved else "rejected"
        approval["decided_at"] = datetime.now().isoformat()
        approval["decided_by"] = "simulated_user"
        approval["reasoning"] = reasoning or ("Approved for testing" if approved else "Rejected for testing")

        return {
            "ok": True,
            "approval_id": approval_id,
            "status": approval["status"]
        }
