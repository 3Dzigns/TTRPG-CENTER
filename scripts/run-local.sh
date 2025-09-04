#!/bin/bash
# scripts/run-local.sh
set -euo pipefail

# Parse environment argument
ENV_NAME="${1:-dev}"

# Validate environment name
case "$ENV_NAME" in
    dev|test|prod) ;;
    *) echo "❌ Error: Environment must be 'dev', 'test', or 'prod'" >&2; exit 1 ;;
esac

# Get paths
ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
ENV_ROOT="$ROOT/env/$ENV_NAME"
CONFIG_DIR="$ENV_ROOT/config"

# Check if environment is initialized
if [[ ! -d "$CONFIG_DIR" ]]; then
    echo "❌ Environment '$ENV_NAME' not initialized. Run: ./scripts/init-environments.sh $ENV_NAME" >&2
    exit 1
fi

# Load environment configuration
if [[ ! -f "$CONFIG_DIR/.env" ]]; then
    echo "⚠️  No .env file found. Using .env.template..." >&2
    if [[ -f "$CONFIG_DIR/.env.template" ]]; then
        cp "$CONFIG_DIR/.env.template" "$CONFIG_DIR/.env"
        echo "📋 Copied .env.template to .env"
    else
        echo "❌ No .env.template found either. Please run init-environments.sh first." >&2
        exit 1
    fi
fi

# Read ports configuration
PORTS_PATH="$CONFIG_DIR/ports.json"
if [[ ! -f "$PORTS_PATH" ]]; then
    echo "❌ ports.json not found. Environment may not be properly initialized." >&2
    exit 1
fi

# Extract ports using Python (more reliable than jq dependency)
HTTP_PORT=$(python3 -c "import json; print(json.load(open('$PORTS_PATH'))['http_port'])")
WS_PORT=$(python3 -c "import json; print(json.load(open('$PORTS_PATH'))['websocket_port'])")

# Set environment variables
export APP_ENV="$ENV_NAME"
export PORT="$HTTP_PORT"
export WEBSOCKET_PORT="$WS_PORT"

# Load .env file into environment variables
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    if [[ -n "$key" && ! "$key" =~ ^[[:space:]]*# ]]; then
        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        export "$key"="$value"
    fi
done < "$CONFIG_DIR/.env"

echo "🚀 Starting TTRPG Center in $ENV_NAME environment..."
echo "📡 HTTP Port: $HTTP_PORT"
echo "🔌 WebSocket Port: $WS_PORT"
echo "📂 Environment Root: $ENV_ROOT"
echo ""

# Change to project root
cd "$ROOT"

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python not found. Please install Python 3.10+." >&2
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version)
echo "🐍 Using: $PYTHON_VERSION"

# Check if we're in a virtual environment or have pip available
if [[ ! -d "venv" ]] && ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "📦 Installing requirements..." 
    if command -v pip3 &> /dev/null; then
        pip3 install -r requirements.txt || echo "⚠️  Failed to install requirements. You may need to install them manually."
    elif command -v pip &> /dev/null; then
        pip install -r requirements.txt || echo "⚠️  Failed to install requirements. You may need to install them manually."
    fi
fi

# Start the application
echo "🎯 Starting application..."
if [[ -f "src_common/app.py" ]]; then
    $PYTHON_CMD -m uvicorn src_common.app:app --host 0.0.0.0 --port "$HTTP_PORT" --reload
else
    echo "❌ src_common/app.py not found. Creating basic application first..." >&2
    exit 1
fi