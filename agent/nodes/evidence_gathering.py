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

    # 3. Pod logs (from affected pods or all pods if not specified)
    print("  ├─ Getting pod logs...")
    logs = []
    affected_pods = incident.get("affected_pods", [])

    # If no specific affected pods listed, get logs from all pods in the deployment
    if not affected_pods and pod_status:
        affected_pods = [pod.get("metadata", {}).get("name") for pod in pod_status[:3]]
        print(f"     No affected_pods specified, using: {affected_pods}")

    for pod_name in affected_pods[:3]:  # Limit to first 3 pods
        if not pod_name:
            continue
        try:
            logs_result = mcp.get_pod_logs(pod_name=pod_name, namespace=namespace, tail=50)
            if "logs" in logs_result:
                logs.extend(logs_result["logs"])
        except Exception as e:
            logger.warning(f"Failed to get logs for pod {pod_name}: {e}")

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

    # Map service to its deployment repository
    import os
    github_org = os.getenv("GITHUB_ORG", "tianhg468")

    # Service-specific repository mapping for GitOps deployments
    service_repo_map = {
        "demo-app": f"{github_org}/ai-incident-response-demo",
        # Add more service mappings as needed
    }

    # Try to get service-specific repo, fallback to agent repo
    repo = service_repo_map.get(service, f"{github_org}/{os.getenv('GITHUB_REPO', 'agentic_ai')}")
    print(f"     Querying GitHub repo: {repo}")

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

    # DEBUG: Show pod details
    if pod_status:
        print(f"  [DEBUG] Pod statuses:")
        for pod in pod_status[:3]:
            name = pod.get("metadata", {}).get("name", "unknown")
            phase = pod.get("status", {}).get("phase", "Unknown")
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            print(f"    - {name}: {phase}")
            if container_statuses:
                for cs in container_statuses:
                    state = cs.get("state", {})
                    last_state = cs.get("lastState", {})
                    restart_count = cs.get("restartCount", 0)
                    print(f"      Container: {cs.get('name')}, Restarts: {restart_count}")
                    if "waiting" in state:
                        print(f"      State: Waiting - {state['waiting'].get('reason')}")
                    if "terminated" in last_state:
                        print(f"      Last: Terminated - {last_state['terminated'].get('reason')}")

    # DEBUG: Show OOM events
    oom_events = [e for e in events if "oom" in e.get("reason", "").lower() or "oom" in e.get("message", "").lower()]
    if oom_events:
        print(f"  [DEBUG] Found {len(oom_events)} OOM-related events:")
        for evt in oom_events[:3]:
            print(f"    - {evt.get('reason')}: {evt.get('message')[:80]}")

    return {
        **state,
        "evidence": evidence,
        "status": "diagnosing",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"Evidence gathering completed - collected data from {len(pod_status)} pods"}
        ]
    }
