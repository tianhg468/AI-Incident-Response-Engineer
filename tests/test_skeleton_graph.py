"""Test the skeleton graph execution."""

from datetime import datetime
from agent.graph import create_incident_response_graph
from agent.state import AgentState


def test_skeleton_graph_executes():
    """Test that the skeleton graph can execute end-to-end."""
    # Create graph without persistence
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

    # Run the graph
    result = graph.invoke(initial_state)

    # Verify the graph completed
    assert result is not None
    assert "status" in result
    assert "messages" in result

    # Should have at least one message from each node
    # (intake, evidence_gathering, diagnosis, verification, recovery_proposal, execution, post_mortem)
    assert len(result["messages"]) >= 7

    # Should have completed or escalated
    assert result["status"] in ["completed", "escalated"]

    print("✅ Skeleton graph test passed!")


if __name__ == "__main__":
    test_skeleton_graph_executes()
