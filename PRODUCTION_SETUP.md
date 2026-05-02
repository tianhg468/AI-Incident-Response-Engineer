# Production Setup Guide

Complete step-by-step guide to set up the AI Incident Response Engineer for production use with all integrations.

## Overview

This guide will help you set up:
- ✅ Local Kubernetes cluster (minikube)
- ✅ GitHub repository with demo app
- ✅ Slack workspace and bot
- ✅ Grafana for observability
- ✅ Live mode configuration
- ✅ End-to-end testing

**Time required:** 1-2 hours

---

## Prerequisites

Install these tools first:

```bash
# macOS
brew install docker kubectl minikube grafana node

# Verify installations
docker --version
kubectl version --client
minikube version
grafana-server --version
node --version
```

---

## Phase 1: GitHub Setup (15 min)

### 1.1 Create Repository

1. Go to https://github.com/new
2. Repository name: `ai-incident-response-demo`
3. Description: `Production demo for AI incident response`
4. **Public** repository
5. Do NOT initialize with README
6. Click **Create repository**

### 1.2 Generate Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Token name: `AI Incident Response Production`
4. Expiration: `90 days`
5. Select scopes:
   - ✅ `repo` (Full control)
   - ✅ `workflow` (Update workflows)
   - ✅ `read:org` (Read org data)
6. Click **Generate token**
7. **SAVE THIS TOKEN** - copy it now (starts with `ghp_`)

### 1.3 Push Demo App

```bash
cd demo-app

# Initialize git
git init
git add .
git commit -m "feat: Initial production demo app"

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/ai-incident-response-demo.git

# Push to GitHub
git branch -M main
git push -u origin main

# Create commit history
echo "// Version 2.0" >> app.js
git add app.js
git commit -m "feat: Add new features for v2"
git push

# This commit causes OOM (intentional for demo)
sed -i '' 's/memory: "256Mi"/memory: "64Mi"/g' k8s/deployment.yaml
git add k8s/deployment.yaml
git commit -m "perf: Reduce memory limits to save costs"
git push

cd ..
```

### 1.4 Verify

Check https://github.com/YOUR_USERNAME/ai-incident-response-demo

You should see:
- ✅ 3 commits
- ✅ All files (app.js, Dockerfile, k8s/, etc.)
- ✅ GitHub Actions workflow

---

## Phase 2: Slack Setup (20 min)

### 2.1 Create Slack Workspace

If you don't have a Slack workspace:

1. Go to https://slack.com/create
2. Enter your email
3. Check your email for verification code
4. Workspace name: `AI Incident Response`
5. Channel name: `incidents`
6. Skip inviting team members

### 2.2 Create Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. App Name: `Incident Response Bot`
4. Pick your workspace
5. Click **Create App**

### 2.3 Configure Bot Permissions

1. In left sidebar, click **OAuth & Permissions**
2. Scroll to **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add these scopes:
   - `chat:write` - Post messages to channels
   - `chat:write.public` - Post to public channels without joining
   - `channels:read` - View basic channel info
   - `channels:history` - Read message history (optional)
   - `users:read` - Read user information (optional)
4. Scroll to top, click **Install to [Your Workspace Name]**
   - The button will show your actual workspace name (e.g., "Install to AI Incident Response")
5. Click **Allow** on the permission screen
6. **SAVE THE BOT TOKEN** - You'll see it on the next page (starts with `xoxb-`)
   - Copy this token immediately and save it to your `.env` file

### 2.4 Enable Interactive Components (For Approval Buttons)

Interactive components (buttons) are enabled here, not via OAuth scopes.

1. In left sidebar, click **Interactivity & Shortcuts**
2. Turn on **Interactivity**
3. Request URL: For now, use a placeholder like `https://example.com/slack/interactions`
   - **Note**: For this demo, we won't set up a webhook server to receive button clicks
   - The bot will still post messages with buttons, but you'll approve actions via the terminal instead
   - In production, you'd set up a webhook server to handle button clicks
4. Click **Save Changes**

**For this demo:** You don't need to set up the webhook server. The agent will request approval via:
- Terminal prompt: "Do you approve? [y/N]"
- Slack message (informational, buttons won't be functional without webhook)

### 2.5 Create #incidents Channel

1. In Slack, create channel: `#incidents`
2. Invite bot: `/invite @Incident Response Bot`

### 2.6 Test Bot

```bash
# Test message posting
curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer xoxb-YOUR-BOT-TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "#incidents",
    "text": "🤖 Bot is online and ready!"
  }'

# Should return: {"ok": true, "message": {...}}
```

---

## Phase 3: Grafana Setup (15 min)

### 3.1 Install and Start Grafana

```bash
# macOS
brew install grafana
brew services start grafana

# Or run directly in foreground
grafana-server --config=/opt/homebrew/etc/grafana/grafana.ini
```

### 3.2 Access Grafana

1. Open http://localhost:3000
2. Login:
   - Username: `admin`
   - Password: `admin`
3. Change password when prompted (use a secure password)

### 3.3 Create Service Account & API Key

1. Click **☰** (menu) → **Administration** → **Service accounts**
2. Click **Add service account**
3. Display name: `AI Incident Response`
4. Role: **Viewer**
5. Click **Create**
6. Click **Add service account token**
7. Name: `Production API Key`
8. Click **Generate token**
9. **SAVE THIS TOKEN** (starts with `glsa_`)

### 3.4 Set Up Prometheus Data Source

```bash
# Deploy Prometheus to minikube
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/prometheus

# Port-forward Prometheus
kubectl port-forward svc/prometheus-server 9090:80 &
```

In Grafana:
1. **☰** → **Connections** → **Data sources**
2. **Add data source** → **Prometheus**
3. URL: `http://localhost:9090`
4. Click **Save & test**
5. Should show ✅ "Data source is working"

---

## Phase 4: Kubernetes Setup (10 min)

### 4.1 Start Minikube

```bash
# Start with sufficient resources
minikube start --memory=4096 --cpus=2 --driver=docker

# Enable metrics server
minikube addons enable metrics-server

# Verify
kubectl get nodes
# Should show: minikube   Ready    control-plane   ...
```

### 4.2 Deploy Demo App

```bash
cd demo-app

# Run automated setup
chmod +x setup.sh
./setup.sh

# Wait for deployment
kubectl wait --for=condition=available --timeout=120s deployment/demo-app

# Check status
kubectl get pods
# Should show 3 pods in Running state
```

### 4.3 Test Application

```bash
# Get service URL
SERVICE_URL=$(minikube service demo-app --url)
echo $SERVICE_URL

# Test health endpoint
curl $SERVICE_URL/health

# Should return JSON with memory usage, uptime, etc.
```

---

## Phase 5: Configure Environment Variables (5 min)

Update your main project `.env` file:

```bash
cd ..  # Back to main project
nano .env
```

Add/update these values:

```bash
# ============================================
# PRODUCTION CONFIGURATION
# ============================================

# Mode
MODE=live

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE

# GitHub (from Phase 1)
GITHUB_TOKEN=ghp_YOUR-GITHUB-TOKEN
GITHUB_ORG=YOUR-GITHUB-USERNAME

# Kubernetes
KUBECONFIG=~/.kube/config
K8S_NAMESPACE=default

# Slack (from Phase 2)
SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-TOKEN
SLACK_CHANNEL=#incidents

# Grafana (from Phase 3)
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=glsa_YOUR-GRAFANA-TOKEN

# Checkpoint
CHECKPOINT_MODE=sqlite
CHECKPOINT_DB_PATH=./data/checkpoints.db
```

Save and exit.

---

## Phase 6: Test Live Mode (15 min)

### 6.1 Verify Configuration

```bash
# Check all environment variables are set
source .env

echo "MODE: $MODE"
echo "GITHUB_TOKEN: ${GITHUB_TOKEN:0:10}..."
echo "SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN:0:10}..."
echo "GRAFANA_API_KEY: ${GRAFANA_API_KEY:0:10}..."

# All should show values (not empty)
```

### 6.2 Test Kubernetes Access

```bash
# Verify kubectl works
kubectl get pods -n default

# Should show demo-app pods
```

### 6.3 Trigger an Incident

```bash
cd demo-app

# Trigger OOM by lowering memory limits
./incidents/trigger-oom.sh

# Wait 30 seconds for pods to start crashing
sleep 30

# Check pod status
kubectl get pods
# Should show OOMKilled or CrashLoopBackOff
```

### 6.4 Run the AI Agent (PRODUCTION MODE!)

```bash
cd ..

# Run in live mode
python -m agent.graph
```

**What you should see:**

```
🚀 Starting incident response workflow (LIVE MODE)...
📝 Investigation ID: incident_xxxxxxxx

🔔 INTAKE: Processing alert...
  📌 Service: demo-app
  📌 Severity: high

🔍 EVIDENCE GATHERING: Collecting from LIVE sources...
  ✅ Kubernetes: Connected
     • 3 pods found
     • 2 pods OOMKilled
     • Events: 6 OOMKilled events
  ✅ GitHub: Connected
     • Repository: ai-incident-response-demo
     • Latest commit: abc123 "perf: Reduce memory limits"
     • Author: YOUR_NAME
     • Time: 15 minutes ago
  ✅ Slack: Connected to #incidents
  ✅ Grafana: Connected
     • Memory usage trending up before crash

🧠 DIAGNOSIS: Generating hypotheses...
   ✓ Generated 3 hypotheses from REAL data
   1. Memory limits too low (recent commit abc123)
   2. Memory leak in application
   3. Traffic spike

✅ VERIFICATION: Testing hypothesis #1...
   ✓ Confirmed: Commit abc123 lowered limits from 256Mi to 64Mi
   ✓ Timing matches OOMKilled events

💡 RECOVERY PROPOSAL:
   Action: rollback deployment
   Target: Previous commit (before memory reduction)
   Command: kubectl rollout undo deployment/demo-app

   📨 Posted to Slack: #incidents

🔒 HUMAN APPROVAL REQUIRED:

   The following action is proposed:

   Action Type: rollback
   Description: Rollback deployment to restore 256Mi memory limit
   Risk Level: medium

   This will execute: kubectl rollout undo deployment/demo-app

   Do you approve this action? [y/N]:
```

### 6.5 Check Slack

While the agent is waiting for approval:

1. Open Slack #incidents channel
2. You should see a message from the bot:
   ```
   🚨 Incident Alert: demo-app

   Status: Requires Approval
   Proposed Action: Rollback deployment

   [Approve] [Reject]
   ```
3. You can approve here OR in the terminal

### 6.6 Approve and Execute

In terminal, type: `y` and press Enter

```
✅ Action approved by user

⚙️ EXECUTION: Executing remediation...
   $ kubectl rollout undo deployment/demo-app
   ✅ Deployment rolled back
   ✅ Pods restarting with 256Mi limit

📝 POST-MORTEM: Generating report...
   ✓ Timeline: 12 minute investigation
   ✓ Root cause: Memory limits lowered in commit abc123
   ✓ Fix: Rollback to previous deployment
   ✓ Status: Resolved

   📨 Posted to Slack: #incidents

✅ Workflow completed with status: completed
📊 Investigation time: 12 minutes
⏱️  Verification rounds: 1
💾 State saved to checkpoint database
```

### 6.7 Verify Fix

```bash
# Check pods are healthy now
kubectl get pods
# Should show 3/3 Running

# Check deployment
kubectl describe deployment demo-app | grep memory
# Should show: 256Mi (restored)

# Check Slack
# Should have post-mortem report in #incidents
```

---

## Phase 7: View Dashboard (5 min)

```bash
# Start dashboard
streamlit run dashboard/app.py

# Open browser to http://localhost:8501
```

You should see:
- **Total Investigations**: 1
- **Completed**: 1 (100%)
- **Service**: demo-app
- **Status**: completed
- **Root cause**: Memory limits too low
- **Full timeline** with all evidence

---

## Production Checklist

Before using in real production:

### Security
- [ ] Rotate all API tokens regularly
- [ ] Use secrets manager (not .env files)
- [ ] Enable RBAC on Kubernetes
- [ ] Restrict Slack bot permissions
- [ ] Use read-only Grafana keys
- [ ] Enable audit logging

### Testing
- [ ] Test all incident scenarios
- [ ] Test approval rejection flow
- [ ] Test with real production data (staging first!)
- [ ] Load test the agent
- [ ] Test failover scenarios

### Monitoring
- [ ] Set up alerts for agent failures
- [ ] Monitor escalation rate
- [ ] Track approval rejection rate
- [ ] Monitor API costs
- [ ] Set up agent health checks

### Documentation
- [ ] Document runbooks
- [ ] Create escalation procedures
- [ ] Document all API keys and where they're stored
- [ ] Create disaster recovery plan
- [ ] Train team on approval process

---

## Troubleshooting

### Agent can't connect to Kubernetes
```bash
# Check kubeconfig
kubectl config current-context
# Should be: minikube

# Check connectivity
kubectl cluster-info
```

### Agent can't access GitHub
```bash
# Test token
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user

# Should return your user info
```

### Slack bot not responding
```bash
# Test bot
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"

# Should return: "ok": true
```

### Grafana connection fails
```bash
# Check Grafana is running
curl http://localhost:3000/api/health

# Check API key
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://localhost:3000/api/org
```

---

## How Live Mode Works

Now that you've completed the setup, here's how the system works in production (MODE=live):

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Incident Response Agent                │
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐  │
│  │   Diagnosis  │─────▶│ Verification │─────▶│  Recovery │  │
│  │    Engine    │      │     Loop     │      │  Proposal │  │
│  └──────────────┘      └──────────────┘      └───────────┘  │
│         │                      │                     │        │
│         └──────────────────────┴─────────────────────┘        │
│                          │                                     │
│                    MCP Registry                               │
│                   (MODE=live)                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┬──────────┐
        │                 │                 │          │
        ▼                 ▼                 ▼          ▼
┌───────────────┐ ┌───────────────┐ ┌──────────┐ ┌─────────┐
│  Kubernetes   │ │    GitHub     │ │  Slack   │ │ Grafana │
│  (kubectl)    │ │  (REST API)   │ │ (Bot API)│ │  (API)  │
└───────────────┘ └───────────────┘ └──────────┘ └─────────┘
        │                 │                 │          │
        ▼                 ▼                 ▼          ▼
   Pod Status        Commit History    Approvals   Metrics
   Pod Logs          Deployment Time   Alerts      Alerts
   Events            Code Changes      Updates     Queries
```

### Live API Wrappers

When MODE=live, the MCP registry loads live server classes that make real API calls:

1. **LiveKubernetesMCPServer** (`mcp_servers/live/kubernetes.py`)
   - Executes `kubectl` commands via subprocess
   - Returns real pod status, logs, events, deployments
   - Used to investigate cluster state

2. **LiveGitHubMCPServer** (`mcp_servers/live/github.py`)
   - Makes REST API calls to GitHub
   - Fetches real commits, PRs, deployment timeline
   - Correlates code changes with incidents

3. **LiveSlackMCPServer** (`mcp_servers/live/slack.py`)
   - Posts messages to Slack workspace
   - Sends approval requests with interactive buttons
   - Provides incident updates and notifications

4. **LiveGrafanaClient** (`mcp_servers/live/observability.py`)
   - Queries Prometheus metrics via Grafana
   - Retrieves active alerts
   - Provides observability data

### Data Flow Example

Here's what happens during an OOM incident in live mode:

1. **Intake**: Agent receives alert about demo-app service
2. **Evidence Gathering**:
   - Calls `k8s_get_pod_status` → LiveKubernetesClient executes `kubectl get pods`
   - Calls `k8s_get_events` → LiveKubernetesClient executes `kubectl get events`
   - Calls `github_get_recent_commits` → LiveGitHubClient calls GitHub API
   - Calls `grafana_query_metrics` → LiveGrafanaClient queries Prometheus
3. **Diagnosis**: Claude analyzes REAL data and generates hypotheses
4. **Verification**: Agent tests hypotheses against real evidence
5. **Recovery**: Agent proposes rollback based on real deployment history
6. **Approval**: Slack message sent to #incidents with interactive buttons
7. **Execution**: If approved, `kubectl rollout undo` executed
8. **Post-Mortem**: Report generated with real timeline and saved to checkpoint DB

### What Makes This Production-Ready?

1. **Real API Calls**: No mocks or fixtures - all data comes from live systems
2. **Modular Design**: Works with just K8s, or add GitHub/Slack/Grafana as needed
3. **Error Handling**: Graceful degradation if optional services unavailable
4. **Human-in-the-Loop**: Approval required before executing remediation
5. **Audit Trail**: All investigations saved to SQLite checkpoint database
6. **Observable**: Dashboard shows investigation history and outcomes
7. **Safe**: Runs locally with minikube - won't affect production accidentally

---

## Next Steps

1. ✅ Run more incident scenarios
2. ✅ Test different failure modes
3. ✅ Practice approval flows
4. ✅ Review post-mortems
5. ✅ Tune alert thresholds
6. ✅ Add more runbooks
7. ✅ Deploy to staging environment
8. ✅ Eventually: Deploy to production!

---

## Cost Estimate

For production use:

**Per incident:**
- Claude API: ~$0.01-0.02
- GitHub API: Free (up to 5000 requests/hour)
- Slack API: Free
- Grafana: Free (self-hosted)

**Monthly (assuming 100 incidents/month):**
- Claude: ~$1-2
- Infrastructure: Depends on K8s cluster size
- Total: Very affordable!

---

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review logs: `kubectl logs <pod-name>`
3. Check agent logs in terminal output
4. Review checkpoint database for investigation history
5. Check Slack #incidents channel for notifications

---

**Congratulations!** You now have a production-ready AI incident response system! 🎉
