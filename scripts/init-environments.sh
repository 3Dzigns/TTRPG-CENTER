#!/bin/bash
# scripts/init-environments.sh
set -euo pipefail

# Parse command line argument
ENV_NAME="${1:-dev}"

# Validate environment name
case "$ENV_NAME" in
    dev|test|prod) ;;
    *) echo "❌ Error: Environment must be 'dev', 'test', or 'prod'" >&2; exit 1 ;;
esac

# Get script directory and project root
ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
ENV_ROOT="$ROOT/env/$ENV_NAME"

# Create directory structure
echo "📁 Creating directory structure for $ENV_NAME..."
mkdir -p "$ENV_ROOT/code" "$ENV_ROOT/config" "$ENV_ROOT/data" "$ENV_ROOT/logs"

# Set port based on environment
case "$ENV_NAME" in
    dev) PORT=8000 ;;
    test) PORT=8181 ;;
    prod) PORT=8282 ;;
esac

# Create ports.json configuration
cat > "$ENV_ROOT/config/ports.json" << EOF
{
  "http_port": $PORT,
  "websocket_port": $((PORT + 1000)),
  "name": "$ENV_NAME"
}
EOF

# Create environment-specific .env template
CACHE_TTL=0
case "$ENV_NAME" in
    dev) CACHE_TTL=0 ;;
    test) CACHE_TTL=5 ;;
    prod) CACHE_TTL=300 ;;
esac

cat > "$ENV_ROOT/config/.env.template" << EOF
# Environment: $ENV_NAME
APP_ENV=$ENV_NAME
PORT=$PORT
LOG_LEVEL=INFO
ARTIFACTS_PATH=./artifacts/$ENV_NAME

# Database Configuration (fill in actual values)
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

# Create logging configuration
cat > "$ENV_ROOT/config/logging.json" << EOF
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

# Set proper permissions on POSIX systems
if [[ "$OSTYPE" != "cygwin" && "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then
    chmod 600 "$ENV_ROOT/config/.env.template"
    echo "🔒 Set secure permissions on .env.template (600)"
fi

echo "✅ Initialized $ENV_NAME environment at $ENV_ROOT"
echo "📁 Created directories: code, config, data, logs"
echo "🔧 Port configured: $PORT"
echo "⚠️  Remember to copy .env.template to .env and fill in actual secrets"