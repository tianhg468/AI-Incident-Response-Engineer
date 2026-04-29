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
# Start infrastructure (Postgres for checkpointing)
docker-compose up -d

# Run the webhook server
uvicorn webhook.main:app --reload

# In another terminal, run the dashboard
streamlit run dashboard/app.py

# Test with a sample incident
python -m agent.graph
```

## Development Status

**Current Phase:** Step 8 - Eval Harness with Scoring ✅

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
- [ ] Real MCP integrations
- [ ] Dashboard

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

## Limitations

*(To be documented based on observed failure modes during eval)*

- TBD

## License

MIT
