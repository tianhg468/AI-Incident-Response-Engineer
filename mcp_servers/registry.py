"""MCP server registry for switching between real and mock servers.

This module provides a unified interface to MCP servers that works
in both live mode (real MCP servers) and eval mode (fixture-based mocks).

The agent code is agnostic to which mode it's running in - it just
calls tools through the registry, which routes to the appropriate backend.
"""

import os
from typing import Any, Optional, Literal
from enum import Enum

from mcp_servers.mock.base import FixtureLoader
from mcp_servers.mock.kubernetes import MockKubernetesMCPServer
from mcp_servers.mock.github import MockGitHubMCPServer
from mcp_servers.mock.slack import MockSlackMCPServer
from mcp_servers.mock.observability import MockObservabilityMCPServer


class MCPMode(str, Enum):
    """MCP server mode."""
    LIVE = "live"  # Real MCP servers
    EVAL = "eval"  # Fixture-based mocks


class MCPServerRegistry:
    """Registry for MCP servers with mode-based routing.

    Usage:
        # In eval mode
        registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

        # Call a tool (works with both real and mock servers)
        result = registry.call_tool("kubernetes", "k8s_get_pod_status", {...})

        # In live mode
        registry = MCPServerRegistry(mode="live")
        result = registry.call_tool("kubernetes", "k8s_get_pod_status", {...})
    """

    def __init__(
        self,
        mode: Optional[Literal["live", "eval"]] = None,
        scenario: Optional[str] = None
    ):
        """Initialize MCP server registry.

        Args:
            mode: Mode to run in (live or eval). Defaults to MODE env var.
            scenario: Scenario name for eval mode. Defaults to SCENARIO env var.
        """
        self.mode = MCPMode(mode or os.getenv("MODE", "eval"))
        self.scenario = scenario or os.getenv("SCENARIO", "default")

        # Initialize servers based on mode
        self._servers = {}

        if self.mode == MCPMode.EVAL:
            self._init_mock_servers()
        else:
            self._init_live_servers()

    def _init_mock_servers(self):
        """Initialize fixture-based mock servers."""
        fixture_loader = FixtureLoader(scenario=self.scenario)

        self._servers = {
            "kubernetes": MockKubernetesMCPServer(fixture_loader),
            "github": MockGitHubMCPServer(fixture_loader),
            "slack": MockSlackMCPServer(fixture_loader),
            "observability": MockObservabilityMCPServer(fixture_loader),
        }

        print(f"📦 Initialized mock MCP servers (scenario: {self.scenario})")

    def _init_live_servers(self):
        """Initialize real MCP servers.

        In live mode, we would connect to actual MCP servers via stdio or HTTP.
        For now, this is a placeholder.
        """
        # TODO: Implement real MCP server connections
        # This would use the MCP Python SDK to connect to actual servers
        # running as separate processes or remote services

        # Placeholder - would be replaced with actual MCP client connections
        raise NotImplementedError(
            "Live mode not yet implemented. "
            "Set MODE=eval to use fixture-based mock servers."
        )

    def get_server(self, service: str):
        """Get an MCP server instance by service name.

        Args:
            service: Service name (kubernetes, github, slack, observability)

        Returns:
            MCP server instance

        Raises:
            KeyError: If service not found
        """
        if service not in self._servers:
            raise KeyError(
                f"MCP server not found: {service}\n"
                f"Available servers: {list(self._servers.keys())}"
            )

        return self._servers[service]

    def list_tools(self, service: str) -> list[dict[str, Any]]:
        """List available tools for a service.

        Args:
            service: Service name

        Returns:
            List of tool definitions
        """
        server = self.get_server(service)
        return server.list_tools()

    def call_tool(
        self,
        service: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on an MCP server.

        This is the main interface agents use to interact with MCP servers.
        The implementation is transparent to whether it's a real or mock server.

        Args:
            service: Service name (kubernetes, github, slack, observability)
            tool_name: Tool name (e.g., "k8s_get_pod_status")
            arguments: Tool arguments

        Returns:
            Tool response
        """
        server = self.get_server(service)
        return server.call_tool(tool_name, arguments)

    def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """Get all available tools from all servers.

        Returns:
            Dict mapping service name to list of tools
        """
        return {
            service: server.list_tools()
            for service, server in self._servers.items()
        }

    def get_mode(self) -> str:
        """Get current mode."""
        return self.mode.value

    def get_scenario(self) -> Optional[str]:
        """Get current scenario (eval mode only)."""
        return self.scenario if self.mode == MCPMode.EVAL else None


# Singleton instance for easy access
_registry: Optional[MCPServerRegistry] = None


def get_mcp_server(
    mode: Optional[Literal["live", "eval"]] = None,
    scenario: Optional[str] = None,
    force_new: bool = False
) -> MCPServerRegistry:
    """Get or create the MCP server registry singleton.

    Args:
        mode: Mode to run in (defaults to env var)
        scenario: Scenario for eval mode (defaults to env var)
        force_new: Force creation of new registry instance

    Returns:
        MCPServerRegistry instance
    """
    global _registry

    if _registry is None or force_new:
        _registry = MCPServerRegistry(mode=mode, scenario=scenario)

    return _registry


def create_mcp_client(service: str, **kwargs) -> Any:
    """Create an MCP client for a specific service.

    This is a convenience function for getting a specific server instance.

    Args:
        service: Service name
        **kwargs: Passed to get_mcp_server()

    Returns:
        MCP server instance for the service
    """
    registry = get_mcp_server(**kwargs)
    return registry.get_server(service)
