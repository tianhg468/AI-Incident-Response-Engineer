"""Diagnosis node: Generate hypotheses about the root cause."""

from agent.state import AgentState, Hypothesis


def diagnosis_node(state: AgentState) -> AgentState:
    """Generate 2-3 ranked hypotheses about the incident root cause.

    Each hypothesis includes:
    - Rank (priority)
    - Description of what went wrong
    - Falsification criterion (explicit test to disprove it)
    - Supporting evidence
    - Specific verification checks to run

    Args:
        state: Current agent state with incident and evidence

    Returns:
        Updated state with generated hypotheses
    """
    print("🧠 DIAGNOSIS: Generating hypotheses...")

    # TODO: Use LLM to analyze evidence and generate hypotheses
    # Consider:
    # - Recent deploys (correlation with incident timing)
    # - Similar past incidents
    # - Runbook guidance
    # - Anomalies in metrics and logs

    # Get current hypothesis index to determine if we're generating new ones
    # or selecting the next from existing list
    current_index = state.get("current_hypothesis_index", 0)
    existing_hypotheses = state.get("hypotheses", [])

    # If we have existing hypotheses and haven't exhausted them, move to next
    if existing_hypotheses and current_index < len(existing_hypotheses):
        next_index = current_index + 1
        print(f"   Moving to hypothesis {next_index}/{len(existing_hypotheses)}")
        return {
            **state,
            "current_hypothesis_index": next_index,
            "status": "verifying",
            "messages": state.get("messages", []) + [
                {"role": "system", "content": f"Moved to next hypothesis (#{next_index})"}
            ]
        }

    # Otherwise, generate new hypotheses
    # Placeholder hypotheses for now
    new_hypotheses: list[Hypothesis] = [
        {
            "rank": 1,
            "description": "Placeholder hypothesis 1",
            "falsification_criterion": "If X is true, this is wrong",
            "supporting_evidence": ["evidence_ref_1"],
            "verification_checks": ["check_1", "check_2"]
        },
        {
            "rank": 2,
            "description": "Placeholder hypothesis 2",
            "falsification_criterion": "If Y is true, this is wrong",
            "supporting_evidence": ["evidence_ref_2"],
            "verification_checks": ["check_3"]
        }
    ]

    return {
        **state,
        "hypotheses": state.get("hypotheses", []) + new_hypotheses,
        "current_hypothesis_index": 0,  # Reset to first hypothesis
        "status": "verifying",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"Generated {len(new_hypotheses)} new hypotheses"}
        ]
    }
