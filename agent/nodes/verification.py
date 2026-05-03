"""Verification node: Test hypotheses with targeted checks."""

import json
import logging
from datetime import datetime
from agent.state import AgentState, VerificationResult
from agent.utils.llm_client import LLMClient
from agent.utils.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def verification_node(state: AgentState) -> AgentState:
    """Run targeted checks to verify the current hypothesis.

    Returns one of:
    - confirmed: Hypothesis is supported by evidence
    - refuted: Hypothesis is contradicted by evidence
    - inconclusive: Unable to confirm or refute

    Args:
        state: Current agent state with hypotheses

    Returns:
        Updated state with verification result
    """
    print("✅ VERIFICATION: Testing hypothesis...")

    # Get current hypothesis
    hypotheses = state.get("hypotheses", [])
    current_index = state.get("current_hypothesis_index", 0)

    if not hypotheses or current_index >= len(hypotheses):
        # No hypothesis to verify - this shouldn't happen
        print("   WARNING: No hypothesis available to verify")
        verification_result: VerificationResult = {
            "hypothesis": {
                "rank": 0,
                "description": "No hypothesis",
                "falsification_criterion": "",
                "supporting_evidence": [],
                "verification_checks": []
            },
            "status": "inconclusive",
            "evidence": [],
            "reasoning": "No hypothesis available to verify",
            "timestamp": datetime.now()
        }
    else:
        current_hypothesis = hypotheses[current_index]
        print(f"   Testing hypothesis #{current_index + 1}: {current_hypothesis['description']}")
        print(f"   Falsification criterion: {current_hypothesis['falsification_criterion']}")

        # Run verification
        verification_result = _verify_hypothesis(
            hypothesis=current_hypothesis,
            incident=state.get("incident"),
            evidence=state.get("evidence")
        )

        print(f"   Result: {verification_result['status'].upper()}")
        print(f"   Reasoning: {verification_result['reasoning'][:100]}...")

    return {
        **state,
        "verification_results": state.get("verification_results", []) + [verification_result],
        "verification_round": state.get("verification_round", 0) + 1,
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"Verification completed: {verification_result['status']}"}
        ]
    }


def _verify_hypothesis(hypothesis: dict, incident: dict, evidence: dict) -> VerificationResult:
    """Verify a hypothesis using targeted checks and falsification criterion.

    Args:
        hypothesis: Hypothesis to verify
        incident: Incident data
        evidence: Evidence data

    Returns:
        VerificationResult
    """
    # Run verification checks specified in the hypothesis
    verification_evidence = _run_verification_checks(
        checks=hypothesis.get("verification_checks", []),
        incident=incident,
        evidence=evidence
    )

    # Use LLM to evaluate the hypothesis against evidence
    llm = LLMClient()
    prompt = _build_verification_prompt(hypothesis, incident, evidence, verification_evidence)

    # Increased max_tokens to 2048 to ensure enough space for complete response
    result = llm.generate_json(prompt=prompt, max_tokens=2048)

    # DEBUG: Print raw LLM response
    print(f"   [DEBUG] LLM verification response: {json.dumps(result, indent=2)[:500]}")
    if "error" in result:
        print(f"   [DEBUG] Full error response: {json.dumps(result, indent=2)}")

    # Parse result
    if "error" in result:
        logger.error(f"LLM verification error: {result['error']}")
        print(f"   [ERROR] LLM failed: {result['error']}")
        # Default to inconclusive if LLM fails
        return {
            "hypothesis": hypothesis,
            "status": "inconclusive",
            "evidence": verification_evidence,
            "reasoning": f"LLM error: {result['error']}",
            "timestamp": datetime.now()
        }

    try:
        status = result.get("status", "inconclusive")
        reasoning = result.get("reasoning", "No reasoning provided")

        # Ensure status is valid
        if status not in ["confirmed", "refuted", "inconclusive"]:
            status = "inconclusive"

        return {
            "hypothesis": hypothesis,
            "status": status,
            "evidence": verification_evidence,
            "reasoning": reasoning,
            "timestamp": datetime.now()
        }

    except Exception as e:
        logger.error(f"Failed to parse verification result: {e}", exc_info=True)
        return {
            "hypothesis": hypothesis,
            "status": "inconclusive",
            "evidence": verification_evidence,
            "reasoning": f"Parse error: {str(e)}",
            "timestamp": datetime.now()
        }


def _run_verification_checks(checks: list[str], incident: dict, evidence: dict) -> list[dict]:
    """Run verification checks to gather targeted evidence.

    Args:
        checks: List of check descriptions
        incident: Incident data
        evidence: Existing evidence

    Returns:
        List of check results
    """
    check_results = []
    mcp = MCPClient()

    service = incident.get("service", "unknown-service")

    # DEBUG: Show what evidence we have available
    pods_count = len(evidence.get("pod_status", {}).get("pods", []))
    events_count = len(evidence.get("pod_status", {}).get("events", []))
    print(f"   [DEBUG] Running {len(checks)} verification checks with {pods_count} pods and {events_count} events")

    for check in checks:
        check_lower = check.lower()

        try:
            # Interpret check and run appropriate MCP call
            if "deployment" in check_lower or "deploy" in check_lower:
                # Check deployment history
                result = mcp.get_deployments(deployment_name=service)
                deployments = result.get("deployments", [])

                check_results.append({
                    "check": check,
                    "type": "deployment_history",
                    "data": deployments,
                    "summary": f"Found {len(deployments)} deployment(s)"
                })

            elif "memory" in check_lower or "resource" in check_lower:
                # Check pod resource limits
                pods = evidence.get("pod_status", {}).get("pods", [])
                resource_info = []

                print(f"   [DEBUG] Checking resources for {len(pods)} pods")

                for pod in pods[:3]:  # Check first 3 pods
                    containers = pod.get("spec", {}).get("containers", [])
                    for container in containers:
                        resources = container.get("resources", {})
                        limits = resources.get("limits", {})
                        requests = resources.get("requests", {})
                        resource_info.append({
                            "pod": pod.get("metadata", {}).get("name"),
                            "container": container.get("name"),
                            "limits": limits,
                            "requests": requests
                        })
                        print(f"   [DEBUG] Pod {pod.get('metadata', {}).get('name')}: memory limit={limits.get('memory')}, request={requests.get('memory')}")

                check_results.append({
                    "check": check,
                    "type": "resource_limits",
                    "data": resource_info,
                    "summary": f"Checked resources for {len(resource_info)} container(s)"
                })

            elif "event" in check_lower or "oom" in check_lower:
                # Check for specific events
                events = evidence.get("pod_status", {}).get("events", [])
                print(f"   [DEBUG] Searching {len(events)} events for '{check_lower}'")

                relevant_events = [
                    e for e in events
                    if check_lower.replace(" ", "") in e.get("reason", "").lower()
                    or check_lower.replace(" ", "") in e.get("message", "").lower()
                ]

                if relevant_events:
                    print(f"   [DEBUG] Found {len(relevant_events)} matching events:")
                    for evt in relevant_events[:3]:
                        print(f"     - {evt.get('reason')}: {evt.get('message')[:60]}")
                else:
                    print(f"   [DEBUG] No events matching '{check_lower}'")

                check_results.append({
                    "check": check,
                    "type": "events",
                    "data": relevant_events,
                    "summary": f"Found {len(relevant_events)} relevant event(s)"
                })

            elif "metric" in check_lower or "cpu" in check_lower:
                # Check metrics
                health = mcp.get_service_health(service=service)

                check_results.append({
                    "check": check,
                    "type": "metrics",
                    "data": health.get("data", {}),
                    "summary": "Retrieved service health metrics"
                })

            else:
                # Generic check - just note it was considered
                check_results.append({
                    "check": check,
                    "type": "generic",
                    "data": {},
                    "summary": "Check noted but no specific action taken"
                })

        except Exception as e:
            logger.error(f"Error running verification check '{check}': {e}")
            check_results.append({
                "check": check,
                "type": "error",
                "data": {},
                "summary": f"Error: {str(e)}"
            })

    return check_results


def _build_verification_prompt(
    hypothesis: dict,
    incident: dict,
    evidence: dict,
    verification_evidence: list[dict]
) -> str:
    """Build verification prompt for LLM.

    Args:
        hypothesis: Hypothesis to verify
        incident: Incident data
        evidence: Original evidence
        verification_evidence: Evidence from verification checks

    Returns:
        Formatted prompt
    """
    # Format verification evidence
    verification_summary = []
    for check in verification_evidence:
        verification_summary.append(f"- {check['check']}: {check['summary']}")

    prompt = f"""Verify this hypothesis about a production incident.

**Hypothesis:**
{hypothesis['description']}

**Falsification Criterion:**
{hypothesis['falsification_criterion']}

**Incident:**
- Service: {incident.get('service')}
- Description: {incident.get('description')}

**Original Evidence Summary:**
- Pods: {len(evidence.get('pod_status', {}).get('pods', []))} total
- Events: {len(evidence.get('pod_status', {}).get('events', []))} total
- Recent Deploys: {len(evidence.get('recent_deploys', []))}

**Verification Checks Performed:**
{chr(10).join(verification_summary)}

**Detailed Verification Evidence:**
{json.dumps(verification_evidence, indent=2)}

**Instructions:**
Evaluate whether this hypothesis is:
1. **confirmed** - Strong evidence supports it, falsification criterion NOT met
2. **refuted** - Evidence contradicts it, falsification criterion IS met
3. **inconclusive** - Insufficient evidence to confirm or refute

Apply the falsification criterion strictly. If the condition in the falsification criterion is true, the hypothesis MUST be refuted.

Return JSON:
{{
  "status": "confirmed | refuted | inconclusive",
  "reasoning": "Detailed explanation of why, referencing specific evidence"
}}"""

    return prompt

