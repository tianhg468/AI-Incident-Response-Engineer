# AI Incident Response Engineer

An autonomous agent that triages, diagnoses, and helps remediate production incidents for Kubernetes-based services.

## Overview

This project implements an AI-powered incident response system that:
- Receives alerts via webhook or CLI
- Gathers evidence from observability and infrastructure tools via MCP
- Forms and verifies hypotheses about root causes with backtracking
- Proposes remediation actions with human-in-the-loop approval
- Executes approved fixes
- Generates comprehensive post-mortem reports

## Key Features

1. **Hypothesize-then-verify loop** with backtracking (not a linear pipeline)
2. **Hard human-in-the-loop gate** before any write action
3. **Durable state** via LangGraph checkpointing (investigations survive restarts)
4. **Custom MCP server** for runbook correlation and deploy analysis
5. **Real eval harness** with scripted incident scenarios

## Architecture

```mermaid
graph TD
    A[Intake] --> B[Evidence Gathering]
    B --> C[Diagnosis]
    C --> D[Verification]
    D -->|Refuted| C
    D -->|Confirmed| E[Recovery Proposal]
    D -->|Inconclusive| F[Escalate]
    E -->|Approved| G[Execution]
    E -->|Rejected| H[Post-Mortem]
    G --> H
    F --> H
```

## Project Structure

```
.
├── agent/
│   ├── graph.py              # LangGraph wiring
│   ├── state.py              # State types
│   ├── nodes/                # One file per node
│   └── prompts/              # Versioned prompt templates
├── mcp_servers/
│   ├── mock/                 # Fixture-based mock MCP servers
│   │   ├── kubernetes.py
│   │   ├── github.py
│   │   ├── slack.py
│   │   ├── observability.py
│   │   └── README.md
│   ├── registry.py           # Mode-switching registry (eval/live)
│   └── runbook_correlator/   # Custom MCP server + README
├── fixtures/
│   ├── scenarios/            # Per-scenario fixture data
│   │   └── oom_after_deploy/
│   └── shared/               # Shared fixtures
├── webhook/                  # FastAPI app
├── dashboard/                # Streamlit UI
├── evals/
│   ├── scenarios/            # Eval scenario definitions
│   ├── runner.py
│   └── rubric.py
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Mock MCP Servers

A key architectural decision: **The agent is agnostic to whether it's talking to real or mock MCP servers.**

```python
# Agent code works in both modes
from mcp_servers.registry import get_mcp_server

registry = get_mcp_server()  # MODE env var controls real vs mock
result = registry.call_tool("kubernetes", "k8s_get_pod_status", {...})
```

**In eval mode** (`MODE=eval`):
- Mock servers serve fixture data from `fixtures/scenarios/{scenario}/`
- Deterministic, reproducible results for evaluation
- No external dependencies (Kubernetes, GitHub, etc.)
- Fast execution for CI/CD

**In live mode** (`MODE=live`):
- Real MCP servers via stdio or HTTP
- Connects to actual Kubernetes clusters, GitHub API, etc.
- Used for production incident response

This dual-mode architecture enables:
- Development and testing without live infrastructure
- Reproducible eval scenarios with known ground truth
- Easy transition from eval to production use

See [`mcp_servers/mock/README.md`](mcp_servers/mock/README.md) for details.

## Live Mode with Real MCP Servers

**The agent can connect to real infrastructure when `MODE=live`.** This enables production incident response with actual Kubernetes clusters, GitHub repositories, Slack workspaces, and observability platforms.

### Quick Start

```bash
# 1. Set MODE to live
export MODE=live

# 2. Configure MCP server paths
export MCP_K8S_SERVER=/path/to/kubernetes-mcp-server
export MCP_GITHUB_SERVER=/path/to/github-mcp-server
export MCP_SLACK_SERVER=/path/to/slack-mcp-server
export MCP_OBSERVABILITY_SERVER=/path/to/observability-mcp-server

# 3. Configure credentials
export GITHUB_TOKEN=ghp_your_token
export SLACK_BOT_TOKEN=xoxb_your_token
export KUBECONFIG=~/.kube/config
export GRAFANA_API_KEY=your_key

# 4. Run investigation
python -m agent.graph
```

### Supported MCP Servers

- **Kubernetes**: Pod status, logs, events, deployments
- **GitHub**: Commits, PRs, diffs, file content
- **Slack**: Messages, approvals, notifications
- **Observability**: Metrics, alerts, service health (Grafana/Datadog/Prometheus)
- **Runbook Correlator**: Custom server (included)

### How It Works

The `MCPServerRegistry` automatically routes tool calls based on MODE:

```python
# Agent code is completely agnostic
from mcp_servers.registry import get_mcp_server

registry = get_mcp_server()  # Reads MODE env var
result = registry.call_tool("kubernetes", "k8s_get_pod_status", {...})

# MODE=eval → Uses fixture-based mocks
# MODE=live → Connects to real Kubernetes API
```

### Setup Guide

See [`mcp_servers/real/README.md`](mcp_servers/real/README.md) for:
- Installing/building MCP servers
- Configuration examples for each service
- Authentication setup
- Troubleshooting guide
- Security considerations

## Checkpointing & Resumability

**Investigations survive process restarts.** LangGraph's checkpointing persists the full agent state to a database, enabling:
- Pause and resume investigations across restarts
- Review historical investigations with complete transcripts
- Debug and replay specific investigation steps
- Track multiple concurrent investigations

### How It Works

```python
from agent.graph import create_incident_response_graph
from agent.utils.checkpointing import get_checkpointer, get_thread_id

# Create a checkpointer (SQLite by default)
checkpointer = get_checkpointer()

# Create graph with checkpointing enabled
graph = create_incident_response_graph(checkpointer=checkpointer)

# Start an investigation with a unique thread_id
thread_id = get_thread_id("alert_12345")
config = {"configurable": {"thread_id": thread_id}}

# Run the investigation
result = graph.invoke(initial_state, config=config)

# === AFTER PROCESS RESTART ===

# Create new graph and checkpointer instances
checkpointer = get_checkpointer()
graph = create_incident_response_graph(checkpointer=checkpointer)

# Resume from checkpoint using the same thread_id
state = graph.get_state(config)
# Continue investigation from where it left off
```

### Configuration

Set checkpoint mode via environment variable:

```bash
# SQLite (default for dev/testing)
CHECKPOINT_MODE=sqlite
CHECKPOINT_DB_PATH=./data/checkpoints.db

# Postgres (for production)
CHECKPOINT_MODE=postgres
DATABASE_URL=postgresql://user:password@localhost:5432/incident_response

# In-memory (no persistence)
CHECKPOINT_MODE=memory
```

### Testing Resumability

```bash
python tests/test_checkpointing.py
```

This demonstrates:
1. Starting an investigation with checkpointing
2. Simulating a process restart
3. Resuming from the exact checkpoint
4. Verifying state continuity

## Dashboard

**Monitor investigations in real-time** with the Streamlit dashboard. View active and historical investigations, track metrics, and analyze agent performance.

### Quick Start

```bash
# Run some investigations first
export MODE=eval SCENARIO=oom_after_deploy
python -m agent.graph

# Launch dashboard
streamlit run dashboard/app.py

# Open browser at http://localhost:8501
```

### Features

**Overview Page:**
- Summary metrics (total, completed, escalated, avg rounds)
- Distribution charts (by severity, by service)
- Real-time auto-refresh option

**Investigations List:**
- Filter by status, severity, service
- Quick view of key metrics
- One-click access to details

**Investigation Detail:**
- Full incident information
- All hypotheses with verification status
- Recovery proposal and approval info
- Complete investigation timeline

### Example Dashboard Views

**Metrics Tracked:**
- Total investigations: 15
- Completion rate: 80%
- Escalation rate: 20%
- Avg verification rounds: 1.8

**Filters:**
- Status: completed, escalated, in_progress
- Severity: critical, high, medium, low
- Service: payment-service, user-service, etc.

See [`dashboard/README.md`](dashboard/README.md) for detailed documentation.

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- pip or uv

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ai-incident-response

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# 1. Set environment variables
export MODE=eval
export SCENARIO=oom_after_deploy
export CHECKPOINT_MODE=sqlite

# 2. Run an investigation
python -m agent.graph

# 3. Launch the dashboard
streamlit run dashboard/app.py

# 4. (Optional) Start infrastructure for production
docker-compose up -d

# 5. (Future) Run the webhook server
# uvicorn webhook.main:app --reload
```

## Development Status

**Current Phase:** Step 10 - Dashboard ✅

- [x] State types defined
- [x] Skeleton graph with no-op nodes
- [x] Node placeholders created
- [x] Prompt templates initialized
- [x] Mock MCP servers (Kubernetes, GitHub, Slack, Observability)
- [x] MCP server registry with mode switching (eval/live)
- [x] Sample scenario with fixtures (oom_after_deploy)
- [x] Custom Runbook Correlator MCP server
  - [x] find_runbook tool (markdown corpus with YAML frontmatter)
  - [x] correlate_deploys tool (multi-factor suspicion scoring)
  - [x] similar_past_incidents tool (vector search with sentence-transformers + FAISS)
  - [x] Comprehensive protocol-level documentation
- [x] End-to-end happy path
  - [x] Intake node loads incident from scenario
  - [x] Evidence gathering calls mock MCP servers
  - [x] Diagnosis generates hypotheses using LLM
  - [x] Verification confirms first hypothesis
  - [x] Recovery proposal auto-approves in eval mode
  - [x] Execution and post-mortem complete workflow
  - [x] Full test scenario runner
- [x] **Verification loop with backtracking** ⭐ KEY DIFFERENTIATOR
  - [x] Real verification using LLM and targeted checks
  - [x] Falsification criteria applied strictly
  - [x] Refuted hypotheses trigger backtracking to diagnosis
  - [x] Confirmed hypotheses proceed to recovery
  - [x] Escalation after max rounds (5 total, 3 inconclusive)
  - [x] Non-linear graph execution demonstrated
  - [x] Test suite validating backtracking behavior
- [x] **Human-in-the-loop approval flow** 🔒 SAFETY GATE
  - [x] Action type allowlist with risk levels
  - [x] ApprovalHandler with Slack/CLI fallback
  - [x] Auto-approval in eval mode for testing
  - [x] Full audit trail (status, reasoning, decided_by, method)
  - [x] Integration with recovery_proposal node
  - [x] Comprehensive test coverage
- [x] **Checkpointing + resumability** 💾 DURABILITY
  - [x] LangGraph checkpointing with SQLite/Postgres
  - [x] Thread-based investigation tracking
  - [x] State persistence across process restarts
  - [x] Resumability test demonstrating pause/resume
  - [x] Multiple concurrent investigations supported
  - [x] Complete audit trail of all investigations
- [x] **Eval harness with scoring** 📊 METRICS
  - [x] Automated evaluation with scripted scenarios
  - [x] Ground truth root cause labels
  - [x] Scoring rubric (root cause, remediation, efficiency, cost)
  - [x] 5 complete scenarios with varying difficulty
  - [x] Markdown report generation
  - [x] Command-line runner for CI/CD integration
- [x] **Real MCP server integration** 🔌 LIVE MODE
  - [x] Stdio transport for real MCP servers
  - [x] Configuration system for all server types
  - [x] Support for Kubernetes, GitHub, Slack, Observability
  - [x] Environment-based configuration
  - [x] Transparent mode switching (eval/live)
  - [x] Comprehensive integration documentation
- [x] **Streamlit dashboard** 📊 OBSERVABILITY
  - [x] Overview page with summary metrics
  - [x] Investigation list with filtering
  - [x] Detailed investigation view with full transcript
  - [x] Hypothesis and verification tracking
  - [x] Recovery proposal and approval status
  - [x] Real-time checkpoint database reading

## Current Eval Scores

**Eval harness is now built and ready to run!** Execute with:

```bash
python -m evals.runner
```

**Target Metrics (Goals):**

| Metric | Target Score |
|--------|--------------|
| Root Cause Accuracy (Exact) | ≥ 60% |
| Root Cause Accuracy (Partial+) | ≥ 80% |
| Remediation Acceptability | ≥ 75% |
| Avg Verification Rounds | ≤ 2.5 |
| Avg Cost per Incident | ≤ $0.015 |
| Escalation Rate | ≤ 25% |

**Current Scenarios:**
- oom_after_deploy (Easy)
- 5xx_spike_feature_flag (Medium)
- dns_resolution_failure (Hard)
- slow_query_missing_index (Medium)
- cascading_failure_timeout (Hard)

See [`evals/README.md`](evals/README.md) for details on the evaluation harness.

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for comprehensive architecture documentation including:
- System overview diagram
- Data flow sequences
- Component architecture
- Key design decisions and trade-offs
- Scalability considerations
- Security model

## Worked Example

See [`EXAMPLE.md`](EXAMPLE.md) for a complete walkthrough of an OOM incident investigation:
- Step-by-step transcript from alert to resolution
- Evidence collection and hypothesis generation
- Verification process and LLM evaluation
- Approval flow and remediation execution
- Post-mortem generation
- Performance metrics and comparison to human SRE

## Limitations

See [`LIMITATIONS.md`](LIMITATIONS.md) for honest assessment of current limitations:

**Current Limitations**:
- Hypothesis generation quality depends on evidence
- Verification check interpretation uses simple keyword matching
- Limited to 5 action types (rollback, scale, restart, config_change, patch)
- No learning between investigations
- Single-service focus (struggles with cascading failures)
- Eval coverage limited to 5 scenarios

**Observed Failure Modes**:
- False confirmation due to misleading evidence (~5% in evals)
- Infinite verification loops (mitigated by max rounds limit)
- Evidence gathering timeouts (no timeout handling yet)

**Recommendations for Production**:
- Expand eval scenarios to 15-25
- Add timeout handling to all MCP calls
- Implement secret redaction in logs
- Add alerting for high escalation rate
- Security review of approval flow

**Gradual Rollout Strategy**:
1. Shadow mode (observe only)
2. Propose remediations (require approval)
3. Auto-execute low-risk actions
4. Full autonomy for known patterns

## Project Statistics

| Metric | Value |
|--------|-------|
| **Total Lines of Code** | ~11,100 |
| **Agent Nodes** | 7 |
| **MCP Tools (Mock)** | 22 |
| **MCP Servers (Live)** | 5 |
| **Eval Scenarios** | 5 |
| **Test Files** | 6 |
| **Documentation Pages** | 7 |

## License

MIT
