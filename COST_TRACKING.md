# Cost Tracking Guide - Test & Delete Approach

## Your Budget: $119.91

## Cost Per Session

### With Current Configuration:
- **$0.23/hour** total
- **$5.60/day** if running continuously
- **Target: 2-4 hours per session = $0.46 - $0.92 per session**

You can afford **50+ testing sessions** with your budget!

## Hourly Breakdown:
- EKS Control Plane: $0.10/hour
- 3x t3.medium nodes: $0.125/hour
- Storage & data transfer: ~$0.005/hour
- **Total: ~$0.23/hour**

---

## ⚡ Quick Commands

### Start a Test Session:
```bash
./test-and-cleanup.sh
# Choose option 1: Deploy cluster
```

### End Session (DELETE CLUSTER):
```bash
./test-and-cleanup.sh
# Choose option 2: DELETE cluster
```

**⚠️ CRITICAL**: Always delete the cluster when done testing!

---

## 💰 Cost Tracking

### Check Your AWS Spending:

**Via AWS CLI:**
```bash
# Get today's costs
aws ce get-cost-and-usage \
    --time-period Start=$(date -u -v-1d +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
    --granularity DAILY \
    --metrics UnblendedCost \
    --query 'ResultsByTime[*].[TimePeriod.Start,Total.UnblendedCost.Amount]' \
    --output table

# Get month-to-date total
aws ce get-cost-and-usage \
    --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
    --granularity MONTHLY \
    --metrics UnblendedCost \
    --query 'ResultsByTime[0].Total.UnblendedCost.Amount' \
    --output text
```

**Via AWS Console:**
1. Go to: https://console.aws.amazon.com/billing/home
2. Click "Bills" in left sidebar
3. View current month charges

### Set Up Billing Alerts:

**1. Create Budget Alert:**
```bash
aws budgets create-budget \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --budget file://budget-config.json
```

Create `budget-config.json`:
```json
{
  "BudgetName": "EKS-Testing-Budget",
  "BudgetLimit": {
    "Amount": "100",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

**2. Via AWS Console:**
1. Go to: https://console.aws.amazon.com/billing/home#/budgets
2. Click "Create budget"
3. Choose "Cost budget"
4. Set amount: $100
5. Add email alert at 80% ($80)

---

## 📊 Session Tracking Template

Copy this to track your sessions:

```
Session Log
-----------

Session 1:
  Date: ___________
  Start: ___:___
  End: ___:___
  Duration: ___ hours
  Cost: $_____
  Purpose: Initial setup and testing

Session 2:
  Date: ___________
  Start: ___:___
  End: ___:___
  Duration: ___ hours
  Cost: $_____
  Purpose: ___________

...

Total Sessions: ___
Total Cost: $_____
Remaining Budget: $_____
```

---

## 🎯 Recommended Testing Schedule

### For Learning/Demo (Optimal Cost):

**Week 1**: 2-3 sessions (6-8 hours total) = **$1.40 - $1.84**
- Session 1: Initial deployment and verification (3-4 hours)
- Session 2: GitHub Actions testing (2-3 hours)
- Session 3: Any fixes or improvements (1-2 hours)

**Week 2-4**: As needed (2-3 hours per week) = **$0.46 - $0.69/week**
- Deploy only when showing the project or making changes

**Total for 1 month**: **~$5-10** ✅

This leaves $109+ for future testing or other AWS services!

---

## ⚠️ Common Mistakes to Avoid

### ❌ Don't:
1. **Leave cluster running overnight** = -$5.60/night wasted!
2. **Forget to delete after testing** = Budget gone in 21 days
3. **Deploy on Friday and forget over weekend** = -$33.60 wasted!

### ✅ Do:
1. **Use `./test-and-cleanup.sh`** - it reminds you to delete
2. **Set phone reminder** when deploying
3. **Delete immediately** after testing
4. **Check AWS billing** weekly

---

## 🚨 Emergency: "I Forgot to Delete!"

If you accidentally left the cluster running:

**Quick delete:**
```bash
eksctl delete cluster --name demo-app-cluster --region us-west-1
```

**Check what's running:**
```bash
# List all EKS clusters
aws eks list-clusters --region us-west-1

# List all EC2 instances
aws ec2 describe-instances \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType]' \
    --output table
```

**Delete everything EKS-related:**
```bash
# Delete cluster
eksctl delete cluster --name demo-app-cluster --region us-west-1

# Verify CloudFormation stacks are deleted
aws cloudformation list-stacks \
    --stack-status-filter DELETE_IN_PROGRESS DELETE_COMPLETE \
    --query 'StackSummaries[?contains(StackName, `eksctl-demo-app-cluster`)]'
```

---

## 💡 Pro Tips

### 1. Use t3.small instead of t3.medium (saves 50%):
Edit `eks-cluster-config.yaml` line 19:
```yaml
instanceType: t3.small  # Change from t3.medium
```
New cost: **$0.15/hour** instead of $0.23/hour

### 2. Use 2 nodes instead of 3:
Edit `eks-cluster-config.yaml` line 22:
```yaml
desiredCapacity: 2  # Change from 3
```

### 3. Test locally first:
Use minikube or Docker Desktop Kubernetes for initial development, only deploy to EKS when you need to test GitHub Actions integration.

---

## 📈 Budget Projection

### Conservative Estimate (Recommended):
- **8 sessions × 3 hours each** = 24 hours total
- **24 hours × $0.23/hour** = **$5.52**
- **Remaining: $114.39** ✅

### Moderate Use:
- **20 sessions × 2 hours each** = 40 hours total
- **40 hours × $0.23/hour** = **$9.20**
- **Remaining: $110.71** ✅

### Heavy Use:
- **50 sessions × 2 hours each** = 100 hours total
- **100 hours × $0.23/hour** = **$23.00**
- **Remaining: $96.91** ✅

**You're in great shape for a project!** 🎉

---

## Verification Checklist

Before ending each session:

- [ ] Tested what I needed to test
- [ ] Captured screenshots/logs if needed
- [ ] Ran `./test-and-cleanup.sh`
- [ ] Chose option 2: DELETE
- [ ] Confirmed deletion completed
- [ ] Ran `aws eks list-clusters` to verify (should be empty)
- [ ] Logged session duration and cost

---

## Quick Reference Card

**Print this and keep it visible:**

```
┌─────────────────────────────────────────┐
│  EKS CLUSTER COST REMINDER              │
├─────────────────────────────────────────┤
│  Running cost: $0.23/hour               │
│  Daily cost: $5.60/day                  │
│  Your budget: $119.91                   │
│                                         │
│  ⚠️  ALWAYS DELETE WHEN DONE!           │
│                                         │
│  Delete command:                        │
│  ./test-and-cleanup.sh                  │
│  (Choose option 2)                      │
│                                         │
│  Verify deleted:                        │
│  aws eks list-clusters                  │
│  (Should return empty)                  │
└─────────────────────────────────────────┘
```

---

**Next Steps:**
1. Add GitHub secrets (one-time setup)
2. Run `./test-and-cleanup.sh` to start your first session
3. Test for 2-4 hours
4. Run `./test-and-cleanup.sh` again and DELETE
5. Check AWS billing to see actual cost
