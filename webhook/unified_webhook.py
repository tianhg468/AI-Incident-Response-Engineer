"""Unified webhook server for both Prometheus alerts and Slack interactions.

Combines alert_webhook and slack_webhook into a single service.
"""

import os
import json
import hmac
import hashlib
import subprocess
import time
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

from webhook.approval_manager import get_approval_manager

load_dotenv()

app = Flask(__name__)

# Disable Flask's default logging for health checks
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").encode()
AGENT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Approval manager for Slack interactions
approval_manager = get_approval_manager()


# ============================================================================
# ALERT WEBHOOK (Prometheus)
# ============================================================================

def verify_bearer_token(request):
    """Verify the bearer token from AlertManager."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header[7:]  # Remove "Bearer " prefix
    expected_token = WEBHOOK_SECRET.decode()

    return hmac.compare_digest(token, expected_token)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "unified-webhook",
        "version": "1.0.0"
    })


@app.route("/alerts", methods=["POST"])
def receive_alert():
    """Receive alerts from Prometheus AlertManager."""

    # Verify authentication
    if not verify_bearer_token(request):
        print("❌ Invalid bearer token")
        return jsonify({"error": "Unauthorized"}), 401

    # Parse alert payload
    payload = request.json

    print(f"\n🚨 Received alert from Prometheus:")
    print(f"   Receiver: {payload.get('receiver')}")
    print(f"   Status: {payload.get('status')}")
    print(f"   Alerts: {len(payload.get('alerts', []))}")

    # Process each alert
    for alert in payload.get("alerts", []):
        process_alert(alert)

    return jsonify({"status": "ok", "processed": len(payload.get("alerts", []))})


def process_alert(alert: dict):
    """Process a single alert and trigger the agent if needed."""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status = alert.get("status", "unknown")

    alert_name = labels.get("alertname", "unknown")
    alert_type = labels.get("alert_type", "unknown")
    severity = labels.get("severity", "unknown")
    service = labels.get("service") or labels.get("pod", "unknown").split("-")[0]

    print(f"\n📋 Alert Details:")
    print(f"   Name: {alert_name}")
    print(f"   Type: {alert_type}")
    print(f"   Severity: {severity}")
    print(f"   Service: {service}")
    print(f"   Status: {status}")
    print(f"   Summary: {annotations.get('summary', 'N/A')}")

    # Only trigger agent for firing critical alerts
    if status == "firing" and severity == "critical":
        print(f"\n🤖 Triggering AI agent for {service}...")
        trigger_agent(service, alert_type, alert)
    elif status == "resolved":
        print(f"   ✓ Alert resolved, no action needed")
    else:
        print(f"   ⏸️  Severity {severity}, not triggering agent")


def trigger_agent(service: str, alert_type: str, alert: dict):
    """Trigger the AI agent to investigate an incident."""
    try:
        # Generate unique investigation ID
        import hashlib
        incident_hash = hashlib.md5(f"{service}_{alert_type}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        investigation_id = f"{service}_{alert_type}_{incident_hash}"

        # Create incident file with alert data for the agent
        incident_data = {
            "investigation_id": investigation_id,
            "service": service,
            "alert_type": alert_type,
            "severity": "critical",
            "triggered_at": datetime.now().isoformat(),
            "status": "investigating",
            "alert_data": alert
        }

        data_dir = os.path.join(AGENT_REPO, "data")
        os.makedirs(data_dir, exist_ok=True)

        # Save individual incident file
        incident_file = os.path.join(data_dir, f"incident_{investigation_id}.json")
        with open(incident_file, 'w') as f:
            json.dump(incident_data, f, indent=2)

        # Also save as current_incident.json for backward compatibility
        current_incident_file = os.path.join(data_dir, "current_incident.json")
        with open(current_incident_file, 'w') as f:
            json.dump(incident_data, f, indent=2)

        # Update investigations index
        investigations_file = os.path.join(data_dir, "investigations.json")
        investigations = {}
        if os.path.exists(investigations_file):
            with open(investigations_file, 'r') as f:
                investigations = json.load(f)

        investigations[investigation_id] = {
            "triggered_at": incident_data["triggered_at"],
            "service": service,
            "alert_type": alert_type,
            "status": "investigating"
        }

        with open(investigations_file, 'w') as f:
            json.dump(investigations, f, indent=2)

        print(f"   💾 Saved incident data: {investigation_id}")

        # Redirect agent output to unique log file
        agent_log_file = os.path.join(data_dir, f"investigation_{investigation_id}.log")
        agent_log = open(agent_log_file, 'w')

        # Run the agent in background
        print(f"   🚀 Starting agent investigation...")
        print(f"   📝 Agent logs: {agent_log_file}")
        result = subprocess.Popen(
            ["python", "-m", "agent.graph"],
            cwd=AGENT_REPO,
            stdout=agent_log,
            stderr=subprocess.STDOUT,
            text=True
        )

        print(f"   ✓ Agent started (PID: {result.pid})")
        print(f"   📊 Investigation ID: {investigation_id}")
        print(f"   📋 Monitor: kubectl exec <pod> -- tail -f /app/data/investigation_{investigation_id}.log")

    except Exception as e:
        print(f"   ❌ Error triggering agent: {e}")


# ============================================================================
# SLACK WEBHOOK (Interactive Components)
# ============================================================================

def verify_slack_signature(request):
    """Verify that the request came from Slack."""
    if not SLACK_SIGNING_SECRET:
        # In development, skip verification if no secret configured
        return True

    # Get the signature from the request headers
    slack_signature = request.headers.get("X-Slack-Signature", "")
    slack_timestamp = request.headers.get("X-Slack-Request-Timestamp", "")

    # Prevent replay attacks
    if abs(time.time() - int(slack_timestamp)) > 60 * 5:
        return False

    # Verify the signature
    sig_basestring = f"v0:{slack_timestamp}:{request.get_data(as_text=True)}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET,
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)


@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    """Handle Slack interactive component events (button clicks)."""

    # Verify the request came from Slack
    if not verify_slack_signature(request):
        print("❌ Invalid Slack signature")
        return jsonify({"error": "Invalid signature"}), 403

    # Parse the payload
    payload = json.loads(request.form.get("payload", "{}"))

    # Log the interaction
    print(f"\n📨 Received Slack interaction:")
    print(f"   Type: {payload.get('type')}")
    print(f"   User: {payload.get('user', {}).get('name')}")

    # Handle block actions (button clicks)
    if payload.get("type") == "block_actions":
        return handle_block_actions(payload)

    return jsonify({"status": "ok"})


def handle_block_actions(payload):
    """Handle button clicks from Slack messages."""
    actions = payload.get("actions", [])
    user = payload.get("user", {})

    for action in actions:
        action_id = action.get("action_id")
        action_value = action.get("value")

        print(f"   Action: {action_id} = {action_value}")

        # Handle approval actions
        if action_id == "approve_action":
            approval_id = action_value
            approval_manager.approve(
                approval_id,
                approved_by=user.get('name', 'slack_user')
            )
            print(f"   ✅ Approved: {approval_id}")

            return jsonify({
                "text": f"✅ Approved by {user.get('name')}",
                "replace_original": True
            })

        elif action_id == "reject_action":
            approval_id = action_value
            approval_manager.reject(
                approval_id,
                rejected_by=user.get('name', 'slack_user')
            )
            print(f"   ❌ Rejected: {approval_id}")

            return jsonify({
                "text": f"❌ Rejected by {user.get('name')}",
                "replace_original": True
            })

    return jsonify({"status": "ok"})


@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events (for URL verification)."""
    payload = request.json

    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload.get("challenge")})

    return jsonify({"status": "ok"})


# ============================================================================
# MAIN
# ============================================================================

def run_unified_webhook(host="0.0.0.0", port=8080):
    """Run the unified webhook server."""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║        Unified Webhook Server - Production Mode                ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting unified webhook server...

   Host: {host}
   Port: {port}

   Endpoints:
   • POST /alerts                - Receives Prometheus alerts
   • POST /slack/interactions    - Receives Slack button clicks
   • POST /slack/events          - Receives Slack events
   • GET  /health                - Health check

⚠️  Configuration:

   AlertManager:
   receivers:
     - name: 'ai-agent-webhook'
       webhook_configs:
         - url: 'http://{host}:{port}/alerts'
           bearer_token: '${{WEBHOOK_SECRET}}'

   Slack App Interactivity URL:
   https://YOUR-NGROK-URL/slack/interactions

════════════════════════════════════════════════════════════════

Waiting for alerts and Slack interactions...
""")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_unified_webhook()
