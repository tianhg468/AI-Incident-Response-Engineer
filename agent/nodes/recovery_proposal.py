"""Recovery proposal node: Draft remediation actions."""

from agent.state import AgentState, RecoveryProposal


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

    # Placeholder recovery proposal
    recovery_proposal: RecoveryProposal = {
        "action_type": "restart",
        "description": description,
        "expected_effect": "Service should recover to normal operation",
        "blast_radius": "Low - only affects specified pods",
        "dry_run_output": None,  # Would be populated in real implementation
        "commands": ["kubectl rollout restart deployment/placeholder-service"],
        "approval_status": "pending",
        "approval_reasoning": None
    }

    print(f"   Proposed action: {recovery_proposal['action_type']}")
    print(f"   Blast radius: {recovery_proposal['blast_radius']}")
    print("   ⏸️  Awaiting human approval...")

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
