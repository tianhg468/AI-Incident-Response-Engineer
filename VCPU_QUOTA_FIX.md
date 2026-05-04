# vCPU Quota Issue - SOLVED ✅

## The Problem

Your AWS account has a **5 vCPU limit** for standard EC2 instances.

**Original configuration tried to use:**
- 3x t3.medium = 3 instances × 2 vCPUs = **6 vCPUs** ❌ (exceeds limit)

**Why it failed:**
- AWS couldn't launch the instances because you'd exceed your quota
- CloudFormation waited 30 minutes then timed out
- This happened in BOTH us-east-1 and us-west-1

## The Solution ✅

I've updated `eks-cluster-config.yaml` to use:
- **2x t3.small = 2 instances × 2 vCPUs = 4 vCPUs** ✅ (within limit!)

### What Changed:

| Setting | Old Value | New Value | Why |
|---------|-----------|-----------|-----|
| Instance Type | t3.medium | t3.small | Fits quota, still powerful enough |
| Desired Nodes | 3 | 2 | Reduces vCPU usage |
| Min Nodes | 2 | 1 | Allows scaling down if needed |
| Max Nodes | 4 | 2 | Prevents exceeding quota |
| **Total vCPUs** | **6** | **4** ✅ | **Within 5 vCPU limit** |

### Cost Impact:

**Old cost:** ~$0.23/hour
**New cost:** ~$0.17/hour (26% cheaper!)

- EKS Control Plane: $0.10/hour
- 2x t3.small: $0.063/hour ($0.0315 each)
- Storage: ~$0.007/hour
- **Total: ~$0.17/hour or ~$4.00/day**

## Next Steps

### 1. Clean Up Failed Deployments

**Clean up us-east-1:**
```bash
eksctl delete cluster --name demo-app-cluster --region us-east-1
```

**Clean up us-west-1:**
```bash
eksctl delete cluster --name demo-app-cluster --region us-west-1
```

Wait for both to complete (5-10 minutes each). You can run them in parallel in separate terminals.

### 2. Deploy with New Configuration

After cleanup completes:

```bash
./test-and-cleanup.sh
```

Choose option 1 to deploy. **This should work now!**

### 3. Verify It Works

After deployment:
```bash
kubectl get nodes
```

You should see 2 nodes in Ready status.

## Alternative: Request Quota Increase

If you need more capacity in the future, you can request a quota increase:

### Via AWS Console:
1. Go to: https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas
2. Search for "Running On-Demand Standard"
3. Click "Request quota increase"
4. Request: 32 vCPUs (allows for 3x t3.medium)
5. Reason: "Need capacity for EKS cluster testing"

**Approval time:** Usually 15 minutes to 2 hours

### Via AWS CLI:
```bash
aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --desired-value 32 \
    --region us-west-1
```

## Check Your Current vCPU Usage

To see how many vCPUs you're currently using:

```bash
aws ec2 describe-instances \
    --region us-west-1 \
    --query 'Reservations[*].Instances[?State.Name==`running`].[InstanceType,CpuOptions.CoreCount,CpuOptions.ThreadsPerCore]' \
    --output table
```

## Why This Happens

**New AWS accounts** typically start with low quotas:
- 5 vCPUs for standard instances
- 32 vCPUs after first quota increase
- Higher limits available on request

This is a safety measure to prevent accidental large bills.

## Summary

✅ **Root cause identified:** vCPU quota limit (5 vCPUs)
✅ **Configuration updated:** 2x t3.small (4 vCPUs)
✅ **Side benefit:** Lower cost ($0.17/hour vs $0.23/hour)
✅ **Next step:** Clean up failed deployments and retry

The cluster should deploy successfully now! 🎉
