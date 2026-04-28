"""Evidence gathering node: Collect data from observability and infrastructure tools."""

import logging
from agent.state import AgentState, Evidence
from agent.utils.mcp_client import MCPClient

logger = logging.getLogger(__name__)


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

    incident = state.get("incident")
    if not incident:
        logger.warning("No incident data in state")
        return {
            **state,
            "status": "diagnosing",
            "messages": state.get("messages", []) + [
                {"role": "system", "content": "Evidence gathering skipped - no incident data"}
            ]
        }

    service = incident["service"]
    namespace = "default"  # Could be extracted from incident

    # Initialize MCP client
    mcp = MCPClient()

    # Gather evidence from multiple sources
    print(f"  📦 Gathering evidence for service: {service}")

    # 1. Kubernetes pod status
    print("  ├─ Getting pod status...")
    pod_status_result = mcp.get_pod_status(
        namespace=namespace,
        label_selector=f"app={service}"
    )
    pod_status = pod_status_result.get("pods", [])

    # 2. Kubernetes events
    print("  ├─ Getting Kubernetes events...")
    events_result = mcp.get_events(namespace=namespace)
    events = events_result.get("events", [])

    # 3. Pod logs (from affected pods)
    print("  ├─ Getting pod logs...")
    logs = []
    affected_pods = incident.get("affected_pods", [])
    for pod_name in affected_pods[:3]:  # Limit to first 3 pods
        logs_result = mcp.get_pod_logs(pod_name=pod_name, namespace=namespace, tail=50)
        if "logs" in logs_result:
            logs.extend(logs_result["logs"])

    # 4. Deployment history
    print("  ├─ Getting deployment history...")
    deployments_result = mcp.get_deployments(
        namespace=namespace,
        deployment_name=service
    )
    deployments = deployments_result.get("deployments", [])

    # Extract recent deploys from rollout history
    recent_deploys = []
    for deployment in deployments:
        history = deployment.get("rolloutHistory", [])
        recent_deploys.extend(history)

    # 5. GitHub activity
    print("  ├─ Getting GitHub activity...")
    repo = f"myorg/{service}"  # TODO: Make configurable
    commits_result = mcp.get_recent_commits(repo=repo, limit=10)
    commits = commits_result.get("commits", [])

    prs_result = mcp.get_recent_prs(repo=repo, limit=5)
    prs = prs_result.get("prs", [])

    # 6. Observability metrics
    print("  ├─ Getting service health metrics...")
    health_result = mcp.get_service_health(service=service, time_window="1h")
    metrics = health_result.get("data", {})

    # 7. Runbooks (via custom MCP server - TODO: implement)
    # For now, leave empty
    runbooks = []

    # 8. Similar past incidents (via custom MCP server - TODO: implement)
    # For now, leave empty
    past_incidents = []

    # Package evidence
    evidence: Evidence = {
        "logs": logs,
        "metrics": metrics,
        "recent_deploys": recent_deploys,
        "pod_status": {
            "pods": pod_status,
            "events": events
        },
        "github_activity": {
            "commits": commits,
            "prs": prs
        },
        "runbooks": runbooks,
        "past_incidents": past_incidents
    }

    print(f"  └─ Evidence gathered:")
    print(f"     • {len(logs)} log entries")
    print(f"     • {len(pod_status)} pods")
    print(f"     • {len(events)} events")
    print(f"     • {len(recent_deploys)} recent deployments")
    print(f"     • {len(commits)} commits, {len(prs)} PRs")

    return {
        **state,
        "evidence": evidence,
        "status": "diagnosing",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"Evidence gathering completed - collected data from {len(pod_status)} pods"}
        ]
    }
