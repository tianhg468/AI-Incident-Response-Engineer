"""Live API wrappers for MCP servers in production mode.

These functions make real API calls to Kubernetes, GitHub, Slack, and Grafana
when MODE=live.
"""

import os
import subprocess
import json
import requests
from typing import Any, Optional


class LiveKubernetesClient:
    """Make real kubectl API calls."""

    def __init__(self):
        self.namespace = os.getenv("K8S_NAMESPACE", "default")

    def get_pod_status(self, service: str) -> dict[str, Any]:
        """Get real pod status from Kubernetes."""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-l", f"app={service}", "-n", self.namespace, "-o", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)

            pods = []
            for item in data.get("items", []):
                pods.append({
                    "name": item["metadata"]["name"],
                    "status": item["status"]["phase"],
                    "restarts": sum(cs.get("restartCount", 0) for cs in item["status"].get("containerStatuses", [])),
                    "ready": all(cs.get("ready", False) for cs in item["status"].get("containerStatuses", [])),
                    "node": item["spec"].get("nodeName"),
                })

            return {"pods": pods}
        except Exception as e:
            return {"error": str(e), "pods": []}

    def get_pod_logs(self, service: str, tail_lines: int = 50) -> dict[str, Any]:
        """Get real pod logs."""
        try:
            # Get first pod
            result = subprocess.run(
                ["kubectl", "get", "pods", "-l", f"app={service}", "-n", self.namespace, "-o", "jsonpath={.items[0].metadata.name}"],
                capture_output=True,
                text=True,
                check=True
            )
            pod_name = result.stdout.strip()

            # Get logs
            result = subprocess.run(
                ["kubectl", "logs", pod_name, "-n", self.namespace, f"--tail={tail_lines}"],
                capture_output=True,
                text=True,
                check=True
            )

            return {"logs": result.stdout.split("\n")}
        except Exception as e:
            return {"error": str(e), "logs": []}

    def get_events(self, service: str) -> dict[str, Any]:
        """Get Kubernetes events."""
        try:
            result = subprocess.run(
                ["kubectl", "get", "events", "-n", self.namespace, "--field-selector", f"involvedObject.name={service}", "-o", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)

            events = []
            for item in data.get("items", []):
                events.append({
                    "type": item.get("type"),
                    "reason": item.get("reason"),
                    "message": item.get("message"),
                    "timestamp": item.get("lastTimestamp"),
                    "count": item.get("count", 1),
                })

            return {"events": events}
        except Exception as e:
            return {"error": str(e), "events": []}

    def get_deployment_history(self, service: str) -> dict[str, Any]:
        """Get deployment history."""
        try:
            result = subprocess.run(
                ["kubectl", "rollout", "history", f"deployment/{service}", "-n", self.namespace, "-o", "json"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output (it's not JSON, so we'll parse the text)
            lines = result.stdout.strip().split("\n")
            deployments = []

            for line in lines[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    deployments.append({
                        "revision": parts[0],
                        "change_cause": " ".join(parts[1:]) if len(parts) > 1 else "unknown"
                    })

            return {"deployments": deployments}
        except Exception as e:
            return {"error": str(e), "deployments": []}


class LiveGitHubClient:
    """Make real GitHub API calls."""

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.org = os.getenv("GITHUB_ORG")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def get_commits(self, repo: str, limit: int = 10) -> dict[str, Any]:
        """Get recent commits."""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/commits"
            response = requests.get(url, headers=self.headers, params={"per_page": limit})
            response.raise_for_status()

            commits = []
            for item in response.json():
                commits.append({
                    "sha": item["sha"][:7],
                    "message": item["commit"]["message"],
                    "author": item["commit"]["author"]["name"],
                    "date": item["commit"]["author"]["date"],
                    "url": item["html_url"]
                })

            return {"commits": commits}
        except Exception as e:
            return {"error": str(e), "commits": []}

    def get_pull_requests(self, repo: str, state: str = "all", limit: int = 10) -> dict[str, Any]:
        """Get pull requests."""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/pulls"
            response = requests.get(url, headers=self.headers, params={"state": state, "per_page": limit})
            response.raise_for_status()

            prs = []
            for item in response.json():
                prs.append({
                    "number": item["number"],
                    "title": item["title"],
                    "state": item["state"],
                    "author": item["user"]["login"],
                    "created_at": item["created_at"],
                    "merged_at": item.get("merged_at"),
                    "url": item["html_url"]
                })

            return {"pull_requests": prs}
        except Exception as e:
            return {"error": str(e), "pull_requests": []}


class LiveSlackClient:
    """Make real Slack API calls."""

    def __init__(self):
        self.token = os.getenv("SLACK_BOT_TOKEN")
        self.channel = os.getenv("SLACK_CHANNEL", "#incidents")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def post_message(self, text: str, blocks: Optional[list] = None) -> dict[str, Any]:
        """Post message to Slack."""
        try:
            payload = {
                "channel": self.channel,
                "text": text
            }
            if blocks:
                payload["blocks"] = blocks

            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                return {"error": data.get("error"), "success": False}

            return {"success": True, "ts": data.get("ts")}
        except Exception as e:
            return {"error": str(e), "success": False}

    def request_approval(self, action_type: str, description: str) -> dict[str, Any]:
        """Request approval via Slack with interactive buttons."""
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🔒 Approval Required: {action_type}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Description:*\n{description}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Approve"
                            },
                            "style": "primary",
                            "value": "approve",
                            "action_id": "approve_action"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "❌ Reject"
                            },
                            "style": "danger",
                            "value": "reject",
                            "action_id": "reject_action"
                        }
                    ]
                }
            ]

            return self.post_message(
                text=f"Approval required for {action_type}",
                blocks=blocks
            )
        except Exception as e:
            return {"error": str(e), "success": False}


class LiveGrafanaClient:
    """Make real Grafana API calls."""

    def __init__(self):
        self.url = os.getenv("GRAFANA_URL", "http://localhost:3000")
        self.api_key = os.getenv("GRAFANA_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def query_metrics(self, query: str) -> dict[str, Any]:
        """Query Prometheus metrics via Grafana."""
        try:
            # Query Prometheus datasource through Grafana
            url = f"{self.url}/api/datasources/proxy/1/api/v1/query"
            response = requests.get(
                url,
                headers=self.headers,
                params={"query": query}
            )
            response.raise_for_status()
            data = response.json()

            return {"status": data.get("status"), "data": data.get("data")}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def get_alerts(self) -> dict[str, Any]:
        """Get active alerts from Grafana."""
        try:
            url = f"{self.url}/api/alerts"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            alerts = []
            for item in response.json():
                alerts.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "state": item.get("state"),
                    "new_state_date": item.get("newStateDate")
                })

            return {"alerts": alerts}
        except Exception as e:
            return {"error": str(e), "alerts": []}
