"""Intake node: Parse alert and extract incident information."""

import os
import logging
from datetime import datetime
from pathlib import Path
import yaml

from agent.state import AgentState, Incident

logger = logging.getLogger(__name__)


def intake_node(state: AgentState) -> AgentState:
    """Parse alert and extract structured incident information.

    In eval mode, loads incident data from scenario manifest.
    In live mode, would parse incoming webhook/CLI alert data.

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

    mode = os.getenv("MODE", "eval")
    scenario = os.getenv("SCENARIO", "oom_after_deploy")

    if mode == "eval":
        # Load incident from scenario manifest
        incident = _load_incident_from_scenario(scenario)
    else:
        # Parse from raw alert (live mode)
        raw_alert = state.get("raw_alert", {})
        incident = _parse_raw_alert(raw_alert)

    print(f"  📌 Service: {incident['service']}")
    print(f"  📌 Severity: {incident['severity']}")
    print(f"  📌 Alert: {incident.get('description', 'N/A')}")

    return {
        **state,
        "incident": incident,
        "status": "gathering_evidence",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"Intake completed for {incident['service']}"}
        ]
    }


def _load_incident_from_scenario(scenario: str) -> Incident:
    """Load incident data from scenario manifest.

    Args:
        scenario: Scenario name

    Returns:
        Incident object
    """
    # Load manifest
    manifest_path = Path(__file__).parent.parent.parent / "fixtures" / "scenarios" / scenario / "manifest.yml"

    if not manifest_path.exists():
        logger.warning(f"Scenario manifest not found: {manifest_path}")
        return _create_placeholder_incident()

    try:
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        incident_data = manifest.get("incident", {})

        # Parse timestamps
        time_window = incident_data.get("time_window", {})
        start_str = time_window.get("start", datetime.now().isoformat())
        end_str = time_window.get("end", datetime.now().isoformat())

        incident: Incident = {
            "alert_id": f"ALERT-{scenario}",
            "service": incident_data.get("service", "unknown-service"),
            "severity": incident_data.get("severity", "high"),
            "time_window_start": datetime.fromisoformat(start_str.replace('Z', '+00:00')),
            "time_window_end": datetime.fromisoformat(end_str.replace('Z', '+00:00')),
            "affected_pods": incident_data.get("affected_pods", []),
            "affected_endpoints": incident_data.get("affected_endpoints", []),
            "description": f"{incident_data.get('alert_type', 'alert')} detected on {incident_data.get('service')}",
            "raw_alert": incident_data
        }

        return incident

    except Exception as e:
        logger.error(f"Failed to load scenario manifest: {e}", exc_info=True)
        return _create_placeholder_incident()


def _parse_raw_alert(raw_alert: dict) -> Incident:
    """Parse raw alert data (live mode).

    Args:
        raw_alert: Raw alert payload

    Returns:
        Incident object
    """
    # TODO: Implement actual alert parsing for live mode
    # Would parse PagerDuty, Alertmanager, or other alert formats

    return _create_placeholder_incident()


def _create_placeholder_incident() -> Incident:
    """Create a placeholder incident for testing.

    Returns:
        Incident object
    """
    return {
        "alert_id": "ALERT-PLACEHOLDER",
        "service": "payment-service",
        "severity": "high",
        "time_window_start": datetime.now(),
        "time_window_end": datetime.now(),
        "affected_pods": [],
        "affected_endpoints": [],
        "description": "Placeholder incident",
        "raw_alert": {}
    }
