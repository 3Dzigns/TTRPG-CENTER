#!/bin/bash
set -euo pipefail

# Start all microservices for development
# MVP v2 Microservices Architecture

ENVIRONMENT=${1:-"dev"}
SERVICE=${2:-""}

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting TTRPG Center Microservices (MVP v2)${NC}"
echo -e "${BLUE}Environment: $ENVIRONMENT${NC}"

# Set environment variable
export TARGET_ENV=$ENVIRONMENT

# Port configuration
declare -A PORTS
PORTS[ingest_dev]=8003
PORTS[ingest_test]=8184
PORTS[ingest_prod]=8285
PORTS[orchestrator_dev]=8004
PORTS[orchestrator_test]=8185
PORTS[orchestrator_prod]=8286
PORTS[admin_api_dev]=8001
PORTS[admin_api_test]=8182
PORTS[admin_api_prod]=8283
PORTS[user_api_dev]=8002
PORTS[user_api_test]=8181
PORTS[user_api_prod]=8284

start_microservice() {
    local service_name=$1
    local port=$2

    echo -e "${YELLOW}🔧 Starting $service_name service on port $port...${NC}"

    local module_path="services.$service_name.api:app"

    python -m uvicorn "$module_path" \
        --host 0.0.0.0 \
        --port "$port" \
        --reload &

    echo -e "${GREEN}✅ $service_name service started on http://localhost:$port${NC}"
}

# Start specific service or all services
if [ -n "$SERVICE" ]; then
    port_key="${SERVICE}_${ENVIRONMENT}"
    if [ -n "${PORTS[$port_key]:-}" ]; then
        port=${PORTS[$port_key]}
        start_microservice "$SERVICE" "$port"
    else
        echo -e "${RED}❌ Unknown service: $SERVICE${NC}"
        echo -e "${YELLOW}Available services: ingest, orchestrator, admin_api, user_api${NC}"
        exit 1
    fi
else
    # Start all services
    for service in ingest orchestrator admin_api user_api; do
        port_key="${service}_${ENVIRONMENT}"
        port=${PORTS[$port_key]}
        start_microservice "$service" "$port"
        sleep 2  # Brief delay between service starts
    done

    echo ""
    echo -e "${GREEN}🎉 All microservices started!${NC}"
    echo ""
    echo -e "${BLUE}Service URLs ($ENVIRONMENT environment):${NC}"
    for service in ingest orchestrator admin_api user_api; do
        port_key="${service}_${ENVIRONMENT}"
        port=${PORTS[$port_key]}
        echo -e "${GRAY}  • $service: http://localhost:$port${NC}"
        echo -e "${GRAY}    - Health: http://localhost:$port/healthz${NC}"
        echo -e "${GRAY}    - Docs: http://localhost:$port/docs${NC}"
    done

    echo ""
    echo -e "${YELLOW}To stop services, use Ctrl+C${NC}"
fi

echo ""
echo -e "${GREEN}Microservices ready for MVP v2 development! 🎮${NC}"
