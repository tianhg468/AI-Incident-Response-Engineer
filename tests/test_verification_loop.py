"""Test verification loop with backtracking."""

import os
from datetime import datetime

# Set eval mode
os.environ["MODE"] = "eval"
os.environ["SCENARIO"] = "oom_after_deploy"

from agent.graph import create_incident_response_graph
from agent.state import AgentState


def test_verification_loop_with_backtracking():
    """Test that the agent correctly backtracks when hypotheses are refuted.

    This test demonstrates the key differentiator: non-linear hypothesis testing
    with backtracking when verification fails.

    Expected flow:
    1. Generate multiple hypotheses
    2. Test first hypothesis
    3. If refuted → loop back to diagnosis → try next hypothesis
    4. If confirmed → proceed to recovery
    5. If inconclusive after N rounds → escalate
    """
    print("\n" + "=" * 80)
    print("TESTING: Verification Loop with Backtracking")
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

    print("🚀 Starting incident response workflow...\n")

    # Run the graph
    result = graph.invoke(initial_state)

    print("\n" + "=" * 80)
    print("VERIFICATION LOOP ANALYSIS")
    print("=" * 80 + "\n")

    # Analyze verification results
    verification_results = result.get("verification_results", [])
    hypotheses = result.get("hypotheses", [])

    print(f"Total Hypotheses Generated: {len(hypotheses)}")
    print(f"Total Verification Rounds: {len(verification_results)}")
    print(f"Final Status: {result.get('status')}\n")

    if len(verification_results) > 1:
        print("✅ BACKTRACKING DETECTED!")
        print("\nVerification sequence:")

        for i, vr in enumerate(verification_results):
            hypothesis_desc = vr['hypothesis']['description']
            status = vr['status']
            reasoning = vr.get('reasoning', 'N/A')[:100]

            print(f"\nRound {i + 1}:")
            print(f"  Hypothesis: {hypothesis_desc}")
            print(f"  Result: {status.upper()}")
            print(f"  Reasoning: {reasoning}...")

            if status == "refuted":
                print("  → Routing back to diagnosis for next hypothesis")
            elif status == "confirmed":
                print("  → Proceeding to recovery proposal")

    else:
        print("ℹ️  Single verification (first hypothesis confirmed)")

    # Check for escalation
    if result.get("status") == "escalated":
        print(f"\n🚨 ESCALATION: {result.get('escalation_reason')}")

    # Final assertions
    assert result is not None, "Graph should return a result"
    assert result.get("status") in ["completed", "escalated"], f"Unexpected status: {result.get('status')}"
    assert len(verification_results) > 0, "Should have at least one verification attempt"

    # If we got multiple verification rounds, verify the flow
    if len(verification_results) > 1:
        # Check that refuted hypotheses came before confirmed/inconclusive
        for i, vr in enumerate(verification_results[:-1]):
            if vr['status'] == "confirmed":
                # If a hypothesis was confirmed, it should be the last one
                assert i == len(verification_results) - 1, \
                    "Confirmed hypothesis should be the last verification"

    print("\n✅ Verification loop test completed successfully!\n")

    return result


def print_workflow_trace(result: dict):
    """Print a visual trace of the workflow.

    Args:
        result: Final state from graph execution
    """
    messages = result.get("messages", [])

    print("\n" + "=" * 80)
    print("WORKFLOW TRACE")
    print("=" * 80 + "\n")

    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        print(f"{i + 1}. {content}")


if __name__ == "__main__":
    result = test_verification_loop_with_backtracking()
    print_workflow_trace(result)
