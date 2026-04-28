"""Evidence gathering node: Collect data from observability and infrastructure tools."""

from agent.state import AgentState, Evidence


def evidence_gathering_node(state: AgentState) -> AgentState:
    """Gather evidence from MCP servers in parallel.

    Collects:
    - Logs from affected pods
    - Relevant metrics (CPU, memory, latency, errors)
    - Recent deployments
    - Pod status and events
    - GitHub activity (commits, PRs)
    - Relevant runbooks
    - Similar past incidents

    Args:
        state: Current agent state with incident information

    Returns:
        Updated state with Evidence object
    """
    print("🔍 EVIDENCE GATHERING: Collecting data from MCP servers...")

    # TODO: Implement parallel MCP tool calls
    # - Kubernetes MCP: logs, pod status, events
    # - GitHub MCP: recent commits/PRs
    # - Observability MCP: metrics
    # - Custom Runbook Correlator MCP: runbooks, past incidents

    evidence: Evidence = {
        "logs": [],
        "metrics": {},
        "recent_deploys": [],
        "pod_status": {},
        "github_activity": [],
        "runbooks": [],
        "past_incidents": []
    }

    return {
        **state,
        "evidence": evidence,
        "status": "diagnosing",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": "Evidence gathering completed"}
        ]
    }
