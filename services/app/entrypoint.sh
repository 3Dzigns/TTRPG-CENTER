#!/bin/bash
set -e

# TTRPG Center Application Entry Point
# Handles initialization, migrations, and application startup

echo "TTRPG Center Application Starting..."
echo "Environment: ${APP_ENV:-dev}"
echo "Port: ${PORT:-8000}"

# Wait for database services to be ready
echo "Waiting for database services..."

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=0
    
    echo "Waiting for $service_name ($host:$port)..."
    
    while [ $attempt -lt $max_attempts ]; do
        if timeout 1 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
            echo "$service_name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "Attempt $attempt/$max_attempts: $service_name not ready, waiting..."
        sleep 2
    done
    
    echo "ERROR: $service_name failed to become ready after $max_attempts attempts"
    return 1
}

# Wait for PostgreSQL
if [ -n "${POSTGRES_HOST}" ]; then
    wait_for_service "${POSTGRES_HOST}" "${POSTGRES_PORT:-5432}" "PostgreSQL"
fi

# Wait for MongoDB
if [ -n "${MONGO_URI}" ]; then
    # Extract host from MongoDB URI (simple parsing)
    MONGO_HOST=$(echo "$MONGO_URI" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    if [ -n "$MONGO_HOST" ]; then
        wait_for_service "$MONGO_HOST" "27017" "MongoDB"
    fi
fi

# Wait for Neo4j
if [ -n "${NEO4J_URI}" ]; then
    # Extract host from Neo4j URI
    NEO4J_HOST=$(echo "$NEO4J_URI" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    if [ -n "$NEO4J_HOST" ]; then
        wait_for_service "$NEO4J_HOST" "7687" "Neo4j"
    fi
fi

# Wait for Redis
if [ -n "${REDIS_URL}" ]; then
    # Extract host from Redis URL
    REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    if [ -n "$REDIS_HOST" ]; then
        wait_for_service "$REDIS_HOST" "6379" "Redis"
    fi
fi

echo "All database services are ready!"

# Run database migrations if configured
if [ -n "${POSTGRES_HOST}" ] && [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    python -m alembic upgrade head || {
        echo "WARNING: Migration failed, continuing anyway..."
    }
fi

# Initialize application data if needed
echo "Initializing application..."
python -c "
import sys
sys.path.append('/app')
try:
    from src_common.preflight_checks import run_preflight_checks
    run_preflight_checks()
    print('Preflight checks completed successfully')
except Exception as e:
    print(f'Preflight checks failed: {e}')
    # Continue anyway for development
" || echo "Preflight checks skipped or failed"

# Start the application
echo "Starting application with command: $@"
exec "$@"