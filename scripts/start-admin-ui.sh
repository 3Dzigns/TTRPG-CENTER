#!/bin/bash
set -euo pipefail

# Start Admin UI with Test Console
# MVP v2 requirement implementation

ENVIRONMENT=${1:-"dev"}
PORT=${2:-3000}

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting TTRPG Center Admin UI with Test Console${NC}"
echo -e "${BLUE}Environment: $ENVIRONMENT${NC}"

# Navigate to admin-ui directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ADMIN_UI_PATH="$SCRIPT_DIR/../web/admin-ui"

if [ ! -d "$ADMIN_UI_PATH" ]; then
    echo -e "${RED}❌ Admin UI directory not found: $ADMIN_UI_PATH${NC}"
    exit 1
fi

cd "$ADMIN_UI_PATH"

# Set environment variables
if [ "$ENVIRONMENT" = "prod" ]; then
    export NODE_ENV="production"
else
    export NODE_ENV="development"
fi
export VITE_ENVIRONMENT="$ENVIRONMENT"

# Set Admin API URL based on environment
case $ENVIRONMENT in
    "dev")
        export ADMIN_API_BASE_URL="http://localhost:8001"
        ;;
    "test")
        export ADMIN_API_BASE_URL="http://localhost:8182"
        ;;
    "prod")
        export ADMIN_API_BASE_URL="http://localhost:8283"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}Admin API URL: $ADMIN_API_BASE_URL${NC}"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Installing dependencies...${NC}"
    npm install
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# Start development server
echo -e "${YELLOW}🔧 Starting Admin UI on port $PORT...${NC}"

if [ "$ENVIRONMENT" = "prod" ]; then
    # Build and serve production version
    echo -e "${YELLOW}Building production version...${NC}"
    npm run build

    echo -e "${YELLOW}Starting production server...${NC}"
    npm run preview -- --port $PORT
else
    # Start development server
    npm run dev -- --port $PORT
fi

echo ""
echo -e "${GREEN}🎉 Admin UI with Test Console is ready!${NC}"
echo ""
echo -e "${BLUE}URLs:${NC}"
echo -e "${GRAY}  • Admin UI: http://localhost:$PORT${NC}"
echo -e "${GRAY}  • Test Console: http://localhost:$PORT (main feature)${NC}"
echo -e "${GRAY}  • Admin API: $ADMIN_API_BASE_URL${NC}"
echo ""
echo -e "${BLUE}Features:${NC}"
echo -e "${GRAY}  ✅ External test execution (Unit/Functional/Security/Regression/Perf)${NC}"
echo -e "${GRAY}  ✅ Real-time test output streaming${NC}"
echo -e "${GRAY}  ✅ Multi-environment targeting (dev/test/prod)${NC}"
echo -e "${GRAY}  ✅ Test result downloads${NC}"
echo -e "${GRAY}  ✅ Execution history tracking${NC}"
echo ""
echo -e "${GREEN}MVP v2 Test Console ready for external test execution! 🧪${NC}"