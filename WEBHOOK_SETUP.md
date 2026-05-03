# Slack Webhook Server Setup Guide

This guide shows you how to set up the production-level Slack webhook server so that interactive approval buttons actually work.

## What You'll Build

A webhook server that:
- Receives button click events from Slack
- Validates requests with signature verification
- Updates approval state in real-time
- Allows the agent to proceed automatically when approved
- Works seamlessly with your AI Incident Response workflow

## Prerequisites

```bash
# Install ngrok (for exposing local server to internet)
brew install ngrok

# Or download from https://ngrok.com/download
```

## Architecture

```
Slack App                                Your Machine
    │                                         │
    │  1. User clicks button               ┌─┴─────────────────┐
    │     in #incidents                     │  Agent (Python)   │
    │                                       │  Requests approval│
    │                                       └─┬─────────────────┘
    │                                         │
    │                                         ▼
    │                                   ┌─────────────────────┐
    │                                   │ Slack API (posts    │
    │                                   │ message with buttons│
    │                                   └─────────────────────┘
    │                                         │
    ├──2. Webhook POST request──────────►┌───┴──────────────────┐
    │  /slack/interactions                │  ngrok (tunnel)      │
    │  (via ngrok tunnel)                 │  https://xyz.ngrok.io│
    │                                     └───┬──────────────────┘
    │                                         │
    │                                         ▼
    │                                    ┌────────────────────────┐
    │                                    │ Flask Webhook Server   │
    │                                    │ localhost:3001         │
    │                                    └────┬───────────────────┘
    │                                         │
    │                                         ▼
    │                                    ┌────────────────────────┐
    │                                    │  Approval Manager      │
    │                                    │  (in-memory state)     │
    │                                    └────┬───────────────────┘
    │                                         │
    │                                         ▼
    └─3. Response───────────────────────Agent checks approval
       "Approved by alice"                and proceeds
```

## Step-by-Step Setup

### Step 1: Install Dependencies

```bash
cd /path/to/agentic_ai
pip install -e .
```

This will install Flask and other webhook server dependencies.

### Step 2: Get Slack Signing Secret

1. Go to https://api.slack.com/apps
2. Click your **Incident Response Bot** app
3. In left sidebar, click **Basic Information**
4. Scroll to **App Credentials**
5. Find **Signing Secret**
6. Click **Show** and copy the secret

### Step 3: Update .env File

Add the signing secret to your `.env`:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=#incidents
SLACK_SIGNING_SECRET=your_signing_secret_here  # Add this line
```

### Step 4: Start the Webhook Server

Open a **new terminal window** and run:

```bash
cd /path/to/agentic_ai
python -m webhook.slack_webhook
```

You should see:

```
╔════════════════════════════════════════════════════════════════╗
║          Slack Webhook Server - Production Mode               ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting webhook server...

   Host: 0.0.0.0
   Port: 3001

   Endpoints:
   • POST /slack/interactions  - Receives button clicks
   • POST /slack/events        - Receives Slack events
   • GET  /approvals/<id>      - Check approval status
   • GET  /health              - Health check

⚠️  IMPORTANT: You need to expose this server to the internet
   using ngrok or similar so Slack can reach it.

   Run in another terminal:
   $ ngrok http 3001

════════════════════════════════════════════════════════════════

Waiting for Slack events...
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:3001
 * Running on http://192.168.1.x:3001
```

**Leave this terminal running** - this is your webhook server.

### Step 5: Expose Server with ngrok

Open **another new terminal window** and run:

```bash
ngrok http 3001
```

You'll see:

```
ngrok

Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc-123-xyz.ngrok-free.app -> http://localhost:3001

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

**Copy the HTTPS URL** - you'll need it in the next step!

Example: `https://abc-123-xyz.ngrok-free.app`

**Leave this terminal running** - this is your ngrok tunnel.

### Step 6: Configure Slack App Request URL

1. Go to https://api.slack.com/apps
2. Click your **Incident Response Bot** app
3. In left sidebar, click **Interactivity & Shortcuts**
4. Toggle **Interactivity** to **On**
5. In **Request URL** field, enter:
   ```
   https://YOUR-NGROK-URL/slack/interactions
   ```
   Example: `https://abc-123-xyz.ngrok-free.app/slack/interactions`
6. Click **Save Changes**

Slack will send a verification request. If everything is configured correctly, you'll see:

✅ **Your Request URL has been verified**

If you see an error, check:
- Is the webhook server running? (terminal 1)
- Is ngrok running? (terminal 2)
- Did you copy the full ngrok HTTPS URL?
- Is the `/slack/interactions` path included?

### Step 7: Test the Integration

Now test that everything works:

#### Terminal 3: Run the Agent

```bash
cd /path/to/agentic_ai

# Make sure MODE=live in .env
python -m agent.graph
```

The agent will:
1. Investigate the incident
2. Propose a remediation
3. Post approval request to Slack **with working buttons**
4. Wait for approval

#### In Slack (#incidents channel)

You should see a message like:

```
🔒 Approval Required: rollback

Description:
Rollback deployment to restore 256Mi memory limit

[✅ Approve]  [❌ Reject]
```

**Click the ✅ Approve button**

#### What Happens Next

1. **Slack sends webhook** → ngrok → Flask server
2. **Flask server validates** the request signature
3. **Approval manager updates** state to "approved"
4. **Agent detects approval** and proceeds with remediation
5. **Message updates** to show "✅ Approved by your-username"

You'll see in the webhook server terminal:

```
📨 Received Slack interaction:
   Type: block_actions
   User: alice
   Action: approve_action = approve
✅ APPROVED by alice
```

And in the agent terminal:

```
✅ Action approved via Slack by alice

⚙️ EXECUTION: Executing remediation...
   $ kubectl rollout undo deployment/demo-app
   ✅ Deployment rolled back
```

## Production Deployment

For production use, instead of ngrok:

1. **Deploy webhook server** to a cloud platform (AWS, GCP, Heroku, etc.)
2. **Use a real domain** with HTTPS (e.g., `https://webhooks.yourcompany.com`)
3. **Add Redis** for approval state persistence (replace in-memory store)
4. **Set up monitoring** for the webhook server
5. **Configure firewall** to only allow Slack IPs

### Example Production Setup

```python
# webhook/approval_manager.py (production version)
import redis

class ApprovalManager:
    def __init__(self):
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=6379,
            decode_responses=True
        )

    def create_approval(self, approval_id, action_type, description):
        self.redis.setex(
            f"approval:{approval_id}",
            300,  # 5 minute TTL
            json.dumps({
                "status": "pending",
                "action_type": action_type,
                "description": description
            })
        )
```

## Troubleshooting

### Webhook Server Won't Start

**Error**: `Address already in use`

```bash
# Find what's using port 3001
lsof -ti:3001

# Kill the process
kill -9 $(lsof -ti:3001)

# Try again
python -m webhook.slack_webhook
```

### Slack URL Verification Fails

**Error**: `Your Request URL didn't respond with the correct verification token`

Check:
1. ✅ Webhook server is running
2. ✅ ngrok is running and showing connection
3. ✅ You copied the full ngrok HTTPS URL (not HTTP)
4. ✅ You added `/slack/interactions` to the end
5. ✅ Your `.env` has `SLACK_SIGNING_SECRET` set

### Buttons Don't Work

**Symptom**: Clicking buttons doesn't do anything

Debug checklist:
1. Check webhook server logs - do you see the POST request?
2. Check ngrok dashboard - http://localhost:4040 - do you see the request?
3. Check Slack App settings - is Request URL still valid?
4. Try clicking **Test URL** in Slack app settings

### Agent Doesn't Detect Approval

**Symptom**: Agent waits forever even after clicking Approve

Check:
1. Is the approval_id the same? (should be the Slack message timestamp)
2. Check webhook server logs - was approval registered?
3. Try: `curl http://localhost:3001/approvals` to see pending approvals

## Commands Reference

```bash
# Start webhook server
python -m webhook.slack_webhook

# Start ngrok tunnel
ngrok http 3001

# Check ngrok status (open in browser)
open http://localhost:4040

# Test webhook server health
curl http://localhost:3001/health

# List pending approvals
curl http://localhost:3001/approvals

# Check specific approval
curl http://localhost:3001/approvals/<approval-id>

# View ngrok logs
# Go to http://localhost:4040 in browser
```

## Next Steps

Once the webhook server is running:

1. ✅ Follow PRODUCTION_SETUP.md to complete infrastructure setup
2. ✅ Test end-to-end incident response workflow
3. ✅ Practice approving/rejecting different actions
4. ✅ Review post-mortems in the dashboard

---

**You now have production-level Slack approvals with working interactive buttons!** 🎉
