# Quick Start Guide - Deploy EKS Cluster with Existing AWS Credentials

You already have AWS admin credentials. Here's the streamlined path to get everything running.

## Step 1: Add GitHub Secrets (Do this first)

1. Go to your GitHub repository: https://github.com/tianhg468/agentic_ai
2. Navigate to: **Settings** > **Secrets and variables** > **Actions**
3. Click **"New repository secret"** and add these three secrets:

| Secret Name | Value |
|-------------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret access key |
| `AWS_REGION` | `us-west-1` |

## Step 2: Deploy the EKS Cluster

Run this command from the project root:

```bash
eksctl create cluster -f eks-cluster-config.yaml
```

**This will take 15-20 minutes.** The command will:
- Create a VPC with subnets
- Launch EKS control plane
- Create 3 t3.medium worker nodes
- Configure kubectl automatically

**Monitor progress**: You can watch the CloudFormation stacks in AWS Console.

## Step 3: Verify Cluster is Ready

After eksctl finishes, verify:

```bash
# Check nodes are ready
kubectl get nodes

# Should show 3 nodes in Ready state
# NAME                             STATUS   ROLES    AGE   VERSION
# ip-10-0-x-x.ec2.internal        Ready    <none>   2m    v1.28.x
# ip-10-0-x-x.ec2.internal        Ready    <none>   2m    v1.28.x
# ip-10-0-x-x.ec2.internal        Ready    <none>   2m    v1.28.x
```

## Step 4: Deploy the Application to EKS

Deploy the demo app and service:

```bash
# Deploy the application
kubectl apply -f demo-app/k8s/deployment.yaml
kubectl apply -f demo-app/k8s/service.yaml

# Wait for pods to be ready
kubectl get pods -w
```

Press `Ctrl+C` when you see all 3 pods in `Running` state.

## Step 5: Fix Image Reference (Important!)

The GitHub Actions workflow will push images to GHCR, but the initial deployment uses a local image. Let's update it to use a placeholder that exists:

```bash
# Update the deployment to use a working nginx image for initial test
kubectl set image deployment/demo-app demo-app=nginx:latest
```

## Step 6: Verify Everything Works

```bash
# Check deployment status
kubectl get deployment demo-app

# Check pod status
kubectl get pods

# Check service
kubectl get svc demo-app

# View logs from one pod
kubectl logs -l app=demo-app --tail=20
```

## Step 7: Test GitHub Actions Deployment

Now test the automated deployment:

1. Make a small change to trigger the workflow:
   ```bash
   # From the demo-app directory
   cd demo-app
   echo "// Test change" >> src/index.js
   cd ..
   ```

2. Commit and push to main:
   ```bash
   git add .
   git commit -m "Test: Trigger automated EKS deployment"
   git push origin main
   ```

3. **Watch the GitHub Actions workflow**:
   - Go to: https://github.com/tianhg468/agentic_ai/actions
   - Click on the running workflow
   - Watch it build the Docker image and deploy to EKS

4. **Verify the deployment updated**:
   ```bash
   # Watch the rollout
   kubectl rollout status deployment/demo-app

   # Check the new image is deployed
   kubectl get deployment demo-app -o jsonpath='{.spec.template.spec.containers[0].image}'
   ```

## Troubleshooting

### If kubectl can't connect after cluster creation:

```bash
# Manually update kubeconfig
aws eks update-kubeconfig --name demo-app-cluster --region us-west-1
```

### If pods show ImagePullBackOff:

This is expected initially since the GHCR image doesn't exist yet. The first GitHub Actions run will create it.

```bash
# Check pod events
kubectl describe pod -l app=demo-app
```

### If GitHub Actions fails with authentication error:

Double-check the GitHub secrets are set correctly:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION (must be `us-west-1`)

### To view cluster info:

```bash
# Get cluster endpoint
kubectl cluster-info

# Get current context
kubectl config current-context

# View all resources
kubectl get all
```

## What Happens Next

After the first successful GitHub Actions run:
1. Your Docker image will be in GitHub Container Registry
2. The deployment will automatically update to the new image
3. Future pushes to `main` will automatically deploy

## Cleanup (When Done Testing)

To delete everything and avoid AWS charges:

```bash
# Delete the cluster (this deletes everything)
eksctl delete cluster -f eks-cluster-config.yaml
```

Or:

```bash
eksctl delete cluster --name demo-app-cluster --region us-west-1
```

## Cost Warning

This cluster costs approximately **$174/month**:
- EKS Control Plane: $73/month
- 3x t3.medium instances: ~$95/month
- Storage & networking: ~$6/month

**Remember to delete the cluster when you're done testing!**

## Quick Command Reference

```bash
# View pods
kubectl get pods

# View deployments
kubectl get deployments

# View services
kubectl get svc

# View pod logs
kubectl logs -l app=demo-app

# Describe a resource
kubectl describe deployment demo-app

# Scale deployment
kubectl scale deployment demo-app --replicas=5

# Delete a pod (it will recreate)
kubectl delete pod <pod-name>

# Force new deployment
kubectl rollout restart deployment/demo-app
```

## Success Criteria

You'll know everything is working when:
- ✅ `kubectl get nodes` shows 3 ready nodes
- ✅ `kubectl get pods` shows 3 running demo-app pods
- ✅ GitHub Actions workflow completes successfully
- ✅ New image is deployed automatically after git push

---

**Next Step**: Start with Step 1 - Add GitHub Secrets, then run the eksctl command in Step 2.
