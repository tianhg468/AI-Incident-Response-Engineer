# AI Incident Response Engineer - Architecture

## System Overview

```mermaid
graph TB
    subgraph "Trigger Sources"
        WEBHOOK[FastAPI Webhook<br/>PagerDuty/Alerts]
        CLI[CLI Manual Trigger<br/>python -m agent.graph]
    end

    subgraph "Agent Core"
        INTAKE[Intake Node<br/>Parse incident]
        EVIDENCE[Evidence Gathering<br/>Parallel MCP calls]
        DIAGNOSIS[Diagnosis Node<br/>LLM hypothesis generation]
        VERIFY[Verification Node<br/>Targeted checks + LLM eval]
        RECOVERY[Recovery Proposal<br/>Remediation planning]
        APPROVAL[Approval Handler<br/>Slack/CLI approval]
        EXECUTION[Execution Node<br/>Run remediation]
        POSTMORTEM[Post-Mortem<br/>Generate report]
        ESCALATE[Escalation<br/>Human handoff]
    end

    subgraph "State Management"
        CHECKPOINT[(LangGraph Checkpoint<br/>SQLite/Postgres)]
    end

    subgraph "MCP Servers - Eval Mode"
        MOCK_K8S[Mock Kubernetes<br/>Fixture-based]
        MOCK_GH[Mock GitHub<br/>Fixture-based]
        MOCK_SLACK[Mock Slack<br/>Fixture-based]
        MOCK_OBS[Mock Observability<br/>Fixture-based]
    end

    subgraph "MCP Servers - Live Mode"
        REAL_K8S[Real Kubernetes<br/>via stdio]
        REAL_GH[Real GitHub<br/>via stdio]
        REAL_SLACK[Real Slack<br/>via stdio]
        REAL_OBS[Real Observability<br/>via stdio]
    end

    subgraph "Custom MCP Server"
        RUNBOOK[Runbook Correlator<br/>Search + Deploy Analysis]
    end

    subgraph "Observability"
        DASHBOARD[Streamlit Dashboard<br/>Investigation tracking]
        EVAL[Eval Harness<br/>Automated scoring]
    end

    WEBHOOK --> INTAKE
    CLI --> INTAKE

    INTAKE --> EVIDENCE
    EVIDENCE --> DIAGNOSIS
    DIAGNOSIS --> VERIFY

    VERIFY -->|Confirmed| RECOVERY
    VERIFY -->|Refuted| DIAGNOSIS
    VERIFY -->|Inconclusive<br/>Max rounds| ESCALATE

    RECOVERY --> APPROVAL
    APPROVAL -->|Approved| EXECUTION
    APPROVAL -->|Rejected| POSTMORTEM

    EXECUTION --> POSTMORTEM
    ESCALATE --> POSTMORTEM

    INTAKE -.->|Save state| CHECKPOINT
    EVIDENCE -.->|Save state| CHECKPOINT
    DIAGNOSIS -.->|Save state| CHECKPOINT
    VERIFY -.->|Save state| CHECKPOINT
    RECOVERY -.->|Save state| CHECKPOINT
    EXECUTION -.->|Save state| CHECKPOINT

    EVIDENCE -->|MODE=eval| MOCK_K8S
    EVIDENCE -->|MODE=eval| MOCK_GH
    EVIDENCE -->|MODE=eval| MOCK_SLACK
    EVIDENCE -->|MODE=eval| MOCK_OBS

    EVIDENCE -->|MODE=live| REAL_K8S
    EVIDENCE -->|MODE=live| REAL_GH
    EVIDENCE -->|MODE=live| REAL_SLACK
    EVIDENCE -->|MODE=live| REAL_OBS

    DIAGNOSIS --> RUNBOOK

    CHECKPOINT --> DASHBOARD
    EVAL -.->|Scores against| CHECKPOINT

    style VERIFY fill:#ff9999
    style DIAGNOSIS fill:#ffcc99
    style APPROVAL fill:#99ccff
    style CHECKPOINT fill:#ccffcc
```

## Data Flow

### Investigation Lifecycle

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant MCP
    participant LLM
    participant Checkpoint
    participant Human

    User->>Agent: Trigger investigation
    Agent->>Checkpoint: Initialize state

    Agent->>MCP: Get pod status
    Agent->>MCP: Get logs
    Agent->>MCP: Get events
    Agent->>MCP: Get deploy history
    MCP-->>Agent: Evidence collected

    Agent->>LLM: Generate hypotheses
    LLM-->>Agent: 2-3 ranked hypotheses
    Agent->>Checkpoint: Save hypotheses

    loop Verification Loop
        Agent->>MCP: Run verification checks
        Agent->>LLM: Evaluate hypothesis

        alt Hypothesis Confirmed
            LLM-->>Agent: Confirmed
            Agent->>Checkpoint: Save result
        else Hypothesis Refuted
            LLM-->>Agent: Refuted
            Agent->>Checkpoint: Save result
            Agent->>Agent: Try next hypothesis
        else Inconclusive after max rounds
            LLM-->>Agent: Inconclusive
            Agent->>Agent: Escalate
        end
    end

    Agent->>Agent: Generate recovery proposal
    Agent->>Checkpoint: Save proposal

    alt Live Mode
        Agent->>Human: Request approval (Slack)
        Human-->>Agent: Approve/Reject
    else Eval Mode
        Agent->>Agent: Auto-approve
    end

    alt Approved
        Agent->>MCP: Execute remediation
        MCP-->>Agent: Execution result
    end

    Agent->>Agent: Generate post-mortem
    Agent->>Checkpoint: Mark completed
    Agent->>MCP: Post to Slack
```

## Component Architecture

### LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> Intake
    Intake --> EvidenceGathering
    EvidenceGathering --> Diagnosis
    Diagnosis --> Verification

    Verification --> Diagnosis : Refuted
    Verification --> RecoveryProposal : Confirmed
    Verification --> Escalate : Inconclusive (max rounds)

    RecoveryProposal --> Execution : Approved
    RecoveryProposal --> PostMortem : Rejected

    Execution --> PostMortem
    Escalate --> PostMortem
    PostMortem --> [*]

    note right of Verification
        Key Differentiator:
        Non-linear backtracking
        when hypothesis refuted
    end note

    note right of RecoveryProposal
        Safety Gate:
        Human approval required
        in live mode
    end note
```

### MCP Server Registry

```mermaid
graph LR
    subgraph "Agent Code"
        AGENT[Agent Nodes<br/>Mode-agnostic]
    end

    subgraph "Registry Layer"
        REGISTRY[MCP Registry<br/>MODE env var]
    end

    subgraph "Eval Mode Backends"
        EVAL_FIXTURES[(Fixture Files<br/>scenarios/*/)]
        MOCK1[Mock K8s Server]
        MOCK2[Mock GitHub Server]
        MOCK3[Mock Slack Server]
        MOCK4[Mock Obs Server]
    end

    subgraph "Live Mode Backends"
        LIVE_K8S[Real K8s<br/>kubectl API]
        LIVE_GH[Real GitHub<br/>REST API]
        LIVE_SLACK[Real Slack<br/>Bot API]
        LIVE_OBS[Real Grafana<br/>Query API]
    end

    AGENT --> REGISTRY

    REGISTRY -->|MODE=eval| MOCK1
    REGISTRY -->|MODE=eval| MOCK2
    REGISTRY -->|MODE=eval| MOCK3
    REGISTRY -->|MODE=eval| MOCK4

    MOCK1 --> EVAL_FIXTURES
    MOCK2 --> EVAL_FIXTURES
    MOCK3 --> EVAL_FIXTURES
    MOCK4 --> EVAL_FIXTURES

    REGISTRY -->|MODE=live| LIVE_K8S
    REGISTRY -->|MODE=live| LIVE_GH
    REGISTRY -->|MODE=live| LIVE_SLACK
    REGISTRY -->|MODE=live| LIVE_OBS

    style REGISTRY fill:#ffcc99
    style AGENT fill:#99ccff
```

## Key Design Decisions

### 1. Non-Linear Graph Architecture

**Decision**: Use LangGraph with conditional routing instead of a linear pipeline.

**Rationale**:
- Real incident response requires hypothesis testing with backtracking
- Linear pipelines can't recover from incorrect hypotheses
- Conditional edges enable `refuted → diagnosis` loop

**Trade-offs**:
- ✅ More realistic agent behavior
- ✅ Can recover from wrong paths
- ❌ More complex to reason about
- ❌ Harder to debug state transitions

### 2. Dual-Mode MCP Architecture

**Decision**: Build mock and real MCP servers with transparent mode switching.

**Rationale**:
- Need deterministic eval scenarios with ground truth
- Can't use live APIs in CI/CD testing
- Agent code should be agnostic to backend

**Trade-offs**:
- ✅ Deterministic evaluation
- ✅ Offline development
- ✅ Easy testing
- ❌ Need to maintain two implementations
- ❌ Mock behavior might diverge from real

### 3. Hard Human-in-the-Loop Gate

**Decision**: Require explicit approval before any write action in live mode.

**Rationale**:
- Safety-critical system affecting production
- AI can make mistakes
- Need human judgment for remediation decisions

**Trade-offs**:
- ✅ Safe - prevents unauthorized actions
- ✅ Auditable approval trail
- ❌ Slower incident response
- ❌ Requires human availability

### 4. LangGraph Checkpointing

**Decision**: Use LangGraph's built-in checkpointing instead of custom state management.

**Rationale**:
- Investigations may span hours/days
- Need to survive process restarts
- Full state history for debugging

**Trade-offs**:
- ✅ Automatic state persistence
- ✅ Resumability
- ✅ Full audit trail
- ❌ Database dependency
- ❌ Increased storage usage

### 5. Action Type Allowlist

**Decision**: Hard-coded allowlist of permitted action types.

**Rationale**:
- Prevent novel/dangerous actions
- Explicit vs implicit safety
- Easy to audit and modify

**Trade-offs**:
- ✅ Predictable behavior
- ✅ Easy to reason about
- ❌ Less flexible
- ❌ Requires code change to add actions

## Scalability Considerations

### Current Limitations

**Single Investigation at a Time**:
- Current implementation processes one investigation per agent instance
- For concurrent investigations, run multiple agent processes

**Checkpoint Database**:
- SQLite for development (single-file database)
- Migrate to Postgres for production with concurrent access

**MCP Server Processes**:
- Each server runs as a subprocess
- For high load, consider server pooling or remote MCP servers

### Scaling Strategy

**Horizontal Scaling**:
```
Load Balancer
    ├─> Agent Instance 1 (handles investigation A)
    ├─> Agent Instance 2 (handles investigation B)
    └─> Agent Instance 3 (handles investigation C)
         │
         └─> Shared Postgres Checkpoint Database
```

**Async Processing**:
```
Webhook → Message Queue → Agent Workers → Checkpoint DB
                         ↓
                    Slack Notifications
```

## Security Model

### Threat Model

**In Scope**:
- Unauthorized remediation actions
- Credential leakage in logs
- Malicious input via webhooks

**Out of Scope** (for this demo):
- DDoS protection
- Rate limiting
- Multi-tenancy

### Security Controls

1. **Action Allowlist**: Only permitted actions can execute
2. **Approval Gate**: Human approval required in live mode
3. **Audit Logging**: All decisions logged with reasoning
4. **Credential Management**: Env vars, not hardcoded
5. **Input Validation**: Structured state types with TypedDict

## Performance Characteristics

### Latency

Typical investigation timeline (eval mode):

```
Intake:             ~0.1s  (parse manifest)
Evidence Gathering: ~1.0s  (parallel MCP calls)
Diagnosis:          ~3.0s  (LLM hypothesis generation)
Verification:       ~2.0s  (LLM evaluation + checks)
Recovery Proposal:  ~0.5s  (template remediation)
Execution:          ~0.5s  (simulated)
Post-Mortem:        ~0.5s  (generate report)
────────────────────────────
Total:              ~7.6s
```

Live mode adds:
- Real MCP server calls: +2-5s
- Human approval wait: +30s-5min
- Real remediation execution: +10-60s

### Cost

Per investigation (estimated):

```
LLM Calls:
  - Diagnosis: 1 call × 2000 tokens × $3/M = $0.006
  - Verification: 1-3 calls × 1000 tokens × $3/M = $0.003-$0.009
  ─────────────────────────────────────────────────
  Total per investigation: $0.009-$0.015

MCP Tool Calls: Free (local or API-specific costs)
```

Target: ≤ $0.015 per investigation (from eval goals)

## Monitoring and Observability

### Metrics Tracked

1. **Investigation Metrics**:
   - Time to diagnosis
   - Time to resolution
   - Verification rounds
   - Hypothesis acceptance rate

2. **System Metrics**:
   - Investigations per hour
   - Completion rate
   - Escalation rate
   - Average cost

3. **Quality Metrics** (from eval harness):
   - Root cause accuracy
   - Remediation acceptability

### Logging Strategy

```python
# Structured logging at each node
logger.info("Starting evidence gathering", extra={
    "thread_id": thread_id,
    "service": incident.service,
    "severity": incident.severity
})

# All tool calls logged
logger.info("MCP tool call", extra={
    "service": "kubernetes",
    "tool": "k8s_get_pod_status",
    "args": {...}
})
```

## Future Architecture Evolution

### Short Term

1. **Webhook Integration**: FastAPI endpoint for PagerDuty
2. **Slack Notifications**: Real-time updates during investigation
3. **Metrics Dashboard**: Grafana integration for agent metrics

### Long Term

1. **Multi-Incident Triage**: Queue and prioritize multiple incidents
2. **Learning from Past**: Fine-tune on successful investigations
3. **Proactive Monitoring**: Predict incidents before they occur
4. **Multi-Cloud**: Support AWS, GCP, Azure
5. **Plugin System**: Custom MCP servers for proprietary tools

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Anthropic API](https://docs.anthropic.com/claude/reference/getting-started)
