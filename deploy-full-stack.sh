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

if kubectl get secret webhook-kubeconfig &>/dev/null; then
    print_warning "webhook-kubeconfig already exists"
else
    print_info "Creating webhook-kubeconfig..."
    kubectl config view --flatten --minify > /tmp/kubeconfig
    kubectl create secret generic webhook-kubeconfig --from-file=config=/tmp/kubeconfig
    rm /tmp/kubeconfig
    print_success "webhook-kubeconfig created"
fi

echo ""
echo "==========================================="
echo "Step 3: Deploying Demo App"
echo "==========================================="
echo ""

print_info "Deploying demo-app..."
kubectl apply -f demo-app/k8s/deployment.yaml
kubectl apply -f demo-app/k8s/service.yaml
print_success "Demo app deployed"

echo ""
echo "==========================================="
echo "Step 4: Deploying AI Agent Webhook"
echo "==========================================="
echo ""

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
echo "Step 5: Installing Prometheus Stack"
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
    print_info "Applying custom alert rules..."
    kubectl apply -f prometheus/alert-rules.yml
    print_success "Alert rules applied"
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
echo "Step 6: Starting GitOps Monitor Dashboard"
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
