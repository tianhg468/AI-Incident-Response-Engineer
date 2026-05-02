# Quick Start Guide - AI Incident Response Engineer

Get the AI Incident Response Engineer running in production mode in ~1-2 hours.

## What You'll Build

A production-ready AI agent that:
- Detects incidents in your Kubernetes cluster
- Investigates root causes by analyzing logs, events, and commit history
- Proposes remediation actions
- Requests human approval via Slack
- Executes fixes and generates post-mortems
- Saves all investigations to a database

## Prerequisites

Install these tools:

```bash
# macOS
brew install docker kubectl minikube grafana node

# Verify
docker --version
kubectl version --client
minikube version
```

You'll also need:
- GitHub account (free)
- Slack workspace (free - or create one)
- Anthropic API key (you already have this)

## 5-Minute Quick Start (Eval Mode)

Want to see it work first? Run in eval mode with mock fixtures:

```bash
# 1. Clone and install
cd /Users/tianhuang/Documents/Personal/Job_Intern_Application/projects/agentic_ai
pip install -e .

# 2. Configure .env
cat > .env <<EOF
MODE=eval
SCENARIO=oom_after_deploy
ANTHROPIC_API_KEY=your-key-here
CHECKPOINT_MODE=sqlite
CHECKPOINT_DB_PATH=./data/checkpoints.db
EOF

# 3. Run agent
python -m agent.graph

# 4. View dashboard
streamlit run dashboard/app.py
# Open http://localhost:8501
```

That's it! You just ran a complete incident investigation with mock data.

## Full Production Setup (1-2 Hours)

Ready for the real thing? Follow **PRODUCTION_SETUP.md** for the complete setup with all integrations:

### Phase 1: GitHub Setup (15 min)
- Create repository for demo app
- Generate personal access token
- Push demo app code
- Create commit history

### Phase 2: Slack Setup (20 min)
- Create Slack workspace (or use existing)
- Create Slack bot app
- Configure permissions
- Get bot token
- Test message posting

### Phase 3: Grafana Setup (15 min)
- Install Grafana locally
- Create service account
- Generate API key
- Add Prometheus data source

### Phase 4: Kubernetes Setup (10 min)
- Start minikube
- Deploy demo application
- Verify pods are running
- Test application endpoints

### Phase 5: Configure Environment (5 min)
- Update `.env` with all tokens
- Set MODE=live
- Verify configuration

### Phase 6: Test Live Mode (15 min)
- Trigger an OOM incident
- Run agent in live mode
- Watch real API calls
- Approve remediation
- Verify fix

### Phase 7: View Dashboard (5 min)
- Launch Streamlit dashboard
- View investigation results
- Review post-mortem report

**Total time: ~1-2 hours**

## Architecture Overview

```
Agent (Python + LangGraph)
    │
    ├─ Claude API (hypothesis generation)
    │
    └─ MCP Registry (MODE=live)
           │
           ├─ Kubernetes API (kubectl)
           ├─ GitHub REST API
           ├─ Slack Bot API
           └─ Grafana API
```

## Key Features

1. **Non-Linear Reasoning**: Agent can backtrack if hypothesis is refuted
2. **Human-in-the-Loop**: Approval required before executing remediation
3. **Multi-Source Evidence**: Combines K8s, Git, metrics, and logs
4. **Audit Trail**: All investigations saved to SQLite database
5. **Observable**: Real-time dashboard with investigation history
6. **Safe**: Runs locally with minikube - won't affect production

## Project Structure

```
agentic_ai/
├── agent/                      # Agent implementation
│   ├── graph.py               # LangGraph workflow
│   ├── nodes/                 # Graph nodes (intake, diagnosis, etc.)
│   └── utils/                 # LLM client, checkpointing
├── mcp_servers/               # MCP server implementations
│   ├── live_wrappers.py      # Real API clients
│   ├── live/                  # Live MCP servers
│   ├── mock/                  # Mock MCP servers (eval mode)
│   └── registry.py            # Routes between live/mock
├── fixtures/                  # Test scenarios (eval mode)
├── evals/                     # Evaluation harness
├── dashboard/                 # Streamlit dashboard
├── demo-app/                  # Demo Node.js app for testing
│   ├── app.js                # Express server
│   ├── k8s/                   # Kubernetes manifests
│   ├── incidents/             # Incident trigger scripts
│   └── setup.sh               # Automated setup
├── PRODUCTION_SETUP.md        # Full production setup guide
├── LIVE_MODE_INTEGRATION.md   # How live mode works
├── DEMO.md                    # Original eval mode demo
└── QUICK_START.md             # This file
```

## Common Commands

```bash
# Eval mode (fixtures)
MODE=eval python -m agent.graph

# Live mode (real APIs)
MODE=live python -m agent.graph

# Dashboard
streamlit run dashboard/app.py

# Deploy demo app
cd demo-app && ./setup.sh

# Trigger incidents
./demo-app/incidents/trigger-oom.sh
./demo-app/incidents/trigger-crash-loop.sh

# Check Kubernetes
kubectl get pods
kubectl logs <pod-name>
kubectl describe pod <pod-name>

# Minikube
minikube start
minikube stop
minikube dashboard
minikube service demo-app --url
```

## Environment Variables

### Eval Mode (Minimum)
```bash
MODE=eval
SCENARIO=oom_after_deploy
ANTHROPIC_API_KEY=sk-ant-...
```

### Live Mode (Full Setup)
```bash
MODE=live
ANTHROPIC_API_KEY=sk-ant-...

# Kubernetes (required)
KUBECONFIG=~/.kube/config
K8S_NAMESPACE=default

# GitHub (optional)
GITHUB_TOKEN=ghp_...
GITHUB_ORG=your-username

# Slack (optional)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#incidents

# Grafana (optional)
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=glsa_...

# Checkpointing
CHECKPOINT_MODE=sqlite
CHECKPOINT_DB_PATH=./data/checkpoints.db
```

## Next Steps

### Option 1: Quick Demo (5 min)
Just want to see it work?
→ Run in **eval mode** with the 5-minute quick start above

### Option 2: Full Production Setup (1-2 hours)
Ready to set up the full system?
→ Follow **PRODUCTION_SETUP.md** step-by-step

### Option 3: Understand the Architecture
Want to understand how it works?
→ Read **LIVE_MODE_INTEGRATION.md**

## Example Workflow

Here's what happens when you run the agent in live mode:

```
1. 🔔 Alert: demo-app OOMKilled
2. 🔍 Gather Evidence:
   - kubectl: 3 pods, 2 OOMKilled
   - GitHub: Recent commit lowered memory limits
   - Grafana: Memory usage trending up
3. 🧠 Generate Hypotheses:
   - Hypothesis 1: Memory limits too low (commit abc123)
   - Hypothesis 2: Memory leak in code
   - Hypothesis 3: Traffic spike
4. ✅ Verify Hypothesis 1:
   - Commit abc123 lowered limits from 256Mi to 64Mi
   - Timing matches OOM events
   - CONFIRMED!
5. 💡 Propose Remediation:
   - Action: rollback deployment
   - Command: kubectl rollout undo
6. 🔒 Request Approval:
   - Terminal: "Do you approve? [y/N]"
   - Slack: Interactive approve/reject buttons
7. ⚙️ Execute (if approved):
   - kubectl rollout undo deployment/demo-app
   - Verify pods healthy
8. 📝 Post-Mortem:
   - Timeline: 12 minutes
   - Root cause: Memory limits too low
   - Fix: Rollback to previous deployment
   - Saved to checkpoint database
```

## Getting Help

- **Setup Issues**: See PRODUCTION_SETUP.md troubleshooting section
- **How It Works**: Read LIVE_MODE_INTEGRATION.md
- **Architecture**: See SPEC.md
- **Eval Mode**: See DEMO.md

## Cost Estimate

**Per incident:**
- Claude API: ~$0.01-0.02
- GitHub API: Free
- Slack API: Free
- Grafana: Free (self-hosted)

**Monthly (100 incidents):**
- Claude: ~$1-2
- Total: Very affordable!

---

**Ready to get started?** Pick one of the options above and dive in! 🚀
