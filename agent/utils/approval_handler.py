"""Approval handler for human-in-the-loop safety."""

import os
import logging
import time
from typing import Optional, Literal

from agent.config.approval_config import (
    is_action_allowed,
    validate_action_type,
    requires_approval
)
from agent.utils.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class ApprovalHandler:
    """Handles approval requests for remediation actions.

    Supports:
    - Slack approval (primary, via MCP)
    - CLI approval (fallback)
    - Auto-approval in eval mode
    - Action type validation against allowlist
    """

    def __init__(self, mode: Optional[Literal["eval", "live"]] = None):
        """Initialize approval handler.

        Args:
            mode: Running mode (eval or live). Defaults to MODE env var.
        """
        self.mode = mode or os.getenv("MODE", "eval")
        self.mcp = MCPClient()
        logger.info(f"Approval handler initialized (mode: {self.mode})")

    def request_approval(
        self,
        action_type: str,
        description: str,
        expected_effect: str,
        blast_radius: str,
        commands: list[str],
        dry_run_output: Optional[str] = None
    ) -> dict:
        """Request approval for a remediation action.

        Args:
            action_type: Type of action (rollback, scale, etc.)
            description: Human-readable description
            expected_effect: What will happen
            blast_radius: Impact assessment
            commands: Commands to execute
            dry_run_output: Optional dry-run output

        Returns:
            Approval result dict with status and reasoning
        """
        logger.info(f"Requesting approval for action: {action_type}")

        # Validate action type against allowlist
        is_valid, message = validate_action_type(action_type)
        if not is_valid:
            logger.warning(f"Action type not allowed: {message}")
            return {
                "status": "rejected",
                "reasoning": message,
                "method": "allowlist_validation"
            }

        # Check if approval is required
        needs_approval = requires_approval(action_type, self.mode)

        if not needs_approval:
            # Auto-approve
            logger.info("Auto-approving action (eval mode)")
            return {
                "status": "approved",
                "reasoning": f"Auto-approved in {self.mode} mode",
                "method": "auto_approve"
            }

        # Live mode - request human approval
        if self.mode == "live":
            return self._request_live_approval(
                action_type=action_type,
                description=description,
                expected_effect=expected_effect,
                blast_radius=blast_radius,
                commands=commands,
                dry_run_output=dry_run_output
            )
        else:
            # Eval mode but action requires approval
            # This shouldn't normally happen with our config
            logger.warning("Action requires approval in eval mode (unusual)")
            return {
                "status": "pending",
                "reasoning": "Action requires manual approval even in eval mode",
                "method": "eval_manual"
            }

    def _request_live_approval(
        self,
        action_type: str,
        description: str,
        expected_effect: str,
        blast_radius: str,
        commands: list[str],
        dry_run_output: Optional[str] = None
    ) -> dict:
        """Request approval in live mode.

        Primary: Slack interactive buttons
        Fallback: CLI prompt

        Args:
            action_type: Action type
            description: Description
            expected_effect: Expected effect
            blast_radius: Blast radius
            commands: Commands
            dry_run_output: Dry-run output

        Returns:
            Approval result
        """
        # Format approval request
        title = f"Approval Required: {action_type}"
        details = f"""**Action:** {action_type}
**Description:** {description}

**Expected Effect:** {expected_effect}
**Blast Radius:** {blast_radius}

**Commands:**
```
{chr(10).join(commands)}
```
"""

        if dry_run_output:
            details += f"\n**Dry-Run Output:**\n```\n{dry_run_output}\n```"

        # Try Slack approval first
        try:
            print("   📲 Attempting Slack approval...")
            logger.info("Attempting Slack approval...")
            slack_result = self._request_slack_approval(title, details, {
                "action_type": action_type,
                "commands": commands,
                "blast_radius": blast_radius
            })

            print(f"   [DEBUG] Slack approval result: {slack_result}")

            # Check for success (either "ok" or "success" field)
            if slack_result.get("ok") or slack_result.get("success"):
                approval_id = slack_result.get("approval_id")
                if approval_id:
                    logger.info(f"Slack approval request posted: {approval_id}")
                    print(f"   ✓ Slack approval request posted: {approval_id}")
                    print(f"   ⏳ Waiting for response in Slack #incidents channel...")

                    # Poll for approval
                    return self._wait_for_slack_approval(approval_id, timeout=300)
                else:
                    print(f"   ✗ No approval_id in response: {slack_result}")
            else:
                print(f"   ✗ Slack approval failed: {slack_result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.warning(f"Slack approval failed: {e}")
            print(f"   ✗ Slack approval error: {e}")
            import traceback
            traceback.print_exc()

        # Fallback to CLI
        print("   ⤵️  Falling back to CLI approval...")
        logger.info("Falling back to CLI approval...")
        return self._request_cli_approval(
            action_type=action_type,
            description=description,
            expected_effect=expected_effect,
            blast_radius=blast_radius,
            commands=commands
        )

    def _request_slack_approval(
        self,
        title: str,
        description: str,
        action_details: dict
    ) -> dict:
        """Post approval request to Slack.

        Args:
            title: Approval title
            description: Full description
            action_details: Action metadata

        Returns:
            Slack API response
        """
        return self.mcp.post_approval_request(
            title=title,
            description=description,
            action_details=action_details,
            channel="#incidents"
        )

    def _wait_for_slack_approval(
        self,
        approval_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> dict:
        """Wait for Slack approval response.

        Args:
            approval_id: Approval request ID
            timeout: Max wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Approval result
        """
        import time
        from webhook.approval_manager import get_approval_manager

        elapsed = 0
        logger.info(f"Waiting for approval (timeout: {timeout}s)...")
        approval_manager = get_approval_manager()

        while elapsed < timeout:
            # Check approval status from the approval manager
            status_dict = approval_manager.get_status(approval_id)

            if status_dict.get("status") == "not_found":
                logger.error(f"Approval not found: {approval_id}")
                break

            approval_status = status_dict.get("status")

            if approval_status == "approved":
                logger.info("✓ Approval granted!")
                print(f"   ✓ Approved by {status_dict.get('approved_by')} via Slack!")
                return {
                    "status": "approved",
                    "reasoning": f"Approved via Slack by {status_dict.get('approved_by')}",
                    "decided_by": status_dict.get("approved_by"),
                    "method": "slack"
                }

            elif approval_status == "rejected":
                logger.info("✗ Approval rejected")
                print(f"   ✗ Rejected by {status_dict.get('approved_by')} via Slack")
                return {
                    "status": "rejected",
                    "reasoning": f"Rejected via Slack by {status_dict.get('approved_by')}",
                    "decided_by": status_dict.get("approved_by"),
                    "method": "slack"
                }

            elif approval_status == "rejected_with_feedback":
                logger.info("🔄 Approval rejected with feedback")
                print(f"   🔄 Rejected with feedback by {status_dict.get('approved_by')} via Slack")
                feedback = status_dict.get("feedback", "")
                print(f"   📝 Feedback: {feedback}")
                return {
                    "status": "rejected_with_feedback",
                    "reasoning": f"Rejected with feedback: {feedback}",
                    "feedback": feedback,
                    "decided_by": status_dict.get("approved_by"),
                    "method": "slack"
                }

            # Still pending, wait and retry
            time.sleep(poll_interval)
            elapsed += poll_interval
            logger.debug(f"Still waiting... ({elapsed}s / {timeout}s)")

        # Timeout
        logger.warning(f"Approval request timed out after {timeout}s")
        return {
            "status": "timeout",
            "reasoning": f"No response received within {timeout} seconds",
            "method": "slack"
        }

    def _request_cli_approval(
        self,
        action_type: str,
        description: str,
        expected_effect: str,
        blast_radius: str,
        commands: list[str]
    ) -> dict:
        """Request approval via CLI prompt.

        Args:
            action_type: Action type
            description: Description
            expected_effect: Expected effect
            blast_radius: Blast radius
            commands: Commands

        Returns:
            Approval result
        """
        print("\n" + "=" * 80)
        print("APPROVAL REQUIRED")
        print("=" * 80)
        print(f"\nAction Type: {action_type}")
        print(f"Description: {description}")
        print(f"\nExpected Effect: {expected_effect}")
        print(f"Blast Radius: {blast_radius}")
        print(f"\nCommands:")
        for cmd in commands:
            print(f"  $ {cmd}")
        print("\n" + "=" * 80)

        # Prompt for approval
        response = input("\nApprove this action? [yes/no/feedback]: ").strip().lower()

        if response in ["yes", "y"]:
            reasoning = input("Reasoning (optional): ").strip()
            return {
                "status": "approved",
                "reasoning": reasoning or "Approved via CLI",
                "decided_by": "cli_user",
                "method": "cli"
            }
        elif response in ["feedback", "f"]:
            feedback = input("Provide feedback on why this won't work and what to try instead: ").strip()
            return {
                "status": "rejected_with_feedback",
                "reasoning": "Rejected with feedback - requesting alternative approach",
                "feedback": feedback or "Try a different approach",
                "decided_by": "cli_user",
                "method": "cli"
            }
        else:
            reasoning = input("Reason for rejection (optional): ").strip()
            return {
                "status": "rejected",
                "reasoning": reasoning or "Rejected via CLI",
                "decided_by": "cli_user",
                "method": "cli"
            }
