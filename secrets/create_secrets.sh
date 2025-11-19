#!/bin/bash
###############################################################################
# create_secrets.sh - Initialize Docker Swarm Secrets
###############################################################################
#
# Creates Docker secrets from environment variables or generates secure defaults.
# Secrets are securely stored in Docker Swarm and accessible only to
# authorized services.
#
# Usage:
#   ./create_secrets.sh [--from-env-file FILE] [--force]
#
# Options:
#   --from-env-file FILE    Load secrets from .env file (default: ../.env)
#   --force                 Recreate existing secrets (requires removal first)
#   -h, --help              Show this help message
#
# Example:
#   ./create_secrets.sh --from-env-file ../.env
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE="../.env"
FORCE=false

# Secret definitions (name, description, env_var_name, default_value)
declare -A SECRETS=(
    ["openai_api_key"]="OpenAI API Key for embeddings and analysis|OPENAI_API_KEY|"
    ["neo4j_user"]="Neo4j database username|NEO4J_USER|neo4j"
    ["neo4j_password"]="Neo4j database password|NEO4J_PASSWORD|"
    ["postgres_user"]="PostgreSQL username|POSTGRES_USER|postgres"
    ["postgres_password"]="PostgreSQL password|POSTGRES_PASSWORD|"
    ["postgres_db"]="PostgreSQL database name|POSTGRES_DB|ttrpg_auth"
)

# Function to generate random password
generate_password() {
    # Generate 32-character random password with alphanumeric and special chars
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to check if Docker Swarm is initialized
check_swarm() {
    if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
        print_error "Docker Swarm is not initialized"
        echo ""
        echo "Initialize Swarm with:"
        echo "  docker swarm init"
        exit 1
    fi
    print_success "Docker Swarm is active"
}

# Function to check if secret exists
secret_exists() {
    docker secret inspect "$1" &>/dev/null
}

# Function to create secret from value
create_secret() {
    local secret_name="$1"
    local secret_value="$2"

    if secret_exists "$secret_name"; then
        if [ "$FORCE" = true ]; then
            print_warning "Secret '$secret_name' already exists (--force specified)"
            echo "  To recreate, first remove it with: docker secret rm $secret_name"
            return 1
        else
            print_warning "Secret '$secret_name' already exists (use --force to recreate)"
            return 1
        fi
    fi

    if [ -z "$secret_value" ]; then
        print_warning "Skipping '$secret_name' - no value provided"
        return 1
    fi

    echo -n "$secret_value" | docker secret create "$secret_name" - &>/dev/null

    if [ $? -eq 0 ]; then
        print_success "Created secret: $secret_name"
        # Show masked value
        local masked="${secret_value:0:8}..."
        echo "  Value: $masked"
        return 0
    else
        print_error "Failed to create secret: $secret_name"
        return 1
    fi
}

# Function to load value from env file
load_from_env() {
    local env_var="$1"

    if [ ! -f "$ENV_FILE" ]; then
        return 1
    fi

    # Extract value from .env file (handles comments and empty lines)
    grep -E "^${env_var}=" "$ENV_FILE" | cut -d '=' -f 2- | sed 's/^["'\'']//' | sed 's/["'\'']$//'
}

# Function to prompt for secret value
prompt_for_secret() {
    local secret_name="$1"
    local description="$2"
    local default_value="$3"

    echo ""
    print_info "Secret: $secret_name"
    echo "  Description: $description"

    if [ -n "$default_value" ]; then
        echo "  Default: ${default_value:0:10}..." # Show first 10 chars
        read -sp "  Enter value (or press Enter to use default): " input_value
        echo ""

        if [ -z "$input_value" ]; then
            echo "$default_value"
        else
            echo "$input_value"
        fi
    else
        read -sp "  Enter value: " input_value
        echo ""
        echo "$input_value"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --from-env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main execution
echo "============================================================"
echo "Docker Swarm Secrets Setup - TTRPG Center"
echo "============================================================"
echo ""

# Check prerequisites
check_swarm

# Check if openssl is available for password generation
if ! command -v openssl &> /dev/null; then
    print_warning "openssl not found - cannot generate random passwords"
    print_info "Install openssl or provide passwords manually"
fi

# Check if env file exists
if [ -f "$ENV_FILE" ]; then
    print_info "Using environment file: $ENV_FILE"
else
    print_warning "Environment file not found: $ENV_FILE"
    print_info "Will use defaults or prompt for secrets interactively"
fi

echo ""
print_info "Creating secrets..."
echo ""

created_count=0
skipped_count=0
failed_count=0

# Track generated passwords to save to .env
declare -A GENERATED_PASSWORDS

# Create each secret
for secret_name in openai_api_key neo4j_user neo4j_password postgres_user postgres_password postgres_db; do
    IFS='|' read -r description env_var default_value <<< "${SECRETS[$secret_name]}"

    # Try to load from env file first
    secret_value=""
    if [ -f "$ENV_FILE" ]; then
        secret_value=$(load_from_env "$env_var")
    fi

    # If not in env file and has default, use default
    if [ -z "$secret_value" ] && [ -n "$default_value" ]; then
        secret_value="$default_value"
        print_info "Using default for $secret_name: $default_value"
    fi

    # Generate random password for password fields if empty
    if [ -z "$secret_value" ] && [[ "$secret_name" == *"password"* ]]; then
        if command -v openssl &> /dev/null; then
            secret_value=$(generate_password)
            GENERATED_PASSWORDS["$env_var"]="$secret_value"
            print_info "Generated random password for $secret_name"
        fi
    fi

    # If still empty, prompt user
    if [ -z "$secret_value" ]; then
        secret_value=$(prompt_for_secret "$secret_name" "$description" "")
    fi

    # Create the secret
    if create_secret "$secret_name" "$secret_value"; then
        ((created_count++))
    elif secret_exists "$secret_name"; then
        ((skipped_count++))
    else
        ((failed_count++))
    fi
done

# Summary
echo ""
echo "============================================================"
echo "Summary"
echo "============================================================"
print_success "Created: $created_count secrets"
if [ $skipped_count -gt 0 ]; then
    print_warning "Skipped: $skipped_count secrets (already exist)"
fi
if [ $failed_count -gt 0 ]; then
    print_error "Failed: $failed_count secrets"
fi
echo ""

# Save generated passwords to .env if any were created
if [ ${#GENERATED_PASSWORDS[@]} -gt 0 ]; then
    echo ""
    print_info "Generated passwords - add these to your .env file:"
    echo "============================================================"
    for env_var in "${!GENERATED_PASSWORDS[@]}"; do
        echo "$env_var=${GENERATED_PASSWORDS[$env_var]}"
    done
    echo "============================================================"
    echo ""
fi

# List created secrets
echo "Current secrets:"
docker secret ls --format "table {{.Name}}\t{{.CreatedAt}}" | grep -E "(openai|neo4j|postgres|NAME)"
echo ""

# Next steps
echo "============================================================"
echo "Next Steps"
echo "============================================================"
echo "1. Build WebUI image: docker build -f webui/Dockerfile.optimized -t ttrpg-webui:latest ."
echo "2. Build Unstructured image (if needed): docker build -f docker/unstructured/Dockerfile -t n8n_ttrpg_unstructured:latest ."
echo "3. Label GPU node: docker node update --label-add gpu=true \$(docker node ls -q)"
echo "4. Deploy stack: docker stack deploy -c docker-stack-ttrpg.yml ttrpg"
echo "5. Check services: docker service ls"
echo "6. View logs: docker service logs ttrpg_<service_name>"
echo ""
print_warning "IMPORTANT: Secrets cannot be read after creation"
print_warning "Store backup of credentials securely outside version control"
echo ""
