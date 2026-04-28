"""Test human-in-the-loop approval flow."""

import os
from datetime import datetime

# Set eval mode for auto-approval
os.environ["MODE"] = "eval"
os.environ["SCENARIO"] = "oom_after_deploy"

from agent.graph import create_incident_response_graph
from agent.state import AgentState


def test_approval_auto_approve_in_eval_mode():
    """Test that approval flow auto-approves in eval mode.

    This test verifies that:
    1. ApprovalHandler is called when recovery proposal is created
    2. In eval mode, allowed actions are auto-approved
    3. Approval metadata is stored correctly in state
    4. Workflow proceeds to execution after approval
    """
    print("\n" + "=" * 80)
    print("TESTING: Approval Flow - Auto-Approve in Eval Mode")
    print("=" * 80 + "\n")

    # Create graph
    graph = create_incident_response_graph()

    # Initialize state
    initial_state: AgentState = {
        "incident": None,
        "evidence": None,
        "hypotheses": [],
        "current_hypothesis_index": 0,
        "verification_results": [],
        "verification_round": 0,
        "recovery_proposal": None,
        "execution_result": None,
        "post_mortem": None,
        "status": "intake",
        "escalation_reason": None,
        "messages": [],
        "tool_calls": [],
        "started_at": datetime.now(),
        "completed_at": None
    }

    print("🚀 Starting workflow with approval flow test...\n")

    # Run the graph
    result = graph.invoke(initial_state)

    print("\n" + "=" * 80)
    print("APPROVAL FLOW RESULTS")
    print("=" * 80 + "\n")

    # Check recovery proposal
    recovery_proposal = result.get("recovery_proposal")
    assert recovery_proposal is not None, "Recovery proposal should be created"

    print(f"Recovery Proposal:")
    print(f"  Action Type: {recovery_proposal['action_type']}")
    print(f"  Description: {recovery_proposal['description']}")
    print(f"  Approval Status: {recovery_proposal['approval_status']}")
    print(f"  Approval Method: {recovery_proposal.get('approval_method')}")
    print(f"  Decided By: {recovery_proposal.get('decided_by')}")
    print(f"  Reasoning: {recovery_proposal.get('approval_reasoning')}")

    # Verify approval in eval mode
    assert recovery_proposal['approval_status'] == "approved", \
        f"Should be auto-approved in eval mode, got: {recovery_proposal['approval_status']}"

    assert recovery_proposal.get('approval_method') == "auto_approve", \
        f"Should use auto_approve method in eval mode, got: {recovery_proposal.get('approval_method')}"

    assert "eval mode" in recovery_proposal.get('approval_reasoning', "").lower(), \
        f"Reasoning should mention eval mode, got: {recovery_proposal.get('approval_reasoning')}"

    # Verify action type is in allowlist
    assert recovery_proposal['action_type'] in ["rollback", "scale", "restart", "config_change", "patch"], \
        f"Action type should be in allowlist, got: {recovery_proposal['action_type']}"

    # Verify execution happened (since approval was granted)
    execution_result = result.get("execution_result")
    assert execution_result is not None, "Execution should happen after approval"
    print(f"\nExecution Result:")
    print(f"  Success: {execution_result.get('success')}")
    print(f"  Output: {execution_result.get('output', 'N/A')[:100]}...")

    # Verify final status
    assert result.get("status") in ["completed", "escalated"], \
        f"Final status should be completed or escalated, got: {result.get('status')}"

    print("\n✅ Approval flow test passed!")
    print("   - Auto-approval worked in eval mode")
    print("   - Approval metadata stored correctly")
    print("   - Workflow proceeded to execution")

    return result


def test_approval_action_type_validation():
    """Test that invalid action types are rejected by allowlist."""
    print("\n" + "=" * 80)
    print("TESTING: Action Type Validation")
    print("=" * 80 + "\n")

    from agent.config.approval_config import validate_action_type, is_action_allowed

    # Test valid action types
    valid_actions = ["rollback", "scale", "restart", "config_change", "patch"]
    for action in valid_actions:
        is_valid, message = validate_action_type(action)
        print(f"✓ {action}: {is_valid} - {message}")
        assert is_valid, f"{action} should be valid"
        assert is_action_allowed(action), f"{action} should be allowed"

    # Test invalid action type
    invalid_action = "delete_production_database"
    is_valid, message = validate_action_type(invalid_action)
    print(f"\n✗ {invalid_action}: {is_valid} - {message}")
    assert not is_valid, f"{invalid_action} should be invalid"
    assert not is_action_allowed(invalid_action), f"{invalid_action} should not be allowed"

    print("\n✅ Action type validation test passed!")

    return True


def test_approval_metadata_completeness():
    """Test that all approval metadata fields are captured."""
    print("\n" + "=" * 80)
    print("TESTING: Approval Metadata Completeness")
    print("=" * 80 + "\n")

    from agent.utils.approval_handler import ApprovalHandler

    # Create approval handler
    handler = ApprovalHandler(mode="eval")

    # Request approval
    result = handler.request_approval(
        action_type="rollback",
        description="Rollback to previous version",
        expected_effect="Service should recover",
        blast_radius="Medium - affects all pods",
        commands=["kubectl rollout undo deployment/test-service"],
        dry_run_output=None
    )

    print("Approval Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Verify all required fields are present
    required_fields = ["status", "reasoning", "method"]
    for field in required_fields:
        assert field in result, f"Approval result should contain '{field}'"
        assert result[field] is not None, f"Approval result '{field}' should not be None"

    # Verify status is valid
    assert result["status"] in ["approved", "rejected", "pending", "timeout"], \
        f"Invalid status: {result['status']}"

    # Verify method is recorded
    assert result["method"] == "auto_approve", \
        f"Expected method='auto_approve' in eval mode, got: {result['method']}"

    print("\n✅ Metadata completeness test passed!")

    return result


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("RUNNING APPROVAL FLOW TEST SUITE")
    print("=" * 80)

    # Run all tests
    test_approval_action_type_validation()
    test_approval_metadata_completeness()
    test_approval_auto_approve_in_eval_mode()

    print("\n" + "=" * 80)
    print("ALL APPROVAL FLOW TESTS PASSED!")
    print("=" * 80 + "\n")
