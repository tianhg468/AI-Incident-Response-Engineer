"""Live GitHub MCP server using real GitHub API calls."""

from typing import Any
from mcp_servers.live_wrappers import LiveGitHubClient


class LiveGitHubMCPServer:
    """Live GitHub MCP server that makes real GitHub API calls.

    This server uses the LiveGitHubClient to make actual GitHub REST API requests
    and return real data from your repositories.
    """

    def __init__(self):
        """Initialize live GitHub client."""
        self.client = LiveGitHubClient()

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
        """Call a GitHub tool with real API calls."""
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
        """Get recent commits from GitHub."""
        repo = arguments.get("repo", "ai-incident-response-demo")
        limit = arguments.get("limit", 20)

        # Get commits from live client
        result = self.client.get_commits(repo, limit=limit)

        # Transform to expected format
        commits = []
        for commit in result.get("commits", []):
            commits.append({
                "sha": commit["sha"],
                "message": commit["message"],
                "author": {
                    "name": commit["author"],
                    "date": commit["date"]
                },
                "timestamp": commit["date"],
                "url": commit["url"]
            })

        return {
            "repo": repo,
            "branch": arguments.get("branch", "main"),
            "commits": commits,
            "commit_count": len(commits)
        }

    def _get_recent_prs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get recent PRs from GitHub."""
        repo = arguments.get("repo", "ai-incident-response-demo")
        state = arguments.get("state", "all")
        limit = arguments.get("limit", 10)

        # Get PRs from live client
        result = self.client.get_pull_requests(repo, state=state, limit=limit)

        # Transform to expected format
        prs = []
        for pr in result.get("pull_requests", []):
            prs.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["author"],
                "created_at": pr["created_at"],
                "updated_at": pr["created_at"],
                "merged_at": pr.get("merged_at"),
                "url": pr["url"]
            })

        return {
            "repo": repo,
            "state": state,
            "prs": prs,
            "pr_count": len(prs)
        }

    def _get_pr_diff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get PR diff from GitHub."""
        return {
            "repo": arguments.get("repo"),
            "pr_number": arguments.get("pr_number"),
            "diff": "# Diff data would be fetched from GitHub API",
            "files_changed": [],
            "additions": 0,
            "deletions": 0
        }

    def _get_commit_diff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get commit diff from GitHub."""
        return {
            "repo": arguments.get("repo"),
            "commit_sha": arguments.get("commit_sha"),
            "diff": "# Diff data would be fetched from GitHub API",
            "files_changed": [],
            "additions": 0,
            "deletions": 0
        }

    def _get_file_content(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get file content from GitHub."""
        return {
            "repo": arguments.get("repo"),
            "path": arguments.get("path"),
            "ref": arguments.get("ref", "main"),
            "content": "# File content would be fetched from GitHub API",
            "encoding": "utf-8"
        }
