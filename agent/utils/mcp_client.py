"""MCP client wrapper for agent nodes."""

import logging
from typing import Any, Optional

from mcp_servers.registry import get_mcp_server

logger = logging.getLogger(__name__)


class MCPClient:
    """Wrapper for MCP server interactions.

    Provides a simplified interface for agent nodes to call MCP tools
    without needing to know about the registry or mode switching.
    """

    def __init__(self):
        """Initialize MCP client."""
        self.registry = get_mcp_server()
        logger.info(f"MCP Client initialized (mode: {self.registry.get_mode()})")

    def call_tool(self, service: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool.

        Args:
            service: Service name (kubernetes, github, slack, observability)
            tool_name: Tool name (e.g., "k8s_get_pod_status")
            arguments: Tool arguments

        Returns:
            Tool response
        """
        logger.info(f"Calling MCP tool: {service}.{tool_name}")
        logger.debug(f"Arguments: {arguments}")

        try:
            result = self.registry.call_tool(service, tool_name, arguments)
            logger.debug(f"Result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error calling {service}.{tool_name}: {e}", exc_info=True)
            return {
                "error": str(e),
                "service": service,
                "tool": tool_name
            }

    # Convenience methods for common operations

    def get_pod_status(self, namespace: str = "default", label_selector: Optional[str] = None) -> dict:
        """Get pod status from Kubernetes."""
        return self.call_tool("kubernetes", "k8s_get_pod_status", {
            "namespace": namespace,
            "label_selector": label_selector
        })

    def get_pod_logs(self, pod_name: str, namespace: str = "default", tail: int = 100) -> dict:
        """Get pod logs from Kubernetes."""
        return self.call_tool("kubernetes", "k8s_get_pod_logs", {
            "namespace": namespace,
            "pod_name": pod_name,
            "tail": tail
        })

    def get_events(self, namespace: str = "default", field_selector: Optional[str] = None) -> dict:
        """Get Kubernetes events."""
        return self.call_tool("kubernetes", "k8s_get_events", {
            "namespace": namespace,
            "field_selector": field_selector
        })

    def get_deployments(self, namespace: str = "default", deployment_name: Optional[str] = None) -> dict:
        """Get deployment information."""
        return self.call_tool("kubernetes", "k8s_get_deployments", {
            "namespace": namespace,
            "deployment_name": deployment_name
        })

    def get_recent_commits(self, repo: str, limit: int = 20) -> dict:
        """Get recent commits from GitHub."""
        return self.call_tool("github", "github_get_recent_commits", {
            "repo": repo,
            "limit": limit
        })

    def get_recent_prs(self, repo: str, limit: int = 10) -> dict:
        """Get recent PRs from GitHub."""
        return self.call_tool("github", "github_get_recent_prs", {
            "repo": repo,
            "limit": limit
        })

    def query_metrics(self, query: str) -> dict:
        """Query observability metrics."""
        return self.call_tool("observability", "obs_query_metric", {
            "query": query
        })

    def get_service_health(self, service: str, time_window: str = "1h") -> dict:
        """Get service health metrics."""
        return self.call_tool("observability", "obs_get_service_health", {
            "service": service,
            "time_window": time_window
        })

    def post_slack_message(self, channel: str, text: str) -> dict:
        """Post a message to Slack."""
        return self.call_tool("slack", "slack_post_message", {
            "channel": channel,
            "text": text
        })

    def post_approval_request(
        self,
        title: str,
        description: str,
        action_details: Optional[dict] = None,
        channel: str = "#incidents"
    ) -> dict:
        """Post an approval request to Slack."""
        return self.call_tool("slack", "slack_request_approval", {
            "channel": channel,
            "title": title,
            "description": description,
            "action_details": action_details or {}
        })

    def get_approval_status(self, approval_id: str) -> dict:
        """Check approval status."""
        return self.call_tool("slack", "slack_get_approval_status", {
            "approval_id": approval_id
        })


# Singleton instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create the singleton MCP client.

    Returns:
        MCPClient instance
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
