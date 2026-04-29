"""Configuration for real MCP servers in live mode."""

import os
from typing import Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class MCPServerConfig:
    """Configuration for a real MCP server."""
    service_name: str
    command: str
    args: list[str]
    env: Optional[dict[str, str]] = None
    cwd: Optional[Path] = None
    description: str = ""


def get_kubernetes_server_config() -> MCPServerConfig:
    """Get configuration for Kubernetes MCP server.

    Environment variables:
        MCP_K8S_SERVER: Path to Kubernetes MCP server script/binary
        KUBECONFIG: Path to kubeconfig file (optional)
        K8S_NAMESPACE: Default namespace (optional)

    Returns:
        MCPServerConfig for Kubernetes
    """
    server_path = os.getenv("MCP_K8S_SERVER")

    if not server_path:
        raise ValueError(
            "MCP_K8S_SERVER environment variable not set. "
            "Please provide the path to your Kubernetes MCP server."
        )

    # Build environment
    env = {}
    if kubeconfig := os.getenv("KUBECONFIG"):
        env["KUBECONFIG"] = kubeconfig
    if namespace := os.getenv("K8S_NAMESPACE"):
        env["K8S_NAMESPACE"] = namespace

    return MCPServerConfig(
        service_name="kubernetes",
        command="python",
        args=[server_path],
        env=env if env else None,
        description="Kubernetes MCP server for pod status, logs, events, and deployments"
    )


def get_github_server_config() -> MCPServerConfig:
    """Get configuration for GitHub MCP server.

    Environment variables:
        MCP_GITHUB_SERVER: Path to GitHub MCP server script/binary
        GITHUB_TOKEN: GitHub personal access token
        GITHUB_ORG: GitHub organization name

    Returns:
        MCPServerConfig for GitHub
    """
    server_path = os.getenv("MCP_GITHUB_SERVER")

    if not server_path:
        raise ValueError(
            "MCP_GITHUB_SERVER environment variable not set. "
            "Please provide the path to your GitHub MCP server."
        )

    # Build environment
    env = {}
    if token := os.getenv("GITHUB_TOKEN"):
        env["GITHUB_TOKEN"] = token
    if org := os.getenv("GITHUB_ORG"):
        env["GITHUB_ORG"] = org

    return MCPServerConfig(
        service_name="github",
        command="python",
        args=[server_path],
        env=env if env else None,
        description="GitHub MCP server for commits, PRs, diffs, and file content"
    )


def get_slack_server_config() -> MCPServerConfig:
    """Get configuration for Slack MCP server.

    Environment variables:
        MCP_SLACK_SERVER: Path to Slack MCP server script/binary
        SLACK_BOT_TOKEN: Slack bot token
        SLACK_CHANNEL: Default Slack channel

    Returns:
        MCPServerConfig for Slack
    """
    server_path = os.getenv("MCP_SLACK_SERVER")

    if not server_path:
        raise ValueError(
            "MCP_SLACK_SERVER environment variable not set. "
            "Please provide the path to your Slack MCP server."
        )

    # Build environment
    env = {}
    if token := os.getenv("SLACK_BOT_TOKEN"):
        env["SLACK_BOT_TOKEN"] = token
    if channel := os.getenv("SLACK_CHANNEL"):
        env["SLACK_CHANNEL"] = channel

    return MCPServerConfig(
        service_name="slack",
        command="python",
        args=[server_path],
        env=env if env else None,
        description="Slack MCP server for messages, approvals, and notifications"
    )


def get_observability_server_config() -> MCPServerConfig:
    """Get configuration for observability MCP server.

    Supports multiple providers: Grafana, Datadog, Prometheus

    Environment variables:
        MCP_OBSERVABILITY_SERVER: Path to observability MCP server script/binary
        OBSERVABILITY_PROVIDER: Provider type (grafana, datadog, prometheus)
        GRAFANA_URL, GRAFANA_API_KEY: For Grafana
        DATADOG_API_KEY, DATADOG_APP_KEY: For Datadog
        PROMETHEUS_URL: For Prometheus

    Returns:
        MCPServerConfig for observability
    """
    server_path = os.getenv("MCP_OBSERVABILITY_SERVER")

    if not server_path:
        raise ValueError(
            "MCP_OBSERVABILITY_SERVER environment variable not set. "
            "Please provide the path to your observability MCP server."
        )

    # Build environment based on provider
    env = {}
    provider = os.getenv("OBSERVABILITY_PROVIDER", "grafana")
    env["OBSERVABILITY_PROVIDER"] = provider

    if provider == "grafana":
        if url := os.getenv("GRAFANA_URL"):
            env["GRAFANA_URL"] = url
        if key := os.getenv("GRAFANA_API_KEY"):
            env["GRAFANA_API_KEY"] = key
    elif provider == "datadog":
        if key := os.getenv("DATADOG_API_KEY"):
            env["DATADOG_API_KEY"] = key
        if app_key := os.getenv("DATADOG_APP_KEY"):
            env["DATADOG_APP_KEY"] = app_key
    elif provider == "prometheus":
        if url := os.getenv("PROMETHEUS_URL"):
            env["PROMETHEUS_URL"] = url

    return MCPServerConfig(
        service_name="observability",
        command="python",
        args=[server_path],
        env=env if env else None,
        description=f"Observability MCP server for metrics and alerts ({provider})"
    )


def get_runbook_correlator_server_config() -> MCPServerConfig:
    """Get configuration for custom Runbook Correlator MCP server.

    Environment variables:
        MCP_RUNBOOK_SERVER: Path to runbook correlator server (optional, has default)

    Returns:
        MCPServerConfig for runbook correlator
    """
    # Default to our custom server in the repo
    default_path = str(
        Path(__file__).parent.parent / "runbook_correlator" / "server.py"
    )
    server_path = os.getenv("MCP_RUNBOOK_SERVER", default_path)

    return MCPServerConfig(
        service_name="runbook_correlator",
        command="python",
        args=[server_path],
        description="Custom runbook and deploy correlator MCP server"
    )


def get_all_server_configs() -> dict[str, MCPServerConfig]:
    """Get configurations for all MCP servers.

    Returns:
        Dictionary mapping service name to MCPServerConfig
    """
    configs = {}

    # Core services (required for incident response)
    try:
        configs["kubernetes"] = get_kubernetes_server_config()
    except ValueError as e:
        print(f"⚠️  Kubernetes server not configured: {e}")

    try:
        configs["github"] = get_github_server_config()
    except ValueError as e:
        print(f"⚠️  GitHub server not configured: {e}")

    try:
        configs["slack"] = get_slack_server_config()
    except ValueError as e:
        print(f"⚠️  Slack server not configured: {e}")

    try:
        configs["observability"] = get_observability_server_config()
    except ValueError as e:
        print(f"⚠️  Observability server not configured: {e}")

    # Custom server (usually available)
    try:
        configs["runbook_correlator"] = get_runbook_correlator_server_config()
    except ValueError as e:
        print(f"⚠️  Runbook correlator not configured: {e}")

    if not configs:
        raise RuntimeError(
            "No MCP servers configured for live mode. "
            "Please set the appropriate MCP_*_SERVER environment variables. "
            "See .env.example for details."
        )

    return configs
