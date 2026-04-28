# AI Incident Response Engineer — Project Spec

## Overview

Build an autonomous agent that triages, diagnoses, and helps remediate production incidents for a Kubernetes-based service. The agent is triggered by an alert (PagerDuty-style webhook), gathers evidence from observability and infra tools via MCP, forms and verifies hypotheses about root cause, and — with human approval — proposes or executes a remediation. After resolution, it drafts a post-mortem.

The differentiators vs. a typical agent demo are:
1. A **hypothesize-then-verify loop** with backtracking, not a linear pipeline
2. A hard **human-in-the-loop gate** before any write action
3. **Durable state** via LangGraph checkpointing so investigations survive restarts
4. A **custom-built MCP server** (not just consumed ones)
5. A real **eval harness** with scripted incident scenarios

The whole thing runs locally via Docker Compose against synthetic data — no real production access required.

## Trigger

- FastAPI HTTP webhook accepting PagerDuty-style incident payloads
- CLI fallback for manual invocation: `investigate --alert-id <id>`

## LangGraph Architecture

The graph is NOT linear. The Verification node loops back to Diagnosis when hypotheses are refuted.

1. **Intake** — parse alert, extract service, severity, time window, affected pods/endpoints. Emit a structured `Incident` into state.
2. **Evidence Gathering** — fan out in parallel: logs, metrics, recent deploys, current pod status. Aggregate into an `Evidence` object.
3. **Diagnosis** — generate 2–3 ranked hypotheses, each with an explicit falsification criterion ("if X is true, this hypothesis is wrong").
4. **Verification** — run targeted checks against the top hypothesis. Returns `confirmed | refuted | inconclusive`.
   - `refuted` → back to Diagnosis with the next hypothesis (or generate new ones if exhausted)
   - `inconclusive` after N rounds → escalate to human with current findings
   - `confirmed` → continue to Recovery
5. **Recovery Proposal** — draft a remediation (rollback, scale, restart, config change). Always pauses here for human approval.
6. **Execution** — runs only after explicit approval. Idempotent. Supports dry-run.
7. **Post-Mortem** — draft an incident report (timeline, root cause, contributing factors, action items) and post to Slack + save as markdown.

State persisted via LangGraph's checkpointer (Postgres in Docker Compose, SQLite for dev). Investigations must be resumable after a process restart — write a test for this.

## MCP Integrations

**Existing MCP servers to consume (real, in production mode):**
- Kubernetes — pod status, events, logs, deployment history
- GitHub — recent commits/PRs for the service repo, deploy timeline, diffs
- Slack — post updates, request approval via interactive messages
- One observability MCP (Grafana, Datadog, or Prometheus)

**Fixture-based mock MCP servers (for evals and CI):**

The eval harness must be deterministic, so build a parallel set of mock MCP servers that implement the same tool interfaces but serve canned fixtures from disk. The agent code does not know whether it is talking to real or mock servers — only the MCP server URLs/commands change between modes. Drive the choice via a `MODE=live|eval` env var or a config file.

This dual-mode setup is itself a resume-worthy design decision: it shows you understand that agent evaluation requires fixture replay, not live API calls.

**Custom MCP server to BUILD — this is the resume centerpiece:**

A **Runbook & Deploy Correlator** MCP server, implemented from scratch using the official MCP Python SDK. Tools it exposes:
- `find_runbook(service, alert_type)` — retrieves the relevant runbook from a local markdown corpus
- `correlate_deploys(service, time_window)` — returns deploys with diff summaries, ranked by suspicion score
- `similar_past_incidents(symptom_text)` — vector search over a local store of past incidents (use a small embedding model)

Run it via stdio. Document the protocol-level decisions in `mcp_servers/runbook_correlator/README.md` — schema choices, why each tool exists, error handling. This documentation is what makes the MCP work read as senior on a resume.

## Human-in-the-Loop Safety

- No mutating action runs without explicit human approval
- Approvals delivered via Slack interactive buttons (primary) or CLI (fallback)
- Each proposed action displays: expected effect, blast radius, dry-run output
- Hard-coded allowlist of action types; novel actions always escalate
- Every approval/rejection logged with reasoning to the checkpointer

## Observability

A Streamlit dashboard reading from the checkpointer, showing:
- Active and historical investigations with full transcript
- Per-node latency and token cost
- Hypothesis acceptance rate (was the first hypothesis correct?)
- Time-to-diagnosis and time-to-resolution distributions

Trace via LangSmith if available, otherwise structured JSONL spans.

## Eval Harness

Hand-build 15–25 scripted incident scenarios with known root causes. Examples:
- OOM after a deploy lowered memory limits
- 5xx spike from a feature flag flip
- DNS resolution failure from a coredns config change
- Cascading failure from a downstream dependency timeout
- Slow query after an index was dropped

Each scenario provides:
- Synthetic logs, metrics, and deploy history served by mock MCP servers
- Ground-truth root cause label
- Set of acceptable remediation actions

Score on:
- Root cause identification: exact / partial / wrong
- Remediation acceptability: yes / no
- Verification rounds required (lower is better)
- Cost per incident (tokens + tool calls)

Run evals in CI on every change to the graph or prompts. Track scores over time.

## Tech Stack

- Python 3.11+
- LangGraph (with Postgres/SQLite checkpointing)
- Official Anthropic Python SDK
- Official MCP Python SDK (for the custom server)
- FastAPI (webhook)
- Streamlit (dashboard)
- Pytest (evals)
- Docker Compose (local environment)

## Suggested Repo Structure

```
.
├── agent/
│   ├── graph.py              # LangGraph wiring
│   ├── state.py              # State types
│   ├── nodes/                # One file per node
│   └── prompts/              # Versioned prompt templates
├── mcp_servers/
│   └── runbook_correlator/   # Custom MCP server + its README
├── webhook/                  # FastAPI app
├── dashboard/                # Streamlit UI
├── evals/
│   ├── scenarios/            # Synthetic incidents
│   ├── runner.py
│   └── rubric.py
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Explicitly Out of Scope

- No real production deployment; everything runs locally
- No auth beyond a shared secret on the webhook
- No fine-tuned models; rely on prompting and tool calls
- Don't try to support every alert type — pick 4–5 representative ones and do them well
- No autoscaling / multi-tenant concerns

## README Must Include

- Architecture diagram (Mermaid is fine)
- One full worked example: incident in, investigation transcript, post-mortem out
- Honest "Limitations" section listing failure modes actually observed during eval
- Current eval scores in a table
- Setup instructions that work on a clean machine

## Build Order Recommendation

1. State types + skeleton graph with all nodes as no-ops
2. Fixture-based mock MCP servers (these unblock development and become the eval substrate forever)
3. The custom Runbook & Deploy Correlator MCP server
4. One end-to-end happy-path scenario working against mocks
5. Hypothesis verification loop with backtracking
6. Human-in-the-loop approval flow
7. Checkpointing + resumability test
8. Eval harness with 5 scenarios, then expand to 20
9. Wire in real MCP servers (Kubernetes, GitHub, Slack, observability) behind the same interfaces — `MODE=live` should now work end-to-end
10. Dashboard
11. Polish: README, architecture diagram, honest limitations writeup, worked example using live mode