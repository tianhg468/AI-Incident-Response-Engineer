"""Diagnosis node: Generate hypotheses about the root cause."""

import json
import logging
from agent.state import AgentState, Hypothesis
from agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


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

    # Otherwise, generate new hypotheses using LLM
    human_feedback = state.get("human_feedback")
    if human_feedback:
        print(f"   Analyzing evidence with human feedback: {human_feedback}")
    else:
        print("   Analyzing evidence to generate hypotheses...")

    incident = state.get("incident")
    evidence = state.get("evidence")

    if not incident or not evidence:
        logger.warning("Missing incident or evidence data")
        # Return placeholder
        return _return_placeholder_hypotheses(state)

    # Build prompt (include human feedback if available)
    prompt = _build_diagnosis_prompt(incident, evidence, human_feedback)

    # Call LLM
    llm = LLMClient()
    result = llm.generate_json(prompt=prompt, max_tokens=2048)

    # Parse hypotheses
    if "error" in result:
        logger.error(f"LLM error: {result['error']}")
        return _return_placeholder_hypotheses(state)

    try:
        hypotheses_list = result if isinstance(result, list) else result.get("hypotheses", [])

        new_hypotheses: list[Hypothesis] = []
        for i, h in enumerate(hypotheses_list[:3]):  # Limit to top 3
            new_hypotheses.append({
                "rank": h.get("rank", i + 1),
                "description": h.get("description", "Unknown hypothesis"),
                "falsification_criterion": h.get("falsification_criterion", ""),
                "supporting_evidence": h.get("supporting_evidence", []),
                "verification_checks": h.get("verification_checks", [])
            })

        print(f"   ✓ Generated {len(new_hypotheses)} hypotheses")
        for h in new_hypotheses:
            print(f"     #{h['rank']}: {h['description']}")

        return {
            **state,
            "hypotheses": state.get("hypotheses", []) + new_hypotheses,
            "current_hypothesis_index": 0,  # Reset to first hypothesis
            "status": "verifying",
            "human_feedback": None,  # Clear feedback after using it
            "messages": state.get("messages", []) + [
                {"role": "system", "content": f"Generated {len(new_hypotheses)} hypotheses using LLM"}
            ]
        }

    except Exception as e:
        logger.error(f"Failed to parse hypotheses: {e}", exc_info=True)
        return _return_placeholder_hypotheses(state)


def _build_diagnosis_prompt(incident: dict, evidence: dict, human_feedback: str = None) -> str:
    """Build diagnosis prompt from incident and evidence.

    Args:
        incident: Incident data
        evidence: Evidence data
        human_feedback: Optional human feedback on why previous approach won't work

    Returns:
        Formatted prompt
    """
    # Summarize evidence
    pods = evidence.get("pod_status", {}).get("pods", [])
    events = evidence.get("pod_status", {}).get("events", [])
    logs = evidence.get("logs", [])
    deploys = evidence.get("recent_deploys", [])
    metrics = evidence.get("metrics", {})

    # Format key evidence
    pod_summary = f"{len(pods)} pods"
    if pods:
        statuses = {}
        for pod in pods:
            status = pod.get("status", {}).get("phase", "Unknown")
            statuses[status] = statuses.get(status, 0) + 1
        pod_summary = ", ".join([f"{count} {status}" for status, count in statuses.items()])

    event_summary = "None"
    if events:
        event_types = {}
        for event in events[:10]:  # Limit to recent
            reason = event.get("reason", "Unknown")
            event_types[reason] = event_types.get(reason, 0) + 1
        event_summary = ", ".join([f"{count}x {reason}" for reason, count in event_types.items()])

    deploy_summary = "No recent deployments"
    if deploys:
        latest = deploys[0]
        deploy_summary = f"Latest deploy: {latest.get('image', 'unknown')} at {latest.get('deployedAt', 'unknown')}"
        if latest.get("changes"):
            changes_desc = ", ".join([c.get("field", "") for c in latest["changes"][:3]])
            deploy_summary += f"\nChanges: {changes_desc}"

    log_errors = [log for log in logs if log.get("level") in ["ERROR", "WARN"]]
    log_summary = f"{len(logs)} total, {len(log_errors)} errors/warnings"

    # Add human feedback section if available
    feedback_section = ""
    if human_feedback:
        feedback_section = f"""
**IMPORTANT - Human Feedback:**
A previous remediation approach was rejected with this feedback:
"{human_feedback}"

Take this feedback into account when generating new hypotheses. Avoid the rejected approach and consider alternative solutions suggested by the human operator.
"""

    # Extract alert details
    alert_data = incident.get('alert_data', {})
    alert_labels = alert_data.get('labels', {})
    alert_annotations = alert_data.get('annotations', {})

    alert_name = alert_labels.get('alertname', 'Unknown')
    alert_summary = alert_annotations.get('summary', '')
    alert_description = alert_annotations.get('description', '')

    prompt = f"""Analyze this production incident and generate 2-3 ranked hypotheses about the root cause.
{feedback_section}

**Incident Details:**
- Alert Name: {alert_name}
- Service: {incident.get('service')}
- Severity: {incident.get('severity')}
- Alert Summary: {alert_summary}
- Alert Description: {alert_description}
- Time Window: {incident.get('time_window_start')} to {incident.get('time_window_end')}

**Evidence:**

Pods: {pod_summary}

Events: {event_summary}

Logs: {log_summary}
Sample errors: {json.dumps([log.get('message') for log in log_errors[:5]], indent=2)}

Recent Deployments: {deploy_summary}

Metrics: {json.dumps(metrics, indent=2)}

**Instructions:**
Generate 2-3 hypotheses ranked by likelihood. For each:
1. **Description**: What you think went wrong
2. **Falsification Criterion**: Explicit test - "if X is true, this hypothesis is wrong"
3. **Supporting Evidence**: References to specific evidence
4. **Verification Checks**: Specific checks to run (e.g., "Check memory limits in deployment config")

Focus on:
- **CRITICALLY IMPORTANT**: Base your hypotheses on the ALERT NAME and ALERT SUMMARY above. Different alerts indicate different root causes.
  - For OOMKilled alerts: Focus on memory limits, memory leaks
  - For CrashLoop alerts: Focus on startup failures, config errors
  - For AlertManager/notification failures: Focus on network issues, authentication, configuration
  - For service down alerts: Focus on availability, health checks, dependencies
- Correlation between deploy timing and incident
- Anomalies in metrics/logs specific to the alert type
- Common failure patterns for this specific type of alert

Return as JSON array of hypotheses."""

    return prompt


def _return_placeholder_hypotheses(state: AgentState) -> AgentState:
    """Return placeholder hypotheses as fallback.

    Args:
        state: Current state

    Returns:
        Updated state with placeholder hypotheses
    """
    new_hypotheses: list[Hypothesis] = [
        {
            "rank": 1,
            "description": "Recent deployment introduced breaking change",
            "falsification_criterion": "If no deployment occurred in the last 24h, this is wrong",
            "supporting_evidence": ["recent_deploys"],
            "verification_checks": ["Check deployment history", "Review code changes"]
        }
    ]

    return {
        **state,
        "hypotheses": state.get("hypotheses", []) + new_hypotheses,
        "current_hypothesis_index": 0,
        "status": "verifying",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": "Generated placeholder hypotheses (LLM unavailable)"}
        ]
    }
