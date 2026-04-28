"""LangGraph workflow for incident response agent."""

from typing import Literal
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.state import AgentState
from agent.nodes import (
    intake_node,
    evidence_gathering_node,
    diagnosis_node,
    verification_node,
    recovery_proposal_node,
    execution_node,
    post_mortem_node,
)


# ============================================================================
# Conditional Routing
# ============================================================================

def route_after_verification(state: AgentState) -> Literal["diagnosis", "recovery_proposal", "escalate"]:
    """Route based on verification result.

    - refuted → back to diagnosis (try next hypothesis or generate new ones)
    - confirmed → proceed to recovery_proposal
    - inconclusive after N rounds → escalate to human

    This is the KEY non-linear routing that enables backtracking.
    """
    verification_results = state.get("verification_results", [])

    if not verification_results:
        # No results yet, go to recovery (temporary)
        return "recovery_proposal"

    latest_result = verification_results[-1]

    # Check if we've done too many rounds
    max_rounds = 5
    if state.get("verification_round", 0) >= max_rounds:
        return "escalate"

    # Route based on verification status
    if latest_result["status"] == "confirmed":
        return "recovery_proposal"
    elif latest_result["status"] == "refuted":
        return "diagnosis"
    else:  # inconclusive
        # Try a few more times before escalating
        if state.get("verification_round", 0) >= 3:
            return "escalate"
        return "diagnosis"


def route_after_recovery_proposal(state: AgentState) -> Literal["execution", "post_mortem"]:
    """Route based on approval status.

    - approved → execution
    - rejected → post_mortem (log decision and close)
    """
    # TODO: Implement actual routing based on approval status
    # For now, always route to execution
    recovery_proposal = state.get("recovery_proposal")

    if not recovery_proposal:
        # No proposal yet, go to execution (temporary)
        return "execution"

    if recovery_proposal.get("approval_status") == "approved":
        return "execution"
    else:
        # Rejected or pending - for now go to post_mortem
        return "post_mortem"


def escalate_node(state: AgentState) -> AgentState:
    """Escalate to human when verification is inconclusive."""
    print("🚨 ESCALATION: Unable to confirm hypothesis, escalating to human...")
    return {
        **state,
        "status": "escalated",
        "escalation_reason": "Unable to verify hypothesis after multiple rounds",
        "messages": state.get("messages", []) + [{"role": "system", "content": "Escalated to human"}]
    }


# ============================================================================
# Graph Construction
# ============================================================================

def create_incident_response_graph(checkpointer=None):
    """Create the incident response LangGraph workflow.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     If None, uses in-memory (no persistence).

    Returns:
        Compiled StateGraph
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("evidence_gathering", evidence_gathering_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("verification", verification_node)
    workflow.add_node("recovery_proposal", recovery_proposal_node)
    workflow.add_node("execution", execution_node)
    workflow.add_node("post_mortem", post_mortem_node)
    workflow.add_node("escalate", escalate_node)

    # Set entry point
    workflow.set_entry_point("intake")

    # Add edges
    # Linear flow: intake → evidence_gathering → diagnosis
    workflow.add_edge("intake", "evidence_gathering")
    workflow.add_edge("evidence_gathering", "diagnosis")
    workflow.add_edge("diagnosis", "verification")

    # Conditional routing after verification (the key backtracking loop)
    workflow.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "diagnosis": "diagnosis",  # Loop back if refuted
            "recovery_proposal": "recovery_proposal",  # Continue if confirmed
            "escalate": "escalate"  # Escalate if inconclusive
        }
    )

    # Conditional routing after recovery proposal
    workflow.add_conditional_edges(
        "recovery_proposal",
        route_after_recovery_proposal,
        {
            "execution": "execution",
            "post_mortem": "post_mortem"
        }
    )

    # Final steps
    workflow.add_edge("execution", "post_mortem")
    workflow.add_edge("escalate", "post_mortem")
    workflow.add_edge("post_mortem", END)

    # Compile with optional checkpointer
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()


# ============================================================================
# Main execution (for testing)
# ============================================================================

if __name__ == "__main__":
    # Create graph without persistence for testing
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

    print("🚀 Starting incident response workflow (skeleton mode)...\n")

    # Run the graph
    result = graph.invoke(initial_state)

    print(f"\n✅ Workflow completed with status: {result.get('status')}")
    print(f"📊 Total messages: {len(result.get('messages', []))}")
    print(f"⏱️  Verification rounds: {result.get('verification_round', 0)}")
