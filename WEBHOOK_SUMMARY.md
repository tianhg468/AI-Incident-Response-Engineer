# Production Webhook Server - Summary

## What Was Added

I've built you a complete production-level Slack webhook server so that interactive approval buttons actually work in Slack. Here's everything that was created:

## New Files Created

### 1. `webhook/slack_webhook.py`
**Flask web server** that:
- Receives button click events from Slack
- Validates requests using HMAC signature verification
- Updates approval state when users click buttons
- Responds to Slack with updated messages
- Provides API endpoints for the agent to check approval status

**Key endpoints:**
- `POST /slack/interactions` - Receives button clicks
- `GET /approvals/<id>` - Check approval status
- `GET /health` - Health check

### 2. `webhook/approval_manager.py`
**Approval state manager** that:
- Tracks approval requests (pending, approved, rejected)
- Provides thread-safe state management
- Allows agent to wait for approval with timeout
- Cleans up old approvals automatically

**Key methods:**
- `create_approval()` - Register new approval request
- `approve()` - Mark as approved
- `reject()` - Mark as rejected
- `wait_for_approval()` - Block until approved/rejected
- `get_status()` - Check current status

### 3. `webhook/__init__.py`
Package initialization file for the webhook module.

### 4. `WEBHOOK_SETUP.md`
**Complete setup guide** covering:
- Architecture diagram
- Step-by-step ngrok setup
- Slack app configuration
- Testing instructions
- Production deployment tips
- Troubleshooting guide

## Modified Files

### 1. `pyproject.toml`
Added Flask dependency:
```python
"flask>=3.0.0",
```

### 2. `mcp_servers/live/slack.py`
Updated `_request_approval()` to:
- Register approvals with the approval manager
- Return approval_id for tracking
- Allow agent to check status later

### 3. `PRODUCTION_SETUP.md`
Added **Phase 2b: Webhook Server Setup**:
- ngrok installation
- Starting webhook server
- Exposing server to internet
- Updating Slack app Request URL
- Environment variable configuration

## How It Works

### Without Webhook Server (Basic)
```
1. Agent requests approval
2. Posts message to Slack with buttons
3. User types 'y' in terminal
4. Agent proceeds
```

### With Webhook Server (Production)
```
1. Agent requests approval
2. Posts message to Slack with buttons
3. ApprovalManager creates approval record (status: pending)
4. Agent waits by polling ApprovalManager
5. User clicks button in Slack
6. Slack sends webhook to ngrok → Flask server
7. Flask validates signature
8. ApprovalManager updates status (approved/rejected)
9. Agent detects status change
10. Agent proceeds with remediation
11. Slack message updates to show who approved
```

## Setup Steps

### Quick Setup (5-10 minutes)

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Get Slack signing secret:**
   - Go to your Slack app → Basic Information → App Credentials
   - Copy the Signing Secret

3. **Update .env:**
   ```bash
   SLACK_SIGNING_SECRET=your-secret-here
   ```

4. **Start webhook server (Terminal 1):**
   ```bash
   python -m webhook.slack_webhook
   ```

5. **Start ngrok (Terminal 2):**
   ```bash
   brew install ngrok  # If not installed
   ngrok http 3001
   ```

6. **Update Slack app:**
   - Go to Interactivity & Shortcuts
   - Set Request URL to: `https://YOUR-NGROK-URL/slack/interactions`
   - Save (should verify successfully)

7. **Run agent (Terminal 3):**
   ```bash
   python -m agent.graph
   ```

8. **Click buttons in Slack!** ✨

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Machine                             │
│                                                              │
│  Terminal 1         Terminal 2         Terminal 3           │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐          │
│  │ Webhook  │      │  ngrok   │      │  Agent   │          │
│  │ Server   │◄─────┤  Tunnel  │      │ (Python) │          │
│  │:3001     │      │          │      │          │          │
│  └────┬─────┘      └────▲─────┘      └────┬─────┘          │
│       │                 │                  │                 │
│       │                 │                  │                 │
│       └────────┬────────┘                  │                 │
│                │                           │                 │
│         ┌──────┴────────┐           ┌─────┴──────┐         │
│         │ Approval      │◄──────────┤ MCP Slack  │         │
│         │ Manager       │           │ Server     │         │
│         │ (shared state)│           └─────┬──────┘         │
│         └───────────────┘                 │                 │
│                                           │                 │
└───────────────────────────────────────────┼─────────────────┘
                                            │
                                            ▼
                                    ┌───────────────┐
                                    │  Slack API    │
                                    │  (posts msg   │
                                    │  with buttons)│
                                    └───────┬───────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────┐
                    │  Slack App / #incidents channel   │
                    │                                   │
                    │  [✅ Approve] [❌ Reject]         │
                    │                                   │
                    │  User clicks button ──────────────┼──┐
                    └───────────────────────────────────┘  │
                                                            │
                                                            │
                                        Webhook POST        │
                                        to ngrok URL ───────┘
```

## Benefits

### Before (Terminal Approval Only)
- ❌ Have to watch terminal
- ❌ Can't approve remotely
- ❌ No audit trail in Slack
- ❌ Buttons in Slack don't work

### After (Production Webhook Server)
- ✅ Click buttons directly in Slack
- ✅ Approve from mobile/anywhere
- ✅ Full audit trail (who approved when)
- ✅ Message updates to show approval status
- ✅ Multiple team members can see/approve
- ✅ Professional production-ready setup

## Security Features

1. **Signature Verification**
   - All requests from Slack are verified using HMAC-SHA256
   - Prevents malicious actors from forging approval requests

2. **Timestamp Validation**
   - Rejects requests older than 5 minutes
   - Prevents replay attacks

3. **TLS/HTTPS**
   - ngrok provides HTTPS automatically
   - All communication encrypted

4. **Secret Management**
   - Signing secret stored in .env (not committed to git)
   - Bot token never exposed to client

## Production Deployment

For real production (not just demo):

1. **Deploy webhook server** to cloud:
   - AWS Lambda + API Gateway
   - Google Cloud Run
   - Heroku
   - Digital Ocean App Platform

2. **Use Redis** for approval state:
   - Replace in-memory dict with Redis
   - Allows multiple webhook instances
   - Persistent across restarts

3. **Add monitoring**:
   - Datadog/New Relic for metrics
   - Sentry for error tracking
   - CloudWatch/Stackdriver logs

4. **Use real domain**:
   - No ngrok in production
   - Custom domain with Let's Encrypt SSL

## Testing

Test the webhook server:

```bash
# Health check
curl http://localhost:3001/health

# List pending approvals
curl http://localhost:3001/approvals

# Check ngrok dashboard
open http://localhost:4040
```

## Troubleshooting

See **WEBHOOK_SETUP.md** for detailed troubleshooting including:
- Port already in use
- URL verification fails
- Buttons don't respond
- Agent doesn't detect approval

## Cost

**Free for demo/development:**
- ngrok free tier: ✅ Sufficient for testing
- No server costs (runs locally)

**Production:**
- Cloud hosting: ~$5-20/month
- Redis: ~$10/month (optional)
- Total: ~$15-30/month

## Next Steps

1. **Try it out!** Follow **WEBHOOK_SETUP.md**
2. **Test end-to-end** with a real incident
3. **Practice approving/rejecting** different actions
4. **Review the audit trail** in Slack

---

**You now have a production-level Slack approval workflow!** 🚀

The buttons actually work, approvals are tracked, and your team can approve incidents directly from Slack on any device.
