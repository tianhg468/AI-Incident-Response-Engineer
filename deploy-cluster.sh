#!/bin/bash
set -e

echo "==========================================="
echo "EKS Cluster Deployment Script"
echo "==========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check prerequisites
echo "Step 1: Checking prerequisites..."
echo ""

command -v kubectl >/dev/null 2>&1 || {
    print_error "kubectl is not installed. Install from: https://kubernetes.io/docs/tasks/tools/"
    exit 1
}
print_success "kubectl is installed"

command -v eksctl >/dev/null 2>&1 || {
    print_error "eksctl is not installed. Install from: https://eksctl.io/installation/"
    exit 1
}
print_success "eksctl is installed"

command -v aws >/dev/null 2>&1 || {
    print_error "AWS CLI is not installed. Install from: https://aws.amazon.com/cli/"
    exit 1
}
print_success "AWS CLI is installed"

# Check AWS credentials
aws sts get-caller-identity >/dev/null 2>&1 || {
    print_error "AWS credentials not configured. Run: aws configure"
    exit 1
}
print_success "AWS credentials are configured"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_info "AWS Account ID: $ACCOUNT_ID"

echo ""
echo "==========================================="
echo "Step 2: Deploying EKS Cluster"
echo "==========================================="
echo ""
print_info "This will take 15-20 minutes..."
print_info "Cluster name: demo-app-cluster"
print_info "Region: us-west-1"
print_info "Node count: 3x t3.medium"
echo ""

read -p "Continue with cluster creation? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Deployment cancelled"
    exit 1
fi

# Create cluster
eksctl create cluster -f eks-cluster-config.yaml

print_success "Cluster created successfully!"

echo ""
echo "==========================================="
echo "Step 3: Verifying Cluster"
echo "==========================================="
echo ""

# Update kubeconfig
aws eks update-kubeconfig --name demo-app-cluster --region us-west-1

# Wait for nodes to be ready
print_info "Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

# Get nodes
print_success "Nodes are ready:"
kubectl get nodes

echo ""
echo "==========================================="
echo "Step 4: Deploying Application"
echo "==========================================="
echo ""

# Deploy application
print_info "Deploying demo-app..."
kubectl apply -f demo-app/k8s/deployment.yaml
kubectl apply -f demo-app/k8s/service.yaml

print_success "Kubernetes resources created"

# Wait for deployment
print_info "Waiting for pods to be ready..."
kubectl wait --for=condition=Ready pods -l app=demo-app --timeout=300s || {
    print_error "Pods failed to become ready. This is expected if the image doesn't exist yet."
    print_info "The first GitHub Actions run will build and push the image."
}

echo ""
echo "==========================================="
echo "Step 5: Deployment Summary"
echo "==========================================="
echo ""

print_success "Cluster deployment complete!"
echo ""
echo "Cluster Information:"
echo "-------------------"
kubectl cluster-info | head -n 1
echo ""

echo "Nodes:"
echo "------"
kubectl get nodes

echo ""
echo "Deployments:"
echo "-----------"
kubectl get deployments

echo ""
echo "Pods:"
echo "-----"
kubectl get pods

echo ""
echo "Services:"
echo "--------"
kubectl get svc

echo ""
echo "==========================================="
echo "Next Steps"
echo "==========================================="
echo ""
print_info "1. Add GitHub Secrets (if not done yet):"
echo "   - Go to: https://github.com/tianhg468/agentic_ai/settings/secrets/actions"
echo "   - Add AWS_ACCESS_KEY_ID"
echo "   - Add AWS_SECRET_ACCESS_KEY"
echo "   - Add AWS_REGION (value: us-west-1)"
echo ""
print_info "2. Test the deployment:"
echo "   cd demo-app"
echo "   echo '// Test change' >> src/index.js"
echo "   git add . && git commit -m 'Test deployment' && git push"
echo ""
print_info "3. Watch deployment at:"
echo "   https://github.com/tianhg468/agentic_ai/actions"
echo ""
print_info "4. To cleanup when done:"
echo "   eksctl delete cluster -f eks-cluster-config.yaml"
echo ""
print_success "Setup complete! 🎉"
