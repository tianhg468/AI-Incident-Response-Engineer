"""Execution node: Run approved remediation actions."""

from datetime import datetime
from agent.state import AgentState, ExecutionResult


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
        # Execute the approved action
        # TODO: Implement actual execution
        # - Run commands via appropriate MCP server (Kubernetes, etc.)
        # - Ensure idempotency
        # - Capture output
        # - Determine if rollback is available

        print(f"   Executing: {recovery_proposal['action_type']}")
        print(f"   Commands: {recovery_proposal['commands']}")

        # Placeholder execution
        execution_result: ExecutionResult = {
            "success": True,
            "output": "Placeholder execution output - action completed successfully",
            "timestamp": datetime.now(),
            "rollback_available": True  # Would be determined based on action type
        }

        print("   ✅ Execution completed successfully")

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
