# Worked Example: OOM After Deploy

This document walks through a complete investigation from alert to resolution, showing the actual agent behavior and decision-making process.

## Scenario

**Service**: `payment-service`
**Severity**: Critical
**Symptom**: Pods are crashing with OOMKilled status
**Timeline**: Started 15 minutes ago

## Investigation Transcript

### Step 1: Intake (0:00)

**Input**: Alert received from monitoring system

```json
{
  "alert_id": "ALERT-2025-001",
  "service": "payment-service",
  "severity": "critical",
  "description": "Multiple pods OOMKilled in payment-service deployment",
  "time_window_start": "2025-01-15T14:30:00Z",
  "time_window_end": "2025-01-15T14:45:00Z",
  "affected_pods": ["payment-service-v2-abc123", "payment-service-v2-def456"],
  "affected_endpoints": ["/api/v1/process-payment"]
}
```

**Agent Action**: Parse incident into structured format

**Output**:
```
✓ Incident parsed successfully
  Service: payment-service
  Severity: critical
  Time Window: 14:30 - 14:45 (15 minutes)
  Affected: 2 pods, 1 endpoint
```

**State**: `status = "intake"` → `status = "gathering_evidence"`

---

### Step 2: Evidence Gathering (0:01)

**Agent Action**: Fan out to gather evidence from multiple sources in parallel

**MCP Calls Made**:
```
[1] kubernetes.k8s_get_pod_status(namespace="default", label_selector="app=payment-service")
[2] kubernetes.k8s_get_pod_logs(pod_name="payment-service-v2-abc123", tail=100)
[3] kubernetes.k8s_get_events(namespace="default", field_selector="involvedObject.name=payment-service")
[4] kubernetes.k8s_get_deployments(namespace="default", deployment_name="payment-service")
[5] github.github_get_recent_commits(repo="payment-service", limit=10)
[6] observability.obs_get_service_health(service="payment-service", time_window="1h")
```

**Evidence Collected**:

**Pod Status**:
```yaml
pods:
  - name: payment-service-v2-abc123
    status: OOMKilled
    restarts: 3
    memory_usage: 512Mi
    memory_limit: 512Mi  # ← At limit
    image: payment-service:v2.1.0

  - name: payment-service-v2-def456
    status: OOMKilled
    restarts: 2
    memory_usage: 512Mi
    memory_limit: 512Mi  # ← At limit
    image: payment-service:v2.1.0

  - name: payment-service-v1-xyz789
    status: Running
    restarts: 0
    memory_usage: 1.8Gi
    memory_limit: 2Gi  # ← Different limit!
    image: payment-service:v2.0.9
```

**Deployment History**:
```yaml
revisions:
  - revision: 3
    created: 2025-01-15T14:25:00Z  # ← 5 minutes before incident
    image: payment-service:v2.1.0
    replicas: 3
    memory_limit: 512Mi  # ← Changed!
    memory_request: 256Mi

  - revision: 2
    created: 2025-01-10T10:00:00Z
    image: payment-service:v2.0.9
    replicas: 3
    memory_limit: 2Gi  # ← Previous value
    memory_request: 1Gi
```

**Events**:
```
14:32 | Pod/payment-service-v2-abc123 | OOMKilled | Container exceeded memory limit
14:35 | Pod/payment-service-v2-abc123 | Killing | Stopping container
14:36 | Pod/payment-service-v2-abc123 | Started | Container restarted
14:38 | Pod/payment-service-v2-abc123 | OOMKilled | Container exceeded memory limit again
...
```

**GitHub Commits**:
```
[1] 2025-01-15 14:20 | feat: optimize payment processing (v2.1.0)
    Author: dev@example.com
    Files: payment_processor.py, config.yaml

[2] 2025-01-15 14:00 | chore: reduce resource requests for cost savings
    Author: devops@example.com
    Files: k8s/deployment.yaml
    Changes: memory: 2Gi → 512Mi  # ← Smoking gun!
```

**Output**:
```
✓ Evidence collected from 4 sources
  - 3 pods examined (2 OOMKilled, 1 healthy)
  - 6 events related to OOM
  - 3 deployment revisions found
  - 10 recent commits retrieved
  - Service health metrics collected
```

**State**: `status = "gathering_evidence"` → `status = "diagnosing"`

---

### Step 3: Diagnosis (0:04)

**Agent Action**: Use LLM to generate hypotheses based on evidence

**LLM Prompt** (simplified):
```
You are diagnosing a production incident. Given the evidence below, generate 2-3 ranked hypotheses about the root cause.

Service: payment-service
Symptom: Pods crashing with OOMKilled

Evidence:
- 2 pods using v2.1.0 are OOMKilled (memory: 512Mi limit)
- 1 pod using v2.0.9 is healthy (memory: 2Gi limit)
- Deployment revision 3 (5min ago) changed memory limit from 2Gi to 512Mi
- Recent commit: "reduce resource requests for cost savings"

For each hypothesis, provide:
1. Description
2. Falsification criterion ("if X is true, this hypothesis is wrong")
3. Verification checks (specific things to verify)

Output as JSON.
```

**LLM Response**:
```json
{
  "hypotheses": [
    {
      "rank": 1,
      "description": "Memory limits were lowered from 2Gi to 512Mi in deployment revision 3, causing the pods to exceed their new allocation and get OOMKilled",
      "falsification_criterion": "If pods with 512Mi limit are not exceeding memory usage, or if memory limit was not changed in revision 3, this hypothesis is wrong",
      "supporting_evidence": [
        "Deployment revision 3 shows memory limit change from 2Gi to 512Mi",
        "OOMKilled pods have memory usage at 512Mi limit",
        "Healthy pod (v2.0.9) has 2Gi limit and is not OOMing",
        "Timing matches: revision 3 deployed 5min before incident started"
      ],
      "verification_checks": [
        "Confirm deployment revision 3 changed memory limits",
        "Verify OOM events started after revision 3 deployment",
        "Check if v2.1.0 code change affects memory usage"
      ]
    },
    {
      "rank": 2,
      "description": "New code in v2.1.0 introduced a memory leak causing gradual memory increase",
      "falsification_criterion": "If memory usage is not increasing over time, or if v2.0.9 has same memory pattern, this hypothesis is wrong",
      "supporting_evidence": [
        "v2.1.0 commit mentions 'optimize payment processing'",
        "Code change could have introduced inefficiency"
      ],
      "verification_checks": [
        "Check memory usage trend over time",
        "Compare memory profile of v2.1.0 vs v2.0.9",
        "Review code changes in payment_processor.py"
      ]
    },
    {
      "rank": 3,
      "description": "Increased traffic or request size causing higher memory usage",
      "falsification_criterion": "If traffic volume and request patterns are unchanged, this hypothesis is wrong",
      "supporting_evidence": [
        "Could be external factor unrelated to deploy"
      ],
      "verification_checks": [
        "Check request rate and size during incident window",
        "Compare to baseline traffic patterns"
      ]
    }
  ]
}
```

**Output**:
```
✓ Generated 3 hypotheses:
  [1] Memory limits lowered in deployment (rank 1)
  [2] Memory leak in v2.1.0 code (rank 2)
  [3] Increased traffic causing higher usage (rank 3)
```

**State**: `status = "diagnosing"` → `status = "verifying"`

---

### Step 4: Verification - Hypothesis #1 (0:06)

**Agent Action**: Test the top hypothesis against falsification criteria

**Hypothesis Being Tested**:
```
Memory limits were lowered from 2Gi to 512Mi in deployment revision 3,
causing pods to exceed their new allocation
```

**Verification Checks Interpreted**:
```python
# Check 1: "Confirm deployment revision 3 changed memory limits"
mcp.call_tool("kubernetes", "k8s_get_deployments", {...})

# Check 2: "Verify OOM events started after revision 3"
mcp.call_tool("kubernetes", "k8s_get_events", {...})

# Check 3: "Check if v2.1.0 code change affects memory usage"
mcp.call_tool("github", "github_get_commit_diff", {...})
```

**Verification Evidence Collected**:
```yaml
deployment_check:
  revision_2:
    memory_limit: 2Gi
    deployed: 2025-01-10T10:00:00Z
  revision_3:
    memory_limit: 512Mi  # ✓ Confirmed change
    deployed: 2025-01-15T14:25:00Z

event_timeline:
  14:25:00 | Deployment revision 3 created
  14:27:00 | Pods rolling update started
  14:32:00 | First OOMKilled event  # ✓ After deployment
  14:35:00 | Second OOMKilled event
  ...

code_diff:
  payment_processor.py:
    + # Optimized caching for faster processing
    + # No significant memory changes observed
  Files changed: 2 insertions, 0 deletions (minimal change)
```

**LLM Evaluation Prompt**:
```
Hypothesis: Memory limits were lowered from 2Gi to 512Mi in deployment revision 3

Falsification criterion: If pods with 512Mi limit are not exceeding memory usage,
or if memory limit was not changed in revision 3, this hypothesis is wrong

Evidence:
- Deployment revision 3 DID change memory limit from 2Gi to 512Mi ✓
- OOMKilled events started 7 minutes after revision 3 deployment ✓
- Pods ARE using 512Mi (at their limit) ✓
- v2.1.0 code changes are minimal (caching optimization, no major memory changes)
- Healthy pod with 2Gi limit is NOT OOMing ✓

Question: Is this hypothesis CONFIRMED, REFUTED, or INCONCLUSIVE?

Return JSON with: {"status": "confirmed|refuted|inconclusive", "reasoning": "..."}
```

**LLM Evaluation**:
```json
{
  "status": "confirmed",
  "reasoning": "The hypothesis is confirmed. All evidence supports it: (1) Memory limit was definitively changed from 2Gi to 512Mi in revision 3, (2) OOM events began immediately after this deployment, (3) Affected pods are hitting the new 512Mi limit, (4) The pod with the old 2Gi limit remains healthy, (5) Code changes in v2.1.0 are minimal and don't explain the memory usage. The falsification criterion is NOT met (limits WERE changed and pods ARE exceeding them), therefore the hypothesis is confirmed."
}
```

**Output**:
```
✓ Hypothesis #1 CONFIRMED

  Root Cause: Memory limits were lowered from 2Gi to 512Mi in deployment
              revision 3, causing pods to exceed their allocation

  Reasoning: Deployment revision 3 changed memory limit from 2Gi to 512Mi.
             OOM events started immediately after deployment. Affected pods
             are hitting the 512Mi limit while the pod with 2Gi remains healthy.
             Code changes are minimal and don't explain the memory usage.
```

**State**: `status = "verifying"` → `status = "awaiting_approval"`

---

### Step 5: Recovery Proposal (0:07)

**Agent Action**: Generate remediation plan based on confirmed root cause

**Remediation Logic**:
```python
# Root cause: Memory limit too low
# Services: payment-service needs ~2Gi based on historical healthy usage

# Appropriate actions:
# - rollback: Revert to revision 2 (2Gi limit)
# - config_change: Update revision 3 to use 2Gi

# Choose: rollback (faster, lower risk)
```

**Recovery Proposal**:
```yaml
action_type: rollback
description: Rollback payment-service deployment to revision 2 to restore 2Gi memory limits
expected_effect: Pods will restart with 2Gi memory limits and should stop OOMKilling
blast_radius: Medium - affects all payment-service pods (rolling update, ~2min downtime per pod)
commands:
  - kubectl rollout undo deployment/payment-service -n default --to-revision=2
dry_run_output: null  # Would run kubectl --dry-run in live mode
```

**Output**:
```
🛠️  RECOVERY PROPOSAL

Action: rollback
Description: Rollback payment-service deployment to revision 2 to restore 2Gi memory limits

Expected Effect: Pods will restart with 2Gi memory limits and stop OOMKilling
Blast Radius: Medium - affects all payment-service pods

Commands:
  $ kubectl rollout undo deployment/payment-service -n default --to-revision=2
```

**State**: `status = "awaiting_approval"`

---

### Step 6: Approval (0:08)

**Mode: Eval** - Auto-approve (for testing)

```
✓ Action type 'rollback' is in allowlist
✓ Auto-approved in eval mode
```

**Mode: Live** - Would request human approval via Slack:

```
┌─────────────────────────────────────────────┐
│ 🔔 Approval Required: rollback              │
├─────────────────────────────────────────────┤
│ Action: rollback                            │
│ Description: Rollback payment-service       │
│              deployment to restore 2Gi      │
│              memory limits                  │
│                                             │
│ Expected Effect: Pods will stop OOMKilling  │
│ Blast Radius: Medium - affects all pods    │
│                                             │
│ Commands:                                   │
│   kubectl rollout undo deployment/...      │
├─────────────────────────────────────────────┤
│        [Approve]         [Reject]           │
└─────────────────────────────────────────────┘
```

**Approval Decision**:
```json
{
  "status": "approved",
  "reasoning": "Auto-approved in eval mode",
  "decided_by": "auto-approve",
  "method": "auto_approve"
}
```

**State**: `status = "awaiting_approval"` → `status = "executing"`

---

### Step 7: Execution (0:09)

**Agent Action**: Execute approved remediation

**Commands Executed** (simulated in eval mode):
```bash
$ kubectl rollout undo deployment/payment-service -n default --to-revision=2

# In live mode, this would actually run:
# - Check current revision (3)
# - Find revision 2 in history
# - Trigger rolling update back to revision 2
# - Monitor rollout status
# - Wait for completion
```

**Execution Result**:
```
✓ Rollback executed successfully

deployment.apps/payment-service rolled back to revision 2

Rollout Status:
  ✓ Waiting for rollout to finish: 1 out of 3 new replicas updated...
  ✓ Waiting for rollout to finish: 2 out of 3 new replicas updated...
  ✓ Waiting for rollout to finish: 3 out of 3 new replicas updated...
  ✓ Rollout complete! 3/3 replicas available

Verification (30s later):
  ✓ 0 OOMKilled events in last 5 minutes
  ✓ All 3 pods running with 2Gi memory limit
  ✓ Memory usage stable at ~1.8Gi per pod
  ✓ Service health check: PASSING
```

**Output**:
```
✅ REMEDIATION SUCCESSFUL

Rollback completed in 2m30s
All pods now running with 2Gi memory limits
No OOM events observed since rollback
Service is healthy
```

**State**: `status = "executing"` → `status = "completed"`

---

### Step 8: Post-Mortem (0:12)

**Agent Action**: Generate incident report

**Post-Mortem Document**:
```markdown
# Incident Post-Mortem: payment-service OOMKilled

**Incident ID**: ALERT-2025-001
**Severity**: Critical
**Duration**: 15 minutes (incident) + 12 minutes (investigation & resolution)
**Status**: Resolved

## Timeline

| Time | Event |
|------|-------|
| 14:25 | Deployment revision 3 created with 512Mi memory limit |
| 14:27 | Rolling update started (revision 3) |
| 14:30 | **INCIDENT START** - Monitoring alert triggered |
| 14:32 | First pod OOMKilled |
| 14:35 | Second pod OOMKilled |
| 14:42 | **INVESTIGATION START** - AI agent triggered |
| 14:43 | Evidence gathered from K8s, GitHub, metrics |
| 14:46 | Hypothesis confirmed: Memory limit too low |
| 14:47 | Rollback proposed and approved |
| 14:50 | Rollback executed (revision 2) |
| 14:52 | **INCIDENT END** - All pods healthy |

## Root Cause

Memory limits were reduced from 2Gi to 512Mi in deployment revision 3 as part of a cost optimization effort. The payment-service application requires approximately 1.8-2.0Gi of memory under normal load, which exceeds the new 512Mi limit, causing pods to be OOMKilled by the Kubernetes kubelet.

## Contributing Factors

1. Memory limit change was not tested in staging before production deploy
2. No alert on memory limit configuration changes
3. Resource requirements not documented for payment-service
4. Cost optimization change applied without understanding actual usage

## Remediation

**Action Taken**: Rolled back deployment to revision 2 (2Gi memory limit)

**Result**: All pods returned to healthy state, no further OOM events observed

## Action Items

1. **[P0] Document** actual memory requirements for payment-service (Owner: SRE Team)
2. **[P0] Add alerts** on Kubernetes resource limit configuration changes (Owner: Platform Team)
3. **[P1] Implement** staging environment testing for all deployments (Owner: DevOps Team)
4. **[P1] Review** memory limits across all services to ensure adequacy (Owner: SRE Team)
5. **[P2] Investigate** memory usage optimization in payment-service to reduce from 2Gi (Owner: Dev Team)

## Lessons Learned

### What Went Well
- AI agent correctly identified root cause in <5 minutes
- Rollback was smooth with no service disruption
- Monitoring alerts triggered appropriately

### What Could Be Improved
- Resource changes should require review by SRE team
- Memory limits should be based on actual usage metrics, not arbitrary cost targets
- Need automated testing of resource configurations

## Metrics

- **Detection Time**: 2 minutes (from first OOM to alert)
- **Investigation Time**: 5 minutes (from alert to confirmed root cause)
- **Resolution Time**: 5 minutes (from approval to all pods healthy)
- **Total Incident Duration**: 22 minutes
- **Affected Requests**: ~450 failed payment requests (estimated)
- **Financial Impact**: ~$1,200 in failed transactions

---

*Generated by AI Incident Response Engineer*
*Investigation Thread ID: incident_oom_after_deploy*
```

**Output**:
```
📝 Post-mortem generated

Key Findings:
  ✓ Root cause: Memory limit reduced from 2Gi to 512Mi
  ✓ Resolution: Rollback to previous deployment
  ✓ Duration: 22 minutes total
  ✓ 5 action items created

Post-mortem saved to checkpoint database
Ready for review and Slack posting
```

**State**: `status = "completed"`

---

## Summary

**Investigation Statistics**:

| Metric | Value |
|--------|-------|
| Total Duration | 12 minutes |
| Verification Rounds | 1 (first hypothesis confirmed) |
| MCP Tool Calls | 6 (evidence) + 3 (verification) = 9 |
| LLM Calls | 2 (diagnosis + verification) |
| Estimated Cost | ~$0.009 |
| Root Cause Accuracy | ✅ Exact match |
| Remediation | ✅ Successful |
| Outcome | Completed (not escalated) |

**Agent Performance**:
- ✅ **Root cause identified correctly** in single verification round
- ✅ **Remediation appropriate** (rollback to restore memory limits)
- ✅ **Hypothesis quality high** (rank 1 hypothesis was correct)
- ✅ **Verification efficient** (no wasted rounds on wrong hypotheses)
- ✅ **Execution successful** (service restored to health)

**Comparison to Human SRE**:
- **Agent**: 12 minutes (automated)
- **Human**: ~30-45 minutes (manual investigation + kubectl commands)
- **Speedup**: ~3-4x faster

**Key Success Factors**:
1. Clear evidence trail (deployment change visible in K8s history)
2. Temporal correlation (OOM events started after deploy)
3. Comparative data (healthy pod with different config)
4. Good hypothesis ranking (correct hypothesis was rank 1)

## Dashboard View

After investigation completes, view in dashboard:

```
┌─────────────────────────────────────────────────────────┐
│ Investigation: payment-service                           │
├─────────────────────────────────────────────────────────┤
│ Status: ✅ Completed                                     │
│ Duration: 12m                                           │
│ Verification Rounds: 1                                  │
│ Root Cause: Memory limits lowered (CONFIRMED)           │
│ Remediation: Rollback (APPROVED, SUCCESSFUL)            │
└─────────────────────────────────────────────────────────┘

📊 Metrics:
   Total investigations: 15
   Completion rate: 87%
   Escalation rate: 13%
   Avg verification rounds: 1.8
```

## Lessons from This Example

**What Worked Well**:
1. Strong evidence made hypothesis obvious
2. Falsification criterion was clear and testable
3. Remediation was straightforward (rollback)
4. Temporal correlation helped confirm root cause

**What Could Be Better**:
1. Could have detected the risky change before deployment (proactive)
2. Could suggest prevention measures (alerts, testing)
3. Could learn that "memory limit changes" often cause OOM incidents
4. Could include cost/benefit analysis of rollback vs memory optimization

**This Example Demonstrates**:
- ✅ Non-linear hypothesis testing (though only needed one round)
- ✅ Evidence-based diagnosis
- ✅ Human-in-the-loop safety (approval gate)
- ✅ Durable checkpointing (full transcript available)
- ✅ End-to-end automation (intake → resolution)
