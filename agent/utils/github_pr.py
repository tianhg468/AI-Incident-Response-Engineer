"""GitHub PR creation for GitOps workflow.

Instead of executing kubectl commands directly, the agent creates a PR
with the proposed changes for human review and approval in GitHub.
"""

import os
import json
import base64
import logging
import time
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)


class GitHubPRCreator:
    """Creates GitHub PRs with remediation changes using GitHub API."""

    def __init__(self, service: Optional[str] = None):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_org = os.getenv("GITHUB_ORG", "tianhg468")

        # Map services to their repositories
        # demo-app is a submodule in a separate repo
        if service == "demo-app":
            self.repo_name = "ai-incident-response-demo"
        else:
            self.repo_name = os.getenv("GITHUB_REPO", "agentic_ai")

        self.base_branch = "main"
        self.api_base = f"https://api.github.com/repos/{self.github_org}/{self.repo_name}"

        if not self.github_token:
            logger.warning("GITHUB_TOKEN not set - PR creation will fail")

        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def create_rollback_pr(
        self,
        service: str,
        target_revision: str,
        current_memory: str,
        target_memory: str,
        incident_summary: str
    ) -> dict:
        """Create a PR to rollback deployment configuration using GitHub API.

        Args:
            service: Service name (e.g., "demo-app")
            target_revision: Target revision number to rollback to
            current_memory: Current (bad) memory limit
            target_memory: Target (good) memory limit
            incident_summary: Summary of the incident

        Returns:
            PR creation result with PR URL
        """
        try:
            branch_name = f"ai-agent/rollback-{service}-{int(time.time())}"
            # Path within the service's repository (not including the service name)
            deployment_path = "k8s/deployment.yaml"

            logger.info(f"Creating PR to rollback {service} memory to {target_memory}")

            # 1. Get the base branch SHA
            base_sha = self._get_branch_sha(self.base_branch)
            logger.info(f"Base branch '{self.base_branch}' SHA: {base_sha}")

            # 2. Get current deployment.yaml content from GitHub
            file_content, file_sha = self._get_file_content(deployment_path, self.base_branch)
            logger.info(f"Retrieved {deployment_path} (SHA: {file_sha})")

            # 3. Update the deployment YAML with new memory limit
            updated_content = self._update_deployment_memory(file_content, target_memory)

            # 4. Create new branch from base
            self._create_branch_api(branch_name, base_sha)
            logger.info(f"Created branch: {branch_name}")

            # 5. Commit the updated file to new branch
            commit_message = f"🤖 Rollback {service} memory limit to {target_memory}\n\nAI Agent detected OOM incidents caused by low memory limit ({current_memory}).\nRolling back to revision {target_revision} with {target_memory} limit.\n\nIncident: {incident_summary}"

            self._update_file_api(
                path=deployment_path,
                content=updated_content,
                message=commit_message,
                branch=branch_name,
                sha=file_sha
            )
            logger.info(f"Committed changes to {branch_name}")

            # 6. Create the PR
            pr_url = self._create_pr_api(
                branch_name=branch_name,
                title=f"🤖 [AI Agent] Rollback {service} to fix OOM incidents",
                body=self._build_pr_body(service, target_revision, current_memory, target_memory, incident_summary)
            )

            logger.info(f"✅ PR created successfully: {pr_url}")

            return {
                "success": True,
                "pr_url": pr_url,
                "branch": branch_name
            }

        except Exception as e:
            logger.error(f"Failed to create PR: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _get_branch_sha(self, branch_name: str) -> str:
        """Get the SHA of a branch."""
        url = f"{self.api_base}/git/refs/heads/{branch_name}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()["object"]["sha"]

    def _get_file_content(self, path: str, branch: str) -> tuple[str, str]:
        """Get file content from GitHub.

        Returns:
            Tuple of (decoded_content, file_sha)
        """
        url = f"{self.api_base}/contents/{path}?ref={branch}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]

    def _update_deployment_memory(self, yaml_content: str, target_memory: str) -> str:
        """Update deployment YAML with new memory limit.

        Args:
            yaml_content: Original YAML content
            target_memory: Target memory limit (e.g., "256Mi")

        Returns:
            Updated YAML content as string
        """
        deployment = yaml.safe_load(yaml_content)

        # Update memory limits
        containers = deployment['spec']['template']['spec']['containers']
        for container in containers:
            if 'resources' in container and 'limits' in container['resources']:
                container['resources']['limits']['memory'] = target_memory
                # Also update requests to be consistent
                if target_memory == "256Mi":
                    container['resources']['requests']['memory'] = "128Mi"
                elif target_memory == "512Mi":
                    container['resources']['requests']['memory'] = "256Mi"
                elif target_memory == "128Mi":
                    container['resources']['requests']['memory'] = "64Mi"

        return yaml.dump(deployment, default_flow_style=False, sort_keys=False)

    def _create_branch_api(self, branch_name: str, base_sha: str):
        """Create a new branch via GitHub API."""
        url = f"{self.api_base}/git/refs"
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

    def _update_file_api(self, path: str, content: str, message: str, branch: str, sha: str):
        """Update a file via GitHub API."""
        url = f"{self.api_base}/contents/{path}"
        data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha,
            "branch": branch
        }
        response = requests.put(url, headers=self.headers, json=data)
        response.raise_for_status()

    def _create_pr_api(self, branch_name: str, title: str, body: str) -> str:
        """Create a PR via GitHub API.

        Args:
            branch_name: Source branch name
            title: PR title
            body: PR description

        Returns:
            PR URL
        """
        url = f"{self.api_base}/pulls"
        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": self.base_branch
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

        pr_data = response.json()
        return pr_data["html_url"]

    def _build_pr_body(
        self,
        service: str,
        target_revision: str,
        current_memory: str,
        target_memory: str,
        incident_summary: str
    ) -> str:
        """Build the PR description body."""
        return f"""## 🤖 AI Agent Automated Remediation

### Incident Summary
{incident_summary}

### Root Cause Analysis
The AI agent identified that the memory limit was reduced from **{target_memory}** to **{current_memory}** in a recent deployment, causing OOM (Out of Memory) incidents.

### Proposed Fix
Rollback the deployment configuration to **revision {target_revision}** with the following changes:

| Resource | Current (Bad) | Target (Good) |
|----------|---------------|---------------|
| Memory Limit | {current_memory} | {target_memory} |
| Memory Request | 64Mi | 128Mi |

### Evidence
- **Pods affected:** Multiple pods OOMKilled
- **Kubernetes events:** OOMKilling events detected
- **Deployment history:** Revision {target_revision} had stable memory limits

### Action Required
Please review the changes in the **Files changed** tab and:
1. ✅ **Approve** if the fix looks correct
2. 💬 **Comment** if you have questions or concerns
3. ❌ **Close** if this is not the right approach

Once approved and merged, GitHub Actions will automatically deploy this fix to the cluster.

---
🤖 *Generated by AI Incident Response Agent* | [View Agent Logs](#) | [Incident Timeline](#)
"""


def create_remediation_pr(
    service: str,
    action_type: str,
    evidence: dict,
    hypothesis: dict
) -> dict:
    """Simplified interface to create a remediation PR.

    Args:
        service: Service name
        action_type: Type of remediation (e.g., "rollback")
        evidence: Evidence collected by the agent
        hypothesis: Confirmed hypothesis

    Returns:
        PR creation result
    """
    pr_creator = GitHubPRCreator(service=service)

    # Extract details from evidence
    recent_deploys = evidence.get("recent_deploys", [])

    # Find target revision (good one) and current revision (bad one)
    target_revision = None
    target_memory = None
    current_memory = None

    for deploy in sorted(recent_deploys, key=lambda d: int(d.get("revision", "0"))):
        resources = deploy.get("resources", [])
        if resources:
            memory = resources[0].get("limits", {}).get("memory", "")
            if "256Mi" in memory or "512Mi" in memory:
                target_revision = deploy.get("revision")
                target_memory = memory
            elif "64Mi" in memory:
                current_memory = memory

    if not target_revision or not target_memory:
        return {
            "success": False,
            "error": "Could not identify target revision for rollback"
        }

    incident_summary = hypothesis.get("description", "OOM incidents detected")

    return pr_creator.create_rollback_pr(
        service=service,
        target_revision=target_revision,
        current_memory=current_memory or "64Mi",
        target_memory=target_memory,
        incident_summary=incident_summary
    )
