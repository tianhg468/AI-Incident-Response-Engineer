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


def get_webhook_logs():
    """Get recent webhook logs."""
    output = run_kubectl("logs deployment/agent-webhook --tail=200")
    lines = output.split('\n')

    # Parse for agent investigation details
    investigation = {
        'active': False,
        'phase': 'idle',
        'evidence': [],
        'hypotheses': [],
        'rootCause': None,
        'fix': None,
        'prUrl': None,
        'allLogs': []
    }

    current_phase = None

    for line in lines:
        # Filter out health check logs and Flask server noise
        if any(skip in line for skip in [
            'GET /health HTTP/1.1',
            '10.0.93.144',
            '10.0.118.207',
            'WARNING: This is a development server',
            'Running on http://',
            'Press CTRL+C to quit'
        ]):
            continue

        # Store all logs (excluding health checks)
        if line.strip():
            investigation['allLogs'].append({
                'timestamp': datetime.now().isoformat(),
                'message': line.strip()
            })

        # Detect investigation start
        if '🤖 Triggering AI agent' in line:
            investigation['active'] = True
            investigation['phase'] = 'investigating'

        # Parse evidence gathering
        if '🔍' in line or 'PHASE 1' in line or 'Evidence Gathering' in line:
            current_phase = 'evidence'
            investigation['phase'] = 'gathering_evidence'

        if current_phase == 'evidence':
            if '✓' in line or 'Found' in line or 'Detected' in line:
                investigation['evidence'].append(line.strip())

        # Parse hypothesis generation
        if '🧠' in line or 'PHASE 2' in line or 'Root Cause' in line or 'hypothesis' in line.lower():
            current_phase = 'analysis'
            investigation['phase'] = 'analyzing'

        if current_phase == 'analysis':
            if 'H1:' in line or 'H2:' in line or 'H3:' in line:
                investigation['hypotheses'].append(line.strip())
            if 'CONFIRMED' in line or 'Root cause:' in line:
                investigation['rootCause'] = line.strip()

        # Parse fix creation
        if '📝' in line or 'PHASE 3' in line or 'Creating Fix' in line or 'Creating PR' in line:
            current_phase = 'fixing'
            investigation['phase'] = 'creating_fix'

        if current_phase == 'fixing':
            if 'Branch:' in line or 'Files changed:' in line or 'Changes:' in line:
                if not investigation['fix']:
                    investigation['fix'] = []
                investigation['fix'].append(line.strip())
            if 'PR created:' in line or 'https://github.com' in line:
                # Extract PR URL
                import re
                url_match = re.search(r'https://github\.com[^\s]+', line)
                if url_match:
                    investigation['prUrl'] = url_match.group(0)

        # Detect completion
        if 'Investigation complete' in line or '🎉' in line:
            investigation['phase'] = 'completed'

    return investigation


def get_github_prs():
    """Get open PRs from GitHub."""
    if not GITHUB_TOKEN:
        return []

    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/pulls?state=open'
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            prs = []
            for pr in response.json():
                prs.append({
                    'number': pr['number'],
                    'title': pr['title'],
                    'author': pr['user']['login'],
                    'created': pr['created_at'],
                    'url': pr['html_url'],
                    'isAI': '[AI Agent]' in pr['title'] or '🤖' in pr['title']
                })
            return prs
    except Exception as e:
        print(f"Error fetching PRs: {e}")

    return []


def get_github_actions():
    """Get recent GitHub Actions workflow runs."""
    if not GITHUB_TOKEN:
        return []

    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/runs?per_page=5'
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            runs = []
            for run in response.json().get('workflow_runs', []):
                runs.append({
                    'id': run['id'],
                    'name': run['name'],
                    'status': run['status'],
                    'conclusion': run['conclusion'],
                    'created': run['created_at'],
                    'url': run['html_url']
                })
            return runs
    except Exception as e:
        print(f"Error fetching actions: {e}")

    return []


@app.route('/')
def index():
    """Render the dashboard."""
    return render_template('gitops_monitor.html')


@app.route('/api/status')
def status():
    """Get current status of all components."""
    investigation = get_webhook_logs()
    incident_data = get_incident_data()
    approvals = get_approvals_data()
    alerts = get_prometheus_alerts()

    # Optionally validate incident against Prometheus alerts (only if Prometheus is accessible)
    if incident_data and alerts and len(alerts) > 0:
        # Prometheus is accessible - validate that incident still has active alert
        incident_alertname = incident_data.get('alert_data', {}).get('labels', {}).get('alertname')
        has_matching_alert = any(
            alert.get('name') == incident_alertname
            for alert in alerts
        )

        if not has_matching_alert:
            # Alert has resolved - clear the incident
            incident_data = None

    # Merge incident data into investigation
    if incident_data:
        investigation['incidentData'] = incident_data
        investigation['active'] = True

        # Determine phase based on available data
        if approvals and approvals[0].get('status') == 'pending':
            # Has pending approvals = reached remediation phase
            investigation['phase'] = 'creating_fix'
            investigation['remediationActions'] = approvals
        elif not investigation['phase'] or investigation['phase'] == 'idle':
            # Calculate time since investigation started
            triggered_at = incident_data.get('triggered_at')
            if triggered_at:
                from datetime import datetime as dt
                start_time = dt.fromisoformat(triggered_at.replace('Z', '+00:00'))
                elapsed = (dt.now(start_time.tzinfo) - start_time).total_seconds()

                # Estimate phase based on elapsed time
                if elapsed < 30:
                    investigation['phase'] = 'gathering_evidence'
                elif elapsed < 60:
                    investigation['phase'] = 'analyzing'
                else:
                    investigation['phase'] = 'creating_fix'
    else:
        # No valid incident - clear investigation state
        investigation['active'] = False
        investigation['phase'] = 'idle'
        investigation['incidentData'] = None
        investigation['remediationActions'] = None

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'pods': get_pod_status(),
        'alerts': alerts,
        'agentInvestigation': investigation,
        'pullRequests': get_github_prs(),
        'githubActions': get_github_actions()
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
