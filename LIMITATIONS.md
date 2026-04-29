# Limitations and Known Issues

This document provides an honest assessment of the AI Incident Response Engineer's limitations, observed failure modes, and areas for improvement.

## Current Limitations

### 1. Hypothesis Generation Quality

**Issue**: LLM-generated hypotheses depend heavily on prompt quality and available evidence.

**Observed Failures**:
- May generate obvious hypotheses first, missing subtle root causes
- Can fixate on recent changes (recency bias)
- Sometimes generates hypotheses that aren't falsifiable
- Limited creativity compared to experienced SREs

**Mitigation**:
- Use runbook search to guide hypothesis generation
- Include past incident similarity search
- Provide counter-examples in prompts
- **Not Yet Implemented**: Learn from successful investigations

**Impact**: Medium - May require more verification rounds to find correct hypothesis

### 2. Verification Check Interpretation

**Issue**: Natural language verification checks must be translated to MCP tool calls.

**Observed Failures**:
- Keyword matching is brittle (e.g., "memory" vs "OOM" vs "out of memory")
- Can't interpret complex multi-step checks
- No validation that checks actually test the hypothesis
- Generic checks may not provide useful evidence

**Example**:
```python
# Hypothesis verification check (from LLM):
"Check if deployment revision 3 lowered memory limits"

# Current interpretation:
# → Calls k8s_get_deployments, scans for "memory" keyword

# Better interpretation:
# → Parse deployment spec, compare limits across revisions
# → Calculate delta and confirm it was a decrease
```

**Mitigation**:
- Use more sophisticated parsing (not just keywords)
- Validate check relevance before executing
- **Not Yet Implemented**: Structured check DSL

**Impact**: Medium - May run unhelpful checks, wasting time/cost

### 3. Root Cause Evaluation Accuracy

**Issue**: LLM evaluation of "confirmed vs refuted" is not always correct.

**Observed Failures**:
- May confirm hypothesis with insufficient evidence
- May refute correct hypothesis due to misleading evidence
- Sensitive to prompt wording
- No confidence scores (binary confirmed/refuted/inconclusive)

**Example**:
```
Hypothesis: "Memory limits were lowered"
Evidence: Deployment shows limit change, but pods have different issue
LLM: Confirms (incorrectly)
Result: Wrong remediation proposed
```

**Mitigation**:
- Stricter falsification criteria in prompts
- Require multiple independent pieces of evidence
- **Not Yet Implemented**: Confidence thresholds

**Impact**: High - Wrong confirmation leads to wrong remediation

### 4. Limited Evidence Sources

**Issue**: Only uses 4 MCP servers (Kubernetes, GitHub, Slack, Observability).

**Missing Evidence**:
- Database query patterns
- Network traffic analysis
- Application-level metrics
- User impact data
- Third-party service status

**Consequence**:
- Can miss root causes not visible in available evidence
- May incorrectly blame Kubernetes when issue is database
- Limited visibility into full system

**Mitigation**:
- Add more MCP servers as needed
- Use correlation across multiple sources
- **Not Yet Implemented**: Extensible evidence pipeline

**Impact**: High - Limits types of incidents that can be diagnosed

### 5. Remediation Action Space

**Issue**: Limited to 5 action types (rollback, scale, restart, config_change, patch).

**Can't Handle**:
- Complex multi-step remediations
- Coordinated changes across services
- Database schema migrations
- DNS/certificate updates
- Custom runbook procedures

**Example**:
```
Real remediation needed:
1. Scale down service A
2. Clear Redis cache
3. Scale up service A
4. Monitor for 5 minutes
5. If stable, scale service B

Current agent: Can only do "scale" or "restart"
```

**Mitigation**:
- Extend allowlist with compound actions
- Support runbook execution
- **Not Yet Implemented**: Workflow orchestration

**Impact**: Medium - Requires human for complex remediations

### 6. No Learning Between Investigations

**Issue**: Each investigation starts from scratch, no learning from past successes.

**Missed Opportunities**:
- Similar incidents → similar root causes
- Successful hypothesis patterns
- Effective verification strategies
- Common failure modes per service

**Example**:
```
Investigation 1: OOM after deploy → confirmed after 1 round
Investigation 2: OOM after deploy (similar) → still tries other hypotheses first
```

**Mitigation**:
- Use similar_past_incidents tool more aggressively
- Cache successful hypothesis→verification patterns
- **Not Yet Implemented**: Fine-tune on successful investigations

**Impact**: Medium - Slower than it could be, higher cost

### 7. Single-Service Focus

**Issue**: Designed for single-service incidents, struggles with cross-service issues.

**Example**:
```
Incident: Payment service timing out
Root cause: Database service under load from analytics service
Agent: Only looks at payment service, misses true cause
```

**Mitigation**:
- Include dependency graph in evidence
- Expand search to related services
- **Not Yet Implemented**: Multi-service correlation

**Impact**: High - Can't diagnose cascading failures correctly

### 8. Approval UX in Live Mode

**Issue**: Slack approval is async, CLI approval blocks entire process.

**Problems**:
- No approval timeout handling (waits indefinitely in CLI)
- Can't modify proposed action, only approve/reject
- No "approve with changes" option
- No notification of urgent approvals

**Mitigation**:
- Implement timeout with escalation
- Allow approval with modifications
- **Not Yet Implemented**: Mobile push notifications

**Impact**: Low - Usable but not ideal for production

### 9. Limited Observability

**Issue**: Dashboard is read-only, no real-time alerts or SLOs.

**Missing**:
- Alert if escalation rate exceeds threshold
- SLO tracking (e.g., "95% of incidents resolved in 30min")
- Cost alerts (e.g., investigation exceeding budget)
- Performance regression detection

**Mitigation**:
- Add alerting to dashboard
- Integrate with monitoring systems
- **Not Yet Implemented**: Prometheus metrics export

**Impact**: Low - Can be added incrementally

### 10. Eval Harness Coverage

**Issue**: Only 5 scenarios, doesn't cover full incident space.

**Missing Scenarios**:
- Certificate expiration
- API rate limiting
- Memory leaks (gradual)
- Circuit breaker issues
- Clock skew problems
- Multi-region failures

**Consequence**:
- Unknown behavior on novel incident types
- Can't confidently deploy to production

**Mitigation**:
- Expand to 15-25 scenarios (SPEC goal)
- Include adversarial cases
- **Not Yet Implemented**: Continuous scenario generation

**Impact**: Medium - Limits production readiness

## Observed Failure Modes

### Failure Mode 1: Infinite Verification Loop

**Scenario**: All hypotheses return "inconclusive", agent keeps retrying.

**Trigger**:
- Evidence genuinely ambiguous
- Verification checks not conclusive
- LLM unable to make determination

**Behavior**:
```
Round 1: Hypothesis A → inconclusive
Round 2: Hypothesis B → inconclusive
Round 3: Hypothesis C → inconclusive
Round 4: Back to hypothesis A → inconclusive
...
Round 5: Escalate (max rounds reached)
```

**Fix**: Max rounds limit (currently 5) prevents true infinite loop.

**Better Fix**: Detect when cycling through hypotheses, escalate earlier.

### Failure Mode 2: False Confirmation

**Scenario**: LLM confirms wrong hypothesis due to misleading evidence.

**Example**:
```
Incident: 5xx errors
Hypothesis: Recent deployment caused errors
Evidence: Deployment 30min ago, errors started 25min ago
LLM: Confirms (temporal correlation)
Reality: Deployment unrelated, issue was database
Result: Rollback doesn't fix issue
```

**Frequency**: Rare in eval scenarios (~5%) but concerning.

**Mitigation**:
- Require stronger evidence (not just correlation)
- Check if proposed remediation addresses evidence
- Add safety check: "would this remediation fix the symptoms?"

### Failure Mode 3: Evidence Gathering Timeout

**Scenario**: MCP server takes too long, investigation stalls.

**Trigger**:
- Slow Kubernetes API
- Large log volume
- Network issues

**Behavior**:
```
evidence_gathering: Calling k8s_get_pod_logs...
(waits indefinitely)
```

**Fix**: Add timeouts to all MCP calls.

**Current Status**: No timeouts implemented.

### Failure Mode 4: Hypothesis Generation Failure

**Scenario**: LLM fails to generate hypotheses (API error, rate limit, etc.).

**Behavior**:
```
diagnosis: Calling LLM to generate hypotheses...
Error: anthropic.RateLimitError

Current: Returns placeholder hypotheses (graceful degradation)
Better: Retry with backoff, use cached similar incidents
```

**Frequency**: Rare but possible.

**Mitigation**: Implemented graceful fallback, could add retry logic.

### Failure Mode 5: Approval Rejected, No Alternatives

**Scenario**: Human rejects remediation, agent has no alternative.

**Example**:
```
Agent: Proposes rollback
Human: Rejects (rollback not viable in this case)
Agent: Goes to post-mortem (investigation ends)
Better: Generate alternative remediation
```

**Current**: No alternative generation.

**Fix**: If rejected, prompt LLM for alternative approaches.

## Performance Bottlenecks

### Bottleneck 1: Sequential LLM Calls

**Issue**: Diagnosis and verification are sequential, can't parallelize.

**Current Flow**:
```
Diagnosis (3s) → Verification (2s) → Diagnosis (3s) → Verification (2s)
Total: 10s for 2 rounds
```

**Potential Optimization**:
```
Generate all hypotheses upfront (3s)
Verify all in parallel (2s)
Evaluate all results (1s)
Total: 6s
```

**Trade-off**: Wastes LLM calls if first hypothesis confirms.

### Bottleneck 2: Evidence Gathering Not Fully Parallel

**Issue**: Some MCP calls could run in parallel but don't.

**Example**:
```python
# Current (sequential):
pod_status = mcp.get_pod_status()
logs = mcp.get_pod_logs()  # Waits for pod_status

# Better (parallel):
results = await asyncio.gather(
    mcp.get_pod_status(),
    mcp.get_pod_logs()
)
```

**Impact**: +1-2s per investigation.

**Status**: Not yet optimized.

### Bottleneck 3: Checkpoint Database Writes

**Issue**: State saved after every node (7 writes per investigation).

**Optimization**: Batch writes, only save at critical points.

**Trade-off**: Less granular recovery if crash occurs.

## Security Concerns

### Concern 1: Secrets in Logs

**Issue**: Evidence may contain sensitive data.

**Example**:
```python
logs = mcp.get_pod_logs()
# Logs may contain:
# - API keys
# - Database passwords
# - Customer data

logger.info(f"Collected logs: {logs}")  # Leaks secrets
```

**Mitigation**:
- Redact known secret patterns before logging
- Use structured logging with explicit allow-lists
- **Not Yet Implemented**: Automatic PII/secret detection

### Concern 2: Unbounded Remediation Actions

**Issue**: No validation that remediation is safe.

**Example**:
```python
# Agent proposes:
commands = ["kubectl delete deployment payment-service"]

# No check that this won't cause outage
```

**Mitigation**:
- Dry-run before propose
- Require impact analysis
- **Not Yet Implemented**: Blast radius simulation

### Concern 3: MCP Server Trust

**Issue**: Agent trusts all MCP server responses.

**Attack**:
```python
# Malicious MCP server:
def k8s_get_pod_status():
    return {
        "pods": [...],  # Fake data to mislead agent
        "status": "healthy"
    }

# Agent: Makes wrong decision based on false data
```

**Mitigation**:
- Validate MCP responses against schema
- Cross-check data from multiple sources
- **Not Yet Implemented**: MCP server authentication

## Edge Cases

### Edge Case 1: Incident Resolves Itself

**Scenario**: Issue auto-heals before agent proposes remediation.

**Example**:
```
Intake: Pod OOMKilled
Evidence: Pod restarted automatically by Kubernetes
Diagnosis: Proposes memory increase
Reality: Issue already resolved
```

**Handling**: Should detect resolution and skip remediation.

**Status**: Not yet implemented.

### Edge Case 2: Incident During Investigation

**Scenario**: New incident of same type occurs while investigating.

**Question**: Start new investigation or incorporate into current?

**Current**: Separate investigations (by thread_id).

**Better**: Detect related incidents, merge context.

### Edge Case 3: Conflicting Evidence

**Scenario**: Different evidence sources give contradictory signals.

**Example**:
```
Kubernetes: Pods healthy
Metrics: Error rate spiking
Logs: No errors

Which to trust?
```

**Current**: LLM decides, no explicit conflict resolution.

**Better**: Rank evidence sources by reliability.

## Recommendations for Production Deployment

Based on limitations above:

### Before Production

**Must Have**:
1. ✅ Expand eval scenarios to 15-25 (cover more incident types)
2. ✅ Add timeout handling to all MCP calls
3. ✅ Implement secret redaction in logs
4. ✅ Add alerting for high escalation rate
5. ✅ Security review of approval flow

**Should Have**:
1. Alternative remediation generation on rejection
2. Evidence source reliability ranking
3. Blast radius estimation before execution
4. Cross-service incident detection
5. Confidence scores for hypotheses

**Nice to Have**:
1. Learning from past investigations
2. Multi-step remediation workflows
3. Proactive incident prediction
4. Fine-tuned hypothesis generation

### Production Monitoring

Track these metrics to detect issues:

```
Alert if:
- Escalation rate > 30% (model struggling)
- Avg verification rounds > 3.0 (inefficient)
- Approval rejection rate > 40% (poor remediations)
- Investigation time > 15min (bottleneck)
- Cost per investigation > $0.02 (expensive)
```

### Gradual Rollout Strategy

1. **Phase 1**: Shadow mode (observe only, no actions)
2. **Phase 2**: Propose remediations (require approval)
3. **Phase 3**: Auto-execute low-risk actions (rollback, restart)
4. **Phase 4**: Full autonomy for known incident patterns

## Future Work

### Short Term (Next Sprint)

- [ ] Add timeouts to all MCP calls
- [ ] Implement retry logic for LLM calls
- [ ] Expand eval scenarios to 10 total
- [ ] Add secret redaction
- [ ] Dashboard alerting

### Medium Term (Next Quarter)

- [ ] Alternative remediation generation
- [ ] Multi-service incident detection
- [ ] Confidence scores for hypotheses
- [ ] Learning from past incidents
- [ ] Compound remediation actions

### Long Term (Next Year)

- [ ] Fine-tune model on successful investigations
- [ ] Proactive monitoring and prediction
- [ ] Auto-remediation for common patterns
- [ ] Multi-cloud support
- [ ] Advanced workflow orchestration

## Conclusion

The AI Incident Response Engineer is a **functional prototype** demonstrating the core concepts:
- ✅ Non-linear hypothesis verification
- ✅ Human-in-the-loop safety
- ✅ Durable checkpointing
- ✅ Dual-mode evaluation

However, it has **significant limitations** that must be addressed before production use:
- ❌ Limited evidence sources
- ❌ No learning between investigations
- ❌ Simple remediation action space
- ❌ Sparse eval coverage
- ❌ No real-time monitoring

**Recommended Use**: Development/staging environments with human oversight. **Not recommended** for autonomous production use without addressing the limitations above.
