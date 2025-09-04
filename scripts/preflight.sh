#!/bin/bash
# scripts/preflight.sh
# Phase 0 preflight validation script for POSIX systems
set -euo pipefail

# Parse arguments
VERBOSE=false
ENVIRONMENT="dev"
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-v|--verbose] [-e|--environment ENV] [--skip-tests]"
            exit 1
            ;;
    esac
done

echo "🚀 Running Phase 0 preflight validation..."
echo ""

ERROR_COUNT=0

# Function to test components
test_component() {
    local name="$1"
    local test_command="$2"
    
    printf "🔍 Testing %s..." "$name"
    
    if eval "$test_command" >/dev/null 2>&1; then
        echo " ✅ PASSED"
    else
        echo " ❌ FAILED"
        ((ERROR_COUNT++))
        if [ "$VERBOSE" = true ]; then
            echo "    Error: $test_command failed"
        fi
    fi
}

# Test 1: Environment initialization
printf "🔍 Testing Environment initialization..."
if ./scripts/init-environments.sh "$ENVIRONMENT" >/dev/null 2>&1; then
    ENV_ROOT="env/$ENVIRONMENT"
    
    # Check required directories
    missing_dirs=()
    for dir in code config data logs; do
        if [[ ! -d "$ENV_ROOT/$dir" ]]; then
            missing_dirs+=("$dir")
        fi
    done
    
    # Check required config files
    missing_files=()
    if [[ ! -f "$ENV_ROOT/config/ports.json" ]]; then
        missing_files+=("ports.json")
    fi
    if [[ ! -f "$ENV_ROOT/config/.env.template" ]]; then
        missing_files+=(".env.template")
    fi
    
    if [[ ${#missing_dirs[@]} -eq 0 && ${#missing_files[@]} -eq 0 ]]; then
        echo " ✅ PASSED"
    else
        echo " ❌ FAILED"
        ((ERROR_COUNT++))
        if [ "$VERBOSE" = true ]; then
            [[ ${#missing_dirs[@]} -gt 0 ]] && echo "    Missing directories: ${missing_dirs[*]}"
            [[ ${#missing_files[@]} -gt 0 ]] && echo "    Missing files: ${missing_files[*]}"
        fi
    fi
else
    echo " ❌ FAILED"
    ((ERROR_COUNT++))
fi

# Test 2: Python availability
test_component "Python availability" "python3 --version || python --version"

# Test 3: Required Python packages
printf "🔍 Testing Python package dependencies..."
required_packages=(fastapi uvicorn pytest)
missing_packages=()

for package in "${required_packages[@]}"; do
    if ! python3 -c "import $package" 2>/dev/null && ! python -c "import $package" 2>/dev/null; then
        missing_packages+=("$package")
    fi
done

if [[ ${#missing_packages[@]} -eq 0 ]]; then
    echo " ✅ PASSED"
else
    echo " ❌ FAILED"
    ((ERROR_COUNT++))
    if [ "$VERBOSE" = true ]; then
        echo "    Missing packages: ${missing_packages[*]}"
        echo "    Install with: pip install ${missing_packages[*]}"
    fi
fi

# Test 4: Application health check
printf "🔍 Testing Application health check..."
export APP_ENV="$ENVIRONMENT"
export PORT="8000"
export LOG_LEVEL="ERROR"

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if cd src_common && $PYTHON_CMD -c "
import sys
import os

try:
    from ttrpg_logging import jlog, setup_logging
    from app import app  
    from mock_ingest import run_mock_sync
    
    # Test logging
    jlog('INFO', 'Preflight test', component='preflight')
    
    # Test mock ingestion
    os.environ['APP_ENV'] = 'test'
    result = run_mock_sync('preflight-test')
    assert result['status'] == 'completed'
    assert result['phases_completed'] == 3
    
    print('Core modules working')
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
" 2>/dev/null && cd ..; then
    echo " ✅ PASSED"
else
    echo " ❌ FAILED"
    ((ERROR_COUNT++))
fi

# Test 5: Port availability  
printf "🔍 Testing Port availability..."
ENV_ROOT="env/$ENVIRONMENT"
if [[ -f "$ENV_ROOT/config/ports.json" ]]; then
    HTTP_PORT=$($PYTHON_CMD -c "import json; print(json.load(open('$ENV_ROOT/config/ports.json'))['http_port'])")
    WS_PORT=$($PYTHON_CMD -c "import json; print(json.load(open('$ENV_ROOT/config/ports.json'))['websocket_port'])")
    
    # Check if ports are available using nc or built-in methods
    ports_available=true
    
    if command -v nc >/dev/null 2>&1; then
        # Use netcat to test ports
        if nc -z localhost "$HTTP_PORT" 2>/dev/null || nc -z localhost "$WS_PORT" 2>/dev/null; then
            ports_available=false
        fi
    else
        # Use Python to test ports
        if ! $PYTHON_CMD -c "
import socket
try:
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.bind(('localhost', $HTTP_PORT))
    s1.close()
    
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.bind(('localhost', $WS_PORT))
    s2.close()
    
    print('Ports available')
except OSError:
    print('Ports in use')
    exit(1)
" 2>/dev/null; then
            ports_available=false
        fi
    fi
    
    if [ "$ports_available" = true ]; then
        echo " ✅ PASSED"
        if [ "$VERBOSE" = true ]; then
            echo "    HTTP Port $HTTP_PORT available"
            echo "    WebSocket Port $WS_PORT available"
        fi
    else
        echo " ❌ FAILED"
        ((ERROR_COUNT++))
        if [ "$VERBOSE" = true ]; then
            echo "    Ports $HTTP_PORT or $WS_PORT may be in use"
        fi
    fi
else
    echo " ❌ FAILED"
    ((ERROR_COUNT++))
    if [ "$VERBOSE" = true ]; then
        echo "    Ports configuration file not found"
    fi
fi

# Test 6: Unit and functional tests (if not skipped)
if [ "$SKIP_TESTS" = false ]; then
    printf "🔍 Testing Unit tests..."
    if $PYTHON_CMD -m pytest tests/unit -q --tb=no >/dev/null 2>&1; then
        echo " ✅ PASSED"
    else
        echo " ❌ FAILED"
        ((ERROR_COUNT++))
    fi
    
    printf "🔍 Testing Functional tests..."
    if $PYTHON_CMD -m pytest tests/functional -q --tb=no >/dev/null 2>&1; then
        echo " ✅ PASSED"
    else
        echo " ❌ FAILED"
        ((ERROR_COUNT++))
    fi
fi

# Test 7: Security configuration
printf "🔍 Testing Security configuration..."
security_ok=true

# Check .gitignore exists and covers .env files
if [[ -d ".git" ]]; then
    if [[ -f ".gitignore" ]]; then
        if ! grep -q "\.env" .gitignore && ! grep -q "env/\*/config/\.env" .gitignore; then
            security_ok=false
            if [ "$VERBOSE" = true ]; then
                echo "    .env files are not properly gitignored"
            fi
        fi
    else
        security_ok=false
        if [ "$VERBOSE" = true ]; then
            echo "    .gitignore file is missing"
        fi
    fi
fi

# Check for suspicious environment variables
suspicious_vars=(SECRET_KEY JWT_SECRET API_KEY PASSWORD)
for var in "${suspicious_vars[@]}"; do
    if [[ -n "${!var:-}" ]]; then
        if [ "$VERBOSE" = true ]; then
            echo "    Warning: $var is set in environment"
        fi
    fi
done

if [ "$security_ok" = true ]; then
    echo " ✅ PASSED"
else
    echo " ❌ FAILED"
    ((ERROR_COUNT++))
fi

# Summary
echo ""
if [[ $ERROR_COUNT -eq 0 ]]; then
    echo "✅ Preflight validation PASSED! All checks successful."
    echo ""
    echo "🎯 Ready for Phase 0 development!"
    echo "Next steps:"
    
    case "$ENVIRONMENT" in
        dev) PORT=8000 ;;
        test) PORT=8181 ;;
        prod) PORT=8282 ;;
    esac
    
    echo "  1. Run: ./scripts/run-local.sh $ENVIRONMENT"
    echo "  2. Open: http://localhost:$PORT/healthz"
    echo "  3. Test: curl http://localhost:$PORT/mock-ingest/test-job-001"
    exit 0
else
    echo "❌ Preflight validation FAILED! $ERROR_COUNT error(s) found."
    echo ""
    echo "Please fix the issues above before proceeding."
    echo "Run with --verbose flag for more details."
    exit 1
fi