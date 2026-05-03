# GitOps Production Setup

This guide walks you through setting up the **full production GitOps workflow** where the AI agent creates GitHub PRs for human review instead of executing changes directly.

## Architecture Overview

```
Developer Push → GitHub Actions → K8s Deploy → Incident → Prometheus Alert
                                                              ↓
                                                      Alert Webhook Server
                                                              ↓
                                                         AI Agent
                                                              ↓
                                                      GitHub PR Created
                                                              ↓
                                                  Human Reviews PR in GitHub
                                                              ↓
                                                      PR Merged → Auto-Deploy
```

## Prerequisites

- GitHub repository
- Kubernetes cluster (minikube or production)
- Prometheus + AlertManager installed
- Slack workspace (optional, for notifications)

---

## Part 1: GitHub Setup

### 1.1 Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (full repository access)
   - `workflow` (update GitHub Actions workflows)
4. Copy the token and add to `.env`:

```bash
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your-github-username
GITHUB_REPO=agentic_ai
```

### 1.2 Configure Branch Protection

1. Go to your repo → Settings → Branches
2. Add rule for `main` branch:
   - ✅ Require a pull request before merging
   - ✅ Require approvals (1)
   - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging

This ensures all changes go through PR review!

### 1.3 Add Kubernetes Config Secret

For GitHub Actions to deploy to your cluster:

```bash
# Encode your kubeconfig
cat ~/.kube/config | base64 > kubeconfig.b64

# Add as repository secret:
# Go to repo → Settings → Secrets and variables → Actions
# Create new secret: KUBECONFIG
# Paste the base64 content
```

### 1.4 Enable GitHub Container Registry

The GitHub Actions workflow will push Docker images to `ghcr.io`:

```bash
# Login to GitHub Container Registry locally
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Make the package public (optional)
# Go to https://github.com/YOUR_USERNAME?tab=packages
# Find your package → Package settings → Change visibility
```

---

## Part 2: Prometheus Setup

### 2.1 Install Prometheus (if not already installed)

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus + AlertManager
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

### 2.2 Apply Alert Rules

```bash
kubectl apply -f prometheus/alert-rules.yml
```

### 2.3 Configure AlertManager

```bash
# Update AlertManager config to send webhooks to our agent
kubectl create secret generic alertmanager-config \
  --from-file=alertmanager.yml=prometheus/alertmanager-config.yml \
  -n monitoring \
  --dry-run=client -o yaml | kubectl apply -f -

# Reload AlertManager
kubectl rollout restart statefulset/alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring
```

---

## Part 3: Agent Webhook Server

### 3.1 Set Execution Mode to GitOps

Update `.env`:

```bash
# Execution mode: "gitops" creates PRs, "direct" executes kubectl
EXECUTION_MODE=gitops
```

### 3.2 Start Alert Webhook Server

This receives alerts from Prometheus and triggers the agent:

```bash
# Terminal 1: Alert webhook server
python webhook/alert_webhook.py
```

Should see:
```
🚀 Starting alert webhook server...
   Host: 0.0.0.0
   Port: 8080
Waiting for alerts...
```

### 3.3 Expose Webhook (Production)

For production, expose the webhook server:

**Option A: Using ngrok (dev/testing)**
```bash
ngrok http 8080
```

**Option B: Using Kubernetes Service (production)**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: agent-webhook
spec:
  selector:
    app: agent-webhook
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
```

### 3.4 Configure AlertManager Webhook URL

Update `prometheus/alertmanager-config.yml` with your webhook URL:

```yaml
receivers:
  - name: 'ai-agent-webhook'
    webhook_configs:
      - url: 'http://agent-webhook:8080/alerts'  # If running in K8s
        # OR
        # - url: 'https://your-ngrok-url.ngrok.io/alerts'  # If using ngrok
```

---

## Part 4: Slack Webhook Server (Optional)

If you still want Slack notifications (recommended for awareness):

```bash
# Terminal 2: Slack webhook server (for button interactions)
python webhook/slack_webhook.py

# Terminal 3: ngrok for Slack
ngrok http 3001
```

Configure Slack app Request URL: `https://your-ngrok-url/slack/interactions`

---

## Part 5: Test the Full Flow

### 5.1 Trigger an Incident

**Option 1: Edit deployment.yaml and push to GitHub**

```bash
# Edit demo-app/k8s/deployment.yaml
# Change memory limit from 256Mi to 64Mi

git add demo-app/k8s/deployment.yaml
git commit -m "Lower memory limit to trigger OOM"
git push origin main
```

GitHub Actions will auto-deploy → Pods will OOMKill → Prometheus fires alert

**Option 2: Use trigger script (for testing)**

```bash
cd demo-app/incidents
./trigger-oom.sh
```

Then manually fire a test alert to the webhook:

```bash
curl -X POST http://localhost:8080/alerts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_webhook_secret" \
  -d '{
    "receiver": "ai-agent-webhook",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "PodOOMKilled",
        "alert_type": "oomkilled",
        "severity": "critical",
        "service": "demo-app"
      },
      "annotations": {
        "summary": "Pod demo-app-xxx was OOMKilled",
        "description": "Container demo-app exceeded memory limit"
      }
    }]
  }'
```

### 5.2 Watch the Agent Work

You'll see in the alert webhook terminal:

```
🚨 Received alert from Prometheus:
   Alerts: 1

📋 Alert Details:
   Name: PodOOMKilled
   Type: oomkilled
   Severity: critical
   Service: demo-app

🤖 Triggering AI agent for demo-app...
   ✓ Agent started (PID: 12345)
```

### 5.3 Review the PR

The agent will:
1. Gather evidence
2. Generate hypotheses
3. Confirm root cause
4. **Create a GitHub PR** with the fix

Check your GitHub repo → Pull Requests → You'll see:

```
🤖 [AI Agent] Rollback demo-app to fix OOM incidents
```

### 5.4 Review and Approve

1. Click on the PR
2. Go to "Files changed" tab
3. See the diff:
   ```diff
   - memory: "64Mi"
   + memory: "256Mi"
   ```
4. Review the AI's analysis in the PR description
5. Click "Approve" and "Merge pull request"

### 5.5 Auto-Deployment

GitHub Actions will:
1. Detect the merge to `main`
2. Build new Docker image
3. Deploy to Kubernetes
4. Pods will restart with correct memory limits
5. Incident resolved!

---

## Part 6: Monitoring and Observability

### 6.1 Check Agent Logs

```bash
# Agent execution logs
tail -f data/agent.log

# Webhook server logs
tail -f data/webhook.log
```

### 6.2 View Slack Notifications

In #incidents channel, you'll see:
- 🚨 Initial alert from Prometheus
- 🤖 "AI Agent created PR"
- ✅ "PR merged, deployment in progress"
- 📊 Post-mortem when resolved

### 6.3 Check Prometheus Alerts

```bash
# Forward Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Open http://localhost:9090/alerts
```

---

## Comparison: GitOps vs Direct Execution

| Aspect | GitOps (PR-based) | Direct (kubectl) |
|--------|-------------------|------------------|
| **Approval** | GitHub PR review | Slack button |
| **Audit Trail** | Full Git history | Checkpoints only |
| **Visibility** | See exact diff | Just command |
| **Rollback** | Git revert | Manual kubectl |
| **Team Workflow** | Fits existing process | Separate workflow |
| **Safety** | Branch protection | Approval handler |
| **Best For** | Production | Development/Demo |

---

## Troubleshooting

### PR Creation Fails

**Error:** `fatal: could not create work tree dir`

**Fix:** Make sure the agent has write access to the repo:
```bash
cd /path/to/agentic_ai
git config --global user.email "ai-agent@example.com"
git config --global user.name "AI Agent"
```

### Alert Webhook Not Receiving Alerts

**Fix:** Check AlertManager config:
```bash
kubectl logs -n monitoring alertmanager-prometheus-kube-prometheus-alertmanager-0

# Should see webhook delivery attempts
```

### GitHub Actions Deploy Fails

**Fix:** Check KUBECONFIG secret:
```bash
# Verify secret exists
kubectl get secret kubeconfig -n default

# Check GitHub Actions logs in repo → Actions tab
```

---

## Next Steps

1. **Add More Alert Types**
   - Edit `prometheus/alert-rules.yml`
   - Add CrashLoopBackOff, high latency, etc.

2. **Customize PR Templates**
   - Edit `.github/pull_request_template.md`
   - Add required sections for AI PRs

3. **Add Required Reviewers**
   - Settings → Branches → Branch protection
   - Add specific teams/users as required reviewers

4. **Enable Auto-Merge**
   - For low-risk changes
   - Settings → General → Allow auto-merge

5. **Add PR Size Limits**
   - Prevent AI from making massive changes
   - Add GitHub Actions check for diff size

---

## Production Checklist

- [ ] Branch protection enabled on `main`
- [ ] Required PR approvals configured
- [ ] GitHub token has correct permissions
- [ ] Prometheus alerts firing correctly
- [ ] Alert webhook accessible from AlertManager
- [ ] GitHub Actions can deploy to cluster
- [ ] Slack notifications working
- [ ] Post-mortem reports generated
- [ ] Agent creates PRs successfully
- [ ] PRs have clear, actionable descriptions
- [ ] Full incident timeline tracked in Git

🎉 **You're running a production-grade GitOps incident response system!**
