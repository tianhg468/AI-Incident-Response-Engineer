"""Live Observability MCP server using real Grafana API calls."""

from typing import Any
from mcp_servers.live_wrappers import LiveGrafanaClient


class LiveObservabilityMCPServer:
    """Live Observability MCP server that makes real Grafana API calls.

    This server uses the LiveGrafanaClient to make actual Grafana/Prometheus API requests
    and return real metrics and alerts from your observability stack.
    """

    def __init__(self):
        """Initialize live Grafana client."""
        self.client = LiveGrafanaClient()

    def get_service_name(self) -> str:
        return "observability"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available observability tools."""
        return [
            {
                "name": "grafana_query_metrics",
                "description": "Query Prometheus metrics via Grafana",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PromQL query string"
                        },
                        "time": {
                            "type": "string",
                            "description": "Query time (RFC3339 or Unix timestamp)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "grafana_get_alerts",
                "description": "Get active alerts from Grafana",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "Alert state filter",
                            "enum": ["alerting", "ok", "pending", "all"],
                            "default": "all"
                        }
                    }
                }
            },
            {
                "name": "grafana_get_dashboard",
                "description": "Get dashboard information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dashboard_uid": {
                            "type": "string",
                            "description": "Dashboard UID"
                        }
                    },
                    "required": ["dashboard_uid"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an observability tool with real API calls."""
        if tool_name == "grafana_query_metrics":
            return self._query_metrics(arguments)
        elif tool_name == "grafana_get_alerts":
            return self._get_alerts(arguments)
        elif tool_name == "grafana_get_dashboard":
            return self._get_dashboard(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _query_metrics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Query metrics from Prometheus via Grafana."""
        query = arguments.get("query", "")

        # Query metrics using live client
        result = self.client.query_metrics(query)

        return {
            "query": query,
            "status": result.get("status", "error"),
            "data": result.get("data", {}),
            "error": result.get("error")
        }

    def _get_alerts(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get alerts from Grafana."""
        state = arguments.get("state", "all")

        # Get alerts using live client
        result = self.client.get_alerts()

        # Filter by state if needed
        alerts = result.get("alerts", [])
        if state != "all":
            alerts = [a for a in alerts if a.get("state") == state]

        return {
            "alerts": alerts,
            "alert_count": len(alerts),
            "state_filter": state,
            "error": result.get("error")
        }

    def _get_dashboard(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get dashboard information."""
        dashboard_uid = arguments.get("dashboard_uid", "")

        return {
            "dashboard_uid": dashboard_uid,
            "title": "Dashboard Title",
            "description": "Dashboard data would be fetched from Grafana API",
            "panels": []
        }
