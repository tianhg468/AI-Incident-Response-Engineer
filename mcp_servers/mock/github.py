"""Mock GitHub MCP server."""

from typing import Any, Optional
from datetime import datetime

from mcp_servers.mock.base import BaseMockMCPServer, FixtureLoader


class MockGitHubMCPServer(BaseMockMCPServer):
    """Mock GitHub MCP server serving fixture data.

    Tools provided:
    - get_recent_commits: Get recent commits to a repository
    - get_recent_prs: Get recent pull requests
    - get_pr_diff: Get diff for a specific PR
    - get_commit_diff: Get diff for a specific commit
    - get_deploy_timeline: Get deployment timeline correlation
    """

    def get_service_name(self) -> str:
        return "github"

    def list_tools(self) -> list[dict[str, Any]]:
        """List available GitHub tools."""
        return [
            {
                "name": "github_get_recent_commits",
                "description": "Get recent commits to a repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository name (org/repo format)"
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name",
                            "default": "main"
                        },
                        "since": {
                            "type": "string",
                            "description": "Only commits after this timestamp (ISO 8601)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of commits to return",
                            "default": 20
                        }
                    }
                }
            },
            {
                "name": "github_get_recent_prs",
                "description": "Get recent pull requests",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository name (org/repo format)"
                        },
                        "state": {
                            "type": "string",
                            "enum": ["open", "closed", "merged", "all"],
                            "description": "PR state filter",
                            "default": "all"
                        },
                        "since": {
                            "type": "string",
                            "description": "Only PRs updated after this timestamp"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of PRs to return",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "github_get_pr_diff",
                "description": "Get the diff for a specific pull request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository name (org/repo format)"
                        },
                        "pr_number": {
                            "type": "integer",
                            "description": "Pull request number"
                        }
                    },
                    "required": ["pr_number"]
                }
            },
            {
                "name": "github_get_commit_diff",
                "description": "Get the diff for a specific commit",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository name (org/repo format)"
                        },
                        "commit_sha": {
                            "type": "string",
                            "description": "Commit SHA"
                        }
                    },
                    "required": ["commit_sha"]
                }
            },
            {
                "name": "github_get_file_content",
                "description": "Get content of a file at a specific commit",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository name (org/repo format)"
                        },
                        "path": {
                            "type": "string",
                            "description": "File path in repository"
                        },
                        "ref": {
                            "type": "string",
                            "description": "Git ref (branch, tag, or commit SHA)",
                            "default": "main"
                        }
                    },
                    "required": ["path"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a GitHub tool with fixture data."""
        if tool_name == "github_get_recent_commits":
            return self._get_recent_commits(arguments)
        elif tool_name == "github_get_recent_prs":
            return self._get_recent_prs(arguments)
        elif tool_name == "github_get_pr_diff":
            return self._get_pr_diff(arguments)
        elif tool_name == "github_get_commit_diff":
            return self._get_commit_diff(arguments)
        elif tool_name == "github_get_file_content":
            return self._get_file_content(arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.list_tools()]
            }

    def _get_recent_commits(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get recent commits from fixtures."""
        commits = self._load_fixture("commits.json")

        # Apply filters
        limit = arguments.get("limit", 20)
        branch = arguments.get("branch", "main")
        since = arguments.get("since")

        # Filter by branch if needed
        if branch and branch != "main":
            commits = [c for c in commits if c.get("branch") == branch]

        # Filter by timestamp if needed
        if since:
            commits = [c for c in commits if c.get("timestamp", "") > since]

        # Apply limit
        commits = commits[:limit]

        return {
            "repo": arguments.get("repo", "unknown/repo"),
            "branch": branch,
            "commits": commits,
            "commit_count": len(commits)
        }

    def _get_recent_prs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get recent PRs from fixtures."""
        prs = self._load_fixture("prs.json")

        # Apply filters
        state = arguments.get("state", "all")
        limit = arguments.get("limit", 10)
        since = arguments.get("since")

        # Filter by state
        if state != "all":
            prs = [pr for pr in prs if pr.get("state") == state]

        # Filter by timestamp if needed
        if since:
            prs = [pr for pr in prs if pr.get("updated_at", "") > since]

        # Apply limit
        prs = prs[:limit]

        return {
            "repo": arguments.get("repo", "unknown/repo"),
            "state": state,
            "prs": prs,
            "pr_count": len(prs)
        }

    def _get_pr_diff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get PR diff from fixtures."""
        diffs = self._load_fixture("diffs.json")
        pr_number = arguments.get("pr_number")

        # Find diff for this PR
        pr_diff = None
        for diff in diffs:
            if diff.get("type") == "pr" and diff.get("number") == pr_number:
                pr_diff = diff
                break

        if not pr_diff:
            return {
                "error": f"No diff found for PR #{pr_number}",
                "pr_number": pr_number
            }

        return {
            "repo": arguments.get("repo", "unknown/repo"),
            "pr_number": pr_number,
            "diff": pr_diff.get("diff", ""),
            "files_changed": pr_diff.get("files_changed", []),
            "additions": pr_diff.get("additions", 0),
            "deletions": pr_diff.get("deletions", 0)
        }

    def _get_commit_diff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get commit diff from fixtures."""
        diffs = self._load_fixture("diffs.json")
        commit_sha = arguments.get("commit_sha")

        # Find diff for this commit
        commit_diff = None
        for diff in diffs:
            if diff.get("type") == "commit" and diff.get("sha") == commit_sha:
                commit_diff = diff
                break

        if not commit_diff:
            return {
                "error": f"No diff found for commit {commit_sha}",
                "commit_sha": commit_sha
            }

        return {
            "repo": arguments.get("repo", "unknown/repo"),
            "commit_sha": commit_sha,
            "diff": commit_diff.get("diff", ""),
            "files_changed": commit_diff.get("files_changed", []),
            "additions": commit_diff.get("additions", 0),
            "deletions": commit_diff.get("deletions", 0)
        }

    def _get_file_content(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get file content from fixtures."""
        # For mock, we could store file contents in fixtures
        # For now, return a simple response
        return {
            "repo": arguments.get("repo", "unknown/repo"),
            "path": arguments.get("path"),
            "ref": arguments.get("ref", "main"),
            "content": "# Mock file content\n# In eval mode, this would come from fixtures",
            "encoding": "utf-8"
        }
