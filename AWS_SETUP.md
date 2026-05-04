# AWS EKS Setup Guide for GitHub Actions

This guide walks you through setting up AWS credentials and deploying the EKS cluster so GitHub Actions can deploy to it.

## Prerequisites

- AWS Account with admin access
- AWS CLI installed locally
- eksctl installed locally
- kubectl installed locally
- GitHub repository access with admin permissions

## Step 1: Create IAM User for GitHub Actions

1. **Log in to AWS Console** and navigate to IAM

2. **Create a new IAM user**:
   ```bash
   aws iam create-user --user-name github-actions-deployer
   ```

3. **Create access keys** for the user:
   ```bash
   aws iam create-access-key --user-name github-actions-deployer
   ```

   Save the output - you'll need the `AccessKeyId` and `SecretAccessKey`

## Step 2: Create IAM Policy for EKS Access

1. **Create a policy file** `github-actions-eks-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:DescribeNodegroup",
        "eks:ListNodegroups"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

2. **Create the policy**:
   ```bash
   aws iam create-policy \
     --policy-name GitHubActionsEKSPolicy \
     --policy-document file://github-actions-eks-policy.json
   ```

3. **Attach the policy to the user**:
   ```bash
   aws iam attach-user-policy \
     --user-name github-actions-deployer \
     --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/GitHubActionsEKSPolicy
   ```

   Replace `YOUR_ACCOUNT_ID` with your AWS account ID.

## Step 3: Deploy the EKS Cluster

1. **Create the cluster using eksctl**:
   ```bash
   eksctl create cluster -f eks-cluster-config.yaml
   ```

   This will take 15-20 minutes. The command will:
   - Create VPC and networking
   - Create EKS control plane
   - Create managed node groups
   - Configure kubectl context automatically

2. **Verify the cluster**:
   ```bash
   kubectl get nodes
   kubectl get namespaces
   ```

## Step 4: Configure EKS Authentication for GitHub Actions

1. **Update the aws-auth ConfigMap** to allow the IAM user to access the cluster:

   ```bash
   kubectl edit configmap aws-auth -n kube-system
   ```

   Add the following under `mapUsers`:

   ```yaml
   mapUsers: |
     - userarn: arn:aws:iam::YOUR_ACCOUNT_ID:user/github-actions-deployer
       username: github-actions-deployer
       groups:
         - system:masters
   ```

   Replace `YOUR_ACCOUNT_ID` with your AWS account ID.

   Alternatively, use eksctl:
   ```bash
   eksctl create iamidentitymapping \
     --cluster demo-app-cluster \
     --region us-west-1 \
     --arn arn:aws:iam::YOUR_ACCOUNT_ID:user/github-actions-deployer \
     --username github-actions-deployer \
     --group system:masters
   ```

## Step 5: Add GitHub Secrets

1. **Navigate to your GitHub repository**:
   - Go to Settings > Secrets and variables > Actions

2. **Add the following secrets**:

   | Secret Name | Value | Description |
   |-------------|-------|-------------|
   | `AWS_ACCESS_KEY_ID` | Your access key ID from Step 1 | AWS access key for GitHub Actions user |
   | `AWS_SECRET_ACCESS_KEY` | Your secret access key from Step 1 | AWS secret key for GitHub Actions user |
   | `AWS_REGION` | `us-west-1` | AWS region where EKS cluster is deployed |

   Click "New repository secret" for each one.

## Step 6: Deploy the Application

1. **Create the Kubernetes namespace** (if needed):
   ```bash
   kubectl create namespace default
   ```

2. **Initial deployment** (one-time manual deploy):
   ```bash
   kubectl apply -f demo-app/k8s/deployment.yaml
   kubectl apply -f demo-app/k8s/service.yaml
   ```

3. **Verify the deployment**:
   ```bash
   kubectl get deployments
   kubectl get pods
   kubectl get services
   ```

## Step 7: Test GitHub Actions Deployment

1. **Make a change** to the demo-app code

2. **Commit and push** to the main branch:
   ```bash
   git add .
   git commit -m "Test automated deployment"
   git push origin main
   ```

3. **Monitor the workflow**:
   - Go to your GitHub repository
   - Click on "Actions" tab
   - Watch the "Deploy to Kubernetes" workflow run

4. **Verify the deployment**:
   ```bash
   kubectl get pods
   kubectl rollout status deployment/demo-app
   ```

## Troubleshooting

### Issue: "error: You must be logged in to the server (Unauthorized)"

**Solution**: The IAM user doesn't have EKS access. Verify the aws-auth ConfigMap:
```bash
kubectl get configmap aws-auth -n kube-system -o yaml
```

### Issue: "error: couldn't get current server API group list"

**Solution**: AWS credentials are incorrect. Verify secrets in GitHub:
- Check AWS_ACCESS_KEY_ID
- Check AWS_SECRET_ACCESS_KEY
- Check AWS_REGION

### Issue: "Error from server (NotFound): deployments.apps 'demo-app' not found"

**Solution**: Initial deployment hasn't been created. Run:
```bash
kubectl apply -f demo-app/k8s/deployment.yaml
```

### Issue: Image pull errors

**Solution**: Ensure the GitHub Container Registry image is public or add imagePullSecrets:
```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT \
  --docker-email=YOUR_EMAIL
```

## Cleanup

When you're done testing, delete the cluster to avoid charges:

```bash
eksctl delete cluster -f eks-cluster-config.yaml
```

Or:

```bash
eksctl delete cluster --name demo-app-cluster --region us-west-1
```

## Cost Estimation

Running this EKS cluster will incur costs:
- EKS Control Plane: ~$73/month
- EC2 Instances (3x t3.medium): ~$95/month
- EBS Volumes: ~$6/month
- Data Transfer: Variable

**Total: ~$174/month**

Consider using smaller instance types (t3.small) or fewer nodes for testing.

## Security Best Practices

1. **Principle of Least Privilege**: The IAM policy provided gives minimal required permissions. Adjust as needed.

2. **Rotate Credentials**: Regularly rotate AWS access keys:
   ```bash
   aws iam create-access-key --user-name github-actions-deployer
   aws iam delete-access-key --user-name github-actions-deployer --access-key-id OLD_KEY_ID
   ```

3. **Enable MFA**: Consider requiring MFA for sensitive operations

4. **Audit Logs**: Enable CloudTrail to audit all AWS API calls

5. **Network Security**: The cluster uses private networking. Consider adding network policies.

## Next Steps

- Set up ingress controller (AWS ALB or NGINX)
- Configure DNS with Route53
- Add monitoring with CloudWatch Container Insights
- Set up automatic scaling (HPA and Cluster Autoscaler)
- Implement GitOps with ArgoCD or Flux
