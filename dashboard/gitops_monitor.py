"""GitOps Flow Monitoring Dashboard

Real-time monitoring of the complete GitOps incident response flow.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import subprocess
import requests
import os
from datetime import datetime
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Set KUBECONFIG if not already set
if 'KUBECONFIG' not in os.environ:
    kubeconfig_path = Path.home() / '.kube' / 'config'
    if kubeconfig_path.exists():
        os.environ['KUBECONFIG'] = str(kubeconfig_path)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_ORG = os.getenv('GITHUB_ORG', 'tianhg468')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'AI-Incident-Response-Engineer')


def run_kubectl(cmd):
    """Execute kubectl command and return output."""
    try:
        result = subprocess.run(
            f"kubectl {cmd}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


def get_pod_status():
    """Get demo-app pod status."""
    output = run_kubectl("get pods -l app=demo-app -o json")
    try:
        data = json.loads(output)
        pods = []
        for pod in data.get('items', []):
            status = pod['status']
            container_statuses = status.get('containerStatuses', [{}])[0]

            # Check for OOMKilled
            terminated = container_statuses.get('lastState', {}).get('terminated', {})
            is_oom = terminated.get('reason') == 'OOMKilled'

            pods.append({
                'name': pod['metadata']['name'],
                'status': status.get('phase', 'Unknown'),
                'restarts': container_statuses.get('restartCount', 0),
                'ready': container_statuses.get('ready', False),
                'oomKilled': is_oom,
                'reason': terminated.get('reason', 'Running')
            })
        return pods
    except:
        return []


def get_prometheus_alerts():
    """Get Prometheus alerts status."""
    try:
        # Try to query Prometheus API
        response = requests.get('http://localhost:9090/api/v1/alerts', timeout=2)
        if response.status_code == 200:
            data = response.json()
            alerts = []
            for alert in data.get('data', {}).get('alerts', []):
                if alert['state'] == 'firing':
                    alerts.append({
                        'name': alert['labels'].get('alertname', 'Unknown'),
                        'severity': alert['labels'].get('severity', 'unknown'),
                        'state': alert['state'],
                        'summary': alert['annotations'].get('summary', ''),
                        'activeAt': alert.get('activeAt', '')
                    })
            return alerts
    except:
        pass

    # Fallback: check via kubectl
    output = run_kubectl("get prometheusrule -n default -o json")
    try:
        data = json.loads(output)
        return [{'name': 'Check Prometheus UI', 'severity': 'info', 'state': 'unknown'}]
    except:
        return []


def get_incident_data():
    """Get current incident data from webhook pod. Validation happens in status endpoint."""
    try:
        # Get webhook pod name
        pod_output = run_kubectl("get pod -l app=agent-webhook -o jsonpath='{.items[0].metadata.name}'")
        pod_name = pod_output.strip().strip("'")

        if not pod_name or 'Error' in pod_name:
            return None

        # Read incident data
        incident_output = run_kubectl(f"exec {pod_name} -- cat /app/data/current_incident.json")

        if incident_output and 'Error' not in incident_output:
            return json.loads(incident_output)
    except:
        pass

    return None


def get_approvals_data():
    """Get pending approvals/remediation actions from webhook pod."""
    try:
        # Get webhook pod name
        pod_output = run_kubectl("get pod -l app=agent-webhook -o jsonpath='{.items[0].metadata.name}'")
        pod_name = pod_output.strip().strip("'")

        if not pod_name or 'Error' in pod_name:
            return []

        # Read approvals data
        approvals_output = run_kubectl(f"exec {pod_name} -- cat /app/data/approvals.json")

        if approvals_output and 'Error' not in approvals_output:
            approvals_dict = json.loads(approvals_output)
            # Convert to list and get most recent
            approvals_list = list(approvals_dict.values())
            # Sort by created_at descending
            approvals_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            return approvals_list[:5]  # Return 5 most recent
    except:
        pass

    return []


def get_all_investigations():
    """Get all active investigations from webhook pod."""
    try:
        # Get webhook pod name
        pod_output = run_kubectl("get pod -l app=agent-webhook -o jsonpath='{.items[0].metadata.name}'")
        pod_name = pod_output.strip().strip("'")

        if not pod_name or 'Error' in pod_name:
            return []

        # Read investigations index
        investigations_output = run_kubectl(f"exec {pod_name} -- cat /app/data/investigations.json 2>/dev/null")

        if investigations_output and 'Error' not in investigations_output and 'No such file' not in investigations_output:
            investigations_index = json.loads(investigations_output)

            # Get details for each investigation
            all_investigations = []
            for inv_id, inv_meta in investigations_index.items():
                # Read investigation log
                log_output = run_kubectl(f"exec {pod_name} -- cat /app/data/investigation_{inv_id}.log 2>/dev/null")

                # Read incident data
                incident_output = run_kubectl(f"exec {pod_name} -- cat /app/data/incident_{inv_id}.json 2>/dev/null")
                incident_data = json.loads(incident_output) if incident_output and 'Error' not in incident_output else None

                all_investigations.append({
                    'id': inv_id,
                    'meta': inv_meta,
                    'incident': incident_data,
                    'log': log_output if log_output and len(log_output.strip()) > 0 else None
                })

            return all_investigations
    except:
        pass

    return []


def parse_investigation_log(agent_log):
    """Parse agent investigation log into structured data."""
    investigation = {
        'active': False,
        'phase': 'idle',
        'evidence': [],
        'hypotheses': [],
        'verification': [],
        'rootCause': None,
        'remediation': [],
        'prUrl': None,
        'allLogs': []
    }

    if not agent_log:
        return investigation

    investigation['active'] = True
    lines = agent_log.split('\n')
    current_phase = None

    for line in lines:
        if not line.strip():
            continue

        # Store all logs
        investigation['allLogs'].append({
            'timestamp': datetime.now().isoformat(),
            'message': line.strip()
        })

        # Detect phases based on actual agent output
        if 'EVIDENCE GATHERING' in line or '🔍 EVIDENCE' in line:
            current_phase = 'evidence'
            investigation['phase'] = 'gathering_evidence'

        elif 'DIAGNOSIS' in line or '🧠 DIAGNOSIS' in line or 'Generating hypotheses' in line:
            current_phase = 'hypothesis'
            investigation['phase'] = 'analyzing'

        elif 'VERIFICATION' in line or '✅ VERIFICATION' in line or 'Testing hypothesis' in line:
            current_phase = 'verification'
            investigation['phase'] = 'analyzing'

        elif 'RECOVERY PROPOSAL' in line or '🛠️' in line or 'Drafting remediation' in line:
            current_phase = 'remediation'
            investigation['phase'] = 'creating_fix'

        # Parse content by phase
        if current_phase == 'evidence':
            if any(marker in line for marker in ['Getting', 'Gathering', '├─', '└─', '•', 'pods', 'events', 'deployments']):
                investigation['evidence'].append(line.strip())

        elif current_phase == 'hypothesis':
            if any(marker in line for marker in ['#1:', '#2:', '#3:', 'hypothesis', '✓ Generated']):
                investigation['hypotheses'].append(line.strip())

        elif current_phase == 'verification':
            if any(marker in line for marker in ['Testing hypothesis', 'Falsification', 'Result:', 'CONFIRMED', 'Reasoning:']):
                investigation['verification'].append(line.strip())
            if 'CONFIRMED' in line or 'status": "confirmed' in line:
                investigation['rootCause'] = 'Hypothesis confirmed - insufficient memory limits'

        elif current_phase == 'remediation':
            if any(marker in line for marker in ['Action Type:', 'Description:', 'Commands:', 'kubectl', 'rollback', 'Blast Radius']):
                investigation['remediation'].append(line.strip())
            if 'PR created:' in line or 'https://github.com' in line:
                import re
                url_match = re.search(r'https://github\.com[^\s]+', line)
                if url_match:
                    investigation['prUrl'] = url_match.group(0)

        # Detect completion
        if 'Investigation complete' in line or 'COMPLETED' in line or '🎉' in line:
            investigation['phase'] = 'completed'

    return investigation


def get_webhook_logs():
    """Get all investigations from webhook pod."""
    all_investigations = get_all_investigations()

    # If we have investigations from the new system, return them
    if all_investigations:
        investigations_list = []
        for inv in all_investigations:
            parsed_investigation = parse_investigation_log(inv.get('log', ''))
            investigations_list.append({
                'id': inv['id'],
                'meta': inv['meta'],
                'incident': inv['incident'],
                'investigation': parsed_investigation
            })
        return investigations_list

    # Fallback: no investigations found
    return []


@app.route('/')
def index():
    """Render the dashboard."""
    return render_template('gitops_monitor.html')


@app.route('/api/status')
def status():
    """Get current status of all components."""
    investigations_list = get_webhook_logs()
    approvals = get_approvals_data()
    alerts = get_prometheus_alerts()

    # Process each investigation
    for inv_data in investigations_list:
        incident = inv_data.get('incident')
        investigation = inv_data.get('investigation', {})

        # Validate incident against Prometheus alerts (only if Prometheus is accessible)
        if incident and alerts and len(alerts) > 0:
            incident_alertname = incident.get('alert_data', {}).get('labels', {}).get('alertname')
            has_matching_alert = any(
                alert.get('name') == incident_alertname
                for alert in alerts
            )

            if not has_matching_alert:
                # Alert has resolved - mark investigation as resolved
                investigation['resolved'] = True
                investigation['active'] = False
            else:
                investigation['active'] = True
        elif incident:
            investigation['active'] = True

        # Add remediation actions if pending
        if approvals:
            for approval in approvals:
                # Match approval to investigation by checking incident ID or service
                if approval.get('investigation_id') == inv_data['id']:
                    investigation['remediationActions'] = [approval]
                    if approval.get('status') == 'pending':
                        investigation['phase'] = 'creating_fix'

        # Store processed investigation back
        inv_data['investigation'] = investigation

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'pods': get_pod_status(),
        'alerts': alerts,
        'investigations': investigations_list  # Changed from single agentInvestigation to multiple
    })


if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════════════╗
║           GitOps Flow Monitoring Dashboard                     ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting monitoring server...

   Dashboard: http://localhost:5001
   API:       http://localhost:5001/api/status

Prerequisites:
  • kubectl configured and connected to cluster
  • GitHub token set in environment (optional)
  • Prometheus port-forward running on :9090 (optional)

────────────────────────────────────────────────────────────────
""")

    app.run(host='0.0.0.0', port=5001, debug=True)
