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

    # Analyze deployment history to find the last good revision
    evidence = state.get("evidence", {})
    recent_deploys = evidence.get("recent_deploys", [])

    # Determine action based on hypothesis and find target revision
    action_type = "rollback"
    expected_effect = "Service should recover to normal operation after rollback"
    blast_radius = f"Medium - affects all pods of {service}"

    target_revision = None
    if recent_deploys and len(recent_deploys) >= 2:
        # Find the revision with higher memory limits (the "good" one)
        for deploy in sorted(recent_deploys, key=lambda d: int(d.get("revision", "0"))):
            resources = deploy.get("resources", [])
            if resources:
                memory_limit = resources[0].get("limits", {}).get("memory", "")
                # If memory limit is >= 128Mi (and not the current low limit), consider it good
                if any(size in memory_limit for size in ["128Mi", "256Mi", "512Mi", "1Gi", "2Gi"]):
                    target_revision = deploy.get("revision")
                    print(f"   Found good revision to rollback to: {target_revision} (memory: {memory_limit})")

    if target_revision:
        commands = [f"kubectl rollout undo deployment/{service} --to-revision={target_revision} -n default"]
        expected_effect = f"Rollback to revision {target_revision} with higher memory limits"
    else:
        # Fallback to generic undo
        commands = [f"kubectl rollout undo deployment/{service} -n default"]
        print("   WARNING: Could not identify specific good revision, using generic rollback")

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
    elif approval_result["status"] == "rejected_with_feedback":
        feedback = approval_result.get("feedback", approval_result.get("reasoning", ""))
        print(f"   🔄 Rejected with feedback ({approval_result.get('method', 'unknown')}): {feedback}")
        print(f"   ↩️  Looping back to diagnosis with this feedback...")
    elif approval_result["status"] == "rejected":
        print(f"   ✗ Rejected ({approval_result.get('method', 'unknown')}): {approval_result.get('reasoning')}")
    elif approval_result["status"] == "timeout":
        print(f"   ⏱️  Timeout: {approval_result.get('reasoning')}")
    else:
        print(f"   ⏸️  Awaiting approval...")

    # Store human feedback if rejected with feedback
    human_feedback = None
    if approval_result["status"] == "rejected_with_feedback":
        human_feedback = approval_result.get("feedback", approval_result.get("reasoning", "Try a different approach"))

    return {
        **state,
        "recovery_proposal": recovery_proposal,
        "status": "awaiting_approval",
        "human_feedback": human_feedback,
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": f"Recovery proposal drafted: {recovery_proposal['action_type']} - awaiting approval"
            }
        ]
    }
