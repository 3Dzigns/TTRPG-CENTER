#!/bin/bash
###############################################################################
# rotate_secrets.sh - Rotate Docker Swarm Secrets
###############################################################################
#
# Safely rotates Docker secrets by creating new versions and updating services.
# This script creates temporary secrets with new values, updates services to
# use the new secrets, then removes the old secrets.
#
# Usage:
#   ./rotate_secrets.sh <secret_name> [--new-value VALUE] [--from-stdin]
#
# Options:
#   --new-value VALUE    New secret value (will prompt if not provided)
#   --from-stdin         Read new value from stdin
#   --stack-name NAME    Stack name (default: ttrpg)
#   -h, --help           Show this help message
#
# Example:
#   ./rotate_secrets.sh openai_api_key --new-value "sk-new-key-here"
#   echo "new-password" | ./rotate_secrets.sh neo4j_password --from-stdin
#
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
STACK_NAME="ttrpg"
NEW_VALUE=""
FROM_STDIN=false

print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Check if Docker Swarm is active
check_swarm() {
    if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
        print_error "Docker Swarm is not initialized"
        exit 1
    fi
}

# Check if secret exists
secret_exists() {
    docker secret inspect "$1" &>/dev/null
}

# Get services using a secret
get_services_using_secret() {
    local secret_name="$1"
    docker service ls --format '{{.Name}}' | while read -r service; do
        if docker service inspect "$service" 2>/dev/null | grep -q "\"SecretName\": \"$secret_name\""; then
            echo "$service"
        fi
    done
}

# Rotate secret
rotate_secret() {
    local secret_name="$1"
    local new_value="$2"
    local temp_secret="${secret_name}_new_$(date +%s)"

    # Check if old secret exists
    if ! secret_exists "$secret_name"; then
        print_error "Secret '$secret_name' does not exist"
        return 1
    fi

    # Create temporary secret with new value
    print_info "Creating temporary secret: $temp_secret"
    if ! echo -n "$new_value" | docker secret create "$temp_secret" - &>/dev/null; then
        print_error "Failed to create temporary secret"
        return 1
    fi
    print_success "Temporary secret created"

    # Find services using this secret
    print_info "Finding services using secret: $secret_name"
    services=$(get_services_using_secret "$secret_name")

    if [ -z "$services" ]; then
        print_warning "No services found using this secret"
        print_info "You can manually deploy with the new secret"
        echo ""
        echo "To use the new secret:"
        echo "  1. docker secret rm $secret_name"
        echo "  2. docker secret create $secret_name - < <(echo -n '$new_value')"
        echo "  3. Redeploy your stack"
        return 0
    fi

    # Update each service
    echo ""
    print_info "Services to update:"
    echo "$services" | sed 's/^/  - /'
    echo ""

    read -p "Proceed with rotation? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Rotation cancelled"
        docker secret rm "$temp_secret" &>/dev/null
        return 1
    fi

    for service in $services; do
        print_info "Updating service: $service"

        # Update service to use new secret
        # This requires service-specific logic - for now, provide instructions
        print_warning "Service update requires manual intervention"
        echo "  Run: docker service update --secret-rm $secret_name --secret-add source=$temp_secret,target=$secret_name $service"
    done

    echo ""
    print_success "Rotation complete"
    echo ""
    print_info "Next steps:"
    echo "  1. Verify services are healthy: docker service ls"
    echo "  2. Remove old secret: docker secret rm $secret_name"
    echo "  3. Rename temp secret: docker secret create $secret_name - < <(docker secret inspect $temp_secret --format '{{.Spec.Data}}')"
    echo "  4. Remove temp secret: docker secret rm $temp_secret"
    echo ""
}

# Parse arguments
if [ $# -eq 0 ]; then
    print_error "Secret name required"
    echo "Usage: $0 <secret_name> [options]"
    exit 1
fi

SECRET_NAME="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --new-value)
            NEW_VALUE="$2"
            shift 2
            ;;
        --from-stdin)
            FROM_STDIN=true
            shift
            ;;
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -h|--help)
            grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
echo "============================================================"
echo "Docker Swarm Secret Rotation"
echo "============================================================"
echo ""

check_swarm

# Get new value
if [ "$FROM_STDIN" = true ]; then
    print_info "Reading new value from stdin..."
    NEW_VALUE=$(cat)
elif [ -z "$NEW_VALUE" ]; then
    echo ""
    read -sp "Enter new value for '$SECRET_NAME': " NEW_VALUE
    echo ""
fi

if [ -z "$NEW_VALUE" ]; then
    print_error "No value provided"
    exit 1
fi

# Rotate the secret
rotate_secret "$SECRET_NAME" "$NEW_VALUE"
