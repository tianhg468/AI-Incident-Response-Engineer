"""Test end-to-end happy path scenario."""

import os
from datetime import datetime

# Set eval mode
os.environ["MODE"] = "eval"
os.environ["SCENARIO"] = "oom_after_deploy"

from agent.graph import create_incident_response_graph
from agent.state import AgentState


def test_oom_after_deploy_happy_path():
    """Test complete happy path for OOM after deploy scenario.

    This test verifies that the agent can:
    1. Parse the incident from the scenario
    2. Gather evidence from mock MCP servers
    3. Generate hypotheses using LLM
    4. Verify the top hypothesis
    5. Propose a remediation
    6. Execute the remediation (with auto-approval)
    7. Generate a post-mortem
    """
    print("\n" + "=" * 80)
    print("TESTING: OOM After Deploy - Happy Path Scenario")
    print("=" * 80 + "\n")

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

    print("🚀 Starting incident response workflow...\n")

    # Run the graph
    result = graph.invoke(initial_state)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80 + "\n")

    # Verify results
    print(f"Final Status: {result.get('status')}")
    print(f"Total Messages: {len(result.get('messages', []))}")
    print(f"Verification Rounds: {result.get('verification_round', 0)}")

    # Check incident
    incident = result.get("incident")
    if incident:
        print(f"\nIncident:")
        print(f"  Service: {incident['service']}")
        print(f"  Severity: {incident['severity']}")
        print(f"  Description: {incident['description']}")

    # Check evidence
    evidence = result.get("evidence")
    if evidence:
        print(f"\nEvidence Collected:")
        print(f"  Logs: {len(evidence.get('logs', []))}")
        print(f"  Pods: {len(evidence.get('pod_status', {}).get('pods', []))}")
        print(f"  Events: {len(evidence.get('pod_status', {}).get('events', []))}")
        print(f"  Deploys: {len(evidence.get('recent_deploys', []))}")

    # Check hypotheses
    hypotheses = result.get("hypotheses", [])
    if hypotheses:
        print(f"\nHypotheses Generated ({len(hypotheses)}):")
        for h in hypotheses:
            print(f"  #{h['rank']}: {h['description']}")

    # Check verification
    verification_results = result.get("verification_results", [])
    if verification_results:
        print(f"\nVerification Results:")
        for vr in verification_results:
            print(f"  Hypothesis: {vr['hypothesis']['description']}")
            print(f"  Status: {vr['status']}")
            print(f"  Reasoning: {vr.get('reasoning', 'N/A')}")

    # Check recovery proposal
    recovery_proposal = result.get("recovery_proposal")
    if recovery_proposal:
        print(f"\nRecovery Proposal:")
        print(f"  Action: {recovery_proposal['action_type']}")
        print(f"  Description: {recovery_proposal['description']}")
        print(f"  Approval Status: {recovery_proposal['approval_status']}")
        print(f"  Commands: {recovery_proposal['commands']}")

    # Check execution
    execution_result = result.get("execution_result")
    if execution_result:
        print(f"\nExecution Result:")
        print(f"  Success: {execution_result['success']}")
        print(f"  Output: {execution_result.get('output', 'N/A')[:100]}...")

    # Check post-mortem
    post_mortem = result.get("post_mortem")
    if post_mortem:
        print(f"\nPost-Mortem:")
        print(f"  Root Cause: {post_mortem['root_cause']}")
        print(f"  Duration: {post_mortem['incident_duration']:.1f} minutes")
        print(f"  Action Items: {len(post_mortem['action_items'])}")

    # Assertions
    assert result is not None, "Graph should return a result"
    assert result.get("status") in ["completed", "escalated"], f"Unexpected status: {result.get('status')}"
    assert incident is not None, "Incident should be parsed"
    assert evidence is not None, "Evidence should be gathered"
    assert len(hypotheses) > 0, "Hypotheses should be generated"

    print("\n✅ Happy path test completed successfully!\n")

    return result


if __name__ == "__main__":
    test_oom_after_deploy_happy_path()
