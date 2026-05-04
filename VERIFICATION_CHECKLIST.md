# EKS Deployment Verification Checklist

Use this checklist to verify that everything is working correctly.

## ☐ Prerequisites (Before Deployment)

- [ ] AWS CLI installed: `aws --version`
- [ ] kubectl installed: `kubectl version --client`
- [ ] eksctl installed: `eksctl version`
- [ ] AWS credentials configured: `aws sts get-caller-identity`
- [ ] Git repository access: Can push to `tianhg468/agentic_ai`

## ☐ GitHub Configuration

- [ ] GitHub Secret `AWS_ACCESS_KEY_ID` is set
- [ ] GitHub Secret `AWS_SECRET_ACCESS_KEY` is set
- [ ] GitHub Secret `AWS_REGION` is set to `us-west-1`

**Verify at**: https://github.com/tianhg468/agentic_ai/settings/secrets/actions

## ☐ EKS Cluster Deployment

Run: `./deploy-cluster.sh` or `eksctl create cluster -f eks-cluster-config.yaml`

- [ ] Command completed without errors
- [ ] CloudFormation stacks created in AWS Console
- [ ] Cluster appears in EKS Console

**Verify**:
```bash
eksctl get cluster --name demo-app-cluster --region us-west-1
```

Expected output:
```
NAME              REGION    EKSCTL CREATED
demo-app-cluster  us-west-1 True
```

## ☐ Kubernetes Cluster Access

**Verify kubectl is configured**:
```bash
kubectl config current-context
```

Expected: `<your-user>@demo-app-cluster.us-west-1.eksctl.io`

**Verify cluster info**:
```bash
kubectl cluster-info
```

Expected: Should show Kubernetes control plane URL

## ☐ Node Status

**Check nodes are ready**:
```bash
kubectl get nodes
```

**Expected**: 3 nodes with STATUS = Ready

Example:
```
NAME                             STATUS   ROLES    AGE   VERSION
ip-10-0-1-123.ec2.internal      Ready    <none>   5m    v1.28.x
ip-10-0-2-123.ec2.internal      Ready    <none>   5m    v1.28.x
ip-10-0-3-123.ec2.internal      Ready    <none>   5m    v1.28.x
```

- [ ] All 3 nodes show STATUS = Ready
- [ ] Node versions match (v1.28.x)

## ☐ Application Deployment

**Check deployment**:
```bash
kubectl get deployment demo-app
```

Expected:
```
NAME       READY   UP-TO-DATE   AVAILABLE   AGE
demo-app   3/3     3            3           2m
```

- [ ] READY shows 3/3
- [ ] AVAILABLE = 3

**Check pods**:
```bash
kubectl get pods -l app=demo-app
```

Expected: 3 pods with STATUS = Running

- [ ] All 3 pods show STATUS = Running
- [ ] READY column shows 1/1 for all pods

**If pods are not running**, check events:
```bash
kubectl describe pod -l app=demo-app
```

## ☐ Service Deployment

**Check service**:
```bash
kubectl get svc demo-app
```

Expected:
```
NAME       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
demo-app   ClusterIP   10.100.x.x      <none>        3000/TCP   2m
```

- [ ] Service exists
- [ ] TYPE = ClusterIP
- [ ] PORT = 3000/TCP

## ☐ Application Health

**Check pod logs**:
```bash
kubectl logs -l app=demo-app --tail=20
```

- [ ] Logs show application is running
- [ ] No critical errors in logs

**Port forward to test locally** (optional):
```bash
kubectl port-forward svc/demo-app 8080:3000
```

Then visit: http://localhost:8080

- [ ] Application responds
- [ ] Health endpoint works: http://localhost:8080/health

## ☐ GitHub Actions Integration

**Make a test commit**:
```bash
cd demo-app
echo "// Test $(date)" >> src/index.js
git add .
git commit -m "Test: Automated deployment"
git push origin main
```

**Monitor workflow**:
- [ ] Go to: https://github.com/tianhg468/agentic_ai/actions
- [ ] Workflow "Deploy to Kubernetes" is triggered
- [ ] "Build and push Docker image" step succeeds
- [ ] "Configure AWS credentials" step succeeds
- [ ] "Configure kubectl for EKS" step succeeds
- [ ] "Deploy to Kubernetes" step succeeds
- [ ] Workflow completes with green checkmark

**Verify deployment updated**:
```bash
kubectl rollout status deployment/demo-app
```

Expected: `deployment "demo-app" successfully rolled out`

```bash
kubectl get deployment demo-app -o jsonpath='{.spec.template.spec.containers[0].image}'
```

Expected: Image should be `ghcr.io/tianhg468/agentic-ai/demo-app:sha-<commit-hash>`

- [ ] Rollout succeeded
- [ ] New image deployed
- [ ] Pods restarted with new image

## ☐ End-to-End Verification

**Make another change and verify full cycle**:

1. Edit a file in demo-app:
   ```bash
   echo "console.log('Test 2');" >> demo-app/src/index.js
   ```

2. Commit and push:
   ```bash
   git add .
   git commit -m "Test: Second deployment"
   git push origin main
   ```

3. Watch the deployment:
   ```bash
   kubectl get pods -w
   ```

- [ ] GitHub Actions workflow starts automatically
- [ ] New image is built and pushed to GHCR
- [ ] Deployment updates automatically
- [ ] Old pods terminate gracefully
- [ ] New pods start and become ready
- [ ] No downtime during rollout

**Check rollout history**:
```bash
kubectl rollout history deployment/demo-app
```

- [ ] Shows multiple revisions (at least 2)

## ☐ Resource Verification

**Check resource usage**:
```bash
kubectl top nodes
kubectl top pods -l app=demo-app
```

- [ ] Nodes have available resources
- [ ] Pods are within memory limits (64Mi limit, 128Mi request)
- [ ] No pods showing OOMKilled status

## ☐ AWS Console Verification

**EKS Console**: https://console.aws.amazon.com/eks/home?region=us-west-1

- [ ] Cluster `demo-app-cluster` is Active
- [ ] Node group `demo-app-ng-1` is Active
- [ ] 3 nodes are healthy

**EC2 Console**: https://console.aws.amazon.com/ec2/home?region=us-west-1

- [ ] 3 EC2 instances running (type: t3.medium)
- [ ] Instances tagged with cluster name

**VPC Console**: https://console.aws.amazon.com/vpc/home?region=us-west-1

- [ ] New VPC created (CIDR: 10.0.0.0/16)
- [ ] Subnets created
- [ ] NAT Gateway created

## ☐ Security & Configuration

**Check OIDC provider**:
```bash
aws eks describe-cluster --name demo-app-cluster --region us-west-1 --query 'cluster.identity.oidc.issuer' --output text
```

- [ ] OIDC issuer URL is returned

**Check cluster logging**:
```bash
aws eks describe-cluster --name demo-app-cluster --region us-west-1 --query 'cluster.logging' --output json
```

- [ ] Logging is enabled for: api, audit, authenticator, controllerManager, scheduler

## ☐ Troubleshooting Commands (If Needed)

If anything fails, use these commands to debug:

```bash
# View all resources
kubectl get all

# Describe deployment
kubectl describe deployment demo-app

# View pod events
kubectl get events --sort-by='.lastTimestamp'

# View pod logs
kubectl logs -l app=demo-app --all-containers=true

# Check node status
kubectl describe nodes

# View cluster events
kubectl get events -A

# Check AWS auth
aws sts get-caller-identity

# Re-configure kubectl
aws eks update-kubeconfig --name demo-app-cluster --region us-west-1
```

## ✅ Success Criteria

**All systems operational when**:
- ✅ All 3 nodes are Ready
- ✅ All 3 demo-app pods are Running
- ✅ GitHub Actions deploys successfully on push to main
- ✅ New images are automatically rolled out
- ✅ Application is accessible (via port-forward or ingress)
- ✅ No errors in pod logs
- ✅ CloudWatch logs are being collected

---

## 🧹 Cleanup (When Done)

**To delete everything and stop AWS charges**:

```bash
# Delete the cluster
eksctl delete cluster -f eks-cluster-config.yaml

# Verify deletion
aws eks list-clusters --region us-west-1
```

- [ ] Cluster deleted
- [ ] CloudFormation stacks deleted
- [ ] EC2 instances terminated
- [ ] VPC resources cleaned up

**Estimated time to complete**: 10-15 minutes

---

**Current Status**: ___ / ___ items completed

**Date**: ___________

**Notes**:
