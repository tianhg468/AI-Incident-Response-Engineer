"""Real MCP server client for live mode.

This module provides a client for connecting to real MCP servers
via stdio transport (the standard MCP communication method).
"""

import os
import logging
import subprocess
import json
from typing import Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RealMCPServerClient:
    """Client for connecting to a real MCP server via stdio.

    This wraps an MCP server process and communicates with it using
    the MCP protocol over stdio (stdin/stdout).

    The interface matches the mock server interface so the agent code
    is agnostic to whether it's talking to a real or mock server.
    """

    def __init__(
        self,
        service_name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[Path] = None
    ):
        """Initialize real MCP server client.

        Args:
            service_name: Service name (kubernetes, github, slack, etc.)
            command: Command to start the MCP server (e.g., "python", "node")
            args: Arguments for the command (e.g., ["server.py", "--config", "..."])
            env: Environment variables for the server process
            cwd: Working directory for the server process
        """
        self.service_name = service_name
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self.cwd = cwd

        # Server process (started lazily on first use)
        self._process: Optional[subprocess.Popen] = None
        self._tools_cache: Optional[list[dict]] = None

        logger.info(f"Configured real MCP server: {service_name}")

    def _ensure_started(self):
        """Ensure the MCP server process is started."""
        if self._process is not None:
            return

        try:
            logger.info(f"Starting MCP server: {self.command} {' '.join(self.args)}")

            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
                text=True,
                bufsize=1  # Line buffered
            )

            logger.info(f"MCP server started with PID {self._process.pid}")

        except Exception as e:
            logger.error(f"Failed to start MCP server {self.service_name}: {e}")
            raise

    def _send_request(self, method: str, params: Optional[dict] = None) -> dict:
        """Send a JSON-RPC request to the MCP server.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            JSON-RPC response

        Raises:
            RuntimeError: If server communication fails
        """
        self._ensure_started()

        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError(f"MCP server {self.service_name} is not running")

        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        try:
            # Send request
            request_line = json.dumps(request) + "\n"
            self._process.stdin.write(request_line)
            self._process.stdin.flush()

            # Read response
            response_line = self._process.stdout.readline()
            if not response_line:
                raise RuntimeError("Server closed connection")

            response = json.loads(response_line)

            # Check for JSON-RPC error
            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"MCP server error: {error.get('message', error)}")

            return response.get("result", {})

        except Exception as e:
            logger.error(f"MCP server communication error: {e}")
            raise

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server.

        Returns:
            List of tool definitions
        """
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            result = self._send_request("tools/list")
            tools = result.get("tools", [])
            self._tools_cache = tools
            logger.info(f"Loaded {len(tools)} tools from {self.service_name}")
            return tools

        except Exception as e:
            logger.error(f"Failed to list tools from {self.service_name}: {e}")
            # Return empty list on error
            return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool response
        """
        try:
            result = self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })

            return result

        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {self.service_name}: {e}")
            return {
                "error": str(e),
                "service": self.service_name,
                "tool": tool_name
            }

    def get_service_name(self) -> str:
        """Get the service name."""
        return self.service_name

    def shutdown(self):
        """Shutdown the MCP server process."""
        if self._process is not None:
            logger.info(f"Shutting down MCP server: {self.service_name}")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"MCP server {self.service_name} did not terminate, killing")
                self._process.kill()

            self._process = None

    def __del__(self):
        """Cleanup on deletion."""
        self.shutdown()
