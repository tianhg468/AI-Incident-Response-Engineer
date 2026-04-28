#!/usr/bin/env python3
"""Runbook & Deploy Correlator MCP Server.

A custom MCP server built from scratch using the official MCP Python SDK.
Provides three specialized tools for incident response:

1. find_runbook - Retrieves relevant runbooks from a markdown corpus
2. correlate_deploys - Analyzes deploys with suspicion scoring
3. similar_past_incidents - Vector search over historical incidents

This server runs via stdio and demonstrates:
- Custom MCP server implementation
- Tool schema design
- Vector search integration
- Structured knowledge retrieval

Author: Built as part of AI Incident Response Engineer project
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from runbook_correlator.tools.runbook_finder import RunbookFinder
from runbook_correlator.tools.deploy_correlator import DeployCorrelator
from runbook_correlator.tools.incident_searcher import IncidentSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RunbookCorrelatorServer:
    """Runbook & Deploy Correlator MCP Server.

    This server provides intelligent incident response tools by correlating
    runbooks, deployment history, and past incidents.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the server.

        Args:
            data_dir: Directory containing runbooks and incident data.
                     Defaults to ./data relative to this file.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"

        self.data_dir = data_dir
        self.server = Server("runbook-correlator")

        # Initialize tool implementations
        self.runbook_finder = RunbookFinder(data_dir / "runbooks")
        self.deploy_correlator = DeployCorrelator()
        self.incident_searcher = IncidentSearcher(data_dir / "past_incidents")

        # Register handlers
        self._register_handlers()

        logger.info(f"Initialized Runbook Correlator Server (data_dir: {data_dir})")

    def _register_handlers(self):
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="find_runbook",
                    description=(
                        "Find relevant runbooks for a service and alert type. "
                        "Searches through a curated markdown corpus of operational runbooks "
                        "and returns the most relevant guidance for handling the incident."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "Service name (e.g., 'payment-service', 'auth-service')"
                            },
                            "alert_type": {
                                "type": "string",
                                "description": "Type of alert (e.g., 'pod_crash_loop', 'high_latency', 'error_rate_spike')"
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low"],
                                "description": "Alert severity level (optional, for filtering)"
                            }
                        },
                        "required": ["service", "alert_type"]
                    }
                ),
                Tool(
                    name="correlate_deploys",
                    description=(
                        "Correlate recent deployments with incident timing to identify suspicious changes. "
                        "Returns deployments within the time window, ranked by suspicion score based on "
                        "timing correlation, change magnitude, and historical patterns."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "Service name"
                            },
                            "time_window_start": {
                                "type": "string",
                                "description": "Start of incident time window (ISO 8601)"
                            },
                            "time_window_end": {
                                "type": "string",
                                "description": "End of incident time window (ISO 8601)"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "description": "How many hours before incident to look for deploys",
                                "default": 24
                            }
                        },
                        "required": ["service", "time_window_start", "time_window_end"]
                    }
                ),
                Tool(
                    name="similar_past_incidents",
                    description=(
                        "Search for similar past incidents using semantic similarity. "
                        "Uses vector embeddings to find historical incidents with similar symptoms, "
                        "helping identify known issues and their resolutions."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symptom_text": {
                                "type": "string",
                                "description": "Description of current incident symptoms (logs, errors, metrics)"
                            },
                            "service": {
                                "type": "string",
                                "description": "Service name (optional, for filtering results)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of similar incidents to return",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "min_similarity": {
                                "type": "number",
                                "description": "Minimum similarity score (0.0-1.0)",
                                "default": 0.6,
                                "minimum": 0.0,
                                "maximum": 1.0
                            }
                        },
                        "required": ["symptom_text"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            logger.info(f"Tool called: {name} with arguments: {arguments}")

            try:
                if name == "find_runbook":
                    result = await self.runbook_finder.find_runbook(
                        service=arguments.get("service"),
                        alert_type=arguments.get("alert_type"),
                        severity=arguments.get("severity")
                    )
                elif name == "correlate_deploys":
                    result = await self.deploy_correlator.correlate_deploys(
                        service=arguments.get("service"),
                        time_window_start=arguments.get("time_window_start"),
                        time_window_end=arguments.get("time_window_end"),
                        lookback_hours=arguments.get("lookback_hours", 24)
                    )
                elif name == "similar_past_incidents":
                    result = await self.incident_searcher.search_similar(
                        symptom_text=arguments.get("symptom_text"),
                        service=arguments.get("service"),
                        limit=arguments.get("limit", 5),
                        min_similarity=arguments.get("min_similarity", 0.6)
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")

                # Format result as TextContent
                import json
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "tool": name
                    }, indent=2)
                )]

    async def run(self):
        """Run the server via stdio."""
        logger.info("Starting Runbook Correlator MCP Server via stdio...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point."""
    server = RunbookCorrelatorServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
