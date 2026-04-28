"""Intake node: Parse alert and extract incident information."""

from datetime import datetime
from agent.state import AgentState, Incident


def intake_node(state: AgentState) -> AgentState:
    """Parse alert and extract structured incident information.

    Extracts:
    - Service name
    - Severity
    - Time window
    - Affected pods/endpoints
    - Alert description

    Args:
        state: Current agent state with raw alert data

    Returns:
        Updated state with structured Incident object
    """
    print("🔔 INTAKE: Processing alert...")

    # TODO: Implement actual alert parsing
    # This is a placeholder that will be implemented in a later step

    incident: Incident = {
        "alert_id": "placeholder-alert-id",
        "service": "placeholder-service",
        "severity": "high",
        "time_window_start": datetime.now(),
        "time_window_end": datetime.now(),
        "affected_pods": [],
        "affected_endpoints": [],
        "description": "Placeholder incident description",
        "raw_alert": {}
    }

    return {
        **state,
        "incident": incident,
        "status": "gathering_evidence",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": "Intake completed"}
        ]
    }
