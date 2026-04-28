"""Mock Kubernetes MCP server."""

from typing import Any, Optional
from datetime import datetime, timedelta

from mcp_servers.mock.base import BaseMockMCPServer, FixtureLoader


class MockKubernetesMCPServer(BaseMockMCPServer):
    """Mock Kubernetes MCP server serving fixture data.

    Tools provided:
    - get_pod_status: Get current pod status and health
    - get_pod_logs: Retrieve logs from specific pods
    - get_events: Get Kubernetes events for a namespace/pod
    - get_deployments: Get deployment history and current state
    - describe_pod: Get detailed pod information
    """

    def get_service_name(self) -> str:
        return "kubernetes"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available Kubernetes tools."""
        return [
            {
                "name": "k8s_get_pod_status",
                "description": "Get current status of pods in a namespace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "default"
                        },
                        "label_selector": {
                            "type": "string",
                            "description": "Label selector (e.g., 'app=payment-service')"
                        }
                    }
                }
            },
            {
                "name": "k8s_get_pod_logs",
                "description": "Retrieve logs from a specific pod",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "default"
                        },
                        "pod_name": {
                            "type": "string",
                            "description": "Name of the pod"
                        },
                        "container": {
                            "type": "string",
                            "description": "Container name (optional)"
                        },
                        "since": {
                            "type": "string",
                            "description": "Only return logs after this time (RFC3339)"
                        },
                        "tail": {
                            "type": "integer",
                            "description": "Number of lines from the end of logs",
                            "default": 100
                        }
                    },
                    "required": ["pod_name"]
                }
            },
            {
                "name": "k8s_get_events",
                "description": "Get Kubernetes events for troubleshooting",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "default"
                        },
                        "field_selector": {
                            "type": "string",
                            "description": "Field selector (e.g., 'involvedObject.name=pod-name')"
                        }
                    }
                }
            },
            {
                "name": "k8s_get_deployments",
                "description": "Get deployment history and current state",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "default"
                        },
                        "deployment_name": {
                            "type": "string",
                            "description": "Deployment name (optional, returns all if not specified)"
                        }
                    }
                }
            },
            {
                "name": "k8s_describe_pod",
                "description": "Get detailed information about a specific pod",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "default"
                        },
                        "pod_name": {
                            "type": "string",
                            "description": "Name of the pod"
                        }
                    },
                    "required": ["pod_name"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a Kubernetes tool with fixture data."""
        if tool_name == "k8s_get_pod_status":
            return self._get_pod_status(arguments)
        elif tool_name == "k8s_get_pod_logs":
            return self._get_pod_logs(arguments)
        elif tool_name == "k8s_get_events":
            return self._get_events(arguments)
        elif tool_name == "k8s_get_deployments":
            return self._get_deployments(arguments)
        elif tool_name == "k8s_describe_pod":
            return self._describe_pod(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _get_pod_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get pod status from fixtures."""
        pods = self._load_fixture("pods.json")

        # Filter by label selector if provided
        label_selector = arguments.get("label_selector")
        if label_selector:
            # Simple label matching (e.g., "app=payment-service")
            filtered_pods = []
            for pod in pods:
                labels = pod.get("metadata", {}).get("labels", {})
                # Parse simple selectors like "app=payment-service"
                if "=" in label_selector:
                    key, value = label_selector.split("=", 1)
                    if labels.get(key) == value:
                        filtered_pods.append(pod)
            pods = filtered_pods

        return {
            "namespace": arguments.get("namespace", "default"),
            "pods": pods,
            "total_count": len(pods)
        }

    def _get_pod_logs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get pod logs from fixtures."""
        logs = self._load_fixture("logs.json")
        pod_name = arguments.get("pod_name")
        tail = arguments.get("tail", 100)

        # Filter logs for the specific pod
        pod_logs = [log for log in logs if log.get("pod") == pod_name]

        # Apply tail limit
        if tail and len(pod_logs) > tail:
            pod_logs = pod_logs[-tail:]

        return {
            "pod_name": pod_name,
            "namespace": arguments.get("namespace", "default"),
            "container": arguments.get("container"),
            "logs": pod_logs,
            "line_count": len(pod_logs)
        }

    def _get_events(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get Kubernetes events from fixtures."""
        events = self._load_fixture("events.json")

        # Filter by field selector if provided
        field_selector = arguments.get("field_selector")
        if field_selector:
            # Simple field matching
            filtered_events = []
            for event in events:
                # Parse selectors like "involvedObject.name=pod-name"
                if "involvedObject.name=" in field_selector:
                    name = field_selector.split("involvedObject.name=")[1]
                    if event.get("involvedObject", {}).get("name") == name:
                        filtered_events.append(event)
                else:
                    filtered_events.append(event)
            events = filtered_events

        return {
            "namespace": arguments.get("namespace", "default"),
            "events": events,
            "event_count": len(events)
        }

    def _get_deployments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get deployment information from fixtures."""
        deployments = self._load_fixture("deployments.json")

        # Filter by deployment name if provided
        deployment_name = arguments.get("deployment_name")
        if deployment_name:
            deployments = [d for d in deployments if d.get("metadata", {}).get("name") == deployment_name]

        return {
            "namespace": arguments.get("namespace", "default"),
            "deployments": deployments,
            "deployment_count": len(deployments)
        }

    def _describe_pod(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get detailed pod description from fixtures."""
        pods = self._load_fixture("pods.json")
        pod_name = arguments.get("pod_name")

        # Find the specific pod
        pod = None
        for p in pods:
            if p.get("metadata", {}).get("name") == pod_name:
                pod = p
                break

        if not pod:
            return {
                "error": f"Pod not found: {pod_name}",
                "namespace": arguments.get("namespace", "default")
            }

        # Also get events for this pod
        events_data = self._get_events({
            "namespace": arguments.get("namespace", "default"),
            "field_selector": f"involvedObject.name={pod_name}"
        })

        return {
            "pod": pod,
            "events": events_data.get("events", []),
            "namespace": arguments.get("namespace", "default")
        }
