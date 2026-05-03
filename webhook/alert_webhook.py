"""Alert webhook server for receiving Prometheus AlertManager alerts.

This server receives alerts from Prometheus and triggers the AI agent
to investigate and remediate incidents automatically.
"""

import os
import json
import hmac
import hashlib
import subprocess
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode()
AGENT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        "service": "alert-webhook",
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
    """Process a single alert and trigger the agent if needed.

    Args:
        alert: Alert data from AlertManager
    """
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
    """Trigger the AI agent to investigate an incident.

    Args:
        service: Service name
        alert_type: Type of alert (oomkilled, crashloop, etc.)
        alert: Full alert data
    """
    try:
        # Create incident file with alert data for the agent
        incident_data = {
            "service": service,
            "alert_type": alert_type,
            "severity": "critical",
            "triggered_at": datetime.now().isoformat(),
            "alert_data": alert
        }

        incident_file = os.path.join(AGENT_REPO, "data", "current_incident.json")
        os.makedirs(os.path.dirname(incident_file), exist_ok=True)

        with open(incident_file, 'w') as f:
            json.dump(incident_data, f, indent=2)

        print(f"   💾 Saved incident data to {incident_file}")

        # Run the agent in background
        print(f"   🚀 Starting agent investigation...")
        result = subprocess.Popen(
            ["python", "-m", "agent.graph"],
            cwd=AGENT_REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"   ✓ Agent started (PID: {result.pid})")
        print(f"   📊 Agent will investigate and create PR if fix is identified")

    except Exception as e:
        print(f"   ❌ Error triggering agent: {e}")


def run_alert_webhook(host="0.0.0.0", port=8080):
    """Run the alert webhook server."""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║        Alert Webhook Server - Production Mode                  ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting alert webhook server...

   Host: {host}
   Port: {port}

   Endpoints:
   • POST /alerts   - Receives Prometheus alerts
   • GET  /health   - Health check

⚠️  IMPORTANT: Configure Prometheus AlertManager to send alerts here:

   In alertmanager.yml:
   receivers:
     - name: 'ai-agent-webhook'
       webhook_configs:
         - url: 'http://{host}:{port}/alerts'
           bearer_token: '${{WEBHOOK_SECRET}}'

════════════════════════════════════════════════════════════════

Waiting for alerts...
""")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_alert_webhook()
