"""Mock Observability MCP server (Prometheus-like interface)."""

from typing import Any, Optional
from datetime import datetime, timedelta

from mcp_servers.mock.base import BaseMockMCPServer, FixtureLoader


class MockObservabilityMCPServer(BaseMockMCPServer):
    """Mock Observability MCP server serving fixture metrics data.

    Provides a Prometheus-like interface for querying metrics.

    Tools provided:
    - query_metric: Run a PromQL-like query
    - query_range: Run a range query for time-series data
    - get_alerts: Get active alerts
    - get_metric_labels: Get available labels for a metric
    """

    def get_service_name(self) -> str:
        return "observability"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available observability tools."""
        return [
            {
                "name": "obs_query_metric",
                "description": "Query metrics using PromQL-like syntax",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Metric query (e.g., 'http_requests_total', 'cpu_usage{pod=~\"payment.*\"}')"
                        },
                        "time": {
                            "type": "string",
                            "description": "Query timestamp (ISO 8601, defaults to now)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "obs_query_range",
                "description": "Query time-series metrics over a time range",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Metric query"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (ISO 8601)"
                        },
                        "end": {
                            "type": "string",
                            "description": "End time (ISO 8601)"
                        },
                        "step": {
                            "type": "string",
                            "description": "Query resolution step (e.g., '1m', '5m')",
                            "default": "1m"
                        }
                    },
                    "required": ["query", "start", "end"]
                }
            },
            {
                "name": "obs_get_alerts",
                "description": "Get active alerts from alerting system",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Filter by service name (optional)"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Filter by severity (optional)"
                        }
                    }
                }
            },
            {
                "name": "obs_get_metric_labels",
                "description": "Get available labels and their values for a metric",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "Metric name"
                        }
                    },
                    "required": ["metric"]
                }
            },
            {
                "name": "obs_get_service_health",
                "description": "Get overall health metrics for a service",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name"
                        },
                        "time_window": {
                            "type": "string",
                            "description": "Time window (e.g., '1h', '6h', '24h')",
                            "default": "1h"
                        }
                    },
                    "required": ["service"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an observability tool with fixture data."""
        if tool_name == "obs_query_metric":
            return self._query_metric(arguments)
        elif tool_name == "obs_query_range":
            return self._query_range(arguments)
        elif tool_name == "obs_get_alerts":
            return self._get_alerts(arguments)
        elif tool_name == "obs_get_metric_labels":
            return self._get_metric_labels(arguments)
        elif tool_name == "obs_get_service_health":
            return self._get_service_health(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _query_metric(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Query a metric at a specific time."""
        metrics = self._load_fixture("metrics.json")
        query = arguments.get("query", "")

        # Simple query parsing (in real impl, would use proper PromQL parser)
        # For now, match metric name
        metric_name = query.split("{")[0].strip()

        results = []
        for metric_def in metrics:
            if metric_def.get("name") == metric_name:
                # Get the latest value
                values = metric_def.get("values", [])
                if values:
                    latest = values[-1]
                    results.append({
                        "metric": metric_def.get("labels", {}),
                        "value": [latest.get("timestamp"), str(latest.get("value"))]
                    })

        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": results
            }
        }

    def _query_range(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Query metrics over a time range."""
        metrics = self._load_fixture("metrics.json")
        query = arguments.get("query", "")
        start = arguments.get("start")
        end = arguments.get("end")

        # Simple query parsing
        metric_name = query.split("{")[0].strip()

        results = []
        for metric_def in metrics:
            if metric_def.get("name") == metric_name:
                # Filter values by time range
                values = metric_def.get("values", [])
                filtered_values = []

                for v in values:
                    timestamp = v.get("timestamp", "")
                    if start <= timestamp <= end:
                        filtered_values.append([timestamp, str(v.get("value"))])

                if filtered_values:
                    results.append({
                        "metric": metric_def.get("labels", {}),
                        "values": filtered_values
                    })

        return {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": results
            }
        }

    def _get_alerts(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get active alerts from fixtures."""
        try:
            alerts = self._load_fixture("alerts.json")
        except FileNotFoundError:
            # No alerts fixture
            alerts = []

        # Apply filters
        service = arguments.get("service")
        severity = arguments.get("severity")

        if service:
            alerts = [a for a in alerts if a.get("labels", {}).get("service") == service]

        if severity:
            alerts = [a for a in alerts if a.get("labels", {}).get("severity") == severity]

        return {
            "status": "success",
            "data": {
                "alerts": alerts,
                "alert_count": len(alerts)
            }
        }

    def _get_metric_labels(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get available labels for a metric."""
        metrics = self._load_fixture("metrics.json")
        metric_name = arguments.get("metric")

        labels_map = {}
        for metric_def in metrics:
            if metric_def.get("name") == metric_name:
                labels = metric_def.get("labels", {})
                for key, value in labels.items():
                    if key not in labels_map:
                        labels_map[key] = set()
                    labels_map[key].add(value)

        # Convert sets to lists
        labels = {k: list(v) for k, v in labels_map.items()}

        return {
            "status": "success",
            "data": {
                "metric": metric_name,
                "labels": labels
            }
        }

    def _get_service_health(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get overall service health metrics."""
        service = arguments.get("service")
        time_window = arguments.get("time_window", "1h")

        # Load various metrics and aggregate into a health summary
        metrics = self._load_fixture("metrics.json")

        # Filter metrics for this service
        service_metrics = [
            m for m in metrics
            if m.get("labels", {}).get("service") == service
        ]

        # Aggregate common health indicators
        health_summary = {
            "service": service,
            "time_window": time_window,
            "error_rate": 0.0,
            "latency_p50": 0.0,
            "latency_p95": 0.0,
            "latency_p99": 0.0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "request_rate": 0.0
        }

        # Extract values from metrics
        for metric in service_metrics:
            name = metric.get("name", "")
            values = metric.get("values", [])

            if not values:
                continue

            latest_value = values[-1].get("value", 0)

            if "error_rate" in name:
                health_summary["error_rate"] = latest_value
            elif "latency_p50" in name or "latency" in name and "quantile" in metric.get("labels", {}) and metric["labels"]["quantile"] == "0.5":
                health_summary["latency_p50"] = latest_value
            elif "latency_p95" in name or "latency" in name and "quantile" in metric.get("labels", {}) and metric["labels"]["quantile"] == "0.95":
                health_summary["latency_p95"] = latest_value
            elif "latency_p99" in name or "latency" in name and "quantile" in metric.get("labels", {}) and metric["labels"]["quantile"] == "0.99":
                health_summary["latency_p99"] = latest_value
            elif "cpu" in name:
                health_summary["cpu_usage"] = latest_value
            elif "memory" in name:
                health_summary["memory_usage"] = latest_value
            elif "request_rate" in name or "requests_total" in name:
                health_summary["request_rate"] = latest_value

        return {
            "status": "success",
            "data": health_summary
        }
