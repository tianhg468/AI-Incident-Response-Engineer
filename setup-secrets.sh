#!/bin/bash
set -e

echo "=========================================="
echo "Setting up Kubernetes Secrets"
echo "=========================================="
echo ""

# Check if required env vars are set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY not set!"
    echo "   Run: export ANTHROPIC_API_KEY='sk-ant-...'"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set!"
    echo "   Run: export GITHUB_TOKEN='ghp_...'"
    exit 1
fi

# Generate webhook secret if not set
if [ -z "$WEBHOOK_SECRET" ]; then
    echo "🔑 Generating webhook secret..."
    export WEBHOOK_SECRET=$(openssl rand -hex 32)
    echo "   Generated: $WEBHOOK_SECRET"
fi

echo ""
echo "Creating webhook-secrets..."
kubectl create secret generic webhook-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY" \
  --from-literal=github-token="$GITHUB_TOKEN" \
  --from-literal=webhook-secret="$WEBHOOK_SECRET"

echo "✅ webhook-secrets created"

echo ""
echo "Creating webhook-kubeconfig..."
kubectl config view --flatten --minify > /tmp/kubeconfig
kubectl create secret generic webhook-kubeconfig --from-file=config=/tmp/kubeconfig
rm /tmp/kubeconfig

echo "✅ webhook-kubeconfig created"

echo ""
echo "=========================================="
echo "Secrets Created Successfully!"
echo "=========================================="
echo ""
kubectl get secrets | grep webhook

echo ""
echo "Next step: Deploy agent-webhook"
echo "  kubectl apply -f k8s/webhook-deployment.yaml"
