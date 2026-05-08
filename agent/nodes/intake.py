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
        raw_alert = state.get("raw_alert")

        # If no raw_alert in state, try loading from current_incident.json
        if not raw_alert:
            import json
            incident_file = Path(__file__).parent.parent.parent / "data" / "current_incident.json"
            if incident_file.exists():
                try:
                    with open(incident_file) as f:
                        raw_alert = json.load(f)
                    logger.info(f"Loaded incident from {incident_file}")
                except Exception as e:
                    logger.error(f"Failed to load incident file: {e}", exc_info=True)
                    raw_alert = {}
            else:
                logger.warning(f"No incident file found at {incident_file}")
                raw_alert = {}

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

        # Map alert_type to Prometheus alert format for consistency with live mode
        alert_type = incident_data.get("alert_type", "alert")
        service = incident_data.get("service", "unknown-service")
        severity = incident_data.get("severity", "high")

        # Map common alert types to Prometheus alert names
        alert_type_mapping = {
            "pod_crash_loop": "PodOOMKilled",
            "oom_after_deploy": "PodOOMKilled",
            "high_latency": "HighRequestLatency",
            "service_down": "ServiceUnavailable",
            "error_rate_spike": "HighErrorRate"
        }

        alert_name = alert_type_mapping.get(alert_type, alert_type.replace("_", " ").title())
        alert_summary = f"{alert_name} alert triggered for {service}"
        alert_description = manifest.get("description", f"{alert_type} detected on {service}")

        # Construct alert_data in Prometheus format
        alert_data = {
            "labels": {
                "alertname": alert_name,
                "service": service,
                "severity": severity
            },
            "annotations": {
                "summary": alert_summary,
                "description": alert_description
            }
        }

        incident: Incident = {
            "alert_id": f"ALERT-{scenario}",
            "service": service,
            "severity": severity,
            "time_window_start": datetime.fromisoformat(start_str.replace('Z', '+00:00')),
            "time_window_end": datetime.fromisoformat(end_str.replace('Z', '+00:00')),
            "affected_pods": incident_data.get("affected_pods", []),
            "affected_endpoints": incident_data.get("affected_endpoints", []),
            "description": alert_summary,
            "alert_data": alert_data,  # Add Prometheus-format alert data
            "raw_alert": incident_data
        }

        return incident

    except Exception as e:
        logger.error(f"Failed to load scenario manifest: {e}", exc_info=True)
        return _create_placeholder_incident()


def _parse_raw_alert(raw_alert: dict) -> Incident:
    """Parse raw alert data (live mode).

    Args:
        raw_alert: Raw alert payload from webhook/current_incident.json

    Returns:
        Incident object
    """
    # Check if we have alert_data from Prometheus/AlertManager
    alert_data = raw_alert.get("alert_data", {})

    if alert_data:
        # Parse Prometheus/AlertManager format
        labels = alert_data.get("labels", {})
        annotations = alert_data.get("annotations", {})

        alert_name = labels.get("alertname", "Unknown")

        # For pod-level alerts (OOMKilled, CrashLoop), extract service from pod name
        # The "service" label is the alert source (e.g., kube-state-metrics), not the affected service
        if alert_name in ["PodOOMKilled", "PodCrashLooping", "PodCrashLoop"]:
            # Extract service from pod name (e.g., "demo-app-598f7f8799-9q7j5" -> "demo-app")
            pod_name = labels.get("pod", "")
            if pod_name:
                # Pod name format: {service}-{replicaset-hash}-{pod-hash}
                service = "-".join(pod_name.split("-")[:-2]) if "-" in pod_name else pod_name
                logger.info(f"Extracted affected service '{service}' from pod '{pod_name}' for {alert_name} alert")
            else:
                service = raw_alert.get("service", labels.get("service", "unknown"))
        else:
            service = raw_alert.get("service", labels.get("service", "unknown"))

        severity = raw_alert.get("severity", labels.get("severity", "high"))

        # Use alert summary as description, fallback to alert name
        description = annotations.get("summary", f"{alert_name} alert triggered")

        return {
            "alert_id": raw_alert.get("investigation_id", "ALERT-LIVE"),
            "service": service,
            "severity": severity,
            "time_window_start": datetime.fromisoformat(raw_alert.get("triggered_at", datetime.now().isoformat()).replace('Z', '+00:00')),
            "time_window_end": datetime.now(),
            "affected_pods": [],  # Could parse from alert labels if needed
            "affected_endpoints": [],
            "description": description,
            "alert_data": alert_data,  # Include alert_data for diagnosis node
            "raw_alert": raw_alert
        }

    # Fallback for unknown alert formats
    return _create_placeholder_incident()


def _create_placeholder_incident() -> Incident:
    """Create a placeholder incident for testing.

    Returns:
        Incident object
    """
    return {
        "alert_id": "ALERT-DEMO",
        "service": "demo-app",
        "severity": "high",
        "time_window_start": datetime.now(),
        "time_window_end": datetime.now(),
        "affected_pods": [],
        "affected_endpoints": [],
        "description": "OOMKilled pods detected in demo-app deployment",
        "raw_alert": {}
    }
