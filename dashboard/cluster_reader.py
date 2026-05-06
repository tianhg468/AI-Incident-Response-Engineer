"""Read live investigation data from Kubernetes cluster."""

import subprocess
import json
from typing import Optional, Dict, Any


def run_kubectl(cmd: str) -> str:
    """Execute kubectl command and return output."""
    try:
        result = subprocess.run(
            f"kubectl {cmd}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def get_current_incident() -> Optional[Dict[str, Any]]:
    """Get current incident from webhook pod."""
    try:
        # Get webhook pod name
        pod_output = run_kubectl("get pod -l app=agent-webhook -o jsonpath='{.items[0].metadata.name}'")
        pod_name = pod_output.strip().strip("'")

        if not pod_name:
            return None

        # Read incident data
        incident_output = run_kubectl(f"exec {pod_name} -- cat /app/data/current_incident.json 2>/dev/null")

        if incident_output and 'Error' not in incident_output:
            return json.loads(incident_output)
    except Exception:
        pass

    return None


def get_agent_investigation_log() -> Optional[str]:
    """Get agent investigation log from webhook pod."""
    try:
        # Get webhook pod name
        pod_output = run_kubectl("get pod -l app=agent-webhook -o jsonpath='{.items[0].metadata.name}'")
        pod_name = pod_output.strip().strip("'")

        if not pod_name:
            return None

        # Read agent investigation log
        log_output = run_kubectl(f"exec {pod_name} -- cat /app/data/agent_investigation.log 2>/dev/null")

        if log_output and 'Error' not in log_output and 'No such file' not in log_output:
            return log_output
    except Exception:
        pass

    return None


def parse_investigation_log(log_text: str) -> Dict[str, Any]:
    """Parse agent investigation log into structured data."""
    investigation = {
        'phase': 'idle',
        'evidence': [],
        'hypotheses': [],
        'verification': [],
        'rootCause': None,
        'remediation': [],
        'prUrl': None
    }

    if not log_text:
        return investigation

    lines = log_text.split('\n')
    current_phase = None

    for line in lines:
        if not line.strip():
            continue

        # Detect phases
        if any(marker in line for marker in ['PHASE 1', 'Evidence Gathering', '🔍']):
            current_phase = 'evidence'
            investigation['phase'] = 'gathering_evidence'

        elif any(marker in line for marker in ['PHASE 2', 'Hypothesis', '🧠']):
            current_phase = 'hypothesis'
            investigation['phase'] = 'analyzing'

        elif any(marker in line for marker in ['PHASE 3', 'Verification', '✓ Verifying']):
            current_phase = 'verification'
            investigation['phase'] = 'analyzing'

        elif any(marker in line for marker in ['PHASE 4', 'Remediation', '📝']):
            current_phase = 'remediation'
            investigation['phase'] = 'creating_fix'

        # Parse content by phase
        if current_phase == 'evidence':
            if any(marker in line for marker in ['Found:', 'Detected:', 'Observed:', '•', '-']):
                investigation['evidence'].append(line.strip())

        elif current_phase == 'hypothesis':
            if any(marker in line for marker in ['Hypothesis', 'H1:', 'H2:', 'H3:', '•', '-']):
                investigation['hypotheses'].append(line.strip())

        elif current_phase == 'verification':
            if any(marker in line for marker in ['Verified:', 'Confirmed:', 'Testing:', '✓', '•', '-']):
                investigation['verification'].append(line.strip())
            if 'ROOT CAUSE' in line.upper() or 'Root cause:' in line:
                investigation['rootCause'] = line.strip()

        elif current_phase == 'remediation':
            if any(marker in line for marker in ['Action:', 'Fix:', 'Change:', '•', '-']):
                investigation['remediation'].append(line.strip())
            if 'PR created:' in line or 'https://github.com' in line:
                import re
                url_match = re.search(r'https://github\.com[^\s]+', line)
                if url_match:
                    investigation['prUrl'] = url_match.group(0)

        # Detect completion
        if 'Investigation complete' in line or 'COMPLETED' in line:
            investigation['phase'] = 'completed'

    return investigation


def get_live_investigation() -> Optional[Dict[str, Any]]:
    """Get live investigation data from cluster."""
    incident = get_current_incident()
    if not incident:
        return None

    log_text = get_agent_investigation_log()
    investigation_data = parse_investigation_log(log_text) if log_text else {}

    return {
        'incident': incident,
        'investigation': investigation_data,
        'log': log_text
    }
