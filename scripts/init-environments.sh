#!/bin/bash
# scripts/init-environments.sh
set -euo pipefail

ENV_NAME="${1:-dev}"
case "$ENV_NAME" in
    dev|test|prod) ;;
    *) echo "Error: Environment must be 'dev', 'test', or 'prod'" >&2; exit 1 ;;
esac

ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
ENV_ROOT="$ROOT/env/$ENV_NAME"

mkdir -p "$ENV_ROOT/code" "$ENV_ROOT/config" "$ENV_ROOT/data" "$ENV_ROOT/logs"

declare -A PORTS=([dev]=8000 [test]=8181 [prod]=8282)
PORT="${PORTS[$ENV_NAME]}"

cat > "$ENV_ROOT/config/ports.json" <<EOF
{
  "http_port": $PORT,
  "websocket_port": $((PORT + 1000)),
  "name": "$ENV_NAME"
}
EOF

case "$ENV_NAME" in
    dev) CACHE_TTL=0 ;;
    test) CACHE_TTL=5 ;;
    prod) CACHE_TTL=300 ;;
esac

cat > "$ENV_ROOT/config/.env.template" <<EOF
# Environment: $ENV_NAME
APP_ENV=$ENV_NAME
PORT=$PORT
LOG_LEVEL=INFO
ARTIFACTS_PATH=./artifacts/$ENV_NAME

# Vector store configuration (DEV defaults to Cassandra)
VECTOR_STORE_BACKEND=cassandra
CASSANDRA_CONTACT_POINTS=cassandra-dev
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ttrpg
CASSANDRA_TABLE=chunks
CASSANDRA_USERNAME=
CASSANDRA_PASSWORD=

# Legacy AstraDB configuration (optional)
ASTRA_DB_API_ENDPOINT=
ASTRA_DB_APPLICATION_TOKEN=
ASTRA_DB_ID=
ASTRA_DB_KEYSPACE=default_keyspace
ASTRA_DB_REGION=us-east-2

# AI Model API Keys (fill in actual values)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Security
SECRET_KEY=
JWT_SECRET=

# Cache settings
CACHE_TTL_SECONDS=$CACHE_TTL
EOF

if [[ ! -f "$ENV_ROOT/config/.env" ]]; then
    cp "$ENV_ROOT/config/.env.template" "$ENV_ROOT/config/.env"
fi

cat > "$ENV_ROOT/config/logging.json" <<EOF
{
  "version": 1,
  "formatters": {
    "json": {
      "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
      "class": "pythonjsonlogger.jsonlogger.JsonFormatter"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "formatter": "json",
      "level": "INFO"
    },
    "file": {
      "class": "logging.handlers.RotatingFileHandler",
      "filename": "env/$ENV_NAME/logs/app.log",
      "formatter": "json",
      "level": "INFO",
      "maxBytes": 10485760,
      "backupCount": 5
    }
  },
  "root": {
    "level": "INFO",
    "handlers": ["console", "file"]
  }
}
EOF

echo "Initialized $ENV_NAME environment at $ENV_ROOT"
echo "Created directories: code, config, data, logs"
echo "Ports JSON written with HTTP port $PORT"
echo "Generated config/.env.template (and config/.env if missing)"
