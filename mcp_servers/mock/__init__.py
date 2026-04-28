"""Mock MCP servers for evaluation and testing.

These servers implement the same tool interfaces as real MCP servers
but serve canned fixture data from disk for deterministic evaluation.
"""

from mcp_servers.mock.base import BaseMockMCPServer, FixtureLoader
from mcp_servers.mock.kubernetes import MockKubernetesMCPServer
from mcp_servers.mock.github import MockGitHubMCPServer
from mcp_servers.mock.slack import MockSlackMCPServer
from mcp_servers.mock.observability import MockObservabilityMCPServer

__all__ = [
    "BaseMockMCPServer",
    "FixtureLoader",
    "MockKubernetesMCPServer",
    "MockGitHubMCPServer",
    "MockSlackMCPServer",
    "MockObservabilityMCPServer",
]
