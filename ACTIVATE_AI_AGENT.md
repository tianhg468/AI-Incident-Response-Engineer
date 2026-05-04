# Activate AI Incident Response Agent

Complete guide to activate the automated incident response system.

## Architecture Overview

```
Incident Occurs → Prometheus Detects → AlertManager → Webhook → AI Agent
                                                                     ↓
                                                              Investigates
                                                              Diagnoses
                                                              Proposes Fix
                                                              Executes (with approval)
```

## Prerequisites

Before starting, you need:

1. **Claude API Key** - Get from: https://console.anthropic.com/settings/keys
2. **GitHub Personal Access Token** - With `repo` and `write:packages` permissions
3. **Webhook Secret** - Generate a random string (e.g., `openssl rand -hex 32`)

---

## Step 1: Create Kubernetes Secrets

### 1.1 Create webhook-secrets

```bash
# Set your credentials (replace with actual values)
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export GITHUB_TOKEN="ghp_..."
export WEBHOOK_SECRET=$(openssl rand -hex 32)

# Create the secret
kubectl create secret generic webhook-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY" \
  --from-literal=github-token="$GITHUB_TOKEN" \
  --from-literal=webhook-secret="$WEBHOOK_SECRET"

# Verify
kubectl get secret webhook-secrets
```

### 1.2 Create webhook-kubeconfig

The agent needs cluster access to investigate issues.

```bash
# Get current kubeconfig
kubectl config view --flatten --minify > /tmp/kubeconfig

# Create secret
kubectl create secret generic webhook-kubeconfig \
  --from-file=config=/tmp/kubeconfig

# Clean up
rm /tmp/kubeconfig

# Verify
kubectl get secret webhook-kubeconfig
```

---

## Step 2: Build and Push Agent-Webhook Image

### 2.1 Check if Dockerfile exists

```bash
ls -la webhook/Dockerfile
# OR
ls -la Dockerfile  # If at project root
```

### 2.2 Build and push

```bash
# Login to GHCR (if not already)
echo "$GITHUB_TOKEN" | docker login ghcr.io -u tianhg468 --password-stdin

# Build the webhook image for linux/amd64 (EKS uses x86_64 nodes)
docker buildx build \
  --platform linux/amd64 \
  -t ghcr.io/tianhg468/agentic_ai/webhook:latest \
  -f webhook/Dockerfile \
  . \
  --push
```

### 2.3 Make package public (optional)

Go to: https://github.com/tianhg468/packages
- Find "webhook" package
- Make it public (like you did for demo-app)

---

## Step 3: Deploy Agent-Webhook

```bash
# Deploy the webhook
kubectl apply -f k8s/webhook-deployment.yaml

# Watch it start
kubectl get pods -l app=agent-webhook -w
```

Expected output:
```
NAME                             READY   STATUS    RESTARTS   AGE
agent-webhook-xxxxx-yyyyy        1/1     Running   0          30s
```

### Verify it's healthy:

```bash
# Check logs
kubectl logs -l app=agent-webhook --tail=50

# Test health endpoint
kubectl port-forward svc/agent-webhook 8080:8080 &
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "alert-webhook",
  "version": "1.0.0"
}
```

---

## Step 4: Deploy Prometheus Stack

### 4.1 Install Prometheus using Helm

```bash
# Add Prometheus community helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false

# Wait for pods to be ready
kubectl wait --for=condition=Ready pods --all -n monitoring --timeout=300s
```

### 4.2 Verify Prometheus is running

```bash
# Check pods
kubectl get pods -n monitoring

# Port-forward Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &

# Open http://localhost:9090
```

---

## Step 5: Configure AlertManager

### 5.1 Apply alert rules

```bash
# Apply your custom alert rules
kubectl apply -f prometheus/alert-rules.yml
```

### 5.2 Configure AlertManager to use webhook

Update AlertManager config to point to your webhook:

```bash
# Edit the AlertManager ConfigMap
kubectl -n monitoring edit configmap prometheus-kube-prometheus-alertmanager
```

Add this receiver configuration:

```yaml
receivers:
  - name: 'ai-agent-webhook'
    webhook_configs:
      - url: 'http://agent-webhook.default.svc.cluster.local:8080/alerts'
        send_resolved: true
        http_config:
          bearer_token: 'YOUR_WEBHOOK_SECRET'  # Use the secret you generated

route:
  group_by: ['alertname', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'ai-agent-webhook'
```

Save and exit. AlertManager will reload automatically.

### 5.3 Verify AlertManager config

```bash
# Port-forward AlertManager UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093 &

# Open http://localhost:9093
```

---

## Step 6: Test the Incident Response Flow

### Test 1: Trigger OOM Alert

Create a pod that will run out of memory:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: memory-hog
  labels:
    app: test-incident
spec:
  containers:
  - name: memory-hog
    image: polinux/stress
    resources:
      limits:
        memory: "128Mi"
      requests:
        memory: "64Mi"
    command: ["stress"]
    args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
EOF
```

Watch for:
1. Pod gets OOMKilled
2. Prometheus detects it (check Prometheus alerts)
3. AlertManager sends to webhook
4. Agent investigates

### Test 2: Check Agent Logs

```bash
# Watch agent-webhook logs in real-time
kubectl logs -f -l app=agent-webhook

# You should see:
# - Alert received from Prometheus
# - Agent starting investigation
# - Gathering evidence
# - Generating hypotheses
# - Proposing remediation
```

### Test 3: Check Investigation in Dashboard

```bash
# Run the dashboard locally
streamlit run dashboard/app.py

# Or access the GitOps monitor
python dashboard/gitops_monitor.py
```

Open http://localhost:8501 to see:
- Active investigations
- Diagnosis results
- Remediation proposals

---

## Step 7: Monitor the System

### View all components:

```bash
# Agent webhook
kubectl get pods -l app=agent-webhook
kubectl logs -f -l app=agent-webhook

# Demo app
kubectl get pods -l app=demo-app

# Prometheus/AlertManager
kubectl get pods -n monitoring

# Check all alerts
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &
# Visit: http://localhost:9090/alerts
```

---

## Troubleshooting

### Agent webhook not starting

```bash
# Check pod status
kubectl describe pod -l app=agent-webhook

# Common issues:
# 1. Missing secrets
kubectl get secrets | grep webhook

# 2. Image not found
# Make sure you built and pushed the webhook image

# 3. Resource limits
# The webhook needs 512Mi-1Gi memory
kubectl top nodes
```

### Alerts not triggering

```bash
# Check if Prometheus is scraping metrics
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &
# Visit: http://localhost:9090/targets

# Check alert rules loaded
# Visit: http://localhost:9090/rules

# Check if AlertManager received alerts
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093 &
# Visit: http://localhost:9093/#/alerts
```

### Agent not receiving alerts

```bash
# Test webhook directly
kubectl port-forward svc/agent-webhook 8080:8080 &

curl -X POST http://localhost:8080/alerts \
  -H "Authorization: Bearer YOUR_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "test",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical",
        "service": "test-service"
      },
      "annotations": {
        "summary": "Test alert",
        "description": "Testing webhook"
      }
    }]
  }'

# Check agent logs
kubectl logs -f -l app=agent-webhook
```

---

## Cost Considerations

Running the full stack will increase costs:

**Prometheus Stack:**
- ~0.5-1 vCPU
- ~1-2Gi memory
- **Additional cost: ~$0.03-0.05/hour**

**Agent Webhook:**
- ~0.25 vCPU
- ~512Mi-1Gi memory
- **Additional cost: ~$0.02-0.03/hour**

**Claude API:**
- ~$0.50-2.00 per investigation (depends on complexity)
- Charged per use, not continuous

**Total additional cost: ~$0.05-0.08/hour or ~$1.20-1.92/day**

Plus API costs when incidents occur.

---

## Next Steps

After activation:

1. **Create more alert rules** - Add custom alerts for your services
2. **Tune agent behavior** - Adjust investigation prompts in `agent/prompts/`
3. **Set up approval workflows** - Configure auto-approval thresholds
4. **Integrate with Slack** - Get notifications when incidents occur
5. **Create runbooks** - Link alerts to runbooks for common issues

---

## Quick Reference

**Check everything is running:**
```bash
kubectl get pods -A | grep -E "demo-app|agent-webhook|prometheus|alertmanager"
```

**View agent investigations:**
```bash
streamlit run dashboard/app.py
```

**Manually trigger investigation:**
```bash
python -m agent.graph
```

**Clean up test pods:**
```bash
kubectl delete pod memory-hog
```

---

You're ready to go! 🚀

Start with Step 1 to create the secrets, then work through each step in order.
