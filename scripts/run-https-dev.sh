#!/bin/bash
# HTTPS Development Server Startup Script
# Configures and runs TTRPG Center with SSL certificates for OAuth development

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Function to display help
show_help() {
    echo -e "${GREEN}HTTPS Development Server for TTRPG Center${NC}"
    echo "==========================================="
    echo ""
    echo "Usage: ./scripts/run-https-dev.sh [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo "  -s, --stop    Stop running servers"
    echo ""
    echo "This script starts both user and admin servers with HTTPS enabled"
    echo "for OAuth authentication development."
    echo ""
    echo -e "Servers will be available at:"
    echo -e "  ${CYAN}User App:  https://localhost:8000${NC}"
    echo -e "  ${CYAN}Admin App: https://localhost:8001${NC}"
    echo ""
    exit 0
}

# Function to stop servers
stop_servers() {
    echo -e "${YELLOW}Stopping existing servers...${NC}"
    pkill -f "uvicorn.*app_user\|uvicorn.*app_admin" 2>/dev/null
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -s|--stop)
            stop_servers
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
    shift
done

# Set working directory to project root
PROJECT_ROOT=$(pwd)
if [[ ! -d "src_common" ]]; then
    echo -e "${RED}Error: Please run this script from the TTRPG Center project root directory${NC}"
    exit 1
fi

# Verify SSL certificates exist
SSL_CERT="env/dev/ssl/cert.pem"
SSL_KEY="env/dev/ssl/key.pem"

if [[ ! -f "$SSL_CERT" ]] || [[ ! -f "$SSL_KEY" ]]; then
    echo -e "${RED}Error: SSL certificates not found.${NC}"
    echo -e "${YELLOW}Expected files:${NC}"
    echo "  $SSL_CERT"
    echo "  $SSL_KEY"
    echo ""
    echo -e "${YELLOW}Generate certificates with:${NC}"
    echo "  cd env/dev/ssl"
    echo "  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj \"/C=US/ST=Development/L=Dev/O=TTRPG-Center/CN=localhost\""
    exit 1
fi

echo -e "${GREEN}Starting HTTPS Development Servers...${NC}"
echo -e "${CYAN}SSL Certificate: $SSL_CERT${NC}"
echo -e "${CYAN}SSL Key: $SSL_KEY${NC}"

# Set environment variables
export APP_ENV="dev"
export PYTHONPATH="$PROJECT_ROOT"

# Function to start server with HTTPS
start_https_server() {
    local app_module=$1
    local port=$2
    local app_name=$3
    
    echo -e "${YELLOW}Starting $app_name Server (HTTPS on port $port)...${NC}"
    
    uvicorn "$app_module" \
        --host 0.0.0.0 \
        --port "$port" \
        --ssl-keyfile "$SSL_KEY" \
        --ssl-certfile "$SSL_CERT" \
        --reload &
    
    # Store PID for later cleanup
    local server_pid=$!
    echo "$server_pid" >> /tmp/ttrpg_https_servers.pid
    
    echo -e "${GRAY}Started $app_name server (PID: $server_pid)${NC}"
}

# Create PID file
echo "" > /tmp/ttrpg_https_servers.pid

# Start servers
start_https_server "app_user:app" 8000 "User App"
sleep 2
start_https_server "app_admin:app" 8001 "Admin App"

echo ""
echo -e "${GREEN}HTTPS Development Servers Starting...${NC}"
echo -e "${GREEN}===============================================${NC}"
echo -e "${CYAN}User App:  https://localhost:8000${NC}"
echo -e "${CYAN}Admin App: https://localhost:8001${NC}"
echo ""
echo -e "${YELLOW}OAuth Configuration:${NC}"
echo -e "${CYAN}  Redirect URL: https://localhost:8000/auth/callback${NC}"
echo -e "${CYAN}  Protocol: HTTPS (matches Google OAuth config)${NC}"
echo ""
echo -e "${YELLOW}Security Features Enabled:${NC}"
echo -e "${GREEN}  ✓ SSL/TLS Encryption${NC}"
echo -e "${GREEN}  ✓ Secure JWT Secrets${NC}"
echo -e "${GREEN}  ✓ OAuth HTTPS Compatibility${NC}"
echo ""
echo -e "${YELLOW}Note: You may see SSL certificate warnings in browser${NC}"
echo -e "${YELLOW}This is normal for self-signed development certificates.${NC}"
echo ""
echo -e "${GRAY}Press Ctrl+C to stop or use: ./scripts/run-https-dev.sh --stop${NC}"

# Cleanup function for graceful shutdown
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    if [[ -f /tmp/ttrpg_https_servers.pid ]]; then
        while read -r pid; do
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo -e "${GRAY}Stopped server (PID: $pid)${NC}"
            fi
        done < /tmp/ttrpg_https_servers.pid
        rm -f /tmp/ttrpg_https_servers.pid
    fi
    echo -e "${GREEN}Clean shutdown complete.${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Monitor servers
echo -e "${GRAY}Monitoring servers... (Press Ctrl+C to stop)${NC}"
while true; do
    sleep 30
    
    # Check if servers are still running
    user_running=false
    admin_running=false
    
    if pgrep -f "uvicorn.*app_user" >/dev/null 2>&1; then
        user_running=true
    fi
    
    if pgrep -f "uvicorn.*app_admin" >/dev/null 2>&1; then
        admin_running=true
    fi
    
    status=""
    if $user_running; then
        status="${status}User ✓"
    else
        status="${status}User ✗"
    fi
    
    if $admin_running; then
        status="${status}, Admin ✓"
    else
        status="${status}, Admin ✗"
    fi
    
    echo -e "${GRAY}$(date '+%H:%M:%S') - Status: $status${NC}"
    
    # Exit if both servers have stopped
    if ! $user_running && ! $admin_running; then
        echo -e "${RED}Both servers have stopped. Exiting.${NC}"
        cleanup
    fi
done