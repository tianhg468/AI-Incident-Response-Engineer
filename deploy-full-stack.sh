#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

echo "==========================================="
echo "Full Stack AI Incident Response Deployment"
echo "==========================================="
echo ""

print_warning "PREREQUISITE: Webhook image must be built first!"
print_info "Run: ./build-webhook.sh (one-time, or when webhook code changes)"
echo ""
read -p "Have you built the webhook image? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Please build the webhook image first:"
    print_info "  ./build-webhook.sh"
    exit 0
fi
echo ""

# Check if cluster exists
CLUSTER_EXISTS=$(aws eks describe-cluster --name demo-app-cluster --region us-west-1 2>/dev/null || echo "not-found")

if [[ $CLUSTER_EXISTS != "not-found" ]]; then
    print_warning "Cluster already exists!"
    echo ""
    echo "What would you like to do?"
    echo "1) Use existing cluster (skip cluster creation)"
    echo "2) Delete and recreate cluster"
    echo "3) Exit"
    echo ""
    read -p "Choose option (1, 2, or 3): " choice

    case $choice in
        1)
            print_info "Using existing cluster..."
            ;;
        2)
            print_info "Deleting existing cluster..."
            eksctl delete cluster -f eks-cluster-config.yaml
            print_success "Cluster deleted"
            CLUSTER_EXISTS="not-found"
            ;;
        3)
            exit 0
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac
fi

# Deploy cluster if needed
if [[ $CLUSTER_EXISTS == "not-found" ]]; then
    print_info "Deploying EKS cluster..."
    print_warning "This will take 15-20 minutes"
    echo ""

    eksctl create cluster -f eks-cluster-config.yaml

    # Update kubeconfig
    aws eks update-kubeconfig --name demo-app-cluster --region us-west-1

    print_success "Cluster deployed!"

    # Start timer
    START_TIME=$(date +%s)
    echo $START_TIME > .cluster-start-time
fi

echo ""
echo "==========================================="
echo "Step 1: Checking Prerequisites"
echo "==========================================="
echo ""

# Check required env vars
if [ -z "$ANTHROPIC_API_KEY" ]; then
    print_error "ANTHROPIC_API_KEY not set!"
    echo ""
    echo "Please set it first:"
    echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
    echo "Or add to ~/.zshrc:"
    echo "  echo 'export ANTHROPIC_API_KEY=\"sk-ant-...\"' >> ~/.zshrc"
    exit 1
fi
print_success "ANTHROPIC_API_KEY is set"

if [ -z "$GITHUB_TOKEN" ]; then
    print_error "GITHUB_TOKEN not set!"
    echo ""
    echo "Please set it first:"
    echo "  export GITHUB_TOKEN='ghp_...'"
    exit 1
fi
print_success "GITHUB_TOKEN is set"

# Check if flux is installed
if ! command -v flux &> /dev/null; then
    print_warning "Flux CLI not found!"
    echo ""
    echo "Installing Flux CLI..."

    # Detect OS
    OS="$(uname -s)"
    case "${OS}" in
        Darwin*)
            if command -v brew &> /dev/null; then
                brew install fluxcd/tap/flux
            else
                print_error "Homebrew not found. Please install Flux manually:"
                echo "  https://fluxcd.io/flux/installation/"
                exit 1
            fi
            ;;
        Linux*)
            curl -s https://fluxcd.io/install.sh | sudo bash
            ;;
        *)
            print_error "Unsupported OS: ${OS}"
            echo "Please install Flux manually: https://fluxcd.io/flux/installation/"
            exit 1
            ;;
    esac

    print_success "Flux CLI installed"
else
    print_success "Flux CLI is installed"
fi

# Generate webhook secret if not set
if [ -z "$WEBHOOK_SECRET" ]; then
    export WEBHOOK_SECRET=$(openssl rand -hex 32)
    print_info "Generated webhook secret: $WEBHOOK_SECRET"
else
    print_success "WEBHOOK_SECRET is set"
fi

echo ""
echo "==========================================="
echo "Step 2: Creating Kubernetes Secrets"
echo "==========================================="
echo ""

# Check if secrets already exist
if kubectl get secret webhook-secrets &>/dev/null; then
    print_warning "webhook-secrets already exists"
    read -p "Recreate it? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete secret webhook-secrets
        print_info "Deleted old secret"
    fi
fi

if ! kubectl get secret webhook-secrets &>/dev/null; then
    print_info "Creating webhook-secrets..."
    kubectl create secret generic webhook-secrets \
      --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY" \
      --from-literal=github-token="$GITHUB_TOKEN" \
      --from-literal=webhook-secret="$WEBHOOK_SECRET"
    print_success "webhook-secrets created"
fi

# webhook-kubeconfig no longer needed - using in-cluster authentication via ServiceAccount

echo ""
echo "==========================================="
echo "Step 3: Deploying Demo App (via Flux CD)"
echo "==========================================="
echo ""

print_info "Demo app will be deployed automatically by Flux CD"
print_info "Flux will sync from: github.com/tianhg468/ai-incident-response-demo"
print_info "This happens after Flux installation in Step 5"
print_success "Skipping direct deployment (Flux will handle it)"

echo ""
echo "==========================================="
echo "Step 4: Deploying AI Agent Webhook"
echo "==========================================="
echo ""

print_info "Creating webhook RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)..."
kubectl apply -f k8s/webhook-rbac.yaml
print_success "Webhook RBAC created"

print_info "Deploying agent-webhook..."
kubectl apply -f k8s/webhook-deployment.yaml
print_success "Agent webhook deployed"

echo ""
print_info "Waiting for webhook pod to be ready..."
kubectl wait --for=condition=Ready pods -l app=agent-webhook --timeout=300s || {
    print_error "Webhook pod failed to start"
    echo ""
    echo "Check logs with:"
    echo "  kubectl logs -l app=agent-webhook"
    echo "  kubectl describe pod -l app=agent-webhook"
    exit 1
}
print_success "Agent webhook is ready!"

echo ""
echo "==========================================="
echo "Step 5: Installing Flux CD (GitOps)"
echo "==========================================="
echo ""

# Check if Flux is already installed in the cluster
if kubectl get namespace flux-system &>/dev/null; then
    print_warning "Flux CD already installed"
    echo ""
    read -p "Reinstall Flux CD? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        flux uninstall --silent
        print_info "Flux uninstalled"
    else
        print_info "Skipping Flux installation"
        SKIP_FLUX=true
    fi
fi

if [ "$SKIP_FLUX" != "true" ]; then
    print_info "Bootstrapping Flux CD to sync from GitHub repository..."
    print_warning "This will create a 'flux-system' directory in your repo with Flux manifests"
    echo ""

    # Set GitHub org and repo
    GITHUB_ORG="${GITHUB_ORG:-tianhg468}"
    GITHUB_REPO="${GITHUB_REPO:-agentic_ai}"
    GITHUB_BRANCH="${GITHUB_BRANCH:-main}"

    # Bootstrap Flux
    export GITHUB_TOKEN
    flux bootstrap github \
      --owner="$GITHUB_ORG" \
      --repository="$GITHUB_REPO" \
      --branch="$GITHUB_BRANCH" \
      --path=./k8s \
      --personal \
      --read-write-key

    print_success "Flux CD installed and bootstrapped!"
    echo ""
    print_info "Flux will now automatically sync changes from:"
    echo "  Repository: $GITHUB_ORG/$GITHUB_REPO"
    echo "  Branch: $GITHUB_BRANCH"
    echo "  Path: ./k8s"
    echo ""
    print_info "Flux is also configured to sync demo-app from:"
    echo "  Repository: tianhg468/ai-incident-response-demo"
    echo "  Branch: main"
    echo "  Path: ./k8s"
    echo ""
    print_info "Any changes pushed to Git will be automatically deployed to the cluster!"
    echo ""
    print_warning "Note: Demo app deployment may take 1-2 minutes as Flux syncs the repository"
fi

echo ""
echo "==========================================="
echo "Step 6: Installing Prometheus Stack"
echo "==========================================="
echo ""

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    print_error "Helm is not installed!"
    echo ""
    echo "Install it with:"
    echo "  macOS: brew install helm"
    echo "  Linux: https://helm.sh/docs/intro/install/"
    echo ""
    read -p "Skip Prometheus installation? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    SKIP_PROMETHEUS=true
fi

if [ "$SKIP_PROMETHEUS" != "true" ]; then
    # Check if already installed
    if helm list -n monitoring | grep -q prometheus; then
        print_warning "Prometheus already installed"
    else
        print_info "Adding Prometheus helm repo..."
        helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
        helm repo update

        print_info "Installing Prometheus stack (this may take 5 minutes)..."
        helm install prometheus prometheus-community/kube-prometheus-stack \
          --namespace monitoring \
          --create-namespace \
          --wait

        print_success "Prometheus stack installed!"
    fi

    echo ""
    print_info "Applying custom alert rules (PrometheusRule)..."
    kubectl apply -f prometheus/prometheus-rule.yml
    print_success "Alert rules applied"

    echo ""
    print_info "Configuring AlertManager to send alerts to webhook..."

    # Update AlertManager config to route to webhook
    kubectl get secret -n monitoring alertmanager-prometheus-kube-prometheus-alertmanager -o json | \
      jq '.data["alertmanager.yaml"]' -r | base64 -d > /tmp/alertmanager.yaml

    # Check if webhook route already exists
    if grep -q "ai-agent-webhook" /tmp/alertmanager.yaml; then
        print_warning "AlertManager already configured for webhook"
    else
        # Add webhook receiver and route
        cat > /tmp/alertmanager.yaml << EOF
global:
  resolve_timeout: 5m
receivers:
- name: "null"
- name: "ai-agent-webhook"
  webhook_configs:
  - url: 'http://agent-webhook.default.svc.cluster.local:8080/alerts'
    send_resolved: true
    http_config:
      bearer_token: '$WEBHOOK_SECRET'
route:
  group_by:
  - namespace
  - alertname
  group_interval: 10s
  group_wait: 10s
  receiver: "ai-agent-webhook"
  repeat_interval: 1h
EOF

        kubectl create secret generic alertmanager-prometheus-kube-prometheus-alertmanager \
          --from-file=alertmanager.yaml=/tmp/alertmanager.yaml \
          -n monitoring \
          --dry-run=client -o yaml | kubectl apply -f -

        # Restart AlertManager to pick up new config
        kubectl delete pod -n monitoring -l app.kubernetes.io/name=alertmanager

        print_success "AlertManager configured"
    fi

    rm /tmp/alertmanager.yaml
fi

echo ""
echo "==========================================="
echo "Deployment Complete! 🎉"
echo "==========================================="
echo ""

print_success "All components deployed successfully!"

echo ""
echo "📊 Component Status:"
echo "-------------------"
kubectl get pods -A | grep -E "demo-app|agent-webhook|prometheus|alertmanager" || echo "Checking pods..."

echo ""
echo "🔗 Access Points:"
echo "----------------"
echo "Demo App:"
echo "  kubectl port-forward svc/demo-app 8080:80"
echo "  Then: http://localhost:8080"
echo ""
echo "Agent Webhook:"
echo "  kubectl port-forward svc/agent-webhook 8080:8080"
echo "  Then: http://localhost:8080/health"
echo ""

if [ "$SKIP_PROMETHEUS" != "true" ]; then
    echo "Prometheus:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
    echo "  Then: http://localhost:9090"
    echo ""
    echo "AlertManager:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093"
    echo "  Then: http://localhost:9093"
    echo ""
fi

echo ""
echo "==========================================="
echo "Step 7: Starting GitOps Monitor Dashboard"
echo "==========================================="
echo ""

read -p "Start GitOps Monitor dashboard now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Starting GitOps Monitor on http://localhost:5000"
    echo ""
    print_success "Dashboard shows:"
    echo "  ✓ Demo-app pod status (live)"
    echo "  ✓ GitHub Actions workflow runs"
    echo "  ✓ Prometheus alerts"
    echo "  ✓ Cluster health"
    echo ""
    print_warning "Press Ctrl+C to stop the dashboard"
    echo ""

    # Set repo info
    export GITHUB_ORG="${GITHUB_ORG:-tianhg468}"
    export GITHUB_REPO="${GITHUB_REPO:-agentic_ai}"

    python dashboard/gitops_monitor.py
else
    echo ""
    print_info "To start dashboards later, run:"
    echo "  GitOps Monitor:  python dashboard/gitops_monitor.py"
    echo "  AI Dashboard:    streamlit run dashboard/app.py"
fi

echo ""
echo "📝 Quick Commands:"
echo "-----------------"
echo "View all pods:        kubectl get pods -A"
echo "View agent logs:      kubectl logs -f -l app=agent-webhook"
echo "View demo-app logs:   kubectl logs -f -l app=demo-app"
echo "Flux status:          flux get all"
echo "Force Flux sync:      flux reconcile kustomization flux-system --with-source"
echo "GitOps Monitor:       python dashboard/gitops_monitor.py"
echo "AI Dashboard:         streamlit run dashboard/app.py"
echo "Delete cluster:       ./test-and-cleanup.sh (option 2)"

echo ""
print_warning "💰 Cost: ~$0.17/hour + Prometheus (~$0.05/hour) = ~$0.22/hour"
print_warning "Remember to delete the cluster when done!"

echo ""
print_info "Session started at: $(date)"

if [ -f .cluster-start-time ]; then
    START_TIME=$(cat .cluster-start-time)
    echo $START_TIME > .cluster-start-time
    print_info "Cluster start time saved for cost tracking"
fi

echo ""
print_success "🚀 Your AI Incident Response system is live!"
