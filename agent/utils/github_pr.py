"""GitHub PR creation for GitOps workflow.

Instead of executing kubectl commands directly, the agent creates a PR
with the proposed changes for human review and approval in GitHub.
"""

import os
import json
import subprocess
import logging
from typing import Optional
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class GitHubPRCreator:
    """Creates GitHub PRs with remediation changes."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_org = os.getenv("GITHUB_ORG", "tianhg468")
        self.repo_name = os.getenv("GITHUB_REPO", "agentic_ai")
        self.repo_path = Path(__file__).parent.parent.parent  # Root of repo

        if not self.github_token:
            logger.warning("GITHUB_TOKEN not set - PR creation will fail")

    def create_rollback_pr(
        self,
        service: str,
        target_revision: str,
        current_memory: str,
        target_memory: str,
        incident_summary: str
    ) -> dict:
        """Create a PR to rollback deployment configuration.

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
            # 1. Create a new branch
            branch_name = f"ai-agent/rollback-{service}-{int(time.time())}"
            self._create_branch(branch_name)

            # 2. Make the changes
            deployment_file = self.repo_path / "demo-app" / "k8s" / "deployment.yaml"
            self._update_deployment_yaml(deployment_file, target_memory)

            # 3. Commit the changes
            commit_message = f"🤖 Rollback {service} memory limit to {target_memory}\n\nAI Agent detected OOM incidents caused by low memory limit ({current_memory}).\nRolling back to revision {target_revision} with {target_memory} limit.\n\nIncident: {incident_summary}"
            self._commit_changes(deployment_file, commit_message)

            # 4. Push the branch
            self._push_branch(branch_name)

            # 5. Create the PR
            pr_url = self._create_pr(
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

    def _create_branch(self, branch_name: str):
        """Create a new Git branch."""
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path, check=True)
        logger.info(f"Created branch: {branch_name}")

    def _update_deployment_yaml(self, deployment_file: Path, target_memory: str):
        """Update the deployment YAML file with new memory limit."""
        import yaml

        with open(deployment_file, 'r') as f:
            deployment = yaml.safe_load(f)

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

        with open(deployment_file, 'w') as f:
            yaml.dump(deployment, f, default_flow_style=False)

        logger.info(f"Updated {deployment_file} with memory limit: {target_memory}")

    def _commit_changes(self, file_path: Path, commit_message: str):
        """Commit changes to Git."""
        subprocess.run(["git", "add", str(file_path)], cwd=self.repo_path, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=self.repo_path, check=True)
        logger.info(f"Committed changes: {commit_message.split(chr(10))[0]}")

    def _push_branch(self, branch_name: str):
        """Push branch to GitHub."""
        subprocess.run(["git", "push", "origin", branch_name], cwd=self.repo_path, check=True)
        logger.info(f"Pushed branch: {branch_name}")

    def _create_pr(self, branch_name: str, title: str, body: str) -> str:
        """Create a PR on GitHub.

        Args:
            branch_name: Source branch name
            title: PR title
            body: PR description

        Returns:
            PR URL
        """
        url = f"https://api.github.com/repos/{self.github_org}/{self.repo_name}/pulls"

        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": "main"
        }

        response = requests.post(url, headers=headers, json=data)
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


import time  # For timestamp in branch name


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
    pr_creator = GitHubPRCreator()

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
