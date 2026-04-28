---
service: payment-service
alert_types:
  - pod_crash_loop
  - crash_loop_backoff
  - oom_killed
severity: [high, critical]
tags: [kubernetes, memory, crashes]
title: Payment Service Pod Crash Loop
---

# Payment Service Pod Crash Loop Runbook

## Overview
This runbook covers pod crash loops in the payment service, including OOM kills, application crashes, and configuration issues.

## Common Causes

### 1. Out of Memory (OOM) Kills
**Symptoms:**
- Exit code 137 in pod status
- "OOMKilled" in pod events
- Memory usage near or at limit before crash

**Investigation:**
```bash
# Check pod events
kubectl describe pod <pod-name> -n default

# Check memory limits
kubectl get pod <pod-name> -n default -o jsonpath='{.spec.containers[*].resources.limits.memory}'

# View recent logs
kubectl logs <pod-name> -n default --tail=100
```

**Resolution:**
- **If recent deploy changed memory limits**: Rollback to previous deployment
- **If gradual memory increase**: Increase memory limits in deployment
- **If memory leak**: Investigate application code, enable heap dumps

### 2. Application Startup Failures
**Symptoms:**
- Rapid restarts (multiple per minute)
- Application errors in logs
- Missing environment variables or secrets

**Investigation:**
```bash
# Check container logs
kubectl logs <pod-name> -n default --previous

# Check environment variables
kubectl exec <pod-name> -n default -- env

# Check secrets/config maps
kubectl get configmap,secret -n default
```

**Resolution:**
- Verify all required environment variables are set
- Check database connectivity
- Validate configuration files

### 3. Health Check Failures
**Symptoms:**
- Pods marked as unhealthy
- Readiness/liveness probe failures

**Investigation:**
```bash
# Check probe configuration
kubectl get pod <pod-name> -n default -o jsonpath='{.spec.containers[*].livenessProbe}'

# Test health endpoint
kubectl exec <pod-name> -n default -- curl localhost:8080/health
```

## Standard Response Procedure

1. **Immediate Triage** (< 5 min)
   - Check pod events: `kubectl describe pod`
   - Review recent deployments
   - Check resource usage (CPU, memory)

2. **Identify Root Cause** (5-15 min)
   - Analyze logs for errors
   - Compare with previous working version
   - Check for recent config changes

3. **Remediation**
   - **If recent deploy**: Rollback
   - **If resource constraints**: Scale up resources
   - **If configuration**: Fix config and redeploy
   - **If external dependency**: Check upstream services

4. **Verification**
   - Confirm pods are running and healthy
   - Check metrics for normal operation
   - Monitor for 15 minutes

## Rollback Procedure

```bash
# View deployment history
kubectl rollout history deployment/payment-service -n default

# Rollback to previous version
kubectl rollout undo deployment/payment-service -n default

# Rollback to specific revision
kubectl rollout undo deployment/payment-service -n default --to-revision=<N>

# Watch rollback progress
kubectl rollout status deployment/payment-service -n default
```

## Escalation

Escalate to on-call engineer if:
- Issue persists after rollback
- Root cause is unclear after 15 minutes
- Multiple services affected
- Payment processing is blocked

## Post-Incident

- Document root cause
- Create action items to prevent recurrence
- Update this runbook if needed
- Schedule post-mortem if severity is critical
