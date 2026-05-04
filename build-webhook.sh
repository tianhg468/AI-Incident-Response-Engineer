#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

echo "==========================================="
echo "Build Webhook Image for EKS"
echo "==========================================="
echo ""

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    print_error "GITHUB_TOKEN not set!"
    echo ""
    echo "Set it first:"
    echo "  export GITHUB_TOKEN='ghp_...'"
    echo ""
    echo "Or load from .env:"
    echo "  export GITHUB_TOKEN=\$(grep GITHUB_TOKEN .env | cut -d '=' -f2)"
    exit 1
fi

print_success "GITHUB_TOKEN is set"

# Login to GHCR
print_info "Logging in to GitHub Container Registry..."
echo "$GITHUB_TOKEN" | docker login ghcr.io -u tianhg468 --password-stdin

print_success "Logged in to GHCR"

echo ""
print_info "Building webhook image for linux/amd64..."
print_info "This may take 5-10 minutes (first time) or 1-2 minutes (with cache)"
echo ""

# Build and push for linux/amd64 (EKS nodes are x86_64)
docker buildx build \
  --platform linux/amd64 \
  -t ghcr.io/tianhg468/agentic_ai/webhook:latest \
  -f webhook/Dockerfile \
  . \
  --push

echo ""
print_success "Webhook image built and pushed successfully!"
echo ""
print_info "Image: ghcr.io/tianhg468/agentic_ai/webhook:latest"
print_info "Platform: linux/amd64 (compatible with EKS t3.small nodes)"
echo ""
print_info "Next step: Deploy the webhook"
echo "  kubectl apply -f k8s/webhook-deployment.yaml"
