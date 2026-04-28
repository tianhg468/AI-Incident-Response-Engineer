"""Recovery proposal node: Draft remediation actions."""

import os
from agent.state import AgentState, RecoveryProposal
from agent.utils.approval_handler import ApprovalHandler


def recovery_proposal_node(state: AgentState) -> AgentState:
    """Draft a remediation proposal based on confirmed hypothesis.

    The proposal includes:
    - Action type (rollback, scale, restart, config_change, etc.)
    - Description and expected effect
    - Blast radius assessment
    - Dry-run output
    - Specific commands to execute

    Always pauses here for human approval.

    Args:
        state: Current agent state with verified hypothesis

    Returns:
        Updated state with recovery proposal awaiting approval
    """
    print("🛠️  RECOVERY PROPOSAL: Drafting remediation...")

    # TODO: Implement actual proposal generation
    # - Based on confirmed hypothesis and root cause
    # - Consider runbook recommendations
    # - Generate specific commands/API calls
    # - Run dry-run if possible
    # - Assess blast radius

    # Get the confirmed hypothesis
    verification_results = state.get("verification_results", [])
    confirmed_hypothesis = None

    for result in reversed(verification_results):
        if result["status"] == "confirmed":
            confirmed_hypothesis = result["hypothesis"]
            break

    if not confirmed_hypothesis:
        # Fallback if no confirmed hypothesis (shouldn't happen in normal flow)
        description = "Placeholder remediation action"
    else:
        description = f"Remediation for: {confirmed_hypothesis['description']}"

    # Get service name
    incident = state.get("incident", {})
    service = incident.get("service", "unknown-service")

    # Determine action based on hypothesis
    action_type = "rollback"  # Default for deployment-related issues
    expected_effect = "Service should recover to normal operation after rollback"
    blast_radius = f"Medium - affects all pods of {service}"
    commands = [f"kubectl rollout undo deployment/{service} -n default"]

    # Request approval via ApprovalHandler
    approval_handler = ApprovalHandler()
    approval_result = approval_handler.request_approval(
        action_type=action_type,
        description=description,
        expected_effect=expected_effect,
        blast_radius=blast_radius,
        commands=commands,
        dry_run_output=None  # Would be populated in real implementation
    )

    # Build recovery proposal with approval result
    recovery_proposal: RecoveryProposal = {
        "action_type": action_type,
        "description": description,
        "expected_effect": expected_effect,
        "blast_radius": blast_radius,
        "dry_run_output": None,
        "commands": commands,
        "approval_status": approval_result["status"],
        "approval_reasoning": approval_result.get("reasoning"),
        "decided_by": approval_result.get("decided_by"),
        "approval_method": approval_result.get("method")
    }

    print(f"   Proposed action: {recovery_proposal['action_type']}")
    print(f"   Blast radius: {recovery_proposal['blast_radius']}")

    if approval_result["status"] == "approved":
        print(f"   ✓ Approved ({approval_result.get('method', 'unknown')}): {approval_result.get('reasoning')}")
    elif approval_result["status"] == "rejected":
        print(f"   ✗ Rejected ({approval_result.get('method', 'unknown')}): {approval_result.get('reasoning')}")
    elif approval_result["status"] == "timeout":
        print(f"   ⏱️  Timeout: {approval_result.get('reasoning')}")
    else:
        print(f"   ⏸️  Awaiting approval...")

    return {
        **state,
        "recovery_proposal": recovery_proposal,
        "status": "awaiting_approval",
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": f"Recovery proposal drafted: {recovery_proposal['action_type']} - awaiting approval"
            }
        ]
    }
