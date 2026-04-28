"""Base classes for mock MCP servers."""

import json
import os
from pathlib import Path
from typing import Any, Optional
import yaml


class FixtureLoader:
    """Loads fixture data from disk for mock MCP servers."""

    def __init__(self, fixtures_dir: Optional[Path] = None, scenario: Optional[str] = None):
        """Initialize fixture loader.

        Args:
            fixtures_dir: Root fixtures directory (defaults to ./fixtures)
            scenario: Scenario name to load (from env var SCENARIO if not provided)
        """
        if fixtures_dir is None:
            # Default to fixtures/ in project root
            project_root = Path(__file__).parent.parent.parent
            fixtures_dir = project_root / "fixtures"

        self.fixtures_dir = fixtures_dir
        self.scenario = scenario or os.getenv("SCENARIO", "default")

        # Path to scenario-specific fixtures
        self.scenario_dir = self.fixtures_dir / "scenarios" / self.scenario

        # Path to shared fixtures
        self.shared_dir = self.fixtures_dir / "shared"

    def load_manifest(self) -> dict[str, Any]:
        """Load scenario manifest with metadata and ground truth."""
        manifest_path = self.scenario_dir / "manifest.yml"

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Scenario manifest not found: {manifest_path}\n"
                f"Available scenarios: {self._list_scenarios()}"
            )

        with open(manifest_path) as f:
            return yaml.safe_load(f)

    def load_json(self, service: str, filename: str) -> Any:
        """Load JSON fixture from scenario or shared directory.

        Args:
            service: MCP service name (kubernetes, github, slack, observability)
            filename: Fixture filename (e.g., "pods.json")

        Returns:
            Parsed JSON data
        """
        # Try scenario-specific first
        scenario_path = self.scenario_dir / service / filename
        if scenario_path.exists():
            with open(scenario_path) as f:
                return json.load(f)

        # Fall back to shared
        shared_path = self.shared_dir / service / filename
        if shared_path.exists():
            with open(shared_path) as f:
                return json.load(f)

        raise FileNotFoundError(
            f"Fixture not found: {filename} in {service}\n"
            f"Tried:\n  - {scenario_path}\n  - {shared_path}"
        )

    def _list_scenarios(self) -> list[str]:
        """List available scenarios."""
        scenarios_dir = self.fixtures_dir / "scenarios"
        if not scenarios_dir.exists():
            return []
        return [d.name for d in scenarios_dir.iterdir() if d.is_dir()]


class BaseMockMCPServer:
    """Base class for mock MCP servers.

    Mock servers implement the same tool interface as real MCP servers
    but serve fixture data instead of making real API calls.
    """

    def __init__(self, fixture_loader: Optional[FixtureLoader] = None):
        """Initialize mock MCP server.

        Args:
            fixture_loader: FixtureLoader instance (creates default if not provided)
        """
        self.fixture_loader = fixture_loader or FixtureLoader()
        self.manifest = self.fixture_loader.load_manifest()

    def get_service_name(self) -> str:
        """Return the service name for this mock server (e.g., 'kubernetes')."""
        raise NotImplementedError("Subclasses must implement get_service_name()")

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools provided by this server.

        Returns:
            List of tool definitions compatible with MCP protocol
        """
        raise NotImplementedError("Subclasses must implement list_tools()")

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool with the given arguments.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool response with fixture data
        """
        raise NotImplementedError("Subclasses must implement call_tool()")

    def _load_fixture(self, filename: str) -> Any:
        """Load fixture for this service.

        Args:
            filename: Fixture filename

        Returns:
            Parsed fixture data
        """
        return self.fixture_loader.load_json(self.get_service_name(), filename)
