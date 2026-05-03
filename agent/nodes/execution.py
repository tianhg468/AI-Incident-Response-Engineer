"""Execution node: Run approved remediation actions."""

import os
import subprocess
import logging
from datetime import datetime
from agent.state import AgentState, ExecutionResult
from agent.utils.github_pr import create_remediation_pr

logger = logging.getLogger(__name__)

# Determine execution mode: "gitops" or "direct"
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "gitops")


def execution_node(state: AgentState) -> AgentState:
    """Execute the approved remediation action.

    Only runs after explicit human approval.
    Execution is idempotent and supports dry-run mode.

    Args:
        state: Current agent state with approved recovery proposal

    Returns:
        Updated state with execution result
    """
    print("⚡ EXECUTION: Running remediation...")

    recovery_proposal = state.get("recovery_proposal")

    if not recovery_proposal:
        # No proposal to execute
        print("   ERROR: No recovery proposal found")
        execution_result: ExecutionResult = {
            "success": False,
            "output": "No recovery proposal found",
            "timestamp": datetime.now(),
            "rollback_available": False
        }
    elif recovery_proposal.get("approval_status") != "approved":
        # Proposal not approved
        print(f"   ERROR: Proposal not approved (status: {recovery_proposal.get('approval_status')})")
        execution_result: ExecutionResult = {
            "success": False,
            "output": f"Proposal not approved (status: {recovery_proposal.get('approval_status')})",
            "timestamp": datetime.now(),
            "rollback_available": False
        }
    else:
        # Execute the approved action based on execution mode
        action_type = recovery_proposal['action_type']
        print(f"   Executing: {action_type} (mode: {EXECUTION_MODE})")

        if EXECUTION_MODE == "gitops":
            # GitOps mode: Create a PR instead of executing directly
            execution_result = _execute_gitops(state, recovery_proposal)
        else:
            # Direct mode: Execute kubectl commands directly
            execution_result = _execute_direct(recovery_proposal)

    return {
        **state,
        "execution_result": execution_result,
        "status": "completed",
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": f"Execution {'succeeded' if execution_result['success'] else 'failed'}: {execution_result['output']}"
            }
        ]
    }


def _execute_gitops(state: AgentState, recovery_proposal: dict) -> ExecutionResult:
    """Execute remediation via GitOps (create GitHub PR).

    Args:
        state: Agent state with evidence and hypothesis
        recovery_proposal: Recovery proposal

    Returns:
        Execution result
    """
    print("   🔀 GitOps Mode: Creating GitHub PR for review...")

    try:
        # Extract information needed for PR
        incident = state.get("incident", {})
        service = incident.get("service", "unknown")
        evidence = state.get("evidence", {})

        # Find the confirmed hypothesis
        verification_results = state.get("verification_results", [])
        confirmed_hypothesis = None
        for result in verification_results:
            if result["status"] == "confirmed":
                confirmed_hypothesis = result["hypothesis"]
                break

        if not confirmed_hypothesis:
            return {
                "success": False,
                "output": "No confirmed hypothesis found for PR creation",
                "timestamp": datetime.now(),
                "rollback_available": False
            }

        # Create the PR
        pr_result = create_remediation_pr(
            service=service,
            action_type=recovery_proposal["action_type"],
            evidence=evidence,
            hypothesis=confirmed_hypothesis
        )

        if pr_result["success"]:
            pr_url = pr_result["pr_url"]
            print(f"   ✅ PR created successfully!")
            print(f"   🔗 Review PR at: {pr_url}")
            print(f"   📝 Once approved and merged, GitHub Actions will deploy the fix")

            # Post PR link to Slack
            try:
                from agent.utils.mcp_client import get_mcp_client
                mcp = get_mcp_client()
                mcp.call_tool("slack", "slack_post_message", {
                    "channel": "#incidents",
                    "text": f"🤖 AI Agent created remediation PR for {service}\n\n🔗 Review and approve: {pr_url}\n\nOnce merged, the fix will be automatically deployed."
                })
                print(f"   📨 Posted PR link to Slack")
            except Exception as e:
                print(f"   ⚠️  Could not post to Slack: {e}")

            return {
                "success": True,
                "output": f"PR created: {pr_url}\n\nAwaiting review and approval in GitHub.",
                "timestamp": datetime.now(),
                "rollback_available": False,  # Rollback is via Git revert
                "pr_url": pr_url
            }
        else:
            error = pr_result.get("error", "Unknown error")
            print(f"   ❌ PR creation failed: {error}")
            return {
                "success": False,
                "output": f"PR creation failed: {error}",
                "timestamp": datetime.now(),
                "rollback_available": False
            }

    except Exception as e:
        logger.error(f"GitOps execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "output": f"GitOps execution error: {str(e)}",
            "timestamp": datetime.now(),
            "rollback_available": False
        }


def _execute_direct(recovery_proposal: dict) -> ExecutionResult:
    """Execute remediation directly via kubectl commands.

    Args:
        recovery_proposal: Recovery proposal with commands

    Returns:
        Execution result
    """
    print("   ⚡ Direct Mode: Executing kubectl commands...")

    commands = recovery_proposal['commands']
    print(f"   Commands: {commands}")

    # Execute each command
    all_outputs = []
    all_success = True

    for cmd in commands:
        try:
            print(f"   Running: {cmd}")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                print(f"   ✓ Command succeeded")
                logger.info(f"Command succeeded: {cmd}")
                logger.debug(f"Output: {result.stdout}")
                all_outputs.append(f"[SUCCESS] {cmd}\n{result.stdout}")
            else:
                print(f"   ✗ Command failed with exit code {result.returncode}")
                print(f"   Error: {result.stderr[:200]}")
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Error: {result.stderr}")
                all_outputs.append(f"[FAILED] {cmd}\nExit code: {result.returncode}\n{result.stderr}")
                all_success = False

        except subprocess.TimeoutExpired:
            print(f"   ✗ Command timed out after 60s")
            logger.error(f"Command timed out: {cmd}")
            all_outputs.append(f"[TIMEOUT] {cmd}\nCommand timed out after 60 seconds")
            all_success = False
        except Exception as e:
            print(f"   ✗ Command failed with exception: {e}")
            logger.error(f"Command exception: {cmd}", exc_info=True)
            all_outputs.append(f"[ERROR] {cmd}\n{str(e)}")
            all_success = False

    if all_success:
        print("   ✅ Execution completed successfully")
    else:
        print("   ⚠️  Execution completed with errors")

    return {
        "success": all_success,
        "output": "\n\n".join(all_outputs),
        "timestamp": datetime.now(),
        "rollback_available": recovery_proposal['action_type'] == "rollback"
    }
