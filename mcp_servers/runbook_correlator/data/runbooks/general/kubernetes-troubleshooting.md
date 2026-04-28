---
service: general
alert_types:
  - pod_issues
  - deployment_issues
  - resource_issues
severity: [high, medium, low]
tags: [kubernetes, troubleshooting, general]
title: General Kubernetes Troubleshooting
---

# General Kubernetes Troubleshooting Guide

## Quick Reference Commands

### Pod Debugging
```bash
# Get pod status
kubectl get pods -n <namespace>

# Describe pod (events, status, config)
kubectl describe pod <pod-name> -n <namespace>

# View logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous  # Previous container

# Execute commands in pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/bash

# Port forward for local testing
kubectl port-forward <pod-name> 8080:8080 -n <namespace>
```

### Deployment Debugging
```bash
# Get deployment status
kubectl get deployment <deployment-name> -n <namespace>

# Describe deployment
kubectl describe deployment <deployment-name> -n <namespace>

# View rollout status
kubectl rollout status deployment/<deployment-name> -n <namespace>

# View rollout history
kubectl rollout history deployment/<deployment-name> -n <namespace>

# Rollback deployment
kubectl rollout undo deployment/<deployment-name> -n <namespace>
```

### Resource Usage
```bash
# Node resource usage
kubectl top nodes

# Pod resource usage
kubectl top pods -n <namespace>

# Resource quotas
kubectl get resourcequota -n <namespace>
```

## Common Issues

### 1. ImagePullBackOff / ErrImagePull
**Cause:** Cannot pull container image

**Solutions:**
- Verify image name and tag
- Check image registry credentials
- Ensure image exists in registry

### 2. CrashLoopBackOff
**Cause:** Container repeatedly crashes

**Solutions:**
- Check application logs
- Verify environment variables
- Check resource limits
- Review recent code changes

### 3. Pending Pods
**Cause:** Pod cannot be scheduled

**Solutions:**
- Check node resources: `kubectl top nodes`
- Verify node selectors/affinities
- Check persistent volume claims

### 4. Service Not Accessible
**Cause:** Service endpoint not reachable

**Solutions:**
- Verify service selector matches pod labels
- Check pod readiness probes
- Verify network policies
- Test with port-forward

## Troubleshooting Workflow

1. **Identify the Problem**
   - What is failing? (Pods, Service, Deployment)
   - When did it start?
   - What changed recently?

2. **Gather Information**
   - Pod/Deployment status
   - Events and logs
   - Resource usage
   - Recent deployments

3. **Form Hypothesis**
   - Based on symptoms and recent changes
   - Check similar past incidents

4. **Test and Verify**
   - Try potential fixes
   - Monitor results
   - Rollback if needed

5. **Document and Resolve**
   - Document root cause
   - Create preventive actions
   - Update runbooks

## Best Practices

- Always check events first: `kubectl describe`
- Look at previous container logs: `--previous`
- Check recent deployments before other investigation
- Use labels consistently for easier debugging
- Set appropriate resource requests and limits
- Implement proper health checks
- Use structured logging for easier parsing
