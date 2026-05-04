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
echo "EKS Test Session Manager"
echo "==========================================="
echo ""

# Check if cluster exists
CLUSTER_EXISTS=$(aws eks describe-cluster --name demo-app-cluster --region us-west-1 2>/dev/null || echo "not-found")

if [[ $CLUSTER_EXISTS == "not-found" ]]; then
    echo "Current Status: No cluster running ✅"
    echo "Estimated cost: $0/hour"
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "1) Deploy cluster and start testing (~$0.23/hour)"
    echo "2) Exit"
    echo ""
    read -p "Choose option (1 or 2): " choice

    if [[ $choice == "1" ]]; then
        echo ""
        print_info "Starting deployment..."
        print_warning "⏱️  This will take 15-20 minutes"
        print_warning "💰 Cost: ~$0.23/hour (~$5.60/day if you forget to delete!)"
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Deployment cancelled"
            exit 0
        fi

        # Deploy cluster
        print_info "Creating EKS cluster..."
        eksctl create cluster -f eks-cluster-config.yaml

        # Update kubeconfig
        aws eks update-kubeconfig --name demo-app-cluster --region us-west-1

        # Deploy app
        print_info "Deploying application..."
        kubectl apply -f demo-app/k8s/deployment.yaml
        kubectl apply -f demo-app/k8s/service.yaml

        print_success "Cluster is ready!"

        # Show status
        echo ""
        echo "==========================================="
        echo "Cluster Information"
        echo "==========================================="
        kubectl get nodes
        echo ""
        kubectl get pods
        echo ""

        # Start timer reminder
        START_TIME=$(date +%s)
        echo $START_TIME > .cluster-start-time

        print_warning "💰 COST REMINDER: Cluster is now running at ~$0.23/hour"
        print_warning "⏰ Started at: $(date)"
        print_info "👉 Run this script again when done to DELETE the cluster!"
        echo ""

        # Set reminder
        print_info "Setting up deletion reminder in 4 hours..."
        echo "#!/bin/bash" > /tmp/eks-reminder.sh
        echo "osascript -e 'display notification \"Your EKS cluster is still running! Cost: ~\$1\" with title \"EKS Cluster Alert\"'" >> /tmp/eks-reminder.sh
        chmod +x /tmp/eks-reminder.sh

        # Schedule reminder (works on macOS)
        (sleep 14400 && /tmp/eks-reminder.sh) &

    else
        print_info "Goodbye!"
        exit 0
    fi
else
    # Cluster exists - show info and delete option
    print_warning "⚠️  CLUSTER IS RUNNING!"

    # Calculate running time
    if [[ -f .cluster-start-time ]]; then
        START_TIME=$(cat .cluster-start-time)
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        HOURS=$(echo "scale=2; $ELAPSED/3600" | bc)
        COST=$(echo "scale=2; $HOURS*0.23" | bc)

        echo ""
        print_info "Running time: ${HOURS} hours"
        print_warning "Estimated cost so far: \$${COST}"
    fi

    echo ""
    echo "Cluster Status:"
    kubectl get nodes 2>/dev/null || print_error "kubectl not configured"
    echo ""

    echo "What would you like to do?"
    echo ""
    echo "1) Keep testing (continue running)"
    echo "2) DELETE cluster and STOP charges ⚠️"
    echo "3) Show cluster info"
    echo ""
    read -p "Choose option (1, 2, or 3): " choice

    case $choice in
        1)
            print_info "Cluster will continue running at ~$0.23/hour"
            print_warning "Don't forget to delete it when done!"
            ;;
        2)
            echo ""
            print_warning "This will DELETE the cluster permanently!"
            print_warning "All data will be lost (this is expected for testing)"
            echo ""
            read -p "Are you sure? Type 'DELETE' to confirm: " confirm

            if [[ $confirm == "DELETE" ]]; then
                print_info "Deleting cluster..."
                print_info "This will take 10-15 minutes..."

                eksctl delete cluster -f eks-cluster-config.yaml

                # Remove start time file
                rm -f .cluster-start-time

                # Calculate final cost
                if [[ -f .cluster-start-time ]]; then
                    START_TIME=$(cat .cluster-start-time)
                    CURRENT_TIME=$(date +%s)
                    ELAPSED=$((CURRENT_TIME - START_TIME))
                    HOURS=$(echo "scale=2; $ELAPSED/3600" | bc)
                    COST=$(echo "scale=2; $HOURS*0.23" | bc)

                    echo ""
                    print_success "Cluster deleted successfully!"
                    print_info "Total session time: ${HOURS} hours"
                    print_info "Estimated session cost: \$${COST}"
                fi

                print_success "Cluster deleted! No more charges."
                print_info "Remaining budget: Check with 'aws ce get-cost-and-usage'"
            else
                print_error "Deletion cancelled - cluster still running!"
            fi
            ;;
        3)
            echo ""
            echo "==========================================="
            echo "Full Cluster Status"
            echo "==========================================="
            echo ""
            echo "Nodes:"
            kubectl get nodes
            echo ""
            echo "Pods:"
            kubectl get pods -A
            echo ""
            echo "Services:"
            kubectl get svc -A
            echo ""
            print_warning "Cluster is still running at ~$0.23/hour"
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac
fi

echo ""
print_info "Session complete"
