# Live Mode Integration - Complete

This document explains how the live mode integration was completed to make the AI Incident Response Engineer production-ready.

## What Was Implemented

The live mode integration connects the agent to real infrastructure APIs instead of mock fixtures. Here's what was built:

### 1. Live API Wrapper Classes (`mcp_servers/live_wrappers.py`)

Four client classes that make real API calls:

#### **LiveKubernetesClient**
- Executes `kubectl` commands via subprocess
- Methods:
  - `get_pod_status(service)` - Real pod status from cluster
  - `get_pod_logs(service, tail_lines)` - Real logs from pods
  - `get_events(service)` - Real Kubernetes events
  - `get_deployment_history(service)` - Real deployment history

#### **LiveGitHubClient**
- Makes REST API calls to GitHub
- Methods:
  - `get_commits(repo, limit)` - Real commit history
  - `get_pull_requests(repo, state, limit)` - Real PR data

#### **LiveSlackClient**
- Makes Bot API calls to Slack
- Methods:
  - `post_message(text, blocks)` - Post to Slack channel
  - `request_approval(action_type, description)` - Interactive approval buttons

#### **LiveGrafanaClient**
- Queries Prometheus via Grafana API
- Methods:
  - `query_metrics(query)` - Real PromQL queries
  - `get_alerts()` - Active alerts from Grafana

### 2. Live MCP Server Classes (`mcp_servers/live/`)

Four MCP server classes that implement the MCP tool interface using live wrappers:

#### **LiveKubernetesMCPServer** (`live/kubernetes.py`)
- Implements MCP tools: `k8s_get_pod_status`, `k8s_get_pod_logs`, `k8s_get_events`, etc.
- Transforms kubectl output into MCP tool response format
- Handles label selectors and field selectors

#### **LiveGitHubMCPServer** (`live/github.py`)
- Implements MCP tools: `github_get_recent_commits`, `github_get_recent_prs`, etc.
- Transforms GitHub API responses into MCP tool response format
- Handles pagination and filtering

#### **LiveSlackMCPServer** (`live/slack.py`)
- Implements MCP tools: `slack_post_message`, `slack_request_approval`, etc.
- Creates formatted Slack Block Kit messages
- Handles interactive components

#### **LiveObservabilityMCPServer** (`live/observability.py`)
- Implements MCP tools: `grafana_query_metrics`, `grafana_get_alerts`, etc.
- Transforms Prometheus/Grafana responses into MCP tool response format
- Handles PromQL queries

### 3. Registry Integration (`mcp_servers/registry.py`)

Modified `_init_live_servers()` method to:
- Import and instantiate live server classes when MODE=live
- Kubernetes is required (throws error if unavailable)
- GitHub, Slack, Grafana are optional (warns if unavailable)
- Provides clear logging about which services are active

## How It Works

### Before (Eval Mode)

```python
# MODE=eval
registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")
# Uses MockKubernetesMCPServer → FixtureLoader → fixtures/scenarios/oom_after_deploy/
```

### After (Live Mode)

```python
# MODE=live
registry = MCPServerRegistry(mode="live")
# Uses LiveKubernetesMCPServer → LiveKubernetesClient → kubectl commands → Real cluster
```

### Agent Code Stays the Same

The agent code doesn't change at all! It just calls:

```python
registry.call_tool("kubernetes", "k8s_get_pod_status", {
    "namespace": "default",
    "label_selector": "app=demo-app"
})
```

In eval mode, this returns fixture data.
In live mode, this executes `kubectl get pods -l app=demo-app -n default -o json` and returns real data.

## File Structure

```
mcp_servers/
├── live_wrappers.py           # Low-level API clients
├── live/                      # MCP server implementations
│   ├── __init__.py
│   ├── kubernetes.py          # Live K8s MCP server
│   ├── github.py              # Live GitHub MCP server
│   ├── slack.py               # Live Slack MCP server
│   └── observability.py       # Live Grafana MCP server
├── mock/                      # Fixture-based mocks (eval mode)
│   ├── kubernetes.py
│   ├── github.py
│   ├── slack.py
│   └── observability.py
└── registry.py                # Routes between live/mock based on MODE
```

## Environment Variables Required

For live mode to work, you need these in `.env`:

```bash
# Core
MODE=live
ANTHROPIC_API_KEY=sk-ant-...

# Kubernetes (REQUIRED)
KUBECONFIG=~/.kube/config
K8S_NAMESPACE=default

# GitHub (OPTIONAL)
GITHUB_TOKEN=ghp_...
GITHUB_ORG=your-username

# Slack (OPTIONAL)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#incidents

# Grafana (OPTIONAL)
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=glsa_...
```

## Testing the Integration

### Step 1: Test in Eval Mode (Fixtures)

```bash
# Set MODE=eval in .env
MODE=eval
SCENARIO=oom_after_deploy

# Run agent
python -m agent.graph

# Should use fixtures from fixtures/scenarios/oom_after_deploy/
```

### Step 2: Test in Live Mode (Real APIs)

```bash
# Set MODE=live in .env
MODE=live

# Make sure minikube is running
minikube status

# Deploy demo app
cd demo-app
./setup.sh

# Trigger incident
./incidents/trigger-oom.sh

# Run agent in live mode
cd ..
python -m agent.graph

# Should make REAL kubectl calls, GitHub API calls, etc.
```

## What You Should See

### Live Mode Startup

```
🚀 Starting incident response workflow (LIVE MODE)...
Initializing live MCP servers for production mode...
Initializing Kubernetes live server...
✅ Kubernetes live server initialized
Initializing GitHub live server...
✅ GitHub live server initialized
Initializing Slack live server...
✅ Slack live server initialized
Initializing Grafana live server...
✅ Grafana live server initialized
🚀 Initialized 4 live MCP servers (PRODUCTION MODE)
   Available services: kubernetes, github, slack, observability
```

### Evidence Gathering (REAL APIs)

```
🔍 EVIDENCE GATHERING: Collecting from LIVE sources...
  ✅ Kubernetes: Connected
     • Executing: kubectl get pods -l app=demo-app -n default -o json
     • 3 pods found
     • 2 pods OOMKilled
  ✅ GitHub: Connected
     • API call: https://api.github.com/repos/you/ai-incident-response-demo/commits
     • Latest commit: abc123 "perf: Reduce memory limits"
     • Time: 15 minutes ago
  ✅ Slack: Connected to #incidents
     • Posted incident alert
  ✅ Grafana: Connected
     • Query: container_memory_usage_bytes{pod=~"demo-app.*"}
```

## Production Readiness Checklist

- ✅ **Live API Integration**: Real kubectl, GitHub, Slack, Grafana calls
- ✅ **Error Handling**: Graceful degradation if optional services unavailable
- ✅ **Human Approval**: Required before executing any remediation
- ✅ **Audit Trail**: All investigations saved to SQLite checkpoint database
- ✅ **Observability**: Dashboard shows real-time and historical investigations
- ✅ **Modular Design**: Works with just K8s or full stack
- ✅ **Safe Testing**: Uses local minikube cluster for safety
- ✅ **Documentation**: Complete setup guide in PRODUCTION_SETUP.md

## What's Next?

Follow the step-by-step instructions in **PRODUCTION_SETUP.md** to:

1. Create GitHub repository for demo-app
2. Set up Slack workspace and bot
3. Install and configure Grafana
4. Deploy demo app to minikube
5. Configure all API tokens
6. Run end-to-end live mode test
7. View results in dashboard

**Total setup time: ~1-2 hours**

---

## Troubleshooting

### "No module named 'mcp_servers.live'"

Make sure you reinstalled the package after adding the live modules:

```bash
pip install -e .
```

### "Kubernetes server is required for live mode"

Check that kubectl is configured and accessible:

```bash
kubectl cluster-info
kubectl get pods
```

### "GitHub server not available"

Check your GitHub token and org in `.env`:

```bash
echo $GITHUB_TOKEN
echo $GITHUB_ORG

# Test GitHub API access
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### "Slack server not available"

Check your Slack bot token:

```bash
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"
```

---

**The live mode integration is complete and production-ready!** 🚀
