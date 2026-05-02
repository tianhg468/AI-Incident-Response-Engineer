"""Slack webhook server for handling interactive button clicks.

This server receives events from Slack when users click approval buttons
and updates the approval state so the agent can proceed.
"""

import os
import json
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from webhook.approval_manager import ApprovalManager

load_dotenv()

app = Flask(__name__)
approval_manager = ApprovalManager()

# Slack signing secret for verifying requests
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").encode()


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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "slack-webhook",
        "version": "1.0.0"
    })


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
    message = payload.get("message", {})

    for action in actions:
        action_id = action.get("action_id")
        action_value = action.get("value")

        print(f"   Action: {action_id} = {action_value}")

        # Handle approval actions
        if action_id == "approve_action":
            handle_approval(payload, user, approved=True)
        elif action_id == "reject_action":
            handle_approval(payload, user, approved=False)

    # Update the message to show the action was taken
    return jsonify({
        "replace_original": "true",
        "text": message.get("text", ""),
        "blocks": update_message_with_response(payload, actions[0] if actions else None)
    })


def handle_approval(payload, user, approved):
    """Handle approval or rejection of an action."""
    username = user.get("name", "unknown")

    # Extract the incident/action ID from the message
    # We'll use the message timestamp as a unique ID
    message_ts = payload.get("message", {}).get("ts", "")

    if approved:
        print(f"✅ APPROVED by {username}")
        approval_manager.approve(message_ts, username)
    else:
        print(f"❌ REJECTED by {username}")
        approval_manager.reject(message_ts, username)


def update_message_with_response(payload, action):
    """Update the Slack message to show the approval/rejection."""
    original_blocks = payload.get("message", {}).get("blocks", [])
    user = payload.get("user", {}).get("name", "User")

    # Remove the action buttons
    updated_blocks = [b for b in original_blocks if b.get("type") != "actions"]

    # Add a context block showing who approved/rejected
    if action:
        action_id = action.get("action_id")
        emoji = "✅" if action_id == "approve_action" else "❌"
        status = "Approved" if action_id == "approve_action" else "Rejected"

        updated_blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{status}* by {user} at <!date^{int(time.time())}^{{time}}|{time.strftime('%H:%M:%S')}>"
                }
            ]
        })

    return updated_blocks


@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack Events API (for URL verification and future events)."""
    payload = request.json

    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload.get("challenge")})

    # Handle other events
    return jsonify({"status": "ok"})


@app.route("/approvals/<approval_id>", methods=["GET"])
def get_approval_status(approval_id):
    """API endpoint for the agent to check approval status."""
    status = approval_manager.get_status(approval_id)
    return jsonify(status)


@app.route("/approvals", methods=["GET"])
def list_approvals():
    """List all pending approvals."""
    approvals = approval_manager.list_pending()
    return jsonify({"approvals": approvals})


def run_webhook_server(host="0.0.0.0", port=3001):
    """Run the webhook server."""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║          Slack Webhook Server - Production Mode               ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting webhook server...

   Host: {host}
   Port: {port}

   Endpoints:
   • POST /slack/interactions  - Receives button clicks
   • POST /slack/events        - Receives Slack events
   • GET  /approvals/<id>      - Check approval status
   • GET  /health              - Health check

⚠️  IMPORTANT: You need to expose this server to the internet
   using ngrok or similar so Slack can reach it.

   Run in another terminal:
   $ ngrok http {port}

   Then update your Slack app's Request URL to:
   https://YOUR-NGROK-URL/slack/interactions

════════════════════════════════════════════════════════════════

Waiting for Slack events...
""")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_webhook_server()
